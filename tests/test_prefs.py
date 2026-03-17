"""Tests for WOPC preferences management."""

from unittest.mock import patch

from launcher import config, prefs


class TestLoadPrefs:
    """Test reading the INI configuration file."""

    def test_creates_defaults_if_missing(self, tmp_path):
        """Creates wopc_prefs.ini with defaults if none exists."""
        prefs_file = tmp_path / "wopc_prefs.ini"

        with patch.object(prefs, "PREFS_FILE", prefs_file):
            parser = prefs.load_prefs()

        assert prefs_file.exists()
        assert parser.has_section("Game")
        assert parser.has_section("Mods")
        assert parser.has_section("Display")
        assert parser.get("Display", "x") == "1920"

    def test_loads_existing_prefs(self, tmp_path):
        """Reads values from existing INI file."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        prefs_file.write_text("[Game]\nactive_map = SCMP_001\n[Mods]\nbrewlan = True")

        with patch.object(prefs, "PREFS_FILE", prefs_file):
            parser = prefs.load_prefs()

        assert parser.get("Game", "active_map", fallback="") == "SCMP_001"
        assert parser.getboolean("Mods", "brewlan", fallback=False) is True


class TestSetPrefs:
    """Test writing to the INI configuration file."""

    def test_set_active_map(self, tmp_path):
        """Updates the selected multiplayer map."""
        prefs_file = tmp_path / "wopc_prefs.ini"

        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_active_map("SCMP_009")

        # Verify INI was physically written
        assert "SCMP_009" in prefs_file.read_text()

        # Verify API can read it back
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            assert prefs.get_active_map() == "SCMP_009"

    def test_set_mod_state(self, tmp_path):
        """Toggles a user mod as enabled/disabled."""
        prefs_file = tmp_path / "wopc_prefs.ini"

        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_mod_state("BlackOpsUnleashed", True)
            prefs.set_mod_state("BrewLAN", False)

        enabled = prefs_file.read_text().lower()
        assert "blackopsunleashed = true" in enabled
        assert "brewlan = false" in enabled

        with patch.object(prefs, "PREFS_FILE", prefs_file):
            mods = prefs.get_enabled_mods()
            # The mod key is forced lowercase by configparser when returning
            assert "blackopsunleashed" in mods
            assert "brewlan" not in mods


class TestServerModUids:
    """Test scanning server-level mod UIDs from WOPC/mods/."""

    def test_returns_uids_from_mod_info(self, tmp_path):
        """Extracts UIDs from mod_info.lua files."""
        mods_dir = tmp_path / "mods"
        mod_a = mods_dir / "ModA"
        mod_a.mkdir(parents=True)
        (mod_a / "mod_info.lua").write_text('name = "Mod A"\nuid = "aaaa-1111"\nenabled = true\n')
        mod_b = mods_dir / "ModB"
        mod_b.mkdir()
        (mod_b / "mod_info.lua").write_text("name = 'Mod B'\nuid = 'bbbb-2222'\n")

        with patch.object(config, "WOPC_MODS", mods_dir):
            uids = prefs.get_server_mod_uids()

        assert uids == ["aaaa-1111", "bbbb-2222"]

    def test_returns_empty_when_no_mods_dir(self, tmp_path):
        """Returns empty list when WOPC/mods/ doesn't exist."""
        with patch.object(config, "WOPC_MODS", tmp_path / "nonexistent"):
            uids = prefs.get_server_mod_uids()

        assert uids == []

    def test_skips_dirs_without_mod_info(self, tmp_path):
        """Ignores directories without mod_info.lua."""
        mods_dir = tmp_path / "mods"
        (mods_dir / "NoModInfo").mkdir(parents=True)
        (mods_dir / "NoModInfo" / "readme.txt").write_text("hi")

        with patch.object(config, "WOPC_MODS", mods_dir):
            uids = prefs.get_server_mod_uids()

        assert uids == []
