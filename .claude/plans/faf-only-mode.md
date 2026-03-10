# Get raw FAF running from launcher into a match

## Context

The quickstart pipeline works E2E (GUI → launcher → engine → sim init), but the sim crashes at `buffdefinitions.lua` because we're mounting **LOUD's `lua.scd`** which expects LOUD-specific content. The user's insight: get vanilla FAF working first, then layer LOUD on top.

**Root cause analysis:**
- LOUD's `lua.scd` is mounted at VFS position 4 (early)
- FAF's `faf_ui.scd` is mounted at position 16 (late)
- Engine C++ `doscript` uses **first-added priority** → loads LOUD's `simInit.lua`, not FAF's
- LOUD's `simInit.lua` imports LOUD's `buffdefinitions.lua` which expects LOUD categories (`MOBILE`)
- Without LOUD content packs mounted, these categories are nil → crash

**Key finding:** `faf_ui.scd` (1157 Lua files) is a complete superset of both `mohodata.scd` and vanilla `lua.scd`'s core files. FAF intentionally replaces vanilla `lua.scd` with its own code. We don't need LOUD's `lua.scd` at all for FAF-only mode.

## The Fix

### Step 1: Stop mounting LOUD's `lua.scd` in FAF-only mode

In `init_generator.py`, `CORE_SCDS` currently includes `lua.scd`:
```python
CORE_SCDS = frozenset({"lua.scd", "loc_US.scd"})
```

Change: Remove `lua.scd` from `CORE_SCDS` since FAF's `faf_ui.scd` provides all the Lua code. Keep `loc_US.scd` for localization.

**File:** `C:\Users\roskv\wopc\launcher\init_generator.py`

### Step 2: Mount vanilla SCFA `units.scd` from Steam

FAF's `init_faf.lua` mounts vanilla `units.scd` from the Steam install. Our init template currently only mounts visual/audio assets from Steam (textures, effects, env, projectiles, props, meshes). We need to add `units.scd` and several other gameplay SCDs that FAF expects.

From FAF's `allowedAssetsScd` list, these vanilla SCDs should be mounted:
- `units.scd` — **unit blueprints + meshes** (essential, 568 unit BPs)
- `mods.scd` — base mod support
- `objects.scd` — in-game objects

These are already mounted: `textures.scd`, `effects.scd`, `env.scd`, `projectiles.scd`, `props.scd`, `meshes.scd`

NOT needed (FAF replaces them): `lua.scd`, `mohodata.scd`, `moholua.scd`, `schook.scd`

**File:** `C:\Users\roskv\wopc\launcher\init_generator.py` — add to the vanilla SCFA content section

### Step 3: Mount `loc_US.scd` from vanilla SCFA (not LOUD)

Currently we mount LOUD's `loc_US.scd` from WOPC gamedata. But in FAF-only mode, we should mount vanilla SCFA's `loc_US.scd` (which has the proper FA localization strings). FAF also allows this (`allowedAssetsScd["loc_us.scd"] = true`).

Change: Move `loc_US.scd` from the CORE_SCDS gamedata mount to the vanilla SCFA section.

**File:** `C:\Users\roskv\wopc\launcher\init_generator.py`

### Step 4: Handle VFS priority for engine C++ doscript

Since `faf_ui.scd` is mounted late (position 6 in our template) but the engine C++ uses first-added priority, `doscript '/lua/simInit.lua'` etc. must find FAF's files. After removing LOUD's `lua.scd`, the earliest SCD with Lua files would be `faf_ui.scd` — but vanilla assets mounted in step 5 come before it.

**Critical:** Vanilla SCFA does NOT have `simInit.lua` in `units.scd` — it's in `lua.scd` (which we're not mounting) and `mohodata.scd` (which FAF also skips). So `faf_ui.scd` will be the ONLY source for these system files. We need to ensure it's found.

Actually, since we removed the only competing source (`lua.scd`), `faf_ui.scd` will be the only SCD providing `lua/simInit.lua`. The engine will find it regardless of priority position.

### Step 5: Update `deploy.py` — don't copy LOUD `lua.scd` in FAF-only mode

Currently `deploy.py` copies all `bundled/gamedata/*.scd` to WOPC. LOUD's `lua.scd` is one of them. In FAF-only mode (no content packs enabled), we should still copy it (in case user enables LOUD packs later), but the init generator simply won't mount it.

**No change needed in deploy.py** — the init generator controls what gets mounted.

### Step 6: Update tests

- Update `test_init_generator.py` to reflect the new `CORE_SCDS` and vanilla mounts
- Verify the generated init file mounts `units.scd` from SCFA

**File:** `C:\Users\roskv\wopc\tests\test_init_generator.py`

## Files to modify

| File | Change |
|------|--------|
| `launcher/init_generator.py` | Remove `lua.scd` from CORE_SCDS; add vanilla `units.scd`, `mods.scd`, `objects.scd`, `loc_US.scd` to SCFA mounts |
| `tests/test_init_generator.py` | Update assertions for new mount structure |

## Verification

1. `pytest tests/ -x -q` — all pass
2. `ruff check && mypy launcher/` — clean
3. `wopc setup` — deploys cleanly
4. `wopc launch` or GUI PLAY MATCH — game launches
5. Check `WOPC.log`:
   - Should NOT see `*AI DEBUG` LOUD messages in sim init
   - Should see FAF's simInit.lua loading
   - Should NOT crash at buffdefinitions.lua
   - Should load 568+ unit blueprints from vanilla units.scd
6. If sim loads fully → we have raw FAF running!
