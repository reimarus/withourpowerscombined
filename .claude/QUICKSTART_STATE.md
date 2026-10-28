# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-10-28 (v2.01.0068 released)
> If session runs out of tokens, a new session can pick up from here.

## Current State: Phase 7 — Pathfinding + Stability + CDN Migration

### What works now:
1. **Solo mode** (quickstart bypass): GUI → select map/players/options → PLAY MATCH → game enters sim
2. **Multiplayer mode** (quickstart bypass): GUI → MULTIPLAYER → game browser (LAN + internet discovery) or Create Game → lobby room (map, players, options, chat) → LAUNCH → all players enter sim via quickstart
3. **Content packs**: TotalMayhem + BlackOps units toggleable in launcher
4. **Content icons**: Downloaded from R2 CDN during deploy
5. **Internet game discovery**: Firebase relay (wopc-75b65) for finding games worldwide
6. **Interactive map preview**: Canvas-based with tinted commander icons, mass/hydro strategic icons, click-to-select spawn, zoom/pan
7. **Player slot management**: Add/remove AI, color picker (HSV wheel), team assignment, faction selection, spawn position selection on minimap
8. **Auto-updater**: Firebase version manifest → R2 CDN download → exe replace → restart (GitHub API fallback)
9. **Spawn position mapping**: Players array index == ARMY_N, gap-filling with civilian entries (v2.01.0032)
10. **Mod sync on startup**: Bundled mods copied from exe bundle to WOPC deployment on every launch
11. **Standalone DLL audit**: Pre-launch DLL validation, build-time SCD import verification, runtime import() wrapper
12. **CDN infrastructure**: All downloads via Cloudflare R2 Worker (`wopc-cdn.roskvarek.workers.dev`), Firebase version manifest

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
| **Lobby** | After creating/joining game | Map panel, player list (host slot with color/team/faction), game options, chat + action bar (LEAVE / LAUNCH) |

### GUI module structure:
| Module | Lines | Role |
|--------|-------|------|
| `launcher/gui/app.py` | ~1,930 | WopcApp main window, solo screen, sidebar, settings — delegates to other modules |
| `launcher/gui/lobby_screen.py` | ~1,250 | Lobby room UI + full multiplayer networking (TCP callbacks, file transfer, game state) |
| `launcher/gui/slot_widget.py` | ~840 | Player slot builders, color picker, team/spawn/color utilities |
| `launcher/gui/map_canvas.py` | ~600 | Canvas rendering, zoom/pan, markers, spawn interaction |
| `launcher/gui/browser_screen.py` | ~460 | Game browser UI + LAN/relay discovery lifecycle |
| `launcher/gui/mod_panel.py` | ~330 | Collapsible mod categories, ModRow with download, shared solo/lobby |
| `launcher/gui/models.py` | 226 | `PlayerSlot` + `PlayerSlotManager`, zero widget deps |
| `launcher/gui/constants.py` | 205 | All shared constants: colors, player palette, faction names, AI names, game option defs |

### Other key modules:
- `launcher/discovery.py` — UDP LAN game discovery (BeaconBroadcaster + BeaconListener)
- `launcher/relay.py` — Firebase REST API for internet game registration/discovery
- `launcher/lobby.py` — TCP lobby server/client, JSON-line protocol
- `launcher/file_transfer.py` — map auto-download over TCP
- `launcher/map_scanner.py` — scenario + save file parsing, DDS extraction, marker extraction
- `launcher/game_config.py` — generates `wopc_game_config.lua` with gap-filling for ARMY mapping
- `launcher/updater.py` — Firebase-first auto-update, GitHub API fallback, R2 CDN download
- `launcher/prefs.py` — INI-based preferences (player name, faction, color, map, display)

### Active work: Phase 7 — Pathfinding + Multiplayer Polish
- `bundled/usermods/wopc_pathing/` — toggleable mod with blocked timer capping, soft collision, engineer zero collision
- `vendor/FA-Binary-Patches/section/WopcPathfinding.cpp` — C++ API: `SetBlockedTimerTuning()`, `GetPathfindingStats()`, `WopcSetZeroCollisionEnabled()`, `unit:WopcMarkZeroCollision()`, `unit:WopcIsZeroCollision()`
- `vendor/FA-Binary-Patches/hooks/WayPointArrive.cpp` — inline ASM for blocked timer clamping
- `bundled/usermods/wopc_artillery/` — T3 artillery range/cost reduction mod
- Next: color picker rendering (#62), A* improvements, remaining multiplayer polish

### CDN Infrastructure (new in v2.01.0066):
- **R2 Worker CDN**: `https://wopc-cdn.roskvarek.workers.dev` — serves all game assets
- **R2 bucket**: `wopc-releases` — content-v1/, content-v2/, content-v3/, launcher/
- **Firebase manifest**: `launcher_version` node at `wopc-75b65-default-rtdb.firebaseio.com`
- **Release script**: `scripts/release.py` auto-uploads exe to R2 + updates Firebase manifest
- **Migration script**: `scripts/migrate_to_r2.py` — one-time, already run, all 27 assets uploaded
- **R2 env vars**: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (set via `setx`)
- **GitHub account status**: Flagged for "multiple free accounts" (appeal pending). All unauthenticated requests 404. Authenticated `gh` CLI still works. R2+Firebase make this non-blocking.
- **Local backup**: `C:\Users\roskv\wopc-backup\` — git bundle + all content assets (~1.7 GB)

### Known bugs (see backlog):
- Color picker rendering in multiplayer (#62)
- Civilian filler armies — investigate idle commander spawns (#54)
- AI reclaim grid reference missing (#33 in Architecture Refactors)
- Global player settings (#72)

### Recent merges:
- **PR #107**: R2 CDN migration — Firebase-first updater, R2 URLs, release script R2 upload, migration script
- **PR #106**: Runtime import() logging + SCD verifier fix (#87)
- **PR #105**: Build-time SCD import verification (#87)
- **PR #104**: Pre-launch DLL validation (#87)

### Recent releases:
- **v2.01.0066**: R2 CDN migration — all downloads via Cloudflare R2, Firebase version manifest
- **v2.01.0065**: Runtime import() wrapper, SCD verifier Unicode fixes
- **v2.01.0064**: Build-time SCD import verification
- **v2.01.0063**: Pre-launch DLL validation for standalone installs
