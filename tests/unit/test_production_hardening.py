"""Tests for CP8 security hardening — rate limiting, headers, CORS, logging."""

from __future__ import annotations

import logging
import time
from typing import Any
from unittest.mock import MagicMock, patch

from fittrack.api.middleware import (
    CSP_HEADER,
    HSTS_HEADER,
    RATE_LIMIT_WINDOW,
    SECURITY_HEADERS,
    _apply_rate_limit,
    _check_rate_limit,
    _get_client_key,
    _get_cors_origins,
    _rate_buckets,
)
from fittrack.core.context import get_correlation_id, set_correlation_id
from fittrack.core.logging import (
    REDACTED,
    JSONFormatter,
    RedactingFormatter,
    is_sensitive_key,
    redact_dict,
    redact_string,
    setup_logging,
)

# ── Rate Limiting ────────────────────────────────────────────────────


class TestRateLimiting:
    def setup_method(self) -> None:
        _rate_buckets.clear()

    def test_allows_first_request(self) -> None:
        allowed, remaining = _check_rate_limit("test:1", 10)
        assert allowed is True
        assert remaining == 9

    def test_blocks_after_limit(self) -> None:
        for _ in range(10):
            _check_rate_limit("test:2", 10)
        allowed, remaining = _check_rate_limit("test:2", 10)
        assert allowed is False
        assert remaining == 0

    def test_different_keys_independent(self) -> None:
        for _ in range(10):
            _check_rate_limit("test:a", 10)
        allowed, _ = _check_rate_limit("test:b", 10)
        assert allowed is True

    def test_expired_entries_pruned(self) -> None:
        key = "test:prune"
        # Insert old timestamps
        _rate_buckets[key] = [time.time() - RATE_LIMIT_WINDOW - 1] * 10
        allowed, _ = _check_rate_limit(key, 10)
        assert allowed is True

    def test_client_key_from_forwarded(self) -> None:
        req = MagicMock()
        req.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        assert _get_client_key(req) == "1.2.3.4"

    def test_client_key_from_client(self) -> None:
        req = MagicMock()
        req.headers = {}
        req.client.host = "10.0.0.1"
        assert _get_client_key(req) == "10.0.0.1"

    def test_client_key_no_client(self) -> None:
        req = MagicMock()
        req.headers = {}
        req.client = None
        assert _get_client_key(req) == "unknown"

    def test_rate_limit_skipped_in_testing(self) -> None:
        settings = MagicMock()
        settings.is_testing = True
        req = MagicMock()
        result = _apply_rate_limit(req, settings)
        assert result is None

    def test_rate_limit_skips_health(self) -> None:
        settings = MagicMock()
        settings.is_testing = False
        req = MagicMock()
        req.url.path = "/health"
        result = _apply_rate_limit(req, settings)
        assert result is None

    def test_rate_limit_skips_health_ready(self) -> None:
        settings = MagicMock()
        settings.is_testing = False
        req = MagicMock()
        req.url.path = "/health/ready"
        result = _apply_rate_limit(req, settings)
        assert result is None

    def test_rate_limit_skips_health_live(self) -> None:
        settings = MagicMock()
        settings.is_testing = False
        req = MagicMock()
        req.url.path = "/health/live"
        result = _apply_rate_limit(req, settings)
        assert result is None

    def test_rate_limit_anonymous_tier(self) -> None:
        _rate_buckets.clear()
        settings = MagicMock()
        settings.is_testing = False
        settings.rate_limit_anonymous = 2
        req = MagicMock()
        req.url.path = "/api/v1/test"
        req.headers = {}
        req.client.host = "1.1.1.1"
        _apply_rate_limit(req, settings)
        _apply_rate_limit(req, settings)
        result = _apply_rate_limit(req, settings)
        assert result is not None
        assert result.status_code == 429

    def test_rate_limit_user_tier(self) -> None:
        _rate_buckets.clear()
        settings = MagicMock()
        settings.is_testing = False
        settings.rate_limit_user = 2
        req = MagicMock()
        req.url.path = "/api/v1/test"
        req.headers = {"authorization": "Bearer faketoken"}
        req.client.host = "1.1.1.1"
        with patch("fittrack.core.security.decode_token_safe") as mock_dec:
            mock_dec.return_value = {"sub": "user1", "role": "user"}
            _apply_rate_limit(req, settings)
            _apply_rate_limit(req, settings)
            result = _apply_rate_limit(req, settings)
        assert result is not None
        assert result.status_code == 429

    def test_rate_limit_admin_tier(self) -> None:
        _rate_buckets.clear()
        settings = MagicMock()
        settings.is_testing = False
        settings.rate_limit_admin = 500
        req = MagicMock()
        req.url.path = "/api/v1/test"
        req.headers = {"authorization": "Bearer admintoken"}
        req.client.host = "1.1.1.1"
        with patch("fittrack.core.security.decode_token_safe") as mock_dec:
            mock_dec.return_value = {"sub": "admin1", "role": "admin"}
            result = _apply_rate_limit(req, settings)
        assert result is None

    def test_rate_limit_none_settings(self) -> None:
        req = MagicMock()
        assert _apply_rate_limit(req, None) is None


