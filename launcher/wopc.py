#!/usr/bin/env python3
"""
WOPC Launcher - With Our Powers Combined
Supreme Commander: Forged Alliance with LOUD gameplay + FAF engine patches.

Usage:
    wopc status       Check game installation, print paths
    wopc setup        Create WOPC directory, copy/symlink content
    wopc launch       Start the game
    wopc validate     Verify WOPC directory integrity
    wopc patch        Build patched exe from FAF binary patches
      --clean         Force rebuild from scratch
      --check         Verify toolchain without building
      --dry-run       Show what would be built
"""

import hashlib
import logging
import subprocess
import sys
from pathlib import Path

from launcher.config import (
    FA_PATCHES_DIR,
    GAME_EXE,
    GAME_LOG,
    LOUD_GAMEDATA,
    LOUD_ROOT,
    PATCH_BUILD_DIR,
    PATCH_MANIFEST,
    SCFA_BIN,
    SCFA_STEAM,
    VERSION,
    WOPC_BIN,
    WOPC_GAMEDATA,
    WOPC_MAPS,
    WOPC_ROOT,
    WOPC_SOUNDS,
    WOPC_USERMODS,
)
from launcher.log import setup_logging

# Resolve paths relative to this script (for finding repo init/ dir)
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent
INIT_DIR = REPO_ROOT / "init"

logger = logging.getLogger("wopc.cli")


def cmd_status() -> int:
    """Check installation status and print paths."""
    logger.info("WOPC v%s\n", VERSION)

    # Check Steam SCFA
    scfa_ok = SCFA_STEAM.exists() and (SCFA_BIN / "SupremeCommander.exe").exists()
    logger.info("Steam SCFA:  %s", SCFA_STEAM)
    logger.info("  Status:    %s", "FOUND" if scfa_ok else "NOT FOUND")

    # Check LOUD
    loud_ok = LOUD_ROOT.exists() and (LOUD_ROOT / "gamedata" / "lua.scd").exists()
    logger.info("\nLOUD:        %s", LOUD_ROOT)
    logger.info("  Status:    %s", "FOUND" if loud_ok else "NOT FOUND")
    if loud_ok:
        scds = list(LOUD_GAMEDATA.glob("*.scd"))
        logger.info("  SCDs:      %d files", len(scds))

    # Check WOPC
    wopc_ok = WOPC_BIN.exists() and (WOPC_BIN / GAME_EXE).exists()
    logger.info("\nWOPC:        %s", WOPC_ROOT)
    logger.info("  Status:    %s", "READY" if wopc_ok else "NOT SET UP (run: wopc setup)")
    if wopc_ok:
        init_ok = (WOPC_BIN / "init_wopc.lua").exists()
        logger.info("  Init file: %s", "OK" if init_ok else "MISSING")
        gd_count = len(list(WOPC_GAMEDATA.glob("*.scd")))
        logger.info("  Gamedata:  %d SCDs", gd_count)
        mods = [d.name for d in WOPC_USERMODS.iterdir()] if WOPC_USERMODS.exists() else []
        logger.info("  User mods: %s", ", ".join(mods) if mods else "none")

    # Check FAF patches
    patched_exe = PATCH_BUILD_DIR / "ForgedAlliance_exxt.exe"
    patches_available = FA_PATCHES_DIR.is_dir()
    logger.info("\nPatches:     %s", FA_PATCHES_DIR)
    logger.info("  Submodule: %s", "FOUND" if patches_available else "NOT INITIALIZED")
    logger.info(
        "  Built exe: %s",
        "READY" if patched_exe.is_file() else "NOT BUILT (run: wopc patch)",
    )

    if not scfa_ok:
        logger.error(
            "\nERROR: SCFA not found. Set SCFA_STEAM environment variable to your install path."
        )
        return 1
    if not loud_ok:
        logger.error("\nERROR: LOUD not found. Install LOUD first.")
        return 1
    return 0


def cmd_setup() -> int:
    """Create the WOPC game directory."""
    # Check prerequisites
    if not SCFA_STEAM.exists():
        logger.error("ERROR: SCFA not found at %s", SCFA_STEAM)
        return 1
    if not LOUD_ROOT.exists():
        logger.error("ERROR: LOUD not found at %s", LOUD_ROOT)
        return 1
    if not INIT_DIR.exists():
        logger.error("ERROR: init/ directory not found at %s", INIT_DIR)
        return 1

    from launcher.deploy import run_setup

    run_setup(INIT_DIR)
    return 0


