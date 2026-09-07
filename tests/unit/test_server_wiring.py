"""Server wiring.

The baseline is FOUR tools, not one: bootstrap_baseline_tools registers
discover_tools, get_liveness, get_readiness, and health_check_all. Registering
only discover_tools leaves probes without a liveness surface.
"""

from __future__ import annotations

import pytest

from archive_org_mcp.server import create_app
from archive_org_mcp.tools.profiles import PROFILE_REGISTRATIONS

EXPECTED_BASELINE = {
    "discover_tools",
    "get_liveness",
    "get_readiness",
    "health_check_all",
}


async def _tool_names(app: object) -> set[str]:
    tools = await app.list_tools()  # type: ignore[attr-defined]
    return {tool.name for tool in tools}


@pytest.mark.unit
class TestBaselineTools:
    async def test_all_four_baseline_tools_registered(self) -> None:
        app = await create_app()
        assert EXPECTED_BASELINE <= await _tool_names(app)


@pytest.mark.unit
class TestProfileDispatch:
    async def test_full_profile_exposes_every_domain_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARCHIVE_ORG_MCP_TOOL_PROFILE", "full")
        names = await _tool_names(await create_app())
        for tool in (
            "wayback_snapshots",
            "wayback_closest",
            "catalog_search",
            "catalog_metadata",
            "retrieve_snapshot",
        ):
            assert tool in names, f"{tool} missing at full profile"

    async def test_minimal_profile_still_exposes_health(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """essential_tool_names enforces this at every profile."""
        monkeypatch.setenv("ARCHIVE_ORG_MCP_TOOL_PROFILE", "minimal")
        names = await _tool_names(await create_app())
        assert "health_check" in names or "health_check_all" in names

    async def test_minimal_profile_omits_retrieval(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARCHIVE_ORG_MCP_TOOL_PROFILE", "minimal")
        assert "retrieve_snapshot" not in await _tool_names(await create_app())

    def test_profile_registrations_cover_all_three_tiers(self) -> None:
        from mcp_common.tools.dispatch import ToolProfile

        assert set(PROFILE_REGISTRATIONS) == {
            ToolProfile.MINIMAL,
            ToolProfile.STANDARD,
            ToolProfile.FULL,
        }


@pytest.mark.unit
class TestSyncBridge:
    def test_create_app_sync_works_without_a_running_loop(self) -> None:
        """main() is sync but profile dispatch is async. Without the bridge this
        raises 'asyncio.run() cannot be called from a running event loop'."""
        from archive_org_mcp.server import create_app_sync

        app = create_app_sync()
        assert app is not None

    async def test_create_app_sync_works_with_a_running_loop(self) -> None:
        """pytest-asyncio already has a loop running here, which is the case the
        ThreadPoolExecutor branch exists for."""
        from archive_org_mcp.server import create_app_sync

        app = create_app_sync()
        assert app is not None
