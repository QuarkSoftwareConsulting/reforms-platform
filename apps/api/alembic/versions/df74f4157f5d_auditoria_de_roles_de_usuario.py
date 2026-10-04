"""auditoria de roles de usuario

Revision ID: df74f4157f5d
Revises: c7d7d55fbb83
Create Date: 2026-10-03 23:37:13.764228
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "df74f4157f5d"
down_revision: str | None = "c7d7d55fbb83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# El tipo `user_role` ya existe (lo usa `users.role`): se reutiliza sin crearlo y el
# downgrade NO lo borra. `scripts.fix_migration` anadiria un DROP TYPE: no aplicarlo.
user_role = postgresql.ENUM("professional", "admin", name="user_role", create_type=False)


def upgrade() -> None:
    op.create_table(
        "user_role_events",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("from_role", user_role, nullable=False),
        sa.Column("to_role", user_role, nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_user_role_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_role_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_role_events")),
    )
    op.create_index("ix_user_role_events_user_id", "user_role_events", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_role_events_user_id", table_name="user_role_events")
    op.drop_table("user_role_events")
