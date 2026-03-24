"""Multiplayer lobby screen — player list, game options, chat, and launch.

Builds the lobby room UI and manages the full multiplayer lifecycle:
TCP callbacks, game state broadcasting, file transfer, and launch flow.
All functions take ``app`` (the WopcApp instance) as the first parameter.

Extracted from app.py to reduce the monolith.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import customtkinter as ctk  # type: ignore[import-untyped,import-not-found]
else:
    try:
        import customtkinter as ctk  # type: ignore[import-untyped]
    except ImportError:
        ctk = None  # type: ignore[assignment]

from launcher import config, file_transfer, map_scanner, mods, prefs
from launcher.gui import browser_screen
from launcher.gui.constants import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_BG,
    COLOR_DANGER,
    COLOR_LAUNCH,
    COLOR_MOD_PANEL,
    COLOR_PANEL,
    COLOR_SURFACE,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
)
from launcher.gui.supcom_frame import SupComFrame
from launcher.lobby import LobbyCallbacks, LobbyClient, LobbyServer
from launcher.wopc import cmd_launch

logger = logging.getLogger("wopc.gui")


# ---------------------------------------------------------------------------
# Screen builder
# ---------------------------------------------------------------------------


def build_lobby_screen(app: Any) -> None:
    """Build the multiplayer lobby room screen."""
    app.lobby_screen = ctk.CTkFrame(app, fg_color="transparent")
    # Don't grid — _show_screen handles it

    app.lobby_screen.grid_rowconfigure(0, weight=2)
    app.lobby_screen.grid_rowconfigure(1, weight=1)
    app.lobby_screen.grid_columnconfigure(0, weight=1)
    app.lobby_screen.grid_columnconfigure(1, weight=1)

    # --- Map Section (top-left) ---
    _map_sf = SupComFrame(app.lobby_screen, fg_color=COLOR_SURFACE)
    _map_sf.frame.grid(row=0, column=0, padx=(20, 5), pady=(20, 5), sticky="nsew")
    map_frame = _map_sf.interior
    map_frame.grid_rowconfigure(3, weight=1)
    map_frame.grid_columnconfigure(0, weight=1)

    map_header = ctk.CTkLabel(
        map_frame,
        text="MAP",
        text_color=COLOR_TEXT_GOLD,
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    map_header.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

    # Lobby map preview image
    _lps = app._LOBBY_PREVIEW_SIZE
    app.lobby_map_preview_label = ctk.CTkLabel(
        map_frame,
        text="No Preview",
        width=_lps,
        height=_lps,
        fg_color=COLOR_PANEL,
        corner_radius=4,
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=11),
    )
    app.lobby_map_preview_label.grid(row=1, column=0, padx=10, pady=(6, 4), sticky="n")

    app.lobby_map_label = ctk.CTkLabel(
        map_frame,
        text="No map selected",
        text_color=COLOR_TEXT_PRIMARY,
        font=ctk.CTkFont(size=16, weight="bold"),
    )
    app.lobby_map_label.grid(row=2, column=0, padx=10, pady=(5, 0), sticky="w")

    # Map info (type, size, players)
    app.lobby_map_info = ctk.CTkLabel(
        map_frame,
        text="",
        text_color=COLOR_TEXT_MUTED,
    )
    app.lobby_map_info.grid(row=3, column=0, padx=10, pady=5, sticky="nw")

    app.lobby_change_map_btn = ctk.CTkButton(
        map_frame,
        text="Change Map",
        width=100,
        height=28,
        fg_color=COLOR_ACCENT,
        hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        corner_radius=3,
        command=lambda: on_lobby_change_map(app),
    )
    app.lobby_change_map_btn.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="w")

    # --- Players Section (top-right) ---
    _players_sf = SupComFrame(app.lobby_screen, fg_color=COLOR_SURFACE)
    _players_sf.frame.grid(row=0, column=1, padx=(5, 20), pady=(20, 5), sticky="nsew")
    players_frame = _players_sf.interior
    players_frame.grid_rowconfigure(1, weight=1)
    players_frame.grid_columnconfigure(0, weight=1)

    players_header_frame = ctk.CTkFrame(players_frame, fg_color="transparent")
    players_header_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
    players_header_frame.grid_columnconfigure(0, weight=1)

    players_label = ctk.CTkLabel(
        players_header_frame,
        text="PLAYERS",
        text_color=COLOR_TEXT_GOLD,
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    players_label.grid(row=0, column=0, sticky="w")

    app.lobby_add_ai_btn = ctk.CTkButton(
        players_header_frame,
        text="+ Add AI",
        width=70,
        height=24,
        fg_color=COLOR_ACCENT,
        hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        font=ctk.CTkFont(size=11),
        corner_radius=3,
        command=app._add_lobby_ai_slot,
    )
    app.lobby_add_ai_btn.grid(row=0, column=1, sticky="e")

    app.lobby_slots_scroll = ctk.CTkScrollableFrame(
        players_frame,
        fg_color="transparent",
    )
    app.lobby_slots_scroll.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
    app.lobby_slots_scroll.grid_columnconfigure(1, weight=1)
    app.lobby_player_slots = []  # list[dict[str, Any]]

    # --- Options Section (bottom-left) ---
    _opts_sf = SupComFrame(app.lobby_screen, fg_color=COLOR_SURFACE)
    _opts_sf.frame.grid(row=1, column=0, padx=(20, 5), pady=(5, 5), sticky="nsew")
    opts_frame = _opts_sf.interior
    opts_frame.grid_columnconfigure(1, weight=1)

    opts_header = ctk.CTkLabel(
        opts_frame,
        text="GAME OPTIONS",
        text_color=COLOR_TEXT_GOLD,
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    opts_header.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")

    app.lobby_option_vars = {}  # dict[str, Any]
    app.lobby_option_widgets = []  # list[Any]

    # Reuse the same option definitions as the solo screen for consistency
    for i, (key, label, values, default) in enumerate(app.GAME_OPTION_DEFS):
        lbl = ctk.CTkLabel(
            opts_frame,
            text=f"{label}:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        lbl.grid(row=i + 1, column=0, padx=(10, 5), pady=2, sticky="w")
        var = ctk.StringVar(value=default)
        menu = ctk.CTkOptionMenu(
            opts_frame,
            values=values,
            variable=var,
            width=130,
            height=24,
            command=lambda _val, _key=key: on_lobby_option_change(app, _key),
        )
        menu.grid(row=i + 1, column=1, padx=(5, 10), pady=2, sticky="w")
        app.lobby_option_vars[key] = var
        app.lobby_option_widgets.extend([lbl, menu])

    # Victory description label (below all option rows)
    victory_row = len(app.GAME_OPTION_DEFS) + 1
    app.lobby_victory_desc = ctk.CTkLabel(
        opts_frame,
        text=app.VICTORY_DESCRIPTIONS.get("Demoralization", ""),
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=11, slant="italic"),
        wraplength=250,
    )
    app.lobby_victory_desc.grid(
        row=victory_row, column=0, columnspan=2, padx=10, pady=(2, 5), sticky="w"
    )

    def _update_lobby_victory_desc(*_a: Any) -> None:
        desc = app.VICTORY_DESCRIPTIONS.get(app.lobby_option_vars["Victory"].get(), "")
        app.lobby_victory_desc.configure(text=desc)

    app.lobby_option_vars["Victory"].trace_add("write", _update_lobby_victory_desc)

    # --- Chat Section (bottom-right) ---
    _chat_sf = SupComFrame(app.lobby_screen, fg_color=COLOR_SURFACE)
    _chat_sf.frame.grid(row=1, column=1, padx=(5, 20), pady=(5, 5), sticky="nsew")
    chat_frame = _chat_sf.interior
    chat_frame.grid_rowconfigure(1, weight=1)
    chat_frame.grid_columnconfigure(0, weight=1)

    chat_header = ctk.CTkLabel(
        chat_frame,
        text="CHAT",
        text_color=COLOR_TEXT_GOLD,
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    chat_header.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="nw")

    app.lobby_chat_textbox = ctk.CTkTextbox(
        chat_frame,
        height=100,
        fg_color=COLOR_BG,
        text_color=COLOR_TEXT_MUTED,
        state="disabled",
    )
    app.lobby_chat_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

    chat_input_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
    chat_input_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
    chat_input_frame.grid_columnconfigure(0, weight=1)

    app.lobby_chat_entry = ctk.CTkEntry(
        chat_input_frame,
        placeholder_text="Type a message...",
    )
    app.lobby_chat_entry.grid(row=0, column=0, padx=(0, 5), sticky="ew")
    app.lobby_chat_entry.bind("<Return>", lambda e: send_lobby_chat(app))

    lobby_chat_send = ctk.CTkButton(
        chat_input_frame,
        text="Send",
        width=60,
        command=lambda: send_lobby_chat(app),
    )
    lobby_chat_send.grid(row=0, column=1)

    # --- Action Bar (bottom, spanning both columns) ---
    action_bar = ctk.CTkFrame(app.lobby_screen, fg_color="transparent")
    action_bar.grid(row=2, column=0, columnspan=2, padx=20, pady=(5, 20), sticky="ew")
    action_bar.grid_columnconfigure(1, weight=1)

    app.lobby_leave_btn = ctk.CTkButton(
        action_bar,
        text="LEAVE",
        width=100,
        height=44,
        fg_color=COLOR_DANGER,
        hover_color="#BF3040",
        text_color=COLOR_TEXT_PRIMARY,
        font=ctk.CTkFont(size=14, weight="bold"),
        corner_radius=4,
        border_width=1,
        border_color="#FF6B75",
        command=lambda: on_leave_lobby(app),
    )
    app.lobby_leave_btn.grid(row=0, column=0, sticky="w")

    app.lobby_launch_btn = ctk.CTkButton(
        action_bar,
        text="\u25b6  LAUNCH GAME",
        width=180,
        height=44,
        fg_color=COLOR_LAUNCH,
        hover_color="#35A8D8",
        text_color=COLOR_BG,
        font=ctk.CTkFont(size=16, weight="bold"),
        corner_radius=4,
        border_width=1,
        border_color="#6CD4FF",
        command=lambda: on_lobby_launch_click(app),
    )
    app.lobby_launch_btn.grid(row=0, column=2, sticky="e")


# ---------------------------------------------------------------------------
# Lobby state configuration
# ---------------------------------------------------------------------------


def update_lobby_for_host(app: Any) -> None:
    """Configure lobby screen widgets for hosting."""
    app.lobby_change_map_btn.grid()
    app.lobby_add_ai_btn.grid()
    app.lobby_launch_btn.configure(
        text="\u25b6  LAUNCH GAME", fg_color=COLOR_LAUNCH, state="normal"
    )
    # Enable option dropdowns
    for w in app.lobby_option_widgets:
        if hasattr(w, "configure") and isinstance(w, ctk.CTkOptionMenu):
            w.configure(state="normal")
    # Update map label
    active_map = prefs.get_active_map()
    app.lobby_map_label.configure(text=active_map or "No map selected")
    # Initialize lobby player slots with host row + one default AI
    app._clear_lobby_player_slots()
    name = app.name_entry.get() if hasattr(app, "name_entry") else "Player"
    host_lbl = ctk.CTkLabel(
        app.lobby_slots_scroll,
        text=f"Host: {name or 'Player'}",
        text_color=COLOR_ACCENT,
        font=ctk.CTkFont(size=12, weight="bold"),
        anchor="w",
    )
    host_lbl.grid(row=0, column=0, columnspan=6, padx=(0, 5), pady=2, sticky="w")
    app.lobby_player_slots.append({"type": "host", "widgets": [host_lbl]})
    app._add_lobby_ai_slot()


def update_lobby_for_joiner(app: Any) -> None:
    """Configure lobby screen widgets for joining."""
    app.lobby_change_map_btn.grid_remove()
    app.lobby_add_ai_btn.grid_remove()
    app.lobby_launch_btn.configure(text="READY", fg_color=COLOR_ACCENT, state="disabled")
    # Disable option dropdowns (host controls)
    for w in app.lobby_option_widgets:
        if hasattr(w, "configure") and isinstance(w, ctk.CTkOptionMenu):
            w.configure(state="disabled")


# ---------------------------------------------------------------------------
# Lobby chat
# ---------------------------------------------------------------------------


def send_lobby_chat(app: Any) -> None:
    """Send a chat message from the lobby screen."""
    text = app.lobby_chat_entry.get().strip()
    if not text:
        return
    app.lobby_chat_entry.delete(0, "end")
    name = app.name_entry.get() or "Player"
    if app._is_hosting and app._lobby_server:
        app._lobby_server.broadcast_chat(name, text)
        append_lobby_chat(app, name, text)
    elif app._lobby_client and app._lobby_client.is_connected:
        app._lobby_client.send_chat(text)
    else:
        append_lobby_chat(app, name, text)


def append_lobby_chat(app: Any, sender: str, text: str) -> None:
    """Append a message to the lobby chat textbox."""
    app.lobby_chat_textbox.configure(state="normal")
    app.lobby_chat_textbox.insert("end", f"[{sender}] {text}\n")
    app.lobby_chat_textbox.configure(state="disabled")
    app.lobby_chat_textbox.see("end")


# ---------------------------------------------------------------------------
# Lobby map picker
# ---------------------------------------------------------------------------


def on_lobby_change_map(app: Any) -> None:
    """Open map picker dialog for the host in lobby mode."""
    if not getattr(app, "_all_maps", None):
        app._all_maps = map_scanner.scan_all_maps()

    dialog = ctk.CTkToplevel(app)
    dialog.title("Select Map")
    dialog.geometry("400x500")
    dialog.transient(app)
    dialog.grab_set()
    dialog.configure(fg_color=COLOR_BG)

    # Search bar
    search_var = ctk.StringVar()
    search_entry = ctk.CTkEntry(
        dialog,
        placeholder_text="Search maps...",
        textvariable=search_var,
        height=32,
        fg_color=COLOR_MOD_PANEL,
    )
    search_entry.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
    dialog.grid_columnconfigure(0, weight=1)
    dialog.grid_rowconfigure(1, weight=1)

    # Scrollable map list
    scroll = ctk.CTkScrollableFrame(dialog, fg_color=COLOR_PANEL)
    scroll.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
    scroll.grid_columnconfigure(0, weight=1)

    map_buttons: list[Any] = []
    active_map = prefs.get_active_map()

    def populate(filter_text: str = "") -> None:
        for btn in map_buttons:
            btn.destroy()
        map_buttons.clear()

        for idx, info in enumerate(app._all_maps):
            name_match = filter_text in info.display_name.lower()
            folder_match = filter_text in info.folder_name.lower()
            if filter_text and not name_match and not folder_match:
                continue

            parts = [info.display_name]
            if info.max_players:
                parts.append(f"{info.max_players}p")
            if info.size_label != "?":
                parts.append(info.size_label)
            label = f"{parts[0]} \u2014 {', '.join(parts[1:])}" if len(parts) > 1 else parts[0]

            is_active = info.folder_name == active_map

            def on_pick(name: str = info.folder_name, disp: str = info.display_name) -> None:
                prefs.set_active_map(name)
                app.lobby_map_label.configure(text=disp)
                broadcast_game_state(app)
                dialog.destroy()

            btn = ctk.CTkButton(
                scroll,
                text=label,
                anchor="w",
                height=30,
                fg_color=COLOR_ACCENT if is_active else "transparent",
                text_color=COLOR_BG if is_active else COLOR_TEXT_PRIMARY,
                hover_color=COLOR_ACCENT_HOVER,
                command=on_pick,
            )
            btn.grid(row=idx, column=0, pady=1, sticky="ew")
            map_buttons.append(btn)

    populate()
    search_var.trace_add("write", lambda *_a: populate(search_var.get().lower()))


def on_lobby_option_change(app: Any, key: str) -> None:
    """Handle game option change in the lobby screen."""
    if app._is_hosting and app._lobby_server:
        broadcast_game_state(app)


# ---------------------------------------------------------------------------
# Multiplayer flow — create / join / leave
# ---------------------------------------------------------------------------


def on_create_game(app: Any) -> None:
    """Handle CREATE GAME click on browser screen."""
    from launcher import upnp

    app._is_hosting = True
    refresh_cached_game_state(app)
    port = int(prefs.get_host_port() or "15000")

    # Attempt UPnP port mapping before starting the server
    app._upnp_mapped = upnp.try_open_port(port)
    if app._upnp_mapped:
        app.log(f"UPnP: port {port} opened on router")
    else:
        app.log(f"UPnP unavailable — remote players may need you to forward TCP port {port}")

    callbacks = make_lobby_callbacks(app, is_host=True)
    app._lobby_server = LobbyServer(
        port, callbacks, game_state_provider=lambda: get_cached_game_state(app)
    )
    try:
        app._lobby_server.start()
        app.log(f"Lobby server started on port {port}")
    except OSError as exc:
        app.log(f"Failed to start lobby server: {exc}")
        app._lobby_server = None
        upnp.close_port(port)
        app._upnp_mapped = False
        return
    browser_screen.start_beacon_broadcaster(app)
    browser_screen.stop_beacon_listener(app)
    browser_screen.stop_relay_polling(app)
    browser_screen.start_relay_registration(app, upnp_ok=app._upnp_mapped)
    app._show_screen("lobby")
    update_lobby_for_host(app)


def on_direct_connect(app: Any) -> None:
    """Handle Direct Connect button click."""
    raw_addr = app.dc_address_entry.get().strip()
    if not raw_addr:
        app.log("ERROR: Enter a host address.")
        return
    # Parse host:port
    if ":" in raw_addr:
        host, port_str = raw_addr.rsplit(":", 1)
        port = int(port_str)
    else:
        host = raw_addr
        port = 15000
    prefs.set_join_address(raw_addr)
    join_game(app, host, port)


def join_game(app: Any, host: str, port: int) -> None:
    """Connect to a host's lobby and switch to lobby screen."""
    app._is_hosting = False
    name = app.name_entry.get() or "Player"
    faction = app.faction_var.get().lower()
    callbacks = make_lobby_callbacks(app)
    app._lobby_client = LobbyClient(host, port, name, faction, callbacks)
    app._lobby_client.connect()
    browser_screen.stop_beacon_listener(app)
    browser_screen.stop_relay_polling(app)
    app._show_screen("lobby")
    update_lobby_for_joiner(app)
    app.lobby_launch_btn.configure(text="CONNECTING...", state="disabled")
    app.log(f"Connecting to {host}:{port}...")


