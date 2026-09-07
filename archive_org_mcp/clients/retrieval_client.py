"""Archived page retrieval.

Bodies are deliberately NOT cached: archived pages are large and re-fetching is
cheap relative to the storage, so caching them would trade a lot of memory for
little benefit (spec §6.1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archive_org_mcp.models.retrieval import RetrievedSnapshot
from archive_org_mcp.models.snapshot import normalize_timestamp

if TYPE_CHECKING:
    from archive_org_mcp.clients.base_client import ArchiveOrgBaseClient
    from archive_org_mcp.config.settings import ArchiveOrgSettings

_WAYBACK_PREFIX = "https://web.archive.org/web"


class RetrievalClient:
    """Fetches archived page content."""

    def __init__(
        self,
        base: ArchiveOrgBaseClient,
        settings: ArchiveOrgSettings,
    ) -> None:
        self._base = base
        self._settings = settings

    async def retrieve(
        self,
        url: str,
        timestamp: str,
        *,
        max_bytes: int | None = None,
    ) -> RetrievedSnapshot:
        """Fetch the archived body of `url` at `timestamp`.

        Args:
            url: Original URL.
            timestamp: Capture time, 1-14 digits (zero-padded).
            max_bytes: Optional narrower ceiling. Can only lower the configured
                `max_response_bytes`.

        Returns:
            The decoded body with a `truncated` flag. Never raises on an
            oversized page — it truncates and says so.
        """
        padded = normalize_timestamp(timestamp) or ""
        target = f"{_WAYBACK_PREFIX}/{padded}/{url}"
        body, truncated = await self._base.get_bytes(target, max_bytes=max_bytes)
        return RetrievedSnapshot(
            url=url,
            timestamp=padded,
            content=body.decode("utf-8", errors="replace"),
            truncated=truncated,
            fetched_bytes=len(body),
        )
