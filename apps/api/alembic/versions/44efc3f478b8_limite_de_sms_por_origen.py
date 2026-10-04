"""limite de sms por origen

Revision ID: 44efc3f478b8
Revises: af5e07db6017
Create Date: 2026-09-29 09:58:31.403305
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "44efc3f478b8"
down_revision: str | None = "af5e07db6017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Contador de SMS por IP y ventana, compartido entre instancias del API.
    op.create_table(
        "rate_limit_counters",
        sa.Column("bucket_key", sa.String(length=160), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bucket_key", "window_start", name=op.f("pk_rate_limit_counters")),
    )
    op.create_index(
        "ix_rate_limit_counters_window_start", "rate_limit_counters", ["window_start"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_counters_window_start", table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
