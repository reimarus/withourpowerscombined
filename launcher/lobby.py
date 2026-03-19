"""TCP lobby server and client for WOPC multiplayer coordination.

The host's launcher runs a LobbyServer; friends' launchers connect with
LobbyClient.  All game configuration (map, players, AI, options) is
managed in the host's GUI and broadcast to connected peers.  When the
host clicks Launch, a Launch message is sent to all peers so they can
start SCFA simultaneously.

Protocol: newline-delimited JSON over TCP.
"""

from __future__ import annotations

import contextlib
import json
import logging
import selectors
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = 1
HEARTBEAT_INTERVAL = 5.0  # seconds
HEARTBEAT_TIMEOUT = 15.0  # seconds
BUFFER_SIZE = 65536
ENCODING = "utf-8"


# ---------------------------------------------------------------------------
# Callback interface
# ---------------------------------------------------------------------------


@dataclass
class LobbyCallbacks:
    """Callbacks from lobby networking into the GUI layer.

    All callbacks are invoked from background threads.  The GUI layer
    must use ``root.after(0, ...)`` or equivalent to marshal onto the
    main thread.
    """

    on_player_joined: Callable[[int, str, str, int], None] | None = None
    on_player_left: Callable[[int], None] | None = None
    on_state_updated: Callable[[dict[str, Any]], None] | None = None
    on_ready_changed: Callable[[int, bool], None] | None = None
    on_launch: Callable[[str], None] | None = None
    on_connected: Callable[[], None] | None = None
    on_disconnected: Callable[[str], None] | None = None
    on_error: Callable[[str], None] | None = None
    on_chat_received: Callable[[str, str], None] | None = None
    on_kicked: Callable[[str], None] | None = None
    on_file_request: Callable[[int, str, str], None] | None = None
    on_file_manifest: Callable[[str, str, list[dict[str, Any]]], None] | None = None
    on_file_chunk: Callable[[str, str, int, int, str], None] | None = None
    on_file_complete: Callable[[str, str], None] | None = None
    on_transfer_progress: Callable[[str, str, float], None] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _send_msg(sock: socket.socket, msg: dict[str, Any]) -> None:
    """Serialize *msg* as a JSON line and send it."""
    data = json.dumps(msg, separators=(",", ":")) + "\n"
    sock.sendall(data.encode(ENCODING))


def _recv_lines(sock: socket.socket, buf: bytearray) -> list[str]:
    """Non-blocking receive: read available data and split into lines."""
    try:
        chunk = sock.recv(BUFFER_SIZE)
    except (TimeoutError, BlockingIOError):
        return []
    if not chunk:
        raise ConnectionResetError("peer closed connection")
    buf.extend(chunk)
    lines: list[str] = []
    while b"\n" in buf:
        line, _, rest = buf.partition(b"\n")
        buf.clear()
        buf.extend(rest)
        lines.append(line.decode(ENCODING))
    return lines


# ---------------------------------------------------------------------------
# Player record (server-side)
# ---------------------------------------------------------------------------


@dataclass
class _RemotePlayer:
    player_id: int
    name: str
    faction: str
    slot: int
    team: int = 1
    color: int = 0
    ready: bool = False
    sock: socket.socket | None = None
    last_heartbeat: float = 0.0
    recv_buf: bytearray = field(default_factory=bytearray)


# ---------------------------------------------------------------------------
# LobbyServer
# ---------------------------------------------------------------------------


