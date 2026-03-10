# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-10
> If session runs out of tokens, a new session can pick up from here.

## Current State: uimain.lua crash fix needed

### What's DONE (code written, tests pass, NOT yet committed):
- `launcher/game_config.py` — fixed double-brace bug (plain `{` not `{{`)
- `launcher/wopc.py` — writes game config + passes `/wopcquickstart` flag
- `launcher/deploy.py` — added `_patch_scd()` to patch lua.scd in-place
- `gamedata/wopc_patches/lua/wopc/quickstart.lua` — LobbyComm-based launcher
- `tests/test_wopc.py` — updated for `/wopcquickstart` in args
- `tests/test_game_config.py` — new file, 11 tests

### What WORKS:
- lua.scd patching mechanism (our uimain.lua IS loaded — confirmed by LOG in game)
- Game config Lua file generation (all edge cases tested)
- All 105 tests pass, 78% coverage, ruff clean

### What's BROKEN (next fix):
- `gamedata/wopc_patches/lua/ui/uimain.lua` — missing `SetupUI()` and ~15 other engine-expected functions
- Crash: `Error running '/lua/ui/uimain.lua:SetupUI': call expected but got nil`

### How to fix:
- Copy the full FAF uimain.lua from `vendor/faf-ui/lua/ui/uimain.lua` (303 lines)
- Add diagnostic LOG at top: `LOG("WOPC: uimain.lua loaded from wopc_patches.scd")`
- Add `/wopcquickstart` check at start of `StartHostLobbyUI()`
- All other functions stay identical to FAF original

### How to BACK OUT if needed:
- Remove `/wopcquickstart` from cmd args in `launcher/wopc.py` → game uses standard lobby
- Or: revert `_patch_scd()` call in `launcher/deploy.py` → lua.scd stays unmodified
- The quickstart code paths are all guarded by `HasCommandLineArg("/wopcquickstart")`

### Key discovery (VFS mount order):
- Engine C++ loads files with **first-added = highest priority** (opposite of Lua `import()`)
- lua.scd is mounted early (position 3), wopc_patches.scd late (position 7)
- So engine always loads lua.scd's uimain.lua unless we patch lua.scd itself
- `_patch_scd()` in deploy.py rewrites lua.scd's uimain.lua in-place during `wopc setup`

### Files changed across sessions (uncommitted):
| File | Change |
|------|--------|
| `gamedata/wopc_patches/lua/ui/uimain.lua` | Rewrite with full FAF functions + WOPC quickstart |
| `gamedata/wopc_patches/lua/wopc/quickstart.lua` | New — LobbyComm-based game launcher |
| `launcher/game_config.py` | Fixed double-brace bug in Lua output |
| `launcher/wopc.py` | Added write_game_config + /wopcquickstart flag |
| `launcher/deploy.py` | Added _patch_scd() + lua.scd patching |
| `tests/test_wopc.py` | Updated for /wopcquickstart in args |
| `tests/test_game_config.py` | New — 11 tests for game config |
