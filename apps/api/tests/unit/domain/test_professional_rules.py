"""Validacion del alta del profesional (F02): que se exige, quien compra y que se bloquea."""

from uuid import uuid4

import pytest

from app.domain.exceptions import (
    ProfessionalNotApprovedError,
    ProfessionalProfileIncompleteError,
    ProfessionalRejectedError,
    ValidationError,
    VerificationLockedError,
    VerificationTransitionError,
)
from app.domain.models import (
    DocumentKind,
    Professional,
    ProfessionalDocument,
    ProfessionalType,
    VerificationStatus,
)
from app.domain.value_objects import TaxId
from tests.factories import NOW, make_professional

ADMIN = uuid4()


def document(kind: DocumentKind) -> ProfessionalDocument:
    return ProfessionalDocument(
        id=uuid4(), kind=kind, storage_key="k", filename="modelo036.pdf", uploaded_at=NOW
    )


def complete(**kwargs: object) -> Professional:
    defaults: dict[str, object] = {
        "verification_status": VerificationStatus.INCOMPLETE,
        "professional_type": ProfessionalType.SELF_EMPLOYED,
        "legal_name": "Ana Lopez Garcia",
        "tax_id": TaxId("12345678Z"),
        "address": "Calle Mayor 1, Madrid",
        "documents": [document(DocumentKind.TAX_REGISTRATION)],
    }
    defaults.update(kwargs)
    return make_professional(**defaults)


def pending() -> Professional:
    professional = complete()
    professional.submit_for_review(event_id=uuid4(), now=NOW)
    return professional


class TestRequirements:
    def test_a_complete_profile_has_nothing_missing(self) -> None:
        assert complete().missing_for_review() == []

    def test_lists_everything_missing_on_an_empty_profile(self) -> None:
        empty = make_professional(verification_status=VerificationStatus.INCOMPLETE)
        assert empty.missing_for_review() == [
            "professional_type",
            "legal_name",
            "tax_id",
            "address",
        ]

    @pytest.mark.parametrize(
        ("kind", "wrong_document", "missing"),
        [
            (ProfessionalType.SELF_EMPLOYED, DocumentKind.IDENTITY, "document_tax_registration"),
            (ProfessionalType.COMPANY, DocumentKind.IDENTITY, "document_tax_registration"),
            (ProfessionalType.INDEPENDENT, DocumentKind.TAX_REGISTRATION, "document_identity"),
        ],
    )
    def test_each_type_needs_its_own_document(
        self, kind: ProfessionalType, wrong_document: DocumentKind, missing: str
    ) -> None:
        tax_id = TaxId("B12345674") if kind is ProfessionalType.COMPANY else TaxId("12345678Z")
        professional = complete(
            professional_type=kind, tax_id=tax_id, documents=[document(wrong_document)]
        )
        assert professional.missing_for_review() == [missing]

    @pytest.mark.parametrize("kind", list(ProfessionalType))
    def test_every_type_needs_a_tax_id_even_with_an_identity_document(
        self, kind: ProfessionalType
    ) -> None:
        document_kind = (
            DocumentKind.IDENTITY
            if kind is ProfessionalType.INDEPENDENT
            else DocumentKind.TAX_REGISTRATION
        )
        professional = complete(
            professional_type=kind, tax_id=None, documents=[document(document_kind)]
        )
        assert professional.missing_for_review() == ["tax_id"]

    def test_a_company_is_identified_by_its_cif(self) -> None:
        with pytest.raises(ValidationError):
            complete(professional_type=ProfessionalType.COMPANY, tax_id=TaxId("12345678Z"))


