"""WOPC Launcher Preferences Management.

Handles reading and writing the user's active map and enabled mods
to the wopc_prefs.ini configuration file.
"""

import configparser
import logging

from launcher import config

logger = logging.getLogger("wopc.prefs")

PREFS_FILE = config.WOPC_ROOT / "wopc_prefs.ini"

# Default configuration structure
DEFAULT_PREFS = {
    "Game": {
        "active_map": "",
        "player_name": "Player",
        "minimap_enabled": "True",
        "player_faction": "random",
    },
    "Mods": {
        # Mods are stored as keys with boolean values (Enabled/Disabled)
        # e.g., "brewlan": "True"
    },
    "Display": {"x": "1920", "y": "1080", "windowed": "False"},
}


def load_prefs() -> configparser.ConfigParser:
    """Load the user preferences from the INI file.

    Creates the file with defaults if it does not exist.
    """
    parser = configparser.ConfigParser()

    if PREFS_FILE.exists():
        try:
            # Read UTF-8 encoded INI file first
            parser.read(PREFS_FILE, encoding="utf-8")
        except configparser.Error as e:
            logger.warning("Failed to parse %s, using defaults: %s", PREFS_FILE, e)

    # Merge defaults for any missing sections/keys
    modified = False
    for section, keys in DEFAULT_PREFS.items():
        if not parser.has_section(section):
            parser.add_section(section)
            modified = True
        for key, default_val in keys.items():
            if not parser.has_option(section, key):
                parser.set(section, key, default_val)
                modified = True

    if modified:
        save_prefs(parser)

    return parser


def save_prefs(parser: configparser.ConfigParser) -> None:
    """Save the current configuration state to the INI file."""
    try:
        # Ensure the directory exists (it should, after `wopc setup`)
        PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PREFS_FILE.open("w", encoding="utf-8") as f:
            parser.write(f)
    except OSError as e:
        logger.error("Failed to save preferences to %s: %s", PREFS_FILE, e)


def get_active_map() -> str:
    """Return the currently selected map, or an empty string."""
    parser = load_prefs()
    return parser.get("Game", "active_map", fallback="")


def set_active_map(map_path: str) -> None:
    """Set the active map."""
    parser = load_prefs()
    if not parser.has_section("Game"):
        parser.add_section("Game")
    parser.set("Game", "active_map", str(map_path))
    save_prefs(parser)


def get_player_name() -> str:
    """Return the player's display name."""
    parser = load_prefs()
    return parser.get("Game", "player_name", fallback="Player")


def get_enabled_mods() -> list[str]:
    """Return a list of folder names for all explicitly enabled mods."""
    parser = load_prefs()
    if not parser.has_section("Mods"):
        return []

    enabled = []
    for mod_name, _ in parser.items("Mods"):
        if parser.getboolean("Mods", mod_name, fallback=False):
            enabled.append(mod_name)
    return enabled


def get_minimap_enabled() -> bool:
    """Return whether the minimap should be visible on game launch."""
    parser = load_prefs()
    return parser.getboolean("Game", "minimap_enabled", fallback=True)


def get_player_faction() -> str:
    """Return the player's chosen faction (uef/aeon/cybran/seraphim/random)."""
    parser = load_prefs()
    return parser.get("Game", "player_faction", fallback="random")


def set_mod_state(mod_name: str, enabled: bool) -> None:
    """Enable or disable a specific user mod."""
    parser = load_prefs()
    if not parser.has_section("Mods"):
        parser.add_section("Mods")

    parser.set("Mods", mod_name, str(enabled))
    save_prefs(parser)
