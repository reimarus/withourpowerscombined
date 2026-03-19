# WOPC Quick-Start — Session State & Recovery Breadcrumbs
> Last updated: 2026-03-18
> If session runs out of tokens, a new session can pick up from here.

## Current State: Multiplayer fully functional. TCP lobby + file transfer + game state sync all working.

### What works now:
1. **Solo mode** (quickstart bypass): GUI → select map → PLAY MATCH → game enters sim
2. **Host mode** (quickstart bypass): GUI → HOST GAME → TCP lobby starts → friends join via launcher → host configures map/options/AI → all synced to joiners → LAUNCH → all players enter sim via quickstart
3. **Join mode** (quickstart bypass): GUI → enter host address → JOIN GAME → connects to host's TCP lobby → sees host's config → ready up → host launches → enters sim via quickstart
4. **Content packs**: TotalMayhem (62 FAF-compatible units) toggleable in launcher
5. **Content icons**: Auto-extracted from LOUD's textures.scd during deploy

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
| **Solo** | `/hostgame udp 15000 {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, no lobby |
| **Host** | `/hostgame udp {port} {name} WOPC {map} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, launcher coordinated players via TCP |
| **Join** | `/joingame udp {address} {name} /wopcquickstart /wopcconfig {cfg}` | Quickstart bypass, launcher received config from host via TCP |

### Multiplayer features (all complete):
- TCP lobby server/client (`lobby.py`) — JSON-line protocol, heartbeat, disconnect detection
- Live game state sync — host broadcasts map, options, AI slots, teams, colors, content packs
- Full state snapshot sent to new joiners on connect
- Player color selector (8 SCFA colors, duplicate prevention)
- Team assignment per slot (1-4)
- Victory condition normalization (display names → engine values)
- Map auto-download — joiner detects missing map, host streams files over TCP
- Content pack mismatch warnings
- Lobby chat
- Kick player
- Ready/unready toggle
- Pre-launch validation (all ready, no duplicate colors, map exists)

### GUI launcher features:
- Mode selector (SOLO / HOST / JOIN segmented button) in sidebar
- Conditional port entry (HOST) or host address entry (JOIN)
- Player name entry in PLAYER SETTINGS panel
- Map selector hidden in JOIN mode (host controls the map)
- Button text changes: PLAY MATCH / HOST GAME / JOIN GAME
- Remote player slots with faction, team, color, ready indicators
- Chat input/display in log area

### Next steps:
- **Modernize multiplayer UX** — replace SOLO/HOST/JOIN with SOLO/MULTIPLAYER, add game browser with LAN discovery, redesign into unified lobby room view
- End-to-end multiplayer test (host + join on LAN)

### Test results: 195+ tests pass (fast), ~65% coverage (lobby.py tests marked slow)
