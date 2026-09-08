"""Repositorio SQLAlchemy de las marcas de revision administrativa."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import PurchaseReviewRepositoryPort
from app.domain.models import PurchaseReview
from app.infrastructure.adapters.db.mappers import apply_purchase_review, purchase_review_to_domain
from app.infrastructure.adapters.db.models import PurchaseReviewRow


class SqlAlchemyPurchaseReviewRepository(PurchaseReviewRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, review: PurchaseReview) -> PurchaseReview:
        row = PurchaseReviewRow(id=review.id)
        apply_purchase_review(row, review)
        self._session.add(row)
        await self._session.flush()
        return review

    async def list_for_purchase(self, purchase_id: UUID) -> list[PurchaseReview]:
        stmt = (
            select(PurchaseReviewRow)
            .where(PurchaseReviewRow.purchase_id == purchase_id)
            .order_by(PurchaseReviewRow.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [purchase_review_to_domain(row) for row in rows]
