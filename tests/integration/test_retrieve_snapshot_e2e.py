from __future__ import annotations

import pytest

from tests.integration.conftest import call_tool, load_fixture


@pytest.mark.integration
class TestRetrieveSnapshotE2E:
    async def test_returns_non_empty_content(self, stub_bytes) -> None:
        body = load_fixture("snapshot_body.html").encode()
        with stub_bytes(body):
            result = await call_tool(
                "retrieve_snapshot",
                url="https://example.org/",
                timestamp="20240115123045",
            )
        assert result["content"], "tool returned empty content"
        assert "Archived content." in result["content"]
        assert result["truncated"] is False

    async def test_marks_content_untrusted(self, stub_bytes) -> None:
        """Archived pages are attacker-controllable and flow toward an LLM."""
        with stub_bytes(b"<html/>"):
            result = await call_tool(
                "retrieve_snapshot",
                url="https://example.org/",
                timestamp="20240115123045",
            )
        assert result["untrusted"] is True

    async def test_truncation_is_reported_not_raised(self, stub_bytes) -> None:
        with stub_bytes(b"a" * 64, truncated=True):
            result = await call_tool(
                "retrieve_snapshot",
                url="https://example.org/",
                timestamp="20240115123045",
            )
        assert result["truncated"] is True
        assert result["fetched_bytes"] == 64
