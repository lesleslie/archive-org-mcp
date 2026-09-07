"""Catalog MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from oneiric.core.logging import get_logger

from archive_org_mcp.models.feed import FEEDS
from archive_org_mcp.utils.exceptions import ArchiveOrgError

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from archive_org_mcp.clients.catalog_client import CatalogClient

logger = get_logger("archive_org_mcp.tools.catalog")


def register_catalog_tools(server: FastMCP, client: CatalogClient) -> None:
    """Register `catalog_search` and `catalog_metadata` on `server`."""

    @server.tool()
    async def catalog_search(
        query: str,
        fields: list[str] | None = None,
        rows: int = 25,
        page: int = 1,
    ) -> list[dict[str, object]]:
        """Search the Internet Archive catalog.

        Args:
            query: advancedsearch query string.
            fields: Metadata fields to return. Defaults to
                identifier, title, mediatype, date.
            rows: Results per page.
            page: 1-based page number.
        """
        feed = FEEDS["catalog"]
        try:
            items = await client.search(query, fields=fields, rows=rows, page=page)
        except ArchiveOrgError:
            feed.record_error()
            logger.exception("catalog-search-failed", query=query)
            raise
        feed.record_cycle(entities=len(items))
        return [item.model_dump() for item in items]

    @server.tool()
    async def catalog_metadata(identifier: str) -> dict[str, object]:
        """Fetch metadata for one catalog identifier.

        Args:
            identifier: The archive.org item identifier.
        """
        feed = FEEDS["catalog"]
        try:
            result = await client.metadata(identifier)
        except ArchiveOrgError:
            feed.record_error()
            logger.exception("catalog-metadata-failed", identifier=identifier)
            raise
        feed.record_cycle(entities=1)
        return result.model_dump()
