# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-17
> If session runs out of tokens, a new session can pick up from here.

## Current State: Multiplayer launcher Phase 1 complete. Three launch modes (SOLO/HOST/JOIN) working.

### What works now:
1. **Solo mode** (quickstart bypass): GUI → select map → PLAY MATCH → game enters sim
2. **Host mode**: GUI → select map → HOST GAME → SCFA opens FAF lobby → friends can join
3. **Join mode**: GUI → enter host address → JOIN GAME → SCFA connects to host's lobby
4. **Content packs**: TotalMayhem (62 FAF-compatible units) toggleable in launcher
5. **Content icons**: Auto-extracted from LOUD's textures.scd during deploy

### IMPORTANT: Rebuilding the exe
After ANY code changes to `launcher/`, `init/`, or `gamedata/`:
```
python build_exe.py    # rebuilds dist/WOPC-Launcher.exe
```
The exe bundles Python + assets at build time. Stale exe = old code!

### Launch modes (implemented in wopc.py):
| Mode | Engine args | Behaviour |
|------|------------|-----------|
| **Solo** | `/hostgame udp 15000 {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, no lobby |
| **Host** | `/hostgame udp {port} {name} WOPC {map}` | FAF lobby opens, friends connect |
| **Join** | `/joingame udp {address} {name}` | Connects to host's FAF lobby |

### GUI launcher features:
- Mode selector (SOLO / HOST / JOIN segmented button) in sidebar
- Conditional port entry (HOST) or host address entry (JOIN)
- Player name entry in PLAYER SETTINGS panel
- Map selector hidden in JOIN mode (host controls the map)
- Button text changes: PLAY MATCH / HOST GAME / JOIN GAME

### Key blocker fix: `/players` nil crash in uimain.lua
Lines 94+115 crashed when `/players` arg is absent (required for host/join mode):
```lua
-- Fixed: nil guard on GetCommandLineArg
local playersArg = GetCommandLineArg("/players", 1)
local autoStart = playersArg and playersArg[1] >= 2
```

### How to BACK OUT if needed:
- Remove `/wopcquickstart` from cmd args in `launcher/wopc.py` → game uses standard lobby
- Or: revert `_patch_scd()` call in `launcher/deploy.py` → lua.scd stays unmodified
- All quickstart code is guarded by `HasCommandLineArg("/wopcquickstart")`

### Player Slots (Phase 2 — done):
- Dynamic slot list in main content area (left half of lower panel)
- Human player always in slot 1 (cannot be removed)
- "+ Add AI" button creates new AI slots with difficulty, faction, and team dropdowns
- Each AI slot has a remove button (✕)
- `get_ai_opponents()` collects slot data as list of dicts for `game_config.py`
- Passed through `cmd_launch(ai_opponents=...)` to `write_game_config()`

### Game Options (Phase 3 — done):
- Options panel in right half of lower panel
- Victory, Unit Cap, Fog of War, Game Speed, Share
- `get_game_options()` collects options, merged with minimap pref in `cmd_launch()`
- Passed through to `write_game_config(game_options=...)` → quickstart.lua

### Next steps:
- End-to-end multiplayer test (host + join on LAN)
- Persist player slot config across sessions (prefs serialization)
- Persist game options across sessions

### Test results: 168 tests pass, ~81% coverage, ruff clean
