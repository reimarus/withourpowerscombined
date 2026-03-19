"""Tests for launcher.lobby — TCP lobby server and client."""

from __future__ import annotations

import json
import socket
import threading
import time

from launcher.lobby import (
    ENCODING,
    PROTOCOL_VERSION,
    LobbyCallbacks,
    LobbyClient,
    LobbyServer,
    _send_msg,
)


def _find_free_port() -> int:
    """Return an ephemeral TCP port that is currently unused."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _raw_connect(port: int, name: str = "Tester", faction: str = "uef") -> socket.socket:
    """Low-level connect + Hello handshake, return the socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect(("127.0.0.1", port))
    _send_msg(sock, {"type": "Hello", "player_name": name, "faction": faction})
    return sock


def _read_msg(sock: socket.socket, timeout: float = 5.0) -> dict:
    """Read a single JSON message from the socket."""
    sock.settimeout(timeout)
    buf = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionResetError
        buf += chunk
        if b"\n" in buf:
            line, _, _ = buf.partition(b"\n")
            return json.loads(line.decode(ENCODING))
    raise TimeoutError("No message received")


# ---------------------------------------------------------------------------
# Server tests
# ---------------------------------------------------------------------------


class TestLobbyServer:
    """LobbyServer basic functionality."""

    def test_start_stop(self):
        """Server starts and stops without error."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()
        assert server.is_running
        server.stop()
        assert not server.is_running

    def test_accept_connection(self):
        """Server accepts a client and fires on_player_joined."""
        port = _find_free_port()
        joined = threading.Event()
        joined_data: dict = {}

        def on_join(pid, name, faction, slot):
            joined_data.update(pid=pid, name=name, faction=faction, slot=slot)
            joined.set()

        server = LobbyServer(port, LobbyCallbacks(on_player_joined=on_join))
        server.start()
        try:
            sock = _raw_connect(port, "Alice", "aeon")
            welcome = _read_msg(sock)
            assert welcome["type"] == "Welcome"
            assert welcome["protocol_version"] == PROTOCOL_VERSION
            assert "player_id" in welcome
            assert "slot" in welcome

            assert joined.wait(timeout=5.0)
            assert joined_data["name"] == "Alice"
            assert joined_data["faction"] == "aeon"
            assert joined_data["slot"] == 2  # host is slot 1
            sock.close()
        finally:
            server.stop()

    def test_multiple_connections(self):
        """Server assigns sequential slots to multiple peers."""
        port = _find_free_port()
        joins: list[dict] = []
        lock = threading.Lock()

        def on_join(pid, name, faction, slot):
            with lock:
                joins.append({"pid": pid, "name": name, "slot": slot})

        server = LobbyServer(port, LobbyCallbacks(on_player_joined=on_join))
        server.start()
        try:
            s1 = _raw_connect(port, "P1", "uef")
            _read_msg(s1)  # Welcome
            time.sleep(0.1)

            s2 = _raw_connect(port, "P2", "cybran")
            _read_msg(s2)  # Welcome
            time.sleep(0.1)

            with lock:
                assert len(joins) == 2
            slots = sorted(j["slot"] for j in joins)
            assert slots == [2, 3]

            assert len(server.connected_players) == 2
            s1.close()
            s2.close()
        finally:
            server.stop()

    def test_ready_state(self):
        """Ready message from client triggers callback and broadcast."""
        port = _find_free_port()
        ready_events: list[tuple[int, bool]] = []
        lock = threading.Lock()

        def on_ready(pid, ready):
            with lock:
                ready_events.append((pid, ready))

        server = LobbyServer(port, LobbyCallbacks(on_ready_changed=on_ready))
        server.start()
        try:
            sock = _raw_connect(port, "Bob")
            welcome = _read_msg(sock)
            pid = welcome["player_id"]
            time.sleep(0.1)

            _send_msg(sock, {"type": "Ready", "ready": True})
            time.sleep(0.3)

            with lock:
                assert any(r == (pid, True) for r in ready_events)
            sock.close()
        finally:
            server.stop()

    def test_player_disconnect(self):
        """Disconnecting a client fires on_player_left."""
        port = _find_free_port()
        left_ids: list[int] = []
        left_event = threading.Event()

        def on_left(pid):
            left_ids.append(pid)
            left_event.set()

        server = LobbyServer(
            port,
            LobbyCallbacks(on_player_left=on_left),
        )
        server.start()
        try:
            sock = _raw_connect(port, "Temp")
            _read_msg(sock)
            time.sleep(0.1)

            _send_msg(sock, {"type": "Goodbye"})
            sock.close()

            assert left_event.wait(timeout=5.0)
            assert len(left_ids) >= 1
        finally:
            server.stop()

    def test_broadcast_state(self):
        """broadcast_state sends LobbyUpdate to connected peers."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()
        try:
            sock = _raw_connect(port, "Watcher")
            _read_msg(sock)  # Welcome
            time.sleep(0.1)

            state = {"map": "Caldera", "options": {"Victory": "demoralization"}}
            server.broadcast_state(state)
            time.sleep(0.1)

            # Drain messages until we find LobbyUpdate
            sock.settimeout(3.0)
            buf = b""
            found = False
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                try:
                    buf += sock.recv(65536)
                except TimeoutError:
                    break
                for line in buf.split(b"\n"):
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if msg.get("type") == "LobbyUpdate":
                            assert msg["lobby_state"]["map"] == "Caldera"
                            found = True
                    except json.JSONDecodeError:
                        pass
                if found:
                    break
            assert found, "LobbyUpdate not received"
            sock.close()
        finally:
            server.stop()

    def test_broadcast_launch(self):
        """broadcast_launch sends Launch to connected peers."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()
        try:
            sock = _raw_connect(port, "Player")
            _read_msg(sock)  # Welcome
            time.sleep(0.1)

            server.broadcast_launch("15000")
            time.sleep(0.1)

            sock.settimeout(3.0)
            buf = b""
            found = False
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                try:
                    buf += sock.recv(65536)
                except TimeoutError:
                    break
                for line in buf.split(b"\n"):
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if msg.get("type") == "Launch":
                            assert msg["host_port"] == "15000"
                            found = True
                    except json.JSONDecodeError:
                        pass
                if found:
                    break
            assert found, "Launch not received"
            sock.close()
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class TestLobbyClient:
    """LobbyClient basic functionality."""

    def test_connect_and_disconnect(self):
        """Client connects, gets Welcome, then disconnects."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()

        connected_event = threading.Event()
        disconnected_event = threading.Event()

        client = LobbyClient(
            "127.0.0.1",
            port,
            "TestPlayer",
            "cybran",
            LobbyCallbacks(
                on_connected=lambda: connected_event.set(),
                on_disconnected=lambda reason: disconnected_event.set(),
            ),
        )
        try:
            client.connect()
            assert connected_event.wait(timeout=10.0), "Client did not connect"
            assert client.is_connected
            assert client.player_id is not None
            assert client.slot is not None

            client.disconnect()
            assert not client.is_connected
        finally:
            client.disconnect()
            server.stop()

    def test_receive_lobby_update(self):
        """Client receives LobbyUpdate from server."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()

        connected = threading.Event()
        state_received = threading.Event()
        received_state: dict = {}

        def on_state(state):
            received_state.update(state)
            state_received.set()

        client = LobbyClient(
            "127.0.0.1",
            port,
            "Viewer",
            "uef",
            LobbyCallbacks(
                on_connected=lambda: connected.set(),
                on_state_updated=on_state,
            ),
        )
        try:
            client.connect()
            assert connected.wait(timeout=10.0)
            time.sleep(0.1)

            server.broadcast_state({"map": "Theta Passage", "players": 4})
            assert state_received.wait(timeout=5.0), "LobbyUpdate not received"
            assert received_state["map"] == "Theta Passage"
        finally:
            client.disconnect()
            server.stop()

    def test_receive_launch(self):
        """Client receives Launch signal from server."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()

        connected = threading.Event()
        launch_event = threading.Event()
        launch_port: list[str] = []

        def on_launch(hp):
            launch_port.append(hp)
            launch_event.set()

        client = LobbyClient(
            "127.0.0.1",
            port,
            "Launcher",
            "seraphim",
            LobbyCallbacks(
                on_connected=lambda: connected.set(),
                on_launch=on_launch,
            ),
        )
        try:
            client.connect()
            assert connected.wait(timeout=10.0)
            time.sleep(0.1)

            server.broadcast_launch("16000")
            assert launch_event.wait(timeout=5.0), "Launch not received"
            assert launch_port[0] == "16000"
        finally:
            client.disconnect()
            server.stop()

    def test_send_ready(self):
        """Client sends Ready, host receives it."""
        port = _find_free_port()
        ready_received = threading.Event()

        def on_ready(pid, ready):
            if ready:
                ready_received.set()

        server = LobbyServer(port, LobbyCallbacks(on_ready_changed=on_ready))
        server.start()

        connected = threading.Event()
        client = LobbyClient(
            "127.0.0.1",
            port,
            "ReadyPlayer",
            "uef",
            LobbyCallbacks(on_connected=lambda: connected.set()),
        )
        try:
            client.connect()
            assert connected.wait(timeout=10.0)
            time.sleep(0.1)

            client.send_ready(True)
            assert ready_received.wait(timeout=5.0), "Ready not received by server"
        finally:
            client.disconnect()
            server.stop()

    def test_connection_refused(self):
        """Client handles connection failure gracefully."""
        port = _find_free_port()  # No server on this port
        error_event = threading.Event()
        error_msgs: list[str] = []

        def on_error(msg):
            error_msgs.append(msg)
            error_event.set()

        client = LobbyClient(
            "127.0.0.1",
            port,
            "Orphan",
            "uef",
            LobbyCallbacks(on_error=on_error),
        )
        try:
            client.connect()
            assert error_event.wait(timeout=5.0), "Error callback not fired"
            assert len(error_msgs) > 0
        finally:
            client.disconnect()