def join_discovered_game(app: Any, game: Any) -> None:
    """Join a game discovered via LAN beacon."""
    join_game(app, game.host_ip, game.lobby_port)


def on_leave_lobby(app: Any) -> None:
    """Leave the current multiplayer lobby."""
    if app._is_hosting:
        browser_screen.stop_beacon_broadcaster(app)
        browser_screen.stop_relay_registration(app)
        if app._lobby_server:
            app._lobby_server.stop()
            app._lobby_server = None
        # Clean up UPnP port mapping
        if getattr(app, "_upnp_mapped", False):
            from launcher import upnp

            port = int(prefs.get_host_port() or "15000")
            upnp.close_port(port)
            app._upnp_mapped = False
    else:
        if app._lobby_client:
            app._lobby_client.disconnect()
            app._lobby_client = None
    clear_remote_players(app)
    app._clear_lobby_player_slots()
    app._show_screen("browser")
    browser_screen.start_beacon_listener(app)
    browser_screen.start_relay_polling(app)
    app.log("Left the lobby.")


def on_lobby_launch_click(app: Any) -> None:
    """Handle the LAUNCH/READY button in the lobby screen."""
    if app._is_hosting:
        # Host launches
        errors = validate_before_launch(app)
        if errors:
            for err in errors:
                app.log(f"Cannot launch: {err}")
            return
        n_remote = len(app._remote_players)
        prefs.set_expected_humans(1 + n_remote)
        host_port = prefs.get_host_port()
        if app._lobby_server:
            app._lobby_server.broadcast_launch(host_port)
        app.log(f"Broadcasting launch to {n_remote} peer(s)...")
        app.lobby_launch_btn.configure(text="LAUNCHING...", state="disabled")
        threading.Thread(target=app._launch_game_and_cleanup, daemon=True).start()
    else:
        # Joiner toggles ready
        btn_text = app.lobby_launch_btn.cget("text")
        if btn_text == "READY" and app._lobby_client:
            app._lobby_client.send_ready(True)
            app.lobby_launch_btn.configure(
                text="UNREADY", fg_color=COLOR_DANGER, hover_color="#BF3040"
            )
        elif btn_text == "UNREADY" and app._lobby_client:
            app._lobby_client.send_ready(False)
            app.lobby_launch_btn.configure(
                text="READY", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER
            )