def cmd_launch() -> int:
    """Launch the game from the WOPC directory."""
    exe_path = WOPC_BIN / GAME_EXE
    init_path = WOPC_BIN / "init_wopc.lua"

    if not exe_path.exists():
        logger.error("ERROR: Game exe not found at %s", exe_path)
        logger.error("Run 'wopc setup' first.")
        return 1
    if not init_path.exists():
        logger.error("ERROR: Init file not found at %s", init_path)
        return 1

    cmd = [
        str(exe_path),
        "/init",
        str(init_path),
        "/log",
        str(WOPC_BIN / GAME_LOG),
        "/nomovie",
    ]

    logger.info("Launching WOPC...")
    logger.info("  Exe:  %s", exe_path)
    logger.info("  Init: %s", init_path)
    logger.info("  Log:  %s", WOPC_BIN / GAME_LOG)

    try:
        subprocess.Popen(cmd, cwd=str(WOPC_BIN))
        logger.info("  Game started.")
    except Exception:
        logger.exception("ERROR: Failed to launch")
        return 1
    return 0


def cmd_validate() -> int:
    """Validate the WOPC directory integrity."""
    if not WOPC_ROOT.exists():
        logger.error("ERROR: WOPC not set up at %s", WOPC_ROOT)
        return 1

    logger.info("WOPC Validation\n")
    errors = 0

    # Check exe
    exe = WOPC_BIN / GAME_EXE
    if exe.exists():
        h = hashlib.md5(exe.read_bytes()).hexdigest()
        logger.info("  exe:        OK  (%s)", h)
    else:
        logger.error("  exe:        MISSING")
        errors += 1

    # Check init
    init = WOPC_BIN / "init_wopc.lua"
    if init.exists():
        logger.info("  init:       OK")
    else:
        logger.error("  init:       MISSING")
        errors += 1

    # Check engine DLL
    dll = WOPC_BIN / "MohoEngine.dll"
    if dll.exists():
        logger.info("  engine:     OK")
    else:
        logger.error("  engine:     MISSING")
        errors += 1

    # Check gamedata
    gd_count = 0
    if WOPC_GAMEDATA.exists():
        for _scd in sorted(WOPC_GAMEDATA.glob("*.scd")):
            gd_count += 1
    logger.info("  gamedata:   %d SCDs", gd_count)
    if gd_count < 10:
        logger.warning("  WARNING: Expected 17+ SCDs, found %d", gd_count)
        errors += 1

    # Check maps
    maps_ok = WOPC_MAPS.exists() and (WOPC_MAPS.is_symlink() or any(WOPC_MAPS.iterdir()))
    logger.info("  maps:       %s", "OK" if maps_ok else "MISSING")
    if not maps_ok:
        errors += 1

    # Check sounds
    sounds_ok = WOPC_SOUNDS.exists()
    logger.info("  sounds:     %s", "OK" if sounds_ok else "MISSING")

    # Check usermods
    if WOPC_USERMODS.exists():
        mods = [
            d.name for d in WOPC_USERMODS.iterdir() if d.is_dir() or d.suffix in (".scd", ".zip")
        ]
        logger.info("  usermods:   %d (%s)", len(mods), ", ".join(mods))
    else:
        logger.info("  usermods:   none")

    logger.info("\n%s", "All checks passed." if errors == 0 else f"{errors} error(s) found.")
    return 0 if errors == 0 else 1


def cmd_patch(args: list[str]) -> int:
    """Build the patched game executable from FAF binary patches."""
    clean = "--clean" in args
    check_only = "--check" in args
    dry_run = "--dry-run" in args

    from launcher.manifest import ManifestError, load_manifest
    from launcher.toolchain import ToolchainError, find_toolchain

    # Check toolchain
    try:
        toolchain = find_toolchain()
    except ToolchainError as exc:
        logger.error("ERROR: %s", exc)
        return 1

    if check_only:
        logger.info("\nToolchain OK. Ready to build patches.")
        return 0

    # Load manifest
    try:
        manifest = load_manifest(PATCH_MANIFEST)
    except ManifestError as exc:
        logger.error("ERROR: %s", exc)
        return 1

    if dry_run:
        logger.info("\nDry run — would build patches with:")
        logger.info("  Toolchain: %s", toolchain)
        logger.info("  Manifest:  %s", PATCH_MANIFEST)
        logger.info("  Output:    %s", PATCH_BUILD_DIR / "ForgedAlliance_exxt.exe")
        return 0

    # Build
    from launcher.patcher import PatchBuildError, build_patches

    try:
        build_patches(toolchain, manifest, clean=clean)
    except PatchBuildError as exc:
        logger.error("ERROR: %s", exc)
        return 1

    return 0


def main() -> int:
    """CLI entry point."""
    # Parse --verbose/-v flag
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--verbose", "-v")]
    setup_logging(verbose=verbose)

    if len(args) < 1:
        logger.info(__doc__)
        return 0

    cmd = args[0].lower()
    cmd_args = args[1:]

    commands = {
        "status": cmd_status,
        "setup": cmd_setup,
        "launch": cmd_launch,
        "validate": cmd_validate,
    }

    # Commands that accept extra arguments
    if cmd == "patch":
        return cmd_patch(cmd_args)

    if cmd in commands:
        return commands[cmd]()
    else:
        logger.error("Unknown command: %s", cmd)
        logger.info(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
