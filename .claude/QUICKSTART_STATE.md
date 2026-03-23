# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-23
> If session runs out of tokens, a new session can pick up from here.

## Current State: Phase 6 ✅ Complete — Stabilization & Refactoring Next

### What works now:
1. **Solo mode** (quickstart bypass): GUI → select map/players/options → PLAY MATCH → game enters sim
2. **Multiplayer mode** (quickstart bypass): GUI → MULTIPLAYER → game browser (LAN + internet discovery) or Create Game → lobby room (map, players, options, chat) → LAUNCH → all players enter sim via quickstart
3. **Content packs**: TotalMayhem + BlackOps units toggleable in launcher
4. **Content icons**: Downloaded from GitHub Releases during deploy
5. **Internet game discovery**: Firebase relay (wopc-75b65) for finding games worldwide
6. **Interactive map preview**: Canvas-based with tinted commander icons, mass/hydro strategic icons, click-to-select spawn, zoom/pan
7. **Player slot management**: Add/remove AI, color picker (HSV wheel), team assignment, faction selection, spawn position selection on minimap
8. **Auto-updater**: GitHub Releases → download → exe replace → restart
9. **Spawn position mapping**: Players array index == ARMY_N, gap-filling with civilian entries (v2.01.0032)

### CRITICAL ARCHITECTURE NOTE:
**Our launcher IS the lobby.** ALL launch modes (solo, host, join) use `/wopcquickstart`. The in-game lobby UI is NEVER shown. All multiplayer coordination (player list, game options, map selection, chat, ready state, file transfer) happens in the Python launcher over TCP. The engine just receives the final config and starts the match.

### CRITICAL ENGINE RULES:
- **ARMY assignment**: `PlayerOptions[N]` → `ARMY_N` → spawns at `ARMY_N` map marker. Array index determines spawn, NOT the StartSpot field.
- **Team numbering**: Engine Team 1 = no team (FFA). UI teams 1-4 map to engine teams 2-5 (+1 offset). See CLAUDE.md Rule #14.
- **OwnerID**: Must be a string (peer ID), not a number. ALL slots (human + AI) use hostPeerID.

### Launch modes (implemented in wopc.py):
| Mode | Engine args | Behaviour |
|------|------------|-----------|
| **Solo** | `/hostgame udp 15000 {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, single player |
| **Host** | `/hostgame udp {port} {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, launcher coordinated players via TCP |
| **Join** | `/joingame udp {address} {name} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, launcher received config from host via TCP |

### GUI screens (three-screen layout):
| Screen | When shown | Key widgets |
|--------|-----------|-------------|
| **Solo** | SOLO mode selected | Map canvas (icon markers, spawn selection), player slots, game options, PLAY MATCH button |
| **Browser** | MULTIPLAYER selected | LAN + internet game list, CREATE GAME, Direct Connect (collapsed) |
| **Lobby** | After creating/joining game | Map panel, player list, game options, chat + action bar (LEAVE / LAUNCH) |

### Key modules:
- `launcher/discovery.py` — UDP LAN game discovery (BeaconBroadcaster + BeaconListener)
- `launcher/relay.py` — Firebase REST API for internet game registration/discovery
- `launcher/lobby.py` — TCP lobby server/client, JSON-line protocol
- `launcher/file_transfer.py` — map auto-download over TCP
- `launcher/map_scanner.py` — scenario + save file parsing, DDS extraction, marker extraction
- `launcher/gui/app.py` — **4,320 lines, 105 methods — refactor planned** (see `.claude/plans/`)
- `launcher/game_config.py` — generates `wopc_game_config.lua` with gap-filling for ARMY mapping
- `launcher/updater.py` — GitHub Releases auto-update (subprocess + os._exit on Windows)
- `launcher/prefs.py` — INI-based preferences (player name, faction, color, map, display)

### Active plan: Solo Launcher Refactor
See `.claude/plans/gentle-enchanting-bengio.md` for the full plan:
- Extract `models.py` (PlayerSlotManager), `constants.py` (lookup tables), `map_canvas.py` (renderer), `slot_widget.py` (unified slot UI)
- Fix 3 bugs: map black screen after ready check, send logs failure, color palette mismatch
- Target: app.py 4,320 → ~2,500 lines, 80%+ test coverage on extracted modules

### Known bugs (see backlog items 50-54):
- Map black screen after ready check / auto-update
- "Send Logs" failure after auto-update
- Player color mismatch between launcher and in-game
- Auto-updater map list not loading after self-restart
- Civilian filler armies — investigate idle commander spawns

### Branch: `main` — Latest release: v2.01.0032. No active feature branch.

### Recent releases:
- **v2.01.0032**: Spawn position fix — Players array gap-filling with civilian entries
- **v2.01.0031**: Diagnostic spawn logging, team offset fix (+1 for engine)
- **v2.01.0030**: Player color persistence in prefs, spawn swap logic, filter reset fix
- **v2.01.0029**: Auto-updater fix (subprocess + os._exit on Windows)
- **v2.01.0028**: Player slot improvements (remove button, color picker, team changes)
- **v2.01.0027**: Icon-based map markers, HSV color picker, unified solo/lobby layout, player name in slots
