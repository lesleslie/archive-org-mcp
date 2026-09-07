"""Wayback Machine access: CDX snapshot lists and closest-snapshot lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, get_args

from archive_org_mcp.models.snapshot import Snapshot, normalize_timestamp

if TYPE_CHECKING:
    from archive_org_mcp.clients.base_client import ArchiveOrgBaseClient
    from archive_org_mcp.config.settings import ArchiveOrgSettings

MatchType = Literal["exact", "prefix", "host", "domain"]
CollapseField = Literal["urlkey", "digest", "timestamp"]

_CDX_FIELDS = "timestamp,original,mimetype,statuscode,digest,length"


class WaybackClient:
    """CDX and availability endpoints."""

    def __init__(
        self,
        base: ArchiveOrgBaseClient,
        settings: ArchiveOrgSettings,
    ) -> None:
        self._base = base
        self._settings = settings

    async def snapshots(
        self,
        url: str,
        *,
        match_type: MatchType = "exact",
        from_ts: str | None = None,
        to_ts: str | None = None,
        collapse: CollapseField | None = None,
        limit: int = 50,
    ) -> list[Snapshot]:
        """List archived captures of `url`.

        Raises:
            ValueError: If `match_type` or `collapse` is not a documented value.
        """
        if match_type not in get_args(MatchType):
            raise ValueError(
                f"match_type must be one of {get_args(MatchType)}, got {match_type!r}"
            )
        if collapse is not None and collapse not in get_args(CollapseField):
            raise ValueError(
                f"collapse must be one of {get_args(CollapseField)}, got {collapse!r}"
            )

        params: dict[str, str | int] = {
            "url": url,
            "output": "json",
            "fl": _CDX_FIELDS,
            "matchType": match_type,
            "limit": limit,
        }
        padded_from = normalize_timestamp(from_ts)
        if padded_from is not None:
            params["from"] = padded_from
        padded_to = normalize_timestamp(to_ts)
        if padded_to is not None:
            params["to"] = padded_to
        if collapse is not None:
            params["collapse"] = collapse

        body = await self._base.get_json(str(self._settings.cdx_base_url), params)
        return self._parse_cdx(body)

    @staticmethod
    def _parse_cdx(body: object) -> list[Snapshot]:
        """Convert a CDX JSON array to snapshots, discarding the header row."""
        if not isinstance(body, list) or len(body) < 2:
            return []
        header_row, *data_rows = body
        if not isinstance(header_row, list):
            return []
        header = [str(column) for column in header_row]
        return [
            Snapshot.from_cdx_row(header, [str(cell) for cell in row])
            for row in data_rows
            if isinstance(row, list)
        ]

    async def closest(self, url: str, timestamp: str) -> Snapshot | None:
        """Return the capture nearest `timestamp`, or None if none exists."""
        params: dict[str, str | int] = {
            "url": url,
            "timestamp": normalize_timestamp(timestamp) or "",
        }
        body = await self._base.get_json(
            str(self._settings.availability_base_url), params
        )
        if not isinstance(body, dict):
            return None
        closest = body.get("archived_snapshots", {}).get("closest")
        if not isinstance(closest, dict) or not closest.get("timestamp"):
            return None
        return Snapshot(
            timestamp=str(closest["timestamp"]),
            original=url,
            statuscode=str(closest.get("status")) if closest.get("status") else None,
        )
