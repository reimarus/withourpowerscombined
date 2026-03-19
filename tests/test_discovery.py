"""Tests for launcher.discovery — LAN game discovery via UDP beacons.

These tests use real UDP sockets and are marked slow.
Run locally with: pytest -m slow tests/test_discovery.py
"""

from __future__ import annotations

import json
import socket
import time

import pytest

from launcher.discovery import (
    BEACON_TYPE,
    BeaconBroadcaster,
    BeaconListener,
    GameBeacon,
)

pytestmark = pytest.mark.slow


def _find_free_port() -> int:
    """Return an ephemeral UDP port that is currently unused."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class TestBeaconSerialization:
    """Test GameBeacon creation and JSON round-trip."""

    def test_beacon_creation(self) -> None:
        """GameBeacon can be created with required fields."""
        b = GameBeacon(
            host_name="Alice",
            map_name="Theta Passage",
            player_count=2,
            max_players=4,
            lobby_port=15000,
        )
        assert b.host_name == "Alice"
        assert b.map_name == "Theta Passage"
        assert b.player_count == 2
        assert b.max_players == 4
        assert b.lobby_port == 15000
        assert b.host_ip == ""

    def test_beacon_json_round_trip(self) -> None:
        """Beacon data survives JSON encode/decode."""
        original = {
            "type": BEACON_TYPE,
            "host": "Bob",
            "map": "Seton's Clutch",
            "players": 3,
            "max": 8,
            "port": 15000,
            "ver": "0.1.0",
        }
        encoded = json.dumps(original).encode("utf-8")
        decoded = json.loads(encoded.decode("utf-8"))
        assert decoded["type"] == BEACON_TYPE
        assert decoded["host"] == "Bob"
        assert decoded["map"] == "Seton's Clutch"
        assert decoded["players"] == 3
        assert decoded["max"] == 8


class TestBroadcasterLifecycle:
    """Test BeaconBroadcaster start/stop without crashes."""

    def test_start_stop(self) -> None:
        """Broadcaster starts and stops cleanly."""
        port = _find_free_port()
        broadcaster = BeaconBroadcaster(
            port=port,
            lobby_port=15000,
            state_provider=lambda: {
                "host_name": "Test",
                "map_name": "Map",
                "player_count": 1,
                "max_players": 2,
            },
            target_address="127.0.0.1",
        )
        broadcaster.start()
        assert broadcaster.is_running
        time.sleep(0.5)
        broadcaster.stop()
        assert not broadcaster.is_running

    def test_double_start_is_safe(self) -> None:
        """Calling start() twice doesn't crash."""
        port = _find_free_port()
        broadcaster = BeaconBroadcaster(port=port, target_address="127.0.0.1")
        broadcaster.start()
        broadcaster.start()  # should be a no-op
        broadcaster.stop()

    def test_double_stop_is_safe(self) -> None:
        """Calling stop() twice doesn't crash."""
        port = _find_free_port()
        broadcaster = BeaconBroadcaster(port=port, target_address="127.0.0.1")
        broadcaster.start()
        broadcaster.stop()
        broadcaster.stop()  # should be a no-op


class TestListenerLifecycle:
    """Test BeaconListener start/stop without crashes."""

    def test_start_stop(self) -> None:
        """Listener starts and stops cleanly."""
        port = _find_free_port()
        listener = BeaconListener(port=port)
        listener.start()
        assert listener.is_running
        time.sleep(0.5)
        listener.stop()
        assert not listener.is_running

    def test_double_start_is_safe(self) -> None:
        """Calling start() twice doesn't crash."""
        port = _find_free_port()
        listener = BeaconListener(port=port)
        listener.start()
        listener.start()
        listener.stop()

    def test_games_empty_initially(self) -> None:
        """No games discovered before any beacons arrive."""
        port = _find_free_port()
        listener = BeaconListener(port=port)
        listener.start()
        time.sleep(0.3)
        assert listener.games == []
        listener.stop()