# ---------------------------------------------------------------------------
# TCP lobby callbacks
# ---------------------------------------------------------------------------


def make_lobby_callbacks(app: Any, *, is_host: bool = False) -> LobbyCallbacks:
    """Create callbacks that marshal onto the GUI thread via app.after()."""
    cbs = LobbyCallbacks(
        on_player_joined=lambda pid, name, faction, slot: app.after(
            0, on_player_joined, app, pid, name, faction, slot
        ),
        on_player_left=lambda pid: app.after(0, on_player_left, app, pid),
        on_ready_changed=lambda pid, ready: app.after(0, on_ready_changed, app, pid, ready),
        on_launch=lambda host_port: app.after(0, on_lobby_launch, app, host_port),
        on_connected=lambda: app.after(0, on_lobby_connected, app),
        on_disconnected=lambda reason: app.after(0, on_lobby_disconnected, app, reason),
        on_error=lambda err: app.after(0, on_lobby_error, app, err),
        on_chat_received=lambda sender, text: app.after(0, on_chat_received, app, sender, text),
        on_kicked=lambda reason: app.after(0, on_kicked, app, reason),
    )
    if is_host:
        cbs.on_file_request = lambda pid, cat, name: app.after(
            0, on_file_request, app, pid, cat, name
        )
    else:
        cbs.on_state_updated = lambda state: app.after(0, on_game_state_received, app, state)
        cbs.on_file_manifest = lambda cat, name, files: app.after(
            0, on_file_manifest, app, cat, name, files
        )
        cbs.on_file_chunk = lambda cat, path, idx, total, data: app.after(
            0, on_file_chunk, app, cat, path, idx, total, data
        )
        cbs.on_file_complete = lambda cat, name: app.after(0, on_file_complete, app, cat, name)
    return cbs


