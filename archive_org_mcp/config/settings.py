"""Typed, layered configuration for archive-org-mcp.

Precedence: defaults -> settings/archive-org-mcp.yaml -> settings/local.yaml
-> ARCHIVE_ORG_MCP_* environment variables.

project_root resolves to the repo root only under the flat layout
(archive_org_mcp/config/settings.py -> parent.parent == repo root). This is a
second reason the src/ layout was removed in Task 1.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    _VERSION = _pkg_version("archive-org-mcp")
except PackageNotFoundError:  # editable install before metadata exists
    _VERSION = "0.0.0-dev"


class ArchiveOrgSettings(BaseSettings):
    """Runtime configuration. Field bounds encode the politeness contract."""

    model_config = SettingsConfigDict(
        env_prefix="ARCHIVE_ORG_MCP_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tool_profile: Literal["full", "standard", "minimal"] = "full"
    log_level: str = "INFO"
    http_port: int | None = 3054

    cdx_base_url: HttpUrl = HttpUrl("http://web.archive.org/cdx/search/cdx")
    availability_base_url: HttpUrl = HttpUrl("https://archive.org/wayback/available")
    search_base_url: HttpUrl = HttpUrl("https://archive.org/advancedsearch.php")
    metadata_base_url: HttpUrl = HttpUrl("https://archive.org/metadata")

    concurrency_limit: int = Field(2, ge=1, le=10)
    max_response_bytes: int = Field(5_242_880, ge=1024)
    retry_max_attempts: int = Field(4, ge=0, le=10)
    backoff_base_seconds: float = Field(1.0, ge=0.0)
    backoff_multiplier: float = Field(2.0, ge=1.0)
    backoff_max_seconds: float = Field(30.0, ge=0.0)
    backoff_random_jitter: bool = True
    http_timeout_seconds: float = Field(30.0, gt=0.0)
    cache_ttl_seconds: int = Field(3600, ge=0)

    # The repo URL is intentionally not embedded in the default — the GitHub URL
    # does not exist yet. Operators override user_agent in settings/archive-org-mcp.yaml
    # or via ARCHIVE_ORG_MCP_USER_AGENT once the repo is pushed. The default still
    # identifies the client and version per IA's politeness guidance.
    user_agent: str = f"archive-org-mcp/{_VERSION}"


@lru_cache(maxsize=1)
def get_settings() -> ArchiveOrgSettings:
    """Return the process-wide settings singleton."""
    return ArchiveOrgSettings()
