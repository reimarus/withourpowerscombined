"""Tests for launcher.init_generator."""

from pathlib import Path
from unittest.mock import patch

import pytest

from launcher import init_generator


@pytest.fixture()
def gamedata_dir(tmp_path: Path) -> Path:
    """Create a fake WOPC gamedata directory with SCD files."""
    gd = tmp_path / "gamedata"
    gd.mkdir()
    # Core SCDs
    (gd / "lua.scd").write_bytes(b"x" * 100)
    (gd / "loc_US.scd").write_bytes(b"x" * 50)
    # Fixed-position SCD (mounted explicitly, not toggleable)
    (gd / "faf_ui.scd").write_bytes(b"x" * 40)
    # Toggleable content packs
    (gd / "brewlan.scd").write_bytes(b"x" * 2000)
    (gd / "blackops.scd").write_bytes(b"x" * 1500)
    (gd / "TotalMayhem.scd").write_bytes(b"x" * 1000)
    return gd


@pytest.fixture()
def prefs_file(tmp_path: Path) -> Path:
    """Return a path for the prefs INI file."""
    return tmp_path / "wopc_prefs.ini"


class TestGetToggleableScds:
    """Tests for get_toggleable_scds()."""

    def test_excludes_fixed_position_scds(self, gamedata_dir: Path) -> None:
        with patch("launcher.init_generator.config") as mock_config:
            mock_config.WOPC_GAMEDATA = gamedata_dir
            result = init_generator.get_toggleable_scds()
        # Fixed-position SCD should not appear (needs special mount order)
        assert "faf_ui.scd" not in result
        # LOUD SCDs (lua.scd, loc_US.scd) are now toggleable content packs
        assert "lua.scd" in result
        assert "loc_US.scd" in result
        # Other toggleable content packs
        assert "brewlan.scd" in result
        assert "blackops.scd" in result
        assert "TotalMayhem.scd" in result

    def test_returns_empty_if_no_dir(self, tmp_path: Path) -> None:
        with patch("launcher.init_generator.config") as mock_config:
            mock_config.WOPC_GAMEDATA = tmp_path / "nonexistent"
            result = init_generator.get_toggleable_scds()
        assert result == []

    def test_sorted_alphabetically(self, gamedata_dir: Path) -> None:
        with patch("launcher.init_generator.config") as mock_config:
            mock_config.WOPC_GAMEDATA = gamedata_dir
            result = init_generator.get_toggleable_scds()
        assert result == sorted(result)


class TestPackState:
    """Tests for set_pack_state() and get_enabled_packs()."""

    def test_faf_only_default(self, gamedata_dir: Path) -> None:
        """No ContentPacks section → empty list (FAF-only mode)."""
        with (
            patch("launcher.init_generator.config") as mock_config,
            patch("launcher.init_generator.prefs") as mock_prefs,
        ):
            mock_config.WOPC_GAMEDATA = gamedata_dir

            import configparser

            parser = configparser.ConfigParser()
            mock_prefs.load_prefs.return_value = parser

            result = init_generator.get_enabled_packs()

        assert result == []

    def test_toggle_pack_off(self, gamedata_dir: Path, prefs_file: Path) -> None:
        with (
            patch("launcher.init_generator.config") as mock_config,
            patch("launcher.init_generator.prefs") as mock_prefs,
        ):
            mock_config.WOPC_GAMEDATA = gamedata_dir

            import configparser

            parser = configparser.ConfigParser()
            parser.add_section("ContentPacks")
            parser.set("ContentPacks", "brewlan.scd", "False")
            mock_prefs.load_prefs.return_value = parser

            result = init_generator.get_enabled_packs()

        assert "brewlan.scd" not in result
        assert "blackops.scd" in result  # defaults to True

    def test_set_pack_state_calls_save(self) -> None:
        with patch("launcher.init_generator.prefs") as mock_prefs:
            import configparser

            parser = configparser.ConfigParser()
            mock_prefs.load_prefs.return_value = parser

            init_generator.set_pack_state("brewlan.scd", False)

            mock_prefs.save_prefs.assert_called_once_with(parser)
            assert parser.get("ContentPacks", "brewlan.scd") == "False"


