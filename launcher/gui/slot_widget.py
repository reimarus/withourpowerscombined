"""Player slot widget building and management for the WOPC launcher.

All slot-related UI construction (human slot, AI slot, remote player slot,
color picker, team balance, spawn tracking) lives here.  The host app
passes itself as the first argument so slots can read map info, broadcast
game state, and redraw the canvas.

Extracted from app.py to reduce the monolith and make slot logic reusable
across solo and multiplayer screens.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import customtkinter as ctk  # type: ignore[import-untyped,import-not-found]
else:
    try:
        import customtkinter as ctk  # type: ignore[import-untyped]
    except ImportError:
        ctk = None  # type: ignore[assignment]

try:
    from PIL import Image as PilImage  # type: ignore[import-not-found]

    _PIL_AVAILABLE = True
except ImportError:
    PilImage = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False

from launcher import prefs
from launcher.gui.constants import (
    AI_DISPLAY_NAMES as _AI_NAMES,
)
from launcher.gui.constants import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_BG,
    COLOR_DANGER,
    COLOR_PANEL,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    PLAYER_COLORS,
    color_hex_to_index,
    color_name_to_hex,
)
from launcher.gui.constants import (
    FACTION_NAMES as _FACTIONS,
)
from launcher.gui.constants import (
    MAX_SLOTS as _MAX_SLOTS,
)

_ICONS_DIR = __import__("pathlib").Path(__file__).parent / "icons"
_FACTION_ICON_SIZE = 20
_faction_icon_cache: dict[str, Any] = {}


def _get_faction_icon(faction: str) -> Any | None:
    """Return a cached CTkImage for the given faction, or None."""
    if not _PIL_AVAILABLE or ctk is None:
        return None
    key = faction.lower()
    if key in _faction_icon_cache:
        return _faction_icon_cache[key]
    path = _ICONS_DIR / f"faction_{key}.png"
    if not path.exists():
        _faction_icon_cache[key] = None
        return None
    img = PilImage.open(path).convert("RGBA")
    sz = (_FACTION_ICON_SIZE, _FACTION_ICON_SIZE)
    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=sz)
    _faction_icon_cache[key] = ctk_img
    return ctk_img


# ---------------------------------------------------------------------------
# Pure utility functions (no app reference needed)
# ---------------------------------------------------------------------------


def next_team(slots: list[dict[str, Any]]) -> str:
    """Return the team number string with fewest players for auto-balance."""
    counts: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0}
    for slot in slots:
        team = slot.get("team_var")
        if team:
            val = team.get() if hasattr(team, "get") else str(team)
            if val in counts:
                counts[val] += 1
    return min(counts, key=lambda t: (counts[t], int(t)))


def next_free_color(slot_list: list[dict[str, Any]]) -> str:
    """Return the next hex color not already taken by another slot."""
    used: set[str] = set()
    for slot in slot_list:
        cvar = slot.get("color_var")
        if cvar:
            used.add(cvar.get())
    for hex_val, _name in PLAYER_COLORS:
        if hex_val not in used:
            return hex_val
    return PLAYER_COLORS[0][0]


def get_color_names() -> list[str]:
    """Return list of color display names."""
    return [name for _, name in PLAYER_COLORS]


def color_to_hex(name: str) -> str:
    """Convert a color name or hex value to its hex value."""
    return color_name_to_hex(name)


def color_to_index(val: str) -> int:
    """Convert a color name or hex to the nearest 1-based SCFA engine color index."""
    return color_hex_to_index(val)


def first_free_spawn(app: Any) -> int:
    """Return the first unoccupied spawn index, or -1 if all taken."""
    info = app._current_map_info
    if info is None or info.markers is None:
        return -1
    n_armies = len(info.markers.armies)
    occupied: set[int] = set()
    for si, slot in enumerate(app.player_slots):
        occupied.add(slot.get("start_spot", si))
    for i in range(n_armies):
        if i not in occupied:
            return i
    return -1


# ---------------------------------------------------------------------------
# Slot building functions
# ---------------------------------------------------------------------------


def build_player_slots_in(app: Any, parent: Any, grid_row: int = 0) -> None:
    """Build the player slots panel inside the given parent frame."""
    slots_frame = ctk.CTkFrame(parent, fg_color="transparent")
    slots_frame.grid(row=grid_row, column=0, sticky="nsew")
    slots_frame.grid_columnconfigure(0, weight=1)
    slots_frame.grid_rowconfigure(1, weight=1)

    header_row = ctk.CTkFrame(slots_frame, fg_color="transparent")
    header_row.grid(row=0, column=0, sticky="ew")
    header_row.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        header_row,
        text="PLAYERS",
        text_color=COLOR_TEXT_GOLD,
        font=ctk.CTkFont(size=12, weight="bold"),
    ).grid(row=0, column=0, sticky="w")

    app.add_slot_btn = ctk.CTkButton(
        header_row,
        text="+ Add AI",
        width=65,
        height=22,
        fg_color=COLOR_ACCENT,
        hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        font=ctk.CTkFont(size=11),
        corner_radius=3,
        command=lambda: add_ai_slot(app),
    )
    app.add_slot_btn.grid(row=0, column=1, padx=(5, 0))

    app.slots_scroll = ctk.CTkScrollableFrame(slots_frame, fg_color="transparent")
    app.slots_scroll.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
    app.slots_scroll.grid_columnconfigure(1, weight=1)

    app.player_slots = []  # list[dict[str, Any]]

    add_human_slot(app)
    add_ai_slot(app)


def add_human_slot(app: Any) -> None:
    """Add the human player row (always slot 1, cannot be removed)."""
    row = len(app.player_slots)
    widgets: list[Any] = []

    lbl = ctk.CTkLabel(
        app.slots_scroll,
        text="1",
        width=20,
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=12),
    )
    lbl.grid(row=row, column=0, padx=(0, 5), pady=2)
    widgets.append(lbl)

    player_name = prefs.get_player_name() or "Player"
    type_lbl = ctk.CTkLabel(
        app.slots_scroll,
        text=player_name,
        text_color=COLOR_ACCENT,
        font=ctk.CTkFont(size=12, weight="bold"),
        anchor="w",
    )
    type_lbl.grid(row=row, column=1, sticky="w", pady=2)
    widgets.append(type_lbl)

    human_faction = prefs.get_player_faction()
    faction_icon = _get_faction_icon(human_faction)
    faction_lbl = ctk.CTkLabel(
        app.slots_scroll,
        text=human_faction.capitalize(),
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=11),
        image=faction_icon,
        compound="left",
    )
    faction_lbl.grid(row=row, column=2, padx=5, pady=2)
    widgets.append(faction_lbl)

    team_var = ctk.StringVar(value="1")
    team_menu = ctk.CTkOptionMenu(
        app.slots_scroll,
        values=["1", "2", "3", "4"],
        variable=team_var,
        command=lambda _val: on_team_change(app, _val),
        width=50,
        height=24,
    )
    team_menu.grid(row=row, column=3, padx=5, pady=2)
    widgets.append(team_menu)

    color_indicator = tk.Canvas(
        app.slots_scroll,
        width=22,
        height=22,
        highlightthickness=1,
        highlightbackground=COLOR_TEXT_MUTED,
        bg=app.player_color_var.get(),
    )
    color_indicator.grid(row=row, column=4, padx=5, pady=2)
    widgets.append(color_indicator)
    app._human_color_indicator = color_indicator

    spacer = ctk.CTkLabel(app.slots_scroll, text="", width=24)
    spacer.grid(row=row, column=5, pady=2)
    widgets.append(spacer)

    app.player_slots.append(
        {
            "type": "human",
            "team_var": team_var,
            "color_var": app.player_color_var,
            "widgets": widgets,
        }
    )


def add_ai_slot(app: Any) -> None:
    """Add an AI opponent slot row (solo mode)."""
    add_ai_slot_to(
        app,
        parent=app.slots_scroll,
        slot_list=app.player_slots,
        use_swatch=True,
        track_spawn=True,
    )


def add_lobby_ai_slot(app: Any) -> None:
    """Add an AI opponent slot row (lobby mode)."""
    add_ai_slot_to(
        app,
        parent=app.lobby_slots_scroll,
        slot_list=app.lobby_player_slots,
        use_swatch=True,
        track_spawn=False,
    )
    # Assign sequential spawn to the new slot and redraw lobby canvas
    new_slot = app.lobby_player_slots[-1] if app.lobby_player_slots else None
    if new_slot and "start_spot" not in new_slot:
        new_slot["start_spot"] = len(app.lobby_player_slots) - 1
    # Lazy import to avoid circular dependency
    from launcher.gui import lobby_screen

    lobby_screen._redraw_lobby_canvas(app)


def add_ai_slot_to(
    app: Any,
    parent: Any,
    slot_list: list[dict[str, Any]],
    *,
    use_swatch: bool = True,
    track_spawn: bool = False,
) -> None:
    """Unified AI slot builder for both solo and lobby screens."""
    info = app._current_map_info
    max_armies = len(info.markers.armies) if info and info.markers else _MAX_SLOTS
    if len(slot_list) >= min(_MAX_SLOTS, max_armies):
        return

    free_spawn = first_free_spawn(app) if track_spawn else -1

    row = len(slot_list)
    slot_num = row + 1
    widgets: list[Any] = []

    lbl = ctk.CTkLabel(
        parent,
        text=str(slot_num),
        width=20,
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=12),
    )
    lbl.grid(row=row, column=0, padx=(0, 5), pady=2)
    widgets.append(lbl)

    ai_var = ctk.StringVar(value="Medium")
    ai_menu = ctk.CTkOptionMenu(
        parent,
        values=list(_AI_NAMES),
        variable=ai_var,
        width=70,
        height=24,
    )
    ai_menu.grid(row=row, column=1, sticky="w", pady=2)
    widgets.append(ai_menu)

    faction_var = ctk.StringVar(value="Random")
    faction_frame = ctk.CTkFrame(parent, fg_color="transparent")
    faction_frame.grid(row=row, column=2, padx=5, pady=2, sticky="w")

    faction_icon_lbl = ctk.CTkLabel(
        faction_frame,
        text="",
        image=_get_faction_icon("random"),
        width=_FACTION_ICON_SIZE,
    )
    faction_icon_lbl.grid(row=0, column=0, padx=(0, 2))

    def _on_faction_change(val: str, lbl: Any = faction_icon_lbl) -> None:
        icon = _get_faction_icon(val)
        if icon:
            lbl.configure(image=icon)

    faction_menu = ctk.CTkOptionMenu(
        faction_frame,
        values=list(_FACTIONS),
        variable=faction_var,
        command=_on_faction_change,
        width=70,
        height=24,
    )
    faction_menu.grid(row=0, column=1)
    widgets.append(faction_frame)

    team_var = ctk.StringVar(value=next_team(slot_list))
    team_menu = ctk.CTkOptionMenu(
        parent,
        values=["1", "2", "3", "4"],
        variable=team_var,
        command=lambda _val: on_team_change(app, _val),
        width=50,
        height=24,
    )
    team_menu.grid(row=row, column=3, padx=5, pady=2)
    widgets.append(team_menu)

    color_var = ctk.StringVar(value=next_free_color(slot_list))
    if use_swatch:
        color_widget = create_color_swatch(app, parent, color_var, row, 4)
    else:
        color_widget = ctk.CTkOptionMenu(
            parent,
            values=get_color_names(),
            variable=color_var,
            command=lambda _val: on_color_change(app, _val),
            width=70,
            height=24,
        )
        color_widget.grid(row=row, column=4, padx=5, pady=2)
    widgets.append(color_widget)

    slot_dict: dict[str, Any] = {
        "type": "ai",
        "ai_var": ai_var,
        "faction_var": faction_var,
        "team_var": team_var,
        "color_var": color_var,
        "widgets": widgets,
    }
    if track_spawn and free_spawn >= 0:
        slot_dict["start_spot"] = free_spawn

    def remove_this(
        sd: dict[str, Any] = slot_dict,
        sl: list[dict[str, Any]] = slot_list,
        redraw: bool = track_spawn,
    ) -> None:
        try:
            idx = sl.index(sd)
        except ValueError:
            return
        remove_slot_from(app, sl, idx, redraw=redraw)

    remove_btn = ctk.CTkButton(
        parent,
        text="✕",
        width=24,
        height=24,
        fg_color="transparent",
        hover_color=COLOR_DANGER,
        text_color=COLOR_TEXT_MUTED,
        command=remove_this,
    )
    remove_btn.grid(row=row, column=5, pady=2)
    widgets.append(remove_btn)

    slot_list.append(slot_dict)
    app._broadcast_game_state()
    if track_spawn:
        app._redraw_canvas()


def remove_slot_from(
    app: Any, slot_list: list[dict[str, Any]], index: int, *, redraw: bool = False
) -> None:
    """Unified slot removal for both solo and lobby screens."""
    if index < 0 or index >= len(slot_list):
        return
    if slot_list is app.player_slots and index < 1:
        return

    slot = slot_list.pop(index)
    for w in slot["widgets"]:
        w.destroy()

    for i, s in enumerate(slot_list):
        for w in s["widgets"]:
            w.grid_configure(row=i)
        s["widgets"][0].configure(text=str(i + 1))
    app._broadcast_game_state()
    if redraw:
        app._redraw_canvas()
    # Redraw lobby canvas when removing lobby slots
    if slot_list is app.lobby_player_slots:
        from launcher.gui import lobby_screen

        lobby_screen._redraw_lobby_canvas(app)


def clear_lobby_player_slots(app: Any) -> None:
    """Destroy all lobby player slot widgets and clear the list."""
    for slot in app.lobby_player_slots:
        for w in slot["widgets"]:
            w.destroy()
    app.lobby_player_slots.clear()


# ---------------------------------------------------------------------------
# Remote player slots (multiplayer)
# ---------------------------------------------------------------------------


def add_remote_human_slot(app: Any, player_id: int, name: str, faction: str, slot: int) -> None:
    """Insert a row in player slots for a remote human player."""
    scroll = app.slots_scroll if hasattr(app, "slots_scroll") else app.lobby_slots_scroll
    row = len(app.player_slots) + len(app._remote_players)
    widgets: list[Any] = []

    slot_lbl = ctk.CTkLabel(
        scroll,
        text=str(slot),
        width=20,
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=12),
    )
    slot_lbl.grid(row=row, column=0, padx=(0, 5), pady=2)
    widgets.append(slot_lbl)

    name_lbl = ctk.CTkLabel(
        scroll,
        text=name,
        text_color=COLOR_ACCENT,
        font=ctk.CTkFont(size=12, weight="bold"),
        anchor="w",
    )
    name_lbl.grid(row=row, column=1, sticky="w", pady=2)
    widgets.append(name_lbl)

    faction_icon = _get_faction_icon(faction)
    faction_lbl = ctk.CTkLabel(
        scroll,
        text=faction.capitalize(),
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=11),
        image=faction_icon,
        compound="left",
    )
    faction_lbl.grid(row=row, column=2, padx=5, pady=2)
    widgets.append(faction_lbl)

    ready_lbl = ctk.CTkLabel(
        scroll,
        text="—",
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=14, weight="bold"),
        width=50,
    )
    ready_lbl.grid(row=row, column=3, padx=5, pady=2)
    widgets.append(ready_lbl)

    color_lbl = ctk.CTkLabel(
        scroll,
        text="●",
        text_color=COLOR_TEXT_MUTED,
        font=ctk.CTkFont(size=14),
        width=70,
    )
    color_lbl.grid(row=row, column=4, padx=5, pady=2)
    widgets.append(color_lbl)

    if app._is_hosting:
        pid_capture = player_id

        def kick_this(pid: int = pid_capture) -> None:
            app._kick_player(pid)

        kick_btn = ctk.CTkButton(
            scroll,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color=COLOR_DANGER,
            text_color=COLOR_TEXT_MUTED,
            command=kick_this,
        )
        kick_btn.grid(row=row, column=5, pady=2)
        widgets.append(kick_btn)
    else:
        spacer = ctk.CTkLabel(scroll, text="", width=24)
        spacer.grid(row=row, column=5, pady=2)
        widgets.append(spacer)

    app._remote_players[player_id] = {
        "name": name,
        "faction": faction,
        "slot": slot,
        "ready": False,
        "widgets": widgets,
        "name_lbl": name_lbl,
        "faction_lbl": faction_lbl,
        "ready_lbl": ready_lbl,
    }


def apply_remote_ai_slots(app: Any, ai_slots: list[dict[str, Any]]) -> None:
    """Update the joiner's AI slot display to match host's config."""
    if app._current_screen == "lobby":
        scroll = app.lobby_slots_scroll
        slots = app.lobby_player_slots
        clear_lobby_player_slots(app)
    else:
        scroll = app.slots_scroll
        slots = app.player_slots
        while len(slots) > 1:
            slot = slots.pop()
            for w in slot["widgets"]:
                w.destroy()

    if hasattr(app, "add_slot_btn"):
        app.add_slot_btn.configure(state="disabled")
    if hasattr(app, "lobby_add_ai_btn"):
        app.lobby_add_ai_btn.configure(state="disabled")

    for ai in ai_slots:
        row = len(slots) + len(app._remote_players)
        widgets: list[Any] = []
        slot_num = len(slots) + 1

        lbl = ctk.CTkLabel(
            scroll,
            text=str(slot_num),
            width=20,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        lbl.grid(row=row, column=0, padx=(0, 5), pady=2)
        widgets.append(lbl)

        name_lbl = ctk.CTkLabel(
            scroll,
            text=ai.get("name", "AI"),
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        name_lbl.grid(row=row, column=1, sticky="w", pady=2)
        widgets.append(name_lbl)

        ai_faction = ai.get("faction", "random")
        faction_lbl = ctk.CTkLabel(
            scroll,
            text=ai_faction.capitalize(),
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
            image=_get_faction_icon(ai_faction),
            compound="left",
        )
        faction_lbl.grid(row=row, column=2, padx=5, pady=2)
        widgets.append(faction_lbl)

        team_lbl = ctk.CTkLabel(
            scroll,
            text=str(ai.get("team", 2)),
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
            width=50,
        )
        team_lbl.grid(row=row, column=3, padx=5, pady=2)
        widgets.append(team_lbl)

        color_idx = ai.get("color", 0)
        color_hex = (
            PLAYER_COLORS[color_idx - 1][0]
            if 1 <= color_idx <= len(PLAYER_COLORS)
            else COLOR_TEXT_MUTED
        )
        color_lbl = ctk.CTkLabel(
            scroll,
            text="●",
            text_color=color_hex,
            font=ctk.CTkFont(size=14),
            width=70,
        )
        color_lbl.grid(row=row, column=4, padx=5, pady=2)
        widgets.append(color_lbl)

        spacer = ctk.CTkLabel(scroll, text="", width=24)
        spacer.grid(row=row, column=5, pady=2)
        widgets.append(spacer)

        slots.append({"type": "ai_remote", "widgets": widgets})


# ---------------------------------------------------------------------------
# Color picker
# ---------------------------------------------------------------------------


def on_color_change(app: Any, _val: str) -> None:
    """Broadcast state and redraw map when a color changes."""
    if hasattr(app, "_map_canvas_widget"):
        app._map_canvas_widget.invalidate_tint_cache()
    if hasattr(app, "_lobby_map_canvas_widget"):
        app._lobby_map_canvas_widget.invalidate_tint_cache()
    if hasattr(app, "player_color_var"):
        hex_color = app.player_color_var.get()
        prefs.set_player_color(hex_color)
        indicator = getattr(app, "_human_color_indicator", None)
        if indicator:
            indicator.configure(bg=hex_color)
        lobby_indicator = getattr(app, "_lobby_host_color_indicator", None)
        if lobby_indicator:
            lobby_indicator.configure(bg=hex_color)
    app._broadcast_game_state()
    app._redraw_canvas()
    # Also redraw the lobby canvas so multiplayer map markers update
    if hasattr(app, "_lobby_map_canvas_widget"):
        from launcher.gui import lobby_screen

        lobby_screen._redraw_lobby_canvas(app)


def on_team_change(app: Any, _val: str) -> None:
    """Broadcast state and redraw map when a team assignment changes."""
    app._broadcast_game_state()
    app._redraw_canvas()
    if hasattr(app, "_lobby_map_canvas_widget"):
        from launcher.gui import lobby_screen

        lobby_screen._redraw_lobby_canvas(app)


def create_color_swatch(app: Any, parent: Any, color_var: Any, row: int, col: int) -> Any:
    """Create a clickable color swatch button that opens a color picker popup."""
    swatch_size = 22
    swatch = tk.Canvas(
        parent,
        width=swatch_size,
        height=swatch_size,
        highlightthickness=2,
        highlightbackground=COLOR_TEXT_MUTED,
        bg=COLOR_PANEL,
        cursor="hand2",
    )
    raw_color = color_var.get()
    hex_color = raw_color if raw_color.startswith("#") else color_to_hex(raw_color)
    swatch.create_rectangle(
        2,
        2,
        swatch_size - 1,
        swatch_size - 1,
        fill=hex_color,
        outline="#333333",
    )
    swatch.grid(row=row, column=col, padx=5, pady=2)

    def _on_swatch_click(event: Any) -> None:
        show_color_popup(app, swatch, color_var)

    swatch.bind("<Button-1>", _on_swatch_click)

    color_var._swatch = swatch  # type: ignore[attr-defined]
    color_var._swatch_size = swatch_size  # type: ignore[attr-defined]
    return swatch


def show_color_popup(app: Any, anchor: Any, color_var: Any) -> None:
    """Show an HSV color wheel popup with brightness slider."""
    import colorsys
    import math

    popup = tk.Toplevel(app)
    popup.overrideredirect(True)
    popup.configure(bg=COLOR_PANEL)

    x = anchor.winfo_rootx()
    y = anchor.winfo_rooty() + anchor.winfo_height() + 2
    popup.geometry(f"+{x}+{y}")

    wheel_size = 160
    brightness = [1.0]
    wheel_canvas = tk.Canvas(
        popup,
        width=wheel_size,
        height=wheel_size,
        bg=COLOR_PANEL,
        highlightthickness=0,
    )
    wheel_canvas.grid(row=0, column=0, padx=8, pady=(8, 4))

    if _PIL_AVAILABLE:
        from PIL import ImageTk  # type: ignore[import-not-found]

        def _render_wheel(val: float = 1.0) -> Any:
            wheel_img = PilImage.new("RGBA", (wheel_size, wheel_size), (0, 0, 0, 0))
            px = wheel_img.load()
            cx, cy = wheel_size // 2, wheel_size // 2
            radius = wheel_size // 2 - 2
            for yi in range(wheel_size):
                for xi in range(wheel_size):
                    dx = xi - cx
                    dy = yi - cy
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= radius:
                        hue = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0
                        sat = dist / radius
                        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
                        px[xi, yi] = (int(r * 255), int(g * 255), int(b * 255), 255)  # type: ignore[index]
            return wheel_img

        wheel_pil = _render_wheel(1.0)
        wheel_tk = ImageTk.PhotoImage(wheel_pil)
        wheel_canvas.create_image(0, 0, anchor="nw", image=wheel_tk)
        wheel_canvas._wheel_tk = wheel_tk  # type: ignore[attr-defined]
        wheel_canvas._wheel_pil = wheel_pil  # type: ignore[attr-defined]

    preview_frame = tk.Frame(popup, bg=COLOR_PANEL)
    preview_frame.grid(row=0, column=1, padx=(0, 8), pady=(8, 4), sticky="n")
    preview = tk.Canvas(
        preview_frame,
        width=40,
        height=40,
        bg=COLOR_PANEL,
        highlightthickness=1,
        highlightbackground=COLOR_TEXT_MUTED,
    )
    raw_val = color_var.get()
    current_hex = raw_val if raw_val.startswith("#") else color_to_hex(raw_val)
    preview.create_rectangle(0, 0, 40, 40, fill=current_hex, outline="", tags="prev")
    preview.grid(row=0, column=0, pady=(0, 4))

    def _apply_color() -> None:
        hex_val = preview._chosen_hex  # type: ignore[attr-defined]
        color_var.set(hex_val)
        swatch_ref = getattr(color_var, "_swatch", None)
        if swatch_ref:
            sz = getattr(color_var, "_swatch_size", 22)
            swatch_ref.delete("all")
            swatch_ref.create_rectangle(0, 0, sz, sz, fill=hex_val, outline="")
        on_color_change(app, hex_val)
        popup.destroy()

    apply_btn = tk.Button(
        preview_frame,
        text="OK",
        command=_apply_color,
        bg=COLOR_ACCENT,
        fg=COLOR_BG,
        width=5,
        relief="flat",
        cursor="hand2",
    )
    apply_btn.grid(row=1, column=0, pady=(2, 0))
    preview._chosen_hex = current_hex  # type: ignore[attr-defined]

    slider_frame = tk.Frame(popup, bg=COLOR_PANEL)
    slider_frame.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")

    slider = tk.Scale(
        slider_frame,
        from_=100,
        to=10,
        orient="horizontal",
        bg=COLOR_PANEL,
        fg=COLOR_TEXT_PRIMARY,
        troughcolor=COLOR_BG,
        highlightthickness=0,
        length=wheel_size,
        showvalue=False,
        command=lambda v: _on_brightness(int(v)),
    )
    slider.set(100)
    slider.grid(row=0, column=0, sticky="ew")
    tk.Label(
        slider_frame,
        text="Brightness",
        bg=COLOR_PANEL,
        fg=COLOR_TEXT_MUTED,
        font=("Segoe UI", 9),
    ).grid(row=1, column=0)

    def _on_brightness(val: int) -> None:
        brightness[0] = val / 100.0
        if _PIL_AVAILABLE:
            from PIL import ImageTk  # type: ignore[import-not-found]

            wheel_pil_new = _render_wheel(brightness[0])
            wheel_tk_new = ImageTk.PhotoImage(wheel_pil_new)
            wheel_canvas.delete("all")
            wheel_canvas.create_image(0, 0, anchor="nw", image=wheel_tk_new)
            wheel_canvas._wheel_tk = wheel_tk_new  # type: ignore[attr-defined]
            wheel_canvas._wheel_pil = wheel_pil_new  # type: ignore[attr-defined]

    def _on_wheel_click(event: Any) -> None:
        cx, cy = wheel_size // 2, wheel_size // 2
        dx = event.x - cx
        dy = event.y - cy
        dist = math.sqrt(dx * dx + dy * dy)
        radius = wheel_size // 2 - 2
        if dist > radius:
            return
        hue = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0
        sat = min(dist / radius, 1.0)
        r, g, b = colorsys.hsv_to_rgb(hue, sat, brightness[0])
        hex_val = f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"
        preview.delete("prev")
        preview.create_rectangle(0, 0, 40, 40, fill=hex_val, outline="", tags="prev")
        preview._chosen_hex = hex_val  # type: ignore[attr-defined]

    wheel_canvas.bind("<Button-1>", _on_wheel_click)
    wheel_canvas.bind("<B1-Motion>", _on_wheel_click)

    popup.bind("<FocusOut>", lambda e: popup.destroy())
    popup.focus_set()


# ---------------------------------------------------------------------------
# Engine-format extraction helpers
# ---------------------------------------------------------------------------


def get_ai_opponents_from(
    app: Any,
    slot_list: list[dict[str, Any]],
    *,
    engine_offset: bool = False,
) -> list[dict[str, Any]]:
    """Unified AI opponent extraction from any slot list."""
    opponents: list[dict[str, Any]] = []
    for si, slot in enumerate(slot_list):
        if slot.get("type") != "ai":
            continue
        ai_display = slot["ai_var"].get()
        ai_key = ai_display.lower()
        faction = slot["faction_var"].get().lower()
        team = int(slot["team_var"].get())
        if engine_offset:
            team += 1
        color = color_to_index(slot["color_var"].get())
        entry: dict[str, Any] = {
            "name": f"AI {len(opponents) + 1}: {ai_display}",
            "faction": faction,
            "ai": ai_key,
            "team": team,
            "color": color,
        }
        if engine_offset:
            entry["start_spot"] = slot.get("start_spot", si) + 1
        opponents.append(entry)
    return opponents
