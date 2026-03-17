# Plan: Mod System Consolidation (Backlog #13)

## Problem

Mod handling is fragmented across 5 files with inconsistent identification:

| File | What it does | Identification |
|------|-------------|----------------|
| `prefs.py` | `get_server_mod_uids()` parses UIDs; `get_enabled_mods()` returns **folder names** | Mixed UID + name |
| `init_generator.py` | Content pack toggling, `CONTENT_PACK_LABELS` | SCD filename |
| `deploy.py` | `_extract_mods_from_scd()` extracts mods from SCDs | Directory name |
| `game_config.py` | Writes UID list to Lua config | UID |
| `wopc.py` | Collects `server_uids + user_mods` | **BUG: mixes UIDs + folder names** |

**Critical bug** in `wopc.py:172`:
```python
server_uids = prefs.get_server_mod_uids()    # returns UIDs ✓
user_mods = prefs.get_enabled_mods()           # returns FOLDER NAMES ✗
all_mod_uids = server_uids + user_mods         # mixed list → quickstart.lua can't resolve
```

## Solution

New `launcher/mods.py` module that owns the full mod lifecycle. Single source of truth for all mod operations.

## Design

### New dataclass

```python
@dataclasses.dataclass(frozen=True)
class ModInfo:
    uid: str           # from mod_info.lua
    name: str          # display name from mod_info.lua
    folder: str        # directory name on disk
    location: str      # "server" | "user"
    mod_info_path: Path
```

### Public API — `launcher/mods.py`

```python
# --- Discovery ---
def parse_mod_info(mod_info_path: Path) -> ModInfo | None
def discover_server_mods() -> list[ModInfo]     # scan WOPC_MODS/
def discover_user_mods() -> list[ModInfo]        # scan WOPC_USERMODS/
def discover_all_mods() -> list[ModInfo]         # server + user

# --- State Management (UID-based) ---
def get_enabled_user_mod_uids() -> list[str]     # from [Mods] prefs
def set_user_mod_enabled(uid: str, enabled: bool) -> None
def get_active_mod_uids() -> list[str]           # server + enabled user = THE SINGLE CALL

# --- Content Packs ---
CONTENT_PACK_LABELS: dict[str, str]              # moved from init_generator.py
def get_toggleable_scds() -> list[str]
def get_enabled_packs() -> list[str]
def set_pack_state(scd_name: str, enabled: bool) -> None

# --- Extraction ---
def extract_mods_from_scd(scd_path: Path) -> list[str]   # moved from deploy.py

# --- Migration ---
def migrate_prefs_folder_to_uid() -> None        # one-time [Mods] key conversion
```

### What moves where

**Into `mods.py` (new)**:
- From `prefs.py`: `_UID_RE`, `_parse_mod_uid()`, `get_server_mod_uids()`, `get_enabled_mods()`, `set_mod_state()`
- From `init_generator.py`: `CONTENT_PACK_LABELS`, `CORE_SCDS`, `_FIXED_POSITION_SCDS`, `get_toggleable_scds()`, `get_enabled_packs()`, `set_pack_state()`
- From `deploy.py`: `_extract_mods_from_scd()`

**Stays in place**:
- `prefs.py`: `load_prefs()`, `save_prefs()`, map/player/display prefs (pure INI infra)
- `init_generator.py`: `generate_init_lua()` — becomes a pure template renderer that calls `mods.get_enabled_packs()`
- `deploy.py`: everything except `_extract_mods_from_scd()`, calls `mods.extract_mods_from_scd()` instead
- `game_config.py`: no changes (already receives `active_mod_uids` param)
- `quickstart.lua`: no changes (already works with UIDs)

### Migration strategy for user prefs

Current `[Mods]` section stores folder names: `brewlan = True`.
New format stores UIDs: `9e8ea941-c306-... = True`.

`migrate_prefs_folder_to_uid()`:
1. Check for `[ModsMigrated] version = 1` — if present, skip
2. For each key in `[Mods]`, scan `WOPC_USERMODS/` to find matching folder → parse UID
3. Rewrite keys from folder name to UID
4. Add `[ModsMigrated] version = 1` marker
5. If folder name has no matching mod on disk, drop entry + log warning

Called at startup (in `gui/app.py` and `wopc.py:cmd_launch()`).

## Implementation Steps

### Step 1: Create `mods.py` with core discovery
- `ModInfo` dataclass
- `parse_mod_info()` — parse uid + name from mod_info.lua
- `discover_server_mods()`, `discover_user_mods()`, `discover_all_mods()`
- Write `tests/test_mods.py` with `TestParseModInfo` and `TestDiscovery`
- **Run tests — green**

