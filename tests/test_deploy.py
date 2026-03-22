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
        # The fake bundled dir has lua.scd and units.scd, plus our consolidated wopc_core.scd
        scds = list(wopc_gd.glob("*.scd"))
        assert len(scds) >= 3
        assert (wopc_gd / "wopc_core.scd").exists()

    def test_wopc_core_scd_includes_wopc_patches(self, patched_config, repo_init_dir):
        """wopc_core.scd must contain WOPC patch files (consolidated build)."""
        import zipfile

        from launcher.deploy import run_setup

        run_setup(repo_init_dir)

        wopc_core_scd = patched_config["WOPC_GAMEDATA"] / "wopc_core.scd"
        with zipfile.ZipFile(wopc_core_scd, "r") as zf:
            names = zf.namelist()
            # The fake wopc_patches dir has patch_file.lua
            assert "patch_file.lua" in names, "wopc_core.scd should contain WOPC patch files"

    def test_wopc_core_scd_includes_textures(self, patched_config, repo_init_dir):
        """wopc_core.scd must contain texture files."""
        import zipfile

        from launcher.deploy import run_setup

        run_setup(repo_init_dir)

        wopc_core_scd = patched_config["WOPC_GAMEDATA"] / "wopc_core.scd"
        with zipfile.ZipFile(wopc_core_scd, "r") as zf:
            texture_entries = [n for n in zf.namelist() if n.startswith("textures/")]
            assert len(texture_entries) >= 1, "wopc_core.scd should contain texture files"
            # Arcnames must be lowercase (engine import() requirement)
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

    def test_downloads_content_packs(self, patched_config):
        """Downloads all content packs from GitHub."""
        from launcher.deploy import _acquire_content_packs

        def fake_download(url, dst, *, progress_cb=None):
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b"\x00" * 50)
            return True

        mock_dl = MagicMock(side_effect=fake_download)
        with patch("launcher.deploy._download_file", mock_dl):
            _acquire_content_packs()

        # blackops: 1 SCD + 2 sounds = 3; TotalMayhem: 1 SCD + 10 sounds = 11
        assert mock_dl.call_count == 14

        wopc_gd = patched_config["WOPC_GAMEDATA"]
        assert (wopc_gd / "blackops.scd").exists()
        assert (wopc_gd / "TotalMayhem.scd").exists()

    def test_skips_when_already_cached(self, patched_config):
        """Does not re-download when files already exist in WOPC."""
        from launcher.deploy import _acquire_content_packs

        # Pre-populate WOPC with existing files for ALL content packs
        wopc_gd = patched_config["WOPC_GAMEDATA"]
        wopc_gd.mkdir(parents=True, exist_ok=True)
        (wopc_gd / "blackops.scd").write_bytes(b"\x00" * 100)
        (wopc_gd / "TotalMayhem.scd").write_bytes(b"\x00" * 100)

        wopc_sounds = patched_config["WOPC_SOUNDS"]
        wopc_sounds.mkdir(parents=True, exist_ok=True)
        (wopc_sounds / "blackopssb.xsb").write_bytes(b"\x01")
        (wopc_sounds / "blackopswb.xwb").write_bytes(b"\x02")
        for sfx in [
            "tm_aeonweapons.xsb",
            "tm_aeonweaponsounds.xwb",
            "tm_aircrafts.xsb",
            "tm_aircraftsounds.xwb",
            "tm_cybranweapons.xsb",
            "tm_cybranweaponsounds.xwb",
            "tm_explosions.xsb",
            "tm_explosionsounds.xwb",
            "tm_uefweapons.xsb",
            "tm_uefweaponsounds.xwb",
        ]:
            (wopc_sounds / sfx).write_bytes(b"\x03")

        mock_dl = MagicMock()
        with patch("launcher.deploy._download_file", mock_dl):
            _acquire_content_packs()

        # Nothing should be downloaded
        mock_dl.assert_not_called()

    def test_download_failure_does_not_crash(self, patched_config):
        """Gracefully handles download failures."""
        from launcher.deploy import _acquire_content_packs

        mock_dl = MagicMock(return_value=False)
        with patch("launcher.deploy._download_file", mock_dl):
            # Should not raise
            _acquire_content_packs()

        wopc_gd = patched_config["WOPC_GAMEDATA"]
        assert not (wopc_gd / "blackops.scd").exists()


