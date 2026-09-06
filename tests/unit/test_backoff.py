from __future__ import annotations

from random import Random

import pytest

from archive_org_mcp.clients.backoff import next_delay
from archive_org_mcp.config.settings import ArchiveOrgSettings


@pytest.mark.unit
class TestNextDelay:
    async def test_returns_none_when_attempts_exhausted(self) -> None:
        settings = ArchiveOrgSettings(retry_max_attempts=2)
        assert await next_delay(2, settings) is None
        assert await next_delay(3, settings) is None

    async def test_grows_with_attempt(self) -> None:
        settings = ArchiveOrgSettings(
            retry_max_attempts=5, backoff_random_jitter=False
        )
        first = await next_delay(0, settings)
        second = await next_delay(1, settings)
        third = await next_delay(2, settings)
        assert first is not None and second is not None and third is not None
        assert first < second < third

    async def test_is_capped_at_max(self) -> None:
        settings = ArchiveOrgSettings(
            retry_max_attempts=10,
            backoff_base_seconds=1.0,
            backoff_multiplier=10.0,
            backoff_max_seconds=5.0,
            backoff_random_jitter=False,
        )
        delay = await next_delay(6, settings)
        assert delay is not None
        assert delay <= 5.0

    async def test_deterministic_without_jitter(self) -> None:
        settings = ArchiveOrgSettings(backoff_random_jitter=False)
        assert await next_delay(1, settings) == await next_delay(1, settings)

    async def test_random_jitter_perturbs_the_delay(self) -> None:
        """oneiric's own jitter is deterministic, so a shared retry storm across
        clients would stay synchronized. The random layer breaks that."""
        settings = ArchiveOrgSettings(backoff_random_jitter=True)
        values = {
            await next_delay(2, settings, rng=Random(seed)) for seed in range(8)
        }
        assert len(values) > 1

    async def test_jitter_never_produces_a_negative_delay(self) -> None:
        settings = ArchiveOrgSettings(backoff_random_jitter=True)
        for seed in range(32):
            delay = await next_delay(0, settings, rng=Random(seed))
            assert delay is not None
            assert delay >= 0.0

    async def test_zero_attempts_disables_retry(self) -> None:
        settings = ArchiveOrgSettings(retry_max_attempts=0)
        assert await next_delay(0, settings) is None
