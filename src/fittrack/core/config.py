"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """FitTrack application settings."""

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    log_level: str = "INFO"
    log_format: str = "text"  # "text" or "json"

    # Oracle Database
    oracle_dsn: str = "localhost:1521/FREEPDB1"
    oracle_user: str = "fittrack"
    oracle_password: str = "FitTrack_Dev_2026!"
    oracle_pool_min: int = 2
    oracle_pool_max: int = 10
    oracle_pool_increment: int = 1

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # CORS
    cors_origins: str = "*"  # Comma-separated origins; "*" for dev only

    # Rate Limiting (requests per minute)
    rate_limit_anonymous: int = 10
    rate_limit_user: int = 100
    rate_limit_admin: int = 500

    # Security
    secret_key: str = "23e08e1edd45cbcef9993a94ba3b8f3c"

    # JWT secret (HS256 symmetric key — used instead of RSA PEM files)
    jwt_secret_key: str = "c1651a382458f6cbcef61fd3ccae78238c"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_testing(self) -> bool:
        return self.app_env == "testing"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
