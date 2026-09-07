"""Shared fixtures for tool e2e tests.

Every test drives a tool through the MCP surface against a recorded fixture, so
it exercises the same path an agent does. The assertion that matters is
NON-EMPTY: a tool returning a well-formed empty list is precisely the failure
mcp-backend-wiring-discipline.md exists to catch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from archive_org_mcp.models.feed import FEEDS

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PATCH_TARGET = "archive_org_mcp.clients.base_client.ArchiveOrgBaseClient"


def load_fixture(name: str) -> Any:
    path = FIXTURES / name
    if path.suffix == ".json":
        return json.loads(path.read_text())
    return path.read_text()


@pytest.fixture(autouse=True)
def reset_feeds() -> None:
    """Feed state is module-level; isolate it between tests."""
    for feed in FEEDS.values():
        feed.entities_count = 0
        feed.errors_total = 0
        feed.cycles_total = 0
        feed.last_updated_timestamp = None


@pytest.fixture
def stub_json():
    """Patch the base client's get_json to return a fixture body."""

    def _stub(body: Any):
        return patch(f"{PATCH_TARGET}.get_json", AsyncMock(return_value=body))

    return _stub


@pytest.fixture
def stub_bytes():
    """Patch the base client's get_bytes to return fixture bytes."""

    def _stub(body: bytes, truncated: bool = False):
        return patch(
            f"{PATCH_TARGET}.get_bytes", AsyncMock(return_value=(body, truncated))
        )

    return _stub


async def call_tool(tool_name: str, **kwargs: Any) -> Any:
    """Invoke a registered tool through the MCP surface.

    FastMCP returns a ToolResult wrapper. The actual tool payload lives in
    `structured_content` when the tool declares a return schema, otherwise in
    `content[0].text` parsed from the TextContent block.

    For the standard pattern tools here use (returning ``dict[str, object]``),
    structured_content is wrapped as ``{"result": <actual_payload>}``. Unwrap
    that single-key envelope so callers see the tool's declared return value.
    """
    import json

    from archive_org_mcp.server import create_app

    app = await create_app()
    tools = await app.list_tools()
    tool = next(t for t in tools if t.name == tool_name)
    result = await tool.run(kwargs)
    payload: Any = None
    if result.structured_content is not None:
        payload = result.structured_content
    elif result.content:
        first = result.content[0]
        if hasattr(first, "text"):
            try:
                payload = json.loads(first.text)
            except (TypeError, ValueError):
                payload = first.text
    if (
        isinstance(payload, dict)
        and set(payload.keys()) == {"result"}
        and "result" in payload
    ):
        return payload["result"]
    return payload
