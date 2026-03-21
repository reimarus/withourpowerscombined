"""Tests for launcher.relay — internet game discovery via Firebase REST.

All HTTP calls are mocked via patch("launcher.relay.urllib.request.urlopen")
so no real network access is required.
"""

from __future__ import annotations

import json
import time
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from launcher.relay import _GAME_EXPIRY, RelayClient, get_public_ip

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(body: bytes, status: int = 200) -> MagicMock:
    """Build a fake urlopen response."""
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status
    return resp


def _game_record(
    host_name: str = "Alice",
    map_name: str = "Theta Passage",
    player_count: int = 1,
    max_players: int = 4,
    lobby_port: int = 15000,
    host_ip: str = "203.0.113.5",
    last_seen: float | None = None,
) -> dict:
    return {
        "host_name": host_name,
        "map_name": map_name,
        "player_count": player_count,
        "max_players": max_players,
        "lobby_port": lobby_port,
        "host_ip": host_ip,
        "last_seen": last_seen if last_seen is not None else time.time(),
    }


# ---------------------------------------------------------------------------
# get_public_ip
# ---------------------------------------------------------------------------


class TestGetPublicIp:
    def test_returns_ip_on_success(self) -> None:
        with patch(
            "launcher.relay.urllib.request.urlopen",
            return_value=_make_response(b"203.0.113.5"),
        ):
            assert get_public_ip() == "203.0.113.5"

    def test_strips_whitespace(self) -> None:
        with patch(
            "launcher.relay.urllib.request.urlopen",
            return_value=_make_response(b"  203.0.113.5\n"),
        ):
            assert get_public_ip() == "203.0.113.5"

    def test_returns_none_on_urlerror(self) -> None:
        with patch(
            "launcher.relay.urllib.request.urlopen",
            side_effect=urllib.error.URLError("timeout"),
        ):
            assert get_public_ip() is None

    def test_returns_none_on_oserror(self) -> None:
        with patch(
            "launcher.relay.urllib.request.urlopen",
            side_effect=OSError("network unreachable"),
        ):
            assert get_public_ip() is None

    def test_returns_none_on_empty_response(self) -> None:
        with patch(
            "launcher.relay.urllib.request.urlopen",
            return_value=_make_response(b""),
        ):
            assert get_public_ip() is None


