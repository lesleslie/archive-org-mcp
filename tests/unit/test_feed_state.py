"""Feed state is what separates this server from spec finding 4.3 — a server
that registers tools, exposes a schema, and returns nothing real while every
surface signal says healthy.
"""

from __future__ import annotations

import pytest

from archive_org_mcp.models.feed import FEEDS, FeedState, as_components


@pytest.mark.unit
class TestFreshFeed:
    def test_fresh_feed_is_degraded_not_ok(self) -> None:
        """A feed that has never returned data must not report ok. This is the
        mcp-surface-health-illusion guard."""
        feed = FeedState(name="cdx", required=True)
        assert feed.entities_count == 0
        assert feed.cycles_total == 0
        assert feed.healthy is False
        assert feed.status == "degraded"

    def test_fresh_feed_has_no_timestamp(self) -> None:
        assert FeedState(name="cdx", required=True).last_updated_timestamp is None


@pytest.mark.unit
class TestRecordCycle:
    def test_successful_cycle_marks_ok(self) -> None:
        feed = FeedState(name="cdx", required=True)
        feed.record_cycle(entities=3)
        assert feed.healthy is True
        assert feed.status == "ok"
        assert feed.entities_count == 3
        assert feed.cycles_total == 1
        assert feed.last_updated_timestamp is not None

    def test_cycles_accumulate(self) -> None:
        feed = FeedState(name="cdx", required=True)
        feed.record_cycle(entities=1)
        feed.record_cycle(entities=2)
        assert feed.cycles_total == 2
        assert feed.entities_count == 2, "entities_count is the latest, not a sum"

    def test_zero_entity_cycle_does_not_mark_ok(self) -> None:
        """An empty result proves the transport works but not that the feed has
        data. Registering tools against a working-but-empty upstream is exactly
        the illusion being guarded against."""
        feed = FeedState(name="cdx", required=True)
        feed.record_cycle(entities=0)
        assert feed.cycles_total == 1
        assert feed.healthy is False
        assert feed.status == "degraded"

    def test_error_cycle_records_failure(self) -> None:
        """Passing `error` increments errors_total without setting entities."""
        feed = FeedState(name="cdx", required=True)
        feed.record_cycle(error="boom")
        assert feed.errors_total == 1
        assert feed.cycles_total == 1
        assert feed.healthy is False


@pytest.mark.unit
class TestRecordError:
    def test_error_increments_without_clearing_entities(self) -> None:
        feed = FeedState(name="cdx", required=True)
        feed.record_cycle(entities=5)
        feed.record_error()
        assert feed.errors_total == 1
        assert feed.entities_count == 5, "a transient error is not data loss"

    def test_error_on_a_fresh_feed_keeps_it_degraded(self) -> None:
        feed = FeedState(name="cdx", required=True)
        feed.record_error()
        assert feed.healthy is False
        assert feed.status == "degraded"


@pytest.mark.unit
class TestCapabilityUnavailable:
    def test_optional_feed_can_be_capability_unavailable(self) -> None:
        feed = FeedState(name="capture", required=False)
        feed.mark_capability_unavailable("feature flag off")
        assert feed.healthy is False
        assert feed.status == "capability_unavailable"

    def test_required_feed_cannot_be_capability_unavailable(self) -> None:
        """A required feed being absent is a fault, not a configuration choice."""
        feed = FeedState(name="cdx", required=True)
        with pytest.raises(ValueError):
            feed.mark_capability_unavailable("env missing")


@pytest.mark.unit
class TestComponentPayload:
    def test_exposes_the_four_required_signals(self) -> None:
        feed = FeedState(name="cdx", required=True)
        feed.record_cycle(entities=2)
        payload = feed.as_component()
        for key in (
            "feed.entities_count",
            "feed.last_updated_timestamp",
            "feed.errors_total",
            "cycles_total",
        ):
            assert key in payload, f"wiring discipline requires {key}"
        assert payload["name"] == "cdx"
        assert payload["healthy"] is True
        assert payload["status"] == "ok"


@pytest.mark.unit
class TestAsComponentsAggregate:
    def test_module_level_as_components_returns_a_list(self) -> None:
        """The module-level `as_components()` returns a list of component dicts
        for every feed — used by /health and /readyz."""
        components = as_components()
        assert isinstance(components, list)
        names = {component["name"] for component in components}
        assert names == {"cdx", "catalog"}
        for component in components:
            assert "healthy" in component
            assert isinstance(component["healthy"], bool)


@pytest.mark.unit
class TestRegistry:
    def test_registry_declares_cdx_and_catalog_as_required(self) -> None:
        assert set(FEEDS) == {"cdx", "catalog"}
        assert all(feed.required for feed in FEEDS.values())
