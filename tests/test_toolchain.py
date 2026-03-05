"""Tests for launcher.toolchain — compiler discovery and validation."""

from pathlib import Path
from unittest.mock import patch

import pytest

from launcher.toolchain import ToolchainError, _find_executable, find_toolchain


class TestFindExecutable:
    """Unit tests for the _find_executable helper."""

    def test_env_var_override_found(self, tmp_path: Path) -> None:
        """Environment variable pointing to a real file should win."""
        fake_gcc = tmp_path / "g++.exe"
        fake_gcc.write_bytes(b"\x00")

        with patch.dict("os.environ", {"WOPC_GPP": str(fake_gcc)}):
            result = _find_executable("g++.exe", env_var="WOPC_GPP")
        assert result == fake_gcc

    def test_env_var_override_missing_file(self, tmp_path: Path) -> None:
        """Env var set to a nonexistent path should return None (fall through)."""
        with (
            patch.dict("os.environ", {"WOPC_GPP": str(tmp_path / "nope.exe")}),
            patch("launcher.toolchain._SEARCH_PATHS", []),
            patch("shutil.which", return_value=None),
        ):
            result = _find_executable("g++.exe", env_var="WOPC_GPP")
        assert result is None

    def test_well_known_path_found(self, tmp_path: Path) -> None:
        """Tool found in a well-known install location."""
        fake_bin = tmp_path / "mingw32" / "bin"
        fake_bin.mkdir(parents=True)
        (fake_bin / "g++.exe").write_bytes(b"\x00")

        with (
            patch("launcher.toolchain._SEARCH_PATHS", [fake_bin]),
            patch.dict("os.environ", {}, clear=False),
        ):
            result = _find_executable("g++.exe")
        assert result == fake_bin / "g++.exe"

    def test_system_path_fallback(self) -> None:
        """Falls back to shutil.which when env var and well-known paths miss."""
        with (
            patch("launcher.toolchain._SEARCH_PATHS", []),
            patch("shutil.which", return_value="/usr/bin/clang++"),
        ):
            result = _find_executable("clang++.exe")
        assert result == Path("/usr/bin/clang++")

    def test_nothing_found(self) -> None:
        """Returns None when tool cannot be found anywhere."""
        with (
            patch("launcher.toolchain._SEARCH_PATHS", []),
            patch("shutil.which", return_value=None),
        ):
            result = _find_executable("ld.exe")
        assert result is None


class TestFindToolchain:
    """Integration tests for the full toolchain discovery flow."""

    def test_all_tools_found(self, tmp_path: Path) -> None:
        """Happy path: all three tools found, returns Toolchain."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for name in ("clang++.exe", "g++.exe", "ld.exe"):
            (bin_dir / name).write_bytes(b"\x00")

        with (
            patch("launcher.toolchain._SEARCH_PATHS", [bin_dir]),
            patch("launcher.toolchain._get_version", return_value="test 1.0"),
        ):
            tc = find_toolchain()

        assert tc.clangpp == bin_dir / "clang++.exe"
        assert tc.gpp == bin_dir / "g++.exe"
        assert tc.ld == bin_dir / "ld.exe"

    def test_missing_clang_raises(self, tmp_path: Path) -> None:
        """Missing clang++ should raise ToolchainError with install hint."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for name in ("g++.exe", "ld.exe"):
            (bin_dir / name).write_bytes(b"\x00")

        with (
            patch("launcher.toolchain._SEARCH_PATHS", [bin_dir]),
            patch("shutil.which", return_value=None),
            pytest.raises(ToolchainError, match="clang\\+\\+"),
        ):
            find_toolchain()

    def test_missing_all_raises_with_all_hints(self) -> None:
        """Missing everything should mention all three tools in the error."""
        with (
            patch("launcher.toolchain._SEARCH_PATHS", []),
            patch("shutil.which", return_value=None),
            pytest.raises(ToolchainError) as exc_info,
        ):
            find_toolchain()
        msg = str(exc_info.value)
        assert "clang++" in msg
        assert "g++" in msg
        assert "ld" in msg

    def test_env_vars_take_priority(self, tmp_path: Path) -> None:
        """WOPC_CLANGPP, WOPC_GPP, WOPC_LD env vars should override search."""
        for name in ("clang++.exe", "g++.exe", "ld.exe"):
            (tmp_path / name).write_bytes(b"\x00")

        env = {
            "WOPC_CLANGPP": str(tmp_path / "clang++.exe"),
            "WOPC_GPP": str(tmp_path / "g++.exe"),
            "WOPC_LD": str(tmp_path / "ld.exe"),
        }
        with (
            patch.dict("os.environ", env),
            patch("launcher.toolchain._get_version", return_value="test 1.0"),
        ):
            tc = find_toolchain()

        assert tc.clangpp == tmp_path / "clang++.exe"
        assert tc.gpp == tmp_path / "g++.exe"
        assert tc.ld == tmp_path / "ld.exe"
