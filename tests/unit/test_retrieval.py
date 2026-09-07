from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from archive_org_mcp.clients.retrieval_client import RetrievalClient
from archive_org_mcp.config.settings import ArchiveOrgSettings


def _client(body: bytes, truncated: bool) -> tuple[RetrievalClient, MagicMock]:
    base = MagicMock()
    base.get_bytes = AsyncMock(return_value=(body, truncated))
    return RetrievalClient(base, ArchiveOrgSettings()), base


@pytest.mark.unit
class TestRetrieve:
    async def test_builds_the_wayback_url(self) -> None:
        client, base = _client(b"<html/>", False)
        await client.retrieve("https://example.org/", "20240115123045")
        assert base.get_bytes.await_args.args[0] == (
            "https://web.archive.org/web/20240115123045/https://example.org/"
        )

    async def test_pads_a_partial_timestamp(self) -> None:
        client, base = _client(b"<html/>", False)
        await client.retrieve("https://example.org/", "2024")
        assert "20240000000000" in base.get_bytes.await_args.args[0]

    async def test_decodes_content(self) -> None:
        client, _ = _client(b"<html>hi</html>", False)
        result = await client.retrieve("https://example.org/", "20240115123045")
        assert result.content == "<html>hi</html>"
        assert result.truncated is False
        assert result.fetched_bytes == 15

    async def test_truncated_flag_is_propagated_not_raised(self) -> None:
        """A page over the ceiling yields partial content plus an honest flag.
        Raising would make large pages unreadable rather than partially readable."""
        client, _ = _client(b"a" * 100, True)
        result = await client.retrieve("https://example.org/", "20240115123045")
        assert result.truncated is True
        assert result.fetched_bytes == 100

    async def test_invalid_utf8_is_replaced_not_raised(self) -> None:
        client, _ = _client(b"\xff\xfe invalid", False)
        result = await client.retrieve("https://example.org/", "20240115123045")
        assert "�" in result.content

    async def test_max_bytes_is_forwarded(self) -> None:
        client, base = _client(b"x", False)
        await client.retrieve("https://example.org/", "20240115123045", max_bytes=512)
        assert base.get_bytes.await_args.kwargs["max_bytes"] == 512

    async def test_bodies_are_not_cached(self) -> None:
        """Spec §6.1: archived pages are large and re-fetching is cheap relative
        to storing them. Two identical calls must both hit the transport."""
        client, base = _client(b"x", False)
        await client.retrieve("https://example.org/", "20240115123045")
        await client.retrieve("https://example.org/", "20240115123045")
        assert base.get_bytes.await_count == 2
