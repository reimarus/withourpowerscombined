# Plan: Internet Game Discovery (Phase A)

## Context

WOPC multiplayer currently uses LAN UDP beacons for game discovery — players can only find each other on the same local network. This plan replaces the browser's discovery mechanism with an internet-first approach: a **Firebase Realtime Database relay** that any host can write to and any joiner can read from. LAN beacons remain as a parallel fallback.

Firebase is chosen because it has zero infrastructure to manage (Google hosts it), a free tier that covers this community indefinitely, a plain REST API (no SDK needed — stdlib `urllib.request` only), and real-time WebSocket support (though we'll use polling for simplicity in Phase A). The "mesh-like" quality: there's no WOPC-owned server process to keep alive. Each host writes directly to a shared database entry; it expires automatically if the host goes offline.

NAT traversal (port forwarding still required for the actual TCP game connection) is deferred to Phase B.

---

## Implementation Steps

### Step 1 — `launcher/discovery.py`: add `source` field to `GameBeacon`

Add `source: str = "lan"` as the last field in the dataclass (default preserves all existing call sites):

```python
@dataclass
class GameBeacon:
    host_name: str
    map_name: str
    player_count: int
    max_players: int
    lobby_port: int
    host_ip: str = ""
    last_seen: float = field(default_factory=time.monotonic)
    source: str = "lan"   # "lan" or "internet"
```

No other changes. All existing tests pass unchanged.

---

### Step 2 — `launcher/config.py`: add relay URL constant

Add at the bottom:

```python
# Internet relay (Firebase Realtime Database). Empty = relay disabled.
RELAY_URL: str = ""
```

After Firebase project is created (Step 8), set to:
`"https://<project-id>-default-rtdb.firebaseio.com"`

---

### Step 3 — `launcher/relay.py` (new file)

**Module-level constants:**
```python
_HEARTBEAT_INTERVAL = 30.0   # seconds between PUTs while hosting
_GAME_EXPIRY = 90.0          # seconds before a game is considered stale
_HTTP_TIMEOUT = 5            # seconds for relay HTTP calls
_IP_TIMEOUT = 3              # seconds for ipify lookup
```

**`get_public_ip() -> str | None`** (module-level):
- GET `https://api.ipify.org` (text/plain), 3s timeout
- Returns IP string or `None` on any error
- Logs warning on failure, does not raise

**`RelayClient` class:**

| Method | Description |
|--------|-------------|
| `register(host_name, map_name, player_count, max_players, lobby_port, public_ip) -> bool` | PUT `/games/{uuid}.json` with all fields + `last_seen=time.time()`. Stores `self._game_id`. Returns `True` on success. |
| `update(host_name, map_name, player_count, max_players) -> None` | PATCH `/games/{game_id}.json` with mutable fields + fresh `last_seen`. Silent on error. |
| `deregister() -> None` | Calls `stop_heartbeat()` then DELETE `/games/{game_id}.json`. Clears `self._game_id`. Silent on error. |
| `start_heartbeat(state_provider: Callable[[], dict]) -> None` | Starts daemon thread calling `update()` every `_heartbeat_interval` seconds. |
| `stop_heartbeat() -> None` | Sets `self._running = False`, joins thread (max 3s). |
| `fetch_games() -> list[GameBeacon]` | GET `/games.json`, filter where `now - last_seen > _GAME_EXPIRY`, return `list[GameBeacon]` with `source="internet"`. Returns `[]` on any error or if `config.RELAY_URL` is empty. |

**Firebase payload schema:**
```json
{
  "host_name": "Alice",
  "map_name": "Theta Passage 10/10",
  "player_count": 1,
  "max_players": 4,
  "lobby_port": 15000,
  "host_ip": "203.0.113.5",
  "last_seen": 1711234567.0
}
```

**Key design notes:**
- No new pip dependencies — `urllib.request`, `json`, `threading`, `uuid` only
- `from launcher import config` then `config.RELAY_URL` (not direct import — keeps mock-patching clean)
- `_heartbeat_interval` stored as instance var so tests can override it for speed
- Heartbeat loop sleeps 0.5s per tick (same pattern as `BeaconBroadcaster`) for responsive stop
- `fetch_games()` handles Firebase returning JSON `null` (empty node) as Python `None`

---

### Step 4 — `launcher/gui/app.py` changes

**4a. New instance variables in `__init__`** (alongside existing `_beacon_broadcaster`):
```python
self._relay_client: Any = None
self._relay_poll_active: bool = False
self._lan_games: list[Any] = []
self._internet_games: list[Any] = []
```

**4b. Modify `_on_games_discovered()`** — update `_lan_games` then call merge:
```python
def _on_games_discovered(self, games: list[Any]) -> None:
    self._lan_games = games
    self.after(0, self._merge_and_refresh)
```

**4c. New `_merge_and_refresh()`** — LAN takes priority for deduplication:
```python
def _merge_and_refresh(self) -> None:
    seen: set[str] = set()
    merged: list[Any] = []
    for g in self._lan_games:
        seen.add(f"{g.host_ip}:{g.lobby_port}")
        merged.append(g)
    for g in self._internet_games:
        if f"{g.host_ip}:{g.lobby_port}" not in seen:
            merged.append(g)
    self._refresh_game_browser(merged)
```

**4d. Relay polling loop** (uses `self.after()`, never blocks GUI):
```python
def _start_relay_polling(self) -> None: ...   # sets flag, calls _poll_relay_once()
def _stop_relay_polling(self) -> None: ...    # clears flag
def _poll_relay_once(self) -> None:
    # spawn daemon thread to fetch, reschedule via self.after(5000, ...)
    # on completion: self.after(0, _on_internet_games_fetched, games)
def _on_internet_games_fetched(self, games: list[Any]) -> None:
    self._internet_games = games
    self._merge_and_refresh()
```

**4e. Relay registration** (background thread, fire-and-forget):
```python
def _start_relay_registration(self) -> None:
    # thread: get_public_ip() → relay.register() → relay.start_heartbeat()
    # stores RelayClient in self._relay_client on success
    # on public IP failure: log warning to lobby chat, continue as LAN-only

def _stop_relay_registration(self) -> None:
    # if self._relay_client: spawn thread → client.deregister(); self._relay_client = None
```

**4f. Lifecycle wiring** — mirror the exact lifecycle of beacon broadcaster/listener:

| Event | Add call |
|-------|----------|
| `_on_mode_change("MULTIPLAYER")` | `_start_relay_polling()` |
| `_on_mode_change("SOLO")` | `_stop_relay_polling()`, `_stop_relay_registration()` |
| `_on_create_game()` | `_stop_relay_polling()`, `_start_relay_registration()` |
| `_join_game()` | `_stop_relay_polling()` |
| `_on_leave_lobby()` | `_stop_relay_registration()`, `_start_relay_polling()` |
| `_launch_game_and_cleanup()` | `_stop_relay_registration()` |
| `_on_lobby_disconnected/error/kicked()` | `_start_relay_polling()` (already shows browser) |
| `destroy()` | `_stop_relay_polling()`, `_stop_relay_registration()` |

**4g. UI changes:**
- Empty-state label → `"Searching for games on your network and the internet..."`
- In `_refresh_game_browser()`: if `getattr(game, "source", "lan") == "internet"`, add small `"🌐"` label to the right of the player-count in the row frame

---

### Step 5 — `tests/test_relay.py` (new file)

Mock target: `launcher.relay.urllib.request.urlopen` (same pattern as `test_updater.py`).

Key test cases:
- `get_public_ip`: success, timeout, URLError, empty response
- `register`: success (PUT sent, game_id stored), relay URL empty (no HTTP), HTTP error, network error
- `update`: PATCH sent, noop if no game_id, silent on error
- `deregister`: DELETE sent, game_id cleared, silent on error
- `fetch_games`: relay URL empty → `[]`, Firebase null → `[]`, stale filtered, fresh returned with `source="internet"`, malformed records skipped, network error → `[]`
- Heartbeat: calls `update()` at interval, start-twice safe, stop terminates thread

No real HTTP. No `@pytest.mark.slow` needed (all mocked).

---

### Step 6 — `docs/backlog.md` update

Mark backlog item #35 "Internet multiplayer — Phase A" as in progress.

---

### Step 7 — Implementation order

1. `discovery.py` source field → verify `pytest tests/test_discovery.py` passes
2. `config.py` RELAY_URL constant
3. `relay.py` module + `tests/test_relay.py` (TDD, function by function)
4. `app.py` merge infrastructure (`_lan_games`, `_internet_games`, `_merge_and_refresh`, update `_on_games_discovered`) — no visible behaviour change yet
5. `app.py` relay polling lifecycle
6. `app.py` host-side registration + deregistration
7. UI badge + empty-state label
8. Firebase project setup (Step 8 below) → set `RELAY_URL` in config
9. Full manual smoke test

---

### Step 8 — Firebase one-time setup (maintainer)

1. `console.firebase.google.com` → Create project → Spark (free) plan
2. Build → Realtime Database → Create database → **Test mode**
3. Copy URL: `https://<project-id>-default-rtdb.firebaseio.com`
4. Set security rules to require mandatory fields (prevents garbage writes):
```json
{
  "rules": {
    "games": {
      "$game_id": {
        ".read": true,
        ".write": true,
        ".validate": "newData.hasChildren(['host_name','map_name','player_count','max_players','lobby_port','host_ip','last_seen'])"
      }
    }
  }
}
```
5. Set `RELAY_URL` in `launcher/config.py`

No Firebase SDK. No credentials in repo. REST only.

---

## Files Modified

| File | Change |
|------|--------|
| `launcher/discovery.py` | Add `source: str = "lan"` to `GameBeacon` |
| `launcher/config.py` | Add `RELAY_URL: str = ""` |
| `launcher/relay.py` | **New** — `RelayClient` + `get_public_ip()` |
| `launcher/gui/app.py` | Polling loop, merge logic, registration lifecycle, UI badge |
| `tests/test_relay.py` | **New** — full unit test suite |
| `docs/backlog.md` | Mark item #35 Phase A in progress |

---

## Verification

```bash
# Unit tests (relay module, discovery unchanged)
pytest tests/test_relay.py tests/test_discovery.py -v

# Full suite
python .claude/utils/run_checks.py

# Manual smoke test (after Firebase setup)
# Machine A: launch WOPC → MULTIPLAYER → CREATE GAME
# Machine B (different network): launch WOPC → MULTIPLAYER → should see Machine A's game
# Machine B: click Join → lobby connects → LAUNCH → both enter sim
```
