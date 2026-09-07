"""Retrieved archived page."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievedSnapshot(BaseModel):
    """Content of one archived capture, possibly truncated."""

    url: str
    timestamp: str
    content: str
    truncated: bool = False
    fetched_bytes: int = Field(default=0, ge=0)