# ---------------------------------------------------------------------------
# New feature tests (P1)
# ---------------------------------------------------------------------------


class TestChatMessages:
    """Chat message relay between server and clients."""

    def test_server_broadcast_chat(self):
        """Server broadcasts chat to all connected peers."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()
        try:
            sock = _raw_connect(port, "Chatter")
            _read_msg(sock)  # Welcome
            time.sleep(0.1)

            server.broadcast_chat("Host", "Hello everyone!")
            time.sleep(0.1)

            sock.settimeout(3.0)
            buf = b""
            found = False
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                try:
                    buf += sock.recv(65536)
                except TimeoutError:
                    break
                for line in buf.split(b"\n"):
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if msg.get("type") == "Chat":
                            assert msg["sender"] == "Host"
                            assert msg["text"] == "Hello everyone!"
                            found = True
                    except json.JSONDecodeError:
                        pass
                if found:
                    break
            assert found, "Chat message not received"
            sock.close()
        finally:
            server.stop()

    def test_client_chat_relay(self):
        """Client sends Chat, server relays it to all peers (including host GUI)."""
        port = _find_free_port()
        chat_received = threading.Event()
        received: list[tuple[str, str]] = []

        def on_chat(sender, text):
            received.append((sender, text))
            chat_received.set()

        server = LobbyServer(port, LobbyCallbacks(on_chat_received=on_chat))
        server.start()

        connected = threading.Event()
        client = LobbyClient(
            "127.0.0.1",
            port,
            "Alice",
            "uef",
            LobbyCallbacks(on_connected=lambda: connected.set()),
        )
        try:
            client.connect()
            assert connected.wait(timeout=10.0)
            time.sleep(0.1)

            client.send_chat("Hi from Alice!")
            assert chat_received.wait(timeout=5.0)
            assert received[0] == ("Alice", "Hi from Alice!")
        finally:
            client.disconnect()
            server.stop()


class TestKickPlayer:
    """Host kicks a player from the lobby."""

    def test_kick_fires_callback_and_removes(self):
        """Kick sends Kicked message and removes player."""
        port = _find_free_port()
        left_event = threading.Event()

        def on_left(pid):
            left_event.set()

        server = LobbyServer(port, LobbyCallbacks(on_player_left=on_left))
        server.start()

        kicked_event = threading.Event()
        kicked_reason: list[str] = []

        client = LobbyClient(
            "127.0.0.1",
            port,
            "Victim",
            "uef",
            LobbyCallbacks(
                on_connected=lambda: None,
                on_kicked=lambda reason: (kicked_reason.append(reason), kicked_event.set()),
            ),
        )
        try:
            connected = threading.Event()
            client._cb.on_connected = lambda: connected.set()
            client.connect()
            assert connected.wait(timeout=10.0)
            time.sleep(0.1)

            pid = client.player_id
            assert pid is not None
            server.kick_player(pid, "No griefing")

            assert left_event.wait(timeout=5.0), "on_player_left not fired"
            assert kicked_event.wait(timeout=5.0), "on_kicked not fired"
            assert kicked_reason[0] == "No griefing"
            assert len(server.connected_players) == 0
        finally:
            client.disconnect()
            server.stop()


class TestGameStateProvider:
    """Game state snapshot sent to new joiners on connect."""

    def test_state_sent_on_connect(self):
        """New joiner receives GameState after Welcome."""
        port = _find_free_port()

        def provide_state():
            return {"map_name": "Theta Passage", "game_options": {"Victory": "Sandbox"}}

        server = LobbyServer(port, LobbyCallbacks(), game_state_provider=provide_state)
        server.start()
        try:
            sock = _raw_connect(port, "Viewer")
            welcome = _read_msg(sock)
            assert welcome["type"] == "Welcome"

            # Next message should be GameState
            state_msg = _read_msg(sock)
            assert state_msg["type"] == "GameState"
            assert state_msg["state"]["map_name"] == "Theta Passage"
            assert state_msg["state"]["game_options"]["Victory"] == "Sandbox"
            sock.close()
        finally:
            server.stop()

    def test_no_state_when_provider_none(self):
        """No GameState sent if provider is not set."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()
        try:
            sock = _raw_connect(port, "Viewer")
            welcome = _read_msg(sock)
            assert welcome["type"] == "Welcome"

            # Next message should NOT be GameState — should be PlayerJoined or Heartbeat
            sock.settimeout(1.0)
            buf = b""
            got_game_state = False
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                try:
                    buf += sock.recv(65536)
                except TimeoutError:
                    break
                for line in buf.split(b"\n"):
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if msg.get("type") == "GameState":
                            got_game_state = True
                    except json.JSONDecodeError:
                        pass
            assert not got_game_state, "GameState should not be sent without provider"
            sock.close()
        finally:
            server.stop()


