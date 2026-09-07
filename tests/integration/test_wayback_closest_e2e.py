from __future__ import annotations

import pytest

from archive_org_mcp.models.feed import FEEDS
from tests.integration.conftest import call_tool, load_fixture


@pytest.mark.integration
class TestWaybackClosestE2E:
    async def test_returns_a_snapshot(self, stub_json) -> None:
        with stub_json(load_fixture("availability_response.json")):
            result = await call_tool(
                "wayback_closest", url="https://example.org/", timestamp="20240115"
            )
        assert result is not None
        assert result["timestamp"] == "20240115123045"
        assert result["wayback_url"].startswith("https://web.archive.org/web/")

    async def test_no_snapshot_returns_none_and_leaves_feed_degraded(
        self, stub_json
    ) -> None:
        with stub_json({"archived_snapshots": {}}):
            result = await call_tool(
                "wayback_closest", url="https://example.org/x", timestamp="20240115"
            )
        assert result is None
        assert FEEDS["cdx"].status == "degraded", (
            "a zero-entity cycle must not mark the feed ok"
        )
