# Unified Multiplayer Experience — Game Browser + Lobby Room

## Context

The current multiplayer flow is technically functional but feels like a developer tool: pick SOLO/HOST/JOIN, type an IP address, configure settings scattered across panels. The user wants a cohesive, modern experience: click MULTIPLAYER, see available games, join with one click, and land in a clean lobby room where everything (map, players, options, chat) is visible in one unified view. Think Discord voice channel meets FAF game lobby — but cleaner, especially around mods and game options.

**What we're NOT changing:** The networking backend (`lobby.py` TCP protocol, `wopc.py` launch logic, `game_config.py`, Lua quickstart/multilobby). The launcher remains the lobby — players always go from our UI straight into the match, never through FAF's in-game lobby.

## New User Flow

```
┌─────────────────────────────────────────────┐
│  WOPC Launcher                              │
│                                             │
│  [SOLO]  [MULTIPLAYER]                      │
│                                             │
│  SOLO → current experience (unchanged)      │
│                                             │
│  MULTIPLAYER → Game Browser Screen          │
│  ┌─────────────────────────────────────┐    │
│  │  Games on your network:             │    │
│  │  ┌───────────────────────────┐      │    │
│  │  │ Alice's Game              │      │    │
│  │  │ Theta Passage    2/4  [Join]│    │    │
│  │  │ Bob's Game                │      │    │
│  │  │ Seton's Clutch   1/2  [Join]│    │    │
│  │  └───────────────────────────┘      │    │
│  │                                     │    │
│  │  [CREATE GAME]   ▸ Direct Connect   │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  Click Join or Create → Lobby Room Screen   │
│  ┌─────────────────────────────────────┐    │
│  │  MAP           │  PLAYERS           │    │
│  │  [preview]     │  1. Alice (Host) ✓ │    │
│  │  Theta Passage │  2. Bob        ✓   │    │
│  │  [Change Map]  │  3. AI: Medium     │    │
│  │                │  [+ Add AI]        │    │
│  │────────────────┼────────────────────│    │
│  │  GAME OPTIONS  │  CHAT              │    │
│  │  Victory: ...  │  [Alice] gl hf     │    │
│  │  Unit Cap: ... │  [Bob] ready!      │    │
│  │  Share: ...    │  [___________][Send]│    │
│  │────────────────┴────────────────────│    │
│  │  [LEAVE]            [LAUNCH GAME]   │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

## Implementation Steps

### Step 1: Create `launcher/discovery.py` — LAN Game Discovery

New module. UDP beacon broadcast/listen for finding games on the local network.

**Constants:**
- `DISCOVERY_PORT = 15001`
- `BEACON_INTERVAL = 2.0` seconds
- `STALE_TIMEOUT = 8.0` seconds

**`GameBeacon` dataclass:**
- `host_name`, `map_name`, `player_count`, `max_players`, `lobby_port`, `host_ip`, `last_seen`

**`BeaconBroadcaster`:**
- Daemon thread sends JSON beacon to `255.255.255.255:15001` every 2s
- `state_provider` callable returns fresh game info each tick
- `target_address` param (default `"<broadcast>"`) allows loopback in tests
- `start()` / `stop()`

**`BeaconListener`:**
- Daemon thread, `SO_REUSEADDR`, 0.5s recv timeout
- Maintains live game dict keyed by `"{ip}:{port}"`, prunes stale entries
- Fires `on_update(games)` callback when list changes
- Filters out self-beacons
- `start()` / `stop()`

### Step 2: Create `tests/test_discovery.py`

Marked `pytest.mark.slow`. Pattern from `test_lobby.py`.

1. `test_beacon_serialization` — JSON round-trip
2. `test_broadcaster_lifecycle` — start/stop without crash
3. `test_listener_lifecycle` — start/stop without crash
4. `test_discovery_loopback` — broadcaster → listener on 127.0.0.1, verify callback fires
5. `test_stale_pruning` — game disappears after timeout
6. `test_multiple_hosts` — two broadcasters, listener sees both

### Step 3: Refactor `app.py` — Screen Switching Infrastructure

Replace the single static layout with switchable screens in the main content area.

**New approach:** The sidebar simplifies to SOLO / MULTIPLAYER toggle. The main content area (column 1) swaps between three screen frames:

1. **`self.solo_screen`** — Current main_content layout (map selector, slots, options, log)
2. **`self.browser_screen`** — Game browser (new)
3. **`self.lobby_screen`** — Multiplayer lobby room (new)

**Screen switching method:**
```python
def _show_screen(self, screen: str) -> None:
    """Switch visible screen: 'solo', 'browser', or 'lobby'."""
    for s in (self.solo_screen, self.browser_screen, self.lobby_screen):
        s.grid_remove()
    target = {"solo": self.solo_screen, "browser": self.browser_screen, "lobby": self.lobby_screen}[screen]
    target.grid(row=0, column=1, sticky="nsew")
