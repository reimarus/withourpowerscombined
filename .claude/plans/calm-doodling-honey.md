# Multiplayer GUI Integration - Wire TCP Lobby into Launcher

## Context

The networking infrastructure is complete:
- `launcher/lobby.py` - TCP lobby server + client, 12 tests passing
- `launcher/prefs.py` - `expected_humans`, `host_port`, `join_address` prefs
- `launcher/game_config.py` - `ExpectedHumans`, `IsHost` fields in generated Lua
- `launcher/wopc.py` - `cmd_launch()` handles solo/host/join with quickstart
- `gamedata/wopc_patches/lua/wopc/multilobby.lua` - SCFA P2P via `InternalCreateLobby`
- `gamedata/wopc_patches/lua/wopc/waitingroom.lua` - transition screen
- `gamedata/wopc_patches/lua/wopc/quickstart.lua` - multiplayer dispatch + JoinLaunch
- `gamedata/wopc_patches/lua/ui/uimain.lua` - join quickstart intercept

**What's missing:** The GUI (`app.py`) doesn't interact with `lobby.py` at all. Clicking HOST GAME or JOIN GAME just launches SCFA directly - there's no TCP coordination, no live player list, no way for friends to connect before the game starts. This plan wires it all together.

## Implementation Plan

### Step 1: Add `expected_humans` widget to HOST mode sidebar

In `_build_sidebar()`, add an "Expected Players" dropdown (values "2"-"8") to `mode_widgets_frame`, visible only in HOST mode. Bind to `prefs.set_expected_humans()`.

File: `launcher/gui/app.py`

### Step 2: Add lobby state management to `WopcApp`

New instance variables:
```python
self._lobby_server: LobbyServer | None = None
self._lobby_client: LobbyClient | None = None
self._remote_players: dict[int, dict] = {}  # player_id -> {name, faction, slot, ready, widgets}
```

New methods:
```python
def _make_lobby_callbacks(self) -> LobbyCallbacks:
    """Create callbacks that marshal onto the GUI thread via self.after()."""

def _on_player_joined(self, player_id, name, faction, slot):
    """TCP callback: add remote human to player slots panel."""

def _on_player_left(self, player_id):
    """TCP callback: remove remote human from player slots panel."""

def _on_ready_changed(self, player_id, ready):
    """TCP callback: update ready indicator for remote player."""

def _on_lobby_launch(self, host_port):
    """TCP callback (joiner): host says launch - start SCFA in join mode."""

def _on_lobby_connected(self):
    """TCP callback (joiner): connected to host."""

def _on_lobby_disconnected(self, reason):
    """TCP callback: connection lost."""

def _on_lobby_error(self, error):
    """TCP callback: connection error."""
```

File: `launcher/gui/app.py`

### Step 3: Wire mode transitions to lobby lifecycle

Modify `_on_mode_change()`:
- HOST: Create and start `LobbyServer` on configured port. Log "Lobby server started on port X".
- SOLO (from HOST): Stop `LobbyServer`, clear remote players.
- SOLO (from JOIN): Disconnect `LobbyClient`, clear remote players.
- JOIN: Do nothing yet (client connects on button click).

File: `launcher/gui/app.py`

### Step 4: Modify `_on_primary_click()` for multiplayer

**HOST mode flow:**
- If lobby server NOT running: start it, change button to "HOST GAME (Waiting...)"
- If lobby server running and button clicked: broadcast launch -> launch SCFA -> stop server
- Show connected player count in button text: "LAUNCH (2/3 players)"

**JOIN mode flow:**
- If NOT connected: create `LobbyClient`, connect to host address. Button shows "CONNECTING..."
- If connected and NOT ready: send ready, button shows "READY"
- If connected and ready: un-ready

**SOLO mode:** Unchanged - launch directly.

File: `launcher/gui/app.py`

### Step 5: Add remote player display to player slots

New method `_add_remote_human_slot(player_id, name, faction, slot)`:
- Inserts a row showing: slot #, player name (bold accent), faction label, ready indicator
- Stores widget refs in `self._remote_players[player_id]["widgets"]`

When `_on_player_left` fires: destroy the row widgets, remove from dict, re-layout remaining slots.

When `_on_ready_changed` fires: update the ready indicator (green checkmark vs gray dash).

File: `launcher/gui/app.py`

### Step 6: Launch coordination

**Host launch flow** (in `_on_primary_click`):
1. `self._lobby_server.broadcast_launch(host_port)`
2. `prefs.set_expected_humans(1 + len(self._remote_players))`
3. Call existing `cmd_launch()` (already handles host mode)
4. `self._lobby_server.stop()` after a short delay

**Joiner launch flow** (in `_on_lobby_launch` callback):
1. Save received `host_port`
2. Construct join address from `self._lobby_client.host_address:host_port`
3. `prefs.set_join_address(join_address)`
4. Launch SCFA in background thread with 2s delay (let host bind first)
5. `self._lobby_client.disconnect()`

File: `launcher/gui/app.py`, `launcher/wopc.py` (no changes needed)

### Step 7: Cleanup on mode switch and window close

- Override `destroy()` to stop server/disconnect client cleanly
- Mode switch (HOST->SOLO, JOIN->SOLO) stops server/client and clears remote player UI

File: `launcher/gui/app.py`

### Step 8: Tests

Verify existing tests still pass. The GUI integration is hard to unit-test (tkinter), but the underlying `lobby.py` is already tested with 12 tests. Main verification is E2E.

Run: `py -m pytest tests/ -x -q`

## Files Modified

| File | Change |
|------|--------|
| `launcher/gui/app.py` | Lobby server/client lifecycle, remote player display, expected_humans widget, launch coordination |

## Verification

1. `py -m pytest tests/ -x -q` - all pass
2. `py -m ruff check launcher/ tests/` - clean
3. **Solo regression**: SOLO mode -> PLAY MATCH -> game starts (unchanged)
4. **Host lobby**: Switch to HOST -> see "Expected Players" dropdown -> lobby server starts -> log shows port
5. **Join connect**: Enter host IP, switch to JOIN, click JOIN GAME -> connects -> shows "Connected to host"
6. **Launch coordination**: Host clicks LAUNCH -> both SCFA instances open -> P2P connects via multilobby.lua
