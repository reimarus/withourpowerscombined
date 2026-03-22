"""LAN game discovery — find and advertise WOPC multiplayer games.

Hosts broadcast a small UDP beacon every few seconds on the local network.
Joiners listen for these beacons and build a live list of available games.
Discovery is a thin layer on top of the existing TCP lobby — it only helps
players *find* each other.  Once they click Join, the TCP ``LobbyClient``
takes over.

Beacon format (JSON, UTF-8, <512 bytes)::

    {"type":"WOPC_GAME","host":"Alice","map":"Theta Passage",
     "players":2,"max":4,"port":15000,"ver":"0.1.0"}
"""

from __future__ import annotations

import contextlib
import json
import logging
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("wopc.discovery")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISCOVERY_PORT = 15001
BEACON_INTERVAL = 2.0  # seconds between broadcasts
STALE_TIMEOUT = 8.0  # seconds before a game is pruned
BEACON_TYPE = "WOPC_GAME"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class GameBeacon:
    """A discovered game on the LAN."""

    host_name: str
    map_name: str
    player_count: int
    max_players: int
    lobby_port: int
    host_ip: str = ""
    game_name: str = ""
    last_seen: float = field(default_factory=time.monotonic)
    source: str = "lan"  # "lan" or "internet"


# ---------------------------------------------------------------------------
# Broadcaster (host side)
# ---------------------------------------------------------------------------


class BeaconBroadcaster:
    """Periodically broadcast a UDP beacon advertising a hosted game.

    Parameters
    ----------
    port:
        UDP port to send beacons on (default ``DISCOVERY_PORT``).
    lobby_port:
        The TCP lobby port that joiners should connect to.
    state_provider:
        Called each tick to get fresh game info.  Must return a dict with
        keys: ``host_name``, ``map_name``, ``player_count``, ``max_players``.
    target_address:
        Broadcast destination.  Default ``"<broadcast>"`` sends to the LAN.
        Override to ``"127.0.0.1"`` for loopback testing.
    """

    def __init__(
        self,
        port: int = DISCOVERY_PORT,
        lobby_port: int = 15000,
        state_provider: Callable[[], dict[str, Any]] | None = None,
        target_address: str = "<broadcast>",
    ) -> None:
        self.port = port
        self.lobby_port = lobby_port
        self._state_provider = state_provider
        self._target = target_address
        self._running = False
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start broadcasting beacons in a background thread."""
        if self._running:
            return
        self._running = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.settimeout(1.0)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Beacon broadcaster started on port %d", self.port)

    def stop(self) -> None:
        """Stop broadcasting and clean up."""
        if not self._running:
            return
        self._running = False
        if self._sock:
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("Beacon broadcaster stopped")

    def _run(self) -> None:
        """Background thread: send beacons at regular intervals."""
        while self._running:
            try:
                self._send_beacon()
            except OSError as exc:
                if self._running:
                    logger.warning("Beacon send failed: %s", exc)
            # Sleep in small increments so stop() is responsive
            deadline = time.monotonic() + BEACON_INTERVAL
            while self._running and time.monotonic() < deadline:
                time.sleep(0.25)

    def _send_beacon(self) -> None:
        """Build and send a single beacon packet."""
        sock = self._sock  # local ref avoids race with stop()
        if not sock or not self._running:
            return

        state = self._state_provider() if self._state_provider else {}
        beacon = {
            "type": BEACON_TYPE,
            "host": state.get("host_name", "Unknown"),
            "map": state.get("map_name", ""),
            "players": state.get("player_count", 1),
            "max": state.get("max_players", 2),
            "port": self.lobby_port,
            "ver": _get_version(),
            "game_name": state.get("game_name", ""),
        }
        data = json.dumps(beacon).encode("utf-8")
        sock.sendto(data, (self._target, self.port))


# ---------------------------------------------------------------------------
# Listener (joiner side)
# ---------------------------------------------------------------------------


class BeaconListener:
    """Listen for UDP beacons and maintain a live list of discovered games.

    Parameters
    ----------
    port:
        UDP port to listen on (default ``DISCOVERY_PORT``).
    on_update:
        Called (from background thread) whenever the game list changes.
        Receives the current list of ``GameBeacon`` objects.
    """

    def __init__(
        self,
        port: int = DISCOVERY_PORT,
        on_update: Callable[[list[GameBeacon]], None] | None = None,
    ) -> None:
        self.port = port
        self._on_update = on_update
        self._running = False
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._games: dict[str, GameBeacon] = {}
        self._local_ips: set[str] = set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def games(self) -> list[GameBeacon]:
        """Current list of discovered games (snapshot)."""
        return list(self._games.values())

    def start(self) -> None:
        """Start listening for beacons in a background thread."""
        if self._running:
            return
        self._local_ips = _get_local_ips()
        self._running = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", self.port))
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Beacon listener started on port %d", self.port)

    def stop(self) -> None:
        """Stop listening and clean up."""
        if not self._running:
            return
        self._running = False
        if self._sock:
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._games.clear()
        logger.info("Beacon listener stopped")

    def _run(self) -> None:
        """Background thread: receive beacons and maintain game list."""
        while self._running:
            try:
                data, addr = self._sock.recvfrom(2048)  # type: ignore[union-attr]
                self._process_beacon(data, addr[0])
            except TimeoutError:
                pass
            except OSError:
                if self._running:
                    break

            # Prune stale entries
            changed = self._prune_stale()
            if changed and self._on_update:
                self._on_update(self.games)

    def _process_beacon(self, data: bytes, source_ip: str) -> None:
        """Parse a received beacon and update the game list."""
        try:
            msg = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        if msg.get("type") != BEACON_TYPE:
            return

        # Filter out our own beacons
        if source_ip in self._local_ips:
            return

        lobby_port = msg.get("port", 15000)
        key = f"{source_ip}:{lobby_port}"

        beacon = GameBeacon(
            host_name=msg.get("host", "Unknown"),
            map_name=msg.get("map", ""),
            player_count=msg.get("players", 1),
            max_players=msg.get("max", 2),
            lobby_port=lobby_port,
            host_ip=source_ip,
            game_name=msg.get("game_name", ""),
            last_seen=time.monotonic(),
        )

        old = self._games.get(key)
        self._games[key] = beacon

        # Fire callback if this is a new game or data changed
        changed = old is None or (
            old.host_name != beacon.host_name
            or old.map_name != beacon.map_name
            or old.player_count != beacon.player_count
            or old.max_players != beacon.max_players
        )
        if changed and self._on_update:
            self._on_update(self.games)

    def _prune_stale(self) -> bool:
        """Remove games that haven't sent a beacon recently.  Returns True if any removed."""
        now = time.monotonic()
        stale_keys = [k for k, g in self._games.items() if now - g.last_seen > STALE_TIMEOUT]
        for k in stale_keys:
            del self._games[k]
        return len(stale_keys) > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_local_ips() -> set[str]:
    """Return the set of IP addresses belonging to this machine."""
    ips: set[str] = {"127.0.0.1", "::1"}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ips.add(str(info[4][0]))
    except OSError:
        pass
    return ips


def _get_version() -> str:
    """Return the WOPC version string."""
    try:
        from launcher.config import VERSION

        return VERSION
    except Exception:
        return "0.1.0"
