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


class TestLaunchModePrefs:
    """Test launch_mode, host_port, and join_address preferences."""

    def test_launch_mode_default_solo(self, tmp_path):
        """Default launch mode is 'solo'."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            assert prefs.get_launch_mode() == "solo"

    def test_launch_mode_roundtrip(self, tmp_path):
        """Setting and reading launch mode works for all valid values."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        for mode in ("solo", "multiplayer"):
            with patch.object(prefs, "PREFS_FILE", prefs_file):
                prefs.set_launch_mode(mode)
                assert prefs.get_launch_mode() == mode

    def test_legacy_host_join_falls_back_to_solo(self, tmp_path):
        """Legacy 'host'/'join' values fall back to 'solo'."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_launch_mode("host")
            assert prefs.get_launch_mode() == "solo"
            prefs.set_launch_mode("join")
            assert prefs.get_launch_mode() == "solo"

    def test_invalid_launch_mode_falls_back_to_solo(self, tmp_path):
        """Invalid launch mode falls back to 'solo'."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_launch_mode("invalid")
            assert prefs.get_launch_mode() == "solo"

    def test_host_port_roundtrip(self, tmp_path):
        """Setting and reading host port works."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_host_port("16000")
            assert prefs.get_host_port() == "16000"

    def test_host_port_default(self, tmp_path):
        """Default host port is '15000'."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            assert prefs.get_host_port() == "15000"

    def test_join_address_roundtrip(self, tmp_path):
        """Setting and reading join address works."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_join_address("192.168.1.50:15000")
            assert prefs.get_join_address() == "192.168.1.50:15000"

    def test_join_address_default_empty(self, tmp_path):
        """Default join address is empty string."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            assert prefs.get_join_address() == ""

    def test_player_name_roundtrip(self, tmp_path):
        """Setting and reading player name works."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_player_name("TestPlayer")
            assert prefs.get_player_name() == "TestPlayer"

    def test_player_name_blank_defaults(self, tmp_path):
        """Setting blank player name falls back to 'Player'."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_player_name("  ")
            assert prefs.get_player_name() == "Player"


class TestExpectedHumansPrefs:
    """Test expected_humans preference for multiplayer hosting."""

    def test_default_is_one(self, tmp_path):
        """Default expected humans is 1 (solo mode)."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            assert prefs.get_expected_humans() == 1

    def test_roundtrip(self, tmp_path):
        """Setting and reading expected humans works."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_expected_humans(4)
            assert prefs.get_expected_humans() == 4

    def test_clamped_low(self, tmp_path):
        """Values below 1 are clamped to 1."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_expected_humans(0)
            assert prefs.get_expected_humans() == 1

    def test_clamped_high(self, tmp_path):
        """Values above 8 are clamped to 8."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            prefs.set_expected_humans(99)
            assert prefs.get_expected_humans() == 8


class TestWindowSizePrefs:
    """Test window size persistence in prefs."""

    def test_default_window_size(self, tmp_path):
        """Default window size is 1024x768."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            parser = prefs.load_prefs()
            assert parser.get("Window", "width") == "1024"
            assert parser.get("Window", "height") == "768"

    def test_window_section_created_on_load(self, tmp_path):
        """Window section is created with defaults if missing."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        prefs_file.write_text("[Game]\nactive_map = test\n")
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            parser = prefs.load_prefs()
            assert parser.has_section("Window")
            assert parser.get("Window", "width") == "1024"

    def test_window_size_roundtrip(self, tmp_path):
        """Saving and loading custom window size works."""
        prefs_file = tmp_path / "wopc_prefs.ini"
        with patch.object(prefs, "PREFS_FILE", prefs_file):
            parser = prefs.load_prefs()
            parser.set("Window", "width", "1280")
            parser.set("Window", "height", "900")
            prefs.save_prefs(parser)

            parser2 = prefs.load_prefs()
            assert parser2.get("Window", "width") == "1280"
            assert parser2.get("Window", "height") == "900"
