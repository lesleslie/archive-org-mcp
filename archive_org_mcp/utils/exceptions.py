"""Typed exception hierarchy for archive-org-mcp.

Production code raises these rather than asserting (bandit B101 forbids
`assert` in the package). Every client method converts upstream failures into
one of these, so tool handlers never see a raw httpx exception.
"""

from __future__ import annotations


class ArchiveOrgError(Exception):
    """Base class for every error this package raises."""


class ConfigurationError(ArchiveOrgError):
    """Settings are missing or invalid."""


class UpstreamError(ArchiveOrgError):
    """archive.org returned an unexpected response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        detail = f" (status={status_code})" if status_code is not None else ""
        super().__init__(f"{message}{detail}")


class RateLimitedError(UpstreamError):
    """archive.org signalled throttling (429, or 503 under load).

    Subclasses UpstreamError so a caller retrying on UpstreamError also
    retries throttling, which is the common case.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, status_code=status_code, url=url)


class ResponseTooLargeError(ArchiveOrgError):
    """A response exceeded `max_response_bytes` and was truncated or refused."""

    def __init__(self, *, limit_bytes: int, seen_bytes: int) -> None:
        self.limit_bytes = limit_bytes
        self.seen_bytes = seen_bytes
        super().__init__(f"response exceeded {limit_bytes} bytes (saw at least {seen_bytes})")


class NotFoundError(ArchiveOrgError):
    """The requested URL or identifier has no archived record."""
