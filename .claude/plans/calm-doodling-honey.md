# Fix match loading bugs — ZIP case normalization

## Context

The game loads to the map (sim timers run, AI detected, 568 unit BPs loaded) but commanders don't spawn and UI has errors. **Root cause:** filenames in `faf_ui.scd` are stored with mixed case (`lua/sim/Unit.lua`, `lua/AI/AIAddBuilderTable.lua`) but FAF's `import()` function lowercases all paths before lookup (line 116 of `import.lua`: `name = name:lower()`). ZIP archives use case-sensitive lookups, so `lua/sim/unit.lua` ≠ `lua/sim/Unit.lua` — the import silently fails and returns nil.

**833 of 1264 files** in faf_ui.scd have mixed-case names. This one bug causes the entire error cascade:
- `Unit.lua` can't be imported → ValidateBone is nil → weapons fail
- `StructureUnit.lua` can't be imported → defaultunits.lua fails → all structure units broken
- `CConstructionUnit.lua` can't be imported → cybranunits.lua fails → Cybran commander doesn't spawn
- Score UI crashes (nil concat), LazyVar circular deps

**Secondary bug:** FAF source `StructureUnit.lua` line 67 has `end` inside a `--` comment, so a function never closes. This is a real syntax bug in FAF's source repo.

## The Fix

### Step 1: Normalize filenames to lowercase in faf_ui.scd build

**File:** `launcher/deploy.py`, lines 156-159

Current:
```python
arcname = file_path.relative_to(faf_ui_src)
zf.write(file_path, arcname)
```

Fix — convert arcname to lowercase with forward slashes:
```python
arcname = str(file_path.relative_to(faf_ui_src)).replace("\\", "/").lower()
zf.write(file_path, arcname)
```

This matches the pattern already used at lines 167-173 for the vanilla merge dedup check.

### Step 2: Normalize vanilla lua.scd merged files too

**File:** `launcher/deploy.py`, line 175

Currently `zf.writestr(info, vanilla_zf.read(info))` preserves the original mixed-case filename from vanilla lua.scd. Fix: write with a lowercase ZipInfo.

```python
lowered_info = copy(info)
lowered_info.filename = normalized  # already lowercase from line 173
zf.writestr(lowered_info, vanilla_zf.read(info))
```

### Step 3: Normalize wopc_patches.scd build

**File:** `launcher/deploy.py`, lines 189-192

Same fix as Step 1:
```python
arcname = str(file_path.relative_to(wopc_patches_src)).replace("\\", "/").lower()
zf.write(file_path, arcname)
```

### Step 4: Update _patch_scd() calls to use lowercase paths

**File:** `launcher/deploy.py`, lines 208, 216, 223

Change all arcname strings to lowercase:
- `"lua/ui/uimain.lua"` — already lowercase ✓
- `"lua/sim/units/StructureUnit.lua"` → `"lua/sim/units/structureunit.lua"`

### Step 5: Update tests

**File:** `tests/test_deploy.py`

Update any assertions that check ZIP contents to expect lowercase filenames.

## Files to modify

| File | Change |
|------|--------|
| `launcher/deploy.py` | Lowercase normalize arcnames in 3 SCD build locations + patch calls |
| `tests/test_deploy.py` | Update assertions for lowercase filenames |

## Verification

1. `pytest tests/ -x -q` — all pass
2. `ruff check && mypy launcher/` — clean
3. `wopc setup` — deploys, check log for "merged N vanilla lua.scd files"
4. Inspect faf_ui.scd: `python -c "import zipfile; z=zipfile.ZipFile(r'C:\ProgramData\WOPC\gamedata\faf_ui.scd'); mixed=[n for n in z.namelist() if n!=n.lower() and not n.endswith('/')]; print(f'Mixed-case: {len(mixed)}')"` → should be 0
5. Launch game, check WOPC.log:
   - No "access to nonexistent global variable" errors
   - No "Error importing" errors
   - Commanders spawn
   - ValidateBone errors gone