class LobbyServer:
    """TCP lobby server run by the host.

    Accepts connections from peers, assigns them player IDs and slots,
    and broadcasts lobby state changes.
    """

    def __init__(
        self,
        port: int,
        callbacks: LobbyCallbacks,
        game_state_provider: Callable[[], dict[str, Any] | None] | None = None,
    ) -> None:
        self.port = port
        self._cb = callbacks
        self._game_state_provider = game_state_provider
        self._players: dict[int, _RemotePlayer] = {}
        self._next_id = 1
        self._next_slot = 2  # slot 1 is reserved for host
        self._lock = threading.RLock()
        self._server_sock: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    # -- public API ----------------------------------------------------------

    def start(self) -> None:
        """Start listening for connections in a background thread."""
        if self._running:
            return
        self._running = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("0.0.0.0", self.port))
        self._server_sock.listen(8)
        self._server_sock.settimeout(1.0)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Lobby server started on port %d", self.port)

    def stop(self) -> None:
        """Shut down the server and disconnect all peers."""
        self._running = False
        with self._lock:
            players = list(self._players.values())
            self._players.clear()
        for p in players:
            self._close_player(p)
        if self._server_sock:
            with contextlib.suppress(OSError):
                self._server_sock.close()
            self._server_sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        self._next_id = 1
        self._next_slot = 2
        logger.info("Lobby server stopped")

    def broadcast_state(self, state: dict[str, Any]) -> None:
        """Send a full lobby state snapshot to all connected peers."""
        msg = {"type": "LobbyUpdate", "lobby_state": state}
        self._broadcast(msg)

    def broadcast_launch(self, host_port: str) -> None:
        """Tell all peers to launch SCFA."""
        msg = {"type": "Launch", "host_port": host_port}
        self._broadcast(msg)

    @property
    def connected_players(self) -> list[dict[str, Any]]:
        """Return a list of connected player dicts."""
        with self._lock:
            return [
                {
                    "player_id": p.player_id,
                    "name": p.name,
                    "faction": p.faction,
                    "slot": p.slot,
                    "team": p.team,
                    "color": p.color,
                    "ready": p.ready,
                }
                for p in self._players.values()
            ]

    @property
    def is_running(self) -> bool:
        return self._running

    def reset_slots(self) -> None:
        """Reset the slot counter (e.g. when expected humans changes)."""
        self._next_slot = 2

    def broadcast_chat(self, sender: str, text: str) -> None:
        """Send a chat message to all connected peers."""
        self._broadcast({"type": "Chat", "sender": sender, "text": text})

    def kick_player(self, player_id: int, reason: str = "Kicked by host") -> None:
        """Kick a player from the lobby."""
        with self._lock:
            player = self._players.get(player_id)
        if player and player.sock:
            with contextlib.suppress(OSError):
                _send_msg(player.sock, {"type": "Kicked", "reason": reason})
        self._remove_player(player_id)

    def send_to_player(self, player_id: int, msg: dict[str, Any]) -> None:
        """Send a message to a specific player."""
        with self._lock:
            player = self._players.get(player_id)
        if player and player.sock:
            with contextlib.suppress(OSError):
                _send_msg(player.sock, msg)

    # -- internals -----------------------------------------------------------

    def _broadcast(self, msg: dict[str, Any]) -> None:
        with self._lock:
            for p in list(self._players.values()):
                try:
                    if p.sock:
                        _send_msg(p.sock, msg)
                except OSError:
                    self._remove_player(p.player_id)

    def _run(self) -> None:
        """Main server loop: accept connections and poll peers via selectors."""
        sel = selectors.DefaultSelector()
        try:
            if self._server_sock:
                sel.register(self._server_sock, selectors.EVENT_READ, data="server")

            last_heartbeat = time.monotonic()
            while self._running:
                # Update selector: register any new peer sockets, unregister stale
                self._sync_selector(sel)

                # Block up to 0.5s waiting for socket activity
                events = sel.select(timeout=0.5)
                for key, _mask in events:
                    if key.data == "server":
                        # New incoming connection
                        try:
                            client_sock, addr = self._server_sock.accept()  # type: ignore[union-attr]
                            logger.info("New connection from %s", addr)
                            self._handle_new_connection(client_sock)
                        except OSError:
                            pass
                    else:
                        # Data from an existing peer
                        self._poll_peer_socket(key.fileobj)  # type: ignore[arg-type]

                # Check heartbeat timeouts
                now = time.monotonic()
                with self._lock:
                    for p in list(self._players.values()):
                        if now - p.last_heartbeat > HEARTBEAT_TIMEOUT:
                            logger.info("Player %d timed out", p.player_id)
                            self._remove_player(p.player_id)

                # Send periodic heartbeats
                if now - last_heartbeat > HEARTBEAT_INTERVAL:
                    self._broadcast({"type": "Heartbeat"})
                    last_heartbeat = now
        finally:
            sel.close()

    def _sync_selector(self, sel: selectors.BaseSelector) -> None:
        """Keep the selector's registered sockets in sync with _players."""
        with self._lock:
            current_socks = {p.sock for p in self._players.values() if p.sock}
            current_fds: set[int] = set()
            for s in current_socks:
                with contextlib.suppress(OSError):
                    current_fds.add(s.fileno())

        # Unregister stale peer sockets (no longer in _players)
        for key in list(sel.get_map().values()):
            if key.data != "server" and key.fd not in current_fds:
                with contextlib.suppress(Exception):
                    sel.unregister(key.fileobj)

        # Register new peer sockets
        registered_fds = {key.fd for key in sel.get_map().values() if key.data != "server"}
        with self._lock:
            for p in self._players.values():
                if p.sock:
                    try:
                        fd = p.sock.fileno()
                    except OSError:
                        continue
                    if fd not in registered_fds:
                        with contextlib.suppress(Exception):
                            sel.register(p.sock, selectors.EVENT_READ, data=p.player_id)

    def _poll_peer_socket(self, sock: socket.socket) -> None:
        """Read data from a peer socket that select() marked as readable."""
        # Find the player under lock, then release before doing I/O
        with self._lock:
            player = None
            for p in self._players.values():
                if p.sock is sock:
                    player = p
                    break
        if not player:
            return
        try:
            lines = _recv_lines(sock, player.recv_buf)
            for line in lines:
                self._handle_message(player, json.loads(line))
        except (ConnectionResetError, OSError):
            self._remove_player(player.player_id)
        except json.JSONDecodeError:
            pass

    def _handle_new_connection(self, sock: socket.socket) -> None:
        """Process the Hello handshake from a new peer."""
        try:
            # Blocking with timeout for the handshake phase
            sock.setblocking(True)
            sock.settimeout(5.0)
            buf = bytearray()
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                lines = _recv_lines(sock, buf)
                for line in lines:
                    msg = json.loads(line)
                    if msg.get("type") == "Hello":
                        # Switch to non-blocking for selector-based polling
                        sock.setblocking(False)
                        self._accept_player(sock, msg)
                        return
            # No Hello received in time
            sock.close()
        except (OSError, json.JSONDecodeError):
            with contextlib.suppress(OSError):
                sock.close()

    def _accept_player(self, sock: socket.socket, hello: dict[str, Any]) -> None:
        """Assign a player ID and slot, send Welcome, notify others."""
        with self._lock:
            pid = self._next_id
            self._next_id += 1
            slot = self._next_slot
            self._next_slot += 1
            name = hello.get("player_name", f"Player {pid}")
            faction = hello.get("faction", "random")
            team = hello.get("team", 1)
            color = hello.get("color", 0)

            player = _RemotePlayer(
                player_id=pid,
                name=name,
                faction=faction,
                slot=slot,
                team=team,
                color=color,
                sock=sock,
                last_heartbeat=time.monotonic(),
            )
            self._players[pid] = player

        # Send Welcome
        welcome = {
            "type": "Welcome",
            "player_id": pid,
            "slot": slot,
            "protocol_version": PROTOCOL_VERSION,
        }
        try:
            # Briefly blocking for reliable handshake delivery
            sock.setblocking(True)
            sock.settimeout(5.0)
            _send_msg(sock, welcome)
            # If a game state snapshot callback is registered, send it now
            if self._game_state_provider:
                state = self._game_state_provider()
                if state:
                    _send_msg(sock, {"type": "GameState", "state": state})
            sock.setblocking(False)
        except OSError:
            self._remove_player(pid)
            return

        # Notify GUI
        if self._cb.on_player_joined:
            self._cb.on_player_joined(pid, name, faction, slot)

        # Notify other peers
        join_msg = {
            "type": "PlayerJoined",
            "player_id": pid,
            "player_name": name,
            "faction": faction,
            "slot": slot,
            "team": team,
            "color": color,
        }
        self._broadcast(join_msg)

    def _handle_message(self, player: _RemotePlayer, msg: dict[str, Any]) -> None:
        """Process a message from a connected peer."""
        msg_type = msg.get("type", "")
        player.last_heartbeat = time.monotonic()

        if msg_type == "Heartbeat":
            return

        if msg_type == "FactionChange":
            player.faction = msg.get("faction", player.faction)
            if self._cb.on_player_joined:
                self._cb.on_player_joined(
                    player.player_id, player.name, player.faction, player.slot
                )

        elif msg_type == "TeamChange":
            player.team = msg.get("team", player.team)
            self._broadcast(
                {
                    "type": "PlayerUpdate",
                    "player_id": player.player_id,
                    "team": player.team,
                }
            )
            if self._cb.on_player_joined:
                self._cb.on_player_joined(
                    player.player_id, player.name, player.faction, player.slot
                )

        elif msg_type == "ColorChange":
            player.color = msg.get("color", player.color)
            self._broadcast(
                {
                    "type": "PlayerUpdate",
                    "player_id": player.player_id,
                    "color": player.color,
                }
            )
            if self._cb.on_player_joined:
                self._cb.on_player_joined(
                    player.player_id, player.name, player.faction, player.slot
                )

        elif msg_type == "Chat":
            text = msg.get("text", "")
            if text:
                # Relay to all peers including sender
                self._broadcast({"type": "Chat", "sender": player.name, "text": text})
                if self._cb.on_chat_received:
                    self._cb.on_chat_received(player.name, text)

        elif msg_type == "Ready":
            player.ready = msg.get("ready", False)
            # Notify GUI
            if self._cb.on_ready_changed:
                self._cb.on_ready_changed(player.player_id, player.ready)
            # Notify other peers
            self._broadcast(
                {
                    "type": "ReadyUpdate",
                    "player_id": player.player_id,
                    "ready": player.ready,
                }
            )

        elif msg_type == "FileRequest":
            # Joiner is requesting files (map, mod, etc.)
            if self._cb.on_file_request:
                category = msg.get("category", "map")
                name = msg.get("name", "")
                self._cb.on_file_request(player.player_id, category, name)

        elif msg_type == "Goodbye":
            self._remove_player(player.player_id)

    def _remove_player(self, player_id: int) -> None:
        """Remove a player and notify GUI + peers."""
        player = self._players.pop(player_id, None)
        if not player:
            return
        self._close_player(player)
        if self._cb.on_player_left:
            self._cb.on_player_left(player_id)
        self._broadcast({"type": "PlayerLeft", "player_id": player_id})

    @staticmethod
    def _close_player(player: _RemotePlayer) -> None:
        if player.sock:
            with contextlib.suppress(OSError):
                _send_msg(player.sock, {"type": "Goodbye"})
            with contextlib.suppress(OSError):
                player.sock.close()
            player.sock = None


