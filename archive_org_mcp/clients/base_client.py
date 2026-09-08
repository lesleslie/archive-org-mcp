"""Async HTTP client for archive.org with self-imposed politeness.

Internet Archive states: "Please be respectful and use this free public
resource. While we do not have hard rate limits..." — so every limit here is
ours to enforce. The semaphore bounds concurrency, the retry loop backs off with
jitter, and get_bytes refuses to buffer an unbounded response.

404 is terminal and never retried: re-asking for a page that was never archived
just costs IA bandwidth.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx2 as httpx
from oneiric.core.logging import get_logger

from archive_org_mcp.clients.backoff import next_delay
from archive_org_mcp.utils.exceptions import (
    NotFoundError,
    RateLimitedError,
    UpstreamError,
)

if TYPE_CHECKING:
    from types import TracebackType

    from archive_org_mcp.config.settings import ArchiveOrgSettings

logger = get_logger("archive_org_mcp.client")

_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class ArchiveOrgBaseClient:
    """Shared transport for every archive.org endpoint."""

    def __init__(self, settings: ArchiveOrgSettings) -> None:
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.concurrency_limit)
        self._closed = False
        self._client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )

    async def __aenter__(self) -> ArchiveOrgBaseClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the transport. Safe to call more than once."""
        if self._closed:
            return
        self._closed = True
        await self._client.aclose()

    def _raise_for_status(self, status_code: int, url: str, headers: object) -> None:
        if status_code == 404:
            raise NotFoundError(f"no archived record for {url}")
        if status_code == 429:
            retry_after: float | None = None
            if isinstance(headers, dict):
                raw = headers.get("Retry-After")
                if isinstance(raw, (str, int, float)):
                    try:
                        retry_after = float(raw)
                    except ValueError:
                        retry_after = None
            raise RateLimitedError(
                "archive.org is throttling this client",
                status_code=status_code,
                url=url,
                retry_after=retry_after,
            )
        if status_code >= 400:
            raise UpstreamError("unexpected response", status_code=status_code, url=url)

    async def get_json(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
    ) -> object:
        """GET `url` and return the parsed JSON body.

        Raises:
            NotFoundError: on 404 (terminal, never retried).
            RateLimitedError: on 429 after retries are exhausted.
            UpstreamError: on any other 4xx/5xx after retries are exhausted.
        """
        attempt = 0
        while True:
            try:
                async with self._semaphore:
                    response = await self._client.get(url, params=params)
                status = response.status_code
                if status < 400:
                    return response.json()
                self._raise_for_status(status, url, response.headers)
            except NotFoundError:
                raise
            except UpstreamError as exc:
                if exc.status_code not in _RETRYABLE_STATUSES:
                    raise
                delay = await next_delay(attempt, self._settings)
                if delay is None:
                    raise
                logger.warning(
                    "archive-org-retry",
                    url=url,
                    attempt=attempt,
                    status=exc.status_code,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
                attempt += 1

    async def get_bytes(
        self,
        url: str,
        *,
        max_bytes: int | None = None,
    ) -> tuple[bytes, bool]:
        """Stream `url`, stopping at the byte ceiling.

        Args:
            url: Target URL.
            max_bytes: Optional narrower ceiling. It can only lower the
                configured `max_response_bytes`, never raise it.

        Returns:
            `(body, truncated)`. `truncated` is True when the ceiling stopped
            the read before the response ended.
        """
        ceiling = self._settings.max_response_bytes
        if max_bytes is not None:
            ceiling = min(ceiling, max_bytes)

        buffer = bytearray()
        truncated = False
        async with self._semaphore, self._client.stream("GET", url) as response:
            status = response.status_code
            if status >= 400:
                self._raise_for_status(status, url, response.headers)
            async for chunk in response.aiter_bytes():
                remaining = ceiling - len(buffer)
                if remaining <= 0:
                    truncated = True
                    break
                if len(chunk) > remaining:
                    buffer.extend(chunk[:remaining])
                    truncated = True
                    break
                buffer.extend(chunk)
        return bytes(buffer), truncated
