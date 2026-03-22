"""Map metadata scanner for the WOPC launcher.

Parses ``_scenario.lua`` files inside each map folder to extract
display name, player count, map size, and description for the UI.

When no separate preview image exists, the scanner extracts the embedded
DDS preview from the ``.scmap`` binary file and caches it as PNG.
"""

import io
import logging
import re
import struct
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
    4096: "160km",
}

# .scmap binary format constants
_SCMAP_MAGIC = b"Map\x1a"
_DDS_MAGIC = b"DDS "
_DDS_OFFSET = 0x22  # DDS preview starts at this fixed offset in version 2 .scmap files
_DDS_HEADER_SIZE = 128  # 4-byte magic + 124-byte header

try:
    from PIL import Image as _PilImage  # type: ignore[import-not-found]

    _PIL_AVAILABLE = True
except ImportError:
    _PilImage = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False


@dataclass
class MapMarkers:
    """Spawn positions, mass deposits, and hydrocarbon markers parsed from _save.lua."""

    armies: list[tuple[str, float, float]]  # (name, x, z)
    mass: list[tuple[float, float]]  # (x, z)
    hydro: list[tuple[float, float]]  # (x, z)


@dataclass
class MapInfo:
    """Parsed metadata for a single map."""

    folder_name: str
    display_name: str
    max_players: int
    size_label: str
    description: str
    is_campaign: bool
    map_width: int = 0
    map_height: int = 0
    preview_path: Path | None = None
    markers: MapMarkers | None = None


def _extract_scmap_preview(map_dir: Path, folder_name: str) -> Path | None:
    """Extract the embedded DDS preview from a .scmap file and cache as PNG.

    SCFA ``.scmap`` files contain a 256x256 BGRA8888 DDS preview image at
    offset 0x22.  This function reads the DDS blob, converts it to PNG via
    Pillow, and saves it alongside the map for future use.

    Returns the path to the cached PNG, or ``None`` on any failure.
    """
    if not _PIL_AVAILABLE:
        return None

    scmap_path = map_dir / f"{folder_name}.scmap"
    if not scmap_path.exists():
        return None

    try:
        with scmap_path.open("rb") as f:
            magic = f.read(4)
            if magic != _SCMAP_MAGIC:
                logger.debug("Invalid .scmap magic in %s", scmap_path)
                return None

            f.seek(_DDS_OFFSET)
            dds_magic = f.read(4)
            if dds_magic != _DDS_MAGIC:
                logger.debug("No DDS header at offset 0x%X in %s", _DDS_OFFSET, scmap_path)
                return None

            # Parse DDS header for dimensions (int32 LE at offsets +12 and +16
            # relative to DDS start, i.e. after magic + dwSize + dwFlags)
            f.seek(_DDS_OFFSET + 12)
            height, width = struct.unpack("<II", f.read(8))

            if width == 0 or height == 0 or width > 4096 or height > 4096:
                logger.debug("Invalid DDS dimensions %dx%d in %s", width, height, scmap_path)
                return None

            # Read full DDS blob (header + uncompressed BGRA pixel data)
            dds_size = _DDS_HEADER_SIZE + width * height * 4
            f.seek(_DDS_OFFSET)
            dds_blob = f.read(dds_size)

            if len(dds_blob) < dds_size:
                logger.debug("Truncated DDS data in %s", scmap_path)
                return None

        img = _PilImage.open(io.BytesIO(dds_blob))
        rgb = img.convert("RGB")

        out_path = map_dir / f"{folder_name}_preview.png"
        rgb.save(out_path)
        logger.debug("Extracted preview from %s", scmap_path.name)
        return out_path

    except Exception as exc:
        logger.warning("Failed to extract preview from %s: %s", scmap_path, exc)
        return None


_VECTOR3_RE = re.compile(r"VECTOR3\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)")

_MARKER_TYPE_RE = re.compile(r"\['type'\]\s*=\s*STRING\(\s*'([^']+)'\s*\)")


def _iter_marker_blocks(content: str) -> list[tuple[str, str]]:
    """Extract (name, body) pairs for each marker block in a _save.lua file.

    Handles nested braces by counting brace depth from each marker opening.
    """
    # Find all ['Name'] = { patterns and extract the body until matching }
    opener = re.compile(r"\['([^']+)'\]\s*=\s*\{")
    results: list[tuple[str, str]] = []
    for m in opener.finditer(content):
        name = m.group(1)
        start = m.end()
        depth = 1
        pos = start
        while pos < len(content) and depth > 0:
            ch = content[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            pos += 1
        if depth == 0:
            results.append((name, content[start : pos - 1]))
    return results


def parse_save_markers(save_path: Path) -> MapMarkers | None:
    """Parse a ``_save.lua`` file for army spawns, mass, and hydro markers.

    Returns ``None`` if the file cannot be read or parsed.
    """
    try:
        content = save_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning("Cannot read %s: %s", save_path, e)
        return None

    armies: list[tuple[str, float, float]] = []
    mass: list[tuple[float, float]] = []
    hydro: list[tuple[float, float]] = []

    for name, body in _iter_marker_blocks(content):
        pos_match = _VECTOR3_RE.search(body)
        if not pos_match:
            continue
        x = float(pos_match.group(1))
        z = float(pos_match.group(3))  # z = vertical axis on 2D map

        # Army spawn positions: key starts with ARMY_
        if name.startswith("ARMY_"):
            armies.append((name, x, z))
            continue

        # Check type field for Mass / Hydrocarbon
        type_match = _MARKER_TYPE_RE.search(body)
        if not type_match:
            continue
        marker_type = type_match.group(1)

        if marker_type == "Mass":
            mass.append((x, z))
        elif marker_type == "Hydrocarbon":
            hydro.append((x, z))

    if not armies and not mass and not hydro:
        return None

    # Sort armies by number for consistent ordering
    armies.sort(key=lambda a: int(a[0].split("_")[1]) if a[0].split("_")[1].isdigit() else 0)

    return MapMarkers(armies=armies, mass=mass, hydro=hydro)


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
    map_width = 0
    map_height = 0
    size_match = re.search(r"size\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}", content)
    if size_match:
        map_width = int(size_match.group(1))
        map_height = int(size_match.group(2))
        size_label = _SIZE_LABELS.get(map_width, f"{map_width}")
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

    # Fallback: extract DDS preview from .scmap binary
    if preview_path is None:
        preview_path = _extract_scmap_preview(map_dir, folder_name)

    # Parse markers from _save.lua (mass, hydro, army spawns)
    markers: MapMarkers | None = None
    for save_candidate in map_dir.iterdir():
        if save_candidate.name.endswith("_save.lua"):
            markers = parse_save_markers(save_candidate)
            break

    return MapInfo(
        folder_name=folder_name,
        display_name=display_name,
        max_players=army_count,
        size_label=size_label,
        description=description,
        is_campaign=is_cam,
        map_width=map_width,
        map_height=map_height,
        preview_path=preview_path,
        markers=markers,
    )


def scan_all_maps() -> list[MapInfo]:
    """Scan ``WOPC_MAPS`` and ``WOPC_USERMAPS`` for every valid map."""
    results: list[MapInfo] = []
    for maps_dir in (config.WOPC_MAPS, config.WOPC_USERMAPS):
        if not maps_dir.exists():
            continue
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
