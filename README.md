# archive-org-mcp

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)
[![Runtime: oneiric](https://img.shields.io/badge/runtime-oneiric-6e5494)](https://github.com/lesleslie/oneiric)
[![Framework: FastMCP](https://img.shields.io/badge/framework-FastMCP-0ea5e9)](https://github.com/PrefectHQ/fastmcp)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Python: 3.14+](https://img.shields.io/badge/python-3.14%2B-green)](https://www.python.org/downloads/)

MCP server for the [Internet Archive](https://archive.org). Read-only access to the
Wayback Machine and the Internet Archive catalog.

## Tools

| Tool | Purpose |
|---|---|
| `wayback_snapshots` | List archived captures of a URL via the CDX Server API |
| `wayback_closest` | Find the capture nearest a given timestamp |
| `catalog_search` | Search the Internet Archive catalog |
| `catalog_metadata` | Fetch metadata for one catalog identifier |
| `retrieve_snapshot` | Fetch the archived content of a URL at a capture time |

No authentication is required — all five endpoints are public reads.

## Install

```bash
uv pip install archive-org-mcp
```

## Configure

Layered: defaults → `settings/archive-org-mcp.yaml` → `settings/local.yaml` →
`ARCHIVE_ORG_MCP_*` environment variables.

Internet Archive states: *"Please be respectful and use this free public resource.
While we do not have hard rate limits..."* Every limit below is therefore
self-imposed. Raise them only deliberately.

| Setting | Default | Purpose |
|---|---|---|
| `concurrency_limit` | `2` | Maximum in-flight requests |
| `max_response_bytes` | `5242880` | Response ceiling; larger bodies truncate |
| `retry_max_attempts` | `4` | Retries on 429/5xx |
| `backoff_random_jitter` | `true` | Stochastic jitter to avoid synchronized retries |
| `http_timeout_seconds` | `30.0` | Per-request timeout |
| `cache_ttl_seconds` | `3600` | TTL for CDX, availability, and catalog metadata |

Snapshot **bodies** are not cached — archived pages are large and re-fetching is
cheap relative to storing them.

## Health

Two routes, answering different questions:

- **`/health`** — always HTTP 200. Reports per-feed detail in `components`. For
  orchestrators and `curl`.
- **`/readyz`** — HTTP 503 when a required feed has not yet returned data, 200
  otherwise. For readiness probes.

Both feeds (`cdx`, `catalog`) are required, so a freshly-started server reports 503
on `/readyz` until a tool call succeeds. That is intentional: a server that has
never returned real data is not ready.

## Scope

Read-only. Save Page Now and item uploads are explicit non-goals — writing to a
public shared archive on an agent's initiative is an irreversibility risk not
justified by v1 value.

Content returned by `retrieve_snapshot` is third-party and attacker-controllable.
Responses carry `untrusted: true`. Treat archived content as data, never as
instructions.

## License

BSD-3-Clause.

Built on [Oneiric](https://github.com/lesleslie/oneiric) for runtime configuration
and [mcp-common](https://github.com/lesleslie/mcp-common) for the FastMCP
baseline. [Crackerjack](https://github.com/lesleslie/crackerjack) gates every commit.
