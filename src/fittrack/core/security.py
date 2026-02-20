"""Security utilities: password hashing (Argon2id) and JWT (RS256)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ── Password Hashing ────────────────────────────────────────────────

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,  # 64 MiB
    argon2__time_cost=3,
    argon2__parallelism=4,
)


def hash_password(plain: str) -> str:
    """Hash a plain-text password with Argon2id."""
    return str(pwd_context.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against an Argon2id hash."""
    try:
        return bool(pwd_context.verify(plain, hashed))
    except Exception:
        return False


def password_needs_rehash(hashed: str) -> bool:
    """Check whether a hash should be upgraded to current parameters."""
    return bool(pwd_context.needs_update(hashed))


# ── Password Complexity ─────────────────────────────────────────────

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def validate_password_complexity(password: str) -> list[str]:
    """Return a list of violation messages (empty = valid).

    Requirements:
    - 8–128 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    errors: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Password must be at most {MAX_PASSWORD_LENGTH} characters")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~" for c in password):
        errors.append("Password must contain at least one special character")
    return errors


# ── JWT Keys ─────────────────────────────────────────────────────────

_KEYS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "keys"

_private_key_cache: str | None = None
_public_key_cache: str | None = None

# HS256 symmetric secret (preferred — set via JWT_SECRET_KEY env var)
_jwt_secret: str | None = None


def _get_jwt_secret() -> str:
    """Get HS256 JWT secret from settings (cached)."""
    global _jwt_secret  # noqa: PLW0603
    if _jwt_secret is None:
        from fittrack.core.config import get_settings

        _jwt_secret = get_settings().jwt_secret_key
    return _jwt_secret


def _load_private_key() -> str:
    """Load RSA private key from file (cached). Fallback for RS256."""
    global _private_key_cache  # noqa: PLW0603
    if _private_key_cache is None:
        key_path = _KEYS_DIR / "dev_private.pem"
        if not key_path.exists():
            msg = f"JWT private key not found at {key_path}"
            raise FileNotFoundError(msg)
        _private_key_cache = key_path.read_text()
    return _private_key_cache


def _load_public_key() -> str:
    """Load RSA public key from file (cached). Fallback for RS256."""
    global _public_key_cache  # noqa: PLW0603
    if _public_key_cache is None:
        key_path = _KEYS_DIR / "dev_public.pem"
        if not key_path.exists():
            msg = f"JWT public key not found at {key_path}"
            raise FileNotFoundError(msg)
        _public_key_cache = key_path.read_text()
    return _public_key_cache


def _get_signing_key() -> str:
    """Get the signing key based on configured algorithm."""
    if ALGORITHM == "HS256":
        return _get_jwt_secret()
    return _load_private_key()


def _get_verify_key() -> str:
    """Get the verification key based on configured algorithm."""
    if ALGORITHM == "HS256":
        return _get_jwt_secret()
    return _load_public_key()


# ── JWT Token Operations ────────────────────────────────────────────

ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    role: str = "user",
    expires_minutes: int = 60,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + (expires_minutes * 60),
    }
    if extra_claims:
        payload.update(extra_claims)
    return str(jwt.encode(payload, _get_signing_key(), algorithm=ALGORITHM))


def create_refresh_token(
    subject: str,
    session_id: str,
    expires_days: int = 30,
) -> str:
    """Create a signed JWT refresh token tied to a session."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "sid": session_id,
        "type": "refresh",
        "iat": now,
        "exp": now + (expires_days * 86400),
    }
    return str(jwt.encode(payload, _get_signing_key(), algorithm=ALGORITHM))


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token. Raises JWTError on failure."""
    try:
        payload: dict[str, Any] = jwt.decode(token, _get_verify_key(), algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise


def decode_token_safe(token: str) -> dict[str, Any] | None:
    """Decode a JWT token, returning None on any error."""
    try:
        return decode_token(token)
    except (JWTError, Exception):
        return None
