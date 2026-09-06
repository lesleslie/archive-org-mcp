# archive-org-mcp

> **Scaffold status: PyPI name reservation.** This package is a placeholder scaffold to claim
> the `archive-org-mcp` name on PyPI. The MCP server is not yet implemented.

MCP server for the [Internet Archive](https://archive.org) (archive.org).
Provides access to:

- **Wayback Machine** — query historical snapshots of any URL via the CDX API
- **Catalog search** — search the Internet Archive's metadata catalog (books,
  videos, audio, software, web pages)
- **Saved pages** — fetch archived page content for a specific timestamp
- **Availability** — closest-snapshot lookup for a URL + timestamp

## Reserve the PyPI name

```bash
cd /Users/les/Projects/archive-org-mcp
uv build
uv publish  # uses UV_PUBLISH_TOKEN from env
```

The package name `archive-org-mcp` is currently free on PyPI (verified 2026-08-31).
Publishing a placeholder 0.1.0 release locks the name.

## Architecture (planned)

Mirrors the `raindropio-mcp` pattern in this ecosystem:

- `httpx2` for the archive.org REST API client (no auth required for read-only
  endpoints; rate-limited)
- `fastmcp` for the MCP server surface
- `oneiric` for layered config (`settings/archive-org-mcp.yaml`, `local.yaml`,
  env vars) — configures the CDX endpoint, rate-limit backoff, and an
  optional `ARCHIVE_ORG_AUTH_TOKEN` for write- operations
- `mcp-common` for bootstrap, health endpoints
- `pydantic`/`pydantic-settings` for typed config models

## Why this name

We considered `internetarchive-mcp`, `waybackmachine-mcp`, `wayback-mcp` (taken),
and `ia-mcp` (collides with anything). `archive-org-mcp` is the user-facing
branding of the Internet Archive (their primary domain) and is the most
discoverable name.

## Status

| Phase | State |
|---|---|
| PyPI name reservation | **pending** (run `uv publish`) |
| Spec / plan | not written |
| Implementation | not started |
| Tests | not started |

## License

BSD-3-Clause.