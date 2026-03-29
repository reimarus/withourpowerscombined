"""WOPC configuration — path constants and version info."""

import os
import sys
from pathlib import Path

from launcher.__version__ import VERSION  # noqa: F401 — re-exported

# --- Game installation paths ---
#
# The launcher exe lives directly in the SCFA install folder.  When frozen
# (PyInstaller exe), the parent directory of the exe *is* the SCFA root.
# WOPC content is deployed to SCFA/WOPC/.


def _resolve_paths() -> tuple[Path, Path]:
    """Derive SCFA root and WOPC root from the exe location.

    Frozen (PyInstaller exe): exe sits in SCFA root → parent = SCFA.
    Dev mode:                 SCFA_STEAM env var, or fallback default.
    """
    if getattr(sys, "frozen", False):
        scfa = Path(sys.executable).parent.resolve()
    else:
        env = os.environ.get("SCFA_STEAM")
        scfa = (
            Path(env)
            if env
            else Path(
                r"C:\Program Files (x86)\Steam\steamapps\common"
                r"\Supreme Commander Forged Alliance"
            )
        )
    return scfa, scfa / "WOPC"


SCFA_STEAM, WOPC_ROOT = _resolve_paths()

# --- WOPC deployed subdirectories ---

WOPC_BIN = WOPC_ROOT / "bin"
WOPC_GAMEDATA = WOPC_ROOT / "gamedata"
WOPC_MAPS = WOPC_ROOT / "maps"
WOPC_SOUNDS = WOPC_ROOT / "sounds"
WOPC_MODS = WOPC_ROOT / "mods"  # Server-level mods (extracted from content packs)
WOPC_USERMODS = WOPC_ROOT / "usermods"
WOPC_USERMAPS = WOPC_ROOT / "usermaps"

# --- Source directories in SCFA ---

SCFA_BIN = SCFA_STEAM / "bin"

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
    # BugSplat crash reporting — keep the DLLs (exe links against them at load)
    # but omit BsSndRpt.exe (the GPG reporter GUI) so crash dumps stay on disk
    # for local analysis instead of being sent to a defunct server.
    "BugSplat.dll",
    "BugSplatRc.dll",
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

# DLLs the exe links against at load time — if ANY are missing, the game
# crashes immediately with exit code 0xC0000135 (STATUS_DLL_NOT_FOUND).
# Discovered via Firebase report 037d3861: fresh SCFA-only install on
# Windows 11 failed silently because setup only warned about missing files.
CRITICAL_BIN_FILES = {
    "SupremeCommander.exe",
    "MohoEngine.dll",
    "LuaPlus_1081.dll",
    "game.dat",
    "d3dx9_31.dll",
    "msvcm80.dll",
    "msvcp80.dll",
    "msvcr80.dll",
    "gpgcore.dll",
    "gpggal.dll",
    "BugSplat.dll",
    "BugSplatRc.dll",
    "DbgHelp.dll",
    "SHSMP.DLL",
    "SHW32d.DLL",
    "zlibwapi.dll",
    "wxmsw24u-vs80.dll",
    "sx32w.dll",
    "steam_api.dll",
}

# --- Files from SCFA/bin/ to copy to WOPC/bin/ ---

# --- Init files from our repo to copy to WOPC/bin/ ---

INIT_FILES = [
    "init_wopc.lua",
    "CommonDataPath.lua",
]

# --- Patch build paths ---
# These are relative to the repo root (where pyproject.toml lives)

_REPO_ROOT = Path(__file__).parent.parent.resolve()
VENDOR_DIR = _REPO_ROOT / "vendor"
FA_PATCHES_DIR = VENDOR_DIR / "FA-Binary-Patches"
FA_PATCHER_DIR = VENDOR_DIR / "fa-python-binary-patcher"
PATCH_BUILD_DIR = _REPO_ROOT / "patches" / "build"
PATCH_MANIFEST = _REPO_ROOT / "wopc_patches.toml"

# Bundled standalone assets (from LFS or release zip)
REPO_BUNDLED = _REPO_ROOT / "bundled"
REPO_BUNDLED_BIN = REPO_BUNDLED / "bin"
REPO_BUNDLED_GAMEDATA = REPO_BUNDLED / "gamedata"
REPO_BUNDLED_MAPS = REPO_BUNDLED / "maps"
REPO_BUNDLED_SOUNDS = REPO_BUNDLED / "sounds"
REPO_BUNDLED_MODS = REPO_BUNDLED / "mods"
REPO_BUNDLED_USERMODS = REPO_BUNDLED / "usermods"

# WOPC Overlay Content (consolidated into wopc_core.scd during build)
REPO_WOPC_PATCHES = _REPO_ROOT / "gamedata" / "wopc_patches"

# WOPC core SCD — merged game logic source + our patches + vanilla gap-fills
REPO_WOPC_CORE_SRC = VENDOR_DIR / "faf-ui"
WOPC_CORE_SCD = "wopc_core.scd"

# The binary patches are built against a specific base exe with known code
# addresses.  The Steam SupremeCommander.exe has different layout, so hooks
# would target wrong locations.  Downloaded once and cached locally.
BASE_EXE_URL = "https://content.faforever.com/build/ForgedAlliance_base.exe"
BASE_EXE_CACHE = PATCH_BUILD_DIR / "ForgedAlliance_base.exe"

