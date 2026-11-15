import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass

from app.domain.consensus import MAX_PRICE_PLN, MIN_PRICE_PLN, SUPPORTED_FUEL_TYPES

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB limit for base64 image uploads


@dataclass(frozen=True)
class ExtractedPricesResult:
    """Result of fuel price extraction from a station pylon photo."""

    mode: str
    prices: dict[str, float | None]
    confidence_note: str


def decode_and_validate_image_base64(raw_base64: str) -> bytes:
    """Strip optional data-URL prefix, decode base64 image, and enforce size/non-empty checks."""
    cleaned = raw_base64.strip()
    if "," in cleaned and cleaned.lower().startswith("data:"):
        cleaned = cleaned.split(",", 1)[1].strip()
    if not cleaned:
        raise ValueError("Image payload cannot be empty")

    try:
        decoded = base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 image payload") from exc

    if not decoded:
        raise ValueError("Decoded image cannot be empty")
    if len(decoded) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds maximum allowed size of 5 MB")
    return decoded


def sanitize_extracted_prices(raw_prices: dict[str, object]) -> dict[str, float | None]:
    """Keep only supported fuel keys with prices inside [3.00, 15.00] PLN."""
    sanitized: dict[str, float | None] = {fuel: None for fuel in SUPPORTED_FUEL_TYPES}
    for fuel in SUPPORTED_FUEL_TYPES:
        val = raw_prices.get(fuel)
        if val is None or isinstance(val, bool):
            continue
        try:
            numeric = round(float(val), 2)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if MIN_PRICE_PLN <= numeric <= MAX_PRICE_PLN:
            sanitized[fuel] = numeric
    return sanitized


def parse_json_prices_from_text(text: str) -> dict[str, float | None]:
    """Extract a JSON object with fuel prices from raw LLM text output."""
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in model output")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Parsed model output must be a JSON object")
    return sanitize_extracted_prices(parsed)


def simulate_demo_extraction(
    image_bytes: bytes, filename: str | None = None
) -> ExtractedPricesResult:
    """Deterministically simulate pylon OCR from image bytes/filename for offline demo mode."""
    digest = hashlib.sha256(image_bytes).digest()
    base_pb95 = round(6.15 + (digest[0] % 45) / 100.0, 2)
    base_pb98 = round(base_pb95 + 0.65 + (digest[1] % 10) / 100.0, 2)
    base_on = round(base_pb95 + 0.08 + (digest[2] % 12) / 100.0, 2)
    base_lpg = round(3.00 + (digest[3] % 25) / 100.0, 2)

    prices: dict[str, float | None] = {
        "PB95": base_pb95,
        "PB98": base_pb98,
        "ON": base_on,
        "LPG": base_lpg,
    }

    # Allow test/demo filenames such as "pb95_6.29_on_6.39.jpg" to override simulated prices.
    if filename:
        for fuel in SUPPORTED_FUEL_TYPES:
            pattern = rf"{fuel.lower()}[_=\-\s]?(\d+[.,]\d{{2}})"
            match = re.search(pattern, filename.lower())
            if match:
                candidate = round(float(match.group(1).replace(",", ".")), 2)
                if MIN_PRICE_PLN <= candidate <= MAX_PRICE_PLN:
                    prices[fuel] = candidate

    return ExtractedPricesResult(
        mode="demo",
        prices=prices,
        confidence_note=(
            "Tryb demo AI (bez klucza API): wygenerowano przykładowy odczyt cen. "
            "Sprawdź i popraw wartości przed zapisaniem."
        ),
    )
