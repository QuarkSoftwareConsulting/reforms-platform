"""Feature flags que el frontend lee al cargar."""

from app.application.use_cases import ListFeatureFlags
from app.domain.models import FeatureFlag, FlagEnvironment
from tests.conftest import World


def flag(name: str, environment: FlagEnvironment, *, enabled: bool) -> FeatureFlag:
    return FeatureFlag(name=name, version="1.4.0", environment=environment, enabled=enabled)


class TestListFeatureFlags:
    async def test_lists_only_the_flags_of_its_environment(self, world: World) -> None:
        world.feature_flags.items = [
            flag("new-checkout", FlagEnvironment.DEV, enabled=True),
            flag("new-checkout", FlagEnvironment.PROD, enabled=False),
            flag("admin.reports", FlagEnvironment.DEV, enabled=False),
        ]

        flags = await world.list_feature_flags.execute()

        assert [(f.name, f.enabled) for f in flags] == [
            ("admin.reports", False),
            ("new-checkout", True),
        ]

    async def test_production_never_sees_the_dev_flags(self, world: World) -> None:
        world.feature_flags.items = [flag("new-checkout", FlagEnvironment.DEV, enabled=True)]
        production = ListFeatureFlags(flags=world.feature_flags, environment=FlagEnvironment.PROD)

        assert await production.execute() == []
