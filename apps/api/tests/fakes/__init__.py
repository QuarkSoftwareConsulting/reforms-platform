"""Implementaciones in-memory de todos los puertos.

Permiten probar los casos de uso sin Postgres, Stripe ni Firebase, y modelar con
precision los escenarios de concurrencia y de reintento de webhooks.
"""

from tests.fakes.clock import FakeClock, SequentialIdGenerator
from tests.fakes.payments import FakePaymentGateway
from tests.fakes.phone_verification import FAKE_CODE, FakePhoneVerifier
from tests.fakes.repositories import (
    InMemoryCategoryRepository,
    InMemoryCreditLedgerRepository,
    InMemoryFeatureFlagRepository,
    InMemoryLeadRepository,
    InMemoryPostalCodeRepository,
    InMemoryProcessedEventRepository,
    InMemoryProfessionalAccountRepository,
    InMemoryProfessionalRepository,
    InMemoryPurchaseRepository,
    InMemoryPurchaseReviewRepository,
    InMemoryRateLimiter,
    InMemorySubscriptionPriceRepository,
    InMemoryUnitOfWork,
    InMemoryUserRepository,
)
from tests.fakes.storage import FakeStorage
from tests.fakes.token_verifier import FakeTokenVerifier

__all__ = [
    "FAKE_CODE",
    "FakeClock",
    "FakePaymentGateway",
    "FakePhoneVerifier",
    "FakeStorage",
    "FakeTokenVerifier",
    "InMemoryCategoryRepository",
    "InMemoryCreditLedgerRepository",
    "InMemoryFeatureFlagRepository",
    "InMemoryLeadRepository",
    "InMemoryPostalCodeRepository",
    "InMemoryProcessedEventRepository",
    "InMemoryProfessionalAccountRepository",
    "InMemoryProfessionalRepository",
    "InMemoryPurchaseRepository",
    "InMemoryPurchaseReviewRepository",
    "InMemoryRateLimiter",
    "InMemorySubscriptionPriceRepository",
    "InMemoryUnitOfWork",
    "InMemoryUserRepository",
    "SequentialIdGenerator",
]
