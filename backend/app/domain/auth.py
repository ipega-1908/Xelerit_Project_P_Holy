import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.domain.benefits import ensure_utc

DEFAULT_TOKEN_TTL_HOURS = 12
PBKDF2_ITERATIONS = 100_000

RoleType = Literal["user", "admin"]


@dataclass(frozen=True)
class AuthActor:
    """Verified identity extracted from a signed session bearer token."""

    username: str
    role: RoleType
    user_id: int | None = None


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random 16-byte salt."""
    if not password:
        raise ValueError("Password must be non-empty")
    salt_bytes = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64url_encode(salt_bytes)}${_b64url_encode(digest)}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2-HMAC-SHA256 hash."""
    if not password or not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
        salt_bytes = _b64url_decode(parts[2])
        expected_digest = _b64url_decode(parts[3])
    except ValueError:
        return False
    if iterations <= 0:
        return False
    computed_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        iterations,
    )
    return hmac.compare_digest(computed_digest, expected_digest)


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


def create_session_token(
    actor: AuthActor,
    secret: str,
    now: datetime,
    ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS,
) -> tuple[str, datetime]:
    """Issue a signed HMAC-SHA256 bearer token for a driver or admin session."""
    if not actor.username.strip() or not secret:
        raise ValueError("Username and signing secret must be non-empty")
    if actor.role == "user" and actor.user_id is None:
        raise ValueError("User session token requires a numeric user_id")

    now_utc = ensure_utc(now)
    expires_at = now_utc + timedelta(hours=ttl_hours)
    payload_bytes = json.dumps(
        {
            "sub": actor.username,
            "role": actor.role,
            "uid": actor.user_id,
            "exp": int(expires_at.timestamp()),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)
    signature_part = _sign_segment(payload_part, secret)
    return f"{payload_part}.{signature_part}", expires_at


def verify_session_token(token: str, secret: str, now: datetime) -> AuthActor:
    """Verify HMAC signature and expiry of a session token and return its AuthActor."""
    if not token or "." not in token or not secret:
        raise ValueError("Invalid session token")

    payload_part, signature_part = token.split(".", 1)
    expected_sig = _sign_segment(payload_part, secret)
    if not hmac.compare_digest(signature_part.encode("ascii"), expected_sig.encode("ascii")):
        raise ValueError("Invalid session token signature")

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed session token payload") from exc

    sub = payload.get("sub")
    role = payload.get("role", "admin")
    uid = payload.get("uid")
    exp = payload.get("exp")
    if not isinstance(sub, str) or not sub.strip() or not isinstance(exp, int):
        raise ValueError("Invalid session token claims")
    if role not in ("user", "admin"):
        raise ValueError("Invalid session token role")
    if uid is not None and (isinstance(uid, bool) or not isinstance(uid, int)):
        raise ValueError("Invalid session token user_id")
    if role == "user" and uid is None:
        raise ValueError("User session token missing user_id")

    now_ts = int(ensure_utc(now).timestamp())
    if now_ts >= exp:
        raise ValueError("Session expired")

    return AuthActor(username=sub, role=role, user_id=uid)


def create_admin_token(
    username: str,
    secret: str,
    now: datetime,
    ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS,
) -> tuple[str, datetime]:
    """Issue a signed HMAC-SHA256 admin token valid until now + ttl_hours."""
    return create_session_token(
        AuthActor(username=username, role="admin", user_id=None),
        secret=secret,
        now=now,
        ttl_hours=ttl_hours,
    )


def verify_admin_token(token: str, secret: str, now: datetime) -> str:
    """Verify HMAC signature and expiry of an admin token; return admin username."""
    actor = verify_session_token(token=token, secret=secret, now=now)
    if actor.role != "admin":
        raise ValueError("Admin role required")
    return actor.username
