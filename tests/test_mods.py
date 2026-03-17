"""Tests for launcher.mods — consolidated mod system."""

import configparser
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from launcher import config, mods, prefs

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mod_info_text() -> str:
    """Typical mod_info.lua content."""
    return 'name = "Test Mod"\nuid = "aaaa-1111-bbbb-2222"\nenabled = true\n'


@pytest.fixture()
def mods_dir(tmp_path: Path) -> Path:
    """Create a fake WOPC/mods/ with two server mods."""
    d = tmp_path / "mods"
    mod_a = d / "ModA"
    mod_a.mkdir(parents=True)
    (mod_a / "mod_info.lua").write_text('name = "Mod A"\nuid = "aaaa-1111"\nenabled = true\n')
    mod_b = d / "ModB"
    mod_b.mkdir()
    (mod_b / "mod_info.lua").write_text("name = 'Mod B'\nuid = 'bbbb-2222'\n")
    return d


@pytest.fixture()
def usermods_dir(tmp_path: Path) -> Path:
    """Create a fake WOPC/usermods/ with one user mod."""
    d = tmp_path / "usermods"
    mod = d / "BrewLAN"
    mod.mkdir(parents=True)
    (mod / "mod_info.lua").write_text('name = "BrewLAN"\nuid = "brew-lan-uid-1234"\n')
    return d


@pytest.fixture()
def prefs_file(tmp_path: Path) -> Path:
    """Return a path for a temporary prefs INI file."""
    return tmp_path / "wopc_prefs.ini"


@pytest.fixture()
def gamedata_dir(tmp_path: Path) -> Path:
    """Create a fake WOPC gamedata directory with SCD files."""
    gd = tmp_path / "gamedata"
    gd.mkdir()
    (gd / "lua.scd").write_bytes(b"x" * 100)
    (gd / "loc_US.scd").write_bytes(b"x" * 50)
    (gd / "faf_ui.scd").write_bytes(b"x" * 40)
    (gd / "brewlan.scd").write_bytes(b"x" * 2000)
    (gd / "blackops.scd").write_bytes(b"x" * 1500)
    (gd / "TotalMayhem.scd").write_bytes(b"x" * 1000)
    return gd


# ---------------------------------------------------------------------------
# TestParseModInfo
# ---------------------------------------------------------------------------


class TestParseModInfo:
    """Tests for parse_mod_info()."""

    def test_parse_valid_double_quotes(self, tmp_path: Path) -> None:
        p = tmp_path / "mod_info.lua"
        p.write_text('name = "My Mod"\nuid = "xxxx-yyyy"\n')
        info = mods.parse_mod_info(p)
        assert info is not None
        assert info.uid == "xxxx-yyyy"
        assert info.name == "My Mod"

    def test_parse_valid_single_quotes(self, tmp_path: Path) -> None:
        p = tmp_path / "mod_info.lua"
        p.write_text("name = 'Cool Mod'\nuid = 'abcd-1234'\n")
        info = mods.parse_mod_info(p)
        assert info is not None
        assert info.uid == "abcd-1234"
        assert info.name == "Cool Mod"

    def test_parse_missing_uid(self, tmp_path: Path) -> None:
        p = tmp_path / "mod_info.lua"
        p.write_text('name = "No UID Mod"\nenabled = true\n')
        assert mods.parse_mod_info(p) is None

    def test_parse_missing_file(self, tmp_path: Path) -> None:
        assert mods.parse_mod_info(tmp_path / "nonexistent.lua") is None

    def test_parse_name_fallback_to_folder(self, tmp_path: Path) -> None:
        """If name field is missing, use parent folder name."""
        d = tmp_path / "FolderName"
        d.mkdir()
        p = d / "mod_info.lua"
        p.write_text('uid = "aaaa-bbbb"\n')
        info = mods.parse_mod_info(p)
        assert info is not None
        assert info.name == "FolderName"


# ---------------------------------------------------------------------------
# TestDiscovery
# ---------------------------------------------------------------------------


class TestDiscovery:
    """Tests for discover_*() functions."""

    def test_discover_server_mods(self, mods_dir: Path) -> None:
        with patch.object(config, "WOPC_MODS", mods_dir):
            result = mods.discover_server_mods()
        assert len(result) == 2
        assert result[0].uid == "aaaa-1111"
        assert result[0].location == "server"
        assert result[1].uid == "bbbb-2222"

    def test_discover_server_mods_empty(self, tmp_path: Path) -> None:
        with patch.object(config, "WOPC_MODS", tmp_path / "nonexistent"):
            result = mods.discover_server_mods()
        assert result == []

    def test_discover_server_mods_skips_no_uid(self, tmp_path: Path) -> None:
        d = tmp_path / "mods"
        (d / "NoUid").mkdir(parents=True)
        (d / "NoUid" / "mod_info.lua").write_text('name = "broken"\n')
        with patch.object(config, "WOPC_MODS", d):
            result = mods.discover_server_mods()
        assert result == []

    def test_discover_user_mods(self, usermods_dir: Path) -> None:
        with patch.object(config, "WOPC_USERMODS", usermods_dir):
            result = mods.discover_user_mods()
        assert len(result) == 1
        assert result[0].uid == "brew-lan-uid-1234"
        assert result[0].location == "user"

    def test_discover_all_mods(self, mods_dir: Path, usermods_dir: Path) -> None:
        with (
            patch.object(config, "WOPC_MODS", mods_dir),
            patch.object(config, "WOPC_USERMODS", usermods_dir),
        ):
            result = mods.discover_all_mods()
        assert len(result) == 3


