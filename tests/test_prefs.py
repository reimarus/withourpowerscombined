"""Tests for WOPC preferences management."""

from unittest.mock import patch

from launcher import prefs


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
