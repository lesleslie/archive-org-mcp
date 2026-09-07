from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from archive_org_mcp.clients.wayback_client import WaybackClient
from archive_org_mcp.config.settings import ArchiveOrgSettings

CDX_HEADER = ["timestamp", "original", "mimetype", "statuscode", "digest", "length"]
CDX_BODY = [
    CDX_HEADER,
    ["20240115123045", "https://example.org/", "text/html", "200", "ABC", "4096"],
    ["20240116080000", "https://example.org/", "text/html", "200", "DEF", "4100"],
]


def _client(json_body: object) -> tuple[WaybackClient, MagicMock]:
    base = MagicMock()
    base.get_json = AsyncMock(return_value=json_body)
    return WaybackClient(base, ArchiveOrgSettings()), base


@pytest.mark.unit
class TestSnapshots:
    async def test_header_row_is_consumed_not_returned(self) -> None:
        """CDX row 0 is column names. Returning it as data yields a bogus
        snapshot with timestamp='timestamp'."""
        client, _ = _client(CDX_BODY)
        results = await client.snapshots("https://example.org/")
        assert len(results) == 2
        assert all(snap.timestamp != "timestamp" for snap in results)
        assert results[0].timestamp == "20240115123045"

    async def test_empty_body_yields_empty_list(self) -> None:
        """A URL with no captures returns [] from CDX, not an error."""
        client, _ = _client([])
        assert await client.snapshots("https://example.org/never") == []

    async def test_header_only_body_yields_empty_list(self) -> None:
        client, _ = _client([CDX_HEADER])
        assert await client.snapshots("https://example.org/never") == []

    async def test_requests_json_output(self) -> None:
        client, base = _client(CDX_BODY)
        await client.snapshots("https://example.org/")
        params = base.get_json.await_args.args[1]
        assert params["output"] == "json"

    async def test_timestamps_are_padded_in_params(self) -> None:
        client, base = _client(CDX_BODY)
        await client.snapshots("https://example.org/", from_ts="2024", to_ts="202402")
        params = base.get_json.await_args.args[1]
        assert params["from"] == "20240000000000"
        assert params["to"] == "20240200000000"

    async def test_omits_unset_optional_params(self) -> None:
        client, base = _client(CDX_BODY)
        await client.snapshots("https://example.org/")
        params = base.get_json.await_args.args[1]
        assert "from" not in params
        assert "to" not in params
        assert "collapse" not in params

    async def test_rejects_unknown_match_type(self) -> None:
        client, _ = _client(CDX_BODY)
        with pytest.raises(ValueError):
            await client.snapshots("https://example.org/", match_type="fuzzy")

    async def test_rejects_unknown_collapse_field(self) -> None:
        client, _ = _client(CDX_BODY)
        with pytest.raises(ValueError):
            await client.snapshots("https://example.org/", collapse="nonsense")

    async def test_limit_is_forwarded(self) -> None:
        client, base = _client(CDX_BODY)
        await client.snapshots("https://example.org/", limit=7)
        assert base.get_json.await_args.args[1]["limit"] == 7


@pytest.mark.unit
class TestClosest:
    async def test_returns_snapshot_from_availability_payload(self) -> None:
        payload = {
            "archived_snapshots": {
                "closest": {
                    "timestamp": "20240115123045",
                    "url": "https://web.archive.org/web/20240115123045/https://example.org/",
                    "status": "200",
                    "available": True,
                }
            }
        }
        client, _ = _client(payload)
        snapshot = await client.closest("https://example.org/", "20240115")
        assert snapshot is not None
        assert snapshot.timestamp == "20240115123045"

    async def test_returns_none_when_no_snapshot(self) -> None:
        """Availability returns an empty archived_snapshots for unarchived URLs.
        That is an answer, not an error."""
        client, _ = _client({"archived_snapshots": {}})
        assert await client.closest("https://example.org/x", "20240115") is None

    async def test_pads_the_requested_timestamp(self) -> None:
        client, base = _client({"archived_snapshots": {}})
        await client.closest("https://example.org/", "2024")
        params = base.get_json.await_args.args[1]
        assert params["timestamp"] == "20240000000000"

    async def test_non_dict_body_returns_none(self) -> None:
        client, _ = _client([])
        assert await client.closest("https://example.org/", "20240115") is None

    async def test_non_dict_closest_returns_none(self) -> None:
        client, _ = _client({"archived_snapshots": {"closest": "not a dict"}})
        assert await client.closest("https://example.org/", "20240115") is None

    async def test_closest_without_timestamp_returns_none(self) -> None:
        client, _ = _client({"archived_snapshots": {"closest": {"status": "200"}}})
        assert await client.closest("https://example.org/", "20240115") is None

    async def test_parse_cdx_tolerates_non_list_body(self) -> None:
        client, _ = _client("not a list")
        assert await client.snapshots("https://example.org/") == []

    async def test_parse_cdx_tolerates_non_list_header(self) -> None:
        client, _ = _client(["not a header row"])
        assert await client.snapshots("https://example.org/") == []

    async def test_parse_cdx_skips_non_list_rows(self) -> None:
        client, _ = _client([CDX_HEADER, "rogue row", ["ok", "url"]])
        # The "rogue row" is skipped — Snapshot.from_cdx_row requires the row
        # to be a list, so a non-list row is filtered before construction.
        result = await client.snapshots("https://example.org/")
        # The valid row only has 2 cells, mapping to header columns
        # ["timestamp", "original"]; everything else becomes None.
        assert len(result) == 1