# ---------------------------------------------------------------------------
# TestContentPacks
# ---------------------------------------------------------------------------


class TestContentPacks:
    """Tests for content pack management (moved from init_generator)."""

    def test_get_toggleable_scds_excludes_fixed(self, gamedata_dir: Path) -> None:
        with patch.object(config, "WOPC_GAMEDATA", gamedata_dir):
            result = mods.get_toggleable_scds()
        assert "faf_ui.scd" not in result
        assert "lua.scd" in result
        assert "brewlan.scd" in result

    def test_returns_empty_if_no_dir(self, tmp_path: Path) -> None:
        with patch.object(config, "WOPC_GAMEDATA", tmp_path / "nonexistent"):
            result = mods.get_toggleable_scds()
        assert result == []

    def test_sorted_alphabetically(self, gamedata_dir: Path) -> None:
        with patch.object(config, "WOPC_GAMEDATA", gamedata_dir):
            result = mods.get_toggleable_scds()
        assert result == sorted(result)

    def test_faf_only_default(self, gamedata_dir: Path) -> None:
        """No ContentPacks section → empty list (FAF-only mode)."""
        parser = configparser.ConfigParser()
        with (
            patch.object(config, "WOPC_GAMEDATA", gamedata_dir),
            patch.object(prefs, "load_prefs", return_value=parser),
        ):
            result = mods.get_enabled_packs()
        assert result == []

    def test_toggle_pack_off(self, gamedata_dir: Path) -> None:
        parser = configparser.ConfigParser()
        parser.add_section("ContentPacks")
        parser.set("ContentPacks", "brewlan.scd", "False")
        with (
            patch.object(config, "WOPC_GAMEDATA", gamedata_dir),
            patch.object(prefs, "load_prefs", return_value=parser),
        ):
            result = mods.get_enabled_packs()
        assert "brewlan.scd" not in result
        assert "blackops.scd" in result

    def test_set_pack_state_calls_save(self) -> None:
        parser = configparser.ConfigParser()
        with (
            patch.object(prefs, "load_prefs", return_value=parser),
            patch.object(prefs, "save_prefs") as mock_save,
        ):
            mods.set_pack_state("brewlan.scd", False)
        mock_save.assert_called_once_with(parser)
        assert parser.get("ContentPacks", "brewlan.scd") == "False"


# ---------------------------------------------------------------------------
# TestExtraction
# ---------------------------------------------------------------------------


class TestExtraction:
    """Tests for extract_mods_from_scd()."""

    def test_extract_mods(self, tmp_path: Path) -> None:
        """Extracts mods/ subtree from an SCD."""
        scd = tmp_path / "test.scd"
        wopc_mods = tmp_path / "mods"

        with zipfile.ZipFile(scd, "w") as zf:
            zf.writestr("mods/TestMod/mod_info.lua", 'uid = "test-uid"\n')
            zf.writestr("mods/TestMod/units/unit01.bp", "blueprint data")

        with patch.object(config, "WOPC_MODS", wopc_mods):
            result = mods.extract_mods_from_scd(scd)

        assert result == ["TestMod"]
        assert (wopc_mods / "TestMod" / "mod_info.lua").exists()
        assert (wopc_mods / "TestMod" / "units" / "unit01.bp").exists()

    def test_extract_skips_existing(self, tmp_path: Path) -> None:
        """Does not overwrite files that already exist."""
        scd = tmp_path / "test.scd"
        wopc_mods = tmp_path / "mods"
        (wopc_mods / "TestMod").mkdir(parents=True)
        existing = wopc_mods / "TestMod" / "mod_info.lua"
        existing.write_text("original content")

        with zipfile.ZipFile(scd, "w") as zf:
            zf.writestr("mods/TestMod/mod_info.lua", "new content")

        with patch.object(config, "WOPC_MODS", wopc_mods):
            mods.extract_mods_from_scd(scd)

        assert existing.read_text() == "original content"

    def test_extract_bad_zip(self, tmp_path: Path) -> None:
        """Handles corrupt SCD gracefully."""
        scd = tmp_path / "bad.scd"
        scd.write_bytes(b"not a zip")
        wopc_mods = tmp_path / "mods"

        with patch.object(config, "WOPC_MODS", wopc_mods):
            result = mods.extract_mods_from_scd(scd)
        assert result == []

    def test_extract_no_mods_subtree(self, tmp_path: Path) -> None:
        """Returns empty when SCD has no mods/ subtree."""
        scd = tmp_path / "nomods.scd"
        wopc_mods = tmp_path / "mods"

        with zipfile.ZipFile(scd, "w") as zf:
            zf.writestr("units/unit01.bp", "data")

        with patch.object(config, "WOPC_MODS", wopc_mods):
            result = mods.extract_mods_from_scd(scd)
        assert result == []