# ── Security Headers ────────────────────────────────────────────────


class TestSecurityHeaders:
    def test_security_headers_defined(self) -> None:
        assert "X-Content-Type-Options" in SECURITY_HEADERS
        assert "X-Frame-Options" in SECURITY_HEADERS
        assert "X-XSS-Protection" in SECURITY_HEADERS
        assert "Referrer-Policy" in SECURITY_HEADERS
        assert "Permissions-Policy" in SECURITY_HEADERS

    def test_x_frame_deny(self) -> None:
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"

    def test_nosniff(self) -> None:
        assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"

    def test_hsts_value(self) -> None:
        assert "max-age=" in HSTS_HEADER
        assert "includeSubDomains" in HSTS_HEADER

    def test_csp_value(self) -> None:
        assert "default-src" in CSP_HEADER
        assert "frame-ancestors 'none'" in CSP_HEADER

    def test_headers_on_response(self, client: Any) -> None:
        resp = client.get("/health")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-XSS-Protection"] == "1; mode=block"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "X-Request-ID" in resp.headers
        assert "X-Response-Time" in resp.headers


# ── CORS Configuration ──────────────────────────────────────────────


class TestCorsConfig:
    def test_cors_origins_none_settings(self) -> None:
        assert _get_cors_origins(None) == ["*"]

    def test_cors_origins_dev(self) -> None:
        settings = MagicMock()
        settings.is_production = False
        settings.cors_origin_list = ["*"]
        assert _get_cors_origins(settings) == ["*"]

    def test_cors_origins_prod(self) -> None:
        settings = MagicMock()
        settings.is_production = True
        del settings.cors_origin_list  # simulate no attribute
        assert _get_cors_origins(settings) == []


# ── Production Guards ────────────────────────────────────────────────


class TestProductionGuards:
    def test_dev_endpoints_accessible_in_dev(self, client: Any) -> None:
        resp = client.post("/api/v1/dev/seed")
        # Should be accessible (not 404)
        assert resp.status_code != 404

    def test_dev_endpoints_blocked_in_prod(self) -> None:
        from fittrack.core.config import Settings
        from fittrack.main import create_app

        settings = Settings(app_env="production")
        prod_app = create_app(settings=settings)
        from starlette.testclient import TestClient

        pclient = TestClient(prod_app)
        resp = pclient.post("/api/v1/dev/seed")
        assert resp.status_code == 404

    def test_static_blocked_in_prod(self) -> None:
        from fittrack.core.config import Settings
        from fittrack.main import create_app

        settings = Settings(app_env="production")
        prod_app = create_app(settings=settings)
        from starlette.testclient import TestClient

        pclient = TestClient(prod_app)
        resp = pclient.get("/static/test.html")
        assert resp.status_code == 404

    def test_hsts_only_in_prod(self) -> None:
        from fittrack.core.config import Settings
        from fittrack.main import create_app

        settings = Settings(app_env="production")
        prod_app = create_app(settings=settings)
        from starlette.testclient import TestClient

        pclient = TestClient(prod_app)
        resp = pclient.get("/health")
        assert "Strict-Transport-Security" in resp.headers

    def test_no_hsts_in_dev(self, client: Any) -> None:
        resp = client.get("/health")
        assert "Strict-Transport-Security" not in resp.headers


# ── Correlation ID ───────────────────────────────────────────────────


class TestCorrelationId:
    def test_set_and_get(self) -> None:
        set_correlation_id("abc123")
        assert get_correlation_id() == "abc123"

    def test_default_none(self) -> None:
        # contextvars are scoped per task, so a fresh context has None
        from fittrack.core.context import _correlation_id

        token = _correlation_id.set(None)
        try:
            assert get_correlation_id() is None
        finally:
            _correlation_id.reset(token)

    def test_correlation_id_in_response(self, client: Any) -> None:
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_custom_correlation_id_forwarded(self, client: Any) -> None:
        resp = client.get("/health", headers={"X-Correlation-ID": "my-trace-123"})
        assert resp.headers["X-Request-ID"] == "my-trace-123"


# ── Sensitive Field Redaction ────────────────────────────────────────


class TestRedaction:
    def test_sensitive_keys(self) -> None:
        assert is_sensitive_key("password") is True
        assert is_sensitive_key("PASSWORD") is True
        assert is_sensitive_key("user_password") is True
        assert is_sensitive_key("api_key") is True
        assert is_sensitive_key("apiKey") is True
        assert is_sensitive_key("secret") is True
        assert is_sensitive_key("authorization") is True
        assert is_sensitive_key("token") is True

    def test_non_sensitive_keys(self) -> None:
        assert is_sensitive_key("email") is False
        assert is_sensitive_key("username") is False
        assert is_sensitive_key("status") is False

    def test_redact_dict_simple(self) -> None:
        data = {"username": "john", "password": "secret123", "email": "j@x.com"}
        result = redact_dict(data)
        assert result["username"] == "john"
        assert result["password"] == REDACTED
        assert result["email"] == "j@x.com"

    def test_redact_dict_nested(self) -> None:
        data = {"user": {"name": "john", "api_key": "abc"}}
        result = redact_dict(data)
        assert result["user"]["api_key"] == REDACTED
        assert result["user"]["name"] == "john"

    def test_redact_dict_list(self) -> None:
        data = {"users": [{"password": "x"}, {"email": "a@b.com"}]}
        result = redact_dict(data)
        assert result["users"][0]["password"] == REDACTED
        assert result["users"][1]["email"] == "a@b.com"

    def test_redact_string_authorization(self) -> None:
        text = "Authorization: Bearer eyJhbGciOi..."
        result = redact_string(text)
        assert "eyJhbGciOi" not in result
        assert REDACTED in result

    def test_redact_string_password(self) -> None:
        text = "password=secretvalue123"
        result = redact_string(text)
        assert "secretvalue" not in result

    def test_redact_string_token(self) -> None:
        text = "token=abc123def"
        result = redact_string(text)
        assert "abc123def" not in result


