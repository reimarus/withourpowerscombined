"""Tests for WOPC deploy/setup logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_copies_bundled_gamedata_scds(self, patched_config, repo_init_dir):
        """Copies each SCD file from bundled gamedata."""
        from launcher.deploy import run_setup

        run_setup(repo_init_dir)

        wopc_gd = patched_config["WOPC_GAMEDATA"]
        # The fake bundled dir has lua.scd and units.scd, plus our consolidated faf_ui.scd
        scds = list(wopc_gd.glob("*.scd"))
        assert len(scds) >= 3
        assert (wopc_gd / "faf_ui.scd").exists()

    def test_faf_ui_scd_includes_wopc_patches(self, patched_config, repo_init_dir):
        """faf_ui.scd must contain WOPC patch files (consolidated build)."""
        import zipfile

        from launcher.deploy import run_setup

        run_setup(repo_init_dir)

        faf_ui_scd = patched_config["WOPC_GAMEDATA"] / "faf_ui.scd"
        with zipfile.ZipFile(faf_ui_scd, "r") as zf:
            names = zf.namelist()
            # The fake wopc_patches dir has patch_file.lua
            assert "patch_file.lua" in names, "faf_ui.scd should contain WOPC patch files"

    def test_faf_ui_scd_includes_textures(self, patched_config, repo_init_dir):
        """faf_ui.scd must contain FAF texture files."""
        import zipfile

        from launcher.deploy import run_setup

        run_setup(repo_init_dir)

        faf_ui_scd = patched_config["WOPC_GAMEDATA"] / "faf_ui.scd"
        with zipfile.ZipFile(faf_ui_scd, "r") as zf:
            texture_entries = [n for n in zf.namelist() if n.startswith("textures/")]
            assert len(texture_entries) >= 1, "faf_ui.scd should contain texture files"
            # Arcnames must be lowercase (FAF import() requirement)
            for name in texture_entries:
                assert name == name.lower(), f"Non-lowercase arcname: {name}"

    def test_copies_scfa_maps(self, patched_config, repo_init_dir):
        """Copies SCFA stock maps to WOPC maps directory."""
        from launcher.deploy import run_setup

        scfa_maps = patched_config["SCFA_STEAM"] / "maps"
        scfa_maps.mkdir(parents=True)
        (scfa_maps / "SCMP_001").mkdir()

        run_setup(repo_init_dir)

        wopc_maps = patched_config["WOPC_MAPS"]
        assert (wopc_maps / "SCMP_001").exists()

    def test_creates_usermods_dir(self, patched_config, repo_init_dir):
        """Creates or copies usermods directory."""
        from launcher.deploy import run_setup

        run_setup(repo_init_dir)

        wopc_usermods = patched_config["WOPC_USERMODS"]
        assert wopc_usermods.exists()


class TestContentPackAcquisition:
    """Test content pack download/copy logic."""

    def test_copies_from_loud_when_available(self, patched_config):
        """Copies SCD from local LOUD install instead of downloading."""
        from launcher.deploy import _acquire_content_packs

        # Set up a fake LOUD install with blackops.scd
        loud_gd = patched_config["LOUD_GAMEDATA"]
        loud_gd.mkdir(parents=True)
        loud_sounds = patched_config["LOUD_SOUNDS"]
        loud_sounds.mkdir(parents=True)

        (loud_gd / "blackops.scd").write_bytes(b"\x00" * 100)
        (loud_sounds / "blackopssb.xsb").write_bytes(b"\x01" * 10)
        (loud_sounds / "blackopswb.xwb").write_bytes(b"\x02" * 20)

        _acquire_content_packs()

        wopc_gd = patched_config["WOPC_GAMEDATA"]
        wopc_sounds = patched_config["WOPC_SOUNDS"]
        assert (wopc_gd / "blackops.scd").exists()
        assert (wopc_gd / "blackops.scd").stat().st_size == 100
        assert (wopc_sounds / "blackopssb.xsb").exists()
        assert (wopc_sounds / "blackopswb.xwb").exists()

    def test_downloads_when_loud_not_installed(self, patched_config):
        """Downloads SCD from GitHub when LOUD is not available."""
        from launcher.deploy import _acquire_content_packs

        # No LOUD directory exists — should attempt download
        mock_retrieve = MagicMock(side_effect=lambda url, dst: Path(dst).write_bytes(b"\x00" * 50))
        with patch("launcher.deploy.urllib.request.urlretrieve", mock_retrieve):
            _acquire_content_packs()

        # Should have been called for SCD + 2 sounds = 3 downloads
        assert mock_retrieve.call_count == 3

        wopc_gd = patched_config["WOPC_GAMEDATA"]
        assert (wopc_gd / "blackops.scd").exists()

    def test_skips_when_already_cached(self, patched_config):
        """Does not re-download when files already exist in WOPC."""
        from launcher.deploy import _acquire_content_packs

        # Pre-populate WOPC with existing files
        wopc_gd = patched_config["WOPC_GAMEDATA"]
        wopc_gd.mkdir(parents=True, exist_ok=True)
        (wopc_gd / "blackops.scd").write_bytes(b"\x00" * 100)

        wopc_sounds = patched_config["WOPC_SOUNDS"]
        wopc_sounds.mkdir(parents=True, exist_ok=True)
        (wopc_sounds / "blackopssb.xsb").write_bytes(b"\x01")
        (wopc_sounds / "blackopswb.xwb").write_bytes(b"\x02")

        mock_retrieve = MagicMock()
        with patch("launcher.deploy.urllib.request.urlretrieve", mock_retrieve):
            _acquire_content_packs()

        # Nothing should be downloaded
        mock_retrieve.assert_not_called()

    def test_download_failure_does_not_crash(self, patched_config):
        """Gracefully handles download failures."""
        from launcher.deploy import _acquire_content_packs

        mock_retrieve = MagicMock(side_effect=OSError("network error"))
        with patch("launcher.deploy.urllib.request.urlretrieve", mock_retrieve):
            # Should not raise
            _acquire_content_packs()

        wopc_gd = patched_config["WOPC_GAMEDATA"]
        assert not (wopc_gd / "blackops.scd").exists()


class TestExtractModsFromScd:
    """Test mod extraction from SCD archives."""

    def test_extracts_mods_to_wopc_mods(self, patched_config, tmp_path):
        """Extracts mods/ subtree from SCD to WOPC/mods/ with prefix stripped."""
        import zipfile

        from launcher.deploy import _extract_mods_from_scd

        # Create a fake SCD with mod content
        scd_path = tmp_path / "test.scd"
        with zipfile.ZipFile(scd_path, "w") as zf:
            zf.writestr("mods/TestMod/mod_info.lua", 'name = "Test Mod"')
            zf.writestr("mods/TestMod/units/TEST001/TEST001_unit.bp", "bp data")
            zf.writestr("mods/TestMod/hook/lua/test.lua", "hook data")
            zf.writestr("lua/AI/test_ai.lua", "ai data")  # non-mod file

        result = _extract_mods_from_scd(scd_path)

        assert result == ["TestMod"]
        wopc_mods = patched_config["WOPC_MODS"]
        assert (wopc_mods / "TestMod" / "mod_info.lua").exists()
        assert (wopc_mods / "TestMod" / "units" / "TEST001" / "TEST001_unit.bp").exists()
        assert (wopc_mods / "TestMod" / "hook" / "lua" / "test.lua").exists()
        # Non-mod files should NOT be extracted
        assert not (wopc_mods / "lua").exists()

    def test_skips_existing_files(self, patched_config, tmp_path):
        """Does not overwrite already-extracted mod files."""
        import zipfile

        from launcher.deploy import _extract_mods_from_scd

        wopc_mods = patched_config["WOPC_MODS"]
        wopc_mods.mkdir(parents=True, exist_ok=True)
        (wopc_mods / "TestMod").mkdir()
        (wopc_mods / "TestMod" / "mod_info.lua").write_text("original")

        scd_path = tmp_path / "test.scd"
        with zipfile.ZipFile(scd_path, "w") as zf:
            zf.writestr("mods/TestMod/mod_info.lua", "new content")

        _extract_mods_from_scd(scd_path)

        # Should keep original content
        assert (wopc_mods / "TestMod" / "mod_info.lua").read_text() == "original"
