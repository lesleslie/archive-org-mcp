"""Base client behaviour.

Patch target note: this package does `import httpx2 as httpx`, which is a LOCAL
alias. Patching global `httpx` patches the legacy library and the test passes
against code that never ran. Always patch
`archive_org_mcp.clients.base_client.httpx`.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from archive_org_mcp.clients.base_client import ArchiveOrgBaseClient
from archive_org_mcp.config.settings import ArchiveOrgSettings
from archive_org_mcp.utils.exceptions import (
    NotFoundError,
    RateLimitedError,
    UpstreamError,
)

PATCH_TARGET = "archive_org_mcp.clients.base_client.httpx"


def _response(
    status_code: int = 200,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.json = MagicMock(return_value=json_body)
    return response


def _client_with(responses: list[Any]) -> MagicMock:
    """A mock AsyncClient whose .get() yields each response in turn."""
    fake = MagicMock()
    fake.get = AsyncMock(side_effect=responses)
    fake.aclose = AsyncMock()
    return fake


@pytest.mark.unit
class TestGetJson:
    async def test_returns_parsed_body(self) -> None:
        settings = ArchiveOrgSettings(retry_max_attempts=0)
        fake = _client_with([_response(200, json_body=[["a"], ["1"]])])
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                result = await client.get_json("https://example.org/x", {"q": "1"})
        assert result == [["a"], ["1"]]

    async def test_sends_identifying_user_agent(self) -> None:
        """IA asks to be used respectfully; an anonymous UA is impolite."""
        settings = ArchiveOrgSettings(retry_max_attempts=0)
        fake = _client_with([_response(200, json_body={})])
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                await client.get_json("https://example.org/x")
        _, kwargs = mod.AsyncClient.call_args
        assert "archive-org-mcp" in kwargs["headers"]["User-Agent"]

    async def test_404_raises_not_found_and_does_not_retry(self) -> None:
        settings = ArchiveOrgSettings(retry_max_attempts=4, backoff_base_seconds=0.0)
        fake = _client_with([_response(404)])
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                with pytest.raises(NotFoundError):
                    await client.get_json("https://example.org/missing")
        assert fake.get.await_count == 1, "404 is terminal; retrying wastes IA's time"

    async def test_429_raises_rate_limited_with_retry_after(self) -> None:
        settings = ArchiveOrgSettings(retry_max_attempts=0)
        fake = _client_with([_response(429, headers={"Retry-After": "42"})])
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                with pytest.raises(RateLimitedError) as excinfo:
                    await client.get_json("https://example.org/x")
        assert excinfo.value.retry_after == 42.0

    async def test_unparseable_retry_after_yields_none(self) -> None:
        """A Retry-After header that isn't a float must not crash — it is
        ignored and the exception still surfaces."""
        settings = ArchiveOrgSettings(retry_max_attempts=0)
        fake = _client_with([_response(429, headers={"Retry-After": "soonish"})])
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                with pytest.raises(RateLimitedError) as excinfo:
                    await client.get_json("https://example.org/x")
        assert excinfo.value.retry_after is None

    async def test_get_bytes_raises_not_found_on_404(self) -> None:
        """get_bytes raises just like get_json does — no silent acceptance."""
        settings = ArchiveOrgSettings(retry_max_attempts=0)
        response = MagicMock()
        response.status_code = 404
        response.headers = {}
        stream_ctx = MagicMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=response)
        stream_ctx.__aexit__ = AsyncMock(return_value=False)
        fake = MagicMock()
        fake.stream = MagicMock(return_value=stream_ctx)
        fake.aclose = AsyncMock()
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                with pytest.raises(NotFoundError):
                    await client.get_bytes("https://example.org/missing")

    async def test_get_bytes_raises_rate_limited_on_429(self) -> None:
        settings = ArchiveOrgSettings(retry_max_attempts=0)
        response = MagicMock()
        response.status_code = 429
        response.headers = {"Retry-After": "5"}
        stream_ctx = MagicMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=response)
        stream_ctx.__aexit__ = AsyncMock(return_value=False)
        fake = MagicMock()
        fake.stream = MagicMock(return_value=stream_ctx)
        fake.aclose = AsyncMock()
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                with pytest.raises(RateLimitedError) as excinfo:
                    await client.get_bytes("https://example.org/x")
        assert excinfo.value.retry_after == 5.0

    async def test_5xx_is_retried_then_raises(self) -> None:
        settings = ArchiveOrgSettings(
            retry_max_attempts=2, backoff_base_seconds=0.0, backoff_max_seconds=0.0
        )
        fake = _client_with([_response(503), _response(503), _response(503)])
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                with pytest.raises(UpstreamError):
                    await client.get_json("https://example.org/x")
        assert fake.get.await_count == 3, "initial attempt plus 2 retries"

    async def test_5xx_then_success_returns_body(self) -> None:
        settings = ArchiveOrgSettings(
            retry_max_attempts=3, backoff_base_seconds=0.0, backoff_max_seconds=0.0
        )
        fake = _client_with([_response(500), _response(200, json_body={"ok": True})])
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                result = await client.get_json("https://example.org/x")
        assert result == {"ok": True}


@pytest.mark.unit
class TestConcurrencyCap:
    async def test_in_flight_requests_are_bounded(self) -> None:
        """IA enforces no hard limit, so the semaphore is the only thing
        stopping this client from opening 50 sockets at once."""
        settings = ArchiveOrgSettings(concurrency_limit=2, retry_max_attempts=0)
        peak = 0
        current = 0

        async def slow_get(*_args: Any, **_kwargs: Any) -> MagicMock:
            nonlocal peak, current
            current += 1
            peak = max(peak, current)
            await asyncio.sleep(0.01)
            current -= 1
            return _response(200, json_body={})

        fake = MagicMock()
        fake.get = AsyncMock(side_effect=slow_get)
        fake.aclose = AsyncMock()
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                await asyncio.gather(
                    *(client.get_json(f"https://example.org/{n}") for n in range(10))
                )
        assert peak <= 2, f"concurrency cap breached: peak {peak}"


@pytest.mark.unit
class TestGetBytes:
    async def test_truncates_at_ceiling_without_raising(self) -> None:
        """Archived pages can be enormous. Truncating beats both buffering and
        failing — the caller gets partial content plus an honest flag."""
        settings = ArchiveOrgSettings(max_response_bytes=1024, retry_max_attempts=0)

        async def chunks() -> Any:
            for _ in range(5):
                yield b"a" * 500

        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.aiter_bytes = MagicMock(return_value=chunks())
        stream_ctx = MagicMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=response)
        stream_ctx.__aexit__ = AsyncMock(return_value=False)

        fake = MagicMock()
        fake.stream = MagicMock(return_value=stream_ctx)
        fake.aclose = AsyncMock()
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                body, truncated = await client.get_bytes("https://example.org/big")
        assert truncated is True
        assert len(body) == 1024

    async def test_max_bytes_narrows_but_never_widens(self) -> None:
        """A caller must not be able to raise the configured ceiling."""
        settings = ArchiveOrgSettings(max_response_bytes=1024, retry_max_attempts=0)

        async def chunks() -> Any:
            yield b"a" * 4096

        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.aiter_bytes = MagicMock(return_value=chunks())
        stream_ctx = MagicMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=response)
        stream_ctx.__aexit__ = AsyncMock(return_value=False)

        fake = MagicMock()
        fake.stream = MagicMock(return_value=stream_ctx)
        fake.aclose = AsyncMock()
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            async with ArchiveOrgBaseClient(settings) as client:
                body, _ = await client.get_bytes(
                    "https://example.org/big", max_bytes=8192
                )
        assert len(body) == 1024, "caller widened the ceiling"


@pytest.mark.unit
class TestLifecycle:
    async def test_aclose_is_idempotent(self) -> None:
        settings = ArchiveOrgSettings()
        fake = _client_with([])
        with patch(PATCH_TARGET) as mod:
            mod.AsyncClient.return_value = fake
            client = ArchiveOrgBaseClient(settings)
            await client.aclose()
            await client.aclose()
        assert fake.aclose.await_count <= 1
