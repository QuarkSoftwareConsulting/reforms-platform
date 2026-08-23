"""Configuracion de la aplicacion (12-factor: todo por variables de entorno)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # ------------------------------- General -----------------------------
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # ------------------------------- Base de datos -----------------------
    database_url: str = "postgresql+asyncpg://reforma:reforma@localhost:5433/reforma_hub"
    test_database_url: str = "postgresql+asyncpg://reforma:reforma@localhost:5434/reforma_hub_test"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_echo: bool = False

    # ------------------------------- Web / CORS --------------------------
    public_web_url: str = "http://localhost:3010"
    cors_origins: str = "http://localhost:3010"

    # ------------------------------- Reglas de negocio -------------------
    lead_max_purchases: int = Field(default=3, ge=1, le=10)
    purchase_reservation_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    default_lead_price_cents: int = Field(default=500, gt=0)
    default_currency: str = "EUR"
    privacy_policy_version: str = "2026-01-v1"
    enforce_category_match: bool = True

    # ------------------------------- Stripe ------------------------------
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # ------------------------------- Firebase ----------------------------
    firebase_project_id: str = ""
    firebase_credentials_json: str = ""
    google_application_credentials: str = ""
    firebase_auth_emulator_host: str = ""

    # ------------------------------- Almacenamiento ----------------------
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_base_url: str = "http://localhost:9000/reforma-hub-dev"
    s3_bucket: str = "reforma-hub-dev"
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_presign_expires_seconds: int = 900

    @field_validator("log_level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def uses_auth_emulator(self) -> bool:
        return bool(self.firebase_auth_emulator_host)

    @property
    def sync_database_url(self) -> str:
        """Version sincrona (psycopg) que necesita Alembic para autogenerar."""
        return self.database_url.replace("+asyncpg", "")

    def assert_production_ready(self) -> None:
        """Falla al arrancar si falta un secreto imprescindible en produccion.

        Es preferible no arrancar a arrancar aceptando pagos que no se pueden
        confirmar o tokens que no se pueden verificar.
        """
        if not self.is_production:
            return
        missing = [
            name
            for name, value in (
                ("STRIPE_SECRET_KEY", self.stripe_secret_key),
                ("STRIPE_WEBHOOK_SECRET", self.stripe_webhook_secret),
                ("FIREBASE_PROJECT_ID", self.firebase_project_id),
                ("S3_ACCESS_KEY_ID", self.s3_access_key_id),
                ("S3_SECRET_ACCESS_KEY", self.s3_secret_access_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Faltan variables de entorno obligatorias en produccion: {', '.join(missing)}"
            )
        if self.uses_auth_emulator:
            raise RuntimeError("FIREBASE_AUTH_EMULATOR_HOST no puede estar definido en produccion")


@lru_cache
def get_settings() -> Settings:
    return Settings()
