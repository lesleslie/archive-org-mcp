"""Per-tool feed state.

Required by .claude/decisions/mcp-backend-wiring-discipline.md: every registered
tool must expose feed.entities_count, feed.last_updated_timestamp,
feed.errors_total, and cycles_total, and /readyz must return 503 when a required
feed is degraded.

The important rule is that a feed which has never returned a non-empty result is
`degraded`, not `ok`. A server can otherwise pass every test, answer 200 on
/health, and list 30 tools while returning zero rows — the failure mode recorded
as `mcp-surface-health-illusion`.

Wiring-discipline contract: per-component payloads use the boolean key `healthy`,
not the string `status` — orchestrators and the wiring audit pattern-match on
`healthy` being `False` to flag degraded feeds. Matches the medium-mcp and
scapy-mcp pattern.
"""

from __future__ import annotations

import time
from typing import Literal

FeedStatus = Literal["ok", "degraded", "capability_unavailable"]


class FeedState:
    """Mutable health record for one data feed."""

    def __init__(self, *, name: str, required: bool) -> None:
        self.name = name
        self.required = required
        self.entities_count = 0
        self.last_updated_timestamp: float | None = None
        self.errors_total = 0
        self.cycles_total = 0
        self._capability_unavailable = False
        self._capability_unavailable_reason: str | None = None

    @property
    def healthy(self) -> bool:
        """Boolean health flag for wiring-discipline consumers.

        True only when the feed has returned at least one non-empty result and
        is not marked capability_unavailable. A working transport over an empty
        upstream is NOT healthy.
        """
        if self._capability_unavailable:
            return False
        return self.entities_count > 0

    @property
    def status(self) -> FeedStatus:
        """Current health as a string (for legacy consumers that read it)."""
        if self._capability_unavailable:
            return "capability_unavailable"
        if self.entities_count > 0:
            return "ok"
        return "degraded"

    def record_cycle(self, *, entities: int = 0, error: str | None = None) -> None:
        """Record a completed upstream call.

        Keyword-only signature matches medium-mcp and scapy-mcp. Pass exactly one
        of `entities` (success path) or `error` (failure path); if both are
        passed, `error` wins.

        Args:
            entities: Number of items the upstream returned. > 0 marks the feed
                healthy.
            error: Error message when the cycle failed. Increments `errors_total`
                without clearing `entities_count` (a transient error is not data
                loss).
        """
        self.cycles_total += 1
        self.last_updated_timestamp = time.time()
        if error is not None:
            self.errors_total += 1
            return
        if entities > 0:
            self.entities_count = entities

    def record_error(self) -> None:
        """Record a failed upstream call. Does not clear `entities_count`."""
        self.record_cycle(error="upstream failure")

    def mark_capability_unavailable(self, reason: str) -> None:
        """Mark this feed unavailable by environment rather than by fault.

        Args:
            reason: Human-readable explanation surfaced in the health payload.

        Raises:
            ValueError: If the feed is required. A required feed being absent is
                a fault and must surface as `degraded` so /readyz returns 503.
        """
        if self.required:
            raise ValueError(
                f"feed {self.name!r} is required and cannot be "
                "capability_unavailable; it must report degraded"
            )
        self._capability_unavailable = True
        self._capability_unavailable_reason = reason

    def as_component(self) -> dict[str, object]:
        """Render one component dict. Exposed via the module-level `as_components`."""
        return {
            "name": self.name,
            "healthy": self.healthy,
            "status": self.status,
            "required": self.required,
            "feed.entities_count": self.entities_count,
            "feed.last_updated_timestamp": self.last_updated_timestamp,
            "feed.errors_total": self.errors_total,
            "cycles_total": self.cycles_total,
        }


FEEDS: dict[str, FeedState] = {
    "cdx": FeedState(name="cdx", required=True),
    "catalog": FeedState(name="catalog", required=True),
}


def as_components() -> list[dict[str, object]]:
    """Render every feed as a component dict for `extra_components=` callers.

    Returns:
        A list with one dict per registered feed, each carrying the boolean
        `healthy` key required by the wiring-discipline contract.
    """
    return [feed.as_component() for feed in FEEDS.values()]


def required_feeds_healthy() -> bool:
    """True when every required feed is healthy. Drives /readyz."""
    return all(feed.healthy for feed in FEEDS.values() if feed.required)