class TestTransitions:
    def test_submit_moves_to_review_and_records_who_and_when(self) -> None:
        professional = complete()
        event = professional.submit_for_review(event_id=uuid4(), now=NOW)
        assert professional.verification_status is VerificationStatus.PENDING
        assert professional.submitted_at == NOW
        assert (event.from_status, event.to_status) == (
            VerificationStatus.INCOMPLETE,
            VerificationStatus.PENDING,
        )
        assert event.actor_user_id is None

    def test_an_incomplete_profile_cannot_be_submitted(self) -> None:
        professional = complete(address=None)
        with pytest.raises(ProfessionalProfileIncompleteError) as error:
            professional.submit_for_review(event_id=uuid4(), now=NOW)
        assert error.value.details == {"missing": ["address"]}
        assert professional.verification_status is VerificationStatus.INCOMPLETE

    def test_the_admin_approves_a_pending_profile(self) -> None:
        professional = pending()
        event = professional.approve(event_id=uuid4(), now=NOW, admin_user_id=ADMIN)
        assert professional.is_approved
        assert event.actor_user_id == ADMIN

    def test_rejection_needs_a_reason_that_is_kept(self) -> None:
        professional = pending()
        with pytest.raises(ValidationError):
            professional.reject(event_id=uuid4(), now=NOW, admin_user_id=ADMIN, reason="  ")
        event = professional.reject(
            event_id=uuid4(), now=NOW, admin_user_id=ADMIN, reason="Documento ilegible"
        )
        assert professional.verification_status is VerificationStatus.REJECTED
        assert professional.rejection_reason == "Documento ilegible"
        assert event.note == "Documento ilegible"

    @pytest.mark.parametrize(
        "status",
        [VerificationStatus.INCOMPLETE, VerificationStatus.APPROVED, VerificationStatus.REJECTED],
    )
    def test_only_a_pending_profile_can_be_reviewed(self, status: VerificationStatus) -> None:
        professional = complete(verification_status=status)
        with pytest.raises(VerificationTransitionError):
            professional.approve(event_id=uuid4(), now=NOW, admin_user_id=ADMIN)
        with pytest.raises(VerificationTransitionError):
            professional.reject(event_id=uuid4(), now=NOW, admin_user_id=ADMIN, reason="x")

    def test_a_profile_is_submitted_only_once(self) -> None:
        professional = pending()
        with pytest.raises(VerificationTransitionError):
            professional.submit_for_review(event_id=uuid4(), now=NOW)


class TestAccess:
    @pytest.mark.parametrize("status", [VerificationStatus.INCOMPLETE, VerificationStatus.PENDING])
    def test_not_yet_approved_can_browse_but_not_buy(self, status: VerificationStatus) -> None:
        professional = complete(verification_status=status)
        professional.assert_ready_to_browse()
        with pytest.raises(ProfessionalNotApprovedError):
            professional.assert_can_purchase()

    def test_approved_can_buy(self) -> None:
        complete(verification_status=VerificationStatus.APPROVED).assert_can_purchase()

    def test_rejected_can_neither_browse_nor_buy(self) -> None:
        professional = complete(verification_status=VerificationStatus.REJECTED)
        with pytest.raises(ProfessionalRejectedError):
            professional.assert_ready_to_browse()
        with pytest.raises(ProfessionalRejectedError):
            professional.assert_can_purchase()


class TestLockAfterSubmitting:
    def test_identity_can_change_while_incomplete(self) -> None:
        professional = complete()
        professional.set_identity(
            professional_type=ProfessionalType.COMPANY,
            legal_name="Reformas Lopez SL",
            tax_id=TaxId("B12345674"),
        )
        assert professional.legal_name == "Reformas Lopez SL"

    def test_identity_is_locked_once_submitted(self) -> None:
        professional = pending()
        with pytest.raises(VerificationLockedError):
            professional.set_identity(
                professional_type=ProfessionalType.SELF_EMPLOYED,
                legal_name="Otro nombre",
                tax_id=professional.tax_id,
            )
        with pytest.raises(VerificationLockedError):
            professional.add_document(document(DocumentKind.IDENTITY))
        with pytest.raises(VerificationLockedError):
            professional.remove_document(professional.documents[0].id)

    def test_resending_the_same_identity_is_not_a_change(self) -> None:
        professional = pending()
        # El formulario manda el perfil entero en cada guardado.
        professional.set_identity(
            professional_type=professional.professional_type,
            legal_name=professional.legal_name,
            tax_id=professional.tax_id,
        )
