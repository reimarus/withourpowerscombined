"""Mod compatibility patches for LOUD-era mods.

Content pack SCDs contain mods originally built for The LOUD Project.
When extracted to ``WOPC/mods/``, some files reference LOUD-specific APIs
that don't exist in WOPC.  This module patches those references to make
mods self-contained.

Adding a new compatibility patch
--------------------------------
1. Add an entry to :data:`MOD_COMPAT_PATCHES` below.
2. Each entry specifies: mod directory name, file glob, old text, new text.
3. Patches are idempotent — only applied if *old* text is found.
4. :func:`apply_mod_compat_patches` runs after SCD extraction **and** at
   game launch time (safety net for existing installations).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger("wopc.mod_compat")


class CompatPatch(TypedDict):
    """Schema for a single mod compatibility patch."""

    mod: str
    description: str
    glob: str
    old: str
    new: str


# ---------------------------------------------------------------------------
# Registry of compatibility patches.
#
# Each entry targets a specific mod directory and replaces text in matching
# files.  The ``old`` string must appear literally — no regex.
# ---------------------------------------------------------------------------
MOD_COMPAT_PATCHES: list[CompatPatch] = [
    {
        "mod": "BrewLAN_LOUD",
        "description": "Replace LOUD game.lua BrewLANLOUDPath() with literal mod path",
        "glob": "**/*.lua",
        "old": "import( '/lua/game.lua' ).BrewLANLOUDPath()",
        "new": "'/mods/BrewLAN_LOUD'",
    },
    {
        "mod": "BrewLAN_LOUD",
        "description": "Replace variant without spaces around import arg",
        "glob": "**/*.lua",
        "old": "import('/lua/game.lua').BrewLANLOUDPath()",
        "new": "'/mods/BrewLAN_LOUD'",
    },
]


def apply_mod_compat_patches(mods_dir: Path) -> int:
    """Apply all registered compatibility patches to extracted mods.

    Parameters
    ----------
    mods_dir:
        Path to the mods directory (e.g. ``WOPC/mods/``).

    Returns
    -------
    int
        Number of files that were actually modified.
    """
    if not mods_dir.exists():
        return 0

    total_patched = 0

    for patch in MOD_COMPAT_PATCHES:
        mod_dir = mods_dir / patch["mod"]
        if not mod_dir.exists():
            continue

        for lua_file in mod_dir.glob(patch["glob"]):
            if not lua_file.is_file():
                continue
            try:
                text = lua_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if patch["old"] not in text:
                continue

            new_text = text.replace(patch["old"], patch["new"])
            lua_file.write_text(new_text, encoding="utf-8")
            total_patched += 1
            logger.info(
                "Patched %s: %s",
                lua_file.relative_to(mods_dir),
                patch["description"],
            )

    if total_patched:
        logger.info("Mod compat: patched %d file(s)", total_patched)
    return total_patched
