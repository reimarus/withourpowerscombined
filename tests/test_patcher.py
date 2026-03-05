"""Tests for launcher.patcher — build orchestration for the patched exe."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from launcher.manifest import PatchManifest
from launcher.patcher import PatchBuildError, _copy_base_exe, _prepare_staging, build_patches
from launcher.toolchain import Toolchain


@pytest.fixture
def fake_patches_src(tmp_path: Path) -> Path:
    """Create a fake FA-Binary-Patches directory structure."""
    src = tmp_path / "FA-Binary-Patches"
    for subdir in ("include", "hooks", "section"):
        d = src / subdir
        d.mkdir(parents=True)
        (d / "test_file.cpp").write_text(f"// {subdir}")
    (src / "SigPatches.txt").write_text("sig patches")
    (src / "asm.h").write_text("// asm header")
    return src


@pytest.fixture
def fake_toolchain(tmp_path: Path) -> Toolchain:
    """Create a fake toolchain with placeholder paths."""
    bin_dir = tmp_path / "tools"
    bin_dir.mkdir()
    for name in ("clang++.exe", "g++.exe", "ld.exe"):
        (bin_dir / name).write_bytes(b"\x00")
    return Toolchain(
        clangpp=bin_dir / "clang++.exe",
        gpp=bin_dir / "g++.exe",
        ld=bin_dir / "ld.exe",
    )


@pytest.fixture
def empty_manifest() -> PatchManifest:
    """Manifest with no exclusions."""
    return PatchManifest()


class TestPrepareStaging:
    """Tests for staging directory setup."""

    def test_copies_all_subdirectories(self, tmp_path: Path, fake_patches_src: Path) -> None:
        """Staging should contain include/, hooks/, section/ from source."""
        staging = tmp_path / "staging"
        _prepare_staging(staging, fake_patches_src)

        assert (staging / "include" / "test_file.cpp").exists()
        assert (staging / "hooks" / "test_file.cpp").exists()
        assert (staging / "section" / "test_file.cpp").exists()
        assert (staging / "SigPatches.txt").exists()
        assert (staging / "asm.h").exists()
        assert (staging / "build").is_dir()

    def test_reuses_existing_staging(self, tmp_path: Path, fake_patches_src: Path) -> None:
        """If staging already exists and clean=False, should not re-copy."""
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "marker.txt").write_text("existing")

        _prepare_staging(staging, fake_patches_src, clean=False)

        # Should NOT have copied new files (skipped because dir exists)
        assert (staging / "marker.txt").exists()
        assert not (staging / "include").exists()

    def test_clean_rebuilds_from_scratch(self, tmp_path: Path, fake_patches_src: Path) -> None:
        """clean=True should wipe and recreate staging."""
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "stale_marker.txt").write_text("old")

        _prepare_staging(staging, fake_patches_src, clean=True)

        assert not (staging / "stale_marker.txt").exists()
        assert (staging / "include" / "test_file.cpp").exists()


class TestCopyBaseExe:
    """Tests for copying the stock SCFA executable."""

    def test_copies_exe_to_staging(self, tmp_path: Path) -> None:
        """Should copy SupremeCommander.exe as ForgedAlliance_base.exe."""
        staging = tmp_path / "staging"
        staging.mkdir()

        scfa_bin = tmp_path / "SCFA" / "bin"
        scfa_bin.mkdir(parents=True)
        (scfa_bin / "SupremeCommander.exe").write_bytes(b"\xde\xad" * 32)

        with patch("launcher.patcher.config") as mock_config:
            mock_config.SCFA_BIN = scfa_bin
            mock_config.SCFA_STEAM = tmp_path / "SCFA"
            result = _copy_base_exe(staging)

        assert result == staging / "ForgedAlliance_base.exe"
        assert result.read_bytes() == b"\xde\xad" * 32

    def test_missing_exe_raises(self, tmp_path: Path) -> None:
        """Should raise PatchBuildError if stock exe doesn't exist."""
        staging = tmp_path / "staging"
        staging.mkdir()

        with patch("launcher.patcher.config") as mock_config:
            mock_config.SCFA_BIN = tmp_path / "nope" / "bin"
            mock_config.SCFA_STEAM = tmp_path / "nope"
            with pytest.raises(PatchBuildError, match="not found"):
                _copy_base_exe(staging)


