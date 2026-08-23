"""Implementaciones in-memory de todos los puertos.

Permiten probar los casos de uso sin Postgres, Stripe ni Firebase, y modelar con
precision los escenarios de concurrencia y de reintento de webhooks.
"""

from tests.fakes.clock import FakeClock, SequentialIdGenerator
from tests.fakes.payments import FakePaymentGateway
from tests.fakes.repositories import (
    InMemoryCategoryRepository,
    InMemoryLeadRepository,
    InMemoryPostalCodeRepository,
    InMemoryProcessedEventRepository,
    InMemoryProfessionalRepository,
    InMemoryPurchaseRepository,
    InMemoryUnitOfWork,
    InMemoryUserRepository,
)
from tests.fakes.storage import FakeStorage
from tests.fakes.token_verifier import FakeTokenVerifier

__all__ = [
    "FakeClock",
    "FakePaymentGateway",
    "FakeStorage",
    "FakeTokenVerifier",
    "InMemoryCategoryRepository",
    "InMemoryLeadRepository",
    "InMemoryPostalCodeRepository",
    "InMemoryProcessedEventRepository",
    "InMemoryProfessionalRepository",
    "InMemoryPurchaseRepository",
    "InMemoryUnitOfWork",
    "InMemoryUserRepository",
    "SequentialIdGenerator",
]
