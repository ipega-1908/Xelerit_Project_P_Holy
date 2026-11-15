import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta

from app.domain.benefits import ensure_utc

DEFAULT_TOKEN_TTL_HOURS = 12


def verify_admin_credentials(
    username: str,
    password: str,
    expected_username: str,
    expected_password: str,
) -> bool:
    """Compare submitted admin credentials against configured values in constant time."""
    if not expected_username or not expected_password:
        return False
    username_ok = hmac.compare_digest(username.encode("utf-8"), expected_username.encode("utf-8"))
    password_ok = hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8"))
    return username_ok and password_ok


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(f"{encoded}{padding}".encode("ascii"))


def _sign_segment(segment: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        segment.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def create_admin_token(
    username: str,
    secret: str,
    now: datetime,
    ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS,
) -> tuple[str, datetime]:
    """Issue a signed HMAC-SHA256 admin token valid until now + ttl_hours."""
    if not username.strip() or not secret:
        raise ValueError("Username and signing secret must be non-empty")

    now_utc = ensure_utc(now)
    expires_at = now_utc + timedelta(hours=ttl_hours)
    payload_bytes = json.dumps(
        {"sub": username, "exp": int(expires_at.timestamp())},
        separators=(",", ":"),
    ).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)
    signature_part = _sign_segment(payload_part, secret)
    return f"{payload_part}.{signature_part}", expires_at


def verify_admin_token(token: str, secret: str, now: datetime) -> str:
    """Verify HMAC signature and expiry of an admin token; return admin username."""
    if not token or "." not in token or not secret:
        raise ValueError("Invalid admin token")

    payload_part, signature_part = token.split(".", 1)
    expected_sig = _sign_segment(payload_part, secret)
    if not hmac.compare_digest(signature_part.encode("ascii"), expected_sig.encode("ascii")):
        raise ValueError("Invalid admin token signature")

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed admin token payload") from exc

    sub = payload.get("sub")
    exp = payload.get("exp")
    if not isinstance(sub, str) or not sub.strip() or not isinstance(exp, int):
        raise ValueError("Invalid admin token claims")

    now_ts = int(ensure_utc(now).timestamp())
    if now_ts >= exp:
        raise ValueError("Admin session expired")

    return sub
