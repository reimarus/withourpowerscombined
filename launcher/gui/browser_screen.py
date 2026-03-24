"""Game browser screen — find, create, and join multiplayer games.

Builds the browser UI (game list, create game, direct connect) and manages
the discovery lifecycle (LAN beacons + internet relay polling).  All
functions take ``app`` (the WopcApp instance) as the first parameter so
they can access widgets and state without subclassing.

Extracted from app.py to reduce the monolith.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import customtkinter as ctk  # type: ignore[import-untyped,import-not-found]
else:
    try:
        import customtkinter as ctk  # type: ignore[import-untyped]
    except ImportError:
        ctk = None  # type: ignore[assignment]

from launcher import prefs
from launcher.gui.constants import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_BG,
    COLOR_READY,
    COLOR_SURFACE,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
)

logger = logging.getLogger("wopc.gui")


# ---------------------------------------------------------------------------
# Screen builder
# ---------------------------------------------------------------------------


def build_browser_screen(app: Any) -> None:
    """Build the multiplayer game browser screen."""
    app.browser_screen = ctk.CTkFrame(app, fg_color="transparent")
    # Don't grid it yet — _show_screen handles that

    app.browser_screen.grid_rowconfigure(1, weight=1)
    app.browser_screen.grid_columnconfigure(0, weight=1)

    # Header
    header = ctk.CTkLabel(
        app.browser_screen,
        text="FIND A GAME",
        text_color=COLOR_TEXT_GOLD,
        font=ctk.CTkFont(size=22, weight="bold"),
    )
    header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

    # Game list (scrollable)
    app.game_list_frame = ctk.CTkScrollableFrame(
        app.browser_screen,
        fg_color=COLOR_SURFACE,
        corner_radius=4,
    )
    app.game_list_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
    app.game_list_frame.grid_columnconfigure(0, weight=1)

    # Empty state label
    app.no_games_label = ctk.CTkLabel(
        app.game_list_frame,
        text="Searching for games on your network and the internet...",
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=14),
    )
    app.no_games_label.grid(row=0, column=0, padx=20, pady=40)

    app.game_rows = []  # list[dict[str, Any]]

    # Bottom bar
    bottom = ctk.CTkFrame(app.browser_screen, fg_color="transparent")
    bottom.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
    bottom.grid_columnconfigure(2, weight=1)

    # Game name entry (host names their game before creating)
    app.game_name_entry = ctk.CTkEntry(
        bottom,
        placeholder_text="Game name (e.g. Friday Night Match)",
        width=250,
        height=44,
    )
    app.game_name_entry.grid(row=0, column=0, sticky="w", padx=(0, 8))

    app.create_game_btn = ctk.CTkButton(
        bottom,
        text="\u25b6  CREATE GAME",
        font=ctk.CTkFont(size=16, weight="bold"),
        height=44,
        fg_color=COLOR_READY,
        hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        corner_radius=4,
        command=app._on_create_game,
    )
    app.create_game_btn.grid(row=0, column=1, sticky="w")

    # Refresh button
    app.refresh_browser_btn = ctk.CTkButton(
        bottom,
        text="\u27f3  Refresh",
        fg_color=COLOR_SURFACE,
        hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_TEXT_PRIMARY,
        width=100,
        height=36,
        corner_radius=4,
        command=lambda: on_refresh_browser(app),
    )
    app.refresh_browser_btn.grid(row=0, column=3, padx=(0, 8), sticky="e")

    # Direct Connect (collapsed)
    app.direct_connect_toggle = ctk.CTkButton(
        bottom,
        text="\u25b8 Direct Connect",
        fg_color="transparent",
        hover_color=COLOR_SURFACE,
        text_color=COLOR_TEXT_MUTED,
        anchor="e",
        width=140,
        command=lambda: toggle_direct_connect(app),
    )
    app.direct_connect_toggle.grid(row=0, column=4, sticky="e")

    app.direct_connect_frame = ctk.CTkFrame(
        app.browser_screen, fg_color=COLOR_SURFACE, corner_radius=4
    )
    # Not gridded initially (collapsed)
    app.direct_connect_frame.grid_columnconfigure(1, weight=1)

    dc_addr_label = ctk.CTkLabel(
        app.direct_connect_frame, text="Host Address:", text_color=COLOR_TEXT_MUTED
    )
    dc_addr_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")

    app.dc_address_entry = ctk.CTkEntry(
        app.direct_connect_frame, placeholder_text="192.168.1.50:15000"
    )
    saved_addr = prefs.get_join_address()
    if saved_addr:
        app.dc_address_entry.insert(0, saved_addr)
    app.dc_address_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

    app.dc_connect_btn = ctk.CTkButton(
        app.direct_connect_frame,
        text="Connect",
        width=80,
        fg_color=COLOR_ACCENT,
        hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        corner_radius=3,
        command=app._on_direct_connect,
    )
    app.dc_connect_btn.grid(row=0, column=2, padx=(5, 10), pady=10)

    app._direct_connect_visible = False


# ---------------------------------------------------------------------------
# Browser UI interactions
# ---------------------------------------------------------------------------


def toggle_direct_connect(app: Any) -> None:
    """Show/hide the direct connect panel on the browser screen."""
    if app._direct_connect_visible:
        app.direct_connect_frame.grid_remove()
        app.direct_connect_toggle.configure(text="\u25b8 Direct Connect")
    else:
        app.direct_connect_frame.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
        app.direct_connect_toggle.configure(text="\u25be Direct Connect")
    app._direct_connect_visible = not app._direct_connect_visible


def refresh_game_browser(app: Any, games: list[Any]) -> None:
    """Update the game browser with discovered games (GUI thread)."""
    # Clear old rows
    for row in app.game_rows:
        for w in row.get("widgets", []):
            w.destroy()
    app.game_rows.clear()

    if not games:
        app.no_games_label.grid(row=0, column=0, padx=20, pady=40)
        return
    app.no_games_label.grid_remove()

    for i, game in enumerate(games):
        row_frame = ctk.CTkFrame(app.game_list_frame, fg_color=COLOR_BG, corner_radius=6)
        row_frame.grid(row=i, column=0, padx=5, pady=3, sticky="ew")
        row_frame.grid_columnconfigure(1, weight=1)

        # Title: game name if set, otherwise host name
        title = getattr(game, "game_name", "") or game.host_name
        name_lbl = ctk.CTkLabel(
            row_frame,
            text=title,
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        name_lbl.grid(row=0, column=0, padx=(10, 5), pady=(8, 0), sticky="w")

        # Subtitle: "host — map"
        subtitle = f"{game.host_name}  \u2014  {game.map_name}"
        map_lbl = ctk.CTkLabel(
            row_frame,
            text=subtitle,
            text_color=COLOR_TEXT_MUTED,
        )
        map_lbl.grid(row=1, column=0, padx=(10, 5), pady=(0, 8), sticky="w")

        count_lbl = ctk.CTkLabel(
            row_frame,
            text=f"{game.player_count}/{game.max_players}",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        count_lbl.grid(row=0, column=1, rowspan=2, padx=5, sticky="e")

        # Internet badge — shown only for relay-discovered games
        row_widgets = [row_frame, name_lbl, map_lbl, count_lbl]
        if getattr(game, "source", "lan") == "internet":
            badge = ctk.CTkLabel(
                row_frame,
                text="\U0001f310",
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(size=11),
                width=20,
            )
            badge.grid(row=1, column=1, padx=(0, 5), pady=(0, 8), sticky="e")
            row_widgets.append(badge)

        join_btn = ctk.CTkButton(
            row_frame,
            text="Join",
            width=60,
            height=28,
            fg_color=COLOR_ACCENT,
            command=lambda g=game: app._join_discovered_game(g),
        )
        join_btn.grid(row=0, column=2, rowspan=2, padx=(5, 10), pady=8)
        row_widgets.append(join_btn)

        app.game_rows.append({"widgets": row_widgets})


def on_refresh_browser(app: Any) -> None:
    """Handle manual refresh button click — force immediate relay + LAN poll."""
    app.refresh_browser_btn.configure(text="Refreshing...", state="disabled")
    # Clear cached games to force a full refresh
    app._internet_games = []
    app._lan_games = []
    refresh_game_browser(app, [])

    def _fetch() -> None:
        from launcher import config
        from launcher.relay import RelayClient

        games: list[Any] = []
        if config.RELAY_URL:
            games = RelayClient().fetch_games()
        app.after(0, _on_manual_refresh_done, app, games)

    threading.Thread(target=_fetch, daemon=True).start()


def _on_manual_refresh_done(app: Any, internet_games: list[Any]) -> None:
    """Callback after manual refresh fetch completes."""
    app._internet_games = internet_games
    merge_and_refresh(app)
    app.refresh_browser_btn.configure(text="\u27f3  Refresh", state="normal")


def merge_and_refresh(app: Any) -> None:
    """Merge LAN + internet game lists and refresh the browser (GUI thread).

    LAN games take priority: if the same host:port appears in both lists,
    the LAN entry is shown (and the internet duplicate dropped).
    """
    seen: set[str] = set()
    merged: list[Any] = []
    for g in app._lan_games:
        key = f"{g.host_ip}:{g.lobby_port}"
        seen.add(key)
        merged.append(g)
    for g in app._internet_games:
        if f"{g.host_ip}:{g.lobby_port}" not in seen:
            merged.append(g)
    refresh_game_browser(app, merged)


# ---------------------------------------------------------------------------
# Beacon (LAN discovery) lifecycle
# ---------------------------------------------------------------------------


def start_beacon_broadcaster(app: Any) -> None:
    """Start broadcasting game presence on the LAN."""
    from launcher.discovery import BeaconBroadcaster

    if app._beacon_broadcaster and app._beacon_broadcaster.is_running:
        return
    port_str = prefs.get_host_port() or "15000"
    app._beacon_broadcaster = BeaconBroadcaster(
        lobby_port=int(port_str),
        state_provider=lambda: beacon_state(app),
    )
    app._beacon_broadcaster.start()


def stop_beacon_broadcaster(app: Any) -> None:
    """Stop broadcasting game presence."""
    if app._beacon_broadcaster:
        app._beacon_broadcaster.stop()
        app._beacon_broadcaster = None


def start_beacon_listener(app: Any) -> None:
    """Start listening for LAN game beacons."""
    from launcher.discovery import BeaconListener

    if app._beacon_listener and app._beacon_listener.is_running:
        return
    app._beacon_listener = BeaconListener(
        on_update=lambda games: on_games_discovered(app, games),
    )
    app._beacon_listener.start()


def stop_beacon_listener(app: Any) -> None:
    """Stop listening for LAN game beacons."""
    if app._beacon_listener:
        app._beacon_listener.stop()
        app._beacon_listener = None


def beacon_state(app: Any) -> dict[str, Any]:
    """Return fresh game info for the beacon broadcaster."""
    game_name = ""
    if hasattr(app, "game_name_entry"):
        game_name = app.game_name_entry.get().strip()
    return {
        "host_name": app.name_entry.get() or "Player",
        "game_name": game_name,
        "map_name": prefs.get_active_map() or "No map",
        "player_count": 1 + len(app._remote_players),
        "max_players": int(app.expected_var.get()),
    }


def on_games_discovered(app: Any, games: list[Any]) -> None:
    """Callback from BeaconListener (background thread)."""
    app._lan_games = games
    app.after(0, merge_and_refresh, app)


# ---------------------------------------------------------------------------
# Internet relay lifecycle
# ---------------------------------------------------------------------------


def start_relay_polling(app: Any) -> None:
    """Start the 5-second internet relay poll loop."""
    if app._relay_poll_active:
        return
    app._relay_poll_active = True
    poll_relay_once(app)


def stop_relay_polling(app: Any) -> None:
    """Stop the internet relay poll loop and clear cached results."""
    app._relay_poll_active = False
    app._internet_games = []


def poll_relay_once(app: Any) -> None:
    """Fetch internet games once, then reschedule the next poll (GUI thread)."""
    if not app._relay_poll_active:
        return

    def _fetch() -> None:
        from launcher import config
        from launcher.relay import RelayClient

        if not config.RELAY_URL:
            return
        games = RelayClient().fetch_games()
        app.after(0, _on_internet_games_fetched, app, games)

    threading.Thread(target=_fetch, daemon=True).start()
    app.after(5000, poll_relay_once, app)


def _on_internet_games_fetched(app: Any, games: list[Any]) -> None:
    """GUI thread callback: relay fetch completed."""
    app._internet_games = games
    merge_and_refresh(app)


def start_relay_registration(app: Any, *, upnp_ok: bool = False) -> None:
    """Register this hosted game on the internet relay (background thread)."""
    from launcher import config

    if not config.RELAY_URL:
        return

    def _register() -> None:
        from launcher.relay import RelayClient, get_public_ip

        public_ip = get_public_ip()
        if not public_ip:
            logger.warning("Relay registration skipped: could not resolve public IP")
            msg = "Internet relay: could not detect public IP \u2014 visible on LAN only."
            app.after(0, lambda m=msg: app.log(m))
            return
        port = int(prefs.get_host_port() or "15000")
        state = beacon_state(app)
        client = RelayClient()
        ok = client.register(
            host_name=state["host_name"],
            map_name=state["map_name"],
            player_count=int(state["player_count"]),
            max_players=int(state["max_players"]),
            lobby_port=port,
            public_ip=public_ip,
            game_name=state.get("game_name", ""),
            upnp_ok=upnp_ok,
        )
        if ok:
            client.start_heartbeat(lambda: beacon_state(app))
            app._relay_client = client
            app.after(0, lambda: app.log("Registered on internet relay."))
        else:
            app.after(
                0,
                lambda: app.log("Internet relay unavailable \u2014 visible on LAN only."),
            )

    threading.Thread(target=_register, daemon=True).start()


def stop_relay_registration(app: Any) -> None:
    """Deregister from the internet relay and stop heartbeat."""
    client = app._relay_client
    if not client:
        return
    app._relay_client = None
    threading.Thread(target=client.deregister, daemon=True).start()