class TestExcludedModCleanup:
    """Test cleanup of previously-extracted excluded mods."""

    def _prepopulate_all_packs(self, patched_config):
        """Pre-populate all content pack files so _acquire_content_packs skips downloads."""
        wopc_gd = patched_config["WOPC_GAMEDATA"]
        wopc_gd.mkdir(parents=True, exist_ok=True)
        (wopc_gd / "blackops.scd").write_bytes(b"\x00" * 100)
        (wopc_gd / "TotalMayhem.scd").write_bytes(b"\x00" * 100)
        wopc_sounds = patched_config["WOPC_SOUNDS"]
        wopc_sounds.mkdir(parents=True, exist_ok=True)
        (wopc_sounds / "blackopssb.xsb").write_bytes(b"\x01")
        (wopc_sounds / "blackopswb.xwb").write_bytes(b"\x02")
        for sfx in [
            "tm_aeonweapons.xsb",
            "tm_aeonweaponsounds.xwb",
            "tm_aircrafts.xsb",
            "tm_aircraftsounds.xwb",
            "tm_cybranweapons.xsb",
            "tm_cybranweaponsounds.xwb",
            "tm_explosions.xsb",
            "tm_explosionsounds.xwb",
            "tm_uefweapons.xsb",
            "tm_uefweaponsounds.xwb",
        ]:
            (wopc_sounds / sfx).write_bytes(b"\x03")

    def test_removes_excluded_mod_directory(self, patched_config):
        """Removes BlackopsACUs from WOPC/mods/ during content pack acquisition."""
        from launcher.deploy import _acquire_content_packs

        self._prepopulate_all_packs(patched_config)

        wopc_mods = patched_config["WOPC_MODS"]
        wopc_mods.mkdir(parents=True, exist_ok=True)
        excluded_dir = wopc_mods / "BlackopsACUs"
        excluded_dir.mkdir()
        (excluded_dir / "mod_info.lua").write_text('uid = "acus-uid"')

        _acquire_content_packs()

        assert not excluded_dir.exists(), "BlackopsACUs should be removed"

    def test_cleanup_ignores_missing_excluded_dir(self, patched_config):
        """No error when excluded mod dir doesn't exist."""
        from launcher.deploy import _acquire_content_packs

        self._prepopulate_all_packs(patched_config)

        # No BlackopsACUs directory exists — should not raise
        _acquire_content_packs()


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


class TestContentIconDownload:
    """Test content_icons.scd download logic."""

    def _make_extracted_mod(self, patched_config, mod_name: str, unit_ids: list[str]):
        """Create a fake extracted mod with unit directories."""
        wopc_mods = patched_config["WOPC_MODS"]
        for uid in unit_ids:
            (wopc_mods / mod_name / "units" / uid).mkdir(parents=True, exist_ok=True)

    def test_skips_when_no_mods_extracted(self, patched_config):
        """Does not download SCD when no content pack mods exist."""
        from launcher.deploy import _build_content_icons_scd

        _build_content_icons_scd()

        icons_scd = patched_config["WOPC_GAMEDATA"] / "content_icons.scd"
        assert not icons_scd.exists()

    def test_downloads_when_mods_present(self, patched_config):
        """Downloads pre-built SCD from GitHub when content pack mods exist."""
        from launcher.deploy import _build_content_icons_scd

        self._make_extracted_mod(patched_config, "TestMod", ["BRMT1PD"])

        def fake_download(url, dst, *, progress_cb=None):
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b"\x00" * 50)
            return True

        mock_dl = MagicMock(side_effect=fake_download)
        with patch("launcher.deploy._download_file", mock_dl):
            _build_content_icons_scd()

        mock_dl.assert_called_once()
        assert "content_icons.scd" in str(mock_dl.call_args)

    def test_skips_download_when_cached(self, patched_config):
        """Does not re-download if content_icons.scd already exists."""
        from launcher.deploy import _build_content_icons_scd

        self._make_extracted_mod(patched_config, "TestMod", ["BRMT1PD"])
        wopc_gd = patched_config["WOPC_GAMEDATA"]
        wopc_gd.mkdir(parents=True, exist_ok=True)
        (wopc_gd / "content_icons.scd").write_bytes(b"\x00" * 50)

        mock_dl = MagicMock()
        with patch("launcher.deploy._download_file", mock_dl):
            _build_content_icons_scd()

        mock_dl.assert_not_called()


