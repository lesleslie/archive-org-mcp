# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-09-08

### Added

- auth: Wire BearerTokenMiddleware into archive-org-mcp lifespan
- Call validate_auth_config at startup
- catalog: Advancedsearch and metadata client with two tools
- clients: Backoff calculator composing with oneiric workflow.retry
- clients: Base httpx2 client with politeness controls
- config: Layered settings with politeness bounds
- errors: Typed exception hierarchy
- health: Feed state with the four wiring-discipline signals
- retrieval: Streaming snapshot fetch with truncation
- server: Baseline tools, two health routes, profile dispatch
- Snapshot model, CDX client, and two wayback tools

### Changed

- End-of-file newlines and import sort from crackerjack fast hooks

### Fixed

- build: Flat layout so the wheel contains the package

### Documentation

- Replace scaffold banner with real usage

### Testing

- e2e: One non-empty assertion per registered tool
- proof: One live CDX call asserting real, non-empty data

### Internal

- Add uv.lock from uv-lock hook
- Initial commit of PyPI name-reservation scaffold
- Ratchet coverage floor and pass the full gate
