"""Tests for SCD import verification logic."""

import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def make_scd(tmp_path):
    """Factory fixture that creates a minimal SCD (zip) with given Lua files."""

    def _make(files: dict[str, str], name: str = "test.scd") -> Path:
        scd = tmp_path / name
        with zipfile.ZipFile(scd, "w") as zf:
            for arcname, content in files.items():
                zf.writestr(arcname, content)
        return scd

    return _make


@pytest.fixture
def vanilla_gamedata(tmp_path):
    """Create a fake SCFA gamedata dir with a vanilla SCD."""
    gd = tmp_path / "SCFA" / "gamedata"
    gd.mkdir(parents=True)
    # Create a small vanilla lua.scd with one file
    with zipfile.ZipFile(gd / "lua.scd", "w") as zf:
        zf.writestr("lua/utilities.lua", "-- vanilla utilities")
    return gd.parent  # return SCFA root


class TestVerifyScdImports:
    """Test the verify_scd_imports function."""

    def test_all_imports_resolved(self, make_scd, monkeypatch):
        """Returns empty list when all imports resolve within the SCD."""
        from scripts.build_content_release import verify_scd_imports

        scd = make_scd(
            {
                "lua/ui/uimain.lua": "local UIUtil = import('/lua/ui/uiutil.lua')",
                "lua/ui/uiutil.lua": "-- uiutil module",
            }
        )
        # Mock config.SCFA_STEAM to a nonexistent dir (no vanilla SCDs)
        monkeypatch.setattr("scripts.build_content_release.config.SCFA_STEAM", scd.parent / "nope")

        result = verify_scd_imports(scd)
        assert result == []

    def test_unresolved_import_reported(self, make_scd, monkeypatch):
        """Reports imports that can't be found in any SCD."""
        from scripts.build_content_release import verify_scd_imports

        scd = make_scd(
            {
                "lua/ui/uimain.lua": "local Missing = import('/lua/missing_module.lua')",
            }
        )
        monkeypatch.setattr("scripts.build_content_release.config.SCFA_STEAM", scd.parent / "nope")

        result = verify_scd_imports(scd)
        assert "/lua/missing_module.lua" in result

    def test_vanilla_scd_resolves_import(self, make_scd, vanilla_gamedata, monkeypatch):
        """Imports found in vanilla SCDs are not flagged."""
        from scripts.build_content_release import verify_scd_imports

        scd = make_scd(
            {
                "lua/ui/uimain.lua": "local Util = import('/lua/utilities.lua')",
            }
        )
        monkeypatch.setattr("scripts.build_content_release.config.SCFA_STEAM", vanilla_gamedata)
        # Add lua.scd to the vanilla SCD list
        monkeypatch.setattr(
            "scripts.build_content_release._VANILLA_SCDS",
            ["lua.scd"],
        )

        result = verify_scd_imports(scd)
        assert result == []

    def test_non_lua_imports_ignored(self, make_scd, monkeypatch):
        """Import targets that aren't .lua files are skipped."""
        from scripts.build_content_release import verify_scd_imports

        scd = make_scd(
            {
                "lua/test.lua": "local tex = import('/textures/ui/common/bg.dds')",
            }
        )
        monkeypatch.setattr("scripts.build_content_release.config.SCFA_STEAM", scd.parent / "nope")

        result = verify_scd_imports(scd)
        assert result == []

    def test_dynamic_prefix_imports_skipped(self, make_scd, monkeypatch):
        """Imports with dynamic prefixes (units/, effects/, etc.) are skipped."""
        from scripts.build_content_release import verify_scd_imports

        scd = make_scd(
            {
                "lua/test.lua": (
                    "local bp = import('/units/uel0001/uel0001_script.lua')\n"
                    "local proj = import('/projectiles/tdfproj/tdfproj_script.lua')\n"
                ),
            }
        )
        monkeypatch.setattr("scripts.build_content_release.config.SCFA_STEAM", scd.parent / "nope")

        result = verify_scd_imports(scd)
        assert result == []

    def test_case_insensitive_matching(self, make_scd, monkeypatch):
        """Import paths are matched case-insensitively."""
        from scripts.build_content_release import verify_scd_imports

        scd = make_scd(
            {
                "lua/ui/uiutil.lua": "-- module",
                "lua/test.lua": "local UIUtil = import('/lua/UI/UIUtil.lua')",
            }
        )
        monkeypatch.setattr("scripts.build_content_release.config.SCFA_STEAM", scd.parent / "nope")

        result = verify_scd_imports(scd)
        assert result == []

    def test_multiple_imports_in_one_file(self, make_scd, monkeypatch):
        """Multiple imports in one file are all checked."""
        from scripts.build_content_release import verify_scd_imports

        scd = make_scd(
            {
                "lua/test.lua": (
                    "local A = import('/lua/a.lua')\n"
                    "local B = import('/lua/b.lua')\n"
                    "local C = import('/lua/c.lua')\n"
                ),
                "lua/a.lua": "-- a",
                # b.lua missing
                # c.lua missing
            }
        )
        monkeypatch.setattr("scripts.build_content_release.config.SCFA_STEAM", scd.parent / "nope")

        result = verify_scd_imports(scd)
        assert "/lua/b.lua" in result
        assert "/lua/c.lua" in result
        assert "/lua/a.lua" not in result
