"""WOPC Mod System — single source of truth for mod lifecycle.

Owns discovery, extraction, activation state, and content pack management.
All mod identification uses UIDs (from mod_info.lua), never folder names.
"""

from __future__ import annotations

import dataclasses
import logging
import re
import zipfile
from pathlib import Path

from launcher import config, prefs

logger = logging.getLogger("wopc.mods")

# ---------------------------------------------------------------------------
# Mod metadata
# ---------------------------------------------------------------------------

_UID_RE = re.compile(r"""uid\s*=\s*['"]([^'"]+)['"]""")
_NAME_RE = re.compile(r"""name\s*=\s*['"]([^'"]+)['"]""")


@dataclasses.dataclass(frozen=True)
class ModInfo:
    """Parsed metadata from a mod_info.lua file."""

    uid: str
    name: str
    folder: str  # directory name on disk
    location: str  # "server" or "user"
    mod_info_path: Path


def parse_mod_info(mod_info_path: Path, location: str = "server") -> ModInfo | None:
    """Parse a mod_info.lua file and return a ModInfo, or None if invalid."""
    try:
        text = mod_info_path.read_text(encoding="utf-8")
    except OSError:
        return None

    uid_match = _UID_RE.search(text)
    if not uid_match:
        return None

    name_match = _NAME_RE.search(text)
    name = name_match.group(1) if name_match else mod_info_path.parent.name

    return ModInfo(
        uid=uid_match.group(1),
        name=name,
        folder=mod_info_path.parent.name,
        location=location,
        mod_info_path=mod_info_path,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _scan_mod_dir(base_dir: Path, location: str) -> list[ModInfo]:
    """Scan a directory for mods with valid mod_info.lua files."""
    if not base_dir.exists():
        return []
    mods = []
    for d in sorted(base_dir.iterdir()):
        if not d.is_dir():
            continue
        info = parse_mod_info(d / "mod_info.lua", location=location)
        if info:
            mods.append(info)
    return mods


def discover_server_mods() -> list[ModInfo]:
    """Scan WOPC/mods/ for server-level mods (always active)."""
    return _scan_mod_dir(config.WOPC_MODS, "server")


def discover_user_mods() -> list[ModInfo]:
    """Scan WOPC/usermods/ for user-installable mods."""
    return _scan_mod_dir(config.WOPC_USERMODS, "user")


def discover_all_mods() -> list[ModInfo]:
    """Return server mods + user mods combined."""
    return discover_server_mods() + discover_user_mods()


# ---------------------------------------------------------------------------
# Content pack management (moved from init_generator.py)
# ---------------------------------------------------------------------------

# Mods inside content pack SCDs that must NOT be extracted.
# BlackopsACUs replaces vanilla ACUs with LOUD-specific units that depend on
# LOUD's extended Unit base class (PlayCommanderWarpInEffect, etc.).  These
# methods don't exist in FAF-only mode, causing cascading script errors that
# make the commander invisible and unresponsive.
EXCLUDED_SCD_MODS: frozenset[str] = frozenset({"BlackopsACUs"})

# SCDs that are always mounted and never toggleable.
CORE_SCDS: frozenset[str] = frozenset({config.CONTENT_ICONS_SCD})

# SCDs with fixed mount positions — excluded from toggleable list.
FIXED_POSITION_SCDS = frozenset({"faf_ui.scd"})

# Human-friendly names for content packs shown in the launcher UI.
CONTENT_PACK_LABELS: dict[str, str] = {
    "lua.scd": "LOUD Lua (required for LOUD packs)",
    "loc_US.scd": "LOUD Localization",
    "4D-CompatibilityPack.scd": "4D Compatibility Pack",
    "blackops.scd": "BlackOps Units",
    "brewlan.scd": "BrewLAN Units",
    "civ_units.scd": "Civilian Units",
    "extra_env.scd": "Extra Environments",
    "loud_misc.scd": "LOUD Miscellaneous",
    "loud_units.scd": "LOUD Units",
    "SC_Music.scd": "Supreme Commander Music",
    "TotalMayhem.scd": "Total Mayhem Units",
    "units.scd": "Core Units",
    "WyvernBattlePack.scd": "Wyvern Battle Pack",
}


def get_toggleable_scds() -> list[str]:
    """Return sorted list of gamedata SCD names the user can toggle.

    Fixed-position SCDs (faf_ui.scd) are excluded.
    """
    if not config.WOPC_GAMEDATA.exists():
        return []

    all_scds = sorted(f.name for f in config.WOPC_GAMEDATA.iterdir() if f.suffix == ".scd")
    non_toggleable = CORE_SCDS | FIXED_POSITION_SCDS
    return [s for s in all_scds if s not in non_toggleable]


def get_enabled_packs() -> list[str]:
    """Return list of currently enabled content pack SCD names."""
    parser = prefs.load_prefs()
    if not parser.has_section("ContentPacks"):
        return []  # FAF-only mode
    enabled = []
    for scd_name in get_toggleable_scds():
        if parser.getboolean("ContentPacks", scd_name, fallback=True):
            enabled.append(scd_name)
    return enabled


def set_pack_state(scd_name: str, enabled: bool) -> None:
    """Enable or disable a content pack SCD. Persists to prefs."""
    parser = prefs.load_prefs()
    if not parser.has_section("ContentPacks"):
        parser.add_section("ContentPacks")
    parser.set("ContentPacks", scd_name, str(enabled))
    prefs.save_prefs(parser)


# ---------------------------------------------------------------------------
# Mod extraction (moved from deploy.py)
# ---------------------------------------------------------------------------


def extract_mods_from_scd(scd_path: Path) -> list[str]:
    """Extract mods/ subtree from an SCD to WOPC/mods/.

    SCFA's mount_mods() needs mods on the real filesystem — it can't
    discover mods inside a ZIP/SCD.  This extracts any ``mods/*/``
    subtree so mount_mods() activates hooks and blueprints.

    Mods listed in :data:`EXCLUDED_SCD_MODS` are skipped (e.g.
    BlackopsACUs which depends on LOUD base classes).

    Returns the list of extracted mod directory names.
    """
    config.WOPC_MODS.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []

    try:
        with zipfile.ZipFile(scd_path, "r") as zf:
            mod_entries = [
                info
                for info in zf.infolist()
                if info.filename.startswith("mods/")
                and not info.is_dir()
                and info.filename.split("/")[1] not in EXCLUDED_SCD_MODS
            ]
            if not mod_entries:
                return extracted

            for info in mod_entries:
                # Strip "mods/" prefix so mount_mods() finds them
                rel_path = info.filename[len("mods/") :]
                dst = config.WOPC_MODS / rel_path
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(zf.read(info))

            # Collect unique mod names
            mod_names = {
                info.filename.split("/")[1] for info in mod_entries if info.filename.count("/") >= 2
            }
            extracted = sorted(mod_names)
            if extracted:
                logger.info("  extracted mods: %s", ", ".join(extracted))

            # Log skipped mods for transparency
            all_mod_names = {
                info.filename.split("/")[1]
                for info in zf.infolist()
                if info.filename.startswith("mods/") and info.filename.count("/") >= 2
            }
            skipped = sorted(all_mod_names & EXCLUDED_SCD_MODS)
            if skipped:
                logger.info("  skipped excluded mods: %s", ", ".join(skipped))
    except (zipfile.BadZipFile, OSError) as exc:
        logger.warning("  WARNING: could not extract mods from %s: %s", scd_path.name, exc)

    return extracted


# ---------------------------------------------------------------------------
# State management (UID-based)
# ---------------------------------------------------------------------------


def get_enabled_user_mod_uids() -> list[str]:
    """Return UIDs of user mods enabled in prefs [Mods] section."""
    parser = prefs.load_prefs()
    if not parser.has_section("Mods"):
        return []

    enabled = []
    for key, _ in parser.items("Mods"):
        if parser.getboolean("Mods", key, fallback=False):
            enabled.append(key)
    return enabled


def set_user_mod_enabled(uid: str, enabled: bool) -> None:
    """Enable or disable a user mod by UID. Persists to prefs."""
    parser = prefs.load_prefs()
    if not parser.has_section("Mods"):
        parser.add_section("Mods")
    parser.set("Mods", uid, str(enabled))
    prefs.save_prefs(parser)


def get_active_mod_uids() -> list[str]:
    """Return complete list of active mod UIDs for game launch.

    This is the single source of truth: all server mod UIDs (always active)
    plus user mods that are enabled in prefs.  Replaces the buggy
    ``server_uids + user_mods`` concatenation in wopc.py.
    """
    server_uids = [m.uid for m in discover_server_mods()]
    user_uids = get_enabled_user_mod_uids()
    return server_uids + user_uids


# ---------------------------------------------------------------------------
# Migration: folder names → UIDs in [Mods] prefs
# ---------------------------------------------------------------------------


def migrate_prefs_folder_to_uid() -> None:
    """One-time migration: convert [Mods] keys from folder names to UIDs.

    Scans WOPC/usermods/, finds UIDs for each folder name in prefs,
    rewrites [Mods] with UID keys. Adds [ModsMigrated] marker.
    """
    parser = prefs.load_prefs()

    # Already migrated?
    if parser.has_section("ModsMigrated"):
        return

    if not parser.has_section("Mods"):
        # Nothing to migrate — just mark done
        parser.add_section("ModsMigrated")
        parser.set("ModsMigrated", "version", "1")
        prefs.save_prefs(parser)
        return

    # Build folder_name_lower → uid lookup from user mods on disk
    folder_to_uid: dict[str, str] = {}
    for mod in discover_user_mods():
        folder_to_uid[mod.folder.lower()] = mod.uid

    # Collect current entries
    old_entries: list[tuple[str, bool]] = []
    for key, _ in parser.items("Mods"):
        enabled = parser.getboolean("Mods", key, fallback=False)
        old_entries.append((key, enabled))

    # Check if migration is needed (any key that looks like a folder name)
    needs_migration = False
    for key, _ in old_entries:
        # UIDs typically contain hyphens; folder names don't
        if "-" not in key and key in folder_to_uid:
            needs_migration = True
            break

    if not needs_migration:
        # Keys already look like UIDs — just mark done
        parser.add_section("ModsMigrated")
        parser.set("ModsMigrated", "version", "1")
        prefs.save_prefs(parser)
        return

    # Rewrite [Mods] with UIDs
    parser.remove_section("Mods")
    parser.add_section("Mods")

    for key, enabled in old_entries:
        uid = folder_to_uid.get(key.lower())
        if uid:
            parser.set("Mods", uid, str(enabled))
        else:
            logger.warning("Migration: dropping mod '%s' — no matching folder in usermods", key)

    parser.add_section("ModsMigrated")
    parser.set("ModsMigrated", "version", "1")
    prefs.save_prefs(parser)
    logger.info("Migrated [Mods] prefs from folder names to UIDs")
