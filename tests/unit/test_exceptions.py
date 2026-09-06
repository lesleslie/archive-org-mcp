from __future__ import annotations

import pytest

from archive_org_mcp.utils.exceptions import (
    ArchiveOrgError,
    ConfigurationError,
    NotFoundError,
    RateLimitedError,
    ResponseTooLargeError,
    UpstreamError,
)


@pytest.mark.unit
class TestExceptionHierarchy:
    @pytest.mark.parametrize(
        "exc_type",
        [ConfigurationError, UpstreamError, RateLimitedError, ResponseTooLargeError, NotFoundError],
    )
    def test_all_derive_from_base(self, exc_type: type[Exception]) -> None:
        assert issubclass(exc_type, ArchiveOrgError)

    def test_rate_limited_is_an_upstream_error(self) -> None:
        """Callers retrying on UpstreamError must also catch rate limiting."""
        assert issubclass(RateLimitedError, UpstreamError)

    def test_upstream_error_carries_status_and_url(self) -> None:
        err = UpstreamError("bad gateway", status_code=502, url="https://example.org/x")
        assert err.status_code == 502
        assert err.url == "https://example.org/x"
        assert "502" in str(err)

    def test_response_too_large_carries_limit_and_seen(self) -> None:
        err = ResponseTooLargeError(limit_bytes=1024, seen_bytes=2048)
        assert err.limit_bytes == 1024
        assert err.seen_bytes == 2048

    def test_rate_limited_carries_retry_after(self) -> None:
        err = RateLimitedError("slow down", status_code=429, url="u", retry_after=30.0)
        assert err.retry_after == 30.0
