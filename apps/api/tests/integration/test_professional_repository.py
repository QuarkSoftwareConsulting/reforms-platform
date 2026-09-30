"""Perfil profesional contra Postgres: alta completa, documentos y auditoria."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.models import (
    Category,
    DocumentKind,
    Professional,
    ProfessionalDocument,
    ProfessionalType,
    VerificationEvent,
    VerificationStatus,
)
from app.domain.value_objects import TaxId
from app.infrastructure.adapters.db.repositories import SqlAlchemyProfessionalRepository
from tests.factories import NOW


def document(kind: DocumentKind, name: str) -> ProfessionalDocument:
    return ProfessionalDocument(
        id=uuid4(),
        kind=kind,
        storage_key=f"professionals/x/documents/{name}",
        filename=name,
        uploaded_at=NOW,
    )


async def reload(session: AsyncSession, professional: Professional) -> Professional:
    session.expunge_all()
    loaded = await SqlAlchemyProfessionalRepository(session).get(professional.id)
    assert loaded is not None
    return loaded


async def test_the_whole_registration_round_trips(
    session: AsyncSession, madrid_carpenter: Professional, carpentry: Category
) -> None:
    repo = SqlAlchemyProfessionalRepository(session)
    # El fixture llega aprobado; un alta nueva empieza incompleta.
    madrid_carpenter.verification_status = VerificationStatus.INCOMPLETE
    madrid_carpenter.set_identity(
        professional_type=ProfessionalType.SELF_EMPLOYED,
        legal_name="Ana Lopez Garcia",
        tax_id=TaxId("12345678Z"),
    )
    madrid_carpenter.address = "Calle Mayor 1, 28013 Madrid"
    madrid_carpenter.service_ids = {carpentry.services[0].id}
    madrid_carpenter.profile_photo_key = "professionals/x/media/cara.jpg"
    madrid_carpenter.logo_key = "professionals/x/media/logo.png"
    madrid_carpenter.work_photo_keys = [
        "professionals/x/media/b.jpg",
        "professionals/x/media/a.jpg",
    ]
    madrid_carpenter.add_document(document(DocumentKind.TAX_REGISTRATION, "036.pdf"))
    await repo.update(madrid_carpenter)
    await session.commit()

    loaded = await reload(session, madrid_carpenter)

    assert loaded.professional_type is ProfessionalType.SELF_EMPLOYED
    assert loaded.tax_id == TaxId("12345678Z")
    assert loaded.address == "Calle Mayor 1, 28013 Madrid"
    assert loaded.service_ids == {carpentry.services[0].id}
    assert loaded.work_photo_keys == madrid_carpenter.work_photo_keys  # en su orden
    assert [d.filename for d in loaded.documents] == ["036.pdf"]
    assert loaded.missing_for_review() == []


async def test_documents_can_be_swapped_in_one_save(
    session: AsyncSession, madrid_carpenter: Professional
) -> None:
    repo = SqlAlchemyProfessionalRepository(session)
    madrid_carpenter.verification_status = VerificationStatus.INCOMPLETE
    kept = document(DocumentKind.TAX_REGISTRATION, "036.pdf")
    dropped = document(DocumentKind.IDENTITY, "dni.pdf")
    madrid_carpenter.add_document(kept)
    madrid_carpenter.add_document(dropped)
    await repo.update(madrid_carpenter)
    await session.commit()

    # Guardar de nuevo el mismo documento con otro al lado no debe chocar con la
    # fila que ya existe (misma clave primaria en la misma sesion).
    professional = await repo.get(madrid_carpenter.id)
    assert professional is not None
    professional.remove_document(dropped.id)
    professional.add_document(document(DocumentKind.IDENTITY, "tie.pdf"))
    await repo.update(professional)
    await session.commit()

    loaded = await reload(session, professional)
    assert sorted(d.filename for d in loaded.documents) == ["036.pdf", "tie.pdf"]


async def test_verification_events_are_appended_in_order(
    session: AsyncSession, madrid_carpenter: Professional
) -> None:
    repo = SqlAlchemyProfessionalRepository(session)
    for offset, (before, after) in enumerate(
        [
            (VerificationStatus.INCOMPLETE, VerificationStatus.PENDING),
            (VerificationStatus.PENDING, VerificationStatus.APPROVED),
        ]
    ):
        await repo.add_verification_event(
            VerificationEvent(
                id=uuid4(),
                professional_id=madrid_carpenter.id,
                from_status=before,
                to_status=after,
                created_at=NOW + timedelta(minutes=offset),
            )
        )
    await session.commit()

    events = await repo.list_verification_events(madrid_carpenter.id)
    assert [e.to_status for e in events] == [
        VerificationStatus.PENDING,
        VerificationStatus.APPROVED,
    ]


async def test_the_review_queue_serves_the_oldest_submission_first(
    session: AsyncSession, madrid_carpenter: Professional
) -> None:
    repo = SqlAlchemyProfessionalRepository(session)
    madrid_carpenter.verification_status = VerificationStatus.PENDING
    madrid_carpenter.submitted_at = NOW + timedelta(days=1)
    await repo.update(madrid_carpenter)
    newer_user_first = await _another_pending(session, submitted=NOW)
    await session.commit()

    queue = await repo.list_admin(
        query=None, limit=10, offset=0, verification_status=VerificationStatus.PENDING
    )
    assert [p.id for p in queue] == [newer_user_first.id, madrid_carpenter.id]
    assert await repo.count_admin(query=None, verification_status=VerificationStatus.APPROVED) == 0


async def _another_pending(session: AsyncSession, *, submitted: datetime) -> Professional:
    from app.domain.models import User, UserRole
    from app.domain.value_objects import Email, PhoneNumber, PostalCode
    from app.infrastructure.adapters.db.repositories import SqlAlchemyUserRepository
    from tests.factories import MADRID

    user = await SqlAlchemyUserRepository(session).add(
        User(
            id=uuid4(),
            firebase_uid=f"fb-{uuid4().hex[:8]}",
            email=Email("otro@example.com"),
            role=UserRole.PROFESSIONAL,
            created_at=NOW,
        )
    )
    professional = Professional(
        id=uuid4(),
        user_id=user.id,
        business_name="Otro",
        phone=PhoneNumber("+34600999888"),
        base_postal_code=PostalCode("28001"),
        base_coordinates=MADRID,
        service_radius_km=25,
        created_at=NOW,
        verification_status=VerificationStatus.PENDING,
        submitted_at=submitted,
    )
    return await SqlAlchemyProfessionalRepository(session).add(professional)


async def test_for_update_serializes_verification_decisions(
    engine: AsyncEngine, session: AsyncSession, madrid_carpenter: Professional, carpentry: Category
) -> None:
    """Con Postgres real: la segunda decision sobre el alta espera a la primera.

    Es lo que impide que aprobar y rechazar a la vez dejen un aprobado con el primer
    cobro devuelto. La segunda sesion, al obtener el bloqueo, lee lo que confirmo la
    primera.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    order: list[str] = []
    seen: list[VerificationStatus] = []

    async def first() -> None:
        async with factory() as s1:
            repo = SqlAlchemyProfessionalRepository(s1)
            locked = await repo.get_for_update(madrid_carpenter.id)
            assert locked is not None
            order.append("primera-bloquea")
            await asyncio.sleep(0.3)
            locked.verification_status = VerificationStatus.REJECTED
            await repo.update(locked)
            order.append("primera-commit")
            await s1.commit()

    async def second() -> None:
        await asyncio.sleep(0.05)  # asegura que la primera bloquea antes
        async with factory() as s2:
            locked = await SqlAlchemyProfessionalRepository(s2).get_for_update(madrid_carpenter.id)
            assert locked is not None
            order.append("segunda-obtiene-bloqueo")
            seen.append(locked.verification_status)
            # Las relaciones llegan cargadas aunque el bloqueo vaya en otra consulta.
            assert locked.category_ids == {carpentry.id}
            await s2.commit()

    await asyncio.wait_for(asyncio.gather(first(), second()), timeout=10)

    assert order == ["primera-bloquea", "primera-commit", "segunda-obtiene-bloqueo"]
    assert seen == [VerificationStatus.REJECTED]


async def test_for_update_of_an_unknown_professional_is_none(session: AsyncSession) -> None:
    assert await SqlAlchemyProfessionalRepository(session).get_for_update(uuid4()) is None