def on_player_joined(app: Any, player_id: int, name: str, faction: str, slot: int) -> None:
    """TCP callback: add or update remote human in player slots panel."""
    if player_id in app._remote_players:
        # Update existing player (e.g. faction change)
        info = app._remote_players[player_id]
        info["name"] = name
        info["faction"] = faction
        info["slot"] = slot
        if "name_lbl" in info:
            info["name_lbl"].configure(text=name)
        if "faction_lbl" in info:
            info["faction_lbl"].configure(text=faction.capitalize())
        return
    app._add_remote_human_slot(player_id, name, faction, slot)
    update_host_button_text(app)
    refresh_cached_game_state(app)
    app.log(f"Player joined: {name} (slot {slot})")


def on_player_left(app: Any, player_id: int) -> None:
    """TCP callback: remove remote human from player slots panel."""
    info = app._remote_players.pop(player_id, None)
    if info:
        for w in info.get("widgets", []):
            w.destroy()
        update_host_button_text(app)
        refresh_cached_game_state(app)
        app.log(f"Player left: {info.get('name', '?')}")


def on_ready_changed(app: Any, player_id: int, ready: bool) -> None:
    """TCP callback: update ready indicator for remote player."""
    from launcher.gui.constants import COLOR_READY

    info = app._remote_players.get(player_id)
    if info and "ready_lbl" in info:
        info["ready"] = ready
        info["ready_lbl"].configure(
            text="\u2713" if ready else "\u2014",
            text_color=COLOR_READY if ready else COLOR_TEXT_MUTED,
        )


