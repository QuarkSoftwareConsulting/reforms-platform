"""Tests del espejo de identidad Firebase, el perfil profesional y el job de reservas."""

import pytest

from app.application.dto import UpsertProfessionalInput
from app.application.ports import AuthenticatedIdentity
from app.domain.exceptions import (
    CategoryNotFoundError,
    ProfessionalNotFoundError,
    UnknownPostalCodeError,
    ValidationError,
)
from app.domain.models import Category, PurchaseStatus, UserRole
from tests.conftest import World
from tests.factories import make_lead


class TestIdentityMirror:
    async def test_creates_local_user_on_first_login(self, world: World) -> None:
        user = await world.sync_user.execute(
            AuthenticatedIdentity(
                provider_uid="fb-uid-1",
                email="pro@example.com",
                email_verified=True,
                display_name="Carpinteria Lopez",
            )
        )

        assert user.firebase_uid == "fb-uid-1"
        assert user.email.value == "pro@example.com"
        assert user.role is UserRole.PROFESSIONAL
        assert world.users.items[user.id] is user

    async def test_second_login_reuses_the_same_local_user(self, world: World) -> None:
        identity = AuthenticatedIdentity(provider_uid="fb-uid-1", email="pro@example.com")
        first = await world.sync_user.execute(identity)
        second = await world.sync_user.execute(identity)

        assert first.id == second.id
        assert len(world.users.items) == 1

    async def test_admin_custom_claim_promotes_the_role(self, world: World) -> None:
        user = await world.sync_user.execute(
            AuthenticatedIdentity(
                provider_uid="fb-admin", email="admin@example.com", is_admin_claim=True
            )
        )
        assert user.role is UserRole.ADMIN

    async def test_email_change_in_firebase_is_mirrored(self, world: World) -> None:
        await world.sync_user.execute(
            AuthenticatedIdentity(provider_uid="fb-uid-1", email="old@example.com")
        )
        updated = await world.sync_user.execute(
            AuthenticatedIdentity(provider_uid="fb-uid-1", email="new@example.com")
        )
        assert updated.email.value == "new@example.com"
        assert len(world.users.items) == 1

    async def test_identity_without_email_is_rejected(self, world: World) -> None:
        with pytest.raises(ValidationError, match="email"):
            await world.sync_user.execute(AuthenticatedIdentity(provider_uid="fb-anon", email=None))


class TestProfessionalProfile:
    async def test_creates_profile_resolving_location_from_postal_code(
        self, world: World, carpentry: Category
    ) -> None:
        user = world.add_user()
        professional = await world.upsert_profile.execute(
            user_id=user.id,
            data=UpsertProfessionalInput(
                business_name="Carpinteria Lopez",
                phone="+34600111222",
                postal_code="08001",
                service_radius_km=40,
                category_ids={carpentry.id},
            ),
        )

        assert professional.city == "Barcelona"
        assert professional.province == "Barcelona"
        assert professional.service_radius_km == 40
        assert professional.category_ids == {carpentry.id}

    async def test_updating_profile_does_not_duplicate_it(
        self, world: World, carpentry: Category, plumbing: Category
    ) -> None:
        user = world.add_user()
        data = UpsertProfessionalInput(
            business_name="Reformas SL",
            phone="+34600111222",
            postal_code="28001",
            service_radius_km=20,
            category_ids={carpentry.id},
        )
        first = await world.upsert_profile.execute(user_id=user.id, data=data)

        second = await world.upsert_profile.execute(
            user_id=user.id,
            data=UpsertProfessionalInput(
                business_name="Reformas SL",
                phone="+34600111222",
                postal_code="08001",
                service_radius_km=60,
                category_ids={carpentry.id, plumbing.id},
            ),
        )

        assert first.id == second.id
        assert len(world.professionals.items) == 1
        assert second.service_radius_km == 60
        assert second.city == "Barcelona"
        assert second.category_ids == {carpentry.id, plumbing.id}

    async def test_invalid_radius_is_rejected_on_update(
        self, world: World, carpentry: Category
    ) -> None:
        user = world.add_user()
        base = UpsertProfessionalInput(
            business_name="Reformas SL",
            phone="+34600111222",
            postal_code="28001",
            service_radius_km=20,
            category_ids={carpentry.id},
        )
        await world.upsert_profile.execute(user_id=user.id, data=base)

        with pytest.raises(ValidationError):
            await world.upsert_profile.execute(
                user_id=user.id,
                data=UpsertProfessionalInput(
                    business_name="Reformas SL",
                    phone="+34600111222",
                    postal_code="28001",
                    service_radius_km=5000,
                    category_ids={carpentry.id},
                ),
            )

    async def test_unknown_postal_code_is_rejected(self, world: World, carpentry: Category) -> None:
        user = world.add_user()
        with pytest.raises(UnknownPostalCodeError):
            await world.upsert_profile.execute(
                user_id=user.id,
                data=UpsertProfessionalInput(
                    business_name="Reformas SL",
                    phone="+34600111222",
                    postal_code="99999",
                    service_radius_km=20,
                    category_ids={carpentry.id},
                ),
            )

    async def test_inactive_category_is_rejected(self, world: World) -> None:
        user = world.add_user()
        inactive = world.add_category(slug="obsoleto", active=False)
        with pytest.raises(CategoryNotFoundError):
            await world.upsert_profile.execute(
                user_id=user.id,
                data=UpsertProfessionalInput(
                    business_name="Reformas SL",
                    phone="+34600111222",
                    postal_code="28001",
                    service_radius_km=20,
                    category_ids={inactive.id},
                ),
            )

    async def test_get_profile_returns_categories(self, world: World, carpentry: Category) -> None:
        user = world.add_user()
        await world.upsert_profile.execute(
            user_id=user.id,
            data=UpsertProfessionalInput(
                business_name="Reformas SL",
                phone="+34600111222",
                postal_code="28001",
                service_radius_km=20,
                category_ids={carpentry.id},
            ),
        )
        profile = await world.get_profile.execute(user_id=user.id)
        assert [c.slug for c in profile.categories] == ["carpinteria"]

    async def test_get_profile_without_profile_raises(self, world: World) -> None:
        user = world.add_user()
        with pytest.raises(ProfessionalNotFoundError):
            await world.get_profile.execute(user_id=user.id)