# Auto-generated SCD containing unit icons for content pack units.
CONTENT_ICONS_SCD = "content_icons.scd"
CONTENT_ICONS_URL = "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/content_icons.scd"

# Content pack assets hosted on GitHub releases.
_V1 = "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1"
_V3 = "https://github.com/reimarus/withourpowerscombined/releases/download/content-v3"

CONTENT_PACK_ASSETS: dict[str, dict] = {
    # --- Required dependency (auto-enabled when any unit pack is active) ---
    "lua.scd": {
        "url": f"{_V3}/lua.scd",
    },
    "loc_US.scd": {
        "url": f"{_V3}/loc_US.scd",
    },
    # --- Unit packs (content-v1) ---
    "blackops.scd": {
        "url": f"{_V1}/blackops.scd",
        "sounds": {
            "blackopssb.xsb": f"{_V1}/blackopssb.xsb",
            "blackopswb.xwb": f"{_V1}/blackopswb.xwb",
        },
    },
    "TotalMayhem.scd": {
        "url": f"{_V1}/TotalMayhem.scd",
        "sounds": {
            "tm_aeonweapons.xsb": f"{_V1}/tm_aeonweapons.xsb",
            "tm_aeonweaponsounds.xwb": f"{_V1}/tm_aeonweaponsounds.xwb",
            "tm_aircrafts.xsb": f"{_V1}/tm_aircrafts.xsb",
            "tm_aircraftsounds.xwb": f"{_V1}/tm_aircraftsounds.xwb",
            "tm_cybranweapons.xsb": f"{_V1}/tm_cybranweapons.xsb",
            "tm_cybranweaponsounds.xwb": f"{_V1}/tm_cybranweaponsounds.xwb",
            "tm_explosions.xsb": f"{_V1}/tm_explosions.xsb",
            "tm_explosionsounds.xwb": f"{_V1}/tm_explosionsounds.xwb",
            "tm_uefweapons.xsb": f"{_V1}/tm_uefweapons.xsb",
            "tm_uefweaponsounds.xwb": f"{_V1}/tm_uefweaponsounds.xwb",
        },
    },
    # --- Unit packs (content-v3) ---
    "brewlan.scd": {
        "url": f"{_V3}/brewlan.scd",
    },
    "loud_units.scd": {
        "url": f"{_V3}/loud_units.scd",
    },
    "WyvernBattlePack.scd": {
        "url": f"{_V3}/WyvernBattlePack.scd",
        "sounds": {
            "BattlePackSB.xsb": f"{_V3}/BattlePackSB.xsb",
            "BattlePackWB.xwb": f"{_V3}/BattlePackWB.xwb",
        },
    },
    "4D-CompatibilityPack.scd": {
        "url": f"{_V3}/4D-CompatibilityPack.scd",
    },
}

# SCDs that must be mounted when any unit pack SCD is enabled.
# lua.scd provides base classes (defaultunits.lua, loudutilities.lua) that
# all LOUD unit mods import. loc_US.scd provides localization strings.
UNIT_PACK_DEPENDENCIES: frozenset[str] = frozenset({"lua.scd", "loc_US.scd"})

# SCDs that contain unit mods (trigger auto-enabling of dependencies).
UNIT_PACK_SCDS: frozenset[str] = frozenset(
    {
        "blackops.scd",
        "TotalMayhem.scd",
        "brewlan.scd",
        "loud_units.scd",
        "WyvernBattlePack.scd",
        "4D-CompatibilityPack.scd",
    }
)

# --- Content version and core assets for standalone installer ---
# deploy.py downloads these from GitHub Releases when not building from source.
CONTENT_VERSION = "v2"

# Bump this integer when content-v2 is rebuilt to force users to re-download.
# The launcher writes this to WOPC/content_build.txt during setup and checks
# it on startup.  A mismatch triggers automatic re-setup.
CONTENT_BUILD = 3

_RELEASE_BASE = "https://github.com/reimarus/withourpowerscombined/releases/download"

CORE_CONTENT_ASSETS: dict[str, dict[str, str | bool]] = {
    "wopc_core.scd.zip": {
        "url": f"{_RELEASE_BASE}/content-v2/wopc_core.scd.zip",
        "dst": "gamedata",
        "extract": True,
    },
    "wopc-maps.zip": {
        "url": f"{_RELEASE_BASE}/content-v2/wopc-maps.zip",
        "dst": "maps",
        "extract": True,
    },
    "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd": {
        "url": f"{_RELEASE_BASE}/content-v2/BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd",
        "dst": "bin",
    },
}

# --- Game exe name and launch arguments ---

GAME_EXE = "SupremeCommander.exe"
GAME_LOG = "WOPC.log"

# --- Internet relay (Firebase Realtime Database) ---
# Set to your Firebase project URL once the project is created, e.g.:
#   "https://<project-id>-default-rtdb.firebaseio.com"
# Leave empty to disable internet discovery (LAN-only mode).
RELAY_URL: str = "https://wopc-75b65-default-rtdb.firebaseio.com"