def on_lobby_launch(app: Any, host_port: str) -> None:
    """TCP callback (joiner): host says launch — start SCFA in join mode."""
    app.log(f"Host launched! Starting game (host port: {host_port})...")
    # Build join address from the lobby client's host + the game port
    if app._lobby_client:
        join_addr = f"{app._lobby_client.host_address}:{host_port}"
        prefs.set_join_address(join_addr)
        app._lobby_client.disconnect()
        app._lobby_client = None
    # Launch with a small delay to let the host bind the game port first
    if app._current_screen == "lobby":
        app.lobby_launch_btn.configure(text="LAUNCHING...", state="disabled")
    else:
        app.primary_btn.configure(text="LAUNCHING...", state="disabled")

    def _delayed_launch() -> None:
        time.sleep(2)
        # Prefer the game state received from the host over local widgets
        rs = app._received_game_state
        if rs:
            logger.info("Joiner launching with host config (map=%s)", rs.get("map_folder"))
            ai_opponents = rs.get("ai_slots") or []
            game_options = rs.get("game_options")
            # Set expected_humans: host + all human players in the state
            n_humans = 1 + len(rs.get("players", []))
            prefs.set_expected_humans(n_humans)
        else:
            logger.warning("Joiner launching WITHOUT host config — using local defaults")
            ai_opponents = app.get_ai_opponents() if hasattr(app, "player_slots") else None
            game_options = app.get_game_options() if hasattr(app, "game_option_vars") else None
        color = app.get_human_color_index()
        start_spot = app.get_human_start_spot() if hasattr(app, "player_slots") else 1
        team = app.get_human_team() if hasattr(app, "player_slots") else 1
        ret = cmd_launch(
            ai_opponents=ai_opponents,
            game_options=game_options,
            player_color=color,
            player_start_spot=start_spot,
            player_team=team,
            launch_mode="join",
        )
        if ret == 0:
            app.log("Game process started successfully.")
        else:
            app.log("Game failed to launch.")
        app.after(0, lambda: app.primary_btn.configure(text="JOIN GAME", state="normal"))

    threading.Thread(target=_delayed_launch, daemon=True).start()


