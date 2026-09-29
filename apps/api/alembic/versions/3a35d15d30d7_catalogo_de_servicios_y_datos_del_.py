"""catalogo de servicios y datos del proyecto

Segundo nivel del catalogo (servicios por categoria), los servicios que eligio el
cliente en cada lead y dos datos nuevos del formulario: tipo de inmueble y
programacion del proyecto. Son nullable porque los leads anteriores no los tienen.

Revision ID: 3a35d15d30d7
Revises: b21c3dcaecb5
Create Date: 2026-09-28 23:36:07.553185
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3a35d15d30d7"
down_revision: str | None = "b21c3dcaecb5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# add_column no crea el tipo ENUM (create_table si): se crean aparte y las columnas
# los referencian con create_type=False.
PROPERTY_TYPE = postgresql.ENUM(
    "flat",
    "house",
    "commercial",
    "office",
    "community",
    "industrial",
    "land",
    name="property_type",
    create_type=False,
)
PROJECT_SCHEDULE = postgresql.ENUM(
    "asap",
    "within_weeks",
    "within_months",
    "gathering_quotes",
    name="project_schedule",
    create_type=False,
)


def upgrade() -> None:
    PROPERTY_TYPE.create(op.get_bind(), checkfirst=True)
    PROJECT_SCHEDULE.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "services",
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name_es", sa.String(length=160), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_services_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint("category_id", "slug", name="uq_services_category_slug"),
    )
    op.create_table(
        "lead_services",
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_services_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_lead_services_service_id_services"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("lead_id", "service_id", name=op.f("pk_lead_services")),
    )
    op.add_column(
        "categories",
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "leads",
        sa.Column("property_type", PROPERTY_TYPE, nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("schedule", PROJECT_SCHEDULE, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leads", "schedule")
    op.drop_column("leads", "property_type")
    op.drop_column("categories", "sort_order")
    op.drop_table("lead_services")
    op.drop_table("services")
    # Los tipos ENUM no los borra drop_table: hay que hacerlo a mano o el
    # siguiente upgrade falla con 'type already exists'.
    for enum_name in ("project_schedule", "property_type"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
