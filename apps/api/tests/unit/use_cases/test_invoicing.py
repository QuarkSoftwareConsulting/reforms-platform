"""Facturas de la recarga: se guardan al cobrarse y llevan los datos fiscales al dia."""

import logging
from datetime import timedelta
from typing import Any

import pytest

from app.application.dto import UpsertProfessionalInput
from app.application.ports import BillingDetails, PaymentEventType
from app.domain.exceptions import PaymentGatewayError
from app.domain.models import Category, Professional, ProfessionalType
from app.domain.value_objects import Money, TaxId
from tests.conftest import World
from tests.factories import NOW
from tests.fakes import FakePaymentGateway
from tests.fakes.payments import VALID_SIGNATURE

TAX_ID = "12345678Z"
ADDRESS = "Calle Mayor 1, 28013 Madrid"


def billed_pro(world: World, category: Category, **kwargs: object) -> Professional:
    return world.add_professional(
        category_ids={category.id},
        subscribed=False,
        legal_name="Juan Lopez Garcia",
        tax_id=TaxId(TAX_ID),
        address=ADDRESS,
        **kwargs,
    )


async def subscribe(world: World, professional: Professional) -> str:
    await world.start_subscription.execute(professional=professional, email="pro@example.com")
    customer_id = world.accounts.items[professional.id].stripe_customer_id
    assert customer_id is not None
    return customer_id


async def invoice_paid(
    world: World,
    customer_id: str,
    *,
    event_id: str = "evt_inv_1",
    invoice_id: str = "in_1",
    amount_cents: int = 1800,
    **kwargs: Any,
) -> None:
    payload = FakePaymentGateway.subscription_event_payload(
        event_id=event_id,
        event_type=PaymentEventType.INVOICE_PAID,
        customer_id=customer_id,
        invoice_id=invoice_id,
        amount_cents=amount_cents,
        **kwargs,
    )
    await world.handle_event.execute(payload=payload, signature=VALID_SIGNATURE)


class TestInvoiceIsStored:
    async def test_paid_invoice_keeps_its_number_link_and_vat(
        self, world: World, carpentry: Category
    ) -> None:
        professional = billed_pro(world, carpentry)
        customer_id = await subscribe(world, professional)

        await invoice_paid(
            world,
            customer_id,
            invoice_number="VAR-0001",
            tax_cents=312,
            issued_at=NOW - timedelta(minutes=1),
            occurred_at=NOW,
        )

        [invoice] = world.invoices.items
        assert invoice.professional_id == professional.id
        assert invoice.gateway_invoice_id == "in_1"
        assert invoice.number == "VAR-0001"
        assert invoice.total == Money(1800, "EUR")
        assert invoice.tax == Money(312, "EUR")
        assert invoice.hosted_url == "https://invoice.test/in_1"
        assert invoice.pdf_url == "https://invoice.test/in_1.pdf"
        assert invoice.issued_at == NOW - timedelta(minutes=1), "la emision, no el cobro"

    async def test_resent_invoice_is_stored_once(self, world: World, carpentry: Category) -> None:
        professional = billed_pro(world, carpentry)
        customer_id = await subscribe(world, professional)

        # El mismo evento reenviado, y la misma factura con otro event_id.
        for event_id in ("evt_inv_1", "evt_inv_1", "evt_inv_1_bis"):
            await invoice_paid(world, customer_id, event_id=event_id)

        assert len(world.invoices.items) == 1

    async def test_monthly_invoices_accumulate(self, world: World, carpentry: Category) -> None:
        professional = billed_pro(world, carpentry)
        customer_id = await subscribe(world, professional)

        for month in range(3):
            await invoice_paid(
                world, customer_id, event_id=f"evt_inv_{month}", invoice_id=f"in_{month}"
            )

        assert [i.gateway_invoice_id for i in world.invoices.items] == ["in_0", "in_1", "in_2"]

    async def test_a_zero_invoice_is_stored_without_crediting(
        self, world: World, carpentry: Category
    ) -> None:
        # Un cupon del 100 %: no hay saldo que abonar, pero la factura se emitio.
        professional = billed_pro(world, carpentry)
        customer_id = await subscribe(world, professional)

        await invoice_paid(world, customer_id, amount_cents=0)

        assert [i.total for i in world.invoices.items] == [Money(0, "EUR")]
        assert world.accounts.items[professional.id].balance == Money(0, "EUR")

    async def test_without_vat_breakdown_the_tax_is_unknown(
        self, world: World, carpentry: Category
    ) -> None:
        professional = billed_pro(world, carpentry)
        customer_id = await subscribe(world, professional)

        await invoice_paid(world, customer_id, occurred_at=NOW)

        [invoice] = world.invoices.items
        assert invoice.tax is None
        assert invoice.issued_at == NOW, "sin fecha de emision, la del evento"


