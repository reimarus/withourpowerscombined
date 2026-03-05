"""Tests for WOPC deploy/setup logic."""

from pathlib import Path
from unittest.mock import patch

import pytest

from launcher.log import setup_logging


@pytest.fixture(autouse=True)
def _init_logging():
    """Ensure logging is initialized for all tests."""
    setup_logging(verbose=False)


class TestLinkOrCopy:
    """Test the link_or_copy helper function."""

    def test_skips_existing_dst(self, tmp_path):
        """Does not overwrite existing destination."""
        from launcher.deploy import link_or_copy

        src = tmp_path / "src.txt"
        src.write_text("source")
        dst = tmp_path / "dst.txt"
        dst.write_text("existing")

        link_or_copy(src, dst)
        assert dst.read_text() == "existing"  # Not overwritten

    def test_copies_file_on_symlink_failure(self, tmp_path):
        """Falls back to copy when symlink fails."""
        from launcher.deploy import link_or_copy

        src = tmp_path / "src.txt"
        src.write_text("source content")
        dst = tmp_path / "dst.txt"

        # Force symlink to fail by patching
        with patch.object(Path, "symlink_to", side_effect=OSError("no admin")):
            link_or_copy(src, dst)

        assert dst.exists()
        assert dst.read_text() == "source content"

    def test_copies_directory_on_fallback(self, tmp_path):
        """Copies entire directory when symlink fails."""
        from launcher.deploy import link_or_copy

        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("hello")
        dst_dir = tmp_path / "dst_dir"

        with patch.object(Path, "symlink_to", side_effect=OSError("no admin")):
            link_or_copy(src_dir, dst_dir)

        assert dst_dir.is_dir()
        assert (dst_dir / "file.txt").read_text() == "hello"


class TestCopyFile:
    """Test the copy_file helper function."""

    def test_copies_file(self, tmp_path):
        """Copies file from src to dst."""
        from launcher.deploy import copy_file

        src = tmp_path / "src.txt"
        src.write_text("data")
        dst = tmp_path / "dst.txt"

        copy_file(src, dst)
        assert dst.read_text() == "data"

    def test_skips_existing(self, tmp_path):
        """Does not overwrite existing file."""
        from launcher.deploy import copy_file

        src = tmp_path / "src.txt"
        src.write_text("new")
        dst = tmp_path / "dst.txt"
        dst.write_text("old")

        copy_file(src, dst)
        assert dst.read_text() == "old"  # Not overwritten


class TestRunSetup:
    """Test the full setup workflow."""

    def test_creates_directory_structure(self, patched_config, repo_init_dir):
        """Creates WOPC_ROOT, WOPC_BIN, WOPC_GAMEDATA."""
        from launcher.deploy import run_setup

        wopc = patched_config["WOPC_ROOT"]
        run_setup(repo_init_dir)

        assert wopc.exists()
        assert (wopc / "bin").exists()
        assert (wopc / "gamedata").exists()

    def test_copies_init_files(self, patched_config, repo_init_dir):
        """Copies init_wopc.lua and CommonDataPath.lua to WOPC/bin/."""
        from launcher.deploy import run_setup

        wopc_bin = patched_config["WOPC_BIN"]
        wopc_bin.mkdir(parents=True, exist_ok=True)
        run_setup(repo_init_dir)

        assert (wopc_bin / "init_wopc.lua").exists()
        assert (wopc_bin / "CommonDataPath.lua").exists()

    def test_generates_wopc_paths_lua(self, patched_config, repo_init_dir):
        """Generates wopc_paths.lua with correct SCFA path."""
        from launcher.deploy import run_setup

        wopc_bin = patched_config["WOPC_BIN"]
        wopc_bin.mkdir(parents=True, exist_ok=True)
        run_setup(repo_init_dir)

        paths_lua = wopc_bin / "wopc_paths.lua"
        assert paths_lua.exists()
        content = paths_lua.read_text()
        assert "SCFARoot" in content

    def test_handles_missing_bin_files(self, patched_config, repo_init_dir):
        """Warns about missing bin files but continues without error."""
        from launcher.deploy import run_setup

        # The fake SCFA tree only has 3 files, so most BIN_FILES will be missing
        # Setup should still complete without raising
        run_setup(repo_init_dir)

    def test_symlinks_gamedata_scds(self, patched_config, repo_init_dir):
        """Symlinks or copies each SCD file from LOUD gamedata."""
        from launcher.deploy import run_setup

        run_setup(repo_init_dir)

        wopc_gd = patched_config["WOPC_GAMEDATA"]
        # The fake LOUD has lua.scd and units.scd
        scds = list(wopc_gd.glob("*.scd"))
        assert len(scds) >= 2

    def test_creates_usermods_dir(self, patched_config, repo_init_dir):
        """Creates or copies usermods directory."""
        from launcher.deploy import run_setup

        run_setup(repo_init_dir)

        wopc_usermods = patched_config["WOPC_USERMODS"]
        assert wopc_usermods.exists()
