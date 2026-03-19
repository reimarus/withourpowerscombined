"""Map metadata scanner for the WOPC launcher.

Parses ``_scenario.lua`` files inside each map folder to extract
display name, player count, map size, and description for the UI.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from launcher import config

logger = logging.getLogger("wopc.map_scanner")

# Map size values used by SCFA (width/height in ogrids, 1 ogrid = 51.2m)
_SIZE_LABELS: dict[int, str] = {
    128: "5km",
    256: "10km",
    512: "20km",
    1024: "40km",
    2048: "81km",
}


@dataclass
class MapInfo:
    """Parsed metadata for a single map."""

    folder_name: str
    display_name: str
    max_players: int
    size_label: str
    description: str
    is_campaign: bool
    preview_path: Path | None = None


def _extract_lua_string(content: str, key: str) -> str:
    """Extract a string value from a Lua assignment like ``key = 'value'``."""
    # Matches: key = 'value' or key = "value"
    pattern = rf"{key}\s*=\s*['\"](.+?)['\"]"
    match = re.search(pattern, content)
    return match.group(1) if match else ""


def _extract_lua_number(content: str, key: str) -> int:
    """Extract an integer value from a Lua assignment like ``key = 8``."""
    pattern = rf"{key}\s*=\s*(\d+)"
    match = re.search(pattern, content)
    return int(match.group(1)) if match else 0


def parse_scenario(scenario_path: Path) -> MapInfo | None:
    """Parse a ``_scenario.lua`` file and return a :class:`MapInfo`.

    Returns ``None`` if the file cannot be parsed.
    """
    try:
        content = scenario_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning("Cannot read %s: %s", scenario_path, e)
        return None

    display_name = _extract_lua_string(content, "name")
    description = _extract_lua_string(content, "description")

    # Player count: SCFA uses ``Configurations.standard.teams[1].armies``
    # which is a Lua table.  A simpler heuristic: count ARMY_ entries.
    army_count = len(re.findall(r"'ARMY_\d+'", content))
    if army_count == 0:
        army_count = len(re.findall(r'"ARMY_\d+"', content))

    # Map size: look for ``size = {width, height}``
    size_match = re.search(r"size\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}", content)
    if size_match:
        width = int(size_match.group(1))
        size_label = _SIZE_LABELS.get(width, f"{width}")
    else:
        size_label = "?"

    folder_name = scenario_path.parent.name
    if not display_name:
        display_name = folder_name

    # SCFA campaign maps use specific prefixes
    is_cam = "CA_" in folder_name or folder_name.startswith(("SCMA_", "X1CA_"))

    # Preview image: SCFA convention is <folder>_preview.png alongside scenario file
    preview_path: Path | None = None
    map_dir = scenario_path.parent
    for ext in (".png", ".PNG", ".jpg", ".JPG"):
        candidate = map_dir / f"{folder_name}_preview{ext}"
        if candidate.exists():
            preview_path = candidate
            break

    return MapInfo(
        folder_name=folder_name,
        display_name=display_name,
        max_players=army_count,
        size_label=size_label,
        description=description,
        is_campaign=is_cam,
        preview_path=preview_path,
    )


def scan_all_maps() -> list[MapInfo]:
    """Scan ``WOPC_MAPS`` and return metadata for every valid map."""
    maps_dir = config.WOPC_MAPS
    if not maps_dir.exists():
        return []

    results: list[MapInfo] = []
    for d in sorted(maps_dir.iterdir()):
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.name.endswith("_scenario.lua"):
                info = parse_scenario(f)
                if info:
                    results.append(info)
                break  # only one scenario per map folder

    return results
