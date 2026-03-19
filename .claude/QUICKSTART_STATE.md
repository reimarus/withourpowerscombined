# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-18
> If session runs out of tokens, a new session can pick up from here.

## Current State: Phase 6 — Modern Multiplayer UX (in progress)

### What works now:
1. **Solo mode** (quickstart bypass): GUI → select map/players/options → PLAY MATCH → game enters sim
2. **Multiplayer mode** (quickstart bypass): GUI → MULTIPLAYER → game browser (LAN discovery) or Create Game → lobby room (map, players, options, chat) → LAUNCH → all players enter sim via quickstart
3. **Content packs**: TotalMayhem (62 FAF-compatible units) toggleable in launcher
4. **Content icons**: Auto-extracted from LOUD's textures.scd during deploy

### CRITICAL ARCHITECTURE NOTE:
**Our launcher IS the lobby.** ALL launch modes (solo, host, join) use `/wopcquickstart`. The FAF in-game lobby UI is NEVER shown. All multiplayer coordination (player list, game options, map selection, chat, ready state, file transfer) happens in the Python launcher over TCP. The engine just receives the final config and starts the match.

### IMPORTANT: Rebuilding the exe
After ANY code changes to `launcher/`, `init/`, or `gamedata/`:
```
python build_exe.py    # rebuilds dist/WOPC-Launcher.exe
```
The exe bundles Python + assets at build time. Stale exe = old code!

### Launch modes (implemented in wopc.py):
| Mode | Engine args | Behaviour |
|------|------------|-----------|
| **Solo** | `/hostgame udp 15000 {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, single player |
| **Host** | `/hostgame udp {port} {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, launcher coordinated players via TCP |
| **Join** | `/joingame udp {address} {name} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, launcher received config from host via TCP |

### GUI screens (Phase 6 — three-screen layout):
| Screen | When shown | Key widgets |
|--------|-----------|-------------|
| **Solo** | SOLO mode selected | Map selector, player slots, game options, PLAY MATCH button |
| **Browser** | MULTIPLAYER selected | LAN game list (auto-discovered via UDP beacons), CREATE GAME, Direct Connect (collapsed) |
| **Lobby** | After creating/joining game | 2×2 grid: map panel, player list, game options, chat + action bar (LEAVE / LAUNCH) |

### Key modules:
- `launcher/discovery.py` — UDP LAN game discovery (BeaconBroadcaster + BeaconListener)
- `launcher/lobby.py` — TCP lobby server/client, JSON-line protocol
- `launcher/file_transfer.py` — map auto-download over TCP
- `launcher/gui/app.py` — all three screens, beacon lifecycle, flow methods

### Multiplayer features (all complete):
- TCP lobby server/client — JSON-line protocol, heartbeat, disconnect detection
- Live game state sync — host broadcasts map, options, AI slots, teams, colors, content packs
- Full state snapshot sent to new joiners on connect
- Player color selector (8 SCFA colors, duplicate prevention)
- Team assignment per slot (1-4)
- Victory condition normalization (display names → engine values)
- Map auto-download — joiner detects missing map, host streams files over TCP
- Content pack mismatch warnings
- Lobby chat, kick player, ready/unready toggle
- Pre-launch validation (all ready, no duplicate colors, map exists)
- LAN game discovery via UDP beacons (port 15001)

### What's broken / stubbed (Phase 6 follow-up):
- "Add AI" button in multiplayer lobby — not wired
- "Change Map" button in multiplayer lobby — not wired
- Remove players from solo screen — no remove button
- Victory type tooltips — no descriptions
- UI is basic — needs polish pass

### Test results: 196 tests pass (fast), ~60% coverage floor (lobby.py tests marked slow)

### Branch: `feature/modern-multiplayer-ux` — PR #17 open
