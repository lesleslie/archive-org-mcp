"""Health routes.

Two routes, deliberately:
  /health  — mcp_common.health.register_http_health_route. Its docstring says
             "The handler always returns HTTP 200". There is no 503 path.
  /readyz  — in-repo. Returns 503 when a REQUIRED feed is not ok.

The split exists because mcp-backend-wiring-discipline.md demands 503-on-degraded
while the shared helper cannot provide it, and modifying the shared helper is a
non-goal. raindropio-mcp sets the precedent by pairing /health with its own
/healthz.
"""

from __future__ import annotations

import pytest

from archive_org_mcp.models.feed import FEEDS
from archive_org_mcp.server import create_app


@pytest.fixture(autouse=True)
def _reset_feeds() -> None:
    for feed in FEEDS.values():
        feed.entities_count = 0
        feed.errors_total = 0
        feed.cycles_total = 0
        feed.last_updated_timestamp = None


async def _call(app: object, path: str) -> tuple[int, dict]:
    from starlette.testclient import TestClient

    with TestClient(app.http_app()) as http:  # type: ignore[attr-defined]
        response = http.get(path)
        return response.status_code, response.json()


@pytest.mark.unit
class TestHealthRoute:
    async def test_health_is_200_even_when_degraded(self) -> None:
        status, _ = await _call(await create_app(), "/health")
        assert status == 200, "the shared helper always returns 200 by contract"

    async def test_health_reports_feed_components(self) -> None:
        _, body = await _call(await create_app(), "/health")
        names = {component["name"] for component in body["components"]}
        assert {"cdx", "catalog"} <= names


@pytest.mark.unit
class TestReadyzRoute:
    async def test_readyz_is_503_when_a_required_feed_is_degraded(self) -> None:
        """Fresh feeds have returned nothing, so the server is not ready."""
        status, body = await _call(await create_app(), "/readyz")
        assert status == 503
        assert body["status"] == "degraded"

    async def test_readyz_is_200_once_all_required_feeds_are_ok(self) -> None:
        FEEDS["cdx"].record_cycle(entities=3)
        FEEDS["catalog"].record_cycle(entities=1)
        status, body = await _call(await create_app(), "/readyz")
        assert status == 200
        assert body["status"] == "ok"

    async def test_readyz_is_503_when_only_one_required_feed_is_ok(self) -> None:
        FEEDS["cdx"].record_cycle(entities=3)
        status, _ = await _call(await create_app(), "/readyz")
        assert status == 503

    async def test_readyz_exposes_the_four_signals_per_feed(self) -> None:
        FEEDS["cdx"].record_cycle(entities=2)
        _, body = await _call(await create_app(), "/readyz")
        component = next(c for c in body["components"] if c["name"] == "cdx")
        for key in (
            "feed.entities_count",
            "feed.last_updated_timestamp",
            "feed.errors_total",
            "cycles_total",
        ):
            assert key in component
