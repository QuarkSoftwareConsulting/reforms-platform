"""Configuracion de la aplicacion (12-factor: todo por variables de entorno)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.models import policy_covers_public_preview


def _is_unset(value: str) -> bool:
    """Vacio o el valor de ejemplo de `.env.example` (`sk_test_xxx`, `whsec_xxx`...).

    Copiar `.env.example` deja esos valores: no estan vacios, pero con ellos Stripe
    rechaza la clave y cada webhook falla la firma. Contaban como configurados.
    """
    return not value.strip() or value.strip().endswith("_xxx")


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
    lead_max_purchases: int = Field(default=5, ge=1, le=10)
    purchase_reservation_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    default_lead_price_cents: int = Field(default=500, gt=0)
    default_currency: str = "EUR"
    privacy_policy_version: str = "2026-09-v2"
    # Prefijos de CP donde se pueden publicar solicitudes. Etapa 1: Comunidad de Madrid.
    covered_postal_prefixes: str = "28"
    # Verificacion del movil del cliente por SMS antes de publicar. "disabled" hasta
    # que haya proveedor; "console" escribe el codigo en el log (solo desarrollo).
    phone_verification_backend: Literal["disabled", "console"] = "disabled"
    # Tope de SMS por IP y hora, contra el "SMS pumping". Holgado para una oficina o
    # una red movil con NAT compartido; el proveedor limita ademas por telefono.
    phone_verification_per_ip_hourly: int = Field(default=10, ge=1, le=1000)
    # Proxies propios que anaden su IP a X-Forwarded-For. Cloud Run sin balanceador
    # anade uno; con un balanceador delante serian dos. La IP del cliente es la que
    # esta a esa distancia desde la derecha: las de la izquierda las escribe el cliente.
    trusted_proxy_hops: int = Field(default=1, ge=0, le=5)
    enforce_category_match: bool = True

    # ------------------------------- Stripe ------------------------------
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Mensualidad INICIAL, hasta que el admin fije la suya desde el panel (que crea
    # su propio precio en Stripe y tiene prioridad). Deben coincidir entre si.
    stripe_topup_price_id: str = ""
    subscription_topup_cents: int = Field(default=1800, gt=0)

    # ------------------------------- Firebase ----------------------------
    firebase_project_id: str = ""
    firebase_credentials_json: str = ""
    google_application_credentials: str = ""
    firebase_auth_emulator_host: str = ""

    # ------------------------------- Almacenamiento ----------------------
    storage_backend: Literal["s3", "gcs"] = "s3"
    gcs_bucket: str = ""
    # Bucket PRIVADO de los documentos de alta del profesional (DNI, modelos de
    # Hacienda). Sin acceso publico: solo descargas firmadas para el admin.
    gcs_private_bucket: str = ""
    gcs_signed_url_expires_seconds: int = Field(default=900, ge=1, le=604800)
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_base_url: str = "http://localhost:9000/reforma-hub-dev"
    s3_bucket: str = "reforma-hub-dev"
    s3_private_bucket: str = "reforma-hub-private"
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_presign_expires_seconds: int = 900

    @model_validator(mode="after")
    def _validate_storage(self) -> Settings:
        if self.storage_backend == "gcs" and not self.gcs_bucket.strip():
            raise ValueError("GCS_BUCKET es obligatorio con STORAGE_BACKEND=gcs")
        if self.storage_backend == "gcs" and not self.gcs_private_bucket.strip():
            raise ValueError("GCS_PRIVATE_BUCKET es obligatorio con STORAGE_BACKEND=gcs")
        private = (
            self.gcs_private_bucket if self.storage_backend == "gcs" else self.s3_private_bucket
        )
        public = self.gcs_bucket if self.storage_backend == "gcs" else self.s3_bucket
        if private.strip() == public.strip():
            # Con el mismo bucket los documentos de identidad serian publicos.
            raise ValueError("El bucket privado de documentos no puede ser el publico")
        if self.storage_backend == "gcs" and self.google_application_credentials:
            raise ValueError("GCS requiere ADC del runtime, sin GOOGLE_APPLICATION_CREDENTIALS")
        return self

    @model_validator(mode="after")
    def _validate_privacy_policy(self) -> Settings:
        # Sin esto, subir la version y olvidar declararla en el dominio apagaria la
        # vista previa de todos los leads nuevos sin que nadie se entere.
        if not policy_covers_public_preview(self.privacy_policy_version):
            raise ValueError(
                f"PRIVACY_POLICY_VERSION={self.privacy_policy_version} no figura en "
                "PUBLIC_PREVIEW_POLICY_VERSIONS: declara si cubre la vista previa del lead"
            )
        return self

    @model_validator(mode="after")
    def _validate_phone_verification(self) -> Settings:
        if self.phone_verification_backend == "console" and self.environment not in {
            "development",
            "test",
        }:
            raise ValueError(
                "PHONE_VERIFICATION_BACKEND=console escribe los codigos en el log: "
                "solo se permite en development y test"
            )
        return self

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

    def unconfigured_payment_secrets(self) -> list[str]:
        """Secretos de Stripe sin valor real: sin ellos no se cobra ni se confirma nada."""
        return [
            name
            for name, value in (
                ("STRIPE_SECRET_KEY", self.stripe_secret_key),
                ("STRIPE_WEBHOOK_SECRET", self.stripe_webhook_secret),
            )
            if _is_unset(value)
        ]

    def assert_production_ready(self) -> None:
        """Falla al arrancar si falta un secreto imprescindible en produccion.

        Es preferible no arrancar a arrancar aceptando pagos que no se pueden
        confirmar o tokens que no se pueden verificar.
        """
        if not self.is_production:
            return
        missing = self.unconfigured_payment_secrets()
        if _is_unset(self.firebase_project_id):
            missing.append("FIREBASE_PROJECT_ID")
        if self.storage_backend == "s3":
            missing.extend(
                name
                for name, value in (
                    ("S3_ACCESS_KEY_ID", self.s3_access_key_id),
                    ("S3_SECRET_ACCESS_KEY", self.s3_secret_access_key),
                )
                if not value
            )
        if missing:
            raise RuntimeError(
                f"Faltan variables de entorno obligatorias en produccion: {', '.join(missing)}"
            )
        if self.uses_auth_emulator:
            raise RuntimeError("FIREBASE_AUTH_EMULATOR_HOST no puede estar definido en produccion")


@lru_cache
def get_settings() -> Settings:
    return Settings()
