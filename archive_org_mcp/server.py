"""FastMCP entrypoint for archive-org-mcp.

Health surface is deliberately two routes:
  /health  — mcp_common.health.register_http_health_route, which always returns
             HTTP 200 by documented contract. Feed detail rides in
             extra_components.
  /readyz  — in-repo, returns 503 when a required feed is not ok. This is the
             route mcp-backend-wiring-discipline.md's 503 requirement refers to.

create_app is async because mcp-common's profile dispatch is async; sync callers
go through create_app_sync, which bridges via _run_async_safely.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import FastMCP
from mcp_common.baseline_tools import seed_liveness_context
from mcp_common.bootstrap import bootstrap_baseline_tools
from mcp_common.health import register_http_health_route
from mcp_common.tools.dispatch import _apply_tool_profile
from oneiric.core.logging import get_logger

from archive_org_mcp import __version__
from archive_org_mcp.clients.base_client import ArchiveOrgBaseClient
from archive_org_mcp.clients.catalog_client import CatalogClient
from archive_org_mcp.clients.retrieval_client import RetrievalClient
from archive_org_mcp.clients.wayback_client import WaybackClient
from archive_org_mcp.config.settings import ArchiveOrgSettings, get_settings
from archive_org_mcp.models.feed import as_components, required_feeds_healthy
from archive_org_mcp.tools.profiles import (
    ARCHIVE_ORG_MANDATORY_GROUPS,
    PROFILE_REGISTRATIONS,
    ClientBundle,
    _build_registration_map,
    register_all_tool_groups,
)

APP_NAME = "archive-org-mcp"
logger = get_logger("archive_org_mcp.server")


def _run_async_safely(coro: Any) -> Any:
    """Run a coroutine from a sync context, tolerating an already-running loop.

    asyncio.run when no loop is running; a private single-worker executor with a
    fresh asyncio.run when one is (the case under pytest-asyncio).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _build_clients(settings: ArchiveOrgSettings) -> ClientBundle:
    base = ArchiveOrgBaseClient(settings)
    return ClientBundle(
        wayback=WaybackClient(base, settings),
        catalog=CatalogClient(base, settings),
        retrieval=RetrievalClient(base, settings),
    )


def _register_routes(app: FastMCP) -> None:
    """Register /health (always 200) and /readyz (503 on degraded)."""
    register_http_health_route(
        app,
        service_name=APP_NAME,
        version=__version__,
        extra_components=as_components(),
    )

    @app.custom_route("/readyz", methods=["GET"])
    async def readyz(_request: Any) -> Any:
        from starlette.responses import JSONResponse

        healthy = required_feeds_healthy()
        return JSONResponse(
            {
                "status": "ok" if healthy else "degraded",
                "service": APP_NAME,
                "version": __version__,
                "components": as_components(),
            },
            status_code=200 if healthy else 503,
        )


async def create_app(settings: ArchiveOrgSettings | None = None) -> FastMCP:
    """Build the configured FastMCP application."""
    if settings is None:
        settings = get_settings()

    app = FastMCP(name=APP_NAME, version=__version__)

    seed_liveness_context(service_name=APP_NAME, version=__version__)
    bootstrap_baseline_tools(app)
    _register_routes(app)

    clients = _build_clients(settings)
    await _apply_tool_profile(
        app,
        profile_env_var="ARCHIVE_ORG_MCP_TOOL_PROFILE",
        registrations=PROFILE_REGISTRATIONS,
        registration_map=_build_registration_map(clients),
        register_all_fn=lambda srv: _register_all_groups(srv, clients),
        mandatory_groups=ARCHIVE_ORG_MANDATORY_GROUPS,
        essential_tool_names={"health_check_all"},
    )
    logger.info("archive-org-mcp-ready", version=__version__)
    return app


def _register_all_groups(server: FastMCP, clients: ClientBundle) -> None:
    """Bridge that drops the tool-group→tool-name map return type.

    ``register_all_tool_groups`` returns the map for the test helper
    convenience, but ``_apply_tool_profile``'s ``register_all_fn`` signature is
    ``Callable[[FastMCP], Awaitable[None] | None]``. Discard the return value
    to satisfy the signature without breaking the helper.
    """
    register_all_tool_groups(server, clients)


def create_app_sync(settings: ArchiveOrgSettings | None = None) -> FastMCP:
    """Sync wrapper around create_app for CLI and __main__ entry points."""
    return _run_async_safely(create_app(settings))


def run() -> None:
    """Start the FastMCP server over stdio."""
    create_app_sync().run()


if __name__ == "__main__":
    run()