def on_lobby_connected(app: Any) -> None:
    """TCP callback (joiner): connected to host."""
    app.log("Connected to host lobby!")
    if app._current_screen == "lobby":
        app.lobby_launch_btn.configure(text="READY", fg_color=COLOR_ACCENT, state="normal")
    else:
        app.primary_btn.configure(text="READY", fg_color=COLOR_ACCENT)


def on_lobby_disconnected(app: Any, reason: str) -> None:
    """TCP callback: connection lost."""
    app.log(f"Disconnected: {reason}")
    app._lobby_client = None
    clear_remote_players(app)
    if app._current_screen == "lobby":
        app._show_screen("browser")
        browser_screen.start_beacon_listener(app)
        browser_screen.start_relay_polling(app)


def on_lobby_error(app: Any, error: str) -> None:
    """TCP callback: connection error."""
    app.log(f"Lobby error: {error}")
    app._lobby_client = None
    clear_remote_players(app)
    if app._current_screen == "lobby":
        app._show_screen("browser")
        browser_screen.start_beacon_listener(app)
        browser_screen.start_relay_polling(app)


def on_chat_received(app: Any, sender: str, text: str) -> None:
    """TCP callback: chat message received."""
    if app._current_screen == "lobby":
        append_lobby_chat(app, sender, text)
    else:
        app._append_chat(sender, text)


def on_kicked(app: Any, reason: str) -> None:
    """TCP callback (joiner): kicked from lobby."""
    app.log(f"Kicked from lobby: {reason}")
    app._lobby_client = None
    clear_remote_players(app)
    if app._current_screen == "lobby":
        app._show_screen("browser")
        browser_screen.start_beacon_listener(app)
        browser_screen.start_relay_polling(app)


def kick_player(app: Any, player_id: int) -> None:
    """Host kicks a player from the lobby."""
    if app._lobby_server:
        info = app._remote_players.get(player_id)
        name = info["name"] if info else "?"
        app._lobby_server.kick_player(player_id)
        app.log(f"Kicked player: {name}")


# ---------------------------------------------------------------------------
# File transfer callbacks
# ---------------------------------------------------------------------------


def on_file_request(app: Any, player_id: int, category: str, name: str) -> None:
    """Host callback: joiner is requesting files."""
    if category == "map":
        app.log(f"Player requested map: {name} \u2014 sending...")
        threading.Thread(
            target=_stream_map_to_player,
            args=(app, player_id, name),
            daemon=True,
        ).start()


