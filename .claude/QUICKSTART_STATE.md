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

### Active plan: Bug Fixes + SupCom UI Skinning
See `C:\Users\roskv\.claude\plans\glimmering-riding-cocke.md` for the full plan:
- **PR 1 (bugs):** Fix civilian filler armies (#54), spawn auto-assign on map load (#57), structured launch logging (#60)
- **PR 2 (skinning):** 9-slice metallic borders from SCFA assets, faction icons in player slots, compact player settings layout (#48), button border accents
- Mark Send Logs (#51) as fixed (Firebase rules updated in console)

### Known bugs (see backlog):
- Civilian filler armies — investigate idle commander spawns (#54)
- Spawn markers uncolored on initial map load (#57)
- Multiplayer TCP port unreachable for remote players (#59, deferred)
- Launcher log missing structured launch params (#60)

### Branch: `fix/bugs-50-52-and-hook` — bug fixes #50, #52, #53
- Fixed map black screen (#50): always-rescan map list + deferred canvas redraw
- Fixed player color mismatch (#52): aligned PLAYER_COLORS with engine's GameColors.lua (8→19 colors)
- Fixed map list after restart (#53): covered by #50's always-rescan fix

### Recent merges:
- **PR #64** (v2.01.0034): Multiplayer join fix — 6 bugs in TCP handshake, thread safety, joiner config

### Completed refactor (PR #63, merged):
- `launcher/gui/constants.py` — lookup tables, color conversions, game option mappings (171 lines)
- `launcher/gui/models.py` — `PlayerSlot` + `PlayerSlotManager`, zero widget deps (226 lines)
- `launcher/gui/map_canvas.py` — canvas rendering, zoom/pan, markers, spawn interaction (531 lines)
- `app.py`: 4,320 → 3,784 lines (536 extracted)

### Recent releases:
- **v2.01.0033**: Refactor — extracted constants, models, map_canvas from app.py
- **v2.01.0032**: Spawn position fix — Players array gap-filling with civilian entries
- **v2.01.0031**: Diagnostic spawn logging, team offset fix (+1 for engine)
- **v2.01.0030**: Player color persistence in prefs, spawn swap logic, filter reset fix
- **v2.01.0029**: Auto-updater fix (subprocess + os._exit on Windows)
