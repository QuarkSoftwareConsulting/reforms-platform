"""precio de venta por lead fijado por el admin

Revision ID: b1c4f2a97d31
Revises: edc072083d48
Create Date: 2026-08-22 20:10:00.000000

El precio deja de ser una propiedad del oficio y pasa a ser una decision por
contacto: `categories.lead_price_cents` se renombra a `suggested_lead_price_cents`
(sigue siendo el valor por defecto) y `leads` gana un precio propio opcional.

El renombrado se hace con ALTER ... RENAME COLUMN, no borrando y recreando: los
precios ya configurados por oficio deben sobrevivir a la migracion.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4f2a97d31"
down_revision: str | None = "edc072083d48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("categories", "lead_price_cents", new_column_name="suggested_lead_price_cents")
    op.drop_constraint("lead_price_positive", "categories", type_="check")
    op.create_check_constraint(
        "suggested_lead_price_positive", "categories", "suggested_lead_price_cents > 0"
    )

    op.add_column("leads", sa.Column("price_override_cents", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("price_override_currency", sa.String(length=3), nullable=True))
    op.create_check_constraint(
        "price_override_positive",
        "leads",
        "price_override_cents IS NULL OR price_override_cents > 0",
    )
    # Importe y divisa viajan juntos: media pareja haria que el mapeo de la fila
    # tuviera que inventarse la moneda del cobro.
    op.create_check_constraint(
        "price_override_complete",
        "leads",
        "(price_override_cents IS NULL) = (price_override_currency IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("price_override_complete", "leads", type_="check")
    op.drop_constraint("price_override_positive", "leads", type_="check")
    op.drop_column("leads", "price_override_currency")
    op.drop_column("leads", "price_override_cents")

    op.drop_constraint("suggested_lead_price_positive", "categories", type_="check")
    op.alter_column("categories", "suggested_lead_price_cents", new_column_name="lead_price_cents")
    op.create_check_constraint("lead_price_positive", "categories", "lead_price_cents > 0")
