"""Tests de la regla central del negocio: el lead capping y el ocultamiento de PII."""

from uuid import uuid4

import pytest

from app.domain.exceptions import (
    CategoryMismatchError,
    ConsentRequiredError,
    ContactLockedError,
    LeadAlreadyPurchasedError,
    LeadCapReachedError,
    LeadNotPurchasableError,
    ValidationError,
)
from app.domain.models import LeadSource, LeadStatus
from tests.factories import make_lead


class TestLeadCapping:
    def test_open_lead_with_free_slots_is_purchasable(self) -> None:
        lead = make_lead(max_purchases=3, purchases_count=1)
        lead.assert_purchasable(occupied_slots=1, already_purchased_by_professional=False)

    def test_cap_counts_reserved_slots_not_only_paid(self) -> None:
        # 2 compras pagadas + 1 reserva viva = 3 plazas ocupadas de 3.
        lead = make_lead(max_purchases=3, purchases_count=2)
        with pytest.raises(LeadCapReachedError):
            lead.assert_purchasable(occupied_slots=3, already_purchased_by_professional=False)

    def test_exhausted_lead_is_not_purchasable(self) -> None:
        lead = make_lead(status=LeadStatus.EXHAUSTED, purchases_count=3)
        with pytest.raises(LeadCapReachedError):
            lead.assert_purchasable(occupied_slots=3, already_purchased_by_professional=False)

    def test_disabled_lead_is_not_purchasable(self) -> None:
        lead = make_lead(status=LeadStatus.DISABLED)
        with pytest.raises(LeadNotPurchasableError) as exc:
            lead.assert_purchasable(occupied_slots=0, already_purchased_by_professional=False)
        assert exc.value.code == "LEAD_NOT_PURCHASABLE"

    def test_same_professional_cannot_buy_twice(self) -> None:
        lead = make_lead()
        with pytest.raises(LeadAlreadyPurchasedError):
            lead.assert_purchasable(occupied_slots=1, already_purchased_by_professional=True)

    def test_lead_outside_professional_categories_is_rejected(self) -> None:
        lead = make_lead()
        with pytest.raises(CategoryMismatchError):
            lead.assert_purchasable(
                occupied_slots=0,
                already_purchased_by_professional=False,
                professional_category_ids={uuid4()},
            )

    def test_matching_category_passes(self) -> None:
        lead = make_lead()
        lead.assert_purchasable(
            occupied_slots=0,
            already_purchased_by_professional=False,
            professional_category_ids={lead.category_id, uuid4()},
        )

    def test_register_paid_purchase_exhausts_lead_at_cap(self) -> None:
        lead = make_lead(max_purchases=2)
        lead.register_paid_purchase()
        assert lead.status is LeadStatus.PUBLISHED
        assert lead.remaining_slots == 1

        lead.register_paid_purchase()
        assert lead.status is LeadStatus.EXHAUSTED
        assert lead.remaining_slots == 0
        assert lead.is_open is False

    def test_register_paid_purchase_beyond_cap_raises(self) -> None:
        lead = make_lead(max_purchases=1, purchases_count=1)
        with pytest.raises(LeadCapReachedError):
            lead.register_paid_purchase()

    def test_disable_and_republish(self) -> None:
        lead = make_lead(max_purchases=3, purchases_count=1)
        lead.disable()
        assert lead.is_open is False
        lead.republish()
        assert lead.is_open is True

    def test_republish_exhausted_lead_raises(self) -> None:
        lead = make_lead(max_purchases=1, purchases_count=1, status=LeadStatus.DISABLED)
        with pytest.raises(LeadCapReachedError):
            lead.republish()


class TestLeadPiiProtection:
    def test_public_view_contains_no_client_pii(self) -> None:
        lead = make_lead()
        view = lead.public_view()
        serialized = repr(view)

        assert lead.contact.name not in serialized
        assert lead.contact.phone.value not in serialized
        assert lead.contact.email is not None
        assert lead.contact.email.value not in serialized

    def test_public_view_exposes_only_postal_prefix(self) -> None:
        lead = make_lead()
        view = lead.public_view()
        assert view.postal_code_prefix == "28"
        assert view.city == "Madrid"

    def test_public_view_masks_contact_hints(self) -> None:
        view = make_lead().public_view()
        assert view.masked_phone.endswith("44")
        assert view.masked_email is not None
        assert view.masked_email.endswith("@example.com")

    def test_public_view_orders_photos(self) -> None:
        from app.domain.models import LeadPhoto

        lead = make_lead(
            photos=[
                LeadPhoto(storage_key="b.jpg", sort_order=2),
                LeadPhoto(storage_key="a.jpg", sort_order=1),
            ]
        )
        assert lead.public_view().photo_keys == ["a.jpg", "b.jpg"]

    def test_contact_view_requires_unlock(self) -> None:
        lead = make_lead()
        with pytest.raises(ContactLockedError):
            lead.contact_view(unlocked=False)
        assert lead.contact_view(unlocked=True).name == "Ana Lopez"


class TestLeadInvariants:
    def test_organic_lead_without_consent_is_rejected(self) -> None:
        with pytest.raises(ConsentRequiredError):
            make_lead(source=LeadSource.ORGANIC, consent=None)

    def test_admin_lead_may_omit_web_consent(self) -> None:
        lead = make_lead(source=LeadSource.ADMIN, consent=None)
        assert lead.source is LeadSource.ADMIN

    def test_short_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_lead(description="muy corto")

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_lead(title="   ")

    def test_too_many_photos_rejected(self) -> None:
        from app.domain.models import LeadPhoto

        with pytest.raises(ValidationError):
            make_lead(photos=[LeadPhoto(storage_key=f"{i}.jpg") for i in range(9)])

    def test_title_and_description_are_trimmed(self) -> None:
        lead = make_lead(title="  Pintar salon  ")
        assert lead.title == "Pintar salon"