class TestReleaseExpiredReservations:
    async def test_releases_only_expired_reservations(
        self, world: World, carpentry: Category
    ) -> None:
        lead = make_lead(category_id=carpentry.id, max_purchases=3)
        world.leads.items[lead.id] = lead
        stale_pro = world.add_professional(category_ids={carpentry.id})
        fresh_pro = world.add_professional(category_ids={carpentry.id})

        stale = await world.start_purchase.execute(lead_id=lead.id, professional_id=stale_pro.id)
        world.clock.advance(minutes=31)
        fresh = await world.start_purchase.execute(lead_id=lead.id, professional_id=fresh_pro.id)

        released = await world.release_reservations.execute()

        assert released == 1
        assert world.purchases.items[stale.purchase_id].status is PurchaseStatus.EXPIRED
        assert world.purchases.items[fresh.purchase_id].status is PurchaseStatus.RESERVED

    async def test_closes_the_gateway_session_of_released_reservations(
        self, world: World, carpentry: Category
    ) -> None:
        lead = make_lead(category_id=carpentry.id)
        world.leads.items[lead.id] = lead
        pro = world.add_professional(category_ids={carpentry.id})
        reservation = await world.start_purchase.execute(lead_id=lead.id, professional_id=pro.id)

        world.clock.advance(minutes=31)
        await world.release_reservations.execute()

        assert world.payments.expired_sessions == [reservation.checkout_session_id]

    async def test_paid_purchases_are_never_released(
        self, world: World, carpentry: Category
    ) -> None:
        from app.application.ports import PaymentEventType
        from tests.fakes.payments import VALID_SIGNATURE, FakePaymentGateway

        lead = make_lead(category_id=carpentry.id)
        world.leads.items[lead.id] = lead
        pro = world.add_professional(category_ids={carpentry.id})
        reservation = await world.start_purchase.execute(lead_id=lead.id, professional_id=pro.id)
        await world.handle_event.execute(
            payload=FakePaymentGateway.event_payload(
                event_id="evt_paid",
                event_type=PaymentEventType.CHECKOUT_COMPLETED,
                purchase_id=reservation.purchase_id,
            ),
            signature=VALID_SIGNATURE,
        )

        world.clock.advance(days=30)
        assert await world.release_reservations.execute() == 0
        assert world.purchases.items[reservation.purchase_id].status is PurchaseStatus.PAID

    async def test_nothing_to_release_is_a_no_op(self, world: World) -> None:
        assert await world.release_reservations.execute() == 0
        assert world.uow.commits == 0


class TestCategoryCatalog:
    async def test_lists_only_active_categories_sorted(self, world: World) -> None:
        world.add_category(slug="pintura", name_es="Pintura", name_en="Painting")
        world.add_category(slug="carpinteria")
        world.add_category(slug="obsoleto", name_es="Obsoleto", active=False)

        categories = await world.list_categories.execute()
        assert [c.name_es for c in categories] == ["Carpinteria", "Pintura"]
