"""Internet game relay — register and discover WOPC games via Firebase.

Hosts write their game entry to a Firebase Realtime Database node;
joiners poll (or could subscribe) to discover active games worldwide.
LAN UDP beacons continue to run in parallel for same-network players.

Firebase REST API (no SDK required — stdlib urllib only)::

    PUT    {RELAY_URL}/games/{game_id}.json   → register / heartbeat
    PATCH  {RELAY_URL}/games/{game_id}.json   → update mutable fields
    DELETE {RELAY_URL}/games/{game_id}.json   → deregister
    GET    {RELAY_URL}/games.json             → fetch all games

Games expire client-side: entries with ``last_seen`` older than
``_GAME_EXPIRY`` seconds are silently skipped in :meth:`fetch_games`.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from launcher import config

if TYPE_CHECKING:
    from launcher.discovery import GameBeacon

logger = logging.getLogger("wopc.relay")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HEARTBEAT_INTERVAL = 30.0  # seconds between PUTs while hosting
_GAME_EXPIRY = 90.0  # seconds; games older than this are ignored on fetch
_HTTP_TIMEOUT = 5  # seconds for relay HTTP calls
_IP_TIMEOUT = 3  # seconds for public-IP lookup


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def get_public_ip() -> str | None:
    """Return this machine's public IPv4 address, or None on failure.

    Queries ``https://api.ipify.org`` (plain-text response).  Times out after
    ``_IP_TIMEOUT`` seconds.  Logs a warning but does not raise on failure.
    """
    try:
        req = urllib.request.Request(
            "https://api.ipify.org",
            headers={"Accept": "text/plain"},
        )
        resp = urllib.request.urlopen(req, timeout=_IP_TIMEOUT)
        ip: str = resp.read().decode("ascii").strip()
        if ip:
            logger.debug("Public IP resolved: %s", ip)
            return ip
    except (OSError, urllib.error.URLError) as exc:
        logger.warning("Failed to resolve public IP: %s", exc)
    return None


# ---------------------------------------------------------------------------
# RelayClient
# ---------------------------------------------------------------------------


class RelayClient:
    """Register, heartbeat, and discover internet games via Firebase REST.

    One instance per session: the host creates a client, calls
    :meth:`register`, then :meth:`start_heartbeat`.  On game end, call
    :meth:`deregister` (or :meth:`stop` as a combined convenience).

    Joiners (and the browser polling loop) create a *throw-away* instance
    per call to :meth:`fetch_games` — there is no connection state to maintain
    on the joiner side.
    """

    def __init__(self) -> None:
        self._game_id: str | None = None
        self._running = False
        self._heartbeat_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # Overridable in tests to speed up the heartbeat loop
        self._heartbeat_interval: float = _HEARTBEAT_INTERVAL

    # ------------------------------------------------------------------
    # Host side
    # ------------------------------------------------------------------

    def register(
        self,
        host_name: str,
        map_name: str,
        player_count: int,
        max_players: int,
        lobby_port: int,
        public_ip: str,
        game_name: str = "",
        upnp_ok: bool = False,
    ) -> bool:
        """Write a new game record to Firebase.  Returns True on success.

        Stores the generated ``game_id`` internally so subsequent
        :meth:`update` / :meth:`deregister` calls target the same record.
        """
        if not config.RELAY_URL:
            return False

        game_id = str(uuid.uuid4())
        url = f"{config.RELAY_URL}/games/{game_id}.json"
        payload: dict[str, Any] = {
            "host_name": host_name,
            "game_name": game_name,
            "map_name": map_name,
            "player_count": player_count,
            "max_players": max_players,
            "lobby_port": lobby_port,
            "host_ip": public_ip,
            "upnp_ok": upnp_ok,
            "last_seen": time.time(),
        }
        try:
            self._http("PUT", url, payload)
            with self._lock:
                self._game_id = game_id
            logger.info("Registered on relay as game %s", game_id)
            self._log_event(
                "game_created",
                {
                    "game_id": game_id,
                    "host_name": host_name,
                    "game_name": game_name,
                    "map_name": map_name,
                    "max_players": max_players,
                    "host_ip": public_ip,
                },
            )
            return True
        except (OSError, urllib.error.URLError) as exc:
            logger.warning("Relay registration failed: %s", exc)
            return False

    def update(
        self,
        host_name: str,
        map_name: str,
        player_count: int,
        max_players: int,
        game_name: str = "",
    ) -> None:
        """PATCH mutable fields and refresh ``last_seen``.

        Silent no-op if not registered or if the relay is unreachable.
        """
        with self._lock:
            game_id = self._game_id
        if not game_id or not config.RELAY_URL:
            return
        url = f"{config.RELAY_URL}/games/{game_id}.json"
        payload: dict[str, Any] = {
            "host_name": host_name,
            "game_name": game_name,
            "map_name": map_name,
            "player_count": player_count,
            "max_players": max_players,
            "last_seen": time.time(),
        }
        try:
            self._http("PATCH", url, payload)
        except (OSError, urllib.error.URLError) as exc:
            logger.warning("Relay heartbeat failed: %s", exc)

    def deregister(self) -> None:
        """Stop the heartbeat and DELETE this game from Firebase.

        Silent on network errors — the TTL-based expiry will clean up the
        record within ``_GAME_EXPIRY`` seconds even if this call fails.
        """
        self.stop_heartbeat()
        with self._lock:
            game_id = self._game_id
            self._game_id = None
        if not game_id or not config.RELAY_URL:
            return
        url = f"{config.RELAY_URL}/games/{game_id}.json"
        try:
            self._http("DELETE", url)
            logger.info("Deregistered game %s from relay", game_id)
            self._log_event("game_closed", {"game_id": game_id})
        except (OSError, urllib.error.URLError) as exc:
            logger.warning("Relay deregister failed (will expire): %s", exc)

    def stop(self) -> None:
        """Convenience alias for :meth:`deregister`."""
        self.deregister()

    def start_heartbeat(self, state_provider: Callable[[], dict[str, Any]]) -> None:
        """Start a daemon thread that calls :meth:`update` every 30 s.

        ``state_provider`` is called on each tick and must return a dict with
        keys ``host_name``, ``map_name``, ``player_count``, ``max_players``.
        """
        if self._running:
            return
        self._running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(state_provider,),
            daemon=True,
            name="wopc-relay-heartbeat",
        )
        self._heartbeat_thread.start()
        logger.debug("Relay heartbeat thread started")

    def stop_heartbeat(self) -> None:
        """Signal the heartbeat thread to stop and wait up to 3 s for it."""
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=3.0)
            self._heartbeat_thread = None

    def _heartbeat_loop(self, state_provider: Callable[[], dict[str, Any]]) -> None:
        deadline = time.monotonic() + self._heartbeat_interval
        while self._running:
            if time.monotonic() >= deadline:
                state = state_provider()
                self.update(
                    host_name=state.get("host_name", ""),
                    map_name=state.get("map_name", ""),
                    player_count=int(state.get("player_count", 1)),
                    max_players=int(state.get("max_players", 2)),
                    game_name=state.get("game_name", ""),
                )
                deadline = time.monotonic() + self._heartbeat_interval
            time.sleep(min(0.5, self._heartbeat_interval / 4))

    # ------------------------------------------------------------------
    # Joiner / browser side
    # ------------------------------------------------------------------

    def fetch_games(self) -> list[GameBeacon]:
        """Fetch active games from Firebase.

        Filters out stale records (``last_seen`` older than ``_GAME_EXPIRY``
        seconds) and returns the rest as :class:`~launcher.discovery.GameBeacon`
        objects with ``source="internet"``.

        Returns an empty list if the relay URL is not configured, if Firebase
        returns an empty node (JSON ``null``), or on any network/parse error.
        """
        from launcher.discovery import GameBeacon

        if not config.RELAY_URL:
            return []

        url = f"{config.RELAY_URL}/games.json"
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT)
            data = json.loads(resp.read())
        except (OSError, urllib.error.URLError) as exc:
            logger.warning("Relay fetch failed: %s", exc)
            return []
        except json.JSONDecodeError as exc:
            logger.warning("Relay response parse error: %s", exc)
            return []

        # Firebase returns JSON null (Python None) when the node is empty
        if not data:
            return []

        now = time.time()
        games: list[GameBeacon] = []
        for record in data.values():
            try:
                age = now - float(record["last_seen"])
                if age > _GAME_EXPIRY:
                    continue
                games.append(
                    GameBeacon(
                        host_name=str(record["host_name"]),
                        map_name=str(record["map_name"]),
                        player_count=int(record["player_count"]),
                        max_players=int(record["max_players"]),
                        lobby_port=int(record["lobby_port"]),
                        host_ip=str(record["host_ip"]),
                        game_name=str(record.get("game_name", "")),
                        last_seen=time.monotonic(),
                        source="internet",
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Malformed relay record skipped: %s", exc)

        logger.debug("Relay: %d active game(s) fetched", len(games))
        return games

    # ------------------------------------------------------------------
    # Log upload for remote troubleshooting
    # ------------------------------------------------------------------

    @staticmethod
    def read_log_tail(path: Path, max_lines: int = 300) -> str:
        """Read the last *max_lines* from a log file.

        Returns the text (lines joined by ``\\n``), or an empty string
        if the file doesn't exist or can't be read.
        """
        try:
            if path.exists():
                all_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                return "\n".join(all_lines[-max_lines:])
        except Exception:
            pass
        return ""

    @staticmethod
    def extract_engine_errors(engine_log: str, max_lines: int = 50) -> str:
        """Filter engine log text for warning/error/ASSERT lines."""
        if not engine_log:
            return ""
        err_lines = [
            line
            for line in engine_log.splitlines()
            if line.startswith(("warning:", "error:", "ASSERT"))
        ]
        return "\n".join(err_lines[-max_lines:])

    @staticmethod
    def collect_system_info() -> dict[str, Any]:
        """Gather OS, Python, WOPC version, and path info."""
        import platform
        import sys

        from launcher.__version__ import COMMIT_HASH

        return {
            "os": platform.platform(),
            "python": sys.version,
            "wopc_version": config.VERSION,
            "commit_hash": COMMIT_HASH,
            "scfa_path": str(config.SCFA_STEAM),
            "wopc_root": str(config.WOPC_ROOT),
        }

    @staticmethod
    def extract_game_prefs_mods(prefs_path: Path) -> str:
        """Extract the ``active_mods`` snippet from Game.prefs."""
        import re

        try:
            if prefs_path.exists():
                content = prefs_path.read_text(encoding="utf-8", errors="replace")
                match = re.search(r"active_mods\s*=\s*[^\n]+", content)
                if match:
                    return match.group(0)[:200]
        except Exception:
            pass
        return ""

    @staticmethod
    def upload_logs(
        log_lines: list[str],
        host_name: str = "",
        launch_id: str = "",
        exit_code: int | None = None,
        exit_duration: float | None = None,
        exit_reason: str = "",
    ) -> bool:
        """Upload launcher + engine logs to Firebase ``/reports/`` node.

        Collects logs from multiple sources (engine, launcher, SupCom.sclog),
        system info, and Game.prefs state, then uploads as a single report.
        The ``launch_id`` correlates this report with launcher and engine logs.

        Returns True on success, False on any failure.
        """
        if not config.RELAY_URL:
            return False
        report_id = str(uuid.uuid4())
        url = f"{config.RELAY_URL}/reports/{report_id}.json"

        # Collect log sources — each helper is independently testable
        engine_log = RelayClient.read_log_tail(config.WOPC_BIN / config.GAME_LOG, 300)
        if not engine_log:
            # Distinguish "no file" from "empty file"
            engine_log_path = config.WOPC_BIN / config.GAME_LOG
            if not engine_log_path.exists():
                engine_log = "(engine log not found)"

        from launcher.game_prefs_repair import _GAME_PREFS_DIR, GAME_PREFS_PATH

        sclog = RelayClient.read_log_tail(_GAME_PREFS_DIR / "SupCom.sclog", 200)
        engine_errors = RelayClient.extract_engine_errors(engine_log)
        game_prefs_snippet = RelayClient.extract_game_prefs_mods(GAME_PREFS_PATH)
        launcher_file_log = RelayClient.read_log_tail(config.WOPC_ROOT / "launcher.log", 300)

        payload: dict[str, Any] = {
            "timestamp": time.time(),
            "host_name": host_name,
            "version": config.VERSION,
            "launch_id": launch_id,
            "system": RelayClient.collect_system_info(),
            "launcher_log": "\n".join(log_lines[-500:]),
            "launcher_file_log": launcher_file_log,
            "engine_log": engine_log,
            "engine_errors": engine_errors,
            "scfa_log": sclog,
            "game_prefs_active_mods": game_prefs_snippet,
        }
        if exit_code is not None:
            payload["exit_code"] = exit_code
            payload["exit_duration"] = exit_duration
            payload["exit_reason"] = exit_reason
        try:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="PUT",
            )
            urllib.request.urlopen(req, timeout=15)
            logger.info("Log report uploaded as %s", report_id)
            return True
        except (OSError, urllib.error.URLError) as exc:
            logger.warning("Failed to upload log report: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Firebase audit logging
    # ------------------------------------------------------------------

    @staticmethod
    def _log_event(event_type: str, data: dict[str, Any]) -> None:
        """Write an audit log entry to Firebase ``/logs/`` node.

        Fire-and-forget: failures are silently logged but never raised.
        This provides a persistent troubleshooting trail in Firebase.
        """
        if not config.RELAY_URL:
            return
        log_id = str(uuid.uuid4())
        url = f"{config.RELAY_URL}/logs/{log_id}.json"
        payload: dict[str, Any] = {
            "event": event_type,
            "timestamp": time.time(),
            **data,
        }
        try:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="PUT",
            )
            urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT)
            logger.debug("Logged event %s to relay", event_type)
        except (OSError, urllib.error.URLError) as exc:
            logger.debug("Failed to log event %s to relay: %s", event_type, exc)

    # ------------------------------------------------------------------
    # Internal HTTP helper
    # ------------------------------------------------------------------

    @staticmethod
    def _http(method: str, url: str, payload: dict[str, Any] | None = None) -> bytes:
        """Send an HTTP request and return the response body.

        Raises :class:`urllib.error.URLError` or :class:`OSError` on failure.
        """
        data: bytes | None = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT)
        body: bytes = resp.read()
        return body
