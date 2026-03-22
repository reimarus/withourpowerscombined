"""Convert DDS game icons to PNG for launcher GUI use.

Sources: vendor/faf-ui/textures/ui/ (game asset DDS files)
Output:  launcher/gui/icons/ (pre-converted PNGs bundled in exe)

Run: .venv/Scripts/python.exe _convert_icons.py
"""

from pathlib import Path

from PIL import Image

ICONS_DIR = Path("launcher/gui/icons")
ICONS_DIR.mkdir(exist_ok=True)

VENDOR = Path("vendor/faf-ui/textures/ui")

# --- Map marker icons (strategic icons, 32x32) ---
MARKERS = {
    "marker_mass": VENDOR / "icons_strategic/structure_mass.dds",
    "marker_hydro": VENDOR / "icons_strategic/structure_energy.dds",
    "marker_commander": VENDOR / "icons_strategic/commander_generic.dds",
}

# --- Faction icons (copy PNGs, convert DDS for random) ---
FACTIONS = {
    "faction_aeon": VENDOR / "common/faction_icon-lg/aeon_med.png",
    "faction_cybran": VENDOR / "common/faction_icon-lg/cybran_med.png",
    "faction_uef": VENDOR / "common/faction_icon-lg/uef_med.png",
    "faction_seraphim": VENDOR / "common/faction_icon-lg/seraphim_med.png",
    "faction_random": VENDOR / "common/faction_icon-sm/random_ico.dds",
}

# --- Lobby chrome (9-slice frame borders, UEF style) ---
CHROME = {
    "frame_topleft": VENDOR / "UEF/scx_menu/lan-game-lobby/frame/topLeft.dds",
    "frame_top": VENDOR / "UEF/scx_menu/lan-game-lobby/frame/top.dds",
    "frame_topright": VENDOR / "UEF/scx_menu/lan-game-lobby/frame/topRight.dds",
    "frame_left": VENDOR / "UEF/scx_menu/lan-game-lobby/frame/left.dds",
    "frame_right": VENDOR / "UEF/scx_menu/lan-game-lobby/frame/right.dds",
    "frame_bottomleft": VENDOR / "UEF/scx_menu/lan-game-lobby/frame/bottomLeft.dds",
    "frame_bottom": VENDOR / "UEF/scx_menu/lan-game-lobby/frame/bottom.dds",
    "frame_bottomright": VENDOR / "UEF/scx_menu/lan-game-lobby/frame/bottomRight.dds",
}


def convert_all() -> None:
    """Convert all asset groups."""
    for group_name, group in [("Markers", MARKERS), ("Factions", FACTIONS), ("Chrome", CHROME)]:
        print(f"\n=== {group_name} ===")
        for name, src in group.items():
            if not src.exists():
                print(f"  MISS: {src}")
                continue
            try:
                img = Image.open(src)
                out = ICONS_DIR / f"{name}.png"
                img.save(out)
                print(f"  OK: {name}.png ({img.size[0]}x{img.size[1]})")
            except Exception as e:
                print(f"  FAIL: {name} - {e}")


if __name__ == "__main__":
    convert_all()
