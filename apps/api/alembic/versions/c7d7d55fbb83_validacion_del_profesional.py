"""validacion del profesional

Alta del profesional (tipo, datos fiscales, direccion, fotos y documentos), servicios
que ofrece y validacion por el admin con su auditoria. Los perfiles existentes quedan
"incompletos": como cualquier alta nueva, aportan sus datos antes de poder comprar.

Revision ID: c7d7d55fbb83
Revises: 3a35d15d30d7
Create Date: 2026-09-29 00:17:45.492571
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7d7d55fbb83"
down_revision: str | None = "3a35d15d30d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Se crean aparte y las columnas los referencian con create_type=False: add_column no
# crea el tipo, y verification_status lo usan dos tablas (crearlo dos veces falla).
PROFESSIONAL_TYPE = postgresql.ENUM(
    "self_employed", "company", "independent", name="professional_type", create_type=False
)
VERIFICATION_STATUS = postgresql.ENUM(
    "incomplete", "pending", "approved", "rejected", name="verification_status", create_type=False
)
DOCUMENT_KIND = postgresql.ENUM(
    "tax_registration", "identity", name="document_kind", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (PROFESSIONAL_TYPE, VERIFICATION_STATUS, DOCUMENT_KIND):
        enum.create(bind, checkfirst=True)
    # Movimiento de saldo nuevo: retirar el primer cobro reembolsado al rechazar.
    op.execute("ALTER TYPE credit_entry_kind ADD VALUE IF NOT EXISTS 'verification_refund'")
    op.create_table(
        "professional_documents",
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("kind", DOCUMENT_KIND, nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["professionals.id"],
            name=op.f("fk_professional_documents_professional_id_professionals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_documents")),
    )
    op.create_index(
        "ix_professional_documents_professional_id",
        "professional_documents",
        ["professional_id"],
        unique=False,
    )
    op.create_table(
        "professional_services",
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["professionals.id"],
            name=op.f("fk_professional_services_professional_id_professionals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_professional_services_service_id_services"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "professional_id", "service_id", name=op.f("pk_professional_services")
        ),
    )
    op.create_table(
        "professional_verification_events",
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column(
            "from_status",
            VERIFICATION_STATUS,
            nullable=False,
        ),
        sa.Column(
            "to_status",
            VERIFICATION_STATUS,
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_professional_verification_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["professionals.id"],
            name=op.f("fk_professional_verification_events_professional_id_professionals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_verification_events")),
    )
    op.create_index(
        "ix_professional_verification_events_professional_id",
        "professional_verification_events",
        ["professional_id"],
        unique=False,
    )
    op.create_table(
        "professional_work_photos",
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["professionals.id"],
            name=op.f("fk_professional_work_photos_professional_id_professionals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_work_photos")),
    )
    op.create_index(
        "ix_professional_work_photos_professional_id",
        "professional_work_photos",
        ["professional_id"],
        unique=False,
    )
    op.add_column(
        "professionals",
        sa.Column(
            "professional_type",
            PROFESSIONAL_TYPE,
            nullable=True,
        ),
    )
    op.add_column("professionals", sa.Column("legal_name", sa.String(length=200), nullable=True))
    op.add_column("professionals", sa.Column("tax_id", sa.String(length=20), nullable=True))
    op.add_column("professionals", sa.Column("address", sa.String(length=300), nullable=True))
    op.add_column(
        "professionals", sa.Column("profile_photo_key", sa.String(length=500), nullable=True)
    )
    op.add_column("professionals", sa.Column("logo_key", sa.String(length=500), nullable=True))
    op.add_column(
        "professionals",
        sa.Column(
            "verification_status",
            VERIFICATION_STATUS,
            server_default=sa.text("'incomplete'"),
            nullable=False,
        ),
    )
    op.add_column(
        "professionals", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "professionals", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("professionals", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.create_index(
        "ix_professionals_verification_status",
        "professionals",
        ["verification_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_professionals_verification_status", table_name="professionals")
    op.drop_column("professionals", "rejection_reason")
    op.drop_column("professionals", "reviewed_at")
    op.drop_column("professionals", "submitted_at")
    op.drop_column("professionals", "verification_status")
    op.drop_column("professionals", "logo_key")
    op.drop_column("professionals", "profile_photo_key")
    op.drop_column("professionals", "address")
    op.drop_column("professionals", "tax_id")
    op.drop_column("professionals", "legal_name")
    op.drop_column("professionals", "professional_type")
    op.drop_index(
        "ix_professional_work_photos_professional_id", table_name="professional_work_photos"
    )
    op.drop_table("professional_work_photos")
    op.drop_index(
        "ix_professional_verification_events_professional_id",
        table_name="professional_verification_events",
    )
    op.drop_table("professional_verification_events")
    op.drop_table("professional_services")
    op.drop_index("ix_professional_documents_professional_id", table_name="professional_documents")
    op.drop_table("professional_documents")
    # Los tipos ENUM no los borra drop_table: hay que hacerlo a mano o el
    # siguiente upgrade falla con 'type already exists'.
    for enum_name in ("professional_type", "verification_status", "document_kind"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
    # 'verification_refund' se queda en credit_entry_kind: Postgres no permite quitar un
    # valor de un ENUM sin recrear el tipo, y un valor sin usar no molesta. El upgrade
    # usa ADD VALUE IF NOT EXISTS, asi que volver a subir no falla.