# ---------------------------------------------------------------------------
# LobbyClient
# ---------------------------------------------------------------------------


class LobbyClient:
    """TCP lobby client run by joiners.

    Connects to the host's LobbyServer, receives lobby state updates,
    and waits for the Launch signal.
    """

    def __init__(
        self,
        host_address: str,
        port: int,
        player_name: str,
        faction: str,
        callbacks: LobbyCallbacks,
    ) -> None:
        self.host_address = host_address
        self.port = port
        self.player_name = player_name
        self.faction = faction
        self._cb = callbacks
        self._sock: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._player_id: int | None = None
        self._slot: int | None = None
        self._recv_buf = bytearray()

    # -- public API ----------------------------------------------------------

    def connect(self) -> None:
        """Connect to the host in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def disconnect(self) -> None:
        """Disconnect from the host."""
        self._running = False
        if self._sock:
            with contextlib.suppress(OSError):
                _send_msg(self._sock, {"type": "Goodbye"})
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        logger.info("Disconnected from lobby")

    def send_faction(self, faction: str) -> None:
        """Notify the host of a faction change."""
        self.faction = faction
        if self._sock:
            with contextlib.suppress(OSError):
                _send_msg(self._sock, {"type": "FactionChange", "faction": faction})

    def send_ready(self, ready: bool) -> None:
        """Send ready state to the host."""
        if self._sock:
            with contextlib.suppress(OSError):
                _send_msg(self._sock, {"type": "Ready", "ready": ready})

    def send_chat(self, text: str) -> None:
        """Send a chat message to the lobby."""
        if self._sock and text.strip():
            with contextlib.suppress(OSError):
                _send_msg(self._sock, {"type": "Chat", "text": text.strip()})

    def send_team(self, team: int) -> None:
        """Notify the host of a team change."""
        if self._sock:
            with contextlib.suppress(OSError):
                _send_msg(self._sock, {"type": "TeamChange", "team": team})

    def send_color(self, color: int) -> None:
        """Notify the host of a color change."""
        if self._sock:
            with contextlib.suppress(OSError):
                _send_msg(self._sock, {"type": "ColorChange", "color": color})

    def request_file(self, category: str, name: str) -> None:
        """Request a file transfer from the host (e.g., a missing map)."""
        if self._sock:
            with contextlib.suppress(OSError):
                _send_msg(
                    self._sock,
                    {"type": "FileRequest", "category": category, "name": name},
                )

    @property
    def is_connected(self) -> bool:
        return self._sock is not None and self._running

    @property
    def player_id(self) -> int | None:
        return self._player_id

    @property
    def slot(self) -> int | None:
        return self._slot

    # -- internals -----------------------------------------------------------

    def _run(self) -> None:
        """Connect and poll for messages."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(10.0)
            self._sock.connect((self.host_address, self.port))
            self._sock.settimeout(1.0)
            logger.info("Connected to %s:%d", self.host_address, self.port)

            # Send Hello
            _send_msg(
                self._sock,
                {
                    "type": "Hello",
                    "player_name": self.player_name,
                    "faction": self.faction,
                    "protocol_version": PROTOCOL_VERSION,
                },
            )

            # Wait for Welcome
            if not self._wait_for_welcome():
                raise ConnectionError("No Welcome received from host")

            if self._cb.on_connected:
                self._cb.on_connected()

            # Main loop
            last_heartbeat = time.monotonic()
            while self._running and self._sock:
                try:
                    lines = _recv_lines(self._sock, self._recv_buf)
                    for line in lines:
                        self._handle_message(json.loads(line))
                except (ConnectionResetError, OSError):
                    break
                except json.JSONDecodeError:
                    continue

                # Send periodic heartbeat
                now = time.monotonic()
                if now - last_heartbeat > HEARTBEAT_INTERVAL:
                    try:
                        _send_msg(self._sock, {"type": "Heartbeat"})
                    except OSError:
                        break
                    last_heartbeat = now

                time.sleep(0.2)

        except (OSError, ConnectionError) as exc:
            logger.error("Connection failed: %s", exc)
            if self._cb.on_error:
                self._cb.on_error(str(exc))

        self._running = False
        if self._cb.on_disconnected:
            self._cb.on_disconnected("Connection closed")

    def _wait_for_welcome(self) -> bool:
        """Block until Welcome is received (up to 10s)."""
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and self._running and self._sock:
            try:
                lines = _recv_lines(self._sock, self._recv_buf)
                for line in lines:
                    msg = json.loads(line)
                    if msg.get("type") == "Welcome":
                        self._player_id = msg.get("player_id")
                        self._slot = msg.get("slot")
                        logger.info(
                            "Welcome: player_id=%s, slot=%s",
                            self._player_id,
                            self._slot,
                        )
                        return True
            except (OSError, json.JSONDecodeError):
                pass
            time.sleep(0.1)
        return False

    def _handle_message(self, msg: dict[str, Any]) -> None:
        """Process a message from the host."""
        msg_type = msg.get("type", "")

        if msg_type == "Heartbeat":
            return

        if msg_type == "LobbyUpdate":
            if self._cb.on_state_updated:
                self._cb.on_state_updated(msg.get("lobby_state", {}))

        elif msg_type == "GameState":
            if self._cb.on_state_updated:
                self._cb.on_state_updated(msg.get("state", {}))

        elif msg_type == "PlayerJoined":
            if self._cb.on_player_joined:
                self._cb.on_player_joined(
                    msg["player_id"],
                    msg["player_name"],
                    msg["faction"],
                    msg["slot"],
                )

        elif msg_type == "PlayerLeft":
            if self._cb.on_player_left:
                self._cb.on_player_left(msg["player_id"])

        elif msg_type == "PlayerUpdate":
            # Partial player update (team/color change) — route via state_updated
            if self._cb.on_state_updated:
                self._cb.on_state_updated({"player_update": msg})

        elif msg_type == "ReadyUpdate":
            if self._cb.on_ready_changed:
                self._cb.on_ready_changed(msg["player_id"], msg["ready"])

        elif msg_type == "Chat":
            if self._cb.on_chat_received:
                self._cb.on_chat_received(msg.get("sender", "?"), msg.get("text", ""))

        elif msg_type == "FileManifest":
            if self._cb.on_file_manifest:
                self._cb.on_file_manifest(
                    msg.get("category", "map"),
                    msg.get("name", ""),
                    msg.get("files", []),
                )

        elif msg_type == "FileChunk":
            if self._cb.on_file_chunk:
                self._cb.on_file_chunk(
                    msg.get("category", "map"),
                    msg.get("path", ""),
                    msg.get("index", 0),
                    msg.get("total", 1),
                    msg.get("data", ""),
                )

        elif msg_type == "FileComplete":
            if self._cb.on_file_complete:
                self._cb.on_file_complete(
                    msg.get("category", "map"),
                    msg.get("name", ""),
                )

        elif msg_type == "Kicked":
            if self._cb.on_kicked:
                self._cb.on_kicked(msg.get("reason", "Kicked"))
            self._running = False

        elif msg_type == "Launch":
            if self._cb.on_launch:
                self._cb.on_launch(msg.get("host_port", "15000"))

        elif msg_type == "Goodbye":
            self._running = False
