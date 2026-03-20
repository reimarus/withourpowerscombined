"""WOPC Launcher Preferences Management.

Pure INI infrastructure for reading/writing wopc_prefs.ini.
Game, display, and player preferences live here.

Mod and content pack state management lives in ``launcher.mods``.
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
        "launch_mode": "solo",  # solo | multiplayer
        "host_port": "15000",
        "join_address": "",  # e.g. "192.168.1.50:15000"
        "expected_humans": "2",  # number of human players for host mode
        "scfa_path": "",  # auto-discovered or user-selected SCFA install path
    },
    "Mods": {
        # Mods are stored as keys with boolean values (Enabled/Disabled)
        # e.g., "brewlan": "True"
    },
    "Display": {"x": "1920", "y": "1080", "windowed": "False"},
    "Window": {"width": "1024", "height": "768"},
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


def get_minimap_enabled() -> bool:
    """Return whether the minimap should be visible on game launch."""
    parser = load_prefs()
    return parser.getboolean("Game", "minimap_enabled", fallback=True)


def get_player_faction() -> str:
    """Return the player's chosen faction (uef/aeon/cybran/seraphim/random)."""
    parser = load_prefs()
    return parser.get("Game", "player_faction", fallback="random")


def set_player_name(name: str) -> None:
    """Set the player's display name."""
    parser = load_prefs()
    parser.set("Game", "player_name", name.strip() or "Player")
    save_prefs(parser)


# ---------------------------------------------------------------------------
# Launch mode (solo / multiplayer)
# ---------------------------------------------------------------------------

VALID_LAUNCH_MODES = ("solo", "multiplayer")


def get_launch_mode() -> str:
    """Return the current launch mode: 'solo' or 'multiplayer'."""
    parser = load_prefs()
    mode = parser.get("Game", "launch_mode", fallback="solo")
    return mode if mode in VALID_LAUNCH_MODES else "solo"


def set_launch_mode(mode: str) -> None:
    """Set the launch mode. Must be 'solo' or 'multiplayer'."""
    if mode not in VALID_LAUNCH_MODES:
        mode = "solo"
    parser = load_prefs()
    parser.set("Game", "launch_mode", mode)
    save_prefs(parser)


def get_host_port() -> str:
    """Return the port for hosting a game."""
    parser = load_prefs()
    return parser.get("Game", "host_port", fallback="15000")


def set_host_port(port: str) -> None:
    """Set the host port."""
    parser = load_prefs()
    parser.set("Game", "host_port", port.strip() or "15000")
    save_prefs(parser)


def get_join_address() -> str:
    """Return the host address for joining (e.g. '192.168.1.50:15000')."""
    parser = load_prefs()
    return parser.get("Game", "join_address", fallback="")


def set_join_address(address: str) -> None:
    """Set the join address."""
    parser = load_prefs()
    parser.set("Game", "join_address", address.strip())
    save_prefs(parser)


# ---------------------------------------------------------------------------
# Expected humans (host mode)
# ---------------------------------------------------------------------------


def get_expected_humans() -> int:
    """Return the number of expected human players (2-8)."""
    parser = load_prefs()
    try:
        val = int(parser.get("Game", "expected_humans", fallback="2"))
        return max(2, min(8, val))
    except ValueError:
        return 2


def set_expected_humans(count: int) -> None:
    """Set the expected human player count (clamped to 2-8)."""
    count = max(2, min(8, count))
    parser = load_prefs()
    parser.set("Game", "expected_humans", str(count))
    save_prefs(parser)


# ---------------------------------------------------------------------------
# SCFA install path
# ---------------------------------------------------------------------------


def get_scfa_path() -> str:
    """Return the saved SCFA install path, or empty string."""
    parser = load_prefs()
    return parser.get("Game", "scfa_path", fallback="")


def set_scfa_path(path: str) -> None:
    """Save the SCFA install path."""
    parser = load_prefs()
    if not parser.has_section("Game"):
        parser.add_section("Game")
    parser.set("Game", "scfa_path", path.strip())
    save_prefs(parser)
