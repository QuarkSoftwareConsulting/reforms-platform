"""vista previa publica del lead

Marca que consentimientos cubren mostrar el nombre de pila y el CP antes de la
compra. Los existentes quedan en false: se dieron bajo una politica que no lo decia.

Revision ID: b21c3dcaecb5
Revises: 34c4e1084577
Create Date: 2026-09-28 23:07:28.526197
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b21c3dcaecb5"
down_revision: str | None = "34c4e1084577"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lead_consents",
        sa.Column(
            "allows_public_preview", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("lead_consents", "allows_public_preview")