class TestDiscoveryLoopback:
    """End-to-end: broadcaster sends beacons, listener discovers them."""

    def test_discovery_on_loopback(self) -> None:
        """Listener discovers a game broadcast on loopback."""
        port = _find_free_port()
        discovered: list[list[GameBeacon]] = []

        def on_update(games: list[GameBeacon]) -> None:
            discovered.append(games)

        # The listener filters out local IPs by default.
        # For loopback testing, we need to bypass that filter.
        listener = BeaconListener(port=port, on_update=on_update)
        listener.start()
        listener._local_ips = set()  # Clear AFTER start() so 127.0.0.1 isn't filtered

        broadcaster = BeaconBroadcaster(
            port=port,
            lobby_port=15000,
            state_provider=lambda: {
                "host_name": "TestHost",
                "map_name": "Test Map",
                "player_count": 2,
                "max_players": 4,
            },
            target_address="127.0.0.1",
        )
        broadcaster.start()

        # Wait for at least one beacon to arrive
        deadline = time.monotonic() + 5.0
        while not discovered and time.monotonic() < deadline:
            time.sleep(0.2)

        broadcaster.stop()
        listener.stop()

        assert len(discovered) > 0, "No beacons received"
        games = discovered[-1]
        assert len(games) == 1
        assert games[0].host_name == "TestHost"
        assert games[0].map_name == "Test Map"
        assert games[0].player_count == 2
        assert games[0].max_players == 4
        assert games[0].lobby_port == 15000
        assert games[0].host_ip == "127.0.0.1"


class TestStalePruning:
    """Test that games disappear when beacons stop arriving."""

    def test_game_pruned_after_timeout(self) -> None:
        """A game is removed from the list when no beacon for STALE_TIMEOUT."""
        port = _find_free_port()
        updates: list[list[GameBeacon]] = []

        def on_update(games: list[GameBeacon]) -> None:
            updates.append(list(games))

        listener = BeaconListener(port=port, on_update=on_update)
        listener.start()
        listener._local_ips = set()  # Clear AFTER start()

        # Send a single beacon manually
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        beacon = json.dumps(
            {
                "type": BEACON_TYPE,
                "host": "Ephemeral",
                "map": "Gone Soon",
                "players": 1,
                "max": 2,
                "port": 16000,
                "ver": "0.1.0",
            }
        ).encode("utf-8")
        sock.sendto(beacon, ("127.0.0.1", port))
        sock.close()

        # Wait for discovery
        deadline = time.monotonic() + 3.0
        while not updates and time.monotonic() < deadline:
            time.sleep(0.2)

        assert len(updates) > 0, "Beacon was not discovered"
        assert any(len(u) > 0 for u in updates), "No games in any update"

        # Now wait for stale pruning (8s + margin)
        time.sleep(9.0)

        # The listener should have pruned it
        assert listener.games == [], f"Expected empty, got {listener.games}"

        listener.stop()


class TestMultipleHosts:
    """Test that listener can see multiple hosts simultaneously."""

    def test_two_broadcasters_discovered(self) -> None:
        """Listener sees games from two different broadcasters."""
        port = _find_free_port()
        updates: list[list[GameBeacon]] = []

        def on_update(games: list[GameBeacon]) -> None:
            updates.append(list(games))

        listener = BeaconListener(port=port, on_update=on_update)
        listener.start()
        listener._local_ips = set()  # Clear AFTER start()

        # Send two different beacons manually (different lobby ports = different games)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        for i, (name, lobby_port) in enumerate([("Alice", 15000), ("Bob", 15001)]):
            beacon = json.dumps(
                {
                    "type": BEACON_TYPE,
                    "host": name,
                    "map": f"Map {i}",
                    "players": 1,
                    "max": 4,
                    "port": lobby_port,
                    "ver": "0.1.0",
                }
            ).encode("utf-8")
            sock.sendto(beacon, ("127.0.0.1", port))
            time.sleep(0.1)

        sock.close()

        # Wait for both to be discovered
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if any(len(u) >= 2 for u in updates):
                break
            time.sleep(0.2)

        listener.stop()

        found_two = any(len(u) >= 2 for u in updates)
        assert found_two, f"Expected 2 games, updates: {[len(u) for u in updates]}"

        # Verify both hosts are present
        last_with_two = [u for u in updates if len(u) >= 2][-1]
        names = {g.host_name for g in last_with_two}
        assert "Alice" in names
        assert "Bob" in names
