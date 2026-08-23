"""initial schema

Revision ID: edc072083d48
Revises:
Create Date: 2026-08-22 18:36:49.908475
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "edc072083d48"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "categories",
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name_es", sa.String(length=120), nullable=False),
        sa.Column("name_en", sa.String(length=120), nullable=False),
        sa.Column("lead_price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
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
        sa.CheckConstraint("lead_price_cents > 0", name=op.f("ck_categories_lead_price_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("slug", name=op.f("uq_categories_slug")),
    )
    op.create_table(
        "postal_codes",
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("province", sa.String(length=120), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_postal_codes")),
    )
    op.create_index("ix_postal_codes_city", "postal_codes", ["city"], unique=False)
    op.create_index(
        "ix_postal_codes_location",
        "postal_codes",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_table(
        "processed_payment_events",
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_processed_payment_events")),
    )
    op.create_table(
        "users",
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.Enum("professional", "admin", name="user_role"), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("firebase_uid", name=op.f("uq_users_firebase_uid")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_table(
        "leads",
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("postal_code", sa.String(length=12), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("province", sa.String(length=120), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("client_phone", sa.String(length=20), nullable=False),
        sa.Column("client_email", sa.String(length=320), nullable=True),
        sa.Column(
            "status",
            sa.Enum("published", "exhausted", "disabled", name="lead_status"),
            nullable=False,
        ),
        sa.Column("source", sa.Enum("organic", "admin", name="lead_source"), nullable=False),
        sa.Column("max_purchases", sa.Integer(), nullable=False),
        sa.Column("purchases_count", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("max_purchases >= 1", name=op.f("ck_leads_max_purchases_positive")),
        sa.CheckConstraint(
            "purchases_count >= 0 AND purchases_count <= max_purchases",
            name=op.f("ck_leads_purchases_count_within_cap"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_leads_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
    )
    op.create_index(
        "ix_leads_browse",
        "leads",
        ["status", "category_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_leads_location", "leads", ["location"], unique=False, postgresql_using="gist"
    )
    op.create_table(
        "professionals",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("base_postal_code", sa.String(length=12), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("province", sa.String(length=120), nullable=True),
        sa.Column(
            "base_location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("service_radius_km", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "service_radius_km BETWEEN 1 AND 300",
            name=op.f("ck_professionals_service_radius_in_range"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_professionals_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professionals")),
        sa.UniqueConstraint("user_id", name=op.f("uq_professionals_user_id")),
    )
    op.create_index(
        "ix_professionals_base_location",
        "professionals",
        ["base_location"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_table(
        "lead_consents",
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("max_recipients", sa.Integer(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_consents_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_consents")),
    )
    op.create_index("ix_lead_consents_lead_id", "lead_consents", ["lead_id"], unique=False)
    op.create_table(
        "lead_photos",
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_lead_photos_lead_id_leads"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_photos")),
    )
    op.create_index("ix_lead_photos_lead_id", "lead_photos", ["lead_id"], unique=False)
    op.create_table(
        "lead_purchases",
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "status",
            sa.Enum("reserved", "paid", "expired", "failed", "refunded", name="purchase_status"),
            nullable=False,
        ),
        sa.Column("reserved_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("amount_cents > 0", name=op.f("ck_lead_purchases_amount_positive")),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_purchases_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["professionals.id"],
            name=op.f("fk_lead_purchases_professional_id_professionals"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_purchases")),
        sa.UniqueConstraint(
            "stripe_checkout_session_id", name=op.f("uq_lead_purchases_stripe_checkout_session_id")
        ),
    )
    op.create_index(
        "ix_lead_purchases_open_reservations",
        "lead_purchases",
        ["reserved_until"],
        unique=False,
        postgresql_where=sa.text("status = 'reserved'"),
    )
    op.create_index(
        "ix_lead_purchases_professional",
        "lead_purchases",
        ["professional_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_lead_purchases_active",
        "lead_purchases",
        ["lead_id", "professional_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('reserved', 'paid', 'refunded')"),
    )
    op.create_table(
        "professional_categories",
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_professional_categories_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["professionals.id"],
            name=op.f("fk_professional_categories_professional_id_professionals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "professional_id", "category_id", name=op.f("pk_professional_categories")
        ),
    )


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("professional_categories")
    op.drop_index(
        "uq_lead_purchases_active",
        table_name="lead_purchases",
        postgresql_where=sa.text("status IN ('reserved', 'paid', 'refunded')"),
    )
    op.drop_index("ix_lead_purchases_professional", table_name="lead_purchases")
    op.drop_index(
        "ix_lead_purchases_open_reservations",
        table_name="lead_purchases",
        postgresql_where=sa.text("status = 'reserved'"),
    )
    op.drop_table("lead_purchases")
    op.drop_index("ix_lead_photos_lead_id", table_name="lead_photos")
    op.drop_table("lead_photos")
    op.drop_index("ix_lead_consents_lead_id", table_name="lead_consents")
    op.drop_table("lead_consents")
    op.drop_index(
        "ix_professionals_base_location", table_name="professionals", postgresql_using="gist"
    )
    op.drop_table("professionals")
    op.drop_index("ix_leads_location", table_name="leads", postgresql_using="gist")
    op.drop_index("ix_leads_browse", table_name="leads")
    op.drop_table("leads")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("processed_payment_events")
    op.drop_index("ix_postal_codes_location", table_name="postal_codes", postgresql_using="gist")
    op.drop_index("ix_postal_codes_city", table_name="postal_codes")
    op.drop_table("postal_codes")
    op.drop_table("categories")
    for enum_name in ("purchase_status", "lead_source", "lead_status", "user_role"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
