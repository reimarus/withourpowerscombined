"""Tests for launcher.config path resolution."""

import os
from pathlib import Path
from unittest.mock import patch

from launcher.config import BIN_FILES, GAME_EXE, INIT_FILES


class TestPathConstants:
    """Test that config paths resolve correctly."""

    def test_default_scfa_path_is_steam(self):
        """SCFA_STEAM defaults to the standard Steam path."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove SCFA_STEAM if set, keep rest of env
            env = os.environ.copy()
            env.pop("SCFA_STEAM", None)
            with patch.dict(os.environ, env, clear=True):
                # Re-import to test fresh value
                import importlib

                import launcher.config

                importlib.reload(launcher.config)
                expected = Path(
                    r"C:\Program Files (x86)\Steam\steamapps\common"
                    r"\Supreme Commander Forged Alliance"
                )
                assert expected == launcher.config.SCFA_STEAM

    def test_scfa_env_override(self):
        """SCFA_STEAM can be overridden by environment variable."""
        import importlib

        import launcher.config

        with patch.dict(os.environ, {"SCFA_STEAM": r"D:\Games\SCFA"}):
            importlib.reload(launcher.config)
            assert Path(r"D:\Games\SCFA") == launcher.config.SCFA_STEAM
        # Reload again to restore
        importlib.reload(launcher.config)

    def test_repo_bundled_relative_to_repo(self):
        """REPO_BUNDLED is relative to the repo root."""
        from launcher.config import _REPO_ROOT, REPO_BUNDLED

        assert REPO_BUNDLED == _REPO_ROOT / "bundled"

    def test_wopc_root_uses_programdata(self):
        """WOPC_ROOT defaults to %PROGRAMDATA%/WOPC."""
        from launcher.config import WOPC_ROOT

        expected_parent = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        assert expected_parent / "WOPC" == WOPC_ROOT


class TestFileLists:
    """Test file list constants."""

    def test_bin_files_not_empty(self):
        """BIN_FILES contains expected game files."""
        assert len(BIN_FILES) > 0

    def test_game_exe_in_bin_files(self):
        """SupremeCommander.exe is in BIN_FILES."""
        assert GAME_EXE in BIN_FILES

    def test_moho_engine_in_bin_files(self):
        """MohoEngine.dll is in BIN_FILES."""
        assert "MohoEngine.dll" in BIN_FILES

    def test_init_files_has_init_wopc(self):
        """init_wopc.lua is in INIT_FILES."""
        assert "init_wopc.lua" in INIT_FILES

    def test_init_files_has_common_data_path(self):
        """CommonDataPath.lua is in INIT_FILES."""
        assert "CommonDataPath.lua" in INIT_FILES
