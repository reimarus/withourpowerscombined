# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-24
> If session runs out of tokens, a new session can pick up from here.

## Current State: Phase 6 ✅ Complete — GUI Refactored, Bug Fixes Next

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

### GUI module structure (refactored in PR #68, v2.01.0037):
| Module | Lines | Role |
|--------|-------|------|
| `launcher/gui/app.py` | 1,913 | WopcApp main window, solo screen, sidebar, settings — delegates to other modules |
| `launcher/gui/lobby_screen.py` | 1,070 | Lobby room UI + full multiplayer networking (TCP callbacks, file transfer, game state) |
| `launcher/gui/slot_widget.py` | 832 | Player slot builders, color picker, team/spawn/color utilities |
| `launcher/gui/map_canvas.py` | 578 | Canvas rendering, zoom/pan, markers, spawn interaction |
| `launcher/gui/browser_screen.py` | 458 | Game browser UI + LAN/relay discovery lifecycle |
| `launcher/gui/models.py` | 226 | `PlayerSlot` + `PlayerSlotManager`, zero widget deps |
| `launcher/gui/constants.py` | 205 | All shared constants: colors, player palette, faction names, AI names, game option defs |

### Other key modules:
- `launcher/discovery.py` — UDP LAN game discovery (BeaconBroadcaster + BeaconListener)
- `launcher/relay.py` — Firebase REST API for internet game registration/discovery
- `launcher/lobby.py` — TCP lobby server/client, JSON-line protocol
- `launcher/file_transfer.py` — map auto-download over TCP
- `launcher/map_scanner.py` — scenario + save file parsing, DDS extraction, marker extraction
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

### Recent merges:
- **PR #68** (v2.01.0037): GUI refactor — extracted slot_widget.py, browser_screen.py, lobby_screen.py from app.py (4,320 → 1,913 lines, 56% reduction)
- **PR #64** (v2.01.0034): Multiplayer join fix — 6 bugs in TCP handshake, thread safety, joiner config

### Recent releases:
- **v2.01.0037**: GUI refactor — extracted 3 screen modules, centralized color constants
- **v2.01.0034**: Multiplayer join fix — 6 bugs in TCP handshake, thread safety, joiner config
- **v2.01.0033**: Refactor — extracted constants, models, map_canvas from app.py
- **v2.01.0032**: Spawn position fix — Players array gap-filling with civilian entries
