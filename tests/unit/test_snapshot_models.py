from __future__ import annotations

import pytest
from pydantic import ValidationError

from archive_org_mcp.models.snapshot import Snapshot, normalize_timestamp


@pytest.mark.unit
class TestNormalizeTimestamp:
    """CDX wants 14-digit YYYYMMDDhhmmss. Callers routinely pass a date."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2024", "20240000000000"),
            ("202401", "20240100000000"),
            ("20240115", "20240115000000"),
            ("2024011512", "20240115120000"),
            ("20240115123045", "20240115123045"),
        ],
    )
    def test_zero_pads_to_fourteen(self, raw: str, expected: str) -> None:
        assert normalize_timestamp(raw) == expected

    def test_rejects_non_digits(self) -> None:
        with pytest.raises(ValueError):
            normalize_timestamp("2024-01-15")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError):
            normalize_timestamp("202401151230456789")

    def test_none_passes_through(self) -> None:
        assert normalize_timestamp(None) is None


@pytest.mark.unit
class TestSnapshot:
    def test_builds_from_cdx_row(self) -> None:
        header = ["timestamp", "original", "mimetype", "statuscode", "digest", "length"]
        row = [
            "20240115123045",
            "https://example.org/",
            "text/html",
            "200",
            "ABC123",
            "4096",
        ]
        snapshot = Snapshot.from_cdx_row(header, row)
        assert snapshot.timestamp == "20240115123045"
        assert snapshot.original == "https://example.org/"
        assert snapshot.statuscode == "200"
        assert snapshot.length == 4096

    def test_tolerates_missing_optional_columns(self) -> None:
        """CDX field sets vary with the fl= parameter."""
        snapshot = Snapshot.from_cdx_row(
            ["timestamp", "original"], ["20240115123045", "https://example.org/"]
        )
        assert snapshot.mimetype is None
        assert snapshot.length is None

    def test_non_numeric_length_becomes_none(self) -> None:
        """CDX emits '-' for unknown lengths."""
        snapshot = Snapshot.from_cdx_row(
            ["timestamp", "original", "length"],
            ["20240115123045", "https://example.org/", "-"],
        )
        assert snapshot.length is None

    def test_wayback_url_is_derived(self) -> None:
        snapshot = Snapshot.from_cdx_row(
            ["timestamp", "original"], ["20240115123045", "https://example.org/"]
        )
        assert snapshot.wayback_url == (
            "https://web.archive.org/web/20240115123045/https://example.org/"
        )

    def test_timestamp_is_required(self) -> None:
        with pytest.raises(ValidationError):
            Snapshot(original="https://example.org/")
