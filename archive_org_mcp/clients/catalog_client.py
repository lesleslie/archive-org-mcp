"""Catalog access: advancedsearch and the metadata endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from archive_org_mcp.models.catalog import CatalogItem, ItemMetadata
from archive_org_mcp.utils.exceptions import NotFoundError

if TYPE_CHECKING:
    from archive_org_mcp.clients.base_client import ArchiveOrgBaseClient
    from archive_org_mcp.config.settings import ArchiveOrgSettings

_DEFAULT_FIELDS = ("identifier", "title", "mediatype", "date")


class CatalogClient:
    """advancedsearch.php and /metadata/{identifier}."""

    def __init__(
        self,
        base: ArchiveOrgBaseClient,
        settings: ArchiveOrgSettings,
    ) -> None:
        self._base = base
        self._settings = settings

    async def search(
        self,
        query: str,
        *,
        fields: list[str] | None = None,
        rows: int = 25,
        page: int = 1,
    ) -> list[CatalogItem]:
        """Search the catalog. Returns [] when nothing matches."""
        params: dict[str, Any] = {
            "q": query,
            "fl[]": list(fields) if fields else list(_DEFAULT_FIELDS),
            "rows": rows,
            "page": page,
            "output": "json",
        }
        body = await self._base.get_json(str(self._settings.search_base_url), params)
        if not isinstance(body, dict):
            return []
        docs = body.get("response", {}).get("docs")
        if not isinstance(docs, list):
            return []
        return [CatalogItem.from_doc(doc) for doc in docs if isinstance(doc, dict)]

    async def metadata(self, identifier: str) -> ItemMetadata:
        """Fetch metadata for one identifier.

        Raises:
            NotFoundError: The metadata endpoint answers 200 with an empty
                object for unknown identifiers, so an empty body is the
                not-found signal rather than a 404.
        """
        url = f"{str(self._settings.metadata_base_url).rstrip('/')}/{identifier}"
        body = await self._base.get_json(url)
        if not isinstance(body, dict) or not body:
            raise NotFoundError(f"no catalog item with identifier {identifier!r}")
        files = body.get("files")
        return ItemMetadata(
            identifier=identifier,
            metadata=body.get("metadata", {}) or {},
            files_count=len(files) if isinstance(files, list) else 0,
            server=body.get("server"),
        )
