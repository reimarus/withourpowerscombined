"""Auto-discover the Supreme Commander: Forged Alliance install path.

Fallback chain:
1. Saved preference (wopc_prefs.ini)
2. Steam libraryfolders.vdf (find library with app 9420)
3. Windows registry (Steam App 9420 uninstall key)
4. Common default paths
5. Return None (caller shows folder picker)

This module deliberately avoids importing ``launcher.config`` to prevent
circular imports.  All needed paths are passed in or derived locally.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

LOG = logging.getLogger("wopc.scfa_finder")

# SCFA Steam App ID
_SCFA_APP_ID = "9420"

# Subdirectory under steamapps/common/
_SCFA_DIRNAME = "Supreme Commander Forged Alliance"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_scfa_path(path: Path) -> bool:
    """Return True if *path* looks like a valid SCFA installation."""
    if not path.is_dir():
        return False
    exe = path / "bin" / "SupremeCommander.exe"
    gamedata = path / "gamedata"
    return exe.is_file() and gamedata.is_dir()


# ---------------------------------------------------------------------------
# Steam VDF parsing
# ---------------------------------------------------------------------------


def _parse_vdf_library_paths(text: str) -> list[Path]:
    """Extract Steam library root paths from libraryfolders.vdf content."""
    paths: list[Path] = []
    # Match "path" value lines — e.g.  "path"		"C:\\Program Files (x86)\\Steam"
    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        raw = match.group(1).replace("\\\\", "\\")
        paths.append(Path(raw))
    return paths


def _vdf_has_app(text: str, app_id: str) -> list[Path]:
    """Return library paths whose apps section contains *app_id*."""
    results: list[Path] = []
    # Split into per-library blocks by top-level numbered keys
    # Each block starts with "N" { and contains "path" and "apps" sections
    blocks = re.split(r'"\d+"\s*\{', text)
    for block in blocks:
        path_match = re.search(r'"path"\s+"([^"]+)"', block)
        if not path_match:
            continue
        raw = path_match.group(1).replace("\\\\", "\\")
        # Check if this block's apps section contains the app ID
        apps_match = re.search(r'"apps"\s*\{([^}]*)\}', block, re.DOTALL)
        if apps_match and re.search(rf'"{app_id}"\s+"', apps_match.group(1)):
            results.append(Path(raw))
    return results


def _find_via_steam_vdf() -> Path | None:
    """Search Steam libraryfolders.vdf for SCFA install path."""
    # Common locations for the VDF file
    candidates = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf"),
        Path(r"C:\Program Files\Steam\steamapps\libraryfolders.vdf"),
    ]
    # Also check STEAM_PATH env var
    steam_path = os.environ.get("STEAM_PATH") or os.environ.get("STEAMPATH")
    if steam_path:
        candidates.insert(0, Path(steam_path) / "steamapps" / "libraryfolders.vdf")

    for vdf_path in candidates:
        if not vdf_path.is_file():
            continue
        try:
            text = vdf_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        libraries = _vdf_has_app(text, _SCFA_APP_ID)
        for lib_root in libraries:
            scfa = lib_root / "steamapps" / "common" / _SCFA_DIRNAME
            if validate_scfa_path(scfa):
                LOG.info("Found SCFA via Steam VDF: %s", scfa)
                return scfa

    return None


# ---------------------------------------------------------------------------
# Windows Registry
# ---------------------------------------------------------------------------


def _find_via_registry() -> Path | None:
    """Check Windows registry for SCFA install location."""
    if sys.platform != "win32":
        return None

    try:
        import winreg
    except ImportError:
        return None

    keys = [
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 9420",
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 9420",
        ),
    ]

    for hive, subkey in keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                install_loc, _ = winreg.QueryValueEx(key, "InstallLocation")
                path = Path(str(install_loc))
                if validate_scfa_path(path):
                    LOG.info("Found SCFA via registry: %s", path)
                    return path
        except OSError:
            continue

    return None


# ---------------------------------------------------------------------------
# Common path scan
# ---------------------------------------------------------------------------

_COMMON_ROOTS = [
    r"C:\Program Files (x86)\Steam",
    r"C:\Program Files\Steam",
    r"D:\SteamLibrary",
    r"E:\SteamLibrary",
    r"F:\SteamLibrary",
    r"D:\Steam",
    r"E:\Steam",
]


def _find_via_common_paths() -> Path | None:
    """Check common Steam library locations for SCFA."""
    for root in _COMMON_ROOTS:
        scfa = Path(root) / "steamapps" / "common" / _SCFA_DIRNAME
        if validate_scfa_path(scfa):
            LOG.info("Found SCFA at common path: %s", scfa)
            return scfa
    return None


# ---------------------------------------------------------------------------
# Prefs integration (lazy to avoid circular imports)
# ---------------------------------------------------------------------------


def _find_via_prefs(prefs_file: Path) -> Path | None:
    """Check saved preferences for a previously-discovered SCFA path."""
    if not prefs_file.is_file():
        return None
    try:
        import configparser

        parser = configparser.ConfigParser()
        parser.read(prefs_file, encoding="utf-8")
        saved = parser.get("Game", "scfa_path", fallback="")
        if saved:
            path = Path(saved)
            if validate_scfa_path(path):
                LOG.info("Found SCFA from saved prefs: %s", path)
                return path
    except Exception:
        pass
    return None


def save_scfa_path(prefs_file: Path, path: Path) -> None:
    """Persist a discovered SCFA path to the prefs INI file."""
    import configparser
    import contextlib

    parser = configparser.ConfigParser()
    if prefs_file.is_file():
        with contextlib.suppress(configparser.Error):
            parser.read(prefs_file, encoding="utf-8")
    if not parser.has_section("Game"):
        parser.add_section("Game")
    parser.set("Game", "scfa_path", str(path))
    prefs_file.parent.mkdir(parents=True, exist_ok=True)
    with prefs_file.open("w", encoding="utf-8") as f:
        parser.write(f)
    LOG.info("Saved SCFA path to prefs: %s", path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_scfa_path(prefs_file: Path | None = None) -> Path | None:
    """Discover the SCFA install path using a fallback chain.

    Parameters
    ----------
    prefs_file:
        Path to ``wopc_prefs.ini``.  If *None*, the prefs check is skipped.

    Returns
    -------
    Path to the SCFA root directory, or *None* if not found.
    """
    # 1. Check environment variable (highest priority, always)
    env_path = os.environ.get("SCFA_STEAM")
    if env_path:
        path = Path(env_path)
        if validate_scfa_path(path):
            return path

    # 2. Check saved prefs
    if prefs_file is not None:
        result = _find_via_prefs(prefs_file)
        if result is not None:
            return result

    # 3. Steam VDF
    result = _find_via_steam_vdf()
    if result is not None:
        if prefs_file is not None:
            save_scfa_path(prefs_file, result)
        return result

    # 4. Windows registry
    result = _find_via_registry()
    if result is not None:
        if prefs_file is not None:
            save_scfa_path(prefs_file, result)
        return result

    # 5. Common paths
    result = _find_via_common_paths()
    if result is not None:
        if prefs_file is not None:
            save_scfa_path(prefs_file, result)
        return result

    LOG.warning("Could not auto-discover SCFA installation")
    return None
