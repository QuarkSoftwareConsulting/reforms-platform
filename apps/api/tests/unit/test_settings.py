"""Validaciones de `Settings` que protegen reglas de negocio al arrancar."""

import pytest

from app.config import Settings


def test_current_privacy_policy_covers_public_preview() -> None:
    assert Settings().privacy_policy_version == "2026-09-v2"


def test_undeclared_privacy_policy_version_is_refused() -> None:
    # Subir la version sin declararla en el dominio apagaria en silencio la vista
    # previa de todos los leads nuevos.
    with pytest.raises(ValueError, match="PUBLIC_PREVIEW_POLICY_VERSIONS"):
        Settings(privacy_policy_version="2027-01-v3")


class TestPaymentSecrets:
    """Los valores de `.env.example` no cuentan como configurados (4 de octubre)."""

    def production(self, **overrides: str) -> Settings:
        values = {
            "environment": "production",
            "stripe_secret_key": "sk_live_realkey123456",
            "stripe_webhook_secret": "whsec_realsecret123456",
            "firebase_project_id": "reforma-hub",
            "storage_backend": "gcs",
            "firebase_auth_emulator_host": "",
            **overrides,
        }
        return Settings(**values)  # type: ignore[arg-type]

    def test_real_secrets_pass(self) -> None:
        settings = self.production()
        assert settings.unconfigured_payment_secrets() == []
        settings.assert_production_ready()

    @pytest.mark.parametrize(
        ("field", "value", "variable"),
        [
            ("stripe_webhook_secret", "whsec_xxx", "STRIPE_WEBHOOK_SECRET"),
            ("stripe_webhook_secret", "", "STRIPE_WEBHOOK_SECRET"),
            ("stripe_secret_key", "sk_test_xxx", "STRIPE_SECRET_KEY"),
        ],
    )
    def test_production_refuses_to_start_with_a_placeholder(
        self, field: str, value: str, variable: str
    ) -> None:
        settings = self.production(**{field: value})
        assert settings.unconfigured_payment_secrets() == [variable]
        with pytest.raises(RuntimeError, match=variable):
            settings.assert_production_ready()

    def test_development_reports_the_placeholder_without_refusing(self) -> None:
        settings = Settings(
            environment="development",
            stripe_secret_key="sk_test_realkey123456",
            stripe_webhook_secret="whsec_xxx",
        )
        assert settings.unconfigured_payment_secrets() == ["STRIPE_WEBHOOK_SECRET"]
        settings.assert_production_ready()
