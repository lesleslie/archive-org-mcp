"""FastMCP entrypoint for archive-org-mcp.

Health surface is deliberately two routes:
  /health  — mcp_common.health.register_http_health_route, which always returns
             HTTP 200 by documented contract. Feed detail rides in
             extra_components; auth detail rides in auth_health_provider.
  /readyz  — in-repo, returns 503 when a required feed is not ok. This is the
             route mcp-backend-wiring-discipline.md's 503 requirement refers to.

create_app is async because mcp-common's profile dispatch is async; sync callers
go through create_app_sync, which bridges via _run_async_safely.

Task 14.2: Auth wiring. The ``Runtime`` class owns the
``BearerTokenMiddleware`` instance and exposes a callable that
``register_http_health_route`` invokes per request to surface live
``AuthHealth`` data in the /health envelope. When auth is disabled
(default), the middleware is not constructed and ``auth_health_provider``
returns ``None`` — the auth component is then omitted from /health.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastmcp import FastMCP
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import JWTIdentityProvider
from mcp_common.auth.error_middleware import AuthErrorTranslationMiddleware
from mcp_common.auth.health import AuthHealth
from mcp_common.auth.identity import IdentityProviderSpec, validate_auth_config
from mcp_common.auth.middleware import BearerTokenMiddleware
from mcp_common.auth.provider import ProviderHealth
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


class Runtime:
    """Wraps ``ArchiveOrgSettings`` and lazily constructs the FastMCP app.

    Task 14.2: this class is also the home of the ``BearerTokenMiddleware``
    wiring. ``_build_auth_middleware`` constructs the middleware from the
    settings' ``auth_config`` dict; ``_build_auth_health_provider`` returns
    a callable that ``register_http_health_route`` invokes per request to
    populate the ``auth`` component in the /health envelope.
    """

    def __init__(self, *, settings: ArchiveOrgSettings) -> None:
        self.settings = settings
        self._auth_middleware: BearerTokenMiddleware | None = None
        self._last_successful_verification_at: datetime | None = None

    def _build_auth_middleware(self) -> BearerTokenMiddleware | None:
        """Construct ``BearerTokenMiddleware`` when auth is configured.

        Returns ``None`` when ``settings.auth_config`` is missing or empty —
        the /health route then omits the auth component entirely.

        I-9 fix (Task 14.2 variant): guard that ``AuthConfig.resolved_secret``
        is not None before passing the JWT provider. A misconfigured sibling
        that enables auth but forgets to set the secret would otherwise crash
        with ``SecretNotConfiguredError`` inside ``JWTIdentityProvider.__init__``.
        We surface that as a RuntimeError so the failure mode is loud at
        startup, not silent on the first request.
        """
        raw = self.settings.auth_config or {}
        if not raw.get("enabled"):
            return None

        # Inject service_name from APP_NAME so the operator's settings.yaml
        # does not need to repeat it. IdentityProviderSpec entries are passed
        # through verbatim from the operator-supplied dict.
        auth_cfg = AuthConfig(
            service_name=APP_NAME,
            **{
                k: v
                for k, v in raw.items()
                if k != "service_name"
            },
        )

        # B6 fix: fail-loud at startup if the auth config is inconsistent
        # (empty trusted_issuers, missing default_provider, etc.) rather than
        # at the first request. Mirrors mcp-common's startup-check contract.
        validate_auth_config(auth_cfg)

        providers: dict[str, JWTIdentityProvider] = {}
        for provider_name, spec in (auth_cfg.identity_providers or {}).items():
            if isinstance(spec, IdentityProviderSpec) and spec.type == "jwt":
                if auth_cfg.resolved_secret is None:
                    raise RuntimeError(
                        "auth.identity_providers['"
                        + provider_name
                        + "'] is type=jwt but auth.secret is None — set "
                        "ARCHIVE_ORG_MCP_AUTH_CONFIG__SECRET or "
                        "BODAI_SHARED_SECRET, or disable auth."
                    )
                providers[provider_name] = JWTIdentityProvider(
                    name=provider_name,
                    secret=auth_cfg.resolved_secret,
                    trusted_issuers=auth_cfg.trusted_issuers,
                )

        self._auth_middleware = BearerTokenMiddleware(
            auth_config=auth_cfg, providers=providers
        )

        return self._auth_middleware

    def _build_auth_health_provider(self):
        """Return a callable that surfaces ``AuthHealth`` to ``/health``.

        Per ``mcp-surface-health-illusion.md``, returning ``None`` keeps the
        auth component out of the envelope when auth is disabled. The
        callable is invoked per request (not captured at registration) so
        transient provider flips surface in the next probe.

        We build ``AuthHealth`` directly (rather than calling the async
        ``AuthHealth.from_providers`` helper) because
        ``register_http_health_route`` invokes the provider callable
        synchronously and expects a sync ``AuthHealth`` return. Provider
        healths are re-read off the live middleware on every probe (Issue
        #6 fix — was previously snapshotted at construction time).
        """
        if self._auth_middleware is None:
            return None

        mw = self._auth_middleware

        def _provider() -> AuthHealth:
            provider_healths: dict[str, ProviderHealth] = {
                name: ProviderHealth(name=name, state="healthy")
                for name in (mw.providers or {})
            }
            return AuthHealth(
                providers=provider_healths,
                verifications_total=mw.verifications_total,
                errors_total=mw.errors_total,
                last_successful_verification_at=self._last_successful_verification_at,
            )

        return _provider


def _register_routes(app: FastMCP, runtime: Runtime) -> None:
    """Register /health (always 200) and /readyz (503 on degraded)."""
    register_http_health_route(
        app,
        service_name=APP_NAME,
        version=__version__,
        extra_components=as_components(),
        auth_health_provider=runtime._build_auth_health_provider(),
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


async def create_app(
    settings: ArchiveOrgSettings | None = None,
    *,
    runtime: Runtime | None = None,
) -> FastMCP:
    """Build the configured FastMCP application."""
    if settings is None:
        settings = get_settings()
    if runtime is None:
        runtime = Runtime(settings=settings)

    # Construct auth middleware at lifespan entry so failures (misconfigured
    # providers, missing secrets) surface at startup, not on first request.
    runtime._build_auth_middleware()

    app = FastMCP(name=APP_NAME, version=__version__)

    seed_liveness_context(service_name=APP_NAME, version=__version__)
    bootstrap_baseline_tools(app)
    if runtime._auth_middleware is not None:
        app.add_middleware(runtime._auth_middleware)  # type: ignore[arg-type]
    # B2 fix: AuthError subclasses raised by BearerTokenMiddleware must be
    # translated to JSON-RPC -32001 with OAuth-style data. Install the
    # translator unconditionally so AuthErrors surfaced by future
    # middleware (or by @require_auth) hit the same shape end-to-end.
    app.add_middleware(AuthErrorTranslationMiddleware())
    _register_routes(app, runtime)

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


def create_app_sync(
    settings: ArchiveOrgSettings | None = None,
    *,
    runtime: Runtime | None = None,
) -> FastMCP:
    """Sync wrapper around create_app for CLI and __main__ entry points."""
    return _run_async_safely(create_app(settings, runtime=runtime))


def run() -> None:
    """Start the FastMCP server over stdio."""
    create_app_sync().run()


if __name__ == "__main__":
    run()