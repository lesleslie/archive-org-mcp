"""Console-script entry point."""

from __future__ import annotations

from archive_org_mcp.server import run


def main() -> None:
    """Start the archive-org-mcp server over stdio."""
    run()


if __name__ == "__main__":
    main()
