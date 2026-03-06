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
    (gd / "wopc_patches.scd").write_bytes(b"x" * 30)
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

    def test_excludes_core_scds(self, gamedata_dir: Path) -> None:
        with patch("launcher.init_generator.config") as mock_config:
            mock_config.WOPC_GAMEDATA = gamedata_dir
            result = init_generator.get_toggleable_scds()
        # Core SCDs should not appear
        assert "lua.scd" not in result
        assert "wopc_patches.scd" not in result
        # Toggleable ones should
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

    def test_generates_file(self, gamedata_dir: Path, tmp_path: Path) -> None:
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
            mock_prefs.get_enabled_mods.return_value = []

            result = init_generator.generate_init_lua()

        assert result.exists()
        content = result.read_text()
        assert "AUTO-GENERATED" in content
        assert "brewlan.scd" in content
        assert "lua.scd" in content

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
            mock_prefs.get_enabled_mods.return_value = []

            result = init_generator.generate_init_lua()

        content = result.read_text()
        # Check the mount_dir line, not just the bare string (it appears in comments)
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\brewlan.scd', '/')" not in content
        assert "mount_dir(WOPCRoot .. '\\\\gamedata\\\\blackops.scd', '/')" in content

    def test_includes_enabled_user_mods(self, gamedata_dir: Path, tmp_path: Path) -> None:
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
            mock_prefs.get_enabled_mods.return_value = ["BetterPathing"]

            result = init_generator.generate_init_lua()

        content = result.read_text()
        assert "BetterPathing" in content
