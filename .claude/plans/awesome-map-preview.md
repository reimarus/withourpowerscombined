# Plan: Awesome Map Preview

**Branch:** `feature/awesome-map-preview`
**Goal:** Make the map the hero of the UI — large, interactive, data-rich — with resource overlays, spawn selection, a dedicated inspect window, and fast filtering.

## Context

The map preview currently shows a DDS-extracted image with basic metadata. Users reported:
- Filters break when changed (size/player mismatch between data and dropdown options)
- Map scanning feels slow
- No mass point or hydrocarbon overlays
- Can't select spawn positions on the map
- Can't assign player/AI starting locations
- **Map preview is too small** — same size as other UI elements, but the map is the most important visual on the screen
- **No detailed inspect view** — clicking the map should open a larger, detailed view

## Data Sources

Each SCFA map folder contains:
- `*_scenario.lua` — metadata: name, description, `size = {W, H}`, army list
- `*_save.lua` — all markers in `MasterChain._MASTERCHAIN_.Markers`:
  - `ARMY_N` — spawn positions, `position = VECTOR3(x, y, z)`
  - `Mass` markers — `type = STRING('Mass')`, `position = VECTOR3(x, y, z)`
  - `Hydrocarbon` markers — `type = STRING('Hydrocarbon')`, `position = VECTOR3(x, y, z)`
- `*.scmap` — binary with embedded 256×256 DDS preview (already extracted)

Coordinate mapping: marker `position.x` and `position.z` (z = vertical on map) map to pixel coordinates via `px = x / map_width * preview_width`.

## Phases

### Phase 1 — Fix Filters, Layout & Performance

**1a. Fix filter data mismatches**
- `_SIZE_LABELS` is missing `4096: "160km"` — maps with size 4096 show as `"4096"` which doesn't match any dropdown option
- Player count dropdown hardcodes `["2", "4", "6", "8", ...]` but real maps have 3, 5, 7 players — **build dropdown values dynamically** from actual scanned data
- Size dropdown should also be built dynamically from scanned data

**1b. Fix filter → preview breakage**
- When filters hide the currently active map, the preview goes blank and never recovers
- `_apply_map_filters` only calls `_update_map_preview` for the exact active map — if it's filtered out, nothing renders
- Fix: always show the preview for the active map (even if filtered out), OR auto-select the first visible map when the active one gets filtered away
- The filter must never leave the preview blank if maps exist

**1c. Make the map the HERO of the UI**
- Current `_PREVIEW_SIZE = 320` — too small, same visual weight as other elements
- The map should dominate the screen. Increase to **fill available vertical space** (use grid weight + sticky="nsew")
- Map preview panel (left column) should get `weight=3` vs map list `weight=1`
- Preview image should scale dynamically with window size, not be a fixed 320px
- Consider: map image fills the entire left panel, metadata overlays at bottom

**1d. Speed up map scanning**
- `scan_all_maps()` runs synchronously on UI thread — move to background thread with `self.after()` callback
- DDS extraction already caches PNGs (only slow on first run), but scanning 145 map dirs is still disk I/O
- Add a lightweight in-memory cache: scan once per session, store in `_all_maps`
  - Already partially done (`if not self._all_maps` guard), but ensure it works across screen switches

### Phase 2 — Parse Save Files for Markers

**2a. New function `parse_save_markers()` in `map_scanner.py`**

```python
@dataclass
class MapMarkers:
    armies: list[tuple[str, float, float]]    # (name, x, z)
    mass: list[tuple[float, float]]           # (x, z)
    hydro: list[tuple[float, float]]          # (x, z)
    map_width: int                            # from scenario size
    map_height: int                           # from scenario size
```

- Parse `_save.lua` with regex: find all marker blocks, extract `type` and `position` fields
- Pattern for ARMY: key matches `'ARMY_\d+'`, extract position VECTOR3
- Pattern for Mass: `type.*STRING.*Mass`, extract position from same block
- Pattern for Hydro: `type.*STRING.*Hydrocarbon`, extract position
- VECTOR3 pattern: `VECTOR3\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)`
- Locate `_save.lua` by: same directory as `_scenario.lua`, filename = `folder_save.lua`

