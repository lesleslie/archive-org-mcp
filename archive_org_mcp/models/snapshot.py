"""Wayback snapshot model.

CDX returns a row-oriented JSON array whose FIRST ROW IS THE HEADER, not data.
Treating row 0 as a snapshot is the single most common CDX integration bug, so
construction goes through `from_cdx_row(header, row)` — a header is always
required, which makes the mistake hard to make silently.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

_WAYBACK_PREFIX = "https://web.archive.org/web"
_TIMESTAMP_WIDTH = 14


def normalize_timestamp(raw: str | None) -> str | None:
    """Zero-pad a partial timestamp to 14-digit YYYYMMDDhhmmss.

    Args:
        raw: A digit string of 1-14 characters, or None.

    Returns:
        The padded timestamp, or None when `raw` is None.

    Raises:
        ValueError: If `raw` contains non-digits or exceeds 14 characters.
    """
    if raw is None:
        return None
    if not raw.isdigit():
        raise ValueError(f"timestamp must be digits only, got {raw!r}")
    if len(raw) > _TIMESTAMP_WIDTH:
        raise ValueError(f"timestamp exceeds {_TIMESTAMP_WIDTH} digits: {raw!r}")
    return raw.ljust(_TIMESTAMP_WIDTH, "0")


class Snapshot(BaseModel):
    """One archived capture of a URL."""

    timestamp: str
    original: str | None = None
    mimetype: str | None = None
    statuscode: str | None = None
    digest: str | None = None
    length: int | None = Field(default=None, ge=0)

    @property
    def wayback_url(self) -> str:
        """Browsable URL for this capture."""
        return f"{_WAYBACK_PREFIX}/{self.timestamp}/{self.original or ''}"

    @classmethod
    def from_cdx_row(cls, header: list[str], row: list[str]) -> Snapshot:
        """Build a Snapshot from a CDX header/row pair.

        Args:
            header: CDX row 0 — the column names.
            row: A data row from CDX row 1 onward.

        Returns:
            A populated Snapshot. Columns absent from `header` are None.
        """
        mapping = dict(zip(header, row, strict=False))
        length_raw = mapping.get("length")
        length: int | None = None
        if length_raw is not None and length_raw.isdigit():
            length = int(length_raw)
        return cls(
            timestamp=mapping["timestamp"],
            original=mapping.get("original"),
            mimetype=mapping.get("mimetype"),
            statuscode=mapping.get("statuscode"),
            digest=mapping.get("digest"),
            length=length,
        )
