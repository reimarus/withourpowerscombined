# Fix Black Ops Commander Bugs (Backlog #2)

## Context

After integrating `blackops.scd` as a content pack, the game extracts **two**
mods from it: `BlackOpsUnleashed` (95 unit pack) and `BlackopsACUs` (ACU
replacement mod). The ACU mod is LOUD-specific — it replaces vanilla commanders
with custom units (`eel0001`, `eal0001`, `erl0001`, `esl0001`) that inherit
from `TWalkingLandUnit` and depend on LOUD's extended `Unit` base class.

In WOPC's FAF-only mode, these LOUD-specific methods don't exist, causing
cascading failures:

- `PlayCommanderWarpInEffect` — nil (LOUD method, not in FAF)
- `SetValidTargetsForCurrentLayer` — nil (LOUD method)
- `OnMotionHorzEventChange` — nil (LOUD override missing)
- `SetPrecedence` on `BuildArmManipulator` — nil
- `Destroy` method missing from unit
- Multiple weapon `OnCreate` errors (nil `dist`, missing `MuzzleSalvoSize`)

Result: commander spawns but is broken — invisible (bones hidden by
`OnStopBeingBuilt` with no way to unhide), unresponsive (errors abort command
processing), and the warp-in effect fails.

**BlackOpsUnleashed** (the actual unit pack) has **zero** dependency on
BlackopsACUs and works independently.

## Solution

Exclude `BlackopsACUs` from SCD extraction. Keep `BlackOpsUnleashed`.

This is done by adding an exclusion list to `mods.py:extract_mods_from_scd()`
so specific mod folders inside SCDs are skipped during extraction. The
exclusion is configurable so future content packs can also exclude
LOUD-specific mods.

## Implementation

### Branch: `fix/blackops-acus`

### Step 1: Add mod exclusion to `launcher/mods.py`

Add a module-level constant and update `extract_mods_from_scd()`:

```python
# Mods inside content pack SCDs that must NOT be extracted.
# BlackopsACUs replaces vanilla ACUs with LOUD-specific units that crash
# in FAF-only mode (missing LOUD base class methods).
EXCLUDED_SCD_MODS: frozenset[str] = frozenset({"BlackopsACUs"})
```

In `extract_mods_from_scd()`, filter out entries whose mod folder is in
`EXCLUDED_SCD_MODS`:

```python
mod_entries = [
    info for info in zf.infolist()
    if info.filename.startswith("mods/")
    and not info.is_dir()
    and info.filename.split("/")[1] not in EXCLUDED_SCD_MODS
]
```

Log a message when mods are skipped.

### Step 2: Delete extracted BlackopsACUs from deployed dir

Add a cleanup step to `deploy.py` setup flow that removes previously-extracted
excluded mods from `WOPC/mods/`. This handles existing installs that already
have BlackopsACUs extracted.

In `launcher/deploy.py`, in `_acquire_content_packs()` (or wherever mod
extraction is called), after extraction:

```python
# Clean up excluded mods from previous extractions
for excluded in mods.EXCLUDED_SCD_MODS:
    excluded_path = config.WOPC_MODS / excluded
    if excluded_path.exists():
        shutil.rmtree(excluded_path)
        logger.info("  removed excluded mod: %s", excluded)
```

### Step 3: Update tests

**`tests/test_mods.py`** — add to `TestExtraction`:

- `test_extract_skips_excluded_mods`: Create SCD with both `mods/BlackopsACUs/`
  and `mods/BlackOpsUnleashed/` entries. Verify only `BlackOpsUnleashed` is
  extracted.
- `test_excluded_mods_constant`: Verify `BlackopsACUs` is in `EXCLUDED_SCD_MODS`.

**`tests/test_deploy.py`** — add:

- `test_cleanup_excluded_mods`: Verify pre-existing excluded mod dirs are removed.

### Step 4: Update backlog

In `docs/backlog.md`, update item #2:
- Mark BlackopsACUs issue as fixed (excluded from extraction)
- Note remaining work: missing strategic icons for some BlackOpsUnleashed units

## Files to modify

| File | Change |
|------|--------|
| `launcher/mods.py` | Add `EXCLUDED_SCD_MODS`, filter in `extract_mods_from_scd()` |
| `launcher/deploy.py` | Add cleanup of excluded mods after extraction |
| `tests/test_mods.py` | Add exclusion tests to `TestExtraction` |
| `tests/test_deploy.py` | Add cleanup test |
| `docs/backlog.md` | Update item #2 |

## Verification

1. `pytest tests/ -x -q` — all pass
2. `ruff check launcher/ tests/` — clean
3. Delete `C:\ProgramData\WOPC\mods\BlackopsACUs\` manually, run `wopc setup`
   — verify it does NOT reappear
4. Run `wopc launch` — commander spawns normally (vanilla ACU), no warp-in
   errors, responsive to commands
5. BlackOps units (from BlackOpsUnleashed) still appear in build menu
6. Some `brb*` units may still have placeholder icons — that's a separate
   issue (missing strategic icon assets, not blocking)
