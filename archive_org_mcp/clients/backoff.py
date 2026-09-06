"""Retry delay calculation.

Composes with oneiric's `workflow.retry` action per CLAUDE.md's
"check oneiric.actions before writing common primitives" rule. That action is
`side_effect_free=True` and returns guidance — {attempt, max_attempts, status,
next_attempt, delay_seconds} — so it computes the delay and this module sleeps
on it. Its jitter is deterministic (0.25 if attempt % 2 == 0 else 0.15), which
keeps concurrent clients synchronized; `backoff_random_jitter` layers real
randomness on top to break retry storms against a shared public resource.

If the oneiric action is unavailable, an equivalent local calculation is used so
the client still backs off rather than hammering upstream.
"""

from __future__ import annotations

from contextlib import suppress
from random import Random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archive_org_mcp.config.settings import ArchiveOrgSettings

_ONEIRIC_RETRY_AVAILABLE = False
with suppress(ImportError):
    from oneiric.actions.workflow import WorkflowRetryAction

    _ONEIRIC_RETRY_AVAILABLE = True

_JITTER_SPREAD = 0.25


def _local_delay(attempt: int, settings: ArchiveOrgSettings) -> float:
    """Exponential backoff, used when the oneiric action is unavailable."""
    raw = settings.backoff_base_seconds * (settings.backoff_multiplier**attempt)
    return min(raw, settings.backoff_max_seconds)


async def _oneiric_delay(attempt: int, settings: ArchiveOrgSettings) -> float | None:
    """Ask oneiric's retry action for a delay. Returns None when exhausted."""
    action = WorkflowRetryAction()
    record = await action.execute(
        {
            "attempt": attempt,
            "max_attempts": settings.retry_max_attempts,
            "base_delay_seconds": settings.backoff_base_seconds,
            "multiplier": settings.backoff_multiplier,
            "max_delay_seconds": settings.backoff_max_seconds,
        }
    )
    if record.get("status") != "scheduled":
        return None
    delay = record.get("delay_seconds")
    return float(delay) if delay is not None else None


async def next_delay(
    attempt: int,
    settings: ArchiveOrgSettings,
    *,
    rng: Random | None = None,
) -> float | None:
    """Seconds to wait before retry `attempt + 1`, or None if exhausted.

    Args:
        attempt: Zero-based index of the attempt that just failed.
        settings: Supplies the backoff curve and jitter flag.
        rng: Injectable randomness so jitter is testable.

    Returns:
        A non-negative delay, or None when `retry_max_attempts` is reached.
    """
    if attempt >= settings.retry_max_attempts:
        return None

    delay: float | None = None
    if _ONEIRIC_RETRY_AVAILABLE:
        delay = await _oneiric_delay(attempt, settings)
        if delay is None:
            return None
    if delay is None:
        delay = _local_delay(attempt, settings)

    if settings.backoff_random_jitter:
        source = rng if rng is not None else Random()
        delay *= 1.0 + source.uniform(-_JITTER_SPREAD, _JITTER_SPREAD)

    return max(0.0, min(delay, settings.backoff_max_seconds))
