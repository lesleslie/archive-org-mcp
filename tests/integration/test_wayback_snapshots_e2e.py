from __future__ import annotations

import pytest

from archive_org_mcp.models.feed import FEEDS
from tests.integration.conftest import call_tool, load_fixture


@pytest.mark.integration
class TestWaybackSnapshotsE2E:
    async def test_returns_non_empty_snapshots(self, stub_json) -> None:
        with stub_json(load_fixture("cdx_response.json")):
            result = await call_tool(
                "wayback_snapshots", url="https://example.org/", limit=10
            )
        assert result, "tool returned an empty result — the wiring-illusion case"
        assert len(result) == 2

    async def test_header_row_is_not_returned_as_data(self, stub_json) -> None:
        with stub_json(load_fixture("cdx_response.json")):
            result = await call_tool("wayback_snapshots", url="https://example.org/")
        assert all(row["timestamp"] != "timestamp" for row in result)

    async def test_feed_entities_count_advances(self, stub_json) -> None:
        """A tool that returns data without recording it leaves /readyz lying."""
        with stub_json(load_fixture("cdx_response.json")):
            await call_tool("wayback_snapshots", url="https://example.org/")
        assert FEEDS["cdx"].entities_count == 2
        assert FEEDS["cdx"].cycles_total == 1
        assert FEEDS["cdx"].status == "ok"
