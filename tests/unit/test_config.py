"""Tests for application configuration loading."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from fittrack.core.config import Settings, get_settings


class TestSettingsDefaults:
    """Settings should load with sane defaults (no .env required)."""

    def test_settings_loads_without_env_file(self):
        """Settings can be constructed with zero env vars (all defaults)."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
        assert s.app_env == "development"
        assert s.oracle_dsn == "localhost:1521/FREEPDB1"
        assert s.redis_url == "redis://localhost:6379/0"

    def test_default_env_is_development(self):
        s = Settings(_env_file=None)
        assert s.is_development is True
        assert s.is_production is False
        assert s.is_testing is False

    def test_oracle_defaults(self):
        s = Settings(_env_file=None)
        assert s.oracle_dsn == "localhost:1521/FREEPDB1"
        assert s.oracle_user == "fittrack"
        assert s.oracle_pool_min == 2
        assert s.oracle_pool_max == 10

    def test_redis_defaults(self):
        s = Settings(_env_file=None)
        assert s.redis_url == "redis://localhost:6379/0"

    def test_jwt_defaults(self):
        s = Settings(_env_file=None)
        assert s.jwt_algorithm == "HS256"
        assert s.jwt_access_token_expire_minutes == 60
        assert s.jwt_refresh_token_expire_days == 30
        assert s.jwt_secret_key  # not empty

    def test_cors_defaults(self):
        s = Settings(_env_file=None)
        assert s.cors_origins == "*"
        assert s.cors_origin_list == ["*"]

    def test_rate_limit_defaults(self):
        s = Settings(_env_file=None)
        assert s.rate_limit_anonymous == 10
        assert s.rate_limit_user == 100
        assert s.rate_limit_admin == 500

    def test_secret_key_present(self):
        s = Settings(_env_file=None)
        assert len(s.secret_key) >= 16


class TestSettingsFromEnv:
    """Settings load from environment variables correctly."""

    def test_override_via_env(self):
        overrides = {
            "APP_ENV": "production",
            "ORACLE_DSN": "prod-host:1521/proddb",
            "REDIS_URL": "redis://prod-redis:6379/1",
        }
        with patch.dict(os.environ, overrides, clear=False):
            s = Settings(_env_file=None)
        assert s.app_env == "production"
        assert s.is_production is True
        assert s.oracle_dsn == "prod-host:1521/proddb"
        assert s.redis_url == "redis://prod-redis:6379/1"

    def test_cors_parsing_multiple(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": "http://a.com, http://b.com"}, clear=False):
            s = Settings(_env_file=None)
        assert s.cors_origin_list == ["http://a.com", "http://b.com"]

    def test_extra_fields_ignored(self):
        """Unknown env vars do not crash Settings (extra='ignore')."""
        with patch.dict(os.environ, {"SOME_RANDOM_VAR": "xyz"}, clear=False):
            s = Settings(_env_file=None)
        assert not hasattr(s, "some_random_var")


class TestEnvExampleFile:
    """.env.example should be parseable and consistent."""

    def test_env_example_exists(self):
        env_example = Path(__file__).resolve().parents[2] / ".env.example"
        assert env_example.exists(), ".env.example not found at project root"

    def test_env_example_has_required_keys(self):
        env_example = Path(__file__).resolve().parents[2] / ".env.example"
        content = env_example.read_text()
        required = [
            "APP_ENV",
            "ORACLE_DSN",
            "ORACLE_USER",
            "ORACLE_PASSWORD",
            "REDIS_URL",
            "JWT_SECRET_KEY",
            "JWT_ALGORITHM",
            "SECRET_KEY",
        ]
        for key in required:
            assert key in content, f".env.example missing {key}"

    def test_env_example_dsn_is_localhost(self):
        env_example = Path(__file__).resolve().parents[2] / ".env.example"
        content = env_example.read_text()
        assert "localhost:1521/FREEPDB1" in content, "ORACLE_DSN should default to localhost"

    def test_env_example_redis_is_localhost(self):
        env_example = Path(__file__).resolve().parents[2] / ".env.example"
        content = env_example.read_text()
        assert "redis://localhost:6379/0" in content, "REDIS_URL should default to localhost"


class TestGetSettings:
    """get_settings() factory function."""

    def test_returns_settings_instance(self):
        s = get_settings()
        assert isinstance(s, Settings)
