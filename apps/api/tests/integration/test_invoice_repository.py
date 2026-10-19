"""Facturas de la recarga contra Postgres: la restriccion unica hace de cerrojo."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Invoice, Professional
from app.domain.value_objects import Money
from app.infrastructure.adapters.db.models import InvoiceRow
from app.infrastructure.adapters.db.repositories import (
    SqlAlchemyInvoiceRepository,
    SqlAlchemyProfessionalAccountRepository,
)
from tests.factories import NOW, make_account

pytestmark = pytest.mark.integration


def invoice(professional: Professional, **overrides: object) -> Invoice:
    values: dict[str, object] = {
        "id": uuid4(),
        "professional_id": professional.id,
        "gateway_invoice_id": "in_1",
        "total": Money(1800, "EUR"),
        "issued_at": NOW,
        "created_at": NOW,
        "number": "VAR-0001",
        "tax": Money(312, "EUR"),
        "hosted_url": "https://invoice.stripe.com/i/acct_1/test_1",
        "pdf_url": "https://pay.stripe.com/invoice/acct_1/test_1/pdf",
        **overrides,
    }
    return Invoice(**values)  # type: ignore[arg-type]


async def count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(InvoiceRow))).scalar_one()


async def with_account(session: AsyncSession, professional: Professional) -> Professional:
    await SqlAlchemyProfessionalAccountRepository(session).add(
        make_account(professional_id=professional.id)
    )
    return professional


async def test_stores_the_invoice_once(
    session: AsyncSession, madrid_carpenter: Professional
) -> None:
    professional = await with_account(session, madrid_carpenter)
    repo = SqlAlchemyInvoiceRepository(session)

    assert await repo.add_if_absent(invoice(professional))
    # El webhook repetido: otro id nuestro, la misma factura de la pasarela.
    assert not await repo.add_if_absent(invoice(professional, number="otra"))

    row = (await session.execute(select(InvoiceRow))).scalar_one()
    assert row.number == "VAR-0001"
    assert row.total_cents == 1800
    assert row.tax_cents == 312
    assert row.issued_at == NOW


async def test_invoice_without_vat_or_number(
    session: AsyncSession, madrid_carpenter: Professional
) -> None:
    professional = await with_account(session, madrid_carpenter)
    repo = SqlAlchemyInvoiceRepository(session)

    assert await repo.add_if_absent(
        invoice(professional, tax=None, number=None, hosted_url=None, pdf_url=None)
    )
    assert await count(session) == 1


async def test_needs_an_existing_account(
    session: AsyncSession, madrid_carpenter: Professional
) -> None:
    with pytest.raises(IntegrityError):
        await SqlAlchemyInvoiceRepository(session).add_if_absent(invoice(madrid_carpenter))
