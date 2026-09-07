from __future__ import annotations

import pytest

from archive_org_mcp.models.feed import FEEDS
from tests.integration.conftest import call_tool, load_fixture


@pytest.mark.integration
class TestCatalogMetadataE2E:
    async def test_returns_populated_metadata(self, stub_json) -> None:
        with stub_json(load_fixture("metadata_response.json")):
            result = await call_tool("catalog_metadata", identifier="nasa-apollo11")
        assert result["identifier"] == "nasa-apollo11"
        assert result["files_count"] == 2
        assert result["metadata"], "metadata dict must not be empty"

    async def test_feed_records_the_cycle(self, stub_json) -> None:
        with stub_json(load_fixture("metadata_response.json")):
            await call_tool("catalog_metadata", identifier="nasa-apollo11")
        assert FEEDS["catalog"].cycles_total == 1
