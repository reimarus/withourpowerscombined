"""Tests for launcher.init_generator.

Content pack state management tests have moved to test_mods.py.
This file tests only the Lua template generation (generate_init_lua).
"""

import configparser
from pathlib import Path
from unittest.mock import patch

import pytest

from launcher import config, init_generator, prefs


@pytest.fixture()
def gamedata_dir(tmp_path: Path) -> Path:
    """Create a fake WOPC gamedata directory with SCD files."""
    gd = tmp_path / "gamedata"
    gd.mkdir()
    # Core SCDs
    (gd / "lua.scd").write_bytes(b"x" * 100)
    (gd / "loc_US.scd").write_bytes(b"x" * 50)
    # Fixed-position SCD (mounted explicitly, not toggleable)
    (gd / "wopc_core.scd").write_bytes(b"x" * 40)
    # Toggleable content packs
    (gd / "brewlan.scd").write_bytes(b"x" * 2000)
    (gd / "blackops.scd").write_bytes(b"x" * 1500)
    (gd / "TotalMayhem.scd").write_bytes(b"x" * 1000)
    return gd


class TestDelegation:
    """Verify init_generator delegates to mods module."""

    def test_get_toggleable_scds_delegates(self, gamedata_dir: Path) -> None:
        with patch.object(config, "WOPC_GAMEDATA", gamedata_dir):
            result = init_generator.get_toggleable_scds()
        assert "wopc_core.scd" not in result
        assert "lua.scd" in result
        assert "brewlan.scd" in result

    def test_set_pack_state_delegates(self) -> None:
        parser = configparser.ConfigParser()
        with (
            patch.object(prefs, "load_prefs", return_value=parser),
            patch.object(prefs, "save_prefs") as mock_save,
        ):
            init_generator.set_pack_state("brewlan.scd", False)
        mock_save.assert_called_once_with(parser)
        assert parser.get("ContentPacks", "brewlan.scd") == "False"


class TestGenerateInitLua:
    """Tests for generate_init_lua()."""

    def test_generates_faf_only_by_default(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """With no ContentPacks section, no gamedata SCDs are mounted."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        parser = configparser.ConfigParser()
        with (
            patch.object(config, "WOPC_GAMEDATA", gamedata_dir),
            patch.object(config, "WOPC_BIN", bin_dir),
            patch.object(prefs, "load_prefs", return_value=parser),
        ):
            result = init_generator.generate_init_lua()

        assert result.exists()
        content = result.read_text()
        assert "AUTO-GENERATED" in content
        # No content packs mounted when none are enabled (CORE_SCDS is empty)
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\lua.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\loc_US.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\brewlan.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\blackops.scd', '/')" not in content
        # Vanilla SCFA gameplay assets ARE mounted from SCFARoot
        assert "mount_dir(SCFARoot .. '\\\\gamedata\\\\units.scd', '/')" in content
        assert "mount_dir(SCFARoot .. '\\\\gamedata\\\\loc_us.scd', '/')" in content
        assert "mount_dir(SCFARoot .. '\\\\gamedata\\\\objects.scd', '/')" in content
        assert "mount_dir(SCFARoot .. '\\\\gamedata\\\\mods.scd', '/')" in content
        # wopc_core still present via fixed mount (patches consolidated into it)
        assert "mount_dir(wopc_core, '/')" in content

    def test_generates_with_enabled_packs(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """With ContentPacks section, enabled SCDs are mounted."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        parser = configparser.ConfigParser()
        parser.add_section("ContentPacks")
        # All default to True when section exists
        with (
            patch.object(config, "WOPC_GAMEDATA", gamedata_dir),
            patch.object(config, "WOPC_BIN", bin_dir),
            patch.object(prefs, "load_prefs", return_value=parser),
        ):
            result = init_generator.generate_init_lua()

        content = result.read_text()
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\brewlan.scd', '/')" in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\lua.scd', '/')" in content

    def test_omits_disabled_packs(self, gamedata_dir: Path, tmp_path: Path) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        parser = configparser.ConfigParser()
        parser.add_section("ContentPacks")
        parser.set("ContentPacks", "brewlan.scd", "False")
        with (
            patch.object(config, "WOPC_GAMEDATA", gamedata_dir),
            patch.object(config, "WOPC_BIN", bin_dir),
            patch.object(prefs, "load_prefs", return_value=parser),
        ):
            result = init_generator.generate_init_lua()

        content = result.read_text()
        # Check the mount_dir line, not just the bare string (it appears in comments)
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\brewlan.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\blackops.scd', '/')" in content

    def test_wopc_core_mounts_before_vanilla_scfa(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """wopc_core.scd must mount BEFORE vanilla (first-added = highest VFS priority)."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        parser = configparser.ConfigParser()
        with (
            patch.object(config, "WOPC_GAMEDATA", gamedata_dir),
            patch.object(config, "WOPC_BIN", bin_dir),
            patch.object(prefs, "load_prefs", return_value=parser),
        ):
            result = init_generator.generate_init_lua()

        content = result.read_text()
        # wopc_core should NOT be in the early gamedata block
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\wopc_core.scd', '/')" not in content
        # wopc_core must appear BEFORE vanilla SCFA mounts
        # (first-added = highest priority in SCFA's VFS)
        vanilla_pos = content.index("mount_dir(SCFARoot")
        wopc_core_mount_pos = content.index("mount_dir(wopc_core, '/')")
        assert wopc_core_mount_pos < vanilla_pos

    def test_wopc_patches_not_separately_mounted(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """wopc_patches.scd is consolidated into wopc_core.scd — no separate mount."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        parser = configparser.ConfigParser()
        with (
            patch.object(config, "WOPC_GAMEDATA", gamedata_dir),
            patch.object(config, "WOPC_BIN", bin_dir),
            patch.object(prefs, "load_prefs", return_value=parser),
        ):
            result = init_generator.generate_init_lua()

        content = result.read_text()
        # wopc_patches should not appear anywhere — consolidated into wopc_core.scd
        assert "wopc_patches" not in content

    def test_uses_mount_mods_for_usermods(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """User mods should use engine mount_mods(), not individual mount_dir() calls."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        parser = configparser.ConfigParser()
        with (
            patch.object(config, "WOPC_GAMEDATA", gamedata_dir),
            patch.object(config, "WOPC_BIN", bin_dir),
            patch.object(prefs, "load_prefs", return_value=parser),
        ):
            result = init_generator.generate_init_lua()

        content = result.read_text()
        assert "mount_mods(WOPCRoot .. '\\\\usermods')" in content