class TestGenerateInitLua:
    """Tests for generate_init_lua()."""

    def test_generates_faf_only_by_default(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """With no ContentPacks section, no gamedata SCDs are mounted (FAF-only mode)."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        with (
            patch("launcher.init_generator.config") as mock_config,
            patch("launcher.init_generator.prefs") as mock_prefs,
        ):
            mock_config.WOPC_GAMEDATA = gamedata_dir
            mock_config.WOPC_BIN = bin_dir

            import configparser

            parser = configparser.ConfigParser()
            mock_prefs.load_prefs.return_value = parser

            result = init_generator.generate_init_lua()

        assert result.exists()
        content = result.read_text()
        assert "AUTO-GENERATED" in content
        # No LOUD content packs mounted in FAF-only mode (CORE_SCDS is empty)
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\lua.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\loc_US.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\brewlan.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\blackops.scd', '/')" not in content
        # Vanilla SCFA gameplay assets ARE mounted from SCFARoot
        assert "mount_dir(SCFARoot .. '\\\\gamedata\\\\units.scd', '/')" in content
        assert "mount_dir(SCFARoot .. '\\\\gamedata\\\\loc_us.scd', '/')" in content
        assert "mount_dir(SCFARoot .. '\\\\gamedata\\\\objects.scd', '/')" in content
        assert "mount_dir(SCFARoot .. '\\\\gamedata\\\\mods.scd', '/')" in content
        # faf_ui still present via fixed mount (wopc_patches consolidated into it)
        assert "mount_dir(faf_ui, '/')" in content

    def test_generates_with_enabled_packs(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """With ContentPacks section, enabled SCDs are mounted."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        with (
            patch("launcher.init_generator.config") as mock_config,
            patch("launcher.init_generator.prefs") as mock_prefs,
        ):
            mock_config.WOPC_GAMEDATA = gamedata_dir
            mock_config.WOPC_BIN = bin_dir

            import configparser

            parser = configparser.ConfigParser()
            parser.add_section("ContentPacks")
            # All default to True when section exists
            mock_prefs.load_prefs.return_value = parser

            result = init_generator.generate_init_lua()

        content = result.read_text()
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\brewlan.scd', '/')" in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\lua.scd', '/')" in content

    def test_omits_disabled_packs(self, gamedata_dir: Path, tmp_path: Path) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        with (
            patch("launcher.init_generator.config") as mock_config,
            patch("launcher.init_generator.prefs") as mock_prefs,
        ):
            mock_config.WOPC_GAMEDATA = gamedata_dir
            mock_config.WOPC_BIN = bin_dir

            import configparser

            parser = configparser.ConfigParser()
            parser.add_section("ContentPacks")
            parser.set("ContentPacks", "brewlan.scd", "False")
            mock_prefs.load_prefs.return_value = parser

            result = init_generator.generate_init_lua()

        content = result.read_text()
        # Check the mount_dir line, not just the bare string (it appears in comments)
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\brewlan.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\blackops.scd', '/')" in content

    def test_faf_ui_mounts_before_vanilla_scfa(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """faf_ui.scd must mount BEFORE vanilla (first-added = highest VFS priority)."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        with (
            patch("launcher.init_generator.config") as mock_config,
            patch("launcher.init_generator.prefs") as mock_prefs,
        ):
            mock_config.WOPC_GAMEDATA = gamedata_dir
            mock_config.WOPC_BIN = bin_dir

            import configparser

            parser = configparser.ConfigParser()
            mock_prefs.load_prefs.return_value = parser

            result = init_generator.generate_init_lua()

        content = result.read_text()
        # faf_ui should NOT be in the early gamedata block
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\faf_ui.scd', '/')" not in content
        # faf_ui (consolidated with WOPC patches) must appear BEFORE vanilla SCFA mounts
        # (first-added = highest priority in SCFA's VFS)
        vanilla_pos = content.index("mount_dir(SCFARoot")
        faf_ui_mount_pos = content.index("mount_dir(faf_ui, '/')")
        assert faf_ui_mount_pos < vanilla_pos

    def test_wopc_patches_not_separately_mounted(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """wopc_patches.scd is consolidated into faf_ui.scd — no separate mount."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        with (
            patch("launcher.init_generator.config") as mock_config,
            patch("launcher.init_generator.prefs") as mock_prefs,
        ):
            mock_config.WOPC_GAMEDATA = gamedata_dir
            mock_config.WOPC_BIN = bin_dir

            import configparser

            parser = configparser.ConfigParser()
            mock_prefs.load_prefs.return_value = parser

            result = init_generator.generate_init_lua()

        content = result.read_text()
        # wopc_patches should not appear anywhere — consolidated into faf_ui.scd
        assert "wopc_patches" not in content

    def test_uses_mount_mods_for_usermods(self, gamedata_dir: Path, tmp_path: Path) -> None:
        """User mods should use engine mount_mods(), not individual mount_dir() calls."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        with (
            patch("launcher.init_generator.config") as mock_config,
            patch("launcher.init_generator.prefs") as mock_prefs,
        ):
            mock_config.WOPC_GAMEDATA = gamedata_dir
            mock_config.WOPC_BIN = bin_dir

            import configparser

            parser = configparser.ConfigParser()
            mock_prefs.load_prefs.return_value = parser

            result = init_generator.generate_init_lua()

        content = result.read_text()
        assert "mount_mods(WOPCRoot .. '\\\\usermods')" in content
