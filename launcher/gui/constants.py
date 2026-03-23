"""Shared constants and lookup tables for the WOPC launcher GUI.

Centralizes all color, faction, AI, and game option definitions that were
previously scattered across app.py.  Every UI → engine value conversion
lives here so there's exactly one place to maintain the mappings.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Player colors — 8 slots matching SCFA's engine palette order
# ---------------------------------------------------------------------------

PLAYER_COLORS: list[tuple[str, str]] = [
    ("#FF0000", "Red"),
    ("#0000FF", "Blue"),
    ("#18DAE8", "Teal"),
    ("#DFBF00", "Yellow"),
    ("#FF6600", "Orange"),
    ("#9161FF", "Purple"),
    ("#FF88FF", "Pink"),
    ("#00FF00", "Green"),
]

# ---------------------------------------------------------------------------
# Faction / AI / slot limits
# ---------------------------------------------------------------------------

FACTION_NAMES: list[str] = ["Random", "UEF", "Aeon", "Cybran", "Seraphim"]

AI_DISPLAY_NAMES: list[str] = [
    "Easy",
    "Medium",
    "Adaptive",
    "Rush",
    "Turtle",
    "Tech",
    "Random",
]

MAX_SLOTS: int = 16

# ---------------------------------------------------------------------------
# Game option definitions: (key, label, values, default)
# ---------------------------------------------------------------------------

GAME_OPTION_DEFS: list[tuple[str, str, list[str], str]] = [
    (
        "Victory",
        "Victory",
        ["Demoralization", "Supremacy", "Assassination", "Sandbox"],
        "Demoralization",
    ),
    ("UnitCap", "Unit Cap", ["500", "1000", "1500", "2000", "4000"], "1500"),
    ("FogOfWar", "Fog of War", ["Explored", "Unexplored", "None"], "Explored"),
    ("GameSpeed", "Game Speed", ["Normal", "Fast", "Adjustable"], "Normal"),
    ("Share", "Share", ["FullShare", "ShareUntilDeath"], "FullShare"),
]

VICTORY_DESCRIPTIONS: dict[str, str] = {
    "Demoralization": "Destroy 70% of an enemy's units to eliminate them",
    "Supremacy": "Destroy all enemy structures and engineers to win",
    "Assassination": "Kill the enemy Commander (ACU) to eliminate them",
    "Sandbox": "No victory condition — play until you quit",
}

# ---------------------------------------------------------------------------
# UI display name → engine value mappings
# ---------------------------------------------------------------------------

VICTORY_MAP: dict[str, str] = {
    "Demoralization": "demoralization",
    "Supremacy": "domination",
    "Assassination": "eradication",
    "Sandbox": "sandbox",
}

FOG_MAP: dict[str, str] = {
    "Explored": "explored",
    "Unexplored": "unexplored",
    "None": "none",
}

SPEED_MAP: dict[str, str] = {
    "Normal": "normal",
    "Fast": "fast",
    "Adjustable": "adjustable",
}

# ---------------------------------------------------------------------------
# Canvas / UI tuning constants
# ---------------------------------------------------------------------------

PREVIEW_MIN: int = 320
LOBBY_PREVIEW_SIZE: int = 280
DRAG_THRESHOLD: int = 8

PLAY_LABELS: dict[str, str] = {
    "SOLO": "PLAY MATCH",
    "MULTIPLAYER": "PLAY MATCH",
}

# ---------------------------------------------------------------------------
# Color conversion helpers
# ---------------------------------------------------------------------------


def color_name_to_hex(name: str) -> str:
    """Convert a color display name (or hex string) to its hex value.

    Returns the first color's hex if no match is found.
    """
    if name.startswith("#"):
        return name
    for hex_val, cname in PLAYER_COLORS:
        if cname == name:
            return hex_val
    return PLAYER_COLORS[0][0]


def color_hex_to_index(val: str) -> int:
    """Convert a color name or hex to the nearest 1-based SCFA engine color index.

    Tries exact match first (name or hex), then falls back to nearest RGB
    distance for arbitrary hex values from the HSV color picker.
    """
    # Direct name or hex match
    for i, (hex_val, cname) in enumerate(PLAYER_COLORS):
        if cname == val or hex_val == val:
            return i + 1
    # Nearest color by RGB distance for arbitrary hex values
    if val.startswith("#") and len(val) == 7:
        r = int(val[1:3], 16)
        g = int(val[3:5], 16)
        b = int(val[5:7], 16)
        best_i, best_d = 0, float("inf")
        for i, (hex_val, _) in enumerate(PLAYER_COLORS):
            pr = int(hex_val[1:3], 16)
            pg = int(hex_val[3:5], 16)
            pb = int(hex_val[5:7], 16)
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_d:
                best_i, best_d = i, d
        return best_i + 1
    return 1


def color_index_to_hex(index: int) -> str:
    """Convert a 1-based SCFA color index to a hex string.

    Clamps to valid range [1, len(PLAYER_COLORS)].
    """
    clamped = max(1, min(index, len(PLAYER_COLORS)))
    return PLAYER_COLORS[clamped - 1][0]


def game_options_to_engine(raw_opts: dict[str, str]) -> dict[str, str]:
    """Convert UI game option display values to engine format.

    Applies the VICTORY_MAP, FOG_MAP, and SPEED_MAP transformations.
    """
    opts: dict[str, str] = {}
    for key, val in raw_opts.items():
        if key == "Victory":
            val = VICTORY_MAP.get(val, val.lower())
        elif key == "FogOfWar":
            val = FOG_MAP.get(val, val.lower())
        elif key == "GameSpeed":
            val = SPEED_MAP.get(val, val.lower())
        opts[key] = val
    return opts
