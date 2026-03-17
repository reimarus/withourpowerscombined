"""Tests for the WOPC CLI entry point."""

from unittest.mock import MagicMock, patch

import pytest

from launcher.log import setup_logging


@pytest.fixture(autouse=True)
def _init_logging():
    """Ensure logging is initialized for all tests."""
    setup_logging(verbose=False)


class TestMain:
    """Test the main() CLI dispatch."""

    def test_no_args_launches_gui(self, mocker):
        """Running with no args launches the GUI and returns 0."""
        import sys

        from launcher.wopc import main

        mock_gui = mocker.patch("launcher.wopc.cmd_gui", return_value=0)
        mocker.patch.object(sys, "argv", ["wopc.py"])
        assert main() == 0
        mock_gui.assert_called_once()

    def test_unknown_command_returns_1(self):
        """Unknown command returns 1."""
        from launcher.wopc import main

        with patch("sys.argv", ["wopc", "foobar"]):
            assert main() == 1

    def test_status_dispatches(self):
        """'status' arg calls cmd_status."""
        from launcher.wopc import main

        with (
            patch("sys.argv", ["wopc", "status"]),
            patch("launcher.wopc.cmd_status", return_value=0) as mock_status,
        ):
            result = main()
            mock_status.assert_called_once()
            assert result == 0

    def test_verbose_flag_parsed(self):
        """--verbose flag is parsed and removed from args."""
        from launcher.wopc import main

        with (
            patch("sys.argv", ["wopc", "--verbose", "status"]),
            patch("launcher.wopc.cmd_status", return_value=0) as mock_status,
        ):
            result = main()
            mock_status.assert_called_once()
            assert result == 0


class TestCmdStatus:
    """Test the status command."""

    def test_scfa_not_found(self, tmp_path):
        """Reports error when SCFA directory doesn't exist."""
        from launcher.wopc import cmd_status

        nonexistent = tmp_path / "nonexistent"
        with (
            patch("launcher.wopc.SCFA_STEAM", nonexistent),
            patch("launcher.wopc.SCFA_BIN", nonexistent / "bin"),
            patch("launcher.wopc.REPO_BUNDLED_GAMEDATA", nonexistent / "bundled" / "gamedata"),
            patch("launcher.wopc.WOPC_ROOT", tmp_path / "WOPC"),
            patch("launcher.wopc.WOPC_BIN", tmp_path / "WOPC" / "bin"),
            patch("launcher.wopc.WOPC_GAMEDATA", tmp_path / "WOPC" / "gamedata"),
            patch("launcher.wopc.WOPC_USERMODS", tmp_path / "WOPC" / "usermods"),
        ):
            result = cmd_status()
            assert result == 1

    def test_scfa_found_bundled_found(self, fake_scfa_tree, tmp_path):
        """Reports FOUND for both when directories exist."""
        from launcher.wopc import cmd_status

        scfa = fake_scfa_tree
        bundled = tmp_path / "bundled"
        wopc = tmp_path / "WOPC"
        wopc_bin = wopc / "bin"
        wopc_bin.mkdir(parents=True)

        with (
            patch("launcher.wopc.SCFA_STEAM", scfa),
            patch("launcher.wopc.SCFA_BIN", scfa / "bin"),
            patch("launcher.wopc.REPO_BUNDLED_GAMEDATA", bundled / "gamedata"),
            patch("launcher.wopc.WOPC_ROOT", wopc),
            patch("launcher.wopc.WOPC_BIN", wopc_bin),
            patch("launcher.wopc.WOPC_GAMEDATA", wopc / "gamedata"),
            patch("launcher.wopc.WOPC_USERMODS", wopc / "usermods"),
        ):
            result = cmd_status()
            assert result == 0


