from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Organ Donor Matching Platform"
    env: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    database_url: str = Field(default="postgresql+psycopg://app:apppass@localhost:5432/organ_match")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    jwt_secret: str = "development-only-change-me"
    totp_encryption_key: str = "development-only-totp-key-change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    otp_expiry_minutes: int = 10
    otp_max_attempts: int = 5
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.env.lower() == "production":
            if self.jwt_secret == "development-only-change-me" or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be a unique secret of at least 32 characters")
            if (
                self.totp_encryption_key == "development-only-totp-key-change-me"
                or len(self.totp_encryption_key) < 32
            ):
                raise ValueError(
                    "TOTP_ENCRYPTION_KEY must be a unique secret of at least 32 characters"
                )
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be enabled in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
