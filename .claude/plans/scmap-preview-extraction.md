# Plan: Extract Map Previews from .scmap Binary Files

## Context

Map previews don't render in the WOPC launcher. Only **1 out of 61 deployed maps** has a separate `_preview.png` file — the rest embed their preview as a DDS texture inside the `.scmap` binary. The current `map_scanner.py` only looks for `_preview.png/jpg` files on disk, so 60/61 maps show "No Preview".

SCFA's `.scmap` format stores a 256x256 BGRA8888 DDS preview image at a fixed offset (0x22) for version 2 maps. Pillow 12.1.1 (already bundled in the exe) can read DDS directly from a `BytesIO`. Verified: extracting the DDS blob and opening with `PIL.Image.open()` produces a perfect RGBA preview.

FAF handles this the same way — `SetTextureFromMap()` in the C++ engine extracts the DDS at runtime. Our Python launcher needs the equivalent.

---

## Implementation

### Step 1 — `launcher/map_scanner.py`: extract DDS preview from .scmap

Add a new function `_extract_scmap_preview()` that:

1. Opens the `.scmap` file in binary mode
2. Validates the `Map\x1a` magic header (4 bytes at offset 0)
3. Reads the DDS blob starting at offset 0x22:
   - Validates `DDS ` magic (4 bytes)
   - Parses DDS header to get width/height (int32 LE at offsets +12, +16 relative to DDS start)
   - Reads `128 + width * height * 4` bytes total (header + uncompressed BGRA pixel data)
4. Opens via `PIL.Image.open(BytesIO(dds_blob))`
5. Converts to RGB
6. Saves as `<mapfolder>/<mapfolder>_preview.png` (cached for next time)
7. Returns the `Path` to the saved PNG, or `None` on any failure

```python
def _extract_scmap_preview(map_dir: Path, folder_name: str) -> Path | None:
    """Extract the embedded DDS preview from a .scmap file and cache as PNG."""
```

**Key design decisions:**
- **Cache to PNG on first extract** — subsequent loads are instant via the existing preview_path logic. This is exactly what FAF map tools do.
- **PIL is optional** — if PIL is not available, return `None` (graceful degradation, same as current behavior)
- **No new dependencies** — uses `struct`, `io.BytesIO`, and PIL (already bundled)
- **Defensive parsing** — validate magic bytes, handle truncated files, catch all exceptions

### Step 2 — `launcher/map_scanner.py`: wire extraction into `parse_scenario()`

Modify the preview detection block (lines 89-96) to add a fallback:

```python
# Current: only looks for existing _preview.png/jpg files
# New: if no preview file found, try extracting from .scmap
if preview_path is None:
    scmap_file = map_dir / f"{folder_name}.scmap"
    if scmap_file.exists():
        preview_path = _extract_scmap_preview(map_dir, folder_name)
```

This preserves the existing behavior — if a `_preview.png` already exists (from a previous extraction or from a map that ships with one), it's used directly. The .scmap extraction only runs as a fallback.

### Step 3 — `launcher/map_scanner.py`: also scan usermaps

Currently `scan_all_maps()` only scans `config.WOPC_MAPS`. Add `config.WOPC_USERMAPS` as a second directory to scan, so user-added maps also get previews:

```python
def scan_all_maps() -> list[MapInfo]:
    results: list[MapInfo] = []
    for maps_dir in (config.WOPC_MAPS, config.WOPC_USERMAPS):
        if not maps_dir.exists():
            continue
        for d in sorted(maps_dir.iterdir()):
            # ... existing logic ...
    return results
```

### Step 4 — `tests/test_map_scanner.py`: add extraction tests

New test class `TestScmapPreviewExtraction`:

- `test_extracts_dds_from_valid_scmap` — build a minimal valid .scmap + DDS blob in `tmp_path`, verify PNG is created and `preview_path` points to it
- `test_returns_none_for_missing_scmap` — no .scmap file → returns `None`
- `test_returns_none_for_invalid_magic` — corrupt .scmap header → returns `None`
- `test_returns_none_for_truncated_file` — .scmap too small → returns `None`
- `test_skips_extraction_when_preview_exists` — existing `_preview.png` → no .scmap read
- `test_returns_none_when_pil_unavailable` — mock `_PIL_AVAILABLE = False` → returns `None`
- `test_parse_scenario_uses_scmap_fallback` — full integration: scenario file + .scmap, no preview PNG → `parse_scenario()` returns `MapInfo` with `preview_path` set

Build a test helper to construct minimal .scmap files:
```python
def _make_scmap(path: Path, width: int = 1, height: int = 1) -> None:
    """Write a minimal valid .scmap with a 1x1 DDS preview."""
    # Map header: "Map\x1a" + version 2 + padding to offset 0x22
    # DDS header: 128 bytes (magic + standard header for uncompressed BGRA)
    # Pixel data: width * height * 4 bytes
```

### Step 5 — `tests/test_map_scanner.py`: test usermaps scanning

- `test_scan_includes_usermaps` — create maps in both `WOPC_MAPS` and `WOPC_USERMAPS` tmp directories, verify both are returned

---

## Files Modified

| File | Change |
|------|--------|
| `launcher/map_scanner.py` | Add `_extract_scmap_preview()`, wire into `parse_scenario()`, scan usermaps |
| `tests/test_map_scanner.py` | Add extraction tests + usermaps test |

**No changes to `app.py`** — the existing `_update_map_preview()` already handles `preview_path` correctly. Once `map_scanner.py` populates it via .scmap extraction, previews will render automatically.

---

## .scmap Binary Format Reference

```
Offset  Size  Field
0x00    4     Magic: "Map\x1a"
0x04    4     Version (int32 LE, always 2 for FA maps)
0x08    4     Unknown (0xBEEFFEED sentinel)
0x0C    16    Header floats (map dimensions etc.)
0x1C    6     Unknown
0x22    4     DDS magic: "DDS "
0x26    124   DDS header (standard DirectDraw Surface format)
0xA2    W*H*4 DDS pixel data (BGRA8888 uncompressed, 256x256 = 262144 bytes)
```

Total DDS blob: 262272 bytes (128 header + 262144 pixels)
End of DDS data: offset 0x400A2

---

## Verification

```bash
# Unit tests
pytest tests/test_map_scanner.py -v

# Full suite
python .claude/utils/run_checks.py

# Manual: launch GUI in dev mode, verify map previews render
.venv/Scripts/python.exe -c "from launcher.gui.app import launch_gui; launch_gui()"
# → Select maps in the list → preview images should appear for all maps
# → Check both solo and multiplayer lobby preview panels
```