class TestWopcCoreMigration:
    """Test faf_ui.scd → wopc_core.scd migration in standalone mode."""

    def _standalone_config(self, scfa, tmp_path):
        """Build config patches for standalone mode (no REPO_WOPC_CORE_SRC)."""
        wopc = scfa / "WOPC"
        wopc.mkdir(exist_ok=True)
        bundled = tmp_path / "bundled"
        (bundled / "gamedata").mkdir(parents=True)
        (bundled / "bin").mkdir()
        (bundled / "bin" / "CommonDataPath.lua").write_text("-- fake")
        for subdir in ["maps", "sounds", "usermods"]:
            (bundled / subdir).mkdir()
        return {
            "SCFA_STEAM": scfa,
            "SCFA_BIN": scfa / "bin",
            "REPO_BUNDLED": bundled,
            "REPO_BUNDLED_BIN": bundled / "bin",
            "REPO_BUNDLED_GAMEDATA": bundled / "gamedata",
            "REPO_BUNDLED_MAPS": bundled / "maps",
            "REPO_BUNDLED_SOUNDS": bundled / "sounds",
            "REPO_BUNDLED_USERMODS": bundled / "usermods",
            "WOPC_ROOT": wopc,
            "WOPC_BIN": wopc / "bin",
            "WOPC_GAMEDATA": wopc / "gamedata",
            "WOPC_MAPS": wopc / "maps",
            "WOPC_SOUNDS": wopc / "sounds",
            "WOPC_MODS": wopc / "mods",
            "WOPC_USERMODS": wopc / "usermods",
            "WOPC_USERMAPS": wopc / "usermaps",
            "PATCH_BUILD_DIR": tmp_path / "patch_build",
            "FA_PATCHES_DIR": tmp_path / "vendor" / "FA-Binary-Patches",
            "FA_PATCHER_DIR": tmp_path / "vendor" / "fa-python-binary-patcher",
            "PATCH_MANIFEST": tmp_path / "wopc_patches.toml",
            "REPO_WOPC_CORE_SRC": tmp_path / "no_vendor",  # doesn't exist → standalone
            "WOPC_CORE_SCD": "wopc_core.scd",
            "REPO_WOPC_PATCHES": tmp_path / "fake_patches",
            "CONTENT_ICONS_SCD": "content_icons.scd",
            "CONTENT_ICONS_URL": "https://example.com/content_icons.scd",
        }

    def test_standalone_skips_when_wopc_core_exists(self, fake_scfa_tree, tmp_path, repo_init_dir):
        """In standalone mode, if wopc_core.scd already exists, skip migration/download."""
        from launcher.deploy import run_setup

        config_patches = self._standalone_config(fake_scfa_tree, tmp_path)
        wopc_gd = config_patches["WOPC_GAMEDATA"]
        wopc_gd.mkdir(parents=True, exist_ok=True)
        (wopc_gd / "wopc_core.scd").write_bytes(b"\x00" * 64)

        with patch.multiple("launcher.config", **config_patches):
            mock_dl = MagicMock()
            mock_copy = MagicMock()
            with (
                patch("launcher.deploy._download_file", mock_dl),
                patch("launcher.deploy.shutil.copy2", mock_copy),
            ):
                run_setup(repo_init_dir)

            # wopc_core.scd download should NOT have been triggered
            wopc_core_calls = [c for c in mock_dl.call_args_list if "wopc_core" in str(c)]
            assert wopc_core_calls == [], "wopc_core.scd should not be downloaded when it exists"
            # wopc_core.scd should not have been overwritten
            assert (wopc_gd / "wopc_core.scd").read_bytes() == b"\x00" * 64
