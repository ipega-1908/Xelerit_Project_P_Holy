import base64
import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.price_extraction import parse_json_prices_from_text


def test_parse_json_prices_filters_invalid_values() -> None:
    raw = '```json\n{"PB95": 6.39, "PB98": 25.0, "ON": null, "LPG": 3.05}\n```'
    parsed = parse_json_prices_from_text(raw)
    assert parsed == {
        "PB95": 6.39,
        "PB98": None,  # out of [3.00, 15.00]
        "ON": None,
        "LPG": 3.05,
    }


def test_ai_extract_prices_demo_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sample_b64 = base64.b64encode(b"fake-jpeg-pylon-bytes").decode("ascii")
    response = client.post(
        "/ai/extract-prices",
        json={
            "image_base64": f"data:image/jpeg;base64,{sample_b64}",
            "mime_type": "image/jpeg",
            "filename": "stacja_pb95_6.29_on_6.49.jpg",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "demo"
    assert body["prices"]["PB95"] == 6.29
    assert body["prices"]["ON"] == 6.49
    assert 3.00 <= body["prices"]["PB98"] <= 15.00
    assert 3.00 <= body["prices"]["LPG"] <= 15.00


def test_ai_extract_prices_rejects_invalid_base64(client: TestClient) -> None:
    response = client.post(
        "/ai/extract-prices",
        json={"image_base64": "not-valid-base64!!!"},
    )
    assert response.status_code == 422


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_ai_extract_prices_gemini_falls_back_on_404_via_models_discovery(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "missing-model")
    called_urls: list[str] = []

    def _fake_urlopen(req: urllib.request.Request, timeout: int = 15) -> _FakeHttpResponse:
        del timeout
        called_urls.append(req.full_url)
        assert req.get_header("X-goog-api-key") == "fake-test-key"

        if req.full_url.endswith("/v1beta/models"):
            return _FakeHttpResponse(
                {
                    "models": [
                        {
                            "name": "models/gemini-discovered-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                }
            )
        if "gemini-discovered-flash:generateContent" in req.full_url:
            return _FakeHttpResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {"PB95": 6.41, "PB98": None, "ON": 6.55, "LPG": 3.09}
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
        raise urllib.error.HTTPError(
            req.full_url,
            404,
            "Not Found",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"error": {"message": "models/foo is not found"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    sample_b64 = base64.b64encode(b"fake-jpeg-pylon-bytes").decode("ascii")
    response = client.post(
        "/ai/extract-prices",
        json={"image_base64": sample_b64, "mime_type": "image/jpeg"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "gemini"
    assert body["prices"] == {"PB95": 6.41, "PB98": None, "ON": 6.55, "LPG": 3.09}
    assert "gemini-discovered-flash" in body["confidence_note"]
    assert any(url.endswith("/v1beta/models") for url in called_urls)


def test_ai_extract_prices_gemini_sends_minimal_thinking_and_skips_thoughts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    captured_payload: dict[str, Any] = {}

    def _fake_urlopen(req: urllib.request.Request, timeout: int = 20) -> _FakeHttpResponse:
        assert timeout == 20
        assert req.data is not None
        captured_payload.update(json.loads(req.data.decode("utf-8")))
        return _FakeHttpResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "internal reasoning", "thought": True},
                                {
                                    "text": json.dumps(
                                        {"PB95": 6.19, "PB98": 6.89, "ON": 6.39, "LPG": None}
                                    )
                                },
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    sample_b64 = base64.b64encode(b"fake-jpeg-pylon-bytes").decode("ascii")
    response = client.post(
        "/ai/extract-prices",
        json={"image_base64": sample_b64, "mime_type": "image/jpeg"},
    )
    assert response.status_code == 200
    assert response.json()["prices"] == {"PB95": 6.19, "PB98": 6.89, "ON": 6.39, "LPG": None}
    assert captured_payload["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}


def test_ai_extract_prices_gemini_falls_back_after_timeout(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    attempted_models: list[str] = []

    def _fake_urlopen(req: urllib.request.Request, timeout: int = 20) -> _FakeHttpResponse:
        del timeout
        if req.full_url.endswith("/v1beta/models"):
            return _FakeHttpResponse(
                {
                    "models": [
                        {
                            "name": "models/gemini-flash-fallback",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                }
            )
        attempted_models.append(req.full_url)
        if "gemini-flash-fallback:generateContent" in req.full_url:
            return _FakeHttpResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {"PB95": 6.29, "PB98": 6.99, "ON": 6.45, "LPG": 3.05}
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    sample_b64 = base64.b64encode(b"fake-jpeg-pylon-bytes").decode("ascii")
    response = client.post(
        "/ai/extract-prices",
        json={"image_base64": sample_b64, "mime_type": "image/jpeg"},
    )
    assert response.status_code == 200
    assert response.json()["prices"] == {"PB95": 6.29, "PB98": 6.99, "ON": 6.45, "LPG": 3.05}
    assert len(attempted_models) >= 2
    assert "gemini-flash-fallback" in response.json()["confidence_note"]