**2b. Extend `MapInfo` dataclass**
- Add `markers: MapMarkers | None = None` field
- Parse markers alongside scenario (lazy or eager — eager is fine since we scan once)
- Add `map_width: int = 0` and `map_height: int = 0` to MapInfo from the size regex (already parsed but discarded for height)

### Phase 3 — Interactive Map Canvas

**3a. Replace static CTkImage with Tkinter Canvas**
- Use `tk.Canvas` (not CTkCanvas — doesn't exist) inside the preview panel
- Draw the preview image as background with `canvas.create_image()`
- Canvas allows click events and overlay drawing

**3b. Draw resource markers**
- Mass points: small circles (r=3px), white fill, positioned at `(x/map_w * canvas_w, z/map_h * canvas_h)`
- Hydro points: small circles (r=4px), green fill
- Toggle visibility with a checkbox ("Show Resources")
- Draw on top of preview image as canvas items

**3c. Draw spawn positions**
- Army markers: numbered circles (r=10px) with army number text
- Color-coded by current player slot assignment (match player slot colors)
- Unassigned slots: gray outline
- Position: same coordinate mapping as resources

**3d. Click-to-assign spawn positions**
- Click near a spawn marker → assign the currently selected player slot to that position
- "Currently selected" = last-clicked player slot in the slot panel, or auto-cycle
- Update `StartSpot` in player data when assigned
- Visual feedback: marker fills with player color, shows player name/AI name
- Right-click to unassign

### Phase 4 — Map Inspect Window

**4a. Popup inspect window on map click**
- Double-click or "Inspect" button on map preview opens a Toplevel window
- Large map image (600×600 or larger) filling the window
- All markers visible: mass (white dots), hydro (green dots), spawns (numbered colored circles)
- Zoomable via mouse wheel (scale the canvas, redraw markers at new scale)
- Legend showing marker types and counts (e.g., "42 mass, 6 hydro, 8 spawns")
- Map metadata: name, size, player count, description
- Close with Escape or X button

**4b. Spawn assignment from inspect window**
- Click a spawn marker to assign a player slot
- Shows which slots are assigned to which positions
- Changes sync back to the main window's player slots

### Phase 5 — Wire to Game Config

**5a. Update player slot ↔ spawn mapping**
- Player slots panel shows spawn assignment (e.g., "Slot 3" or map position indicator)
- Clicking a player slot highlights their spawn on the map
- `game_config.py` already uses `StartSpot` — wire the UI assignment through to config generation
- Default behavior: auto-assign sequentially (ARMY_1 → slot 1, etc.) — same as current

**5b. Multiplayer lobby sync**
- When host changes spawn assignments, broadcast via lobby protocol
- Guests see updated spawn markers on their preview
- (Lower priority — can ship without this initially)

## File Changes

| File | Changes |
|------|---------|
| `launcher/map_scanner.py` | Add `MapMarkers` dataclass, `parse_save_markers()`, extend `MapInfo`, fix `_SIZE_LABELS` |
| `launcher/gui/app.py` | Hero-sized canvas preview, marker overlays, click handlers, dynamic filters, async scan, inspect button |
| `launcher/gui/map_inspect.py` | (new) `MapInspectWindow` — Toplevel with zoomable canvas, full marker overlay, spawn assignment |
| `launcher/game_config.py` | Accept spawn assignments from UI (may already work via StartSpot) |
| `tests/test_map_scanner.py` | Tests for `parse_save_markers()`, edge cases, coordinate mapping |
| `tests/test_map_filters.py` | (new) Tests for filter logic, dynamic dropdown building |

## Implementation Order

1. Phase 1a+1b — Fix filters + preview breakage → stop the fragility
2. Phase 1c — Hero layout → map dominates the screen
3. Phase 1d — Async scan → responsive UI
4. Phase 2 — Parse markers → data layer
5. Phase 3a-3b — Canvas + resource overlay → visual wow factor
6. Phase 3c-3d — Spawn positions + click → interactive
7. Phase 4 — Map inspect window → detailed view
8. Phase 5a — Wire to config → functional
9. Tests throughout each phase

## Non-Goals (this PR)
- Multiplayer spawn sync (Phase 5b) — future PR
- 3D heightmap rendering — overkill
- Map downloading/browsing from online library — separate feature (#19 in backlog)