class TestCmdLaunch:
    """Test the launch command."""

    def test_exe_missing_returns_1(self, tmp_path):
        """Returns 1 when exe not found."""
        from launcher.wopc import cmd_launch

        with (
            patch("launcher.wopc.WOPC_BIN", tmp_path),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
        ):
            result = cmd_launch()
            assert result == 1

    @patch("subprocess.Popen")
    def test_launch_calls_popen(self, mock_popen, tmp_path):
        """Launches game with correct arguments including quickstart."""
        from launcher.wopc import cmd_launch

        wopc_bin = tmp_path / "bin"
        wopc_bin.mkdir()
        (wopc_bin / "SupremeCommander.exe").write_bytes(b"\x00")
        (wopc_bin / "init_wopc.lua").write_text("-- init")

        wopc_maps = tmp_path / "maps"
        (wopc_maps / "SCMP_002").mkdir(parents=True)
        (wopc_maps / "SCMP_002" / "SCMP_002_scenario.lua").write_text("-- scenario")

        mock_popen.return_value = MagicMock()

        with (
            patch("launcher.wopc.WOPC_BIN", wopc_bin),
            patch("launcher.wopc.WOPC_MAPS", wopc_maps),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
            patch("launcher.wopc.GAME_LOG", "WOPC.log"),
            patch("launcher.wopc.prefs.get_active_map", return_value="SCMP_002"),
            patch("launcher.wopc.prefs.get_player_name", return_value="Player"),
            patch(
                "launcher.wopc.mods.get_active_mod_uids",
                return_value=["server-uid-1", "brew-lan-uid"],
            ),
            patch(
                "launcher.wopc.write_game_config",
                return_value=wopc_bin / "wopc_game_config.lua",
            ),
        ):
            result = cmd_launch()
            assert result == 0
            mock_popen.assert_called_once()
            # Verify exe is first arg
            call_args = mock_popen.call_args[0][0]
            assert "SupremeCommander.exe" in call_args[0]
            assert "/hostgame" in call_args
            assert "/wopcquickstart" in call_args
            assert "/wopcconfig" in call_args
            assert "/maps/SCMP_002/SCMP_002_scenario.lua" in call_args
            # Mod activation is handled via game config + quickstart.lua,
            # not /mod command line — verify /mod is NOT in args
            assert "/mod" not in call_args

    @patch("subprocess.Popen", side_effect=OSError("access denied"))
    def test_launch_handles_oserror(self, mock_popen, tmp_path):
        """Handles launch failure gracefully."""
        from launcher.wopc import cmd_launch

        wopc_bin = tmp_path / "bin"
        wopc_bin.mkdir()
        (wopc_bin / "SupremeCommander.exe").write_bytes(b"\x00")
        (wopc_bin / "init_wopc.lua").write_text("-- init")

        with (
            patch("launcher.wopc.WOPC_BIN", wopc_bin),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
            patch("launcher.wopc.GAME_LOG", "WOPC.log"),
            patch("launcher.wopc.prefs.get_active_map", return_value=""),
            patch("launcher.wopc.mods.get_active_mod_uids", return_value=[]),
        ):
            result = cmd_launch()
            assert result == 1


