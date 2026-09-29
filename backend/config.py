from functools import lru_cache

from pydantic import EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    app_url: str = "http://localhost:3000"
    environment: str = Field(default="development", alias="APP_ENV")

    jwt_secret: str = Field(min_length=32)
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 30

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    brevo_api_key: str = ""
    email_from: str = "Gatewise <no-reply@example.com>"

    super_admin_email: EmailStr = "admin@gatewise.dev"
    super_admin_password: str = Field(default="Admin@12345", min_length=8)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_callback_url(self) -> str:
        return self.google_redirect_uri or f"{self.app_url.rstrip('/')}/api/auth/google/callback"

    @property
    def email_enabled(self) -> bool:
        return bool(self.brevo_api_key)

    @property
    def email_sender(self) -> tuple[str, str]:
        raw = self.email_from.strip()
        if "<" in raw and raw.endswith(">"):
            name, _, addr = raw.rpartition("<")
            return name.strip().strip('"') or "Gatewise", addr[:-1].strip()
        return "Gatewise", raw

    @property
    def is_serverless(self) -> bool:
        import os

        return bool(os.environ.get("VERCEL"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
