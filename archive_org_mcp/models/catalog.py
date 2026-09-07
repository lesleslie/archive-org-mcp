"""Internet Archive catalog models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CatalogItem(BaseModel):
    """One result from advancedsearch."""

    identifier: str
    title: str | None = None
    mediatype: str | None = None
    date: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> CatalogItem:
        """Build from an advancedsearch doc, preserving unknown keys."""
        known = {"identifier", "title", "mediatype", "date"}
        return cls(
            identifier=str(doc.get("identifier", "")),
            title=doc.get("title"),
            mediatype=doc.get("mediatype"),
            date=doc.get("date"),
            extra={key: value for key, value in doc.items() if key not in known},
        )


class ItemMetadata(BaseModel):
    """Response from the metadata endpoint for one identifier."""

    identifier: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    files_count: int = Field(default=0, ge=0)
    server: str | None = None