# ---------------------------------------------------------------------------
# TestStateManagement
# ---------------------------------------------------------------------------


class TestStateManagement:
    """Tests for UID-based state management."""

    def test_get_enabled_user_mod_uids(self, prefs_file: Path) -> None:
        prefs_file.write_text("[Mods]\naaaa-1111 = True\nbbbb-2222 = False\n")
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            result = mods.get_enabled_user_mod_uids()
        assert "aaaa-1111" in result
        assert "bbbb-2222" not in result

    def test_set_user_mod_enabled(self, prefs_file: Path) -> None:
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            mods.set_user_mod_enabled("xxxx-yyyy", True)
        content = prefs_file.read_text()
        assert "xxxx-yyyy = True" in content

    def test_get_active_mod_uids(self, mods_dir: Path, prefs_file: Path) -> None:
        """Combines server UIDs + enabled user UIDs."""
        prefs_file.write_text("[Mods]\nuser-mod-uid = True\n")
        with (
            patch.object(config, "WOPC_MODS", mods_dir),
            patch.object(config, "WOPC_USERMODS", mods_dir.parent / "nonexistent"),
            patch.object(prefs, "PREFS_FILE", prefs_file),
        ):
            result = mods.get_active_mod_uids()
        # 2 server mods + 1 user mod
        assert "aaaa-1111" in result
        assert "bbbb-2222" in result
        assert "user-mod-uid" in result

    def test_get_active_mod_uids_empty(self, tmp_path: Path, prefs_file: Path) -> None:
        with (
            patch.object(config, "WOPC_MODS", tmp_path / "nomods"),
            patch.object(config, "WOPC_USERMODS", tmp_path / "nousermods"),
            patch.object(prefs, "PREFS_FILE", prefs_file),
        ):
            result = mods.get_active_mod_uids()
        assert result == []


# ---------------------------------------------------------------------------
# TestMigration
# ---------------------------------------------------------------------------


class TestMigration:
    """Tests for migrate_prefs_folder_to_uid()."""

    def test_migrate_converts_folder_to_uid(self, usermods_dir: Path, prefs_file: Path) -> None:
        """Rewrites [Mods] keys from folder names to UIDs."""
        prefs_file.write_text("[Mods]\nbrewlan = True\n")
        with (
            patch.object(config, "WOPC_USERMODS", usermods_dir),
            patch.object(prefs, "PREFS_FILE", prefs_file),
        ):
            mods.migrate_prefs_folder_to_uid()

        content = prefs_file.read_text()
        assert "brew-lan-uid-1234" in content
        assert "brewlan" not in content.split("[ModsMigrated]")[0].lower().split("mods]")[1]

    def test_migrate_skips_if_already_done(self, prefs_file: Path) -> None:
        prefs_file.write_text("[Mods]\nsome-uid = True\n[ModsMigrated]\nversion = 1\n")
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            mods.migrate_prefs_folder_to_uid()
        # Should not modify the file
        content = prefs_file.read_text()
        assert "some-uid" in content

    def test_migrate_drops_unknown_folders(self, usermods_dir: Path, prefs_file: Path) -> None:
        """Drops entries for mods that no longer exist on disk."""
        prefs_file.write_text("[Mods]\nbrewlan = True\ndeleted_mod = True\n")
        with (
            patch.object(config, "WOPC_USERMODS", usermods_dir),
            patch.object(prefs, "PREFS_FILE", prefs_file),
        ):
            mods.migrate_prefs_folder_to_uid()

        content = prefs_file.read_text()
        assert "deleted_mod" not in content

    def test_migrate_no_mods_section(self, prefs_file: Path) -> None:
        """No-op when [Mods] section doesn't exist."""
        prefs_file.write_text("[Game]\nactive_map = SCMP_001\n")
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            mods.migrate_prefs_folder_to_uid()
        content = prefs_file.read_text()
        assert "ModsMigrated" in content

    def test_migrate_idempotent(self, usermods_dir: Path, prefs_file: Path) -> None:
        """Running twice produces the same result."""
        prefs_file.write_text("[Mods]\nbrewlan = True\n")
        with (
            patch.object(config, "WOPC_USERMODS", usermods_dir),
            patch.object(prefs, "PREFS_FILE", prefs_file),
        ):
            mods.migrate_prefs_folder_to_uid()
            content_after_first = prefs_file.read_text()
            mods.migrate_prefs_folder_to_uid()
            content_after_second = prefs_file.read_text()
        assert content_after_first == content_after_second