def _stream_map_to_player(app: Any, player_id: int, map_folder: str) -> None:
    """Background thread: stream a map's files to a specific joiner."""
    if not app._lobby_server:
        return
    map_dir = file_transfer.find_map_directory(map_folder)
    if not map_dir:
        app.after(0, app.log, f"Cannot find map '{map_folder}' to send!")
        return

    manifest = file_transfer.build_file_manifest(map_dir)
    total_size = file_transfer.total_transfer_size(manifest)
    app.after(
        0,
        app.log,
        f"Sending map '{map_folder}' "
        f"({file_transfer.format_size(total_size)}, {len(manifest)} files)",
    )

    # Send manifest
    app._lobby_server.send_to_player(
        player_id,
        {
            "type": "FileManifest",
            "category": "map",
            "name": map_folder,
            "files": manifest,
        },
    )

    # Stream each file in chunks
    for f_info in manifest:
        chunks = file_transfer.iter_file_chunks(map_dir, f_info["path"])
        for chunk in chunks:
            app._lobby_server.send_to_player(
                player_id,
                {
                    "type": "FileChunk",
                    "category": "map",
                    **chunk,
                },
            )

    # Send completion
    app._lobby_server.send_to_player(
        player_id,
        {"type": "FileComplete", "category": "map", "name": map_folder},
    )
    app.after(0, app.log, f"Map '{map_folder}' sent to player")


def on_file_manifest(app: Any, category: str, name: str, files: list[dict[str, Any]]) -> None:
    """Joiner callback: received file manifest from host."""
    total = file_transfer.total_transfer_size(files)
    app.log(f"Downloading {category} '{name}' ({file_transfer.format_size(total)})...")
    # Store manifest for verification
    app._pending_download = {
        "category": category,
        "name": name,
        "files": {f["path"]: f for f in files},
        "received_files": set(),
    }


def on_file_chunk(app: Any, category: str, path: str, index: int, total: int, data: str) -> None:
    """Joiner callback: received a file chunk — write to disk."""
    if category == "map":
        dest_dir = file_transfer.get_map_install_dir() / app._pending_download.get("name", "")
        file_transfer.write_chunk_to_disk(dest_dir, path, index, total, data)
        # Log progress for last chunk of each file
        if index == total - 1:
            dl = app._pending_download
            if dl:
                dl["received_files"].add(path)
                done = len(dl["received_files"])
                expected = len(dl.get("files", {}))
                app.log(f"  [{done}/{expected}] {path}")


def on_file_complete(app: Any, category: str, name: str) -> None:
    """Joiner callback: file transfer complete — verify and refresh."""
    if category == "map":
        dest_dir = file_transfer.get_map_install_dir() / name
        dl = app._pending_download
        ok = True
        if dl and dl.get("files"):
            for rel_path, info in dl["files"].items():
                if not file_transfer.verify_file(dest_dir, rel_path, info["sha256"]):
                    app.log(f"WARNING: Hash mismatch for {rel_path}!")
                    ok = False
        if ok:
            app.log(f"Map '{name}' downloaded and verified!")
            # Refresh map list
            app._all_maps = map_scanner.scan_all_maps()
        else:
            app.log(f"WARNING: Map '{name}' download had errors!")
        app._pending_download = {}


# ---------------------------------------------------------------------------
# Game state management (host builds this for joiners)
# ---------------------------------------------------------------------------


def on_game_state_received(app: Any, state: dict[str, Any]) -> None:
    """TCP callback (joiner): full game state from host."""
    # Handle partial player updates
    if "player_update" in state:
        return  # For now, we only care about full state updates

    # Store the received state for use at launch time
    app._received_game_state = state
    logger.info(
        "Received game state: map=%s, options=%d, ai=%d, players=%d",
        state.get("map_folder", "?"),
        len(state.get("game_options", {})),
        len(state.get("ai_slots", [])),
        len(state.get("players", [])),
    )

    # Update map display and check if joiner has the map
    if "map_name" in state:
        map_name = state["map_name"]
        map_folder = state.get("map_folder", "")
        if hasattr(app, "header_label"):
            app.header_label.configure(text=f"Map: {map_name}")
        if hasattr(app, "lobby_map_label"):
            app.lobby_map_label.configure(text=map_name)
        # Persist host's map so cmd_launch() picks it up
        if map_folder:
            prefs.set_active_map(map_folder)
        # Check if joiner has this map — auto-download if missing
        if map_folder:
            # Check _all_maps cache first, then fall back to filesystem
            has_map = any(m.folder_name == map_folder for m in getattr(app, "_all_maps", []))
            if not has_map:
                # Filesystem fallback: check both maps/ and usermaps/
                has_map = (config.WOPC_MAPS / map_folder).is_dir() or (
                    config.WOPC_USERMAPS / map_folder
                ).is_dir()
            if not has_map:
                app.log(f"Map '{map_name}' not found locally \u2014 requesting from host...")
                if app._lobby_client:
                    app._lobby_client.request_file("map", map_folder)

    # Update game options display
    if "game_options" in state:
        for key, val in state["game_options"].items():
            if key in app.game_option_vars:
                app.game_option_vars[key].set(val)
            if key in getattr(app, "lobby_option_vars", {}):
                app.lobby_option_vars[key].set(val)

    # Update AI slots display for joiner
    if "ai_slots" in state:
        app._apply_remote_ai_slots(state["ai_slots"])

    # Check content packs — warn about missing ones
    if "content_packs" in state:
        host_packs = state["content_packs"]
        local_packs = mods.get_enabled_packs()
        missing = [p for p in host_packs if p not in local_packs]
        extra = [p for p in local_packs if p not in host_packs]
        if missing:
            names = [mods.CONTENT_PACK_LABELS.get(p, p) for p in missing]
            app.log(f"WARNING: Host has content packs you don't: {', '.join(names)}")
            app.log("Enable them in the Mods panel to avoid desyncs!")
        if extra:
            names = [mods.CONTENT_PACK_LABELS.get(p, p) for p in extra]
            app.log(f"NOTE: You have extra packs not on host: {', '.join(names)}")

    # Update player list
    if "players" in state:
        for p in state["players"]:
            pid = p.get("player_id", 0)
            if pid and pid not in app._remote_players:
                app._add_remote_human_slot(pid, p["name"], p.get("faction", "random"), p["slot"])


