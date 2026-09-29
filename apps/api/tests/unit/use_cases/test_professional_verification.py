"""Alta y validacion del profesional (F02) con fakes de todos los puertos."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.application.dto import UpsertProfessionalInput
from app.application.use_cases import UploadPurpose
from app.domain.exceptions import (
    InvalidServiceError,
    InvalidTaxIdError,
    PaymentGatewayError,
    PhoneNotMobileError,
    PostalCodeNotCoveredError,
    ProfessionalNotApprovedError,
    ProfessionalProfileIncompleteError,
    ValidationError,
    VerificationLockedError,
    VerificationTransitionError,
)
from app.domain.models import (
    Category,
    CreditEntry,
    CreditEntryKind,
    DocumentKind,
    Professional,
    ProfessionalType,
    Service,
    VerificationStatus,
)
from app.domain.value_objects import Money, TaxId
from tests.conftest import World
from tests.factories import NOW, make_lead

ADMIN = uuid4()


def profile(category: Category, **overrides: object) -> UpsertProfessionalInput:
    data: dict[str, object] = {
        "business_name": "Reformas Lopez",
        "phone": "+34611223344",
        "postal_code": "28001",
        "service_radius_km": 25,
        "category_ids": {category.id},
        "professional_type": ProfessionalType.SELF_EMPLOYED,
        "legal_name": "Ana Lopez Garcia",
        "tax_id": "12345678Z",
        "address": "Calle Mayor 1, Madrid",
    }
    data.update(overrides)
    return UpsertProfessionalInput(**data)  # type: ignore[arg-type]


async def registered(world: World, category: Category, **overrides: object) -> Professional:
    user = world.add_user()
    return await world.upsert_profile.execute(user_id=user.id, data=profile(category, **overrides))


async def with_document(world: World, professional: Professional) -> Professional:
    await world.add_document.execute(
        professional_id=professional.id,
        kind=DocumentKind.TAX_REGISTRATION,
        storage_key=f"professionals/{professional.id}/documents/036.pdf",
        filename="036.pdf",
    )
    return world.professionals.items[professional.id]


async def pending(world: World, category: Category) -> Professional:
    professional = await with_document(world, await registered(world, category))
    return await world.submit_for_review.execute(professional_id=professional.id)


class TestRegistration:
    async def test_stores_the_registration_data(self, world: World, carpentry: Category) -> None:
        professional = await registered(world, carpentry)
        assert professional.verification_status is VerificationStatus.INCOMPLETE
        assert professional.tax_id == TaxId("12345678Z")
        assert professional.missing_for_review() == ["document_tax_registration"]

    async def test_base_must_be_in_madrid(self, world: World, carpentry: Category) -> None:
        with pytest.raises(PostalCodeNotCoveredError):
            await registered(world, carpentry, postal_code="08001")

    async def test_needs_a_mobile_phone(self, world: World, carpentry: Category) -> None:
        with pytest.raises(PhoneNotMobileError):
            await registered(world, carpentry, phone="912345678")

    async def test_rejects_a_mistyped_tax_id(self, world: World, carpentry: Category) -> None:
        with pytest.raises(InvalidTaxIdError):
            await registered(world, carpentry, tax_id="12345678A")

    async def test_services_must_belong_to_the_chosen_trades(self, world: World) -> None:
        mine = Service(id=uuid4(), slug="puertas", name_es="Puertas", name_en="Doors")
        other = Service(id=uuid4(), slug="aerotermia", name_es="Aerotermia", name_en="Heat")
        carpentry = world.add_category(slug="carpinteria", services=[mine])
        world.add_category(slug="instaladores", services=[other])

        ok = await registered(world, carpentry, service_ids={mine.id})
        assert ok.service_ids == {mine.id}
        with pytest.raises(InvalidServiceError):
            await registered(world, carpentry, service_ids={other.id})

    async def test_photos_must_be_uploaded_by_this_professional(
        self, world: World, carpentry: Category
    ) -> None:
        user = world.add_user()
        created = await world.upsert_profile.execute(user_id=user.id, data=profile(carpentry))
        own = f"professionals/{created.id}/media/cara.jpg"
        updated = await world.upsert_profile.execute(
            user_id=user.id, data=profile(carpentry, profile_photo_key=own)
        )
        assert updated.profile_photo_key == own

        stolen = f"professionals/{uuid4()}/media/cara.jpg"
        with pytest.raises(ValidationError):
            await world.upsert_profile.execute(
                user_id=user.id, data=profile(carpentry, profile_photo_key=stolen)
            )

    async def test_identity_is_locked_once_submitted(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await pending(world, carpentry)
        user_id = professional.user_id
        # El resto del perfil se sigue pudiendo editar...
        updated = await world.upsert_profile.execute(
            user_id=user_id, data=profile(carpentry, service_radius_km=40)
        )
        assert updated.service_radius_km == 40
        # ...pero no lo que se valido.
        with pytest.raises(VerificationLockedError):
            await world.upsert_profile.execute(
                user_id=user_id, data=profile(carpentry, legal_name="Otro titular")
            )


class TestUploads:
    async def test_documents_go_to_the_private_bucket(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await registered(world, carpentry)
        upload = await world.request_professional_upload.execute(
            professional_id=professional.id,
            purpose=UploadPurpose.DOCUMENT,
            filename="036.pdf",
            content_type="application/pdf",
        )
        assert upload.storage_key.startswith(f"professionals/{professional.id}/documents/")
        assert upload.upload_url.startswith(world.private_storage.base_url)

    async def test_photos_go_to_the_public_bucket_and_must_be_images(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await registered(world, carpentry)
        upload = await world.request_professional_upload.execute(
            professional_id=professional.id,
            purpose=UploadPurpose.MEDIA,
            filename="logo.png",
            content_type="image/png",
        )
        assert upload.upload_url.startswith(world.storage.base_url)
        with pytest.raises(ValidationError):
            await world.request_professional_upload.execute(
                professional_id=professional.id,
                purpose=UploadPurpose.MEDIA,
                filename="logo.pdf",
                content_type="application/pdf",
            )

    async def test_a_document_from_someone_else_cannot_be_attached(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await registered(world, carpentry)
        with pytest.raises(ValidationError):
            await world.add_document.execute(
                professional_id=professional.id,
                kind=DocumentKind.IDENTITY,
                storage_key=f"professionals/{uuid4()}/documents/dni.pdf",
                filename="dni.pdf",
            )

    async def test_removing_a_document_deletes_the_file(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await with_document(world, await registered(world, carpentry))
        document = professional.documents[0]
        await world.remove_document.execute(
            professional_id=professional.id, document_id=document.id
        )
        assert world.professionals.items[professional.id].documents == []
        assert world.private_storage.deleted == [document.storage_key]


class TestReview:
    async def test_submitting_needs_the_documents(self, world: World, carpentry: Category) -> None:
        professional = await registered(world, carpentry)
        with pytest.raises(ProfessionalProfileIncompleteError) as error:
            await world.submit_for_review.execute(professional_id=professional.id)
        assert error.value.details == {"missing": ["document_tax_registration"]}

    async def test_submitting_leaves_an_audit_trail(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await pending(world, carpentry)
        assert professional.verification_status is VerificationStatus.PENDING
        events = await world.professionals.list_verification_events(professional.id)
        assert [(e.from_status, e.to_status, e.actor_user_id) for e in events] == [
            (VerificationStatus.INCOMPLETE, VerificationStatus.PENDING, None)
        ]

    async def test_approval_is_recorded_with_the_admin(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await pending(world, carpentry)
        approved = await world.approve_professional.execute(
            professional_id=professional.id, admin_user_id=ADMIN
        )
        assert approved.is_approved
        events = await world.professionals.list_verification_events(professional.id)
        assert events[-1].actor_user_id == ADMIN

    async def test_the_dossier_signs_document_downloads_from_the_private_bucket(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await pending(world, carpentry)
        dossier = await world.verification_dossier.execute(professional_id=professional.id)
        assert [d.document.filename for d in dossier.documents] == ["036.pdf"]
        assert dossier.documents[0].download_url.startswith(world.private_storage.base_url)
        assert len(dossier.events) == 1


class TestPurchaseNeedsApproval:
    @pytest.mark.parametrize("status", [VerificationStatus.INCOMPLETE, VerificationStatus.PENDING])
    async def test_not_approved_cannot_buy_even_with_the_top_up(
        self, world: World, carpentry: Category, status: VerificationStatus
    ) -> None:
        professional = world.add_professional(
            category_ids={carpentry.id}, verification_status=status
        )
        lead = make_lead(category_id=carpentry.id)
        world.leads.items[lead.id] = lead

        with pytest.raises(ProfessionalNotApprovedError):
            await world.start_purchase.execute(lead_id=lead.id, professional_id=professional.id)
        assert world.purchases.items == {}

    async def test_pending_can_still_browse(self, world: World, carpentry: Category) -> None:
        professional = world.add_professional(
            category_ids={carpentry.id}, verification_status=VerificationStatus.PENDING
        )
        lead = make_lead(category_id=carpentry.id)
        world.leads.items[lead.id] = lead
        result = await world.list_leads.execute(professional_id=professional.id)
        assert [item.lead.id for item in result.items] == [lead.id]


def paid_topup(world: World, professional_id: UUID, invoice: str, *, days: int = 0) -> None:
    world.ledger.entries.append(
        CreditEntry(
            id=uuid4(),
            professional_id=professional_id,
            kind=CreditEntryKind.TOPUP,
            amount=Money(1800, "EUR"),
            source_ref=invoice,
            created_at=NOW + timedelta(days=days),
        )
    )


class TestRejection:
    async def rejected_after_paying(self, world: World, carpentry: Category) -> Professional:
        professional = await pending(world, carpentry)
        world.add_account(professional, balance_cents=3600)
        paid_topup(world, professional.id, "in_second", days=30)
        paid_topup(world, professional.id, "in_first")
        return professional

    async def test_refunds_the_first_charge_and_cancels_the_top_up(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await self.rejected_after_paying(world, carpentry)

        result = await world.reject_professional.execute(
            professional_id=professional.id, admin_user_id=ADMIN, reason="Documento ilegible"
        )

        assert result.professional.verification_status is VerificationStatus.REJECTED
        assert result.refunded == Money(1800, "EUR")
        assert result.subscription_canceled
        # El primer cobro, no el ultimo.
        assert list(world.payments.refunds.values()) == ["in_first"]
        account = world.accounts.items[professional.id]
        assert account.stripe_subscription_id in world.payments.canceled_subscriptions
        assert account.balance == Money(1800, "EUR")
        refunds = [e for e in world.ledger.entries if e.kind is CreditEntryKind.VERIFICATION_REFUND]
        assert [(e.source_ref, e.amount) for e in refunds] == [("in_first", Money(1800, "EUR"))]

    async def test_a_gateway_failure_changes_nothing_and_can_be_retried(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await self.rejected_after_paying(world, carpentry)
        world.payments.fail_on_refund = True

        with pytest.raises(PaymentGatewayError):
            await world.reject_professional.execute(
                professional_id=professional.id, admin_user_id=ADMIN, reason="Ilegible"
            )
        stored = world.professionals.items[professional.id]
        assert stored.verification_status is VerificationStatus.PENDING
        assert world.accounts.items[professional.id].balance == Money(3600, "EUR")

        world.payments.fail_on_refund = False
        await world.reject_professional.execute(
            professional_id=professional.id, admin_user_id=ADMIN, reason="Ilegible"
        )
        assert len(world.payments.refunds) == 1
        assert world.accounts.items[professional.id].balance == Money(1800, "EUR")

    async def test_never_withdraws_more_than_the_balance(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await pending(world, carpentry)
        world.add_account(professional, balance_cents=500)
        paid_topup(world, professional.id, "in_first")

        await world.reject_professional.execute(
            professional_id=professional.id, admin_user_id=ADMIN, reason="Ilegible"
        )
        assert world.accounts.items[professional.id].balance == Money(0, "EUR")

    async def test_without_payment_there_is_nothing_to_refund(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await pending(world, carpentry)
        result = await world.reject_professional.execute(
            professional_id=professional.id, admin_user_id=ADMIN, reason="Ilegible"
        )
        assert result.refunded is None
        assert not result.subscription_canceled
        assert world.payments.refunds == {}

    async def test_an_approved_professional_is_not_rejected_nor_refunded(
        self, world: World, carpentry: Category
    ) -> None:
        professional = await self.rejected_after_paying(world, carpentry)
        await world.approve_professional.execute(
            professional_id=professional.id, admin_user_id=ADMIN
        )
        with pytest.raises(VerificationTransitionError):
            await world.reject_professional.execute(
                professional_id=professional.id, admin_user_id=ADMIN, reason="Ilegible"
            )
        assert world.payments.refunds == {}
        assert world.payments.canceled_subscriptions == set()
