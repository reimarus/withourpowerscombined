# Merge vanilla lua.scd files into faf_ui.scd

## Context

FAF-only mode init changes are working: quickstart fires, 568 unit blueprints load, no more
buffdefinitions.lua crash. But the sim initialization fails because FAF's `simInit.lua` imports
files that exist in vanilla `lua.scd` but NOT in FAF's source repo (`vendor/faf-ui/`).

**Root cause:** The real FAF distribution (`.nx2` files) merges vanilla `lua.scd` content with
FAF's modifications into a single package. Our `faf_ui.scd` build only packages FAF's source
files, missing 102 vanilla files that FAF's code references.

**Missing files breakdown:**
- `lua/ai/` — 89 files (AI utilities, base templates, Sorian AI, etc.)
- `lua/editor/` — 10 files (editor tools)
- `lua/sim/` — 2 files
- `lua/ui/` — 1 file

**Specific errors from game log:**
- `Error importing '/lua/ai/aiutilities.lua'` (in vanilla lua.scd as `lua/AI/aiutilities.lua`)
- `Error importing '/lua/ai/gridreclaim.lua'` (FAF-specific, not in vanilla either — needs stub)
- `Error importing '/lua/ai/sorianutilities.lua'` (FAF-specific, not in vanilla — needs stub)
- `Error importing '/lua/ai/aiattackutilities.lua'` (in vanilla lua.scd)

## The Fix

### Step 1: Modify faf_ui.scd build to include vanilla lua.scd files

In `deploy.py`, after packaging FAF source files into `faf_ui.scd`, also extract files from
vanilla SCFA's `lua.scd` that don't already exist in the archive. This fills the gap between
"FAF source" and "FAF distribution".

**File:** `C:\Users\roskv\wopc\launcher\deploy.py`

The build step currently:
```python
with zipfile.ZipFile(faf_ui_dst, "w", zipfile.ZIP_DEFLATED) as zf:
    for target_dir in ["lua", "modules", "ui", "loc"]:
        # ... add FAF source files
```

Change to:
```python
with zipfile.ZipFile(faf_ui_dst, "w", zipfile.ZIP_DEFLATED) as zf:
    # 1. Add FAF source files (these take priority)
    for target_dir in ["lua", "modules", "ui", "loc"]:
        # ... add FAF source files (same as before)

    # 2. Merge vanilla lua.scd files that FAF doesn't replace
    vanilla_lua_scd = config.SCFA_STEAM / "gamedata" / "lua.scd"
    if vanilla_lua_scd.exists():
        existing = {name.lower() for name in zf.namelist()}
        with zipfile.ZipFile(vanilla_lua_scd, "r") as vanilla:
            for info in vanilla.infolist():
                if not info.is_dir() and info.filename.lower() not in existing:
                    zf.writestr(info, vanilla.read(info))
        logger.info("  merged %d vanilla files from lua.scd", merged_count)
```

Key design points:
- FAF files are written first → they take priority for any filename collisions
- Vanilla files only fill gaps (case-insensitive filename comparison)
- This matches what the real FAF distribution does

### Step 2: Handle FAF-specific files not in vanilla

Two files referenced by FAF code don't exist in vanilla lua.scd either:
- `lua/ai/gridreclaim.lua` — FAF has `lua/ui/game/GridReclaim.lua` (wrong path for sim import)
- `lua/ai/sorianutilities.lua` — not found anywhere

These are likely provided in FAF's distribution via a different mechanism (possibly built/generated).
For now, we can create empty stubs in `gamedata/wopc_patches/` that return empty tables, preventing
the crash without affecting gameplay (these are AI utilities, and our quickstart uses a simple AI).

**File:** `C:\Users\roskv\wopc\gamedata\wopc_patches\lua\ai\gridreclaim.lua`
**File:** `C:\Users\roskv\wopc\gamedata\wopc_patches\lua\ai\sorianutilities.lua`

These stubs will be in `wopc_patches.scd` which is mounted AFTER `faf_ui.scd`, so for Lua
`import()` (last-added wins) they'll shadow any version. But they won't affect engine C++
`doscript` calls (first-added wins) — which is fine because the engine doesn't doscript these
AI files directly.

### Step 3: Update tests

- Update `test_deploy.py` to verify vanilla lua.scd merging behavior
- Test that FAF files take priority over vanilla files with same name

### Step 4: Add SCFA_GAMEDATA constant to config.py

Add `SCFA_GAMEDATA = SCFA_STEAM / "gamedata"` for cleaner access to vanilla SCDs.

## Files to modify

| File | Change |
|------|--------|
| `launcher/deploy.py` | Merge vanilla lua.scd into faf_ui.scd build |
| `launcher/config.py` | Add `SCFA_GAMEDATA` constant |
| `gamedata/wopc_patches/lua/ai/gridreclaim.lua` | New: empty stub |
| `gamedata/wopc_patches/lua/ai/sorianutilities.lua` | New: empty stub |
| `tests/test_deploy.py` | Add tests for vanilla merge behavior |

## Verification

1. `pytest tests/ -x -q` — all pass
2. `ruff check && mypy launcher/` — clean
3. `wopc setup` — rebuilds faf_ui.scd with vanilla files merged
4. Verify: `faf_ui.scd` now contains `lua/AI/aiutilities.lua` etc.
5. Launch game → sim should initialize without AI import errors
6. If sim loads fully → we have raw FAF running from our launcher!
