# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-10
> If session runs out of tokens, a new session can pick up from here.

## Current State: QUICKSTART WORKS! Sim init fails on missing LOUD content.

### Quickstart flow (VERIFIED WORKING):
1. Python launcher writes `wopc_game_config.lua` + passes `/wopcquickstart /wopcconfig <path>`
2. Engine loads our patched uimain.lua from lua.scd (via `_patch_scd()`)
3. `StartHostLobbyUI()` detects `/wopcquickstart`, calls `quickstart.Launch()`
4. quickstart.lua reads config, creates LobbyComm, builds gameInfo, calls `LaunchGame()`
5. Engine enters simulation — loads simInit.lua

### Current blocker: Missing LOUD gameplay content
The sim crashes at `buffdefinitions.lua` because LOUD-specific categories (like `MOBILE`) aren't defined.
This is because `bundled/gamedata/*.scd` (LOUD gameplay content) isn't in the repo.
**This is a content packaging issue, NOT a quickstart issue.**

### All commits pushed (feature/phase-6-advanced-launcher):
1. `3d1cc33` — Add quickstart system: bypass lobby, launch directly into match
2. `fe7b66e` — Refactor init_generator and add player_name preference
3. `7c111de` — Fix quickstart: pass config path via /wopcconfig command-line arg
4. `98a500f` — Fix quickstart: OwnerID must be string, not number

### Key fixes applied:
- uimain.lua: full FAF copy (303 lines) with WOPC quickstart hook in StartHostLobbyUI
- quickstart.lua: InitFileDir → /wopcconfig command-line arg (UI Lua state doesn't have InitFileDir)
- quickstart.lua: OwnerID as string, not number (C++ LaunchGame expects string peer IDs)
- quickstart.lua: removed broken fallback (port already bound after HostGame)
- deploy.py: _patch_scd() to patch lua.scd (engine C++ uses first-added priority)
- deploy.py: combined nested `with` statement (ruff SIM117)
- game_config.py: fixed double-brace bug in Lua output

### How to BACK OUT if needed:
- Remove `/wopcquickstart` from cmd args in `launcher/wopc.py` → game uses standard lobby
- Or: revert `_patch_scd()` call in `launcher/deploy.py` → lua.scd stays unmodified
- All quickstart code is guarded by `HasCommandLineArg("/wopcquickstart")`

### Next steps:
- Package LOUD gameplay content (bundled/gamedata/*.scd) so the sim can initialize
- OR: test with vanilla SCFA content only (no LOUD) to verify quickstart fully works
- The quickstart Lua code is complete and working

### Test results: 105 tests pass, 78.49% coverage, ruff clean, mypy clean
