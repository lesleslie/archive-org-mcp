from __future__ import annotations

import pytest

from archive_org_mcp.models.feed import FEEDS
from tests.integration.conftest import call_tool, load_fixture


@pytest.mark.integration
class TestCatalogSearchE2E:
    async def test_returns_non_empty_items(self, stub_json) -> None:
        with stub_json(load_fixture("search_response.json")):
            result = await call_tool("catalog_search", query="apollo", rows=10)
        assert result
        assert result[0]["identifier"] == "nasa-apollo11"

    async def test_feed_records_the_cycle(self, stub_json) -> None:
        with stub_json(load_fixture("search_response.json")):
            await call_tool("catalog_search", query="apollo")
        assert FEEDS["catalog"].entities_count == 2
        assert FEEDS["catalog"].status == "ok"
