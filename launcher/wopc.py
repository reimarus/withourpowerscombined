#!/usr/bin/env python3
"""
WOPC Launcher - With Our Powers Combined
Supreme Commander: Forged Alliance with LOUD gameplay + FAF engine patches.

Usage:
    python wopc.py status    Check game installation, print paths
    python wopc.py setup     Create WOPC directory, copy/symlink content
    python wopc.py launch    Start the game
    python wopc.py validate  Verify WOPC directory integrity
"""

import hashlib
import subprocess
import sys
from pathlib import Path

# Resolve paths relative to this script
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT  = SCRIPT_DIR.parent
INIT_DIR   = REPO_ROOT / "init"

# Import config (add launcher dir to path for clean imports)
sys.path.insert(0, str(SCRIPT_DIR))
from config import (
    VERSION, SCFA_STEAM, LOUD_ROOT,
    WOPC_ROOT, WOPC_BIN, WOPC_GAMEDATA, WOPC_MAPS,
    WOPC_SOUNDS, WOPC_USERMODS,
    SCFA_BIN, LOUD_BIN, LOUD_GAMEDATA,
    GAME_EXE, GAME_LOG,
)


def cmd_status():
    """Check installation status and print paths."""
    print(f"WOPC v{VERSION}\n")

    # Check Steam SCFA
    scfa_ok = SCFA_STEAM.exists() and (SCFA_BIN / "SupremeCommander.exe").exists()
    print(f"Steam SCFA:  {SCFA_STEAM}")
    print(f"  Status:    {'FOUND' if scfa_ok else 'NOT FOUND'}")

    # Check LOUD
    loud_ok = LOUD_ROOT.exists() and (LOUD_ROOT / "gamedata" / "lua.scd").exists()
    print(f"\nLOUD:        {LOUD_ROOT}")
    print(f"  Status:    {'FOUND' if loud_ok else 'NOT FOUND'}")
    if loud_ok:
        scds = list(LOUD_GAMEDATA.glob("*.scd"))
        print(f"  SCDs:      {len(scds)} files")

    # Check WOPC
    wopc_ok = WOPC_BIN.exists() and (WOPC_BIN / GAME_EXE).exists()
    print(f"\nWOPC:        {WOPC_ROOT}")
    print(f"  Status:    {'READY' if wopc_ok else 'NOT SET UP (run: python wopc.py setup)'}")
    if wopc_ok:
        init_ok = (WOPC_BIN / "init_wopc.lua").exists()
        print(f"  Init file: {'OK' if init_ok else 'MISSING'}")
        gd_count = len(list(WOPC_GAMEDATA.glob("*.scd")))
        print(f"  Gamedata:  {gd_count} SCDs")
        mods = [d.name for d in WOPC_USERMODS.iterdir()] if WOPC_USERMODS.exists() else []
        print(f"  User mods: {', '.join(mods) if mods else 'none'}")

    if not scfa_ok:
        print(f"\nERROR: SCFA not found. Set SCFA_STEAM environment variable to your install path.")
        return 1
    if not loud_ok:
        print(f"\nERROR: LOUD not found. Install LOUD first.")
        return 1
    return 0


def cmd_setup():
    """Create the WOPC game directory."""
    # Check prerequisites
    if not SCFA_STEAM.exists():
        print(f"ERROR: SCFA not found at {SCFA_STEAM}")
        return 1
    if not LOUD_ROOT.exists():
        print(f"ERROR: LOUD not found at {LOUD_ROOT}")
        return 1
    if not INIT_DIR.exists():
        print(f"ERROR: init/ directory not found at {INIT_DIR}")
        return 1

    from setup import run_setup
    run_setup(INIT_DIR)
    return 0


def cmd_launch():
    """Launch the game from the WOPC directory."""
    exe_path  = WOPC_BIN / GAME_EXE
    init_path = WOPC_BIN / "init_wopc.lua"

    if not exe_path.exists():
        print(f"ERROR: Game exe not found at {exe_path}")
        print(f"Run 'python wopc.py setup' first.")
        return 1
    if not init_path.exists():
        print(f"ERROR: Init file not found at {init_path}")
        return 1

    cmd = [
        str(exe_path),
        "/init", str(init_path),
        "/log", str(WOPC_BIN / GAME_LOG),
        "/nomovie",
    ]

    print(f"Launching WOPC...")
    print(f"  Exe:  {exe_path}")
    print(f"  Init: {init_path}")
    print(f"  Log:  {WOPC_BIN / GAME_LOG}")

    try:
        subprocess.Popen(cmd, cwd=str(WOPC_BIN))
        print(f"  Game started.")
    except Exception as e:
        print(f"ERROR: Failed to launch: {e}")
        return 1
    return 0


def cmd_validate():
    """Validate the WOPC directory integrity."""
    if not WOPC_ROOT.exists():
        print(f"ERROR: WOPC not set up at {WOPC_ROOT}")
        return 1

    print(f"WOPC Validation\n")
    errors = 0

    # Check exe
    exe = WOPC_BIN / GAME_EXE
    if exe.exists():
        h = hashlib.md5(exe.read_bytes()).hexdigest()
        print(f"  exe:        OK  ({h})")
    else:
        print(f"  exe:        MISSING")
        errors += 1

    # Check init
    init = WOPC_BIN / "init_wopc.lua"
    if init.exists():
        print(f"  init:       OK")
    else:
        print(f"  init:       MISSING")
        errors += 1

    # Check engine DLL
    dll = WOPC_BIN / "MohoEngine.dll"
    if dll.exists():
        print(f"  engine:     OK")
    else:
        print(f"  engine:     MISSING")
        errors += 1

    # Check gamedata
    gd_count = 0
    if WOPC_GAMEDATA.exists():
        for scd in sorted(WOPC_GAMEDATA.glob("*.scd")):
            gd_count += 1
    print(f"  gamedata:   {gd_count} SCDs")
    if gd_count < 10:
        print(f"  WARNING: Expected 17+ SCDs, found {gd_count}")
        errors += 1

    # Check maps
    maps_ok = WOPC_MAPS.exists() and (WOPC_MAPS.is_symlink() or any(WOPC_MAPS.iterdir()))
    print(f"  maps:       {'OK' if maps_ok else 'MISSING'}")
    if not maps_ok:
        errors += 1

    # Check sounds
    sounds_ok = WOPC_SOUNDS.exists()
    print(f"  sounds:     {'OK' if sounds_ok else 'MISSING'}")

    # Check usermods
    if WOPC_USERMODS.exists():
        mods = [d.name for d in WOPC_USERMODS.iterdir() if d.is_dir() or d.suffix in ('.scd', '.zip')]
        print(f"  usermods:   {len(mods)} ({', '.join(mods)})")
    else:
        print(f"  usermods:   none")

    print(f"\n{'All checks passed.' if errors == 0 else f'{errors} error(s) found.'}")
    return 0 if errors == 0 else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0

    cmd = sys.argv[1].lower()

    if cmd == "status":
        return cmd_status()
    elif cmd == "setup":
        return cmd_setup()
    elif cmd == "launch":
        return cmd_launch()
    elif cmd == "validate":
        return cmd_validate()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
