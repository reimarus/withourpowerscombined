# Multiplayer — Unified Lobby in Our Launcher

## Context

The WOPC launcher already has a lobby UI: map selection, player slots (human + AI), game options, faction/team dropdowns. It works for solo play. We need to extend it for multiplayer by adding TCP networking so friends' launchers connect to the same lobby, appear in the same player slots, and launch together. One UI, one experience — solo and multiplayer.

## Architecture

The existing lobby UI (player slots panel + game options panel) becomes the single lobby for all modes. The mode selector just controls whether TCP networking is active:

- **SOLO**: No networking. Host + AI. Click Launch → SCFA quickstart → sim.
- **HOST**: TCP server starts on configured port. Friends' launchers connect. They appear as human players in the slot list. Host configures everything. Click Launch → all launchers fire SCFA → quickstart → sim.
- **JOIN**: TCP client connects to host's launcher. GUI shows host's lobby state (map, players, options) — read-only except personal faction. Ready toggle. Host launches everyone.

```
Host Launcher                          Friend's Launcher
┌────────────────────────┐    TCP     ┌────────────────────────┐
│  Map: Caldera          │◄──────────►│  Map: Caldera (r/o)    │
│  ┌──────────────────┐  │           │  ┌──────────────────┐  │
│  │ 1. Player (Human)│  │           │  │ 1. Player (Human)│  │
│  │ 2. Friend (Human)│  │           │  │ 2. Friend (Human)│  │
│  │ 3. AI: Adaptive  │  │           │  │ 3. AI: Adaptive  │  │
│  │ + Add AI         │  │           │  │                  │  │
│  └──────────────────┘  │           │  └──────────────────┘  │
│  Options: Victory, etc │           │  Options (read-only)   │
│  [LAUNCH]              │           │  [READY ✓]  [LEAVE]    │
└───────────┬────────────┘           └───────────┬────────────┘
            │ Launch signal via TCP               │
            ▼                                     ▼
   SCFA /hostgame /wopcquickstart       SCFA /joingame /wopcquickstart
            │                                     │
            └──────────► SIM ◄────────────────────┘
```

## Phase 1: TCP Lobby Networking (`launcher/lobby.py`)

### New file: `launcher/lobby.py` (~250 lines)

JSON-line protocol over TCP. `threading` + `socket`.

**Messages:**

| Message | Direction | Fields |
|---------|-----------|--------|
| `Hello` | client→host | `player_name`, `faction` |
| `Welcome` | host→client | `player_id`, `lobby_state` (full snapshot: map, players, options, mods) |
| `PlayerJoined` | host→all | `player_id`, `player_name`, `faction`, `slot` |
| `PlayerLeft` | host→all | `player_id` |
| `LobbyUpdate` | host→all | `lobby_state` (when host changes map/options/AI/slots) |
| `FactionChange` | client→host | `faction` |
| `Ready` | client→host | `ready: bool` |
| `ReadyUpdate` | host→all | `player_id`, `ready: bool` |
| `Launch` | host→all | `host_port` |
| `Heartbeat` | both | — (every 5s, timeout 15s) |

**Classes:**

```python
class LobbyServer:
    """Host's TCP server. Manages connected players, broadcasts state."""
    def __init__(self, port: int, callbacks: LobbyCallbacks): ...
    def start(self) -> None:
    def stop(self) -> None:
    def broadcast_state(self, state: dict) -> None:
    def broadcast_launch(self, host_port: str) -> None:
    @property
    def connected_players(self) -> list[dict]: ...

class LobbyClient:
    """Joiner's TCP client. Connects to host, receives state updates."""
    def __init__(self, address: str, port: int, name: str, faction: str, callbacks: LobbyCallbacks): ...
    def connect(self) -> None:
    def disconnect(self) -> None:
    def send_faction(self, faction: str) -> None:
    def send_ready(self, ready: bool) -> None:

@dataclass
class LobbyCallbacks:
    on_player_joined: Callable  # (player_id, name, faction, slot)
    on_player_left: Callable    # (player_id)
    on_state_updated: Callable  # (lobby_state)
    on_ready_changed: Callable  # (player_id, ready)
    on_launch: Callable         # (host_port)
```

GUI callbacks use `root.after(0, callback)` for thread-safe tkinter updates.

Uses the same port as game (default 15000) on TCP — SCFA uses UDP, no conflict.

## Phase 2: Unified Lobby GUI (`launcher/gui/app.py`)

The existing player slots + game options panels already have the right structure. Changes:

### Player slots evolution:
- **Slot types expand**: Human (local), Human (remote/connected), AI, Empty
- Remote human slots show the connected player's name + faction (synced via TCP)
- Remote slots show a ready indicator (green dot / checkmark)
- In JOIN mode, all controls are read-only except own faction dropdown + ready toggle
- "Add AI" button only available to host (solo + host modes)

### Mode behavior:
- **SOLO→HOST transition**: TCP server starts. Slot 1 stays as local human. Empty human slots become "Waiting for player..." placeholders.
- **HOST→SOLO transition**: TCP server stops, disconnects all peers. Remote human slots removed.
- **JOIN activation**: TCP client connects. On success, GUI replaces local config with host's lobby state. Map selector disabled, options read-only. Own slot gets faction dropdown + ready button.

### New controls:
- **Expected Players** spinner (HOST mode, in sidebar): 2-8. Controls how many human slots are shown.
- **Ready toggle** (JOIN mode): button that sends ready state to host.
- **Launch button logic**: In HOST mode, enabled when all remote humans are ready (or solo with 0 remote). Text: "LAUNCH" for host, "READY" for joiner.

