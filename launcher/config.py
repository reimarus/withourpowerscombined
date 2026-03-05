"""WOPC configuration - path constants and version info."""

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    VERSION = version("wopc")
except PackageNotFoundError:
    VERSION = "0.1.0-dev"

# --- Game installation paths ---

# Steam SCFA root (override with SCFA_STEAM environment variable)
SCFA_STEAM = Path(
    os.environ.get(
        "SCFA_STEAM",
        r"C:\Program Files (x86)\Steam\steamapps\common\Supreme Commander Forged Alliance",
    )
)

# LOUD lives inside the SCFA directory
LOUD_ROOT = SCFA_STEAM / "LOUD"

# --- WOPC deployed directory ---

WOPC_ROOT = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "WOPC"
WOPC_BIN = WOPC_ROOT / "bin"
WOPC_GAMEDATA = WOPC_ROOT / "gamedata"
WOPC_MAPS = WOPC_ROOT / "maps"
WOPC_SOUNDS = WOPC_ROOT / "sounds"
WOPC_USERMODS = WOPC_ROOT / "usermods"
WOPC_USERMAPS = WOPC_ROOT / "usermaps"

# --- Source directories in SCFA/LOUD ---

SCFA_BIN = SCFA_STEAM / "bin"
LOUD_BIN = LOUD_ROOT / "bin"
LOUD_GAMEDATA = LOUD_ROOT / "gamedata"
LOUD_MAPS = LOUD_ROOT / "maps"
LOUD_SOUNDS = LOUD_ROOT / "sounds"
LOUD_USERMODS = LOUD_ROOT / "usermods"
LOUD_USERMAPS = LOUD_ROOT / "usermaps"

# --- Files to copy from SCFA/bin/ to WOPC/bin/ ---

BIN_FILES = [
    # Core engine
    "SupremeCommander.exe",
    "MohoEngine.dll",
    "LuaPlus_1081.dll",
    "game.dat",
    # GPG libraries
    "gpgcore.dll",
    "gpggal.dll",
    # DirectX / Visual C++ runtime
    "d3dx9_31.dll",
    "msvcm80.dll",
    "msvcp80.dll",
    "msvcr80.dll",
    # BugSplat crash reporting
    "BugSplat.dll",
    "BugSplatRc.dll",
    "BsSndRpt.exe",
    "DbgHelp.dll",
    # Sound / UI / compression
    "SHSMP.DLL",
    "SHW32d.DLL",
    "zlibwapi.dll",
    "wxmsw24u-vs80.dll",
    "sx32w.dll",
    "GDFBinary.dll",
    # Steam
    "steam_api.dll",
    "steam_appid.txt",
    # Assets
    "splash.png",
]

# --- Files from LOUD/bin/ to copy to WOPC/bin/ ---

LOUD_BIN_FILES = [
    "CommonDataPath.lua",
    "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd",
]

# --- Init files from our repo to copy to WOPC/bin/ ---

INIT_FILES = [
    "init_wopc.lua",
    "CommonDataPath.lua",
]

# --- Game exe name and launch arguments ---

GAME_EXE = "SupremeCommander.exe"
GAME_LOG = "WOPC.log"
