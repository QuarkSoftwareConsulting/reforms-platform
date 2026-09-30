"""Verificacion del movil del cliente por SMS antes de publicar (F01)."""

import pytest

from app.application.dto import ConsentInput
from app.application.use_cases import StartPhoneVerification
from app.domain.exceptions import (
    PhoneNotMobileError,
    PhoneNotVerifiedError,
    PhoneVerificationUnavailableError,
    ValidationError,
)
from app.domain.models import Category, LeadSource
from app.domain.value_objects import PhoneNumber
from tests.conftest import World
from tests.fakes import FAKE_CODE
from tests.unit.use_cases.test_create_lead import lead_input

PHONE = "+34611223344"


class TestStartVerification:
    async def test_sends_a_code_to_the_mobile(self, world: World) -> None:
        result = await world.start_phone_verification.execute("611 22 33 44")
        assert result.required is True
        assert world.phone_verifier.sent_to == ["611223344"]

    async def test_is_not_required_without_a_provider(self) -> None:
        result = await StartPhoneVerification(verifier=None).execute(PHONE)
        assert result.required is False

    @pytest.mark.parametrize("phone", ["912345678", "+34812345678"])
    async def test_a_landline_cannot_receive_the_sms(self, world: World, phone: str) -> None:
        with pytest.raises(PhoneNotMobileError):
            await world.start_phone_verification.execute(phone)
        assert world.phone_verifier.sent_to == []

    async def test_garbage_is_a_validation_error(self, world: World) -> None:
        with pytest.raises(ValidationError):
            await world.start_phone_verification.execute("no es un telefono")

    async def test_provider_failure_surfaces_as_unavailable(self, world: World) -> None:
        world.phone_verifier.fail_next = True
        with pytest.raises(PhoneVerificationUnavailableError):
            await world.start_phone_verification.execute(PHONE)


class TestPublishingRequiresTheCode:
    async def test_publishes_with_the_right_code(self, world: World, carpentry: Category) -> None:
        await world.start_phone_verification.execute(PHONE)
        lead = await world.create_lead_with_sms.execute(
            lead_input(carpentry, phone_verification_code=FAKE_CODE), source=LeadSource.ORGANIC
        )
        assert lead.contact.phone == PhoneNumber(PHONE)
        assert lead.id in world.leads.items

    @pytest.mark.parametrize("code", [None, "", "000000"])
    async def test_rejects_a_missing_or_wrong_code(
        self, world: World, carpentry: Category, code: str | None
    ) -> None:
        await world.start_phone_verification.execute(PHONE)
        with pytest.raises(PhoneNotVerifiedError):
            await world.create_lead_with_sms.execute(
                lead_input(carpentry, phone_verification_code=code), source=LeadSource.ORGANIC
            )
        assert world.leads.items == {}

    async def test_a_code_cannot_publish_twice(self, world: World, carpentry: Category) -> None:
        await world.start_phone_verification.execute(PHONE)
        data = lead_input(carpentry, phone_verification_code=FAKE_CODE)
        await world.create_lead_with_sms.execute(data, source=LeadSource.ORGANIC)

        with pytest.raises(PhoneNotVerifiedError):
            await world.create_lead_with_sms.execute(data, source=LeadSource.ORGANIC)
        assert len(world.leads.items) == 1

    async def test_an_invalid_form_does_not_burn_the_code(
        self, world: World, carpentry: Category
    ) -> None:
        await world.start_phone_verification.execute(PHONE)
        with pytest.raises(ValidationError):
            await world.create_lead_with_sms.execute(
                lead_input(carpentry, description="corto", phone_verification_code=FAKE_CODE),
                source=LeadSource.ORGANIC,
            )
        # El mismo codigo sigue valiendo para el reintento con el formulario corregido.
        lead = await world.create_lead_with_sms.execute(
            lead_input(carpentry, phone_verification_code=FAKE_CODE), source=LeadSource.ORGANIC
        )
        assert lead.id in world.leads.items

    async def test_admin_leads_skip_the_sms(self, world: World, carpentry: Category) -> None:
        consent = ConsentInput(accepted=True, policy_version="2026-09-v2", channel="Meta Ads")
        lead = await world.create_lead_with_sms.execute(
            lead_input(carpentry, consent=consent), source=LeadSource.ADMIN
        )
        assert lead.id in world.leads.items