### State broadcasting:
When host changes anything (map, AI slot, game option, slot config), call `lobby_server.broadcast_state(self._get_lobby_state())`. The `_get_lobby_state()` method collects the current map, player slots, game options, and active mods into a dict.

## Phase 3: Launch Coordination

### Host clicks Launch:
1. Broadcast `Launch` message (includes `host_port`)
2. Write game config with all players (human + AI), `ExpectedHumans=N`
3. Launch SCFA: `/hostgame udp <port> <name> WOPC <map> /wopcquickstart /wopcconfig <path>`
4. Stop TCP server

### Peer receives Launch:
1. Write minimal game config (personal faction + host info)
2. Wait 2s (let host's SCFA start first)
3. Launch SCFA: `/joingame udp <host_address:port> <name> /wopcquickstart /wopcconfig <path>`
4. Disconnect TCP client

### Solo Launch (unchanged):
Write game config → launch SCFA with `/wopcquickstart` → straight to sim.

## Phase 4: SCFA-Side Multiplayer Quickstart

### `quickstart.lua` — Add multiplayer dispatch (~5 lines)
If `ExpectedHumans > 1`, delegate to `multilobby.lua` instead of launching immediately.

### `uimain.lua` — Intercept join quickstart (~5 lines)
Add `/wopcquickstart` detection to `StartJoinLobbyUI()`.

### New: `multilobby.lua` — P2P connection handler (~200 lines)
Headless P2P manager using `InternalCreateLobby` with custom class (same pattern as FAF's `AutolobbyController`):
- **Host:** `Hosting()` → populate gameInfo from config → `LaunchThread` polls until all peers connected → auto-launch
- **Joiner:** `ConnectionToHostEstablished()` → send `AddPlayer` → receive config → wait for host's launch signal
- **No interactive UI** — just a background + "Connecting..." text that auto-dismisses

### New: `waitingroom.lua` — Transition screen (~50 lines)
Background painting (reuse FAF's autolobby backgrounds) + centered status text. Auto-destroys on `GameLaunched()`.

## Phase 5: Supporting Changes

### `launcher/prefs.py`
- `expected_humans` (default "2"), getter/setter
- `lobby_port` (default "15000"), getter/setter

### `launcher/game_config.py`
- Add `expected_humans: int = 1`, `is_host: bool = True` parameters
- Generated Lua gains `ExpectedHumans` and `IsHost` fields

### `launcher/wopc.py`
- Host mode: write full config, pass `/wopcquickstart /wopcconfig`
- Join mode: write minimal config, pass `/wopcquickstart /wopcconfig`
- Accept `expected_humans` from GUI

### `launcher/deploy.py`
- Already fixed: `etc/` directory included in faf_ui.scd build (blacklist.lua fix from this session)

## Files Modified/Created

| File | Change |
|------|--------|
| `launcher/lobby.py` | **NEW** — TCP lobby server + client (~250 lines) |
| `launcher/gui/app.py` | Unified lobby: live player list, server/client integration, ready state |
| `launcher/prefs.py` | `expected_humans`, `lobby_port` prefs |
| `launcher/game_config.py` | `expected_humans`, `is_host` fields |
| `launcher/wopc.py` | Host/join use `/wopcquickstart`, accept `expected_humans` |
| `gamedata/wopc_patches/lua/wopc/quickstart.lua` | 5-line multiplayer dispatch |
| `gamedata/wopc_patches/lua/ui/uimain.lua` | 5-line join quickstart intercept |
| `gamedata/wopc_patches/lua/wopc/multilobby.lua` | **NEW** — P2P handler (~200 lines) |
| `gamedata/wopc_patches/lua/wopc/waitingroom.lua` | **NEW** — transition screen (~50 lines) |
| `tests/test_lobby.py` | **NEW** — server/client unit tests |
| `tests/test_prefs.py` | expected_humans, lobby_port tests |
| `tests/test_game_config.py` | multiplayer field tests |
| `tests/test_wopc.py` | host/join quickstart arg tests |

## Implementation Order

1. `launcher/lobby.py` + `tests/test_lobby.py` — TCP networking (testable standalone)
2. `launcher/prefs.py` + `launcher/game_config.py` — new fields + tests
3. `launcher/wopc.py` — quickstart flags for host/join + tests
4. `launcher/gui/app.py` — unified lobby integration
5. Lua: `multilobby.lua` + `waitingroom.lua` + quickstart dispatch + uimain intercept
6. Deploy + rebuild exe + full E2E test

## Backlog: Steam Friends Integration

Future phase — authenticate through Steam so friends can join via Steam overlay (right-click → Join Game). Requires Steamworks SDK, lobby registration, join request handling.

## Verification

1. `py -m pytest tests/ -x -q` — all pass, ≥70% coverage
2. `py -m ruff check launcher/ tests/` — clean
3. **Solo regression**: PLAY MATCH → game enters sim (unchanged)
4. **Host lobby**: Switch to HOST → TCP server starts → friend's launcher can connect → appears in player list live
5. **Join lobby**: Enter host IP, JOIN GAME → connects → sees host's config → faction/ready controls work
6. **Launch**: Host clicks LAUNCH → all SCFA instances open → P2P connects → straight to sim
7. **LAN test**: Two machines, host + join, full game to sim
