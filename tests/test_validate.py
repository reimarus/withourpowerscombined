"""Tests for WOPC validation logic."""

from unittest.mock import patch

import pytest

from launcher.log import setup_logging


@pytest.fixture(autouse=True)
def _init_logging():
    """Ensure logging is initialized for all tests."""
    setup_logging(verbose=False)


class TestCmdValidate:
    """Test the validate command."""

    def test_wopc_not_exists_returns_1(self, tmp_path):
        """Returns 1 when WOPC directory doesn't exist."""
        from launcher.wopc import cmd_validate

        with patch("launcher.wopc.WOPC_ROOT", tmp_path / "nonexistent"):
            result = cmd_validate()
            assert result == 1

    def test_all_checks_pass(self, fake_wopc_dir):
        """Returns 0 when all required files present."""
        from launcher.wopc import cmd_validate

        with (
            patch("launcher.wopc.WOPC_ROOT", fake_wopc_dir),
            patch("launcher.wopc.WOPC_BIN", fake_wopc_dir / "bin"),
            patch("launcher.wopc.WOPC_GAMEDATA", fake_wopc_dir / "gamedata"),
            patch("launcher.wopc.WOPC_MAPS", fake_wopc_dir / "maps"),
            patch("launcher.wopc.WOPC_SOUNDS", fake_wopc_dir / "sounds"),
            patch("launcher.wopc.WOPC_USERMODS", fake_wopc_dir / "usermods"),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
        ):
            result = cmd_validate()
            assert result == 0

    def test_missing_exe_reports_error(self, fake_wopc_dir):
        """Missing exe is counted as an error."""
        from launcher.wopc import cmd_validate

        # Remove the exe
        (fake_wopc_dir / "bin" / "SupremeCommander.exe").unlink()

        with (
            patch("launcher.wopc.WOPC_ROOT", fake_wopc_dir),
            patch("launcher.wopc.WOPC_BIN", fake_wopc_dir / "bin"),
            patch("launcher.wopc.WOPC_GAMEDATA", fake_wopc_dir / "gamedata"),
            patch("launcher.wopc.WOPC_MAPS", fake_wopc_dir / "maps"),
            patch("launcher.wopc.WOPC_SOUNDS", fake_wopc_dir / "sounds"),
            patch("launcher.wopc.WOPC_USERMODS", fake_wopc_dir / "usermods"),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
        ):
            result = cmd_validate()
            assert result == 1

    def test_low_scd_count_warns(self, fake_wopc_dir):
        """Warns when fewer than 10 SCDs present."""
        # Remove most SCDs, keep just 2

        from launcher.wopc import cmd_validate

        gd = fake_wopc_dir / "gamedata"
        for scd in list(gd.glob("*.scd"))[2:]:
            scd.unlink()

        with (
            patch("launcher.wopc.WOPC_ROOT", fake_wopc_dir),
            patch("launcher.wopc.WOPC_BIN", fake_wopc_dir / "bin"),
            patch("launcher.wopc.WOPC_GAMEDATA", gd),
            patch("launcher.wopc.WOPC_MAPS", fake_wopc_dir / "maps"),
            patch("launcher.wopc.WOPC_SOUNDS", fake_wopc_dir / "sounds"),
            patch("launcher.wopc.WOPC_USERMODS", fake_wopc_dir / "usermods"),
            patch("launcher.wopc.GAME_EXE", "SupremeCommander.exe"),
        ):
            result = cmd_validate()
            assert result == 1  # Low SCD count is an error