# ---------------------------------------------------------------------------
# RelayClient.register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_success_returns_true_and_stores_game_id(self) -> None:
        client = RelayClient()
        with (
            patch("launcher.relay.urllib.request.urlopen", return_value=_make_response(b"{}")),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            result = client.register("Alice", "Theta", 1, 4, 15000, "1.2.3.4")
        assert result is True
        assert client._game_id is not None

    def test_relay_url_empty_returns_false_without_http(self) -> None:
        client = RelayClient()
        with (
            patch("launcher.relay.urllib.request.urlopen") as mock_open,
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = ""
            result = client.register("Alice", "Theta", 1, 4, 15000, "1.2.3.4")
        assert result is False
        mock_open.assert_not_called()

    def test_http_error_returns_false(self) -> None:
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                side_effect=urllib.error.URLError("403"),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            result = client.register("Alice", "Theta", 1, 4, 15000, "1.2.3.4")
        assert result is False
        assert client._game_id is None

    def test_network_error_returns_false(self) -> None:
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                side_effect=OSError("connection refused"),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            result = client.register("Alice", "Theta", 1, 4, 15000, "1.2.3.4")
        assert result is False

    def test_put_url_contains_game_id(self) -> None:
        client = RelayClient()
        with (
            patch("launcher.relay.urllib.request.urlopen", return_value=_make_response(b"{}")),
            patch("launcher.relay.urllib.request.Request") as mock_req,
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            client.register("Alice", "Theta", 1, 4, 15000, "1.2.3.4")
            url_arg = mock_req.call_args[0][0]
        assert "/games/" in url_arg
        assert url_arg.endswith(".json")


# ---------------------------------------------------------------------------
# RelayClient.update
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_sends_patch_with_last_seen(self) -> None:
        client = RelayClient()
        client._game_id = "test-game-id"
        with (
            patch("launcher.relay.urllib.request.urlopen", return_value=_make_response(b"{}")),
            patch("launcher.relay.urllib.request.Request") as mock_req,
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            client.update("Alice", "Theta", 2, 4)
            _, kwargs = mock_req.call_args
            assert kwargs.get("method") == "PATCH"
            sent_data = json.loads(mock_req.call_args[1]["data"])
        assert "last_seen" in sent_data
        assert sent_data["player_count"] == 2

    def test_noop_if_no_game_id(self) -> None:
        client = RelayClient()
        with (
            patch("launcher.relay.urllib.request.urlopen") as mock_open,
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            client.update("Alice", "Theta", 1, 4)
        mock_open.assert_not_called()

    def test_silently_ignores_network_error(self) -> None:
        client = RelayClient()
        client._game_id = "test-id"
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                side_effect=OSError("network unreachable"),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            client.update("Alice", "Theta", 1, 4)  # must not raise


# ---------------------------------------------------------------------------
# RelayClient.deregister
# ---------------------------------------------------------------------------


class TestDeregister:
    def test_sends_delete_and_clears_game_id(self) -> None:
        client = RelayClient()
        client._game_id = "test-game-id"
        with (
            patch("launcher.relay.urllib.request.urlopen", return_value=_make_response(b"null")),
            patch("launcher.relay.urllib.request.Request") as mock_req,
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            client.deregister()
            method = mock_req.call_args[1].get("method")
        assert method == "DELETE"
        assert client._game_id is None

    def test_clears_game_id_even_on_error(self) -> None:
        client = RelayClient()
        client._game_id = "test-id"
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                side_effect=OSError("network error"),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            client.deregister()  # must not raise
        assert client._game_id is None

    def test_noop_if_no_game_id(self) -> None:
        client = RelayClient()
        with (
            patch("launcher.relay.urllib.request.urlopen") as mock_open,
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            client.deregister()
        mock_open.assert_not_called()


# ---------------------------------------------------------------------------
# RelayClient.fetch_games
# ---------------------------------------------------------------------------


class TestFetchGames:
    def test_returns_empty_when_relay_url_not_configured(self) -> None:
        client = RelayClient()
        with (
            patch("launcher.relay.urllib.request.urlopen") as mock_open,
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = ""
            games = client.fetch_games()
        assert games == []
        mock_open.assert_not_called()

    def test_returns_empty_when_firebase_returns_null(self) -> None:
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                return_value=_make_response(b"null"),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            games = client.fetch_games()
        assert games == []

    def test_returns_empty_on_network_error(self) -> None:
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                side_effect=urllib.error.URLError("no route"),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            games = client.fetch_games()
        assert games == []

    def test_returns_empty_on_json_error(self) -> None:
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                return_value=_make_response(b"not-valid-json{{{"),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            games = client.fetch_games()
        assert games == []

    def test_returns_fresh_games_with_internet_source(self) -> None:
        payload = {"g1": _game_record(host_name="Bob", host_ip="5.6.7.8")}
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                return_value=_make_response(json.dumps(payload).encode()),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            games = client.fetch_games()
        assert len(games) == 1
        assert games[0].host_name == "Bob"
        assert games[0].host_ip == "5.6.7.8"
        assert games[0].source == "internet"

    def test_filters_stale_games(self) -> None:
        stale_ts = time.time() - (_GAME_EXPIRY + 30)
        fresh_ts = time.time() - 10
        payload = {
            "stale": _game_record(host_name="Old", host_ip="1.1.1.1", last_seen=stale_ts),
            "fresh": _game_record(host_name="New", host_ip="2.2.2.2", last_seen=fresh_ts),
        }
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                return_value=_make_response(json.dumps(payload).encode()),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            games = client.fetch_games()
        assert len(games) == 1
        assert games[0].host_name == "New"

    def test_skips_malformed_records(self) -> None:
        payload = {
            "good": _game_record(host_name="Good"),
            "bad": {"host_name": "Missing required fields"},
        }
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                return_value=_make_response(json.dumps(payload).encode()),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            games = client.fetch_games()
        assert len(games) == 1
        assert games[0].host_name == "Good"

    def test_returns_multiple_games(self) -> None:
        payload = {
            "g1": _game_record(host_name="Alice", host_ip="1.1.1.1"),
            "g2": _game_record(host_name="Bob", host_ip="2.2.2.2"),
            "g3": _game_record(host_name="Carol", host_ip="3.3.3.3"),
        }
        client = RelayClient()
        with (
            patch(
                "launcher.relay.urllib.request.urlopen",
                return_value=_make_response(json.dumps(payload).encode()),
            ),
            patch("launcher.relay.config") as mock_cfg,
        ):
            mock_cfg.RELAY_URL = "https://example.firebaseio.com"
            games = client.fetch_games()
        assert len(games) == 3
        names = {g.host_name for g in games}
        assert names == {"Alice", "Bob", "Carol"}


# ---------------------------------------------------------------------------
# Heartbeat thread
# ---------------------------------------------------------------------------


class TestHeartbeatThread:
    @pytest.mark.slow
    def test_heartbeat_calls_update_at_interval(self) -> None:
        update_calls: list[float] = []

        def fake_update(**_kwargs: object) -> None:
            update_calls.append(time.monotonic())

        client = RelayClient()
        client._game_id = "test-id"
        client._heartbeat_interval = 0.1  # fast for testing

        state = {"host_name": "X", "map_name": "Y", "player_count": 1, "max_players": 2}
        with patch.object(client, "update", side_effect=fake_update):
            client.start_heartbeat(lambda: state)
            time.sleep(0.45)
            client.stop_heartbeat()

        assert len(update_calls) >= 3

    def test_start_twice_is_safe(self) -> None:
        client = RelayClient()
        client._heartbeat_interval = 100.0  # won't fire during test
        with patch.object(client, "update"):
            client.start_heartbeat(lambda: {})
            thread_before = client._heartbeat_thread
            client.start_heartbeat(lambda: {})  # second call is a no-op
            thread_after = client._heartbeat_thread
        assert thread_before is thread_after
        client.stop_heartbeat()

    def test_stop_terminates_thread(self) -> None:
        client = RelayClient()
        client._heartbeat_interval = 100.0
        with patch.object(client, "update"):
            client.start_heartbeat(lambda: {})
            assert client._heartbeat_thread is not None
            assert client._heartbeat_thread.is_alive()
            client.stop_heartbeat()
        assert client._heartbeat_thread is None
        assert not client._running
