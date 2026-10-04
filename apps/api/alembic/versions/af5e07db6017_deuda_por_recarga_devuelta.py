"""deuda por recarga devuelta

Revision ID: af5e07db6017
Revises: c7d7d55fbb83
Create Date: 2026-09-29 09:29:08.324531
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "af5e07db6017"
down_revision: str | None = "c7d7d55fbb83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Movimientos nuevos: la recarga que el banco devolvio y su devolucion si la
    # disputa se gana. --autogenerate no detecta valores nuevos de un ENUM.
    op.execute("ALTER TYPE credit_entry_kind ADD VALUE IF NOT EXISTS 'chargeback'")
    op.execute("ALTER TYPE credit_entry_kind ADD VALUE IF NOT EXISTS 'chargeback_reversal'")
    # Las cuentas existentes no deben nada: el server_default rellena las filas.
    op.add_column(
        "professional_accounts",
        sa.Column("debt_cents", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_professional_accounts_balance_or_debt"),
        "professional_accounts",
        "balance_cents = 0 OR debt_cents = 0",
    )
    op.create_check_constraint(
        op.f("ck_professional_accounts_debt_non_negative"),
        "professional_accounts",
        "debt_cents >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_professional_accounts_debt_non_negative"), "professional_accounts", type_="check"
    )
    op.drop_constraint(
        op.f("ck_professional_accounts_balance_or_debt"), "professional_accounts", type_="check"
    )
    op.drop_column("professional_accounts", "debt_cents")
    # 'chargeback' y 'chargeback_reversal' se quedan en credit_entry_kind: Postgres no
    # permite quitar un valor de un ENUM sin recrear el tipo, y un valor sin usar no
    # molesta. El upgrade usa ADD VALUE IF NOT EXISTS, asi que volver a subir no falla.