def build_game_state(app: Any) -> dict[str, Any] | None:
    """Capture the full game configuration for broadcasting to joiners."""
    if not hasattr(app, "game_option_vars"):
        return None
    active_map = prefs.get_active_map()
    # Find display name for the map
    map_display = active_map
    for m in getattr(app, "_all_maps", []):
        if m.folder_name == active_map:
            map_display = m.display_name
            break

    state = {
        "map_folder": active_map,
        "map_name": map_display,
        "game_options": app.get_game_options(),
        "ai_slots": (
            app._get_lobby_ai_opponents()
            if app._current_screen == "lobby"
            else app.get_ai_opponents()
        ),
        "players": app._lobby_server.connected_players if app._lobby_server else [],
        "content_packs": mods.get_enabled_packs(),
    }
    logger.debug(
        "Built game state: map=%s, players=%d, ai=%d",
        active_map,
        len(state["players"]),
        len(state["ai_slots"]),
    )
    return state


def refresh_cached_game_state(app: Any) -> None:
    """Rebuild the cached game state snapshot (GUI thread only).

    The network thread calls ``get_cached_game_state()`` to read the
    snapshot without touching any tkinter widgets.
    """
    state = build_game_state(app)
    with app._game_state_lock:
        app._cached_game_state = state


def get_cached_game_state(app: Any) -> dict[str, Any] | None:
    """Return the last cached game state (thread-safe, any thread)."""
    with app._game_state_lock:
        state: dict[str, Any] | None = app._cached_game_state
        return state


def validate_before_launch(app: Any) -> list[str]:
    """Check pre-launch conditions. Returns list of error strings (empty = OK)."""
    errors: list[str] = []
    # Check map is selected
    active_map = prefs.get_active_map()
    if not active_map:
        errors.append("No map selected")
    # Check all remote players are ready (multiplayer only)
    not_ready = [
        info["name"] for info in app._remote_players.values() if not info.get("ready", False)
    ]
    if not_ready:
        errors.append(f"{', '.join(not_ready)} not ready")
    # Check for duplicate colors
    used_colors: list[str] = []
    for slot in app.player_slots:
        cvar = slot.get("color_var")
        if cvar:
            used_colors.append(cvar.get())
    dupes = {c for c in used_colors if used_colors.count(c) > 1}
    if dupes:
        errors.append(f"Duplicate player colors: {', '.join(sorted(dupes))}")
    # Check WOPC deployment is intact
    if not (config.WOPC_BIN / config.GAME_EXE).exists():
        errors.append("WOPC not deployed \u2014 run Install first")
    # Check manifest exists for multiplayer (warns only, doesn't block)
    manifest_path = config.WOPC_ROOT / "manifest.json"
    if app._remote_players and not manifest_path.exists():
        app.log("TIP: Run 'wopc manifest' to generate file hashes for desync prevention")
    return errors


def broadcast_game_state(app: Any) -> None:
    """Send the current game state to all connected joiners."""
    refresh_cached_game_state(app)
    if not app._lobby_server or not app._lobby_server.is_running:
        return
    state = get_cached_game_state(app)
    if state:
        app._lobby_server.broadcast_state(state)


# ---------------------------------------------------------------------------
# Remote player display
# ---------------------------------------------------------------------------


def clear_remote_players(app: Any) -> None:
    """Remove all remote player UI rows."""
    for info in app._remote_players.values():
        for w in info.get("widgets", []):
            w.destroy()
    app._remote_players.clear()


def update_host_button_text(app: Any) -> None:
    """Update lobby launch button to show connected player count."""
    if not app._is_hosting or not app._lobby_server:
        return
    n_remote = len(app._remote_players)
    expected = int(app.expected_var.get())
    total = 1 + n_remote  # host + connected peers
    if app._current_screen == "lobby":
        if n_remote == 0:
            app.lobby_launch_btn.configure(text="\u25b6  LAUNCH GAME (Waiting...)")
        else:
            app.lobby_launch_btn.configure(text=f"\u25b6  LAUNCH ({total}/{expected} players)")