# ── Structured Logging ───────────────────────────────────────────────


class TestStructuredLogging:
    def test_json_formatter_format(self) -> None:
        import json

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello %s",
            args=("World",),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Hello World"
        assert "timestamp" in parsed
        assert parsed["logger"] == "test"

    def test_json_formatter_redacts(self) -> None:
        import json

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Login with password=secret123",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "secret123" not in parsed["message"]

    def test_json_formatter_exception(self) -> None:
        import json
        import sys

        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Failed",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "test error"

    def test_redacting_formatter(self) -> None:
        formatter = RedactingFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Authorization: Bearer mytoken123",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "mytoken123" not in output

    def test_setup_logging_text(self) -> None:
        setup_logging(level="INFO", log_format="text")
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) > 0

    def test_setup_logging_json(self) -> None:
        setup_logging(level="DEBUG", log_format="json")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_setup_logging_clears_handlers(self) -> None:
        setup_logging(level="INFO", log_format="text")
        setup_logging(level="INFO", log_format="text")
        root = logging.getLogger()
        # Should not have duplicated handlers
        handler_count = len(root.handlers)
        assert handler_count == 1


# ── Health Probes ────────────────────────────────────────────────────


class TestHealthProbes:
    def test_health_endpoint(self, client: Any) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["environment"] == "testing"

    def test_liveness_probe(self, client: Any) -> None:
        resp = client.get("/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"

    def test_readiness_probe(self, client: Any) -> None:
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ready", "not_ready")
        assert "checks" in data

    def test_readiness_db_not_configured(self, client: Any) -> None:
        resp = client.get("/health/ready")
        data = resp.json()
        assert data["checks"]["database"]["status"] == "not_configured"


# ── Config ───────────────────────────────────────────────────────────


class TestConfig:
    def test_default_settings(self) -> None:
        from fittrack.core.config import Settings

        s = Settings()
        assert s.app_env == "development"
        assert s.rate_limit_anonymous == 10
        assert s.rate_limit_user == 100
        assert s.rate_limit_admin == 500
        assert s.log_level == "INFO"
        assert s.log_format == "text"
        assert s.cors_origins == "*"

    def test_cors_origin_list_wildcard(self) -> None:
        from fittrack.core.config import Settings

        s = Settings(cors_origins="*")
        assert s.cors_origin_list == ["*"]

    def test_cors_origin_list_multiple(self) -> None:
        from fittrack.core.config import Settings

        s = Settings(cors_origins="https://a.com, https://b.com")
        assert s.cors_origin_list == ["https://a.com", "https://b.com"]

    def test_is_production(self) -> None:
        from fittrack.core.config import Settings

        s = Settings(app_env="production")
        assert s.is_production is True
        assert s.is_development is False

    def test_is_testing(self) -> None:
        from fittrack.core.config import Settings

        s = Settings(app_env="testing")
        assert s.is_testing is True


# ── GZip Compression ────────────────────────────────────────────────


class TestCompression:
    def test_gzip_accepted(self, client: Any) -> None:
        resp = client.get("/health", headers={"Accept-Encoding": "gzip"})
        # Small responses may not be compressed (>500 byte minimum)
        assert resp.status_code == 200


# ── DB Query Timing ─────────────────────────────────────────────────


class TestQueryTiming:
    def test_log_query_slow(self) -> None:
        from fittrack.repositories.base import BaseRepository

        repo = BaseRepository(pool=MagicMock(), table_name="t", id_column="id")
        with patch("fittrack.repositories.base.logger") as mock_logger:
            repo._log_query("SELECT * FROM t", 150.0)
            mock_logger.warning.assert_called_once()

    def test_log_query_fast(self) -> None:
        from fittrack.repositories.base import BaseRepository

        repo = BaseRepository(pool=MagicMock(), table_name="t", id_column="id")
        with patch("fittrack.repositories.base.logger") as mock_logger:
            repo._log_query("SELECT * FROM t", 5.0)
            mock_logger.debug.assert_called_once()

    def test_slow_query_threshold(self) -> None:
        from fittrack.repositories.base import SLOW_QUERY_THRESHOLD_MS

        assert SLOW_QUERY_THRESHOLD_MS == 100
