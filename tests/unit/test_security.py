"""Tests for password hashing, JWT encode/decode, and password complexity."""

from __future__ import annotations

import time

import pytest

from fittrack.core.security import (
    ALGORITHM,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_token_safe,
    hash_password,
    password_needs_rehash,
    validate_password_complexity,
    verify_password,
)

# ── Password Hashing ────────────────────────────────────────────────


class TestPasswordHashing:
    """Tests for Argon2id password hashing."""

    def test_hash_password_returns_argon2_hash(self) -> None:
        hashed = hash_password("Str0ng!Pass")
        assert hashed.startswith("$argon2")

    def test_verify_correct_password(self) -> None:
        hashed = hash_password("Str0ng!Pass")
        assert verify_password("Str0ng!Pass", hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("Str0ng!Pass")
        assert verify_password("WrongPass1!", hashed) is False

    def test_verify_empty_password(self) -> None:
        hashed = hash_password("Str0ng!Pass")
        assert verify_password("", hashed) is False

    def test_verify_invalid_hash(self) -> None:
        assert verify_password("Str0ng!Pass", "not-a-hash") is False

    def test_different_passwords_different_hashes(self) -> None:
        h1 = hash_password("Str0ng!Pass1")
        h2 = hash_password("Str0ng!Pass2")
        assert h1 != h2

    def test_same_password_different_salt(self) -> None:
        h1 = hash_password("Str0ng!Pass")
        h2 = hash_password("Str0ng!Pass")
        assert h1 != h2  # Different salts

    def test_password_needs_rehash_current(self) -> None:
        hashed = hash_password("Str0ng!Pass")
        assert password_needs_rehash(hashed) is False


# ── Password Complexity ─────────────────────────────────────────────


class TestPasswordComplexity:
    """Tests for password validation rules."""

    def test_valid_password(self) -> None:
        errors = validate_password_complexity("Str0ng!Pass")
        assert errors == []

    def test_too_short(self) -> None:
        errors = validate_password_complexity("Ab1!")
        assert any(str(MIN_PASSWORD_LENGTH) in e for e in errors)

    def test_too_long(self) -> None:
        errors = validate_password_complexity("A" * (MAX_PASSWORD_LENGTH + 1) + "a1!")
        assert any(str(MAX_PASSWORD_LENGTH) in e for e in errors)

    def test_missing_uppercase(self) -> None:
        errors = validate_password_complexity("str0ng!pass")
        assert any("uppercase" in e for e in errors)

    def test_missing_lowercase(self) -> None:
        errors = validate_password_complexity("STR0NG!PASS")
        assert any("lowercase" in e for e in errors)

    def test_missing_digit(self) -> None:
        errors = validate_password_complexity("Strong!Pass")
        assert any("digit" in e for e in errors)

    def test_missing_special(self) -> None:
        errors = validate_password_complexity("Str0ngPass1")
        assert any("special" in e for e in errors)

    def test_all_violations(self) -> None:
        errors = validate_password_complexity("abc")
        assert len(errors) >= 3  # too short, no uppercase, no digit, no special

    def test_exact_min_length(self) -> None:
        errors = validate_password_complexity("Aa1!" + "x" * 4)
        assert not any(str(MIN_PASSWORD_LENGTH) in e for e in errors)

    def test_special_characters_accepted(self) -> None:
        for char in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~":
            pwd = f"Str0ng{char}Pass"
            errors = validate_password_complexity(pwd)
            assert not any("special" in e for e in errors), f"Special char '{char}' not accepted"


# ── JWT Token Operations ────────────────────────────────────────────


class TestJWT:
    """Tests for JWT creation and verification."""

    def test_create_and_decode_access_token(self) -> None:
        token = create_access_token(subject="user123", role="user")
        payload = decode_token(token)
        assert payload["sub"] == "user123"
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_access_token_default_expiry(self) -> None:
        token = create_access_token(subject="user123")
        payload = decode_token(token)
        assert payload["exp"] - payload["iat"] == 60 * 60  # 1 hour

    def test_access_token_custom_expiry(self) -> None:
        token = create_access_token(subject="user123", expires_minutes=30)
        payload = decode_token(token)
        assert payload["exp"] - payload["iat"] == 30 * 60

    def test_access_token_extra_claims(self) -> None:
        token = create_access_token(
            subject="user123",
            extra_claims={"email": "test@example.com"},
        )
        payload = decode_token(token)
        assert payload["email"] == "test@example.com"

    def test_create_and_decode_refresh_token(self) -> None:
        token = create_refresh_token(subject="user123", session_id="sess456")
        payload = decode_token(token)
        assert payload["sub"] == "user123"
        assert payload["sid"] == "sess456"
        assert payload["type"] == "refresh"

    def test_refresh_token_default_expiry(self) -> None:
        token = create_refresh_token(subject="user123", session_id="sess456")
        payload = decode_token(token)
        assert payload["exp"] - payload["iat"] == 30 * 86400  # 30 days

    def test_decode_invalid_token(self) -> None:
        from jose import JWTError

        with pytest.raises(JWTError):
            decode_token("invalid.token.here")

    def test_decode_tampered_token(self) -> None:
        from jose import JWTError

        token = create_access_token(subject="user123")
        # Tamper with payload
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_decode_safe_returns_none_on_invalid(self) -> None:
        result = decode_token_safe("invalid.token.here")
        assert result is None

    def test_decode_safe_returns_payload_on_valid(self) -> None:
        token = create_access_token(subject="user123")
        result = decode_token_safe(token)
        assert result is not None
        assert result["sub"] == "user123"

    def test_algorithm_is_hs256(self) -> None:
        assert ALGORITHM == "HS256"

    def test_admin_role_in_token(self) -> None:
        token = create_access_token(subject="admin1", role="admin")
        payload = decode_token(token)
        assert payload["role"] == "admin"

    def test_premium_role_in_token(self) -> None:
        token = create_access_token(subject="prem1", role="premium")
        payload = decode_token(token)
        assert payload["role"] == "premium"

    def test_expired_token(self) -> None:
        """Create a token that has already expired."""
        from jose import JWTError

        token = create_access_token(subject="user123", expires_minutes=-1)
        with pytest.raises(JWTError):
            decode_token(token)

    def test_token_contains_iat(self) -> None:
        before = int(time.time())
        token = create_access_token(subject="user123")
        after = int(time.time())
        payload = decode_token(token)
        assert before <= payload["iat"] <= after
