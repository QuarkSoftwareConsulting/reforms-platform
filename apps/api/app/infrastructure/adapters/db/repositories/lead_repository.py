"""Repositorio de leads sobre PostGIS."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.ports import (
    LeadRepositoryPort,
    LeadSearchFilters,
    LeadSearchRow,
)
from app.domain.exceptions import LeadNotFoundError
from app.domain.models import Lead, LeadStatus, PurchaseStatus
from app.infrastructure.adapters.db.mappers import apply_lead, lead_to_domain, to_geography
from app.infrastructure.adapters.db.models import (
    LeadConsentRow,
    LeadPhotoRow,
    LeadPurchaseRow,
    LeadRow,
)


class SqlAlchemyLeadRepository(LeadRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------ Escritura ----------------------------

    async def add(self, lead: Lead) -> Lead:
        row = LeadRow(id=lead.id)
        apply_lead(row, lead)
        row.photos = [
            LeadPhotoRow(
                lead_id=lead.id,
                storage_key=photo.storage_key,
                sort_order=photo.sort_order,
            )
            for photo in lead.photos
        ]
        # Se asigna siempre, aunque este vacia: deja la coleccion en estado cargado
        # y evita una carga perezosa (imposible en contexto async) si alguien lee
        # este mismo objeto despues desde la sesion.
        row.consents = (
            [
                LeadConsentRow(
                    lead_id=lead.id,
                    policy_version=lead.consent.policy_version,
                    ip_address=lead.consent.ip_address,
                    user_agent=lead.consent.user_agent,
                    max_recipients=lead.consent.max_recipients,
                    accepted_at=lead.consent.accepted_at,
                )
            ]
            if lead.consent is not None
            else []
        )
        self._session.add(row)
        await self._session.flush()
        # Se devuelve la entidad recibida: la fila acaba de escribirse y su columna
        # geografica todavia contiene el WKT sin convertir a WKB.
        return lead

    async def update(self, lead: Lead) -> Lead:
        row = await self._load_row(lead.id)
        if row is None:
            raise LeadNotFoundError()
        apply_lead(row, lead)
        await self._session.flush()
        return lead

    # ------------------------------ Lectura ------------------------------

    async def get(self, lead_id: UUID) -> Lead | None:
        row = await self._load_row(lead_id)
        return lead_to_domain(row) if row is not None else None

    async def _load_row(self, lead_id: UUID) -> LeadRow | None:
        """Carga la fila con sus relaciones resueltas.

        Se usa `select(...).populate_existing()` en vez de `session.get(...)` porque
        `get` devuelve la instancia ya presente en la sesion sin aplicar los
        `selectinload`, y leer una relacion no cargada en async falla con
        MissingGreenlet.
        """
        stmt = (
            select(LeadRow)
            .where(LeadRow.id == lead_id)
            .options(selectinload(LeadRow.photos), selectinload(LeadRow.consents))
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_for_update(self, lead_id: UUID) -> Lead | None:
        """Bloquea la fila del lead hasta el final de la transaccion.

        `with_for_update` es lo que serializa las compras concurrentes; sin el, dos
        profesionales podrian leer el mismo recuento de plazas libres y superar el
        cap. Las relaciones se cargan aparte porque Postgres no admite FOR UPDATE
        junto a los OUTER JOIN que generaria un eager load.
        """
        stmt = select(LeadRow).where(LeadRow.id == lead_id).with_for_update()
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        await self._session.refresh(row, ["photos", "consents"])
        return lead_to_domain(row)

    # ------------------------------ Busqueda -----------------------------

    def _base_query(self, filters: LeadSearchFilters) -> Select[tuple[LeadRow]]:
        stmt = select(LeadRow).where(LeadRow.status == LeadStatus.PUBLISHED)

        if filters.category_ids:
            stmt = stmt.where(LeadRow.category_id.in_(filters.category_ids))
        if filters.province:
            stmt = stmt.where(LeadRow.province == filters.province)
        if filters.center is not None and filters.radius_km is not None:
            # ST_DWithin sobre geography usa metros y aprovecha el indice GIST.
            stmt = stmt.where(
                func.ST_DWithin(
                    LeadRow.location,
                    to_geography(filters.center),
                    filters.radius_km * 1000,
                )
            )
        return stmt

    async def search(
        self, filters: LeadSearchFilters, *, requester_professional_id: UUID | None = None
    ) -> list[LeadSearchRow]:
        distance = (
            func.ST_Distance(LeadRow.location, to_geography(filters.center))
            if filters.center is not None
            else None
        )

        stmt = (
            self._base_query(filters)
            .options(selectinload(LeadRow.photos), selectinload(LeadRow.consents))
            .order_by(LeadRow.created_at.desc())
            .limit(filters.limit)
            .offset(filters.offset)
        )
        if distance is not None:
            stmt = stmt.add_columns(distance.label("distance_m"))

        result = await self._session.execute(stmt)
        rows = result.all()

        lead_rows = [row[0] for row in rows]
        purchased_ids = await self._purchased_lead_ids(
            [row.id for row in lead_rows], requester_professional_id
        )

        search_rows: list[LeadSearchRow] = []
        for record in rows:
            lead_row = record[0]
            distance_km = (
                round(record[1] / 1000, 1)
                if distance is not None and record[1] is not None
                else None
            )
            search_rows.append(
                LeadSearchRow(
                    lead=lead_to_domain(lead_row),
                    distance_km=distance_km,
                    purchased_by_requester=lead_row.id in purchased_ids,
                )
            )
        return search_rows

    async def count(self, filters: LeadSearchFilters) -> int:
        stmt = self._base_query(filters).with_only_columns(func.count(LeadRow.id))
        return (await self._session.execute(stmt)).scalar_one()

    async def _purchased_lead_ids(
        self, lead_ids: list[UUID], professional_id: UUID | None
    ) -> set[UUID]:
        """Marca de una sola consulta cuales de los leads listados ya compro."""
        if professional_id is None or not lead_ids:
            return set()
        stmt = select(LeadPurchaseRow.lead_id).where(
            LeadPurchaseRow.professional_id == professional_id,
            LeadPurchaseRow.lead_id.in_(lead_ids),
            LeadPurchaseRow.status == PurchaseStatus.PAID,
        )
        return set((await self._session.execute(stmt)).scalars().all())
