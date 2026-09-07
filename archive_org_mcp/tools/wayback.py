"""Wayback MCP tools.

Each handler records feed state so /readyz can distinguish "returned real data"
from "registered but empty" — the mcp-surface-health-illusion guard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from oneiric.core.logging import get_logger

from archive_org_mcp.models.feed import FEEDS
from archive_org_mcp.utils.exceptions import ArchiveOrgError

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from archive_org_mcp.clients.wayback_client import WaybackClient

logger = get_logger("archive_org_mcp.tools.wayback")


def register_wayback_tools(server: FastMCP, client: WaybackClient) -> None:
    """Register `wayback_snapshots` and `wayback_closest` on `server`."""

    @server.tool()
    async def wayback_snapshots(
        url: str,
        match_type: Literal["exact", "prefix", "host", "domain"] = "exact",
        from_ts: str | None = None,
        to_ts: str | None = None,
        collapse: Literal["urlkey", "digest", "timestamp"] | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        """List Wayback Machine captures of a URL.

        Args:
            url: The URL to look up.
            match_type: exact | prefix | host | domain.
            from_ts: Earliest capture, 1-14 digits (zero-padded).
            to_ts: Latest capture, 1-14 digits (zero-padded).
            collapse: Deduplicate adjacent rows by this field.
            limit: Maximum rows to return.
        """
        feed = FEEDS["cdx"]
        try:
            snapshots = await client.snapshots(
                url,
                match_type=match_type,
                from_ts=from_ts,
                to_ts=to_ts,
                collapse=collapse,
                limit=limit,
            )
        except ArchiveOrgError:
            feed.record_error()
            logger.exception("wayback-snapshots-failed", url=url)
            raise
        feed.record_cycle(entities=len(snapshots))
        return [
            snapshot.model_dump() | {"wayback_url": snapshot.wayback_url}
            for snapshot in snapshots
        ]

    @server.tool()
    async def wayback_closest(url: str, timestamp: str) -> dict[str, object] | None:
        """Return the capture nearest a timestamp, or null if none exists.

        Args:
            url: The URL to look up.
            timestamp: Target time, 1-14 digits (zero-padded).
        """
        feed = FEEDS["cdx"]
        try:
            snapshot = await client.closest(url, timestamp)
        except ArchiveOrgError:
            feed.record_error()
            logger.exception("wayback-closest-failed", url=url)
            raise
        feed.record_cycle(entities=1 if snapshot is not None else 0)
        if snapshot is None:
            return None
        return snapshot.model_dump() | {"wayback_url": snapshot.wayback_url}
