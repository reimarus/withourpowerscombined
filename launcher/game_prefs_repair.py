"""SCFA Game.prefs repair — detect and fix corrupted preference files.

The SCFA engine stores preferences in a Lua-table-format file called
``Game.prefs``, located at::

    %LOCALAPPDATA%/Gas Powered Games/Supreme Commander Forged Alliance/Game.prefs

Known corruption patterns:

1. ``active_mods = true`` (boolean) instead of ``active_mods = { ... }`` (table).
   Causes: "attempt to index a boolean value" errors in prefs.lua and optionslogic.lua,
   leading to black screen on launch.

This module provides a ``repair_game_prefs()`` function that should be called
before every game launch.  It reads the file as text, detects known corruption
patterns, and repairs them in-place (with backup).
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger("wopc.game_prefs_repair")

# Standard SCFA Game.prefs location
_GAME_PREFS_DIR = (
    Path.home() / "AppData" / "Local" / "Gas Powered Games" / "Supreme Commander Forged Alliance"
)
GAME_PREFS_PATH = _GAME_PREFS_DIR / "Game.prefs"


def repair_game_prefs(prefs_path: Path | None = None) -> list[str]:
    """Detect and repair known corruption patterns in Game.prefs.

    Parameters
    ----------
    prefs_path:
        Path to Game.prefs.  Defaults to the standard SCFA location.

    Returns
    -------
    list[str]
        List of repairs applied (empty if file was clean).
    """
    if prefs_path is None:
        prefs_path = GAME_PREFS_PATH

    if not prefs_path.exists():
        return []

    try:
        content = prefs_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning("Could not read Game.prefs at %s: %s", prefs_path, e)
        return []

    repairs: list[str] = []

    # --- Repair 1: active_mods = true/false → active_mods = { } ---
    # Matches top-level or nested "active_mods = true" or "active_mods = false"
    # but NOT "active_mods = {" (which is already correct).
    pattern = re.compile(r"(active_mods\s*=\s*)(true|false)(\s*[,\n}])", re.IGNORECASE)
    if pattern.search(content):
        content = pattern.sub(r"\1{ }\3", content)
        repairs.append("active_mods was boolean, replaced with empty table")

    if not repairs:
        return []

    # Back up the corrupted file before overwriting
    backup_path = prefs_path.with_suffix(".prefs.bak")
    try:
        shutil.copy2(prefs_path, backup_path)
        logger.info("Backed up corrupted Game.prefs to %s", backup_path)
    except OSError as e:
        logger.warning("Could not back up Game.prefs: %s", e)

    # Write repaired content
    try:
        prefs_path.write_text(content, encoding="utf-8")
        for repair in repairs:
            logger.info("Game.prefs repair: %s", repair)
        logger.info(
            "Game.prefs repaired successfully (%d change(s)). Backup saved as %s",
            len(repairs),
            backup_path.name,
        )
    except OSError as e:
        logger.error("Failed to write repaired Game.prefs: %s", e)
        # Try to restore from backup
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, prefs_path)
                logger.info("Restored original Game.prefs from backup")
            except OSError:
                pass
        return []

    return repairs
