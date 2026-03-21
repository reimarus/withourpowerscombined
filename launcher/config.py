"""WOPC configuration - path constants and version info."""

import os
import sys
from pathlib import Path

from launcher.__version__ import VERSION  # noqa: F401 — re-exported

# --- Game installation paths ---
#
# The launcher exe lives directly in the SCFA install folder.  When frozen
# (PyInstaller exe), the parent directory of the exe *is* the SCFA root.
# WOPC content is deployed to SCFA/WOPC/ (alongside LOUD's SCFA/LOUD/).


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
REPO_BUNDLED_USERMODS = REPO_BUNDLED / "usermods"

# WOPC Overlay Content (consolidated into wopc_core.scd during build)
REPO_WOPC_PATCHES = _REPO_ROOT / "gamedata" / "wopc_patches"

# WOPC core SCD — merged FAF game logic + our patches + vanilla gap-fills
REPO_WOPC_CORE_SRC = VENDOR_DIR / "faf-ui"
WOPC_CORE_SCD = "wopc_core.scd"

# FAF distributes a specific base exe that the binary patches are built against.
# The Steam SupremeCommander.exe has different code addresses, so hooks would
# target wrong locations.  We download FAF's exe once and cache it locally.
FAF_BASE_EXE_URL = "https://content.faforever.com/build/ForgedAlliance_base.exe"
FAF_BASE_EXE_CACHE = PATCH_BUILD_DIR / "ForgedAlliance_base.exe"

# --- LOUD installation paths (for sourcing content packs) ---

LOUD_ROOT = SCFA_STEAM / "LOUD"
LOUD_GAMEDATA = LOUD_ROOT / "gamedata"
LOUD_SOUNDS = LOUD_ROOT / "sounds"
LOUD_TEXTURES_SCD = LOUD_GAMEDATA / "textures.scd"

# Auto-generated SCD containing unit icons extracted from LOUD's textures.scd.
# This is rebuilt during `wopc setup` whenever content packs change.
CONTENT_ICONS_SCD = "content_icons.scd"
CONTENT_ICONS_URL = "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/content_icons.scd"

# Content pack assets hosted on GitHub releases.
# deploy.py tries local LOUD install first, then downloads from these URLs.
CONTENT_PACK_ASSETS: dict[str, dict] = {
    "blackops.scd": {
        "url": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/blackops.scd",
        "sounds": {
            "blackopssb.xsb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/blackopssb.xsb",
            "blackopswb.xwb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/blackopswb.xwb",
        },
    },
    "TotalMayhem.scd": {
        "url": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/TotalMayhem.scd",
        "sounds": {
            "tm_aeonweapons.xsb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_aeonweapons.xsb",
            "tm_aeonweaponsounds.xwb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_aeonweaponsounds.xwb",
            "tm_aircrafts.xsb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_aircrafts.xsb",
            "tm_aircraftsounds.xwb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_aircraftsounds.xwb",
            "tm_cybranweapons.xsb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_cybranweapons.xsb",
            "tm_cybranweaponsounds.xwb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_cybranweaponsounds.xwb",
            "tm_explosions.xsb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_explosions.xsb",
            "tm_explosionsounds.xwb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_explosionsounds.xwb",
            "tm_uefweapons.xsb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_uefweapons.xsb",
            "tm_uefweaponsounds.xwb": "https://github.com/reimarus/withourpowerscombined/releases/download/content-v1/tm_uefweaponsounds.xwb",
        },
    },
}

# --- Content version and core assets for standalone installer ---
# When running from the frozen exe without the full repo or LOUD,
# deploy.py downloads these from GitHub Releases.
CONTENT_VERSION = "v2"

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