class TestCmdLaunchModes:
    """Test the three launch modes: solo, host, join."""

    def _setup_wopc_tree(self, tmp_path):
        """Create a minimal WOPC tree with exe, init, and a map."""
        wopc_bin = tmp_path / "bin"
        wopc_bin.mkdir()
        (wopc_bin / "SupremeCommander.exe").write_bytes(b"\x00")
        (wopc_bin / "init_wopc.lua").write_text("-- init")
        wopc_maps = tmp_path / "maps"
        (wopc_maps / "TestMap").mkdir(parents=True)
        (wopc_maps / "TestMap" / "TestMap_scenario.lua").write_text("-- scen")
        return wopc_bin, wopc_maps

    @patch("subprocess.Popen")
    def test_solo_mode_has_quickstart(self, mock_popen, tmp_path):
        """Solo mode includes /wopcquickstart and /wopcconfig flags."""
        from launcher.wopc import cmd_launch

        wopc_bin, wopc_maps = self._setup_wopc_tree(tmp_path)
        mock_popen.return_value = MagicMock()

        with (
            patch("launcher.wopc.WOPC_BIN", wopc_bin),
            patch("launcher.wopc.WOPC_MAPS", wopc_maps),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
            patch("launcher.wopc.GAME_LOG", "WOPC.log"),
            patch("launcher.wopc.mods.get_active_mod_uids", return_value=[]),
            patch("launcher.wopc.prefs.get_launch_mode", return_value="solo"),
            patch("launcher.wopc.prefs.get_active_map", return_value="TestMap"),
            patch("launcher.wopc.prefs.get_player_name", return_value="P1"),
            patch(
                "launcher.wopc.write_game_config",
                return_value=wopc_bin / "wopc_game_config.lua",
            ),
        ):
            assert cmd_launch() == 0
            args = mock_popen.call_args[0][0]
            assert "/wopcquickstart" in args
            assert "/hostgame" in args

    @patch("subprocess.Popen")
    def test_host_mode_no_quickstart(self, mock_popen, tmp_path):
        """Host mode uses /hostgame but NOT /wopcquickstart."""
        from launcher.wopc import cmd_launch

        wopc_bin, wopc_maps = self._setup_wopc_tree(tmp_path)
        mock_popen.return_value = MagicMock()

        with (
            patch("launcher.wopc.WOPC_BIN", wopc_bin),
            patch("launcher.wopc.WOPC_MAPS", wopc_maps),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
            patch("launcher.wopc.GAME_LOG", "WOPC.log"),
            patch("launcher.wopc.mods.get_active_mod_uids", return_value=[]),
            patch("launcher.wopc.prefs.get_launch_mode", return_value="host"),
            patch("launcher.wopc.prefs.get_active_map", return_value="TestMap"),
            patch("launcher.wopc.prefs.get_player_name", return_value="HostP"),
            patch("launcher.wopc.prefs.get_host_port", return_value="16000"),
        ):
            assert cmd_launch() == 0
            args = mock_popen.call_args[0][0]
            assert "/hostgame" in args
            assert "/wopcquickstart" not in args
            assert "16000" in args

    @patch("subprocess.Popen")
    def test_host_custom_port(self, mock_popen, tmp_path):
        """Host mode uses the configured port from prefs."""
        from launcher.wopc import cmd_launch

        wopc_bin, wopc_maps = self._setup_wopc_tree(tmp_path)
        mock_popen.return_value = MagicMock()

        with (
            patch("launcher.wopc.WOPC_BIN", wopc_bin),
            patch("launcher.wopc.WOPC_MAPS", wopc_maps),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
            patch("launcher.wopc.GAME_LOG", "WOPC.log"),
            patch("launcher.wopc.mods.get_active_mod_uids", return_value=[]),
            patch("launcher.wopc.prefs.get_launch_mode", return_value="host"),
            patch("launcher.wopc.prefs.get_active_map", return_value="TestMap"),
            patch("launcher.wopc.prefs.get_player_name", return_value="P1"),
            patch("launcher.wopc.prefs.get_host_port", return_value="17500"),
        ):
            assert cmd_launch() == 0
            args = mock_popen.call_args[0][0]
            assert "17500" in args

    @patch("subprocess.Popen")
    def test_join_mode_uses_joingame(self, mock_popen, tmp_path):
        """Join mode uses /joingame with address, no map arg."""
        from launcher.wopc import cmd_launch

        wopc_bin, wopc_maps = self._setup_wopc_tree(tmp_path)
        mock_popen.return_value = MagicMock()

        with (
            patch("launcher.wopc.WOPC_BIN", wopc_bin),
            patch("launcher.wopc.WOPC_MAPS", wopc_maps),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
            patch("launcher.wopc.GAME_LOG", "WOPC.log"),
            patch("launcher.wopc.mods.get_active_mod_uids", return_value=[]),
            patch("launcher.wopc.prefs.get_launch_mode", return_value="join"),
            patch("launcher.wopc.prefs.get_active_map", return_value="TestMap"),
            patch("launcher.wopc.prefs.get_player_name", return_value="JoinP"),
            patch(
                "launcher.wopc.prefs.get_join_address",
                return_value="192.168.1.10:15000",
            ),
        ):
            assert cmd_launch() == 0
            args = mock_popen.call_args[0][0]
            assert "/joingame" in args
            assert "192.168.1.10:15000" in args
            assert "/hostgame" not in args
            assert "/wopcquickstart" not in args

    def test_join_missing_address_returns_1(self, tmp_path):
        """Join mode returns error when no address is configured."""
        from launcher.wopc import cmd_launch

        wopc_bin, wopc_maps = self._setup_wopc_tree(tmp_path)

        with (
            patch("launcher.wopc.WOPC_BIN", wopc_bin),
            patch("launcher.wopc.WOPC_MAPS", wopc_maps),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
            patch("launcher.wopc.GAME_LOG", "WOPC.log"),
            patch("launcher.wopc.mods.get_active_mod_uids", return_value=[]),
            patch("launcher.wopc.prefs.get_launch_mode", return_value="join"),
            patch("launcher.wopc.prefs.get_active_map", return_value="TestMap"),
            patch("launcher.wopc.prefs.get_player_name", return_value="P1"),
            patch("launcher.wopc.prefs.get_join_address", return_value=""),
        ):
            assert cmd_launch() == 1


class TestCmdSetup:
    """Test the setup command."""

    def test_scfa_missing_returns_1(self, tmp_path):
        """Returns 1 when SCFA not found."""
        from launcher.wopc import cmd_setup

        with patch("launcher.wopc.SCFA_STEAM", tmp_path / "nonexistent"):
            result = cmd_setup()
            assert result == 1

    def test_bundled_missing_warns(self, fake_scfa_tree, tmp_path):
        """Generates warning when bundled gamedata is missing."""
        from launcher.wopc import cmd_setup

        bundled = tmp_path / "bundled"

        with (
            patch("launcher.wopc.SCFA_STEAM", fake_scfa_tree),
            patch("launcher.wopc.REPO_BUNDLED_GAMEDATA", bundled / "gamedata"),
            patch("launcher.wopc.INIT_DIR", tmp_path),
        ):
            # should still setup and return 0
            with patch("launcher.deploy.run_setup"):
                result = cmd_setup()
            assert result == 0
