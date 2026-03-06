"""Shared test fixtures for WOPC tests."""

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def fake_scfa_tree(tmp_path: Path) -> Path:
    """Create a minimal fake SCFA directory tree for testing.

    Returns the path to the fake SCFA root directory.
    """
    scfa = tmp_path / "SCFA"
    scfa_bin = scfa / "bin"
    scfa_bin.mkdir(parents=True)

    # Create minimal exe and DLLs (empty files, just need to exist)
    for name in ["SupremeCommander.exe", "MohoEngine.dll", "gpgcore.dll"]:
        (scfa_bin / name).write_bytes(b"\x00" * 64)

    # Create LOUD structure
    loud = scfa / "LOUD"
    loud_gd = loud / "gamedata"
    loud_gd.mkdir(parents=True)
    (loud_gd / "lua.scd").write_bytes(b"\x00" * 32)
    (loud_gd / "units.scd").write_bytes(b"\x00" * 32)

    loud_bin = loud / "bin"
    loud_bin.mkdir()
    (loud_bin / "CommonDataPath.lua").write_text("-- fake")
    (loud_bin / "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd").write_bytes(b"\x00")

    for subdir in ["maps", "sounds", "usermods", "usermaps"]:
        (loud / subdir).mkdir()

    return scfa


@pytest.fixture
def fake_wopc_dir(tmp_path: Path) -> Path:
    """Create a fake WOPC deployment directory for validation tests."""
    wopc = tmp_path / "WOPC"
    wopc_bin = wopc / "bin"
    wopc_bin.mkdir(parents=True)
    (wopc_bin / "SupremeCommander.exe").write_bytes(b"\x00" * 64)
    (wopc_bin / "init_wopc.lua").write_text("-- init")
    (wopc_bin / "MohoEngine.dll").write_bytes(b"\x00" * 32)

    wopc_gd = wopc / "gamedata"
    wopc_gd.mkdir()
    for i in range(17):
        (wopc_gd / f"content{i}.scd").write_bytes(b"\x00")

    (wopc / "maps").mkdir()
    # Put a file in maps so iterdir() is non-empty
    (wopc / "maps" / "test_map").mkdir()
    (wopc / "sounds").mkdir()
    (wopc / "usermods").mkdir()

    return wopc


@pytest.fixture
def patched_config(fake_scfa_tree: Path, tmp_path: Path):
    """Patch config module constants to use fake directories.

    This is the key fixture -- it replaces all filesystem-dependent
    constants so tests never touch real game installations.
    """
    scfa = fake_scfa_tree
    loud = scfa / "LOUD"
    wopc = tmp_path / "WOPC_DEPLOY"
    wopc.mkdir(exist_ok=True)

    # Patch build paths (Phase 2)
    patch_build = tmp_path / "patch_build"
    vendor = tmp_path / "vendor"

    # Fake Submodules
    faf_ui = vendor / "faf_ui"
    (faf_ui / "lua").mkdir(parents=True)
    (faf_ui / "lua" / "ui").mkdir()
    (faf_ui / "lua" / "ui" / "file.lua").write_bytes(b"\x00")

    wopc_patches = scfa / "repo_patches"
    wopc_patches.mkdir()
    (wopc_patches / "patch_file.lua").write_bytes(b"\x00")

    config_patches = {
        "SCFA_STEAM": scfa,
        "SCFA_BIN": scfa / "bin",
        "LOUD_ROOT": loud,
        "LOUD_BIN": loud / "bin",
        "LOUD_GAMEDATA": loud / "gamedata",
        "LOUD_MAPS": loud / "maps",
        "LOUD_SOUNDS": loud / "sounds",
        "LOUD_USERMODS": loud / "usermods",
        "LOUD_USERMAPS": loud / "usermaps",
        "WOPC_ROOT": wopc,
        "WOPC_BIN": wopc / "bin",
        "WOPC_GAMEDATA": wopc / "gamedata",
        "WOPC_MAPS": wopc / "maps",
        "WOPC_SOUNDS": wopc / "sounds",
        "WOPC_USERMODS": wopc / "usermods",
        "WOPC_USERMAPS": wopc / "usermaps",
        "PATCH_BUILD_DIR": patch_build,
        "FA_PATCHES_DIR": vendor / "FA-Binary-Patches",
        "FA_PATCHER_DIR": vendor / "fa-python-binary-patcher",
        "PATCH_MANIFEST": tmp_path / "wopc_patches.toml",
        "REPO_FAF_UI": vendor / "faf_ui",
        "FAF_UI_SCD": "faf_ui.scd",
    }

    with patch.multiple("launcher.config", **config_patches):  # type: ignore[call-overload]
        yield config_patches


@pytest.fixture
def repo_init_dir(tmp_path: Path) -> Path:
    """Create fake repo init/ directory with Lua files."""
    init_dir = tmp_path / "init"
    init_dir.mkdir()
    (init_dir / "init_wopc.lua").write_text("-- init_wopc")
    (init_dir / "CommonDataPath.lua").write_text("-- common")
    return init_dir
