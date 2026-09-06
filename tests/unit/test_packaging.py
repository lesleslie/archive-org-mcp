"""Guard the wheel actually contains the package.

The scaffold declared packages = ["archive_org_mcp"] while the code lived at
src/archive_org_mcp/. Hatchling resolves that against the project root, finds
nothing, and emits a metadata-only wheel WITHOUT erroring. Published as-is,
pip install would succeed, install the console script, and then fail at first
run with ModuleNotFoundError.
"""

from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
class TestFlatLayout:
    def test_package_is_at_repo_root(self) -> None:
        assert (REPO_ROOT / "archive_org_mcp" / "__init__.py").is_file()

    def test_src_layout_is_gone(self) -> None:
        assert not (REPO_ROOT / "src").exists()

    def test_hatch_target_has_no_src_prefix(self) -> None:
        content = (REPO_ROOT / "pyproject.toml").read_text()
        assert '"src/archive_org_mcp"' not in content
        assert '"archive_org_mcp"' in content


@pytest.mark.unit
class TestBuiltWheel:
    """Requires `uv build` to have run. Skips cleanly if dist/ is empty."""

    @staticmethod
    def _newest_wheel() -> Path | None:
        wheels = sorted((REPO_ROOT / "dist").glob("*.whl"))
        return wheels[-1] if wheels else None

    def test_wheel_contains_package_init(self) -> None:
        wheel = self._newest_wheel()
        if wheel is None:
            pytest.skip("no wheel in dist/; run `uv build` first")
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
        assert "archive_org_mcp/__init__.py" in names, (
            f"wheel ships no package modules, only: {names}"
        )