class TestBillingDetailsOnSubscribe:
    async def test_new_customer_is_created_with_fiscal_data(
        self, world: World, carpentry: Category
    ) -> None:
        professional = billed_pro(world, carpentry)
        customer_id = await subscribe(world, professional)

        assert world.payments.customers[customer_id].billing == BillingDetails(
            name="Juan Lopez Garcia", tax_id=TaxId(TAX_ID), address=ADDRESS
        )

    async def test_without_legal_name_the_business_name_is_used(
        self, world: World, carpentry: Category
    ) -> None:
        professional = world.add_professional(category_ids={carpentry.id}, subscribed=False)
        customer_id = await subscribe(world, professional)

        billing = world.payments.customers[customer_id].billing
        assert billing == BillingDetails(name=professional.business_name)

    async def test_existing_customer_is_brought_up_to_date(
        self, world: World, carpentry: Category
    ) -> None:
        # Se dio de alta en la pasarela antes de tener NIF y domicilio en el perfil.
        professional = world.add_professional(category_ids={carpentry.id}, subscribed=False)
        customer_id = await subscribe(world, professional)
        professional.legal_name = "Juan Lopez Garcia"
        professional.tax_id = TaxId(TAX_ID)
        professional.address = ADDRESS

        await world.start_subscription.execute(professional=professional, email="pro@example.com")

        assert world.payments.billing_updates[customer_id].tax_id == TaxId(TAX_ID)
        assert len(world.payments.customers) == 1, "no se crea otro cliente"

    async def test_no_checkout_if_the_fiscal_data_cannot_be_updated(
        self, world: World, carpentry: Category
    ) -> None:
        # La primera factura sale nada mas pagar: sin los datos al dia, saldria sin NIF.
        professional = billed_pro(world, carpentry)
        await subscribe(world, professional)
        world.payments.fail_on_billing_update = True

        with pytest.raises(PaymentGatewayError):
            await world.start_subscription.execute(
                professional=professional, email="pro@example.com"
            )
        assert len(world.payments.subscription_checkouts) == 1


def profile_input(category: Category, **overrides: object) -> UpsertProfessionalInput:
    values: dict[str, object] = {
        "business_name": "Reformas Lopez",
        "phone": "+34600111222",
        "postal_code": "28001",
        "service_radius_km": 20,
        "category_ids": {category.id},
        "professional_type": ProfessionalType.SELF_EMPLOYED,
        "legal_name": "Juan Lopez Garcia",
        "tax_id": TAX_ID,
        "address": ADDRESS,
        **overrides,
    }
    return UpsertProfessionalInput(**values)  # type: ignore[arg-type]


class TestBillingDetailsOnProfileSave:
    async def _customer(self, world: World, category: Category) -> tuple[Professional, str]:
        user = world.add_user()
        professional = await world.upsert_profile.execute(
            user_id=user.id, data=profile_input(category)
        )
        return professional, await subscribe(world, professional)

    async def test_a_new_address_reaches_the_gateway(
        self, world: World, carpentry: Category
    ) -> None:
        professional, customer_id = await self._customer(world, carpentry)

        await world.upsert_profile.execute(
            user_id=professional.user_id,
            data=profile_input(carpentry, address="Gran Via 2, 28013 Madrid"),
        )

        assert world.payments.billing_updates[customer_id] == BillingDetails(
            name="Juan Lopez Garcia", tax_id=TaxId(TAX_ID), address="Gran Via 2, 28013 Madrid"
        )

    async def test_unrelated_changes_do_not_call_the_gateway(
        self, world: World, carpentry: Category
    ) -> None:
        professional, _ = await self._customer(world, carpentry)

        await world.upsert_profile.execute(
            user_id=professional.user_id, data=profile_input(carpentry, service_radius_km=50)
        )

        assert world.payments.billing_updates == {}

    async def test_without_a_gateway_customer_there_is_nothing_to_sync(
        self, world: World, carpentry: Category
    ) -> None:
        user = world.add_user()
        await world.upsert_profile.execute(user_id=user.id, data=profile_input(carpentry))

        await world.upsert_profile.execute(
            user_id=user.id, data=profile_input(carpentry, address="Gran Via 2, 28013 Madrid")
        )

        assert world.payments.billing_updates == {}

    async def test_a_gateway_failure_does_not_undo_the_save(
        self, world: World, carpentry: Category, caplog: pytest.LogCaptureFixture
    ) -> None:
        professional, _ = await self._customer(world, carpentry)
        world.payments.fail_on_billing_update = True

        with caplog.at_level(logging.WARNING):
            saved = await world.upsert_profile.execute(
                user_id=professional.user_id,
                data=profile_input(carpentry, address="Gran Via 2, 28013 Madrid"),
            )

        assert saved.address == "Gran Via 2, 28013 Madrid"
        assert world.professionals.items[professional.id].address == saved.address
        assert "datos_fiscales_sin_sincronizar" in caplog.text
        # Sin datos personales en el log.
        assert ADDRESS not in caplog.text
        assert "Gran Via" not in caplog.text