### Step 2: Move content pack management
- Move `CONTENT_PACK_LABELS`, `CORE_SCDS`, `_FIXED_POSITION_SCDS`, `get_toggleable_scds()`, `get_enabled_packs()`, `set_pack_state()` from `init_generator.py` to `mods.py`
- Update `init_generator.py` to `from launcher import mods` and delegate
- Migrate tests from `test_init_generator.py` (`TestGetToggleableScds`, `TestPackState`) to `test_mods.py`
- Update `TestGenerateInitLua` mocks
- **Run tests — green**

### Step 3: Move mod extraction
- Move `_extract_mods_from_scd()` from `deploy.py` to `mods.py` as `extract_mods_from_scd()`
- Update `deploy.py:_acquire_content_packs()` to call `mods.extract_mods_from_scd()`
- Migrate any extraction tests from `test_deploy.py`
- **Run tests — green**

### Step 4: Add state management + migration
- `get_enabled_user_mod_uids()`, `set_user_mod_enabled()`, `get_active_mod_uids()`
- `migrate_prefs_folder_to_uid()` — one-time prefs conversion
- Write `TestStateManagement` and `TestMigration` in `test_mods.py`
- **Run tests — green**

### Step 5: Fix the bug in `wopc.py`
- Replace lines 170-172 with `all_mod_uids = mods.get_active_mod_uids()`
- Remove dead imports (`prefs.get_server_mod_uids`, `prefs.get_enabled_mods`)
- Update `test_wopc.py` to mock `mods.get_active_mod_uids()` instead of separate prefs calls
- **Run tests — green**

### Step 6: Update GUI
- `app.py:_refresh_mods_list()` → use `mods.discover_user_mods()`, `mods.get_enabled_user_mod_uids()`, `mods.set_user_mod_enabled()`
- Content pack section → use `mods.CONTENT_PACK_LABELS`, `mods.get_toggleable_scds()`, `mods.get_enabled_packs()`, `mods.set_pack_state()`
- `_update_play_summary()` → use `mods.get_active_mod_uids()`
- Call `mods.migrate_prefs_folder_to_uid()` at startup
- **Run tests — green**

### Step 7: Clean up dead code
- Remove from `prefs.py`: `get_enabled_mods()`, `set_mod_state()`, `get_server_mod_uids()`, `_parse_mod_uid()`, `_UID_RE`
- Remove from `test_prefs.py`: `TestServerModUids`, mod-related assertions in `TestSetPrefs`
- **Run full suite — green**

### Step 8: Final validation
- `pytest` — all pass, coverage ≥ 70%
- `ruff check launcher/ tests/`
- `mypy launcher/`
- Update `docs/backlog.md` — mark item #13 as done, update #17 (user mod activation now fixed)
- Commit, push, PR

## Files touched

| File | Action |
|------|--------|
| `launcher/mods.py` | **NEW** — central mod module |
| `tests/test_mods.py` | **NEW** — comprehensive tests |
| `launcher/prefs.py` | Remove mod functions (keep INI infra) |
| `launcher/init_generator.py` | Remove content pack state; delegate to mods.py |
| `launcher/deploy.py` | Remove `_extract_mods_from_scd()`; call `mods.extract_mods_from_scd()` |
| `launcher/wopc.py` | Fix bug: use `mods.get_active_mod_uids()` |
| `launcher/gui/app.py` | Update imports to use mods.py API |
| `tests/test_prefs.py` | Remove migrated tests |
| `tests/test_init_generator.py` | Remove migrated tests, update mocks |
| `tests/test_deploy.py` | Remove migrated tests, update mocks |
| `tests/test_wopc.py` | Update mocks |
| `docs/backlog.md` | Mark #13 done, update #17 |

## Risks

- **GUI import timing**: `mods.py` imports `prefs.py` and `config.py`. `gui/app.py` currently imports `init_generator` at top level. Switching to `mods` should be drop-in since the dependency direction is the same.
- **ConfigParser case folding**: ConfigParser lowercases keys. UIDs contain uppercase hex. We must call `parser.optionxform = str` before writing UID keys, or accept lowercased UIDs (quickstart.lua comparison should be case-insensitive).
- **Migration on first run**: If user has mods enabled by folder name but the mod folder was deleted, migration drops those entries. This is correct behavior (can't enable a mod that doesn't exist).
