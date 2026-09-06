from __future__ import annotations

import pytest

from archive_org_mcp.config.settings import ArchiveOrgSettings


@pytest.mark.unit
class TestDefaults:
    """Defaults are the spec's §13.2 table. Politeness defaults matter because
    Internet Archive enforces no hard rate limits — self-limiting is our job."""

    def test_endpoint_defaults(self) -> None:
        settings = ArchiveOrgSettings()
        assert str(settings.cdx_base_url) == "http://web.archive.org/cdx/search/cdx"
        assert str(settings.availability_base_url).rstrip("/") == (
            "https://archive.org/wayback/available"
        )
        assert str(settings.search_base_url).rstrip("/") == (
            "https://archive.org/advancedsearch.php"
        )
        assert str(settings.metadata_base_url).rstrip("/") == (
            "https://archive.org/metadata"
        )

    def test_politeness_defaults(self) -> None:
        settings = ArchiveOrgSettings()
        assert settings.concurrency_limit == 2
        assert settings.max_response_bytes == 5_242_880
        assert settings.retry_max_attempts == 4
        assert settings.backoff_base_seconds == 1.0
        assert settings.backoff_multiplier == 2.0
        assert settings.backoff_max_seconds == 30.0
        assert settings.backoff_random_jitter is True
        assert settings.http_timeout_seconds == 30.0
        assert settings.cache_ttl_seconds == 3600

    def test_http_port_default(self) -> None:
        assert ArchiveOrgSettings().http_port == 3054

    def test_tool_profile_default(self) -> None:
        assert ArchiveOrgSettings().tool_profile == "full"

    def test_user_agent_identifies_the_client(self) -> None:
        """IA asks to be used respectfully; an anonymous UA is impolite."""
        assert "archive-org-mcp" in ArchiveOrgSettings().user_agent


@pytest.mark.unit
class TestValidation:
    def test_concurrency_limit_is_bounded(self) -> None:
        with pytest.raises(ValueError):
            ArchiveOrgSettings(concurrency_limit=0)
        with pytest.raises(ValueError):
            ArchiveOrgSettings(concurrency_limit=11)

    def test_backoff_multiplier_must_be_at_least_one(self) -> None:
        with pytest.raises(ValueError):
            ArchiveOrgSettings(backoff_multiplier=0.5)

    def test_retry_attempts_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError):
            ArchiveOrgSettings(retry_max_attempts=-1)


@pytest.mark.unit
class TestEnvOverride:
    def test_env_prefix_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARCHIVE_ORG_MCP_CONCURRENCY_LIMIT", "5")
        assert ArchiveOrgSettings().concurrency_limit == 5

    def test_env_override_is_validated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARCHIVE_ORG_MCP_CONCURRENCY_LIMIT", "99")
        with pytest.raises(ValueError):
            ArchiveOrgSettings()
