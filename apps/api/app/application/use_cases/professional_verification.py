"""Validacion del alta del profesional (F02): enviar a revision, aprobar y rechazar.

Tras registrarse y configurar su perfil, el profesional envia sus datos y documentos
a revision. Mientras esta "en revision" ve solicitudes pero no compra; compra solo
cuando el admin lo aprueba. Si lo rechaza, se le reembolsa el primer cobro de la
recarga y se cancela la suscripcion (documento del cliente, F02).

Cada cambio de estado deja un `VerificationEvent`: es la auditoria de quien decidio
que y cuando.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto import (
    DocumentDownload,
    RejectionResult,
    VerificationDossier,
)
from app.application.ports import (
    CategoryRepositoryPort,
    ClockPort,
    CreditLedgerRepositoryPort,
    IdGeneratorPort,
    PaymentPort,
    ProfessionalAccountRepositoryPort,
    ProfessionalRepositoryPort,
    StoragePort,
    UnitOfWork,
    UserRepositoryPort,
)
from app.application.use_cases.credit_ledger import CreditLedgerService
from app.domain.exceptions import ProfessionalNotFoundError, VerificationTransitionError
from app.domain.models import CreditEntryKind, Professional, VerificationStatus
from app.domain.value_objects import Money


async def _load(professionals: ProfessionalRepositoryPort, professional_id: UUID) -> Professional:
    professional = await professionals.get(professional_id)
    if professional is None:
        raise ProfessionalNotFoundError()
    return professional


@dataclass(slots=True)
class SubmitForReview:
    """El profesional envia su alta. Falla con la lista de lo que le falta."""

    professionals: ProfessionalRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(self, *, professional_id: UUID) -> Professional:
        professional = await _load(self.professionals, professional_id)
        event = professional.submit_for_review(event_id=self.ids.new_id(), now=self.clock.now())
        async with self.uow:
            await self.professionals.update(professional)
            await self.professionals.add_verification_event(event)
        return professional


@dataclass(slots=True)
class ApproveProfessional:
    professionals: ProfessionalRepositoryPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(self, *, professional_id: UUID, admin_user_id: UUID) -> Professional:
        professional = await _load(self.professionals, professional_id)
        event = professional.approve(
            event_id=self.ids.new_id(), now=self.clock.now(), admin_user_id=admin_user_id
        )
        async with self.uow:
            await self.professionals.update(professional)
            await self.professionals.add_verification_event(event)
        return professional


@dataclass(slots=True)
class RejectProfessional:
    """Rechaza el alta: reembolsa el primer cobro y cancela la recarga.

    La pasarela va PRIMERO y con operaciones idempotentes (clave de idempotencia en
    el reembolso; cancelar dos veces no falla). Si falla, no se guarda nada y el admin
    puede reintentar. Si falla despues, al guardar, el reintento repite la pasarela
    sin efecto y termina de guardar. Al reves (guardar primero) un fallo de la
    pasarela dejaria un rechazado sin reembolso y sin nadie que lo reintente.

    El saldo de ese primer cobro se retira con un movimiento propio
    (`VERIFICATION_REFUND`) sobre la misma factura: el `UNIQUE (kind, source_ref)`
    del libro impide retirarlo dos veces.
    """

    professionals: ProfessionalRepositoryPort
    accounts: ProfessionalAccountRepositoryPort
    ledger: CreditLedgerRepositoryPort
    credit: CreditLedgerService
    payments: PaymentPort
    clock: ClockPort
    ids: IdGeneratorPort
    uow: UnitOfWork

    async def execute(
        self, *, professional_id: UUID, admin_user_id: UUID, reason: str
    ) -> RejectionResult:
        professional = await _load(self.professionals, professional_id)
        # Se comprueba antes de tocar la pasarela: rechazar un alta aprobada no
        # debe reembolsar a nadie.
        if professional.verification_status is not VerificationStatus.PENDING:
            raise VerificationTransitionError(
                f"Solo se rechaza un alta en revision, no una {professional.verification_status}"
            )

        account = await self.accounts.get(professional_id)
        first_charge = await self.ledger.first_topup(professional_id)

        subscription_canceled = False
        if account is not None and account.stripe_subscription_id:
            await self.payments.cancel_subscription(account.stripe_subscription_id)
            subscription_canceled = True
        if first_charge is not None:
            await self.payments.refund_invoice(
                invoice_id=first_charge.source_ref,
                idempotency_key=f"verification-refund-{first_charge.source_ref}",
            )

        now = self.clock.now()
        event = professional.reject(
            event_id=self.ids.new_id(), now=now, admin_user_id=admin_user_id, reason=reason
        )
        refunded: Money | None = None
        async with self.uow:
            await self.professionals.update(professional)
            await self.professionals.add_verification_event(event)
            if first_charge is not None:
                refunded = first_charge.amount
                locked = await self.accounts.get_for_update(professional_id)
                if locked is not None:
                    # Nunca por encima del saldo: si el admin ya habia retirado parte,
                    # se retira lo que quede (el reembolso de la pasarela es integro).
                    withdraw = min(first_charge.amount.amount_cents, locked.balance.amount_cents)
                    if withdraw > 0:
                        await self.credit.record(
                            locked,
                            kind=CreditEntryKind.VERIFICATION_REFUND,
                            amount=Money(withdraw, first_charge.amount.currency),
                            source_ref=first_charge.source_ref,
                            now=now,
                            note="Reembolso del primer cobro al rechazar el alta",
                            created_by_user_id=admin_user_id,
                        )
        return RejectionResult(
            professional=professional,
            refunded=refunded,
            subscription_canceled=subscription_canceled,
        )


@dataclass(slots=True)
class GetVerificationDossier:
    """Expediente para el admin: perfil, documentos (descarga firmada) y auditoria."""

    professionals: ProfessionalRepositoryPort
    categories: CategoryRepositoryPort
    users: UserRepositoryPort
    documents: StoragePort
    """El almacenamiento PRIVADO: los documentos nunca van al bucket publico."""

    async def execute(self, *, professional_id: UUID) -> VerificationDossier:
        professional = await _load(self.professionals, professional_id)
        user = await self.users.get(professional.user_id)
        downloads = [
            DocumentDownload(
                document=document,
                download_url=await self.documents.signed_download_url(
                    document.storage_key, filename=document.filename
                ),
            )
            for document in professional.documents
        ]
        return VerificationDossier(
            professional=professional,
            categories=await self.categories.get_many(professional.category_ids),
            documents=downloads,
            events=await self.professionals.list_verification_events(professional_id),
            email=user.email.value if user is not None else None,
        )
