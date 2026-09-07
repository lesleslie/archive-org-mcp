"""Phase 0b — proof that the upstream endpoint exists and returns real data.

This guards against spec finding 4.3: a public MCP server that registered six
tools against five endpoints that do not exist, shipped a fabricated auth token,
and passed every mocked test while being incapable of returning one real row.
Endpoint existence is a falsifiable claim, so it gets falsified here.

Marked requires_network and deselected from the default crackerjack run. CI here
is crackerjack on the developer machine — there is no hosted runner, so marker
deselection is the only separation between this and routine runs.

Run explicitly:
  pytest tests/integration/test_upstream_proof.py -m requires_network -v

Refresh the recording:
  ARCHIVE_ORG_MCP_REFRESH_PROOF=1 pytest tests/integration/test_upstream_proof.py \
      -m requires_network -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from archive_org_mcp.clients.base_client import ArchiveOrgBaseClient
from archive_org_mcp.clients.wayback_client import WaybackClient
from archive_org_mcp.config.settings import ArchiveOrgSettings

RECORDING = Path(__file__).resolve().parents[1] / "fixtures" / "cdx_live.json"

# archive.org itself, archived since 1996 — as close to a guaranteed-archived
# URL as exists. If this returns nothing, the endpoint or its contract changed.
PROOF_URL = "https://archive.org/"


@pytest.mark.integration
@pytest.mark.requires_network
class TestUpstreamProof:
    async def test_live_cdx_query_returns_at_least_one_row(self) -> None:
        settings = ArchiveOrgSettings()
        async with ArchiveOrgBaseClient(settings) as base:
            client = WaybackClient(base, settings)
            snapshots = await client.snapshots(PROOF_URL, limit=5)

        assert snapshots, (
            "live CDX query returned zero rows. Either the endpoint moved, its "
            "response shape changed, or the parser is wrong. Do not register "
            "tools against an endpoint that cannot be shown to return data."
        )
        first = snapshots[0]
        assert first.timestamp.isdigit()
        assert len(first.timestamp) == 14
        assert first.timestamp != "timestamp", "header row leaked into data"

        if not RECORDING.exists() or os.environ.get("ARCHIVE_ORG_MCP_REFRESH_PROOF"):
            RECORDING.write_text(
                json.dumps(
                    [snapshot.model_dump() for snapshot in snapshots], indent=2
                )
                + "\n"
            )

    def test_recording_exists_after_first_run(self) -> None:
        """Once recorded, later runs replay hermetically instead of re-calling."""
        if not RECORDING.exists():
            pytest.skip("run the live proof once to create the recording")
        payload = json.loads(RECORDING.read_text())
        assert payload, "recording is empty"
        assert payload[0]["timestamp"].isdigit()
