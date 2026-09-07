from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from archive_org_mcp.clients.catalog_client import CatalogClient
from archive_org_mcp.config.settings import ArchiveOrgSettings
from archive_org_mcp.utils.exceptions import NotFoundError

SEARCH_BODY = {
    "response": {
        "numFound": 2,
        "start": 0,
        "docs": [
            {
                "identifier": "nasa-apollo11",
                "title": "Apollo 11",
                "mediatype": "movies",
                "date": "1969-07-20T00:00:00Z",
            },
            {"identifier": "gutenberg-1342", "title": "Pride and Prejudice",
             "mediatype": "texts", "date": "1813-01-28T00:00:00Z"},
        ],
    }
}

METADATA_BODY = {
    "metadata": {"identifier": "nasa-apollo11", "title": "Apollo 11"},
    "files": [{"name": "a.mp4"}, {"name": "b.mp4"}],
    "server": "ia801504.us.archive.org",
}


def _client(json_body: object) -> tuple[CatalogClient, MagicMock]:
    base = MagicMock()
    base.get_json = AsyncMock(return_value=json_body)
    return CatalogClient(base, ArchiveOrgSettings()), base


@pytest.mark.unit
class TestSearch:
    async def test_returns_items(self) -> None:
        client, _ = _client(SEARCH_BODY)
        items = await client.search("apollo")
        assert len(items) == 2
        assert items[0].identifier == "nasa-apollo11"
        assert items[0].mediatype == "movies"

    async def test_default_fields_are_the_documented_four(self) -> None:
        client, base = _client(SEARCH_BODY)
        await client.search("apollo")
        params = base.get_json.await_args.args[1]
        assert params["fl[]"] == ["identifier", "title", "mediatype", "date"]

    async def test_custom_fields_are_forwarded_as_repeated_param(self) -> None:
        """advancedsearch takes repeated fl[] params, not a comma string."""
        client, base = _client(SEARCH_BODY)
        await client.search("apollo", fields=["identifier", "creator"])
        params = base.get_json.await_args.args[1]
        assert params["fl[]"] == ["identifier", "creator"]

    async def test_requests_json_output(self) -> None:
        client, base = _client(SEARCH_BODY)
        await client.search("apollo")
        assert base.get_json.await_args.args[1]["output"] == "json"

    async def test_paging_params_are_forwarded(self) -> None:
        client, base = _client(SEARCH_BODY)
        await client.search("apollo", rows=10, page=3)
        params = base.get_json.await_args.args[1]
        assert params["rows"] == 10
        assert params["page"] == 3

    async def test_empty_docs_yields_empty_list(self) -> None:
        client, _ = _client({"response": {"docs": []}})
        assert await client.search("nothing-matches-this") == []

    async def test_malformed_body_yields_empty_list(self) -> None:
        client, _ = _client({"unexpected": True})
        assert await client.search("apollo") == []

    async def test_unknown_doc_keys_are_preserved_in_extra(self) -> None:
        client, _ = _client(
            {"response": {"docs": [{"identifier": "x", "downloads": 42}]}}
        )
        items = await client.search("x")
        assert items[0].extra["downloads"] == 42


@pytest.mark.unit
class TestMetadata:
    async def test_returns_metadata(self) -> None:
        client, _ = _client(METADATA_BODY)
        result = await client.metadata("nasa-apollo11")
        assert result.identifier == "nasa-apollo11"
        assert result.files_count == 2
        assert result.server == "ia801504.us.archive.org"

    async def test_empty_body_raises_not_found(self) -> None:
        """The metadata endpoint returns 200 with {} for a nonexistent
        identifier rather than 404 — so an empty body IS the not-found signal."""
        client, _ = _client({})
        with pytest.raises(NotFoundError):
            await client.metadata("does-not-exist")

    async def test_identifier_is_in_the_path_not_the_query(self) -> None:
        client, base = _client(METADATA_BODY)
        await client.metadata("nasa-apollo11")
        called_url = base.get_json.await_args.args[0]
        assert called_url.endswith("/nasa-apollo11")