class TestBuildPatches:
    """Integration tests for the full build_patches flow."""

    def test_skips_when_output_exists(
        self, tmp_path: Path, fake_toolchain: Toolchain, empty_manifest: PatchManifest
    ) -> None:
        """Should skip the build if patched exe already exists."""
        build_dir = tmp_path / "build"
        build_dir.mkdir(parents=True)
        existing_exe = build_dir / "ForgedAlliance_exxt.exe"
        existing_exe.write_bytes(b"\x00" * 64)

        with patch("launcher.patcher.config") as mock_config:
            mock_config.PATCH_BUILD_DIR = build_dir
            mock_config.FA_PATCHES_DIR = tmp_path / "patches"
            result = build_patches(fake_toolchain, empty_manifest, clean=False)

        assert result == existing_exe

    def test_raises_when_submodule_missing(
        self, tmp_path: Path, fake_toolchain: Toolchain, empty_manifest: PatchManifest
    ) -> None:
        """Should raise PatchBuildError if FA-Binary-Patches not cloned."""
        build_dir = tmp_path / "build"

        with (
            patch("launcher.patcher.config") as mock_config,
            pytest.raises(PatchBuildError, match="submodule"),
        ):
            mock_config.FA_PATCHES_DIR = tmp_path / "nonexistent"
            mock_config.PATCH_BUILD_DIR = build_dir
            build_patches(fake_toolchain, empty_manifest)

    def test_full_build_success(
        self,
        tmp_path: Path,
        fake_patches_src: Path,
        fake_toolchain: Toolchain,
        empty_manifest: PatchManifest,
    ) -> None:
        """Full build flow with mocked patcher subprocess."""
        build_dir = tmp_path / "build"
        scfa_bin = tmp_path / "SCFA" / "bin"
        scfa_bin.mkdir(parents=True)
        (scfa_bin / "SupremeCommander.exe").write_bytes(b"\xde\xad" * 32)

        patcher_dir = tmp_path / "patcher"
        patcher_dir.mkdir()
        (patcher_dir / "main.py").write_text("# fake patcher")

        def fake_run(cmd, **kwargs):
            """Simulate patcher creating the output exe."""
            # The staging dir is the second argument to main.py
            staging_dir = Path(cmd[2])
            (staging_dir / "ForgedAlliance_exxt.exe").write_bytes(b"\xbe\xef" * 64)
            result = MagicMock()
            result.returncode = 0
            result.stdout = "Patched in 1.23s"
            result.stderr = ""
            return result

        with (
            patch("launcher.patcher.config") as mock_config,
            patch("launcher.patcher.subprocess.run", side_effect=fake_run),
        ):
            mock_config.FA_PATCHES_DIR = fake_patches_src
            mock_config.FA_PATCHER_DIR = patcher_dir
            mock_config.PATCH_BUILD_DIR = build_dir
            mock_config.SCFA_BIN = scfa_bin
            mock_config.SCFA_STEAM = tmp_path / "SCFA"
            mock_config.GAME_EXE = "SupremeCommander.exe"
            result = build_patches(fake_toolchain, empty_manifest)

        assert result == build_dir / "ForgedAlliance_exxt.exe"
        assert result.read_bytes() == b"\xbe\xef" * 64

    def test_patcher_failure_raises(
        self,
        tmp_path: Path,
        fake_patches_src: Path,
        fake_toolchain: Toolchain,
        empty_manifest: PatchManifest,
    ) -> None:
        """Patcher returning nonzero exit code should raise PatchBuildError."""
        build_dir = tmp_path / "build"
        scfa_bin = tmp_path / "SCFA" / "bin"
        scfa_bin.mkdir(parents=True)
        (scfa_bin / "SupremeCommander.exe").write_bytes(b"\x00" * 32)

        patcher_dir = tmp_path / "patcher"
        patcher_dir.mkdir()
        (patcher_dir / "main.py").write_text("# fake")

        def fake_fail(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stdout = ""
            result.stderr = "compilation error"
            return result

        with (
            patch("launcher.patcher.config") as mock_config,
            patch("launcher.patcher.subprocess.run", side_effect=fake_fail),
            pytest.raises(PatchBuildError, match="exit code 1"),
        ):
            mock_config.FA_PATCHES_DIR = fake_patches_src
            mock_config.FA_PATCHER_DIR = patcher_dir
            mock_config.PATCH_BUILD_DIR = build_dir
            mock_config.SCFA_BIN = scfa_bin
            mock_config.SCFA_STEAM = tmp_path / "SCFA"
            mock_config.GAME_EXE = "SupremeCommander.exe"
            build_patches(fake_toolchain, empty_manifest)

    def test_clean_forces_rebuild(
        self,
        tmp_path: Path,
        fake_patches_src: Path,
        fake_toolchain: Toolchain,
        empty_manifest: PatchManifest,
    ) -> None:
        """clean=True should rebuild even when output exists."""
        build_dir = tmp_path / "build"
        build_dir.mkdir(parents=True)
        old_exe = build_dir / "ForgedAlliance_exxt.exe"
        old_exe.write_bytes(b"\x00" * 16)  # old/small

        scfa_bin = tmp_path / "SCFA" / "bin"
        scfa_bin.mkdir(parents=True)
        (scfa_bin / "SupremeCommander.exe").write_bytes(b"\xde\xad" * 32)

        patcher_dir = tmp_path / "patcher"
        patcher_dir.mkdir()
        (patcher_dir / "main.py").write_text("# fake")

        def fake_run(cmd, **kwargs):
            staging_dir = Path(cmd[2])
            (staging_dir / "ForgedAlliance_exxt.exe").write_bytes(b"\xbe\xef" * 64)
            result = MagicMock()
            result.returncode = 0
            result.stdout = "Patched"
            result.stderr = ""
            return result

        with (
            patch("launcher.patcher.config") as mock_config,
            patch("launcher.patcher.subprocess.run", side_effect=fake_run),
        ):
            mock_config.FA_PATCHES_DIR = fake_patches_src
            mock_config.FA_PATCHER_DIR = patcher_dir
            mock_config.PATCH_BUILD_DIR = build_dir
            mock_config.SCFA_BIN = scfa_bin
            mock_config.SCFA_STEAM = tmp_path / "SCFA"
            mock_config.GAME_EXE = "SupremeCommander.exe"
            result = build_patches(fake_toolchain, empty_manifest, clean=True)

        # Should have new content, not the old 16-byte file
        assert result.read_bytes() == b"\xbe\xef" * 64
