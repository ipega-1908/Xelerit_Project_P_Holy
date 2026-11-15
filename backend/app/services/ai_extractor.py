import base64
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException, status

from app.domain.price_extraction import (
    ExtractedPricesResult,
    decode_and_validate_image_base64,
    parse_json_prices_from_text,
    simulate_demo_extraction,
)
from app.schemas import PriceExtractionRequest, PriceExtractionResponse

logger = logging.getLogger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_GEMINI_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
)
_NON_TEXT_FLASH_MARKERS = ("image", "tts", "audio", "live", "robotics", "computer-use", "thinking")
_RETRIABLE_HTTP_CODES = {404, 429, 500, 502, 503, 504}


def _extract_http_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return str(exc.reason or exc)

    if not raw:
        return str(exc.reason or exc)

    try:
        parsed = json.loads(raw)
        message = parsed.get("error", {}).get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    except json.JSONDecodeError:
        pass
    return raw


def _discover_flash_models(api_key: str) -> list[str]:
    """Query Gemini API for flash models supporting generateContent for this API key."""
    req = urllib.request.Request(
        f"{_GEMINI_BASE_URL}/models",
        headers={"x-goog-api-key": api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    discovered: list[str] = []
    for entry in body.get("models", []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", ""))
        methods = entry.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        model_id = name.removeprefix("models/")
        lowered = model_id.lower()
        if (
            "flash" in lowered
            and model_id
            and not any(marker in lowered for marker in _NON_TEXT_FLASH_MARKERS)
        ):
            discovered.append(model_id)
    return discovered


def _thinking_config_for_model(model_id: str) -> dict[str, Any] | None:
    """Minimize internal reasoning latency on Gemini 2.5 / 3.x models for fast OCR."""
    lowered = model_id.lower()
    if "2.5" in lowered:
        return {"thinkingBudget": 0}
    if "3." in lowered or "flash-latest" in lowered:
        return {"thinkingLevel": "MINIMAL"}
    return None


def _build_gemini_payload(
    encoded_image: str,
    mime_type: str,
    model_id: str,
    *,
    include_thinking_config: bool = True,
) -> dict[str, Any]:
    generation_config: dict[str, Any] = {
        "responseMimeType": "application/json",
        "temperature": 0.1,
        "maxOutputTokens": 1024,
    }
    if include_thinking_config:
        thinking_cfg = _thinking_config_for_model(model_id)
        if thinking_cfg is not None:
            generation_config["thinkingConfig"] = thinking_cfg

    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Read fuel prices in PLN per liter from this gas station price board. "
                            "Return ONLY a JSON object with keys PB95, PB98, ON, LPG "
                            "(float or null if not visible)."
                        )
                    },
                    {"inline_data": {"mime_type": mime_type, "data": encoded_image}},
                ]
            }
        ],
        "generationConfig": generation_config,
    }


def _extract_response_text(body: dict[str, Any]) -> str:
    parts = body["candidates"][0]["content"]["parts"]
    text_chunks = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and not part.get("thought") and isinstance(part.get("text"), str)
    ]
    if not text_chunks:
        raise ValueError("Gemini response contained no text output")
    return "\n".join(text_chunks)


def _call_gemini_generate_content(
    model_id: str,
    payload: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    url = f"{_GEMINI_BASE_URL}/models/{model_id}:generateContent"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return dict(json.loads(resp.read().decode("utf-8")))


def _append_discovered_models(candidates: list[str], api_key: str) -> None:
    for found in _discover_flash_models(api_key):
        if found not in candidates:
            candidates.append(found)


def _extract_with_gemini(
    image_bytes: bytes,
    mime_type: str,
    api_key: str,
) -> ExtractedPricesResult:
    encoded = base64.b64encode(image_bytes).decode("ascii")

    configured = os.getenv("GEMINI_MODEL", "").strip()
    candidates: list[str] = []
    for candidate in ([configured] if configured else []) + list(_DEFAULT_GEMINI_MODELS):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    discovered_added = False
    last_error_detail = "No responsive Gemini flash model found"
    idx = 0

    while idx < len(candidates):
        model_id = candidates[idx]
        idx += 1
        payload = _build_gemini_payload(encoded, mime_type, model_id, include_thinking_config=True)
        try:
            try:
                body = _call_gemini_generate_content(model_id, payload, api_key)
            except urllib.error.HTTPError as exc:
                # Some model aliases reject thinkingConfig with HTTP 400; retry once without it.
                if exc.code == 400 and "thinkingConfig" in payload["generationConfig"]:
                    fallback_payload = _build_gemini_payload(
                        encoded,
                        mime_type,
                        model_id,
                        include_thinking_config=False,
                    )
                    body = _call_gemini_generate_content(model_id, fallback_payload, api_key)
                else:
                    raise

            text = _extract_response_text(body)
            prices = parse_json_prices_from_text(text)
            return ExtractedPricesResult(
                mode="gemini",
                prices=prices,
                confidence_note=(
                    f"Odczytano ceny ze zdjęcia przez Gemini AI ({model_id}). "
                    "Sprawdź wartości przed zapisem."
                ),
            )
        except urllib.error.HTTPError as exc:
            detail = _extract_http_error_detail(exc)
            logger.warning("Gemini API HTTP %s on model %s: %s", exc.code, model_id, detail)
            if exc.code in _RETRIABLE_HTTP_CODES:
                last_error_detail = f"({exc.code}): {detail}"
                if not discovered_added:
                    discovered_added = True
                    _append_discovered_models(candidates, api_key)
                continue
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI vision service failed ({exc.code}): {detail}",
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning("Gemini API transport/timeout failure on model %s: %s", model_id, exc)
            last_error_detail = str(exc)
            if not discovered_added:
                discovered_added = True
                _append_discovered_models(candidates, api_key)
            continue
        except (KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Gemini API parse failure on model %s: %s", model_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI vision service failed: {exc}",
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"AI vision service failed {last_error_detail}",
    )


def extract_prices_from_image(payload: PriceExtractionRequest) -> PriceExtractionResponse:
    """Extract fuel prices using Gemini API when configured, falling back to demo mode."""
    try:
        image_bytes = decode_and_validate_image_base64(payload.image_base64)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            result = _extract_with_gemini(image_bytes, payload.mime_type, api_key)
        except HTTPException as exc:
            # Keep the demo usable when a configured key is expired, rate-limited, or offline.
            logger.warning("Gemini AI failed (%s); falling back to demo extraction", exc.detail)
            demo_result = simulate_demo_extraction(image_bytes, payload.filename)
            result = ExtractedPricesResult(
                mode=demo_result.mode,
                prices=demo_result.prices,
                confidence_note=(
                    "Gemini AI jest niedostępne lub przekroczono limit — "
                    "użyto przykładowego odczytu (tryb demo)."
                ),
            )
    else:
        result = simulate_demo_extraction(image_bytes, payload.filename)

    return PriceExtractionResponse(
        mode=result.mode,
        prices=result.prices,  # type: ignore[arg-type]
        confidence_note=result.confidence_note,
    )
