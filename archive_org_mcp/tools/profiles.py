"""Tool-profile dispatch surface.

Mirrors raindropio_mcp/tools/profiles.py. Registration flows through a SINGLE
path — this registration_map — with no parallel optional-block mechanism, per
the dual-track drift pattern recorded on 2026-08-29.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from mcp_common.tools.dispatch import ALL_TOOLS, ToolProfile

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from archive_org_mcp.clients.catalog_client import CatalogClient
    from archive_org_mcp.clients.retrieval_client import RetrievalClient
    from archive_org_mcp.clients.wayback_client import WaybackClient


class ClientBundle:
    """The three domain clients, passed to registration adapters together."""

    def __init__(
        self,
        wayback: WaybackClient,
        catalog: CatalogClient,
        retrieval: RetrievalClient,
    ) -> None:
        self.wayback = wayback
        self.catalog = catalog
        self.retrieval = retrieval


MINIMAL_REGISTRATIONS: list[str] = ["health_tools"]
STANDARD_REGISTRATIONS: list[str] = ["health_tools", "wayback_tools"]
FULL_REGISTRATIONS: list[str] = [
    "health_tools",
    "wayback_tools",
    "catalog_tools",
    "retrieval_tools",
]

PROFILE_REGISTRATIONS: dict[
    ToolProfile,
    list[str | Callable[[FastMCP], Awaitable[None] | None]] | type[ALL_TOOLS],
] = {
    ToolProfile.MINIMAL: MINIMAL_REGISTRATIONS,
    ToolProfile.STANDARD: STANDARD_REGISTRATIONS,
    ToolProfile.FULL: FULL_REGISTRATIONS,
}

ARCHIVE_ORG_MANDATORY_GROUPS: set[str] = {"health_tools"}


def _register_health_tools(server: FastMCP) -> None:
    """Health tool group — present at every profile.

    The four Bodai baseline tools (discover_tools, get_liveness, get_readiness,
    health_check_all) are registered globally by bootstrap_baseline_tools in
    server.create_app(), so this group is intentionally a no-op. It exists so
    that the profile dispatch table carries the group key and the mandatory_groups
    contract resolves, matching the medium-mcp and scapy-mcp patterns.
    """
    return


def _build_registration_map(
    clients: ClientBundle,
) -> dict[str, Callable[[FastMCP], Awaitable[None] | None]]:
    """Map group keys to their registration callables."""
    from archive_org_mcp.tools.catalog import register_catalog_tools
    from archive_org_mcp.tools.retrieval import register_retrieval_tools
    from archive_org_mcp.tools.wayback import register_wayback_tools

    return {
        "health_tools": _register_health_tools,
        "wayback_tools": lambda srv: register_wayback_tools(srv, clients.wayback),
        "catalog_tools": lambda srv: register_catalog_tools(srv, clients.catalog),
        "retrieval_tools": lambda srv: register_retrieval_tools(srv, clients.retrieval),
    }


def register_all_tool_groups(server: FastMCP, clients: ClientBundle) -> dict[str, list[str]]:
    """Register every group, ignoring the profile. Used by register_all_fn.

    Returns a ``{group_name: [tool_name, ...]}`` map so callers (tests, the
    smoke gate) can assert which tools landed. Matches the medium-mcp and
    scapy-mcp return shape — pinning all three plans to the same convention
    lets a cross-repo audit script diff registrations without parsing each
    per-server implementation.
    """
    from archive_org_mcp.tools.catalog import register_catalog_tools
    from archive_org_mcp.tools.retrieval import register_retrieval_tools
    from archive_org_mcp.tools.wayback import register_wayback_tools

    catalog_tools = ["catalog_search", "catalog_metadata"]
    wayback_tools = ["wayback_snapshots", "wayback_closest"]
    retrieval_tools = ["retrieve_snapshot"]

    _register_health_tools(server)
    register_wayback_tools(server, clients.wayback)
    register_catalog_tools(server, clients.catalog)
    register_retrieval_tools(server, clients.retrieval)

    return {
        "health_tools": [],
        "wayback_tools": wayback_tools,
        "catalog_tools": catalog_tools,
        "retrieval_tools": retrieval_tools,
    }


__all__ = [
    "ARCHIVE_ORG_MANDATORY_GROUPS",
    "ClientBundle",
    "PROFILE_REGISTRATIONS",
    "_build_registration_map",
    "register_all_tool_groups",
]