class TestTeamColorChange:
    """Clients can change team and color."""

    def test_team_change_from_client(self):
        """Client sends TeamChange, server updates player record."""
        port = _find_free_port()
        join_event = threading.Event()

        def on_join(pid, name, faction, slot):
            join_event.set()

        server = LobbyServer(port, LobbyCallbacks(on_player_joined=on_join))
        server.start()

        connected = threading.Event()
        client = LobbyClient(
            "127.0.0.1",
            port,
            "TeamPlayer",
            "cybran",
            LobbyCallbacks(on_connected=lambda: connected.set()),
        )
        try:
            client.connect()
            assert connected.wait(timeout=10.0)
            assert join_event.wait(timeout=5.0)
            time.sleep(0.1)

            client.send_team(3)
            time.sleep(0.3)

            # Verify server updated the player record
            players = server.connected_players
            assert len(players) == 1
            assert players[0]["team"] == 3
        finally:
            client.disconnect()
            server.stop()

    def test_color_change_from_client(self):
        """Client sends ColorChange, server updates player record."""
        port = _find_free_port()
        join_event = threading.Event()

        def on_join(pid, name, faction, slot):
            join_event.set()

        server = LobbyServer(port, LobbyCallbacks(on_player_joined=on_join))
        server.start()

        connected = threading.Event()
        client = LobbyClient(
            "127.0.0.1",
            port,
            "ColorPlayer",
            "uef",
            LobbyCallbacks(on_connected=lambda: connected.set()),
        )
        try:
            client.connect()
            assert connected.wait(timeout=10.0)
            assert join_event.wait(timeout=5.0)
            time.sleep(0.1)

            client.send_color(5)
            time.sleep(0.3)

            players = server.connected_players
            assert len(players) == 1
            assert players[0]["color"] == 5
        finally:
            client.disconnect()
            server.stop()


class TestClientSendChat:
    """Client chat helpers."""

    def test_send_chat_empty_ignored(self):
        """Empty chat messages are not sent."""
        port = _find_free_port()
        server = LobbyServer(port, LobbyCallbacks())
        server.start()

        connected = threading.Event()
        client = LobbyClient(
            "127.0.0.1",
            port,
            "Silent",
            "uef",
            LobbyCallbacks(on_connected=lambda: connected.set()),
        )
        try:
            client.connect()
            assert connected.wait(timeout=10.0)
            # Should not raise or send anything
            client.send_chat("")
            client.send_chat("   ")
        finally:
            client.disconnect()
            server.stop()
