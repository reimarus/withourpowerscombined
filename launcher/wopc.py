import hashlib
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from launcher import mods, prefs
from launcher.config import (
    FA_PATCHES_DIR,
    GAME_EXE,
    GAME_LOG,
    PATCH_BUILD_DIR,
    PATCH_MANIFEST,
    REPO_BUNDLED_GAMEDATA,
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
from launcher.game_config import write_game_config
from launcher.log import setup_logging

HELP_TEXT = """
WOPC Launcher - With Our Powers Combined
Standalone Supreme Commander: Forged Alliance client.

Usage:
    wopc gui          Launch the graphical UI (default)
    wopc status       Check game installation, print paths
    wopc setup        Create WOPC directory, copy/symlink content
    wopc launch       Start the game
    wopc validate     Verify WOPC directory integrity (or pass manifest.json to check hashes)
    wopc manifest     Generate manifest.json of current WOPC installation hashes
    wopc patch        Build patched game executable
      --clean         Force rebuild from scratch
      --check         Verify toolchain without building
      --dry-run       Show what would be built
"""


# Resolve paths relative to this script (for finding repo init/ dir)
if getattr(sys, "frozen", False):
    REPO_ROOT = Path(sys.executable).parent.resolve()
else:
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

    # Check bundled assets
    bundled_ok = REPO_BUNDLED_GAMEDATA.exists()
    logger.info("\nBundled:     %s", REPO_BUNDLED_GAMEDATA)
    logger.info("  Status:    %s", "FOUND" if bundled_ok else "NOT FOUND")
    if bundled_ok:
        scds = list(REPO_BUNDLED_GAMEDATA.glob("*.scd"))
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

    # Check binary patches
    patched_exe = PATCH_BUILD_DIR / "ForgedAlliance_exxt.exe"
    patches_available = FA_PATCHES_DIR.is_dir()
    logger.info("\nPatches:     %s", FA_PATCHES_DIR)
    logger.info("  Submodule: %s", "FOUND" if patches_available else "NOT INITIALIZED")
    logger.info(
        "  Built exe: %s",
        "READY" if patched_exe.is_file() else "NOT BUILT (run: wopc patch)",
    )

    if not scfa_ok:
        logger.error("\nERROR: SCFA not found. Place WOPC-Launcher.exe in the SCFA install folder.")
        return 1
    if not bundled_ok:
        logger.warning("\nWARNING: Bundled assets not found in repo.")
    return 0


def cmd_setup() -> int:
    """Create the WOPC game directory."""
    # Check prerequisites
    if not SCFA_STEAM.exists():
        logger.error(
            "ERROR: SCFA not found at %s. Place WOPC-Launcher.exe in the SCFA install folder.",
            SCFA_STEAM,
        )
        return 1
    if not REPO_BUNDLED_GAMEDATA.exists():
        logger.warning("WARNING: Bundled assets not found in repo.")
    if not INIT_DIR.exists():
        logger.error("ERROR: init/ directory not found at %s", INIT_DIR)
        return 1

    from launcher.deploy import run_setup

    run_setup(INIT_DIR)
    return 0


def _resolve_map_vfs_path(active_map: str) -> str | None:
    """Convert a map folder name to a VFS scenario path.

    Returns e.g. ``/maps/Caldera/Caldera_scenario.lua`` or None.
    """
    if not active_map:
        return None
    map_dir = WOPC_MAPS / active_map
    if map_dir.exists():
        for f in map_dir.iterdir():
            if f.name.endswith("_scenario.lua"):
                return f"/maps/{active_map}/{f.name}"
    logger.warning("Could not find _scenario.lua in %s", map_dir)
    return None


def cmd_launch(
    ai_opponents: list[dict[str, Any]] | None = None,
    game_options: dict[str, str] | None = None,
    player_color: int = 1,
    launch_mode: str | None = None,
) -> int:
    """Launch the game from the WOPC directory.

    Supports three launch modes:
    - **solo**: Quickstart bypass — 1 human + AI, no lobby UI.
    - **host**: Host a multiplayer game via quickstart + UDP P2P.
    - **join**: Join a hosted multiplayer game via quickstart + UDP P2P.

    Parameters
    ----------
    ai_opponents:
        Optional list of AI opponent dicts for solo mode.
        If None, a single medium AI is used (game_config default).
    game_options:
        Optional dict of game option overrides for solo mode.
    launch_mode:
        Explicit launch mode ('solo', 'host', or 'join').  If None,
        falls back to the pref value (for backwards compatibility).
    """
    exe_path = WOPC_BIN / GAME_EXE

    if not exe_path.exists():
        logger.error("ERROR: Game exe not found at %s", exe_path)
        logger.error("Run 'wopc setup' first.")
        return 1

    # Regenerate init_wopc.lua from current preferences (content packs, mods)
    from launcher.init_generator import generate_init_lua

    init_path = generate_init_lua()
    logger.info("Regenerated %s", init_path)

    if launch_mode is None:
        launch_mode = prefs.get_launch_mode()
    # Normalize legacy pref values — "multiplayer" was an old pref value
    # that doesn't map to a valid launch mode.
    if launch_mode not in ("solo", "host", "join"):
        launch_mode = "solo"
    player_name = prefs.get_player_name()

    cmd = [
        str(exe_path),
        "/init",
        str(init_path),
        "/log",
        str(WOPC_BIN / GAME_LOG),
        "/nomovie",
    ]

    active_map = prefs.get_active_map()
    all_mod_uids = mods.get_active_mod_uids()

    if launch_mode == "join":
        # Join mode: connect to host's game via SCFA UDP.
        # Our launcher's TCP lobby already coordinated everything —
        # we just need to launch SCFA with /joingame and quickstart config.
        join_address = prefs.get_join_address()
        if not join_address:
            logger.error("ERROR: No host address configured. Set join_address in prefs.")
            return 1
        player_faction = prefs.get_player_faction()
        expected_humans = prefs.get_expected_humans()
        # Joiner writes minimal config (just faction + multiplayer flags)
        config_path = write_game_config(
            scenario_file="",  # host provides the map
            player_name=player_name,
            player_faction=player_faction,
            player_color=player_color,
            ai_opponents=[],
            active_mod_uids=all_mod_uids,
            expected_humans=expected_humans,
            is_host=False,
        )
        logger.info("Wrote game config: %s", config_path)
        cmd.extend(
            [
                "/joingame",
                "udp",
                join_address,
                player_name,
                "/wopcquickstart",
                "/wopcconfig",
                str(config_path),
            ]
        )
        logger.info("Launching WOPC (join mode)...")
        logger.info("  Connecting to: %s", join_address)

    elif launch_mode == "host":
        # Host mode: launch SCFA with /hostgame + quickstart.
        # Our launcher's TCP lobby coordinated players — SCFA handles
        # the UDP P2P networking via multilobby.lua.
        vfs_path = _resolve_map_vfs_path(active_map)
        if not vfs_path:
            logger.error("ERROR: No map selected — cannot host.")
            return 1
        host_port = prefs.get_host_port()
        expected_humans = prefs.get_expected_humans()
        player_faction = prefs.get_player_faction()
        minimap_enabled = prefs.get_minimap_enabled()
        merged_options: dict[str, str] = {"minimap_enabled": str(minimap_enabled)}
        if game_options:
            merged_options.update(game_options)
        config_path = write_game_config(
            scenario_file=vfs_path,
            player_name=player_name,
            player_faction=player_faction,
            player_color=player_color,
            ai_opponents=ai_opponents,
            game_options=merged_options,
            active_mod_uids=all_mod_uids,
            expected_humans=expected_humans,
            is_host=True,
        )
        logger.info("Wrote game config: %s", config_path)
        cmd.extend(
            [
                "/hostgame",
                "udp",
                host_port,
                player_name,
                "WOPC",
                vfs_path,
                "/wopcquickstart",
                "/wopcconfig",
                str(config_path),
            ]
        )
        logger.info("Launching WOPC (host mode)...")
        logger.info("  Hosting on port: %s", host_port)

    else:
        # Solo mode: quickstart bypass (existing behavior).
        vfs_path = _resolve_map_vfs_path(active_map)
        if vfs_path:
            player_faction = prefs.get_player_faction()
            minimap_enabled = prefs.get_minimap_enabled()
            merged_options_solo: dict[str, str] = {"minimap_enabled": str(minimap_enabled)}
            if game_options:
                merged_options_solo.update(game_options)
            config_path = write_game_config(
                scenario_file=vfs_path,
                player_name=player_name,
                player_faction=player_faction,
                player_color=player_color,
                ai_opponents=ai_opponents,
                game_options=merged_options_solo,
                active_mod_uids=all_mod_uids,
            )
            logger.info("Wrote game config: %s", config_path)
            cmd.extend(
                [
                    "/hostgame",
                    "udp",
                    "15000",
                    player_name,
                    "WOPC",
                    vfs_path,
                    "/wopcquickstart",
                    "/wopcconfig",
                    str(config_path),
                ]
            )
        else:
            logger.warning("No map selected — launching to main menu")
        logger.info("Launching WOPC (solo mode)...")

    logger.info("  Exe:  %s", exe_path)
    logger.info("  Init: %s", init_path)
    logger.info("  Log:  %s", WOPC_BIN / GAME_LOG)
    if active_map and launch_mode != "join":
        logger.info("  Map:  %s", active_map)
    if all_mod_uids:
        logger.info("  Mods: %s", ", ".join(all_mod_uids))

    try:
        subprocess.Popen(cmd, cwd=str(WOPC_BIN))
        logger.info("  Game started.")
    except Exception:
        logger.exception("ERROR: Failed to launch")
        return 1
    return 0


def cmd_validate(args: list[str] | None = None) -> int:
    """Validate the WOPC directory integrity."""
    if not WOPC_ROOT.exists():
        logger.error("ERROR: WOPC not set up at %s", WOPC_ROOT)
        return 1

    # If user provided a manifest JSON, run the hash verify instead of basic validation
    if args and len(args) > 0:
        manifest_path = Path(args[0])
        from launcher.manifest_builder import verify_manifest

        return verify_manifest(manifest_path)

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


def cmd_manifest() -> int:
    """Generate the multiplayer sync manifest."""
    if not WOPC_ROOT.exists():
        logger.error("ERROR: WOPC not set up at %s", WOPC_ROOT)
        return 1

    from launcher.manifest_builder import generate_manifest

    output = Path("manifest.json")
    generate_manifest(output)
    return 0


def cmd_patch(args: list[str]) -> int:
    """Build the patched game executable from binary patches."""
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


def cmd_gui() -> int:
    """Launch the WOPC graphical user interface."""
    from launcher.gui.app import launch_gui

    launch_gui()
    return 0


def main() -> int:
    """CLI entry point."""
    # Parse --verbose/-v flag
    raw_args: list[str] = sys.argv
    verbose: bool = "--verbose" in raw_args or "-v" in raw_args
    args: list[str] = []

    # Avoid Pyre __getitem__ slice linting errors by iterating directly
    for i in range(1, len(raw_args)):
        val = raw_args[i]
        if val not in ("--verbose", "-v"):
            args.append(val)

    setup_logging(verbose=verbose)

    if len(args) < 1:
        return cmd_gui()

    cmd: str = args[0].lower()
    cmd_args: list[str] = args[1:]

    commands = {
        "status": cmd_status,
        "setup": cmd_setup,
        "launch": cmd_launch,
        "validate": lambda: cmd_validate(cmd_args),
        "manifest": cmd_manifest,
        "gui": cmd_gui,
    }

    # Commands that accept extra arguments
    if cmd == "patch":
        return cmd_patch(cmd_args)

    if cmd in commands:
        return commands[cmd]()  # type: ignore[no-any-return, operator]
    else:
        logger.error("Unknown command: %s", cmd)
        logger.info(HELP_TEXT)
        return 1


if __name__ == "__main__":
    sys.exit(main())