```

**Mode selector changes:**
- Replace `["SOLO", "HOST", "JOIN"]` segmented button with `["SOLO", "MULTIPLAYER"]`
- Remove `launch_mode` pref values `"host"` / `"join"` — internally track whether you're hosting or joining via `self._is_hosting: bool`
- Clicking MULTIPLAYER → show browser screen, start beacon listener
- Clicking SOLO → show solo screen, stop any lobby/discovery

### Step 4: Build the Game Browser Screen

**`_build_browser_screen()`** — new method, builds `self.browser_screen` frame.

Layout:
- **Header:** "Find a Game" (large, bold)
- **Game list area:** `CTkScrollableFrame` showing discovered games
  - Each row: host name (bold), map name (muted), player count badge, "Join" button (accent)
  - Empty state: "Searching for games on your network..." with subtle animation or spinner
  - Games appear/disappear live as beacons arrive/expire
- **Bottom bar:**
  - `[CREATE GAME]` button (accent/green) — starts lobby server, broadcasts beacon, switches to lobby screen as host
  - `▸ Direct Connect` toggle — expands to show address entry + Connect button (for VPN/internet)
- **Back/cancel:** Clicking SOLO in the sidebar returns to solo screen

**Beacon listener integration:**
- Start `BeaconListener` when browser screen is shown
- Stop when leaving browser screen
- `_on_games_discovered()` callback → `self.after(0, _refresh_game_list)` for thread safety
- `_refresh_game_list()` clears and rebuilds game rows from current beacon data

### Step 5: Build the Lobby Room Screen

**`_build_lobby_screen()`** — new method, builds `self.lobby_screen` frame.

This is the core multiplayer experience. A **2×2 grid layout** with an action bar at the bottom:

```
┌──────────────────┬───────────────────┐
│  MAP SECTION     │  PLAYERS SECTION  │
│  (row 0, col 0)  │  (row 0, col 1)  │
├──────────────────┼───────────────────┤
│  OPTIONS SECTION │  CHAT SECTION     │
│  (row 1, col 0)  │  (row 1, col 1)  │
├──────────────────┴───────────────────┤
│  ACTION BAR (row 2, colspan 2)       │
│  [LEAVE]              [LAUNCH GAME]  │
└──────────────────────────────────────┘
```

**Map Section (top-left):**
- Map name (large, bold)
- Map preview image or type/size info (reuse `map_scanner` data)
- [Change Map] button (host only) — opens a compact map picker dropdown or modal
- Hidden/read-only for joiners — they see what the host picked

**Players Section (top-right):**
- Scrollable player list with slot rows
- Reuse existing slot structure: slot #, name/type, faction, team, color, ready indicator
- Host: can add/remove AI, kick players
- Joiner: read-only except own faction/team/color
- [+ Add AI] button (host only)
- Each remote player shows ready state (✓ green or — gray)

**Options Section (bottom-left):**
- Victory, Unit Cap, Fog of War, Game Speed, Share dropdowns
- Host: editable, changes broadcast to all
- Joiner: read-only labels (synced from host via game state)
- Content packs summary (e.g., "2 content packs enabled")

**Chat Section (bottom-right):**
- Chat message display (scrollable text area)
- System messages: "[Player joined]", "[Player left]", "[Player kicked]"
- Input bar + Send button at bottom
- Reuse existing chat infrastructure (`_send_chat`, `_append_chat`, lobby callbacks)

**Action Bar (bottom):**
- Left: `[LEAVE]` button — disconnects from lobby, returns to browser screen
- Right: `[LAUNCH GAME]` button (host) or `[READY] / [UNREADY]` toggle (joiner)
- Launch button shows player count: "LAUNCH (2/4 ready)"
- Launch disabled until all players ready (existing validation logic)

### Step 6: Wire Create Game Flow

When user clicks "CREATE GAME" on browser screen:
1. Start `LobbyServer` on default port (15000)
2. Start `BeaconBroadcaster` (game now visible on LAN)
3. Set `self._is_hosting = True`
4. Switch to lobby screen (`_show_screen("lobby")`)
5. Populate lobby with host's settings (map, options, local slots)
6. Stop `BeaconListener` (no longer browsing)

### Step 7: Wire Join Game Flow

When user clicks "Join" on a discovered game (or Direct Connect):
1. Create `LobbyClient` with game's IP and port
2. Connect (existing `_connect_lobby_client` logic)
3. Set `self._is_hosting = False`
4. Switch to lobby screen (`_show_screen("lobby")`)
5. Show "Connecting..." state
6. On connected: populate lobby from received game state
7. Stop `BeaconListener`

### Step 8: Wire Leave Flow

When user clicks "LEAVE" on lobby screen:
1. If hosting: stop `LobbyServer` + `BeaconBroadcaster`, clear remote players
2. If joined: disconnect `LobbyClient`, clear remote player display
3. Switch back to browser screen (`_show_screen("browser")`)
4. Restart `BeaconListener`

### Step 9: Migrate Existing Functionality

Move/reuse from current layout into new screens:

| Current Location | New Location | Change |
|-----------------|-------------|--------|
| Sidebar mode selector (SOLO/HOST/JOIN) | Sidebar (SOLO/MULTIPLAYER) | Simplified |
| Sidebar port entry | Hidden (internal default 15000) | Removed from UI |
| Sidebar address entry | Browser screen → Direct Connect | Collapsed, advanced |
| Sidebar PLAY button | Solo: sidebar. Multiplayer: lobby action bar | Split |
| Main map selector | Solo: unchanged. Lobby: map section | Moved |
| Main player slots | Solo: unchanged. Lobby: players section | Moved |
| Main game options | Solo: unchanged. Lobby: options section | Moved |
| Main log/chat | Solo: log only. Lobby: dedicated chat | Split |
| Right mod pane | Always visible (all screens) | Unchanged |

### Step 10: Update Prefs

In `launcher/prefs.py`:
- `launch_mode` values: `"solo"` | `"multiplayer"` (drop `"host"` / `"join"`)
- `host_port` stays (used internally, not shown in UI)
- `join_address` stays (used for direct connect)
- Add: `get_launch_mode()` / `set_launch_mode()` — update valid values

In `launcher/wopc.py`:
- `cmd_launch()` no longer reads `launch_mode` directly from prefs for host/join distinction
- Instead, `app.py` passes the mode explicitly or sets the right prefs before calling `cmd_launch()`
- Alternatively: keep existing host/join logic in `cmd_launch()`, and `app.py` sets `launch_mode` to `"host"` or `"join"` in prefs just before launching

## Files Modified

| File | Changes |
|------|---------|
| `launcher/discovery.py` | **NEW** — GameBeacon, BeaconBroadcaster, BeaconListener |
| `launcher/gui/app.py` | Major refactor — screen switching, browser screen, lobby room screen, simplified mode selector |
| `launcher/prefs.py` | Update `launch_mode` valid values (solo/multiplayer), keep host_port/join_address internal |
| `launcher/wopc.py` | Minor — adjust how launch mode is determined (app sets host/join before calling) |
| `tests/test_discovery.py` | **NEW** — 6 discovery tests (marked slow) |
| `tests/test_prefs.py` | Update launch mode tests for new valid values |

## Files NOT Modified

| File | Why |
|------|-----|
| `launcher/lobby.py` | TCP lobby protocol unchanged |
| `launcher/game_config.py` | Game config generation unchanged |
| `launcher/file_transfer.py` | Map/mod transfer unchanged |
| All Lua files | Quickstart, multilobby, waitingroom — all unchanged |

## Verification

1. `py -m pytest tests/ -x -q` — fast tests pass
2. `py -m pytest -m slow tests/test_discovery.py` — discovery tests pass
3. **Solo mode**: Click SOLO → existing experience, completely unchanged
4. **Create game**: Click MULTIPLAYER → browser screen → CREATE GAME → lobby room as host → beacon broadcasting → game visible on LAN
5. **Join game**: Machine B clicks MULTIPLAYER → sees host's game in browser → click Join → lobby room as joiner → sees host's map, players, options
6. **Lobby interaction**: Both players configure factions/teams/colors, chat works, host adds AI, options sync to joiner
7. **Launch**: Host clicks LAUNCH → both go straight into the match via quickstart
8. **Leave**: Click LEAVE → back to browser → can join another game
9. **Direct connect**: Expand "Direct Connect" on browser → enter IP → Connect → works
10. **Map auto-download**: Joiner missing map → auto-requested from host (existing file transfer)
