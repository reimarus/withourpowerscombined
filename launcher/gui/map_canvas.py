"""Interactive map preview canvas for the WOPC launcher.

Handles map rendering, zoom/pan, mass/hydro/spawn marker overlays,
spawn click-to-select, drag-to-swap, and hover highlighting.

Extracted from app.py to isolate canvas logic from the main GUI class.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from PIL import Image as PilImage  # type: ignore[import-not-found]

    _PIL_AVAILABLE = True
except ImportError:
    PilImage = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False

if TYPE_CHECKING:
    from launcher import map_scanner

from launcher.gui.constants import DRAG_THRESHOLD, PLAYER_COLORS, color_name_to_hex

logger = logging.getLogger("wopc.gui.map_canvas")

# UI color constants (matches app.py palette)
_COLOR_BG = "#080C14"
_COLOR_TEXT_MUTED = "#4A5A70"


def _icons_dir() -> Path:
    """Resolve the GUI icons directory (works in dev mode and frozen exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "launcher" / "gui" / "icons"  # type: ignore[attr-defined]
    return Path(__file__).parent / "icons"


# ---------------------------------------------------------------------------
# Slot protocol — minimal interface the canvas needs from the host
# ---------------------------------------------------------------------------


class SlotAccessor:
    """Protocol-like adapter for reading player slot data.

    The canvas doesn't know about tkinter StringVars or widget dicts.
    The host (WopcApp) provides a concrete implementation that reads
    from its ``player_slots`` list.
    """

    def slot_count(self) -> int:
        """Number of active player slots."""
        return 0

    def slot_start_spot(self, index: int) -> int:
        """0-based spawn position for slot *index*."""
        return index

    def slot_color_hex(self, index: int) -> str:
        """Hex color string for slot *index*."""
        return PLAYER_COLORS[index % len(PLAYER_COLORS)][0]

    def slot_team_label(self, index: int) -> str:
        """Team display label for slot *index*."""
        return ""


class DictSlotAccessor(SlotAccessor):
    """Reads slot data from the WopcApp's ``player_slots`` dict-list."""

    def __init__(self, slots: list[dict[str, Any]]) -> None:
        self._slots = slots

    def slot_count(self) -> int:
        return len(self._slots)

    def slot_start_spot(self, index: int) -> int:
        return int(self._slots[index].get("start_spot", index))

    def slot_color_hex(self, index: int) -> str:
        cvar = self._slots[index].get("color_var")
        if cvar:
            return color_name_to_hex(cvar.get())
        return "#444444"

    def slot_team_label(self, index: int) -> str:
        team = self._slots[index].get("team_var")
        if team and hasattr(team, "get"):
            return str(team.get())
        return ""


# ---------------------------------------------------------------------------
# MapCanvas
# ---------------------------------------------------------------------------


class MapCanvas:
    """Encapsulates the interactive map preview canvas.

    Parameters
    ----------
    parent : tk widget
        The parent frame for the canvas.
    slot_accessor : SlotAccessor
        Adapter for reading current player slot state.
    on_spawn_select : callable(int) -> None
        Called when the user clicks a spawn position.
    on_spawn_swap : callable(int, int) -> None
        Called when the user drags one spawn onto another.
    after_fn : callable
        ``widget.after()`` function for scheduling (throttled redraws).
    cancel_fn : callable
        ``widget.after_cancel()`` function.
    """

    def __init__(
        self,
        parent: Any,
        slot_accessor: SlotAccessor,
        on_spawn_select: Callable[[int], None],
        on_spawn_swap: Callable[[int, int], None],
        after_fn: Callable[..., str],
        cancel_fn: Callable[[str], None],
    ) -> None:
        self._slot_accessor = slot_accessor
        self._on_spawn_select = on_spawn_select
        self._on_spawn_swap = on_spawn_swap
        self._after = after_fn
        self._cancel = cancel_fn

        # Canvas state
        self._map_info: map_scanner.MapInfo | None = None
        self._raw_preview: Any = None
        self._canvas_tk_image: Any = None
        self._canvas_image_id: int | None = None
        self._marker_tk_cache: list[Any] = []
        self._tinted_icon_cache: dict[tuple[str, int, str], Any] = {}
        self._marker_icons: dict[str, Any] = {}

        # Zoom / pan
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0

        # Drag
        self._drag_start: tuple[int, int] | None = None
        self._drag_moved: bool = False
        self._drag_spawn_src: int = -1
        self._hover_spawn: int = -1

        # Throttle IDs
        self._canvas_redraw_id: str | None = None
        self._scroll_redraw_id: str | None = None

        # Load icons
        self._load_marker_icons()

        # Build the canvas widget
        self.canvas = tk.Canvas(parent, bg=_COLOR_BG, highlightthickness=0, cursor="hand2")
        self.canvas.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_map(
        self,
        map_info: map_scanner.MapInfo | None,
        raw_preview: Any = None,
    ) -> None:
        """Set the current map and optional raw PIL preview image."""
        self._map_info = map_info
        self._raw_preview = raw_preview
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._tinted_icon_cache.clear()
        self._hover_spawn = -1
        self.redraw()
        # Safety net: if redraw() bailed because the canvas hasn't been laid
        # out yet (winfo_width() == 1), schedule a deferred retry so the map
        # preview isn't left black.  (Backlog #50)
        if self.canvas.winfo_width() < 10:
            if self._canvas_redraw_id is not None:
                self._cancel(self._canvas_redraw_id)
            self._canvas_redraw_id = self._after(100, self.redraw)

    def redraw(self) -> None:
        """Full redraw of the map preview and all overlays."""
        canvas = self.canvas
        canvas.delete("all")

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        base_size = min(cw, ch)
        size = int(base_size * self._zoom)
        ox = int((cw - size) / 2 + self._pan_x)
        oy = int((ch - size) / 2 + self._pan_y)

        if self._raw_preview is not None and _PIL_AVAILABLE:
            from PIL import ImageTk  # type: ignore[import-not-found]

            resample = (
                PilImage.LANCZOS if self._zoom == 1.0 else PilImage.BILINEAR  # type: ignore[attr-defined]
            )
            resized = self._raw_preview.resize((size, size), resample)
            self._canvas_tk_image = ImageTk.PhotoImage(resized)
            self._canvas_image_id = canvas.create_image(
                ox, oy, anchor="nw", image=self._canvas_tk_image
            )
        else:
            canvas.create_rectangle(ox, oy, ox + size, oy + size, fill=_COLOR_BG, outline="")
            canvas.create_text(
                ox + size // 2,
                oy + size // 2,
                text="No Preview",
                fill=_COLOR_TEXT_MUTED,
                font=("Segoe UI", 12),
            )
            return

        info = self._map_info
        if info is None or info.markers is None or info.map_width == 0:
            return

        from PIL import ImageTk  # type: ignore[import-not-found]

        mw = info.map_width
        mh = info.map_height or mw
        self._marker_tk_cache.clear()

        def _map_to_px(mx: float, mz: float) -> tuple[int, int]:
            px = ox + int(mx / mw * size)
            py = oy + int(mz / mh * size)
            return px, py

        def _draw_icon(icon_key: str, px: int, py: int, icon_size: int) -> None:
            raw = self._marker_icons.get(icon_key)
            if raw is not None:
                scaled = raw.resize(
                    (icon_size, icon_size),
                    PilImage.BILINEAR,  # type: ignore[attr-defined]
                )
                tk_img = ImageTk.PhotoImage(scaled)
                canvas.create_image(px, py, image=tk_img)
                self._marker_tk_cache.append(tk_img)

        # Mass markers
        mass_icon_size = max(6, base_size // 50)
        for mx, mz in info.markers.mass:
            px, py = _map_to_px(mx, mz)
            if "marker_mass" in self._marker_icons:
                _draw_icon("marker_mass", px, py, mass_icon_size)
            else:
                r = max(3, size // 80)
                canvas.create_oval(
                    px - r,
                    py - r,
                    px + r,
                    py + r,
                    fill="#00C800",
                    outline="#006400",
                    width=max(1, size // 300),
                )

        # Hydro markers
        hydro_icon_size = max(8, base_size // 40)
        for mx, mz in info.markers.hydro:
            px, py = _map_to_px(mx, mz)
            if "marker_hydro" in self._marker_icons:
                _draw_icon("marker_hydro", px, py, hydro_icon_size)
            else:
                r = max(4, size // 60)
                canvas.create_oval(
                    px - r,
                    py - r,
                    px + r,
                    py + r,
                    fill="#FFD700",
                    outline="#B8860B",
                    width=max(1, size // 250),
                )

        # Spawn positions
        sa = self._slot_accessor
        active_count = sa.slot_count()
        spawn_icon_size = max(16, base_size // 22)

        # Build spawn→slot mapping
        spawn_occupied: dict[int, int] = {}
        for si in range(active_count):
            spawn_occupied[sa.slot_start_spot(si)] = si

        for i, (_name, mx, mz) in enumerate(info.markers.armies):
            px, py = _map_to_px(mx, mz)
            slot_idx = spawn_occupied.get(i)
            is_occupied = slot_idx is not None and slot_idx < active_count

            if is_occupied and slot_idx is not None:
                color = sa.slot_color_hex(slot_idx)
                team_num = sa.slot_team_label(slot_idx)
            else:
                color = "#444444"
                team_num = ""

            is_hovered = i == self._hover_spawn

            # Hover halo
            if is_hovered:
                halo_r = spawn_icon_size // 2 + 5
                canvas.create_oval(
                    px - halo_r,
                    py - halo_r,
                    px + halo_r,
                    py + halo_r,
                    fill="",
                    outline=color if is_occupied else "#AAAAAA",
                    width=2,
                )

            # Selection ring (human = slot 0)
            if is_occupied and slot_idx == 0:
                sel_r = spawn_icon_size // 2 + 3
                canvas.create_oval(
                    px - sel_r,
                    py - sel_r,
                    px + sel_r,
                    py + sel_r,
                    fill="",
                    outline="#FFFFFF",
                    width=2,
                )

            # Tinted commander icon
            if "marker_commander" in self._marker_icons:
                tinted = self._get_tinted_icon("marker_commander", spawn_icon_size, color)
                if tinted is not None:
                    tk_img = ImageTk.PhotoImage(tinted)
                    canvas.create_image(px, py, image=tk_img)
                    self._marker_tk_cache.append(tk_img)
            else:
                r = spawn_icon_size // 2
                canvas.create_oval(
                    px - r,
                    py - r,
                    px + r,
                    py + r,
                    fill=color,
                    outline="#000000",
                    width=2,
                )

            # Team label
            if team_num:
                r = spawn_icon_size // 2 + 2
                font_size = max(8, base_size // 50)
                canvas.create_text(
                    px + r,
                    py - r,
                    text=team_num,
                    fill="#FFFFFF",
                    font=("Segoe UI", font_size, "bold"),
                )

    def invalidate_tint_cache(self) -> None:
        """Clear tinted icon cache (call when colors change)."""
        self._tinted_icon_cache.clear()

    # ------------------------------------------------------------------
    # Icon loading / tinting
    # ------------------------------------------------------------------

    def _load_marker_icons(self) -> None:
        """Load map marker icon PNGs from the icons directory."""
        if not _PIL_AVAILABLE:
            return
        icons = _icons_dir()
        for name in ("marker_mass", "marker_hydro", "marker_commander"):
            path = icons / f"{name}.png"
            if path.exists():
                try:
                    self._marker_icons[name] = PilImage.open(path).convert("RGBA")
                except Exception as exc:
                    logger.debug("Failed to load icon %s: %s", name, exc)

    def _get_tinted_icon(self, icon_key: str, icon_size: int, tint: str) -> Any:
        """Get a tinted icon from cache, or create and cache it."""
        cache_key = (icon_key, icon_size, tint)
        cached = self._tinted_icon_cache.get(cache_key)
        if cached is not None:
            return cached
        raw = self._marker_icons.get(icon_key)
        if raw is None:
            return None
        scaled = raw.resize(
            (icon_size, icon_size),
            PilImage.BILINEAR,  # type: ignore[attr-defined]
        )
        r_c = int(tint[1:3], 16)
        g_c = int(tint[3:5], 16)
        b_c = int(tint[5:7], 16)
        pixels = scaled.load()
        for yi in range(icon_size):
            for xi in range(icon_size):
                r, g, b, a = pixels[xi, yi]
                if a > 0 and (r + g + b) > 180:
                    pixels[xi, yi] = (r_c, g_c, b_c, a)
        self._tinted_icon_cache[cache_key] = scaled
        return scaled

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_resize(self, _event: Any) -> None:
        if self._canvas_redraw_id is not None:
            self._cancel(self._canvas_redraw_id)
        self._canvas_redraw_id = self._after(50, self.redraw)

    def _on_scroll(self, event: Any) -> None:
        old_zoom = self._zoom
        if event.delta > 0:
            self._zoom = min(4.0, self._zoom * 1.15)
        else:
            self._zoom = max(1.0, self._zoom / 1.15)

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        mx_rel = event.x - cw / 2
        my_rel = event.y - ch / 2
        scale = self._zoom / old_zoom
        self._pan_x = mx_rel - scale * (mx_rel - self._pan_x)
        self._pan_y = my_rel - scale * (my_rel - self._pan_y)
        self._clamp_pan()
        if self._scroll_redraw_id is not None:
            self._cancel(self._scroll_redraw_id)
        self._scroll_redraw_id = self._after(16, self.redraw)

    def _on_drag_start(self, event: Any) -> None:
        self._drag_start = (event.x, event.y)
        self._drag_moved = False
        self._drag_spawn_src = self._hit_test_spawn(event.x, event.y)

    def _on_drag(self, event: Any) -> None:
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        if abs(dx) > DRAG_THRESHOLD or abs(dy) > DRAG_THRESHOLD:
            self._drag_moved = True
        if self._drag_spawn_src >= 0:
            if self._drag_moved:
                self._draw_drag_ghost(event.x, event.y)
            return
        self._drag_start = (event.x, event.y)
        self._pan_x += dx
        self._pan_y += dy
        self._clamp_pan()
        self.redraw()

    def _on_release(self, event: Any) -> None:
        src = self._drag_spawn_src
        if not self._drag_moved:
            hit = self._hit_test_spawn(event.x, event.y)
            if hit >= 0:
                self._on_spawn_select(hit)
        elif src >= 0:
            dst = self._hit_test_spawn(event.x, event.y)
            if dst >= 0 and dst != src:
                self._on_spawn_swap(src, dst)
        self._drag_start = None
        self._drag_moved = False
        self._drag_spawn_src = -1
        self._clear_drag_ghost()

    def _on_motion(self, event: Any) -> None:
        hit = self._hit_test_spawn(event.x, event.y)
        if hit != self._hover_spawn:
            self._hover_spawn = hit
            self.canvas.configure(cursor="hand2" if hit >= 0 else "")
            self.redraw()

    # ------------------------------------------------------------------
    # Hit testing / drag ghost
    # ------------------------------------------------------------------

    def _hit_test_spawn(self, mx: int, my: int) -> int:
        """Return spawn index under (mx, my), or -1 if none."""
        info = self._map_info
        if info is None or info.markers is None or info.map_width == 0:
            return -1
        canvas = self.canvas
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        base_size = min(cw, ch)
        size = int(base_size * self._zoom)
        ox = int((cw - size) / 2 + self._pan_x)
        oy = int((ch - size) / 2 + self._pan_y)
        mw = info.map_width
        mh = info.map_height or mw
        spawn_icon_size = max(16, base_size // 22)
        hit_radius = spawn_icon_size // 2 + 4
        for i, (_name, map_x, map_z) in enumerate(info.markers.armies):
            px = ox + int(map_x / mw * size)
            py = oy + int(map_z / mh * size)
            if (mx - px) ** 2 + (my - py) ** 2 <= hit_radius**2:
                return i
        return -1

    def _draw_drag_ghost(self, cx: int, cy: int) -> None:
        """Draw a semi-transparent ghost icon at cursor during spawn drag."""
        canvas = self.canvas
        canvas.delete("drag_ghost")
        icon_size = max(16, min(canvas.winfo_width(), canvas.winfo_height()) // 22)
        r = icon_size // 2
        canvas.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill="",
            outline="#FFFFFF",
            width=2,
            stipple="gray50",
            tags="drag_ghost",
        )
        dst = self._hit_test_spawn(cx, cy)
        if dst >= 0 and dst != self._drag_spawn_src:
            info = self._map_info
            if info and info.markers and info.map_width:
                cw = canvas.winfo_width()
                ch = canvas.winfo_height()
                base_size = min(cw, ch)
                size = int(base_size * self._zoom)
                ox = int((cw - size) / 2 + self._pan_x)
                oy = int((ch - size) / 2 + self._pan_y)
                _name, mx, mz = info.markers.armies[dst]
                px = ox + int(mx / info.map_width * size)
                py = oy + int(mz / (info.map_height or info.map_width) * size)
                halo_r = icon_size // 2 + 6
                canvas.create_oval(
                    px - halo_r,
                    py - halo_r,
                    px + halo_r,
                    py + halo_r,
                    fill="",
                    outline="#00FF00",
                    width=2,
                    tags="drag_ghost",
                )

    def _clear_drag_ghost(self) -> None:
        self.canvas.delete("drag_ghost")

    def _clamp_pan(self) -> None:
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        base_size = min(cw, ch)
        max_pan = base_size * self._zoom / 2
        self._pan_x = max(-max_pan, min(max_pan, self._pan_x))
        self._pan_y = max(-max_pan, min(max_pan, self._pan_y))
