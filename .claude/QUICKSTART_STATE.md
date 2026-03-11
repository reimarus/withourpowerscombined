# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-10
> If session runs out of tokens, a new session can pick up from here.

## Current State: QUICKSTART WORKS END-TO-END (GUI → game). Sim init fails on missing LOUD content.

### End-to-end verified (GUI launcher → game):
1. **Build exe:** `python build_exe.py` → `dist/WOPC-Launcher.exe` (~18 MB)
2. **Run exe:** `dist/WOPC-Launcher.exe` (or dev: `from launcher.gui.app import launch_gui; launch_gui()`)
3. User selects map (Caldera) → clicks PLAY MATCH
4. Python writes `wopc_game_config.lua` + passes `/wopcquickstart /wopcconfig <path>`
5. Engine loads patched uimain.lua → detects quickstart → calls quickstart.Launch()
6. quickstart.lua reads config, creates LobbyComm, calls LaunchGame()
7. Engine enters simulation → loads map → loads blueprints → hits LOUD content blocker

### IMPORTANT: Rebuilding the exe
After ANY code changes to `launcher/`, `init/`, or `gamedata/`:
```
python build_exe.py    # rebuilds dist/WOPC-Launcher.exe
```
The exe bundles Python + assets at build time. Stale exe = old code!

### Current blocker: Missing LOUD gameplay content
The sim crashes at `buffdefinitions.lua` because LOUD-specific categories (like `MOBILE`) aren't defined.
This is because `bundled/gamedata/*.scd` (LOUD gameplay content) isn't in the repo.
**This is a content packaging issue, NOT a quickstart issue.**

### All commits pushed (feature/phase-6-advanced-launcher):
1. `3d1cc33` — Add quickstart system: bypass lobby, launch directly into match
2. `fe7b66e` — Refactor init_generator and add player_name preference
3. `7c111de` — Fix quickstart: pass config path via /wopcconfig command-line arg
4. `98a500f` — Fix quickstart: OwnerID must be string, not number
5. `03e8a17` — Update quickstart breadcrumbs
6. `c8ba228` — Document quickstart architecture + VFS dual search order

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
