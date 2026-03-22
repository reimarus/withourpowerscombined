# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-21
> If session runs out of tokens, a new session can pick up from here.

## Current State: Phase 6 — Modern Multiplayer UX (in progress)

### What works now:
1. **Solo mode** (quickstart bypass): GUI → select map/players/options → PLAY MATCH → game enters sim
2. **Multiplayer mode** (quickstart bypass): GUI → MULTIPLAYER → game browser (LAN + internet discovery) or Create Game → lobby room (map, players, options, chat) → LAUNCH → all players enter sim via quickstart
3. **Content packs**: TotalMayhem + BlackOps units toggleable in launcher
4. **Content icons**: Auto-extracted from LOUD's textures.scd during deploy
5. **Internet game discovery**: Firebase relay (wopc-75b65) for finding games worldwide
6. **Interactive map preview**: Canvas-based with mass/hydro/spawn overlays, click-to-inspect window with zoom

### CRITICAL ARCHITECTURE NOTE:
**Our launcher IS the lobby.** ALL launch modes (solo, host, join) use `/wopcquickstart`. The FAF in-game lobby UI is NEVER shown. All multiplayer coordination (player list, game options, map selection, chat, ready state, file transfer) happens in the Python launcher over TCP. The engine just receives the final config and starts the match.

### Launch modes (implemented in wopc.py):
| Mode | Engine args | Behaviour |
|------|------------|-----------|
| **Solo** | `/hostgame udp 15000 {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, single player |
| **Host** | `/hostgame udp {port} {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, launcher coordinated players via TCP |
| **Join** | `/joingame udp {address} {name} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, launcher received config from host via TCP |

### GUI screens (Phase 6 — three-screen layout):
| Screen | When shown | Key widgets |
|--------|-----------|-------------|
| **Solo** | SOLO mode selected | Map selector (canvas preview with markers), player slots, game options, PLAY MATCH button |
| **Browser** | MULTIPLAYER selected | LAN + internet game list, CREATE GAME, Direct Connect (collapsed) |
| **Lobby** | After creating/joining game | 2×2 grid: map panel, player list, game options, chat + action bar (LEAVE / LAUNCH) |

### Key modules:
- `launcher/discovery.py` — UDP LAN game discovery (BeaconBroadcaster + BeaconListener)
- `launcher/relay.py` — Firebase REST API for internet game registration/discovery
- `launcher/lobby.py` — TCP lobby server/client, JSON-line protocol
- `launcher/file_transfer.py` — map auto-download over TCP
- `launcher/map_scanner.py` — scenario + save file parsing, DDS extraction, marker extraction
- `launcher/gui/app.py` — all three screens, beacon lifecycle, flow methods
- `launcher/gui/map_inspect.py` — zoomable map inspect window with marker overlays

### Map preview system:
- `parse_scenario()` extracts name, size, player count from `_scenario.lua`
- `parse_save_markers()` extracts ARMY positions, Mass deposits, Hydrocarbon markers from `_save.lua`
- `_extract_scmap_preview()` pulls embedded DDS 256×256 preview from `.scmap` binary
- Canvas renders preview image + markers (mass=white dots, hydro=green, spawns=numbered colored circles)
- Click opens `MapInspectWindow` with zoom (mouse wheel, 0.5x-4.0x)
- Coordinate mapping: `px = marker_x / map_width * canvas_size`
- **Gotcha**: `_save.lua` has both `['orientation']` and `['position']` VECTOR3 fields — must match `['position']` specifically

### Branch: `main` — Latest release: v2.01.0009. No active feature branch.

### Recent releases:
- **v2.01.0009**: Interactive map preview with markers, inspect window, hero layout, filter fixes
- **v2.01.0008**: DDS preview extraction from .scmap binary files
- **v2.01.0007**: Internet game discovery via Firebase relay (Phase A)
- **v2.01.0006**: Black screen fix (HostGame/JoinGame arg mismatch)
