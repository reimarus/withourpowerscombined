import logging
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

try:
    from PIL import Image as PilImage  # type: ignore[import-not-found]

    _PIL_AVAILABLE = True
except ImportError:
    PilImage = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False

from launcher import map_scanner, mods
from launcher.lobby import LobbyCallbacks, LobbyClient, LobbyServer

if TYPE_CHECKING:
    import customtkinter as ctk  # type: ignore[import-untyped,import-not-found]

    BaseApp = ctk.CTk
else:
    try:
        import customtkinter as ctk  # type: ignore[import-untyped]

        BaseApp = ctk.CTk
    except ImportError:
        ctk = None  # type: ignore[assignment]
        BaseApp = object  # type: ignore[misc, no-redef]

from launcher import config, file_transfer, prefs, updater
from launcher.gui.worker import SetupWorker
from launcher.wopc import cmd_launch

logger = logging.getLogger("wopc.gui")

if ctk is not None:
    # Set the default color theme and appearance for the entire application
    ctk.set_appearance_mode("Dark")
    # We'll use the built-in dark-blue theme as a sleek base
    ctk.set_default_color_theme("dark-blue")

# SupCom-inspired color palette — deep space navy + gold
COLOR_BG = "#080C14"  # Deep space black-navy (sidebar, deepest level)
COLOR_PANEL = "#0D1220"  # Dark navy main background
COLOR_MOD_PANEL = "#111827"  # Secondary panel (mod pane, cards)
COLOR_SURFACE = "#162030"  # Card/elevated surface
COLOR_BORDER = "#1E2D42"  # Subtle panel border
COLOR_ACCENT = "#C8A84B"  # Gold — primary interactive
COLOR_ACCENT_HOVER = "#E8C870"  # Gold hover state
COLOR_ACCENT_DIM = "#6B5A28"  # Dimmed gold for decorative lines/dividers
COLOR_READY = "#C8A84B"  # Gold — PLAY MATCH (matches accent)
COLOR_LAUNCH = "#4DC3F5"  # Electric cyan — LAUNCH GAME in lobby
COLOR_WARN = "#FF8C42"  # Orange — warning state
COLOR_DANGER = "#E84855"  # Red — LEAVE / destructive actions
COLOR_TEXT_PRIMARY = "#E8E4D4"  # Warm cream (not cold white)
COLOR_TEXT_MUTED = "#4A5A70"  # Muted navy-grey
COLOR_TEXT_GOLD = "#C8A84B"  # Gold text (headers, section labels)

# SCFA player colors (index 1-8 match engine's color system)
PLAYER_COLORS: list[tuple[str, str]] = [
    ("#FF0000", "Red"),
    ("#0000FF", "Blue"),
    ("#18DAE8", "Teal"),
    ("#DFBF00", "Yellow"),
    ("#FF6600", "Orange"),
    ("#9161FF", "Purple"),
    ("#FF88FF", "Pink"),
    ("#00FF00", "Green"),
]


def _icons_dir() -> Path:
    """Resolve the GUI icons directory (works in dev mode and frozen exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "launcher" / "gui" / "icons"  # type: ignore[attr-defined]
    return Path(__file__).parent / "icons"


class WopcApp(BaseApp):  # type: ignore
    """The main Graphical User Interface for the WOPC Launcher."""

    # UI Widgets
    sidebar: Any
    logo_label: Any
    subtitle_label: Any
    status_scfa: Any
    status_bundled: Any
    status_wopc: Any
    primary_btn: Any
    version_label: Any
    solo_screen: Any
    browser_screen: Any
    lobby_screen: Any
    header_label: Any
    config_panel: Any
    map_scroll: Any
    map_buttons: list[Any]
    map_canvas: Any
    map_preview_name: Any
    log_textbox: Any
    mods_scroll: Any
    mod_checkboxes: dict[str, Any]
    play_summary: Any

    def __init__(self) -> None:
        super().__init__()

        # Lobby networking state
        self._lobby_server: LobbyServer | None = None
        self._lobby_client: LobbyClient | None = None
        self._remote_players: dict[int, dict[str, Any]] = {}
        self._pending_download: dict[str, Any] = {}
        self._beacon_broadcaster: Any = None
        self._beacon_listener: Any = None
        self._relay_client: Any = None
        self._relay_poll_active: bool = False
        self._lan_games: list[Any] = []
        self._internet_games: list[Any] = []
        self._is_hosting: bool = False
        self._current_screen: str = "solo"
        self._log_lines: list[str] = []

        # Map preview state
        self._canvas_image_id: int | None = None
        self._canvas_tk_image: Any = None
        self._current_map_info: map_scanner.MapInfo | None = None
        self._raw_preview: Any = None
        self._canvas_redraw_id: str | None = None
        self._scroll_redraw_id: str | None = None
        self._marker_icons: dict[str, Any] = {}  # raw PIL images
        self._marker_tk_cache: list[Any] = []  # keep refs alive for tk
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._drag_start: tuple[int, int] | None = None
        self._drag_moved: bool = False
        self._drag_spawn_src: int = -1  # spawn being dragged
        self._hover_spawn: int = -1  # index of spawn under cursor
        self._tinted_icon_cache: dict[tuple[str, int, str], Any] = {}
        self._load_marker_icons()

        self.title("WOPC - Match Lobby")
        self._restore_window_size()
        self.minsize(1100, 700)
        self.configure(fg_color=COLOR_BG)
        self._set_window_icon()

        # Configure grid layout (Sidebar | Main Area spanning cols 1-2)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=240)  # Left Sidebar
        self.grid_columnconfigure(1, weight=1)  # Main content area
        self.grid_columnconfigure(2, weight=0)  # Used by solo_screen columnspan

        self._build_sidebar()
        self._build_main_lobby()
        self._build_browser_screen()
        self._build_lobby_screen()
        # Show the correct initial screen
        self._show_screen("solo")

        self._check_installation_status()
        self._bind_hotkeys()

        # Clean up old exe from previous update and check for new version
        updater.cleanup_old_exe()
        self._pending_update: updater.UpdateInfo | None = None
        threading.Thread(target=self._check_for_update, daemon=True).start()

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

    def _set_window_icon(self) -> None:
        """Set the application window icon if it exists."""
        from pathlib import Path

        if getattr(sys, "frozen", False):
            # PyInstaller extracts bundled data to _MEIPASS
            base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        else:
            base_dir = Path(__file__).parent.parent.parent.resolve()

        icon_path = base_dir / "launcher" / "gui" / "wopc.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception as exc:
                logger.warning("Failed to set window icon: %s", exc)

    def _restore_window_size(self) -> None:
        """Restore the last saved window dimensions from user prefs."""
        try:
            parser = prefs.load_prefs()
            w = parser.getint("Window", "width", fallback=1400)
            h = parser.getint("Window", "height", fallback=780)
            # Clamp to reasonable minimums
            w = max(w, 1100)
            h = max(h, 700)
            self.geometry(f"{w}x{h}")
        except Exception:
            self.geometry("1400x780")

    def _save_window_size(self) -> None:
        """Persist current window dimensions to user prefs."""
        try:
            # winfo_width/height return actual rendered size
            w = self.winfo_width()
            h = self.winfo_height()
            if w < 100 or h < 100:
                return  # Window not yet rendered or minimized
            parser = prefs.load_prefs()
            if not parser.has_section("Window"):
                parser.add_section("Window")
            parser.set("Window", "width", str(w))
            parser.set("Window", "height", str(h))
            prefs.save_prefs(parser)
        except Exception:
            pass  # Don't break shutdown over prefs

    def _make_divider(self, parent: Any, color: str = COLOR_ACCENT_DIM) -> Any:
        """Return a thin 1-pixel accent line for use as a section separator."""
        return ctk.CTkFrame(parent, fg_color=color, height=1, corner_radius=0)

    _PREVIEW_MIN: ClassVar[int] = 320
    _LOBBY_PREVIEW_SIZE: ClassVar[int] = 280

    def _update_map_preview(self, info: "map_scanner.MapInfo | None") -> None:
        """Load and display the map preview image and metadata."""
        self._current_map_info = info

        if info is None:
            self._raw_preview = None
            self._redraw_canvas()
            self.map_preview_name.configure(text="No map selected")
            if hasattr(self, "lobby_map_preview_label"):
                self.lobby_map_preview_label.configure(image=None, text="No Preview")
                self.lobby_map_label.configure(text="No map selected")
                self.lobby_map_info.configure(text="")
            return

        # Compact metadata: "Syrtis Major — 4p, 20km"
        parts = [info.display_name]
        if info.max_players:
            parts.append(f"{info.max_players}p")
        if info.size_label and info.size_label != "?":
            parts.append(info.size_label)
        label = f"{parts[0]} — {', '.join(parts[1:])}" if len(parts) > 1 else parts[0]
        self.map_preview_name.configure(text=label)

        # Reset zoom/pan/cache when map changes
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._tinted_icon_cache.clear()
        self._hover_spawn = -1

        # Load raw preview image for canvas rendering
        self._raw_preview = None
        lobby_ctk_img = None
        if _PIL_AVAILABLE and info.preview_path and info.preview_path.exists():
            try:
                self._raw_preview = PilImage.open(info.preview_path).convert("RGB")
                # Lobby preview (separate widget, still uses CTkImage)
                lsz = self._LOBBY_PREVIEW_SIZE
                lobby = self._raw_preview.resize(
                    (lsz, lsz),
                    PilImage.LANCZOS,  # type: ignore[attr-defined]
                )
                lobby_ctk_img = ctk.CTkImage(light_image=lobby, dark_image=lobby, size=(lsz, lsz))
                self._lobby_preview_ctk_image = lobby_ctk_img
            except Exception as exc:
                logger.warning("Failed to load map preview %s: %s", info.preview_path, exc)

        self._redraw_canvas()

        # Update lobby preview widget
        if hasattr(self, "lobby_map_preview_label"):
            if lobby_ctk_img is not None:
                self.lobby_map_preview_label.configure(image=lobby_ctk_img, text="")
            else:
                self.lobby_map_preview_label.configure(image=None, text="No Preview")
            self.lobby_map_label.configure(text=info.display_name)
            detail_parts = []
            if info.max_players:
                detail_parts.append(f"{info.max_players}p")
            if info.size_label and info.size_label != "?":
                detail_parts.append(info.size_label)
            self.lobby_map_info.configure(text=", ".join(detail_parts))

    def _on_canvas_resize(self, event: Any) -> None:
        """Redraw the map canvas when its size changes (throttled)."""
        # Cancel any pending redraw to avoid flickering during resize
        if hasattr(self, "_canvas_redraw_id") and self._canvas_redraw_id is not None:
            self.after_cancel(self._canvas_redraw_id)
        self._canvas_redraw_id = self.after(50, self._redraw_canvas)

    def _on_canvas_scroll(self, event: Any) -> None:
        """Zoom the map canvas toward the mouse position (throttled)."""
        if not hasattr(self, "map_canvas"):
            return
        old_zoom = self._zoom
        if event.delta > 0:
            self._zoom = min(4.0, self._zoom * 1.15)
        else:
            self._zoom = max(1.0, self._zoom / 1.15)

        canvas = self.map_canvas
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        mx_rel = event.x - cw / 2
        my_rel = event.y - ch / 2
        scale = self._zoom / old_zoom
        self._pan_x = mx_rel - scale * (mx_rel - self._pan_x)
        self._pan_y = my_rel - scale * (my_rel - self._pan_y)
        self._clamp_pan()
        # Throttle scroll redraws to avoid lag
        if hasattr(self, "_scroll_redraw_id") and self._scroll_redraw_id is not None:
            self.after_cancel(self._scroll_redraw_id)
        self._scroll_redraw_id = self.after(16, self._redraw_canvas)

    def _on_canvas_drag_start(self, event: Any) -> None:
        """Start panning the map canvas (or spawn drag if clicking a spawn)."""
        self._drag_start = (event.x, event.y)
        self._drag_moved = False
        self._drag_spawn_src = self._hit_test_spawn(event.x, event.y)

    # Minimum pixel distance before a click becomes a drag
    _DRAG_THRESHOLD: ClassVar[int] = 8

    def _on_canvas_drag(self, event: Any) -> None:
        """Pan the map canvas by dragging, or drag a spawn to swap positions."""
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        if abs(dx) > self._DRAG_THRESHOLD or abs(dy) > self._DRAG_THRESHOLD:
            self._drag_moved = True
        # If dragging from a spawn point, draw a ghost icon at cursor position
        if getattr(self, "_drag_spawn_src", -1) >= 0:
            if self._drag_moved:
                self._draw_drag_ghost(event.x, event.y)
            return
        self._drag_start = (event.x, event.y)
        self._pan_x += dx
        self._pan_y += dy
        self._clamp_pan()
        self._redraw_canvas()

    def _on_canvas_release(self, event: Any) -> None:
        """Handle mouse release — click (spawn select), spawn drag-drop, or end pan."""
        src = getattr(self, "_drag_spawn_src", -1)
        if not self._drag_moved:
            self._on_canvas_click(event)
        elif src >= 0:
            # Dragged from a spawn — check if dropped on another spawn
            dst = self._hit_test_spawn(event.x, event.y)
            if dst >= 0 and dst != src:
                self._swap_spawns(src, dst)
        self._drag_start = None
        self._drag_moved = False
        self._drag_spawn_src = -1
        # Clean up drag ghost overlay
        self._clear_drag_ghost()

    def _on_canvas_motion(self, event: Any) -> None:
        """Track mouse hover over spawn positions for halo effect."""
        hit = self._hit_test_spawn(event.x, event.y)
        if hit != self._hover_spawn:
            self._hover_spawn = hit
            canvas = self.map_canvas
            canvas.configure(cursor="hand2" if hit >= 0 else "")
            self._redraw_canvas()

    def _draw_drag_ghost(self, cx: int, cy: int) -> None:
        """Draw a semi-transparent ghost icon at the cursor during spawn drag."""
        canvas = self.map_canvas
        # Remove previous ghost items
        canvas.delete("drag_ghost")
        # Draw ghost commander icon at cursor
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
        # Highlight valid drop targets
        dst = self._hit_test_spawn(cx, cy)
        if dst >= 0 and dst != getattr(self, "_drag_spawn_src", -1):
            info = self._current_map_info
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
        """Remove the drag ghost overlay from the canvas."""
        if hasattr(self, "map_canvas"):
            self.map_canvas.delete("drag_ghost")

    def _hit_test_spawn(self, mx: int, my: int) -> int:
        """Return spawn index under (mx, my), or -1 if none."""
        if not hasattr(self, "map_canvas") or self._current_map_info is None:
            return -1
        info = self._current_map_info
        if info.markers is None or info.map_width == 0:
            return -1
        canvas = self.map_canvas
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

    def _on_canvas_click(self, event: Any) -> None:
        """Handle click on map canvas — select spawn position."""
        hit = self._hit_test_spawn(event.x, event.y)
        if hit >= 0:
            self._select_spawn(hit)

    def _select_spawn(self, spawn_index: int) -> None:
        """Select a spawn position for the human player (slot 0).

        If another player already occupies the target spawn, swap them
        to the human's previous position so no two players share a spawn.
        """
        if not hasattr(self, "player_slots") or not self.player_slots:
            return
        info = self._current_map_info
        if info is None or info.markers is None:
            return
        if spawn_index >= len(info.markers.armies):
            return
        # Find old human spawn and swap with whoever is at the target
        old_spawn = self.player_slots[0].get("start_spot", 0)
        if old_spawn != spawn_index:
            # Check if another slot occupies the target spawn
            for si, slot in enumerate(self.player_slots):
                if si == 0:
                    continue
                if slot.get("start_spot", si) == spawn_index:
                    slot["start_spot"] = old_spawn
                    logger.info("Swapped slot %d to spawn %d", si + 1, old_spawn + 1)
                    break
        self.player_slots[0]["start_spot"] = spawn_index
        logger.info("Player start spot set to %d", spawn_index + 1)
        self._redraw_canvas()

    def _swap_spawns(self, src_spawn: int, dst_spawn: int) -> None:
        """Swap the slot assignments between two spawn positions."""
        if not hasattr(self, "player_slots"):
            return
        # Build current spawn→slot mapping
        spawn_to_slot: dict[int, int] = {}
        for si, slot in enumerate(self.player_slots):
            spawn_to_slot[slot.get("start_spot", si)] = si

        src_slot = spawn_to_slot.get(src_spawn)
        dst_slot = spawn_to_slot.get(dst_spawn)

        # Swap start_spot values on the slot dicts
        if src_slot is not None:
            self.player_slots[src_slot]["start_spot"] = dst_spawn
        if dst_slot is not None:
            self.player_slots[dst_slot]["start_spot"] = src_spawn

        logger.info("Swapped spawn %d ↔ %d", src_spawn + 1, dst_spawn + 1)
        self._redraw_canvas()

    def _clamp_pan(self) -> None:
        """Clamp pan offset to keep the map visible."""
        if not hasattr(self, "map_canvas"):
            return
        canvas = self.map_canvas
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        base_size = min(cw, ch)
        max_pan = base_size * self._zoom / 2
        self._pan_x = max(-max_pan, min(max_pan, self._pan_x))
        self._pan_y = max(-max_pan, min(max_pan, self._pan_y))

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
        # Tint only bright pixels (interior), preserve dark pixels (outline)
        pixels = scaled.load()
        for yi in range(icon_size):
            for xi in range(icon_size):
                r, g, b, a = pixels[xi, yi]
                if a > 0 and (r + g + b) > 180:
                    pixels[xi, yi] = (r_c, g_c, b_c, a)
        self._tinted_icon_cache[cache_key] = scaled
        return scaled

    def _redraw_canvas(self) -> None:
        """Redraw the map preview and marker overlays on the canvas."""
        if not hasattr(self, "map_canvas"):
            return
        canvas = self.map_canvas
        canvas.delete("all")

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        # Square preview with zoom and pan
        base_size = min(cw, ch)
        size = int(base_size * self._zoom)
        ox = int((cw - size) / 2 + self._pan_x)
        oy = int((ch - size) / 2 + self._pan_y)

        if self._raw_preview is not None and _PIL_AVAILABLE:
            from PIL import ImageTk  # type: ignore[import-not-found]

            # Use BILINEAR for fast zoom; LANCZOS only at 1x
            resample = (
                PilImage.LANCZOS if self._zoom == 1.0 else PilImage.BILINEAR  # type: ignore[attr-defined]
            )
            resized = self._raw_preview.resize((size, size), resample)
            self._canvas_tk_image = ImageTk.PhotoImage(resized)
            self._canvas_image_id = canvas.create_image(
                ox, oy, anchor="nw", image=self._canvas_tk_image
            )
        else:
            # Dark placeholder rectangle
            canvas.create_rectangle(ox, oy, ox + size, oy + size, fill=COLOR_BG, outline="")
            canvas.create_text(
                ox + size // 2,
                oy + size // 2,
                text="No Preview",
                fill=COLOR_TEXT_MUTED,
                font=("Segoe UI", 12),
            )
            return

        # Draw marker overlays if available
        info = self._current_map_info
        if info is None or info.markers is None or info.map_width == 0:
            return

        from PIL import ImageTk  # type: ignore[import-not-found]

        mw = info.map_width
        mh = info.map_height or mw  # fallback to square
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

        # Icon sizes based on base_size (screen-space constant, shrink when zooming)
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

        # Hydro points — strategic energy icon, slightly larger
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

        # Army spawn positions — tinted commander icon + hover halo + selection
        slots = self.player_slots if hasattr(self, "player_slots") else []
        active_count = len(slots)
        spawn_icon_size = max(16, base_size // 22)

        # Build spawn-to-slot mapping from start_spot assignments
        spawn_occupied: dict[int, int] = {}  # spawn_index -> slot_index
        for si, slot in enumerate(slots):
            spot = slot.get("start_spot", si)  # default: slot index = spawn index
            spawn_occupied[spot] = si

        for i, (_name, mx, mz) in enumerate(info.markers.armies):
            px, py = _map_to_px(mx, mz)
            slot_idx = spawn_occupied.get(i)
            is_occupied = slot_idx is not None and slot_idx < active_count

            # Use the player's chosen color from their color_var
            if is_occupied and slot_idx is not None:
                slot = slots[slot_idx]
                cvar = slot.get("color_var")
                color = self._color_name_to_hex(cvar.get()) if cvar else "#444444"
                team = slot.get("team_var")
                team_num = team.get() if team and hasattr(team, "get") else "?"
            else:
                color = "#444444"
                team_num = ""

            is_hovered = i == self._hover_spawn

            # Hover halo — glow ring
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

            # Selected spawn — bright ring (human player)
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

            # Tinted commander icon (preserves black outline)
            if "marker_commander" in self._marker_icons:
                tinted = self._get_tinted_icon("marker_commander", spawn_icon_size, color)
                if tinted is not None:
                    tk_img = ImageTk.PhotoImage(tinted)
                    canvas.create_image(px, py, image=tk_img)
                    self._marker_tk_cache.append(tk_img)
            else:
                r = spawn_icon_size // 2
                canvas.create_oval(
                    px - r, py - r, px + r, py + r, fill=color, outline="#000000", width=2
                )

            # Team number label (instead of slot number)
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

    def _bind_hotkeys(self) -> None:
        """Bind global keyboard shortcuts."""
        self.bind("<Return>", lambda e: self._on_primary_click())
        self.bind("<Escape>", lambda e: self.destroy())

    def _show_screen(self, screen: str) -> None:
        """Switch visible screen in the main content area."""
        for s in (self.solo_screen, self.browser_screen, self.lobby_screen):
            s.grid_remove()
        target = {
            "solo": self.solo_screen,
            "browser": self.browser_screen,
            "lobby": self.lobby_screen,
        }[screen]
        if screen == "solo":
            target.grid(row=0, column=1, columnspan=2, sticky="nsew")
        else:
            target.grid(row=0, column=1, sticky="nsew")
        self._current_screen = screen

    def _build_sidebar(self) -> None:
        """Construct the left sidebar navigation and status area."""
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(9, weight=1)

        # --- Logo / Title ---
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="WOPC",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=32, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 0), sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar,
            text="WITH OUR POWERS COMBINED",
            text_color=COLOR_ACCENT_DIM,
            font=ctk.CTkFont(size=9, weight="bold"),
        )
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(2, 10), sticky="w")

        # Gold accent divider below logo
        logo_div = self._make_divider(self.sidebar)
        logo_div.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")

        # --- Status indicators (label + thin progress bar each) ---
        self.status_scfa = ctk.CTkLabel(
            self.sidebar,
            text="◌  SCFA: Checking...",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.status_scfa.grid(row=3, column=0, padx=20, pady=(4, 0), sticky="w")

        self.progress_scfa = ctk.CTkProgressBar(
            self.sidebar,
            height=3,
            width=160,
            progress_color=COLOR_ACCENT,
            fg_color=COLOR_SURFACE,
            corner_radius=2,
        )
        self.progress_scfa.configure(mode="indeterminate")
        self.progress_scfa.grid(row=4, column=0, padx=24, pady=(0, 2), sticky="w")
        self.progress_scfa.start()

        self.status_bundled = ctk.CTkLabel(
            self.sidebar,
            text="◌  Assets: Checking...",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.status_bundled.grid(row=5, column=0, padx=20, pady=(2, 0), sticky="w")

        self.progress_bundled = ctk.CTkProgressBar(
            self.sidebar,
            height=3,
            width=160,
            progress_color=COLOR_ACCENT,
            fg_color=COLOR_SURFACE,
            corner_radius=2,
        )
        self.progress_bundled.configure(mode="indeterminate")
        self.progress_bundled.grid(row=6, column=0, padx=24, pady=(0, 2), sticky="w")
        self.progress_bundled.start()

        self.status_wopc = ctk.CTkLabel(
            self.sidebar,
            text="◌  WOPC: Checking...",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.status_wopc.grid(row=7, column=0, padx=20, pady=(2, 0), sticky="w")

        self.progress_wopc = ctk.CTkProgressBar(
            self.sidebar,
            height=3,
            width=160,
            progress_color=COLOR_ACCENT,
            fg_color=COLOR_SURFACE,
            corner_radius=2,
        )
        self.progress_wopc.configure(mode="indeterminate")
        self.progress_wopc.grid(row=8, column=0, padx=24, pady=(0, 8), sticky="w")
        self.progress_wopc.start()

        # Divider before launch mode
        mode_div = self._make_divider(self.sidebar)
        mode_div.grid(row=9, column=0, padx=16, pady=(0, 10), sticky="ew")

        # --- Launch Mode Selector ---
        self.mode_label = ctk.CTkLabel(
            self.sidebar,
            text="LAUNCH MODE",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.mode_label.grid(row=10, column=0, padx=20, pady=(0, 6), sticky="w")

        # Always start in SOLO mode for consistent startup
        self.mode_var = ctk.StringVar(value="SOLO")
        self.mode_selector = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["SOLO", "MULTIPLAYER"],
            variable=self.mode_var,
            command=self._on_mode_change,
            selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER,
            unselected_color=COLOR_SURFACE,
            unselected_hover_color=COLOR_BORDER,
            fg_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
        )
        self.mode_selector.grid(row=11, column=0, padx=20, pady=(0, 5), sticky="ew")

        # Conditional widgets for multiplayer mode
        self.mode_widgets_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.mode_widgets_frame.grid(row=12, column=0, padx=20, sticky="ew")

        self.port_label = ctk.CTkLabel(
            self.mode_widgets_frame,
            text="Port:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.port_entry = ctk.CTkEntry(self.mode_widgets_frame, width=120, placeholder_text="15000")
        self.port_entry.insert(0, prefs.get_host_port())
        self.port_entry.bind("<FocusOut>", lambda e: prefs.set_host_port(self.port_entry.get()))

        self.address_label = ctk.CTkLabel(
            self.mode_widgets_frame,
            text="Host Address:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.address_entry = ctk.CTkEntry(
            self.mode_widgets_frame, width=180, placeholder_text="192.168.1.50:15000"
        )
        saved_addr = prefs.get_join_address()
        if saved_addr:
            self.address_entry.insert(0, saved_addr)
        self.address_entry.bind(
            "<FocusOut>", lambda e: prefs.set_join_address(self.address_entry.get())
        )

        # Expected Players dropdown (hosting only)
        self.expected_label = ctk.CTkLabel(
            self.mode_widgets_frame,
            text="Expected Players:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        saved_expected = str(prefs.get_expected_humans())
        self.expected_var = ctk.StringVar(value=saved_expected)
        self.expected_menu = ctk.CTkOptionMenu(
            self.mode_widgets_frame,
            values=["2", "3", "4", "5", "6", "7", "8"],
            variable=self.expected_var,
            command=self._on_expected_humans_change,
            width=80,
            height=28,
        )

        self._update_mode_widgets()

        # Play Button (anchored above version)
        self.primary_btn = ctk.CTkButton(
            self.sidebar,
            text="▶  PLAY MATCH",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            fg_color=COLOR_READY,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            corner_radius=4,
            command=self._on_primary_click,
        )
        self.primary_btn.grid(row=13, column=0, padx=20, pady=(10, 6), sticky="ew")

        # Progress bar (hidden until setup runs)
        self.setup_progress = ctk.CTkProgressBar(
            self.sidebar,
            height=6,
            progress_color=COLOR_ACCENT,
            fg_color=COLOR_PANEL,
            corner_radius=3,
        )
        self.setup_progress.set(0)
        # Hidden by default — shown during install
        self.setup_progress_label = ctk.CTkLabel(
            self.sidebar,
            text="",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )

        # Send Logs button
        self.send_logs_btn = ctk.CTkButton(
            self.sidebar,
            text="Send Logs",
            font=ctk.CTkFont(size=11),
            height=26,
            fg_color=COLOR_PANEL,
            hover_color=COLOR_ACCENT_DIM,
            text_color=COLOR_TEXT_MUTED,
            border_width=1,
            border_color=COLOR_TEXT_MUTED,
            corner_radius=4,
            command=self._on_send_logs,
        )
        self.send_logs_btn.grid(row=14, column=0, padx=20, pady=(4, 0), sticky="ew")

        # Version tag
        self.version_label = ctk.CTkLabel(
            self.sidebar,
            text=f"v{config.VERSION}",
            text_color=COLOR_ACCENT_DIM,
            font=ctk.CTkFont(size=11),
        )
        self.version_label.grid(row=15, column=0, padx=20, pady=(0, 20), sticky="w")

    def _build_main_lobby(self) -> None:
        """Construct the central matching routing/configuration area."""
        self.solo_screen = ctk.CTkFrame(self, fg_color="transparent")
        self.solo_screen.grid(row=0, column=1, columnspan=2, sticky="nsew", padx=20, pady=20)
        # Row 0: header, Row 1: config_panel (fills space), Row 2: log/chat
        self.solo_screen.grid_rowconfigure(1, weight=1)
        self.solo_screen.grid_columnconfigure(0, weight=1)

        self.header_label = ctk.CTkLabel(
            self.solo_screen,
            text="GAME CONFIGURATION",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.header_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        header_div = self._make_divider(self.solo_screen)
        header_div.grid(row=0, column=0, sticky="ews", pady=(0, 0))

        # --- Main config panel: 4 columns ---
        # Col 0: Game Options + Mods | Col 1: Player Settings + Players
        # Col 2: Map (hero) | Col 3: Map List
        self.config_panel = ctk.CTkFrame(self.solo_screen, fg_color=COLOR_SURFACE, corner_radius=4)
        self.config_panel.grid(row=1, column=0, sticky="nsew")
        self.config_panel.grid_columnconfigure(0, weight=0, minsize=180)
        self.config_panel.grid_columnconfigure(1, weight=1, minsize=340)
        self.config_panel.grid_columnconfigure(2, weight=4)  # map hero
        self.config_panel.grid_columnconfigure(3, weight=0, minsize=200)
        self.config_panel.grid_rowconfigure(0, weight=1)

        # --- Col 0: Game Options + Mods ---
        self._build_options_column()

        # --- Col 1: Player Settings + Players ---
        self._build_players_column()

        # --- Col 2: Map Preview (hero) ---
        map_frame = ctk.CTkFrame(self.config_panel, fg_color=COLOR_PANEL, corner_radius=4)
        map_frame.grid(row=0, column=2, sticky="nsew", padx=4, pady=6)
        map_frame.grid_columnconfigure(0, weight=1)
        map_frame.grid_rowconfigure(0, weight=1)

        self.map_canvas = tk.Canvas(map_frame, bg=COLOR_BG, highlightthickness=0, cursor="hand2")
        self.map_canvas.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        self.map_canvas.bind("<Configure>", self._on_canvas_resize)
        self.map_canvas.bind("<MouseWheel>", self._on_canvas_scroll)
        self.map_canvas.bind("<ButtonPress-1>", self._on_canvas_drag_start)
        self.map_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.map_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.map_canvas.bind("<Motion>", self._on_canvas_motion)

        self.map_preview_name = ctk.CTkLabel(
            map_frame,
            text="",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.map_preview_name.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="w")

        # --- Col 3: Map List ---
        self._build_map_list_column()

        # --- Log / Chat Window ---
        self.log_chat_frame = ctk.CTkFrame(
            self.solo_screen, fg_color=COLOR_SURFACE, corner_radius=4
        )
        self.log_chat_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.log_chat_frame.grid_columnconfigure(0, weight=1)
        self.log_chat_frame.grid_rowconfigure(0, weight=1)

        self.log_textbox = ctk.CTkTextbox(
            self.log_chat_frame,
            height=80,
            fg_color=COLOR_PANEL,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.log_textbox.grid(row=0, column=0, sticky="ew")
        self.log_textbox.insert("0.0", "Welcome to the WOPC Match Lobby.\n")
        self.log_textbox.configure(state="disabled")

        # Chat input row
        self.chat_input_frame = ctk.CTkFrame(self.log_chat_frame, fg_color="transparent")
        self.chat_input_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.chat_input_frame.grid_columnconfigure(0, weight=1)

        self.chat_entry = ctk.CTkEntry(
            self.chat_input_frame,
            placeholder_text="Type a message...",
            height=28,
        )
        self.chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.chat_entry.bind("<Return>", lambda e: self._send_chat())

        self.chat_send_btn = ctk.CTkButton(
            self.chat_input_frame,
            text="Send",
            width=60,
            height=28,
            command=self._send_chat,
        )
        self.chat_send_btn.grid(row=0, column=1)

    def _build_browser_screen(self) -> None:
        """Build the multiplayer game browser screen."""
        self.browser_screen = ctk.CTkFrame(self, fg_color="transparent")
        # Don't grid it yet — _show_screen handles that

        self.browser_screen.grid_rowconfigure(1, weight=1)
        self.browser_screen.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkLabel(
            self.browser_screen,
            text="FIND A GAME",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Game list (scrollable)
        self.game_list_frame = ctk.CTkScrollableFrame(
            self.browser_screen,
            fg_color=COLOR_SURFACE,
            corner_radius=4,
        )
        self.game_list_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.game_list_frame.grid_columnconfigure(0, weight=1)

        # Empty state label
        self.no_games_label = ctk.CTkLabel(
            self.game_list_frame,
            text="Searching for games on your network and the internet...",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=14),
        )
        self.no_games_label.grid(row=0, column=0, padx=20, pady=40)

        self.game_rows: list[dict[str, Any]] = []

        # Bottom bar
        bottom = ctk.CTkFrame(self.browser_screen, fg_color="transparent")
        bottom.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        bottom.grid_columnconfigure(2, weight=1)

        # Game name entry (host names their game before creating)
        self.game_name_entry = ctk.CTkEntry(
            bottom,
            placeholder_text="Game name (e.g. Friday Night Match)",
            width=250,
            height=44,
        )
        self.game_name_entry.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.create_game_btn = ctk.CTkButton(
            bottom,
            text="▶  CREATE GAME",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=44,
            fg_color=COLOR_READY,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            corner_radius=4,
            command=self._on_create_game,
        )
        self.create_game_btn.grid(row=0, column=1, sticky="w")

        # Refresh button
        self.refresh_browser_btn = ctk.CTkButton(
            bottom,
            text="⟳  Refresh",
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            width=100,
            height=36,
            corner_radius=4,
            command=self._on_refresh_browser,
        )
        self.refresh_browser_btn.grid(row=0, column=3, padx=(0, 8), sticky="e")

        # Direct Connect (collapsed)
        self.direct_connect_toggle = ctk.CTkButton(
            bottom,
            text="\u25b8 Direct Connect",
            fg_color="transparent",
            hover_color=COLOR_SURFACE,
            text_color=COLOR_TEXT_MUTED,
            anchor="e",
            width=140,
            command=self._toggle_direct_connect,
        )
        self.direct_connect_toggle.grid(row=0, column=4, sticky="e")

        self.direct_connect_frame = ctk.CTkFrame(
            self.browser_screen, fg_color=COLOR_SURFACE, corner_radius=4
        )
        # Not gridded initially (collapsed)
        self.direct_connect_frame.grid_columnconfigure(1, weight=1)

        dc_addr_label = ctk.CTkLabel(
            self.direct_connect_frame, text="Host Address:", text_color=COLOR_TEXT_MUTED
        )
        dc_addr_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")

        self.dc_address_entry = ctk.CTkEntry(
            self.direct_connect_frame, placeholder_text="192.168.1.50:15000"
        )
        saved_addr = prefs.get_join_address()
        if saved_addr:
            self.dc_address_entry.insert(0, saved_addr)
        self.dc_address_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.dc_connect_btn = ctk.CTkButton(
            self.direct_connect_frame,
            text="Connect",
            width=80,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            corner_radius=3,
            command=self._on_direct_connect,
        )
        self.dc_connect_btn.grid(row=0, column=2, padx=(5, 10), pady=10)

        self._direct_connect_visible = False

    def _build_lobby_screen(self) -> None:
        """Build the multiplayer lobby room screen."""
        self.lobby_screen = ctk.CTkFrame(self, fg_color="transparent")
        # Don't grid — _show_screen handles it

        self.lobby_screen.grid_rowconfigure(0, weight=2)
        self.lobby_screen.grid_rowconfigure(1, weight=1)
        self.lobby_screen.grid_columnconfigure(0, weight=1)
        self.lobby_screen.grid_columnconfigure(1, weight=1)

        # --- Map Section (top-left) ---
        map_frame = ctk.CTkFrame(self.lobby_screen, fg_color=COLOR_SURFACE, corner_radius=4)
        map_frame.grid(row=0, column=0, padx=(20, 5), pady=(20, 5), sticky="nsew")
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
        _lps = self._LOBBY_PREVIEW_SIZE
        self.lobby_map_preview_label = ctk.CTkLabel(
            map_frame,
            text="No Preview",
            width=_lps,
            height=_lps,
            fg_color=COLOR_PANEL,
            corner_radius=4,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.lobby_map_preview_label.grid(row=1, column=0, padx=10, pady=(6, 4), sticky="n")

        self.lobby_map_label = ctk.CTkLabel(
            map_frame,
            text="No map selected",
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.lobby_map_label.grid(row=2, column=0, padx=10, pady=(5, 0), sticky="w")

        # Map info (type, size, players)
        self.lobby_map_info = ctk.CTkLabel(
            map_frame,
            text="",
            text_color=COLOR_TEXT_MUTED,
        )
        self.lobby_map_info.grid(row=3, column=0, padx=10, pady=5, sticky="nw")

        self.lobby_change_map_btn = ctk.CTkButton(
            map_frame,
            text="Change Map",
            width=100,
            height=28,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            corner_radius=3,
            command=self._on_lobby_change_map,
        )
        self.lobby_change_map_btn.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="w")

        # --- Players Section (top-right) ---
        players_frame = ctk.CTkFrame(self.lobby_screen, fg_color=COLOR_SURFACE, corner_radius=4)
        players_frame.grid(row=0, column=1, padx=(5, 20), pady=(20, 5), sticky="nsew")
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

        self.lobby_add_ai_btn = ctk.CTkButton(
            players_header_frame,
            text="+ Add AI",
            width=70,
            height=24,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=ctk.CTkFont(size=11),
            corner_radius=3,
            command=self._add_lobby_ai_slot,
        )
        self.lobby_add_ai_btn.grid(row=0, column=1, sticky="e")

        self.lobby_slots_scroll = ctk.CTkScrollableFrame(
            players_frame,
            fg_color="transparent",
        )
        self.lobby_slots_scroll.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.lobby_slots_scroll.grid_columnconfigure(1, weight=1)
        self.lobby_player_slots: list[dict[str, Any]] = []

        # --- Options Section (bottom-left) ---
        opts_frame = ctk.CTkFrame(self.lobby_screen, fg_color=COLOR_SURFACE, corner_radius=4)
        opts_frame.grid(row=1, column=0, padx=(20, 5), pady=(5, 5), sticky="nsew")
        opts_frame.grid_columnconfigure(1, weight=1)

        opts_header = ctk.CTkLabel(
            opts_frame,
            text="GAME OPTIONS",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        opts_header.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")

        self.lobby_option_vars: dict[str, Any] = {}
        self.lobby_option_widgets: list[Any] = []

        # Reuse the same option definitions as the solo screen for consistency
        for i, (key, label, values, default) in enumerate(self.GAME_OPTION_DEFS):
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
                command=lambda _val, _key=key: self._on_lobby_option_change(_key),
            )
            menu.grid(row=i + 1, column=1, padx=(5, 10), pady=2, sticky="w")
            self.lobby_option_vars[key] = var
            self.lobby_option_widgets.extend([lbl, menu])

        # Victory description label (below all option rows)
        victory_row = len(self.GAME_OPTION_DEFS) + 1
        self.lobby_victory_desc = ctk.CTkLabel(
            opts_frame,
            text=self.VICTORY_DESCRIPTIONS.get("Demoralization", ""),
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11, slant="italic"),
            wraplength=250,
        )
        self.lobby_victory_desc.grid(
            row=victory_row, column=0, columnspan=2, padx=10, pady=(2, 5), sticky="w"
        )

        def _update_lobby_victory_desc(*_a: Any) -> None:
            desc = self.VICTORY_DESCRIPTIONS.get(self.lobby_option_vars["Victory"].get(), "")
            self.lobby_victory_desc.configure(text=desc)

        self.lobby_option_vars["Victory"].trace_add("write", _update_lobby_victory_desc)

        # --- Chat Section (bottom-right) ---
        chat_frame = ctk.CTkFrame(self.lobby_screen, fg_color=COLOR_SURFACE, corner_radius=4)
        chat_frame.grid(row=1, column=1, padx=(5, 20), pady=(5, 5), sticky="nsew")
        chat_frame.grid_rowconfigure(1, weight=1)
        chat_frame.grid_columnconfigure(0, weight=1)

        chat_header = ctk.CTkLabel(
            chat_frame,
            text="CHAT",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        chat_header.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="nw")

        self.lobby_chat_textbox = ctk.CTkTextbox(
            chat_frame,
            height=100,
            fg_color=COLOR_BG,
            text_color=COLOR_TEXT_MUTED,
            state="disabled",
        )
        self.lobby_chat_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        chat_input_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
        chat_input_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        chat_input_frame.grid_columnconfigure(0, weight=1)

        self.lobby_chat_entry = ctk.CTkEntry(
            chat_input_frame,
            placeholder_text="Type a message...",
        )
        self.lobby_chat_entry.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.lobby_chat_entry.bind("<Return>", lambda e: self._send_lobby_chat())

        lobby_chat_send = ctk.CTkButton(
            chat_input_frame,
            text="Send",
            width=60,
            command=self._send_lobby_chat,
        )
        lobby_chat_send.grid(row=0, column=1)

        # --- Action Bar (bottom, spanning both columns) ---
        action_bar = ctk.CTkFrame(self.lobby_screen, fg_color="transparent")
        action_bar.grid(row=2, column=0, columnspan=2, padx=20, pady=(5, 20), sticky="ew")
        action_bar.grid_columnconfigure(1, weight=1)

        self.lobby_leave_btn = ctk.CTkButton(
            action_bar,
            text="LEAVE",
            width=100,
            height=44,
            fg_color=COLOR_DANGER,
            hover_color="#BF3040",
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=4,
            command=self._on_leave_lobby,
        )
        self.lobby_leave_btn.grid(row=0, column=0, sticky="w")

        self.lobby_launch_btn = ctk.CTkButton(
            action_bar,
            text="▶  LAUNCH GAME",
            width=180,
            height=44,
            fg_color=COLOR_LAUNCH,
            hover_color="#35A8D8",
            text_color=COLOR_BG,
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=4,
            command=self._on_lobby_launch_click,
        )
        self.lobby_launch_btn.grid(row=0, column=2, sticky="e")

    def _build_options_column(self) -> None:
        """Col 0: Game Options + Content Packs + User Mods."""
        col = ctk.CTkFrame(self.config_panel, fg_color="transparent")
        col.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        col.grid_columnconfigure(0, weight=1)
        col.grid_rowconfigure(4, weight=1)  # mods scroll expands

        # Game Options
        ctk.CTkLabel(
            col,
            text="GAME OPTIONS",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        opts_frame = ctk.CTkFrame(col, fg_color="transparent")
        opts_frame.grid(row=1, column=0, sticky="ew")

        self.game_option_vars: dict[str, ctk.StringVar] = {}
        for idx, (key, label, values, default) in enumerate(self.GAME_OPTION_DEFS):
            ctk.CTkLabel(
                opts_frame,
                text=f"{label}:",
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(size=11),
            ).grid(row=idx, column=0, sticky="w", padx=(0, 5), pady=1)
            var = ctk.StringVar(value=default)
            ctk.CTkOptionMenu(
                opts_frame,
                values=values,
                variable=var,
                command=lambda _v, _k=key: self._on_game_option_change(_k),
                width=110,
                height=22,
            ).grid(row=idx, column=1, sticky="w", pady=1)
            self.game_option_vars[key] = var

        # Victory description
        self.solo_victory_desc = ctk.CTkLabel(
            col,
            text=self.VICTORY_DESCRIPTIONS.get("Demoralization", ""),
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=10, slant="italic"),
            wraplength=170,
        )
        self.solo_victory_desc.grid(row=2, column=0, sticky="w", pady=(2, 8))

        def _update_victory(*_a: Any) -> None:
            desc = self.VICTORY_DESCRIPTIONS.get(self.game_option_vars["Victory"].get(), "")
            self.solo_victory_desc.configure(text=desc)

        self.game_option_vars["Victory"].trace_add("write", _update_victory)

        # Mods header
        ctk.CTkLabel(
            col,
            text="MODS",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=3, column=0, sticky="w", pady=(0, 3))

        # Content packs + user mods in one scrollable area
        self.packs_scroll = ctk.CTkScrollableFrame(col, fg_color="transparent", height=60)
        self.packs_scroll.grid(row=4, column=0, sticky="nsew")
        self.pack_checkboxes: dict[str, Any] = {}
        self.mods_scroll = self.packs_scroll  # unified scroll
        self.mod_checkboxes: dict[str, Any] = {}

        self.play_summary = ctk.CTkLabel(
            col,
            text="Active Mods: 0",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=10),
        )
        self.play_summary.grid(row=5, column=0, sticky="w", pady=(3, 0))

    def _build_players_column(self) -> None:
        """Col 1: Player Settings + Player Slots."""
        col = ctk.CTkFrame(self.config_panel, fg_color="transparent")
        col.grid(row=0, column=1, sticky="nsew", padx=5, pady=10)
        col.grid_columnconfigure(0, weight=1)
        col.grid_rowconfigure(3, weight=1)  # slots scroll expands

        # Player Settings
        ctk.CTkLabel(
            col,
            text="PLAYER",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        settings = ctk.CTkFrame(col, fg_color="transparent")
        settings.grid(row=1, column=0, sticky="ew")

        ctk.CTkLabel(
            settings,
            text="Name:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.name_entry = ctk.CTkEntry(settings, width=100, height=22, placeholder_text="Player")
        saved_name = prefs.get_player_name()
        self.name_entry.insert(0, saved_name)
        self.name_entry.bind("<FocusOut>", lambda e: self._on_name_change())
        self.name_entry.bind("<Return>", lambda e: self._on_name_change())
        self.name_entry.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            settings,
            text="Faction:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(3, 0))
        saved_faction = prefs.get_player_faction()
        display_faction = "UEF" if saved_faction == "uef" else saved_faction.capitalize()
        self.faction_var = ctk.StringVar(value=display_faction)
        self.faction_menu = ctk.CTkOptionMenu(
            settings,
            values=["Random", "UEF", "Aeon", "Cybran", "Seraphim"],
            variable=self.faction_var,
            command=self._on_faction_change,
            width=100,
            height=22,
        )
        self.faction_menu.grid(row=1, column=1, sticky="w", pady=(3, 0))

        # Player color — persisted in prefs
        ctk.CTkLabel(
            settings,
            text="Color:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, sticky="w", padx=(0, 5), pady=(3, 0))
        saved_color = prefs.get_player_color()
        initial_color = saved_color if saved_color else PLAYER_COLORS[0][0]
        self.player_color_var = ctk.StringVar(value=initial_color)
        self.player_color_swatch = self._create_color_swatch(settings, self.player_color_var, 2, 1)

        self.minimap_var = ctk.BooleanVar(value=prefs.get_minimap_enabled())
        self.minimap_cb = ctk.CTkCheckBox(
            col,
            text="Show minimap on launch",
            command=self._on_minimap_toggle,
            variable=self.minimap_var,
            font=ctk.CTkFont(size=11),
        )
        self.minimap_cb.grid(row=2, column=0, sticky="w", pady=(5, 8))

        # Player Slots
        self._build_player_slots_in(col, grid_row=3)

    def _build_map_list_column(self) -> None:
        """Col 3: Map search, filters, and scrollable map list."""
        col = ctk.CTkFrame(self.config_panel, fg_color="transparent")
        col.grid(row=0, column=3, sticky="nsew", padx=(5, 10), pady=10)
        col.grid_columnconfigure(0, weight=1)
        col.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            col,
            text="MAP LIST",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        # Filters
        self.filter_frame = ctk.CTkFrame(col, fg_color="transparent")
        self.filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 3))
        self.filter_frame.grid_columnconfigure(0, weight=1)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._apply_map_filters)
        self.search_entry = ctk.CTkEntry(
            self.filter_frame,
            textvariable=self.search_var,
            placeholder_text="Search...",
            height=24,
        )
        self.search_entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 3))

        self.type_var = ctk.StringVar(value="All")
        self.type_menu = ctk.CTkOptionMenu(
            self.filter_frame,
            values=["All", "Skirmish", "Campaign"],
            variable=self.type_var,
            command=self._apply_map_filters,
            width=60,
            height=22,
        )
        self.type_menu.grid(row=1, column=0, padx=(0, 2), sticky="ew")

        self.players_var = ctk.StringVar(value="Any")
        self.players_menu = ctk.CTkOptionMenu(
            self.filter_frame,
            values=["Any"],
            variable=self.players_var,
            command=self._apply_map_filters,
            width=45,
            height=22,
        )
        self.players_menu.grid(row=1, column=1, padx=(0, 2), sticky="ew")

        self.size_var = ctk.StringVar(value="Any")
        self.size_menu = ctk.CTkOptionMenu(
            self.filter_frame,
            values=["Any"],
            variable=self.size_var,
            command=self._apply_map_filters,
            width=45,
            height=22,
        )
        self.size_menu.grid(row=1, column=2, sticky="ew")

        self.map_scroll = ctk.CTkScrollableFrame(col, fg_color="transparent")
        self.map_scroll.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
        self.map_buttons: list[Any] = []

    # ------------------------------------------------------------------
    # Player Slots
    # ------------------------------------------------------------------

    FACTION_NAMES: ClassVar[list[str]] = ["Random", "UEF", "Aeon", "Cybran", "Seraphim"]
    AI_DISPLAY_NAMES: ClassVar[list[str]] = [
        "Easy",
        "Medium",
        "Adaptive",
        "Rush",
        "Turtle",
        "Tech",
        "Random",
    ]
    MAX_SLOTS: ClassVar[int] = 16
    VICTORY_DESCRIPTIONS: ClassVar[dict[str, str]] = {
        "Demoralization": "Destroy 70% of an enemy's units to eliminate them",
        "Supremacy": "Destroy all enemy structures and engineers to win",
        "Assassination": "Kill the enemy Commander (ACU) to eliminate them",
        "Sandbox": "No victory condition \u2014 play until you quit",
    }

    def _build_player_slots_in(self, parent: Any, grid_row: int = 0) -> None:
        """Build the player slots inside the given parent frame."""
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

        self.add_slot_btn = ctk.CTkButton(
            header_row,
            text="+ Add AI",
            width=65,
            height=22,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=ctk.CTkFont(size=11),
            corner_radius=3,
            command=self._add_ai_slot,
        )
        self.add_slot_btn.grid(row=0, column=1, padx=(5, 0))

        self.slots_scroll = ctk.CTkScrollableFrame(slots_frame, fg_color="transparent")
        self.slots_scroll.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        self.slots_scroll.grid_columnconfigure(1, weight=1)

        # Internal slot data: list of dicts
        # Each: {"type": "human"|"ai", "faction_var", "ai_var", "team_var", "widgets": [...]}
        self.player_slots: list[dict[str, Any]] = []

        # Always start with human player in slot 1
        self._add_human_slot()
        # Default: one AI opponent
        self._add_ai_slot()

    def _get_color_names(self) -> list[str]:
        """Return list of color display names."""
        return [name for _, name in PLAYER_COLORS]

    def _next_free_color(self) -> str:
        """Return the next hex color not already taken by another slot."""
        used: set[str] = set()
        for slot in self.player_slots:
            cvar = slot.get("color_var")
            if cvar:
                used.add(cvar.get())
        for hex_val, _name in PLAYER_COLORS:
            if hex_val not in used:
                return hex_val
        # All taken — just return first
        return PLAYER_COLORS[0][0]

    def _on_color_change(self, _val: str) -> None:
        """Broadcast state and redraw map when a color changes."""
        self._tinted_icon_cache.clear()
        # Persist human player's color to prefs so it survives restarts
        if hasattr(self, "player_color_var"):
            hex_color = self.player_color_var.get()
            prefs.set_player_color(hex_color)
            # Update the read-only indicator in the human slot row
            indicator = getattr(self, "_human_color_indicator", None)
            if indicator:
                indicator.configure(bg=hex_color)
        self._broadcast_game_state()
        self._redraw_canvas()

    def _on_team_change(self, _val: str) -> None:
        """Broadcast state and redraw map when a team assignment changes."""
        self._broadcast_game_state()
        self._redraw_canvas()

    @staticmethod
    def _color_name_to_hex(name: str) -> str:
        """Convert a color name or hex value to its hex value."""
        if name.startswith("#"):
            return name
        for hex_val, cname in PLAYER_COLORS:
            if cname == name:
                return hex_val
        return PLAYER_COLORS[0][0]

    def _create_color_swatch(self, parent: Any, color_var: Any, row: int, col: int) -> Any:
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
        hex_color = raw_color if raw_color.startswith("#") else self._color_name_to_hex(raw_color)
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
            self._show_color_popup(swatch, color_var)

        swatch.bind("<Button-1>", _on_swatch_click)

        # Store swatch ref on color_var for updates
        color_var._swatch = swatch  # type: ignore[attr-defined]
        color_var._swatch_size = swatch_size  # type: ignore[attr-defined]
        return swatch

    def _show_color_popup(self, anchor: Any, color_var: Any) -> None:
        """Show an HSV color wheel popup with brightness slider."""
        import colorsys
        import math

        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.configure(bg=COLOR_PANEL)

        # Position near the anchor widget
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 2
        popup.geometry(f"+{x}+{y}")

        wheel_size = 160
        brightness = [1.0]  # mutable container for closure access
        wheel_canvas = tk.Canvas(
            popup,
            width=wheel_size,
            height=wheel_size,
            bg=COLOR_PANEL,
            highlightthickness=0,
        )
        wheel_canvas.grid(row=0, column=0, padx=8, pady=(8, 4))

        # Generate the HSV wheel image
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

        # Preview swatch showing selected color
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
        current_hex = raw_val if raw_val.startswith("#") else self._color_name_to_hex(raw_val)
        preview.create_rectangle(0, 0, 40, 40, fill=current_hex, outline="", tags="prev")
        preview.grid(row=0, column=0, pady=(0, 4))

        # "Apply" button
        def _apply_color() -> None:
            hex_val = preview._chosen_hex  # type: ignore[attr-defined]
            color_var.set(hex_val)
            swatch_ref = getattr(color_var, "_swatch", None)
            if swatch_ref:
                sz = getattr(color_var, "_swatch_size", 22)
                swatch_ref.delete("all")
                swatch_ref.create_rectangle(0, 0, sz, sz, fill=hex_val, outline="")
            self._on_color_change(hex_val)
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

        # Brightness slider
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

        # Close popup when clicking elsewhere
        popup.bind("<FocusOut>", lambda e: popup.destroy())
        popup.focus_set()

    def _next_team(self, slots: list[dict[str, Any]]) -> str:
        """Return the team number string with the fewest players for auto-balance.

        Counts team assignments across the given slot list and returns the
        team ("1"-"4") that has the fewest members. Ties break to the lower
        numbered team.
        """
        counts: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0}
        for slot in slots:
            team = slot.get("team_var")
            if team:
                val = team.get() if hasattr(team, "get") else str(team)
                if val in counts:
                    counts[val] += 1
        return min(counts, key=lambda t: (counts[t], int(t)))

    def _add_human_slot(self) -> None:
        """Add the human player row (always slot 1, cannot be removed)."""
        row = len(self.player_slots)
        widgets: list[Any] = []

        lbl = ctk.CTkLabel(
            self.slots_scroll,
            text="1",
            width=20,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        lbl.grid(row=row, column=0, padx=(0, 5), pady=2)
        widgets.append(lbl)

        player_name = prefs.get_player_name() or "Player"
        type_lbl = ctk.CTkLabel(
            self.slots_scroll,
            text=player_name,
            text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        type_lbl.grid(row=row, column=1, sticky="w", pady=2)
        widgets.append(type_lbl)

        # Faction is controlled by the mod pane's faction selector for human
        faction_lbl = ctk.CTkLabel(
            self.slots_scroll,
            text="(see Player Settings)",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        faction_lbl.grid(row=row, column=2, padx=5, pady=2)
        widgets.append(faction_lbl)

        team_var = ctk.StringVar(value="1")
        team_menu = ctk.CTkOptionMenu(
            self.slots_scroll,
            values=["1", "2", "3", "4"],
            variable=team_var,
            command=self._on_team_change,
            width=50,
            height=24,
        )
        team_menu.grid(row=row, column=3, padx=5, pady=2)
        widgets.append(team_menu)

        # Human color is managed by the Player Settings color picker above
        # Show a small indicator swatch (read-only, matches player_color_var)
        color_indicator = tk.Canvas(
            self.slots_scroll,
            width=22,
            height=22,
            highlightthickness=1,
            highlightbackground=COLOR_TEXT_MUTED,
            bg=self.player_color_var.get(),
        )
        color_indicator.grid(row=row, column=4, padx=5, pady=2)
        widgets.append(color_indicator)
        self._human_color_indicator = color_indicator

        # No remove button for human
        spacer = ctk.CTkLabel(self.slots_scroll, text="", width=24)
        spacer.grid(row=row, column=5, pady=2)
        widgets.append(spacer)

        self.player_slots.append(
            {
                "type": "human",
                "team_var": team_var,
                "color_var": self.player_color_var,
                "widgets": widgets,
            }
        )

    def _first_free_spawn(self) -> int:
        """Return the first unoccupied spawn index, or -1 if all taken."""
        info = self._current_map_info
        if info is None or info.markers is None:
            return -1
        n_armies = len(info.markers.armies)
        occupied: set[int] = set()
        for si, slot in enumerate(self.player_slots):
            occupied.add(slot.get("start_spot", si))
        for i in range(n_armies):
            if i not in occupied:
                return i
        return -1

    def _add_ai_slot(self) -> None:
        """Add an AI opponent slot row."""
        info = self._current_map_info
        max_armies = len(info.markers.armies) if info and info.markers else self.MAX_SLOTS
        if len(self.player_slots) >= min(self.MAX_SLOTS, max_armies):
            return

        # Find first unoccupied spawn for the new slot
        free_spawn = self._first_free_spawn()

        row = len(self.player_slots)
        slot_num = row + 1
        widgets: list[Any] = []

        lbl = ctk.CTkLabel(
            self.slots_scroll,
            text=str(slot_num),
            width=20,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        lbl.grid(row=row, column=0, padx=(0, 5), pady=2)
        widgets.append(lbl)

        # AI difficulty
        ai_var = ctk.StringVar(value="Medium")
        ai_menu = ctk.CTkOptionMenu(
            self.slots_scroll,
            values=self.AI_DISPLAY_NAMES,
            variable=ai_var,
            width=90,
            height=24,
        )
        ai_menu.grid(row=row, column=1, sticky="w", pady=2)
        widgets.append(ai_menu)

        # Faction
        faction_var = ctk.StringVar(value="Random")
        faction_menu = ctk.CTkOptionMenu(
            self.slots_scroll,
            values=self.FACTION_NAMES,
            variable=faction_var,
            width=90,
            height=24,
        )
        faction_menu.grid(row=row, column=2, padx=5, pady=2)
        widgets.append(faction_menu)

        # Team (auto-balanced)
        team_var = ctk.StringVar(value=self._next_team(self.player_slots))
        team_menu = ctk.CTkOptionMenu(
            self.slots_scroll,
            values=["1", "2", "3", "4"],
            variable=team_var,
            command=self._on_team_change,
            width=50,
            height=24,
        )
        team_menu.grid(row=row, column=3, padx=5, pady=2)
        widgets.append(team_menu)

        # Color swatch picker
        color_var = ctk.StringVar(value=self._next_free_color())
        swatch = self._create_color_swatch(self.slots_scroll, color_var, row, 4)
        widgets.append(swatch)

        slot_dict: dict[str, Any] = {
            "type": "ai",
            "ai_var": ai_var,
            "faction_var": faction_var,
            "team_var": team_var,
            "color_var": color_var,
            "widgets": widgets,
        }
        if free_spawn >= 0:
            slot_dict["start_spot"] = free_spawn

        # Remove button — reference the slot dict, not a stale index
        def remove_this(sd: dict[str, Any] = slot_dict) -> None:
            try:
                idx = self.player_slots.index(sd)
            except ValueError:
                return
            self._remove_slot(idx)

        remove_btn = ctk.CTkButton(
            self.slots_scroll,
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

        self.player_slots.append(slot_dict)
        self._broadcast_game_state()
        self._redraw_canvas()

    def _remove_slot(self, index: int) -> None:
        """Remove a player slot and re-layout remaining slots."""
        if index < 1 or index >= len(self.player_slots):
            return  # Can't remove human slot (index 0)

        # Destroy widgets for the removed slot
        slot = self.player_slots.pop(index)
        for w in slot["widgets"]:
            w.destroy()

        # Re-layout all remaining slots
        for i, s in enumerate(self.player_slots):
            for w in s["widgets"]:
                w.grid_configure(row=i)
            # Update slot number label
            s["widgets"][0].configure(text=str(i + 1))
        self._broadcast_game_state()
        self._redraw_canvas()

    # ------------------------------------------------------------------
    # Lobby Player Slots (mirror of solo slots for the lobby screen)
    # ------------------------------------------------------------------

    def _add_lobby_ai_slot(self) -> None:
        """Add an AI opponent slot row in the lobby screen."""
        info = self._current_map_info
        max_armies = len(info.markers.armies) if info and info.markers else self.MAX_SLOTS
        if len(self.lobby_player_slots) >= min(self.MAX_SLOTS, max_armies):
            return

        row = len(self.lobby_player_slots)
        slot_num = row + 1
        widgets: list[Any] = []

        lbl = ctk.CTkLabel(
            self.lobby_slots_scroll,
            text=str(slot_num),
            width=20,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        lbl.grid(row=row, column=0, padx=(0, 5), pady=2)
        widgets.append(lbl)

        # AI difficulty
        ai_var = ctk.StringVar(value="Medium")
        ai_menu = ctk.CTkOptionMenu(
            self.lobby_slots_scroll,
            values=self.AI_DISPLAY_NAMES,
            variable=ai_var,
            width=90,
            height=24,
        )
        ai_menu.grid(row=row, column=1, sticky="w", pady=2)
        widgets.append(ai_menu)

        # Faction
        faction_var = ctk.StringVar(value="Random")
        faction_menu = ctk.CTkOptionMenu(
            self.lobby_slots_scroll,
            values=self.FACTION_NAMES,
            variable=faction_var,
            width=90,
            height=24,
        )
        faction_menu.grid(row=row, column=2, padx=5, pady=2)
        widgets.append(faction_menu)

        # Team (auto-balanced)
        team_var = ctk.StringVar(value=self._next_team(self.lobby_player_slots))
        team_menu = ctk.CTkOptionMenu(
            self.lobby_slots_scroll,
            values=["1", "2", "3", "4"],
            variable=team_var,
            width=50,
            height=24,
        )
        team_menu.grid(row=row, column=3, padx=5, pady=2)
        widgets.append(team_menu)

        # Color selector
        color_var = ctk.StringVar(value=self._next_free_color())
        color_menu = ctk.CTkOptionMenu(
            self.lobby_slots_scroll,
            values=self._get_color_names(),
            variable=color_var,
            command=self._on_color_change,
            width=70,
            height=24,
        )
        color_menu.grid(row=row, column=4, padx=5, pady=2)
        widgets.append(color_menu)

        lobby_slot_dict: dict[str, Any] = {
            "type": "ai",
            "ai_var": ai_var,
            "faction_var": faction_var,
            "team_var": team_var,
            "color_var": color_var,
            "widgets": widgets,
        }

        # Remove button — reference the slot dict, not a stale index
        def remove_this(sd: dict[str, Any] = lobby_slot_dict) -> None:
            try:
                idx = self.lobby_player_slots.index(sd)
            except ValueError:
                return
            self._remove_lobby_slot(idx)

        remove_btn = ctk.CTkButton(
            self.lobby_slots_scroll,
            text="\u2715",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color=COLOR_DANGER,
            text_color=COLOR_TEXT_MUTED,
            command=remove_this,
        )
        remove_btn.grid(row=row, column=5, pady=2)
        widgets.append(remove_btn)

        self.lobby_player_slots.append(lobby_slot_dict)
        self._broadcast_game_state()

    def _remove_lobby_slot(self, index: int) -> None:
        """Remove a player slot from the lobby screen and re-layout remaining slots."""
        if index < 0 or index >= len(self.lobby_player_slots):
            return

        # Destroy widgets for the removed slot
        slot = self.lobby_player_slots.pop(index)
        for w in slot["widgets"]:
            w.destroy()

        # Re-layout all remaining slots
        for i, s in enumerate(self.lobby_player_slots):
            for w in s["widgets"]:
                w.grid_configure(row=i)
            # Update slot number label
            s["widgets"][0].configure(text=str(i + 1))
        self._broadcast_game_state()

    def _get_lobby_ai_opponents(self) -> list[dict[str, Any]]:
        """Collect AI opponent config from the lobby slot UI."""
        opponents: list[dict[str, Any]] = []
        for slot in self.lobby_player_slots:
            if slot.get("type") != "ai":
                continue
            ai_display = slot["ai_var"].get()
            ai_key = ai_display.lower()
            faction = slot["faction_var"].get().lower()
            team = int(slot["team_var"].get())
            color = self._color_name_to_index(slot["color_var"].get())
            opponents.append(
                {
                    "name": f"AI {len(opponents) + 1}: {ai_display}",
                    "faction": faction,
                    "ai": ai_key,
                    "team": team,
                    "color": color,
                }
            )
        return opponents

    def _clear_lobby_player_slots(self) -> None:
        """Destroy all lobby player slot widgets and clear the list."""
        for slot in self.lobby_player_slots:
            for w in slot["widgets"]:
                w.destroy()
        self.lobby_player_slots.clear()

    @staticmethod
    def _color_name_to_index(val: str) -> int:
        """Convert a color name or hex to the nearest 1-based SCFA engine color index."""
        # Direct name match
        for i, (hex_val, cname) in enumerate(PLAYER_COLORS):
            if cname == val or hex_val == val:
                return i + 1
        # Nearest color by RGB distance for arbitrary hex values
        if val.startswith("#") and len(val) == 7:
            r = int(val[1:3], 16)
            g = int(val[3:5], 16)
            b = int(val[5:7], 16)
            best_i, best_d = 0, float("inf")
            for i, (hex_val, _) in enumerate(PLAYER_COLORS):
                pr = int(hex_val[1:3], 16)
                pg = int(hex_val[3:5], 16)
                pb = int(hex_val[5:7], 16)
                d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
                if d < best_d:
                    best_i, best_d = i, d
            return best_i + 1
        return 1

    def get_human_color_index(self) -> int:
        """Return the human player's selected color index (1-based)."""
        if self.player_slots and self.player_slots[0].get("color_var"):
            return self._color_name_to_index(self.player_slots[0]["color_var"].get())
        return 1

    def get_human_start_spot(self) -> int:
        """Return the human player's selected spawn position (1-based)."""
        if self.player_slots:
            return int(self.player_slots[0].get("start_spot", 0)) + 1
        return 1

    def get_human_team(self) -> int:
        """Return the human player's selected team number (engine-format).

        SCFA engine uses Team 1 = no team (FFA), Team 2+ = allied teams.
        The UI shows teams 1-4, so we add 1 to convert: UI 1 → engine 2.
        """
        if self.player_slots and self.player_slots[0].get("team_var"):
            return int(self.player_slots[0]["team_var"].get()) + 1
        return 2

    def get_ai_opponents(self) -> list[dict[str, Any]]:
        """Collect AI opponent config from the slot UI for game_config.py."""
        opponents: list[dict[str, Any]] = []
        for si, slot in enumerate(self.player_slots):
            if slot["type"] != "ai":
                continue
            ai_display = slot["ai_var"].get()
            ai_key = ai_display.lower()
            faction = slot["faction_var"].get().lower()
            team = int(slot["team_var"].get()) + 1  # UI 1-4 → engine 2-5
            color = self._color_name_to_index(slot["color_var"].get())
            start_spot = slot.get("start_spot", si) + 1  # 1-based for engine
            opponents.append(
                {
                    "name": f"AI {len(opponents) + 1}: {ai_display}",
                    "faction": faction,
                    "ai": ai_key,
                    "team": team,
                    "color": color,
                    "start_spot": start_spot,
                }
            )
        return opponents

    # ------------------------------------------------------------------
    # Game Options
    # ------------------------------------------------------------------

    # Option definitions: (key, label, values, default)
    GAME_OPTION_DEFS: ClassVar[list[tuple[str, str, list[str], str]]] = [
        (
            "Victory",
            "Victory",
            ["Demoralization", "Supremacy", "Assassination", "Sandbox"],
            "Demoralization",
        ),
        ("UnitCap", "Unit Cap", ["500", "1000", "1500", "2000", "4000"], "1500"),
        ("FogOfWar", "Fog of War", ["Explored", "Unexplored", "None"], "Explored"),
        ("GameSpeed", "Game Speed", ["Normal", "Fast", "Adjustable"], "Normal"),
        ("Share", "Share", ["FullShare", "ShareUntilDeath"], "FullShare"),
    ]

    # _build_game_options and _build_settings_column removed — consolidated
    # into _build_options_column and _build_players_column above.

    def _on_game_option_change(self, key: str) -> None:
        """Broadcast state when a game option changes (host only)."""
        self._broadcast_game_state()

    def get_game_options(self) -> dict[str, str]:
        """Collect game options from the UI for game_config.py."""
        opts: dict[str, str] = {}
        for key, var in self.game_option_vars.items():
            val = var.get()
            # Normalize display names to engine values
            if key == "FogOfWar":
                val = {"Explored": "explored", "Unexplored": "unexplored", "None": "none"}.get(
                    val, val.lower()
                )
            elif key == "Victory":
                val = {
                    "Demoralization": "demoralization",
                    "Supremacy": "domination",
                    "Assassination": "eradication",
                    "Sandbox": "sandbox",
                }.get(val, val.lower())
            elif key == "GameSpeed":
                val = val.lower()
            opts[key] = val
        return opts

    def _refresh_mods_list(self) -> None:
        """Read available mods and content packs from disk and update the UI."""
        # --- Content Packs ---
        for cb in self.pack_checkboxes.values():
            cb.destroy()
        self.pack_checkboxes.clear()

        toggleable = mods.get_toggleable_scds()
        enabled_packs = mods.get_enabled_packs()

        for idx, scd_name in enumerate(toggleable):
            label = mods.CONTENT_PACK_LABELS.get(scd_name, scd_name)
            scd_path = config.WOPC_GAMEDATA / scd_name
            if scd_path.exists():
                size_mb = scd_path.stat().st_size / 1_048_576
                label = f"{label}  ({size_mb:.0f} MB)"

            is_enabled = scd_name in enabled_packs

            def on_pack_toggle(name=scd_name) -> None:
                cb = self.pack_checkboxes[name]
                mods.set_pack_state(name, bool(cb.get()))
                self._update_play_summary()

            cb = ctk.CTkCheckBox(self.packs_scroll, text=label, command=on_pack_toggle)
            if is_enabled:
                cb.select()
            cb.grid(row=idx, column=0, pady=3, padx=10, sticky="w")
            self.pack_checkboxes[scd_name] = cb

        # --- User Mods ---
        for cb in self.mod_checkboxes.values():
            cb.destroy()
        self.mod_checkboxes.clear()

        user_mods_on_disk = mods.discover_user_mods()
        enabled_uids = mods.get_enabled_user_mod_uids()

        # Offset user mod rows past content packs
        mod_row_offset = len(toggleable) + 1
        for idx, mod_info in enumerate(user_mods_on_disk):
            is_enabled = mod_info.uid in enabled_uids

            def on_toggle(uid=mod_info.uid) -> None:
                cb = self.mod_checkboxes[uid]
                mods.set_user_mod_enabled(uid, bool(cb.get()))
                self._update_play_summary()

            cb = ctk.CTkCheckBox(self.mods_scroll, text=mod_info.name, command=on_toggle)
            if is_enabled:
                cb.select()
            cb.grid(row=mod_row_offset + idx, column=0, pady=3, padx=10, sticky="w")
            self.mod_checkboxes[mod_info.uid] = cb

        self._update_play_summary()

    def _refresh_map_list(self) -> None:
        """Scan the maps directory and cache the list, then apply filters."""
        self._all_maps = getattr(self, "_all_maps", [])
        if not self._all_maps:
            self._all_maps = map_scanner.scan_all_maps()

        # Auto-select the first map if none is set in prefs.
        if self._all_maps and not prefs.get_active_map():
            prefs.set_active_map(self._all_maps[0].folder_name)

        # Build dynamic filter dropdown values from actual map data
        player_counts = sorted({str(m.max_players) for m in self._all_maps if m.max_players > 0})
        self.players_menu.configure(values=["Any", *player_counts])

        sizes = sorted(
            {m.size_label for m in self._all_maps if m.size_label != "?"},
            key=lambda s: map_scanner._SIZE_LABELS.get(
                next((k for k, v in map_scanner._SIZE_LABELS.items() if v == s), 0), s
            ),
        )
        self.size_menu.configure(values=["Any", *sizes])

        self._apply_map_filters()

    def _apply_map_filters(self, *args: Any) -> None:
        """Filter the cached map list and rebuild the UI buttons."""
        for btn in self.map_buttons:
            btn.destroy()
        self.map_buttons.clear()

        if not getattr(self, "_all_maps", None):
            return

        active_map = prefs.get_active_map()
        search_term = self.search_var.get().lower()
        map_type = self.type_var.get()
        players = self.players_var.get()
        size = self.size_var.get()

        filtered_maps = []
        for info in self._all_maps:
            if search_term:
                name_match = search_term in info.display_name.lower()
                folder_match = search_term in info.folder_name.lower()
                if not name_match and not folder_match:
                    continue
            if map_type == "Skirmish" and info.is_campaign:
                continue
            if map_type == "Campaign" and not info.is_campaign:
                continue
            if players != "Any" and str(info.max_players) != players:
                continue
            if size != "Any" and info.size_label != size:
                continue
            filtered_maps.append(info)

        # If active map is filtered out, auto-select the first visible map
        active_in_list = any(m.folder_name == active_map for m in filtered_maps)
        if not active_in_list and filtered_maps:
            active_map = filtered_maps[0].folder_name
            prefs.set_active_map(active_map)

        preview_shown = False
        for idx, info in enumerate(filtered_maps):
            is_active = info.folder_name == active_map

            # Rich label: "Setons Clutch — 8p, 20km"
            parts = [info.display_name]
            if info.max_players:
                parts.append(f"{info.max_players}p")
            if info.size_label != "?":
                parts.append(info.size_label)
            label = f"{parts[0]} — {', '.join(parts[1:])}" if len(parts) > 1 else parts[0]

            def on_select(name=info.folder_name, disp=info.display_name, _info=info) -> None:
                prefs.set_active_map(name)
                for map_btn in self.map_buttons:
                    map_btn.configure(
                        fg_color=COLOR_SURFACE,
                        text_color=COLOR_TEXT_PRIMARY,
                        hover_color=COLOR_BORDER,
                    )
                # Re-highlight selected
                for map_btn in self.map_buttons:
                    if getattr(map_btn, "_wopc_folder", None) == name:
                        map_btn.configure(
                            fg_color=COLOR_ACCENT,
                            text_color=COLOR_BG,
                            hover_color=COLOR_ACCENT_HOVER,
                        )
                self.map_preview_name.configure(text=f"{disp}")
                self._update_map_preview(_info)
                self._broadcast_game_state()

            color = COLOR_ACCENT if is_active else COLOR_SURFACE
            tcolor = COLOR_BG if is_active else COLOR_TEXT_PRIMARY
            hover = COLOR_ACCENT_HOVER if is_active else COLOR_BORDER

            btn = ctk.CTkButton(
                self.map_scroll,
                text=label,
                fg_color=color,
                text_color=tcolor,
                hover_color=hover,
                anchor="w",
                corner_radius=3,
                command=on_select,
            )
            btn._wopc_folder = info.folder_name
            btn.grid(row=idx, column=0, sticky="ew", pady=2)
            self.map_buttons.append(btn)

            if is_active:
                self._update_map_preview(info)
                preview_shown = True

        # If no maps matched filters, clear the preview
        if not filtered_maps and not preview_shown:
            self._update_map_preview(None)

    def _on_name_change(self) -> None:
        """Persist player name and update the human slot label."""
        name = self.name_entry.get() or "Player"
        prefs.set_player_name(name)
        # Update the human slot label (widget index 1 = type/name label)
        if hasattr(self, "player_slots") and self.player_slots:
            self.player_slots[0]["widgets"][1].configure(text=name)

    def _on_faction_change(self, choice: str) -> None:
        """Persist faction preference when dropdown changes."""
        parser = prefs.load_prefs()
        parser.set("Game", "player_faction", choice.lower())
        prefs.save_prefs(parser)

    def _on_minimap_toggle(self) -> None:
        """Persist minimap visibility preference when checkbox is toggled."""
        parser = prefs.load_prefs()
        parser.set("Game", "minimap_enabled", str(self.minimap_var.get()))
        prefs.save_prefs(parser)

    # ------------------------------------------------------------------
    # Launch mode helpers
    # ------------------------------------------------------------------

    _PLAY_LABELS: ClassVar[dict[str, str]] = {
        "SOLO": "PLAY MATCH",
        "MULTIPLAYER": "PLAY MATCH",
    }

    def _on_expected_humans_change(self, value: str) -> None:
        """Persist expected humans preference when dropdown changes."""
        prefs.set_expected_humans(int(value))

    # ------------------------------------------------------------------
    # Lobby networking callbacks
    # ------------------------------------------------------------------

    def _make_lobby_callbacks(self, *, is_host: bool = False) -> LobbyCallbacks:
        """Create callbacks that marshal onto the GUI thread via self.after()."""
        cbs = LobbyCallbacks(
            on_player_joined=lambda pid, name, faction, slot: self.after(
                0, self._on_player_joined, pid, name, faction, slot
            ),
            on_player_left=lambda pid: self.after(0, self._on_player_left, pid),
            on_ready_changed=lambda pid, ready: self.after(0, self._on_ready_changed, pid, ready),
            on_launch=lambda host_port: self.after(0, self._on_lobby_launch, host_port),
            on_connected=lambda: self.after(0, self._on_lobby_connected),
            on_disconnected=lambda reason: self.after(0, self._on_lobby_disconnected, reason),
            on_error=lambda err: self.after(0, self._on_lobby_error, err),
            on_chat_received=lambda sender, text: self.after(
                0, self._on_chat_received, sender, text
            ),
            on_kicked=lambda reason: self.after(0, self._on_kicked, reason),
        )
        if is_host:
            cbs.on_file_request = lambda pid, cat, name: self.after(
                0, self._on_file_request, pid, cat, name
            )
        else:
            cbs.on_state_updated = lambda state: self.after(0, self._on_game_state_received, state)
            cbs.on_file_manifest = lambda cat, name, files: self.after(
                0, self._on_file_manifest, cat, name, files
            )
            cbs.on_file_chunk = lambda cat, path, idx, total, data: self.after(
                0, self._on_file_chunk, cat, path, idx, total, data
            )
            cbs.on_file_complete = lambda cat, name: self.after(
                0, self._on_file_complete, cat, name
            )
        return cbs

    def _on_player_joined(self, player_id: int, name: str, faction: str, slot: int) -> None:
        """TCP callback: add or update remote human in player slots panel."""
        if player_id in self._remote_players:
            # Update existing player (e.g. faction change)
            info = self._remote_players[player_id]
            info["name"] = name
            info["faction"] = faction
            info["slot"] = slot
            if "name_lbl" in info:
                info["name_lbl"].configure(text=name)
            if "faction_lbl" in info:
                info["faction_lbl"].configure(text=faction.capitalize())
            return
        self._add_remote_human_slot(player_id, name, faction, slot)
        self._update_host_button_text()
        self.log(f"Player joined: {name} (slot {slot})")

    def _on_player_left(self, player_id: int) -> None:
        """TCP callback: remove remote human from player slots panel."""
        info = self._remote_players.pop(player_id, None)
        if info:
            for w in info.get("widgets", []):
                w.destroy()
            self._update_host_button_text()
            self.log(f"Player left: {info.get('name', '?')}")

    def _on_ready_changed(self, player_id: int, ready: bool) -> None:
        """TCP callback: update ready indicator for remote player."""
        info = self._remote_players.get(player_id)
        if info and "ready_lbl" in info:
            info["ready"] = ready
            info["ready_lbl"].configure(
                text="✓" if ready else "—",
                text_color=COLOR_READY if ready else COLOR_TEXT_MUTED,
            )

    def _on_lobby_launch(self, host_port: str) -> None:
        """TCP callback (joiner): host says launch — start SCFA in join mode."""
        self.log(f"Host launched! Starting game (host port: {host_port})...")
        # Build join address from the lobby client's host + the game port
        if self._lobby_client:
            join_addr = f"{self._lobby_client.host_address}:{host_port}"
            prefs.set_join_address(join_addr)
            self._lobby_client.disconnect()
            self._lobby_client = None
        # Launch with a small delay to let the host bind the game port first
        if self._current_screen == "lobby":
            self.lobby_launch_btn.configure(text="LAUNCHING...", state="disabled")
        else:
            self.primary_btn.configure(text="LAUNCHING...", state="disabled")

        def _delayed_launch() -> None:
            time.sleep(2)
            ai_opponents = self.get_ai_opponents() if hasattr(self, "player_slots") else None
            game_options = self.get_game_options() if hasattr(self, "game_option_vars") else None
            color = self.get_human_color_index()
            start_spot = self.get_human_start_spot() if hasattr(self, "player_slots") else 1
            team = self.get_human_team() if hasattr(self, "player_slots") else 1
            ret = cmd_launch(
                ai_opponents=ai_opponents,
                game_options=game_options,
                player_color=color,
                player_start_spot=start_spot,
                player_team=team,
                launch_mode="join",
            )
            if ret == 0:
                self.log("Game process started successfully.")
            else:
                self.log("Game failed to launch.")
            self.after(0, lambda: self.primary_btn.configure(text="JOIN GAME", state="normal"))

        threading.Thread(target=_delayed_launch, daemon=True).start()

    def _on_lobby_connected(self) -> None:
        """TCP callback (joiner): connected to host."""
        self.log("Connected to host lobby!")
        if self._current_screen == "lobby":
            self.lobby_launch_btn.configure(text="READY", fg_color=COLOR_ACCENT, state="normal")
        else:
            self.primary_btn.configure(text="READY", fg_color=COLOR_ACCENT)

    def _on_lobby_disconnected(self, reason: str) -> None:
        """TCP callback: connection lost."""
        self.log(f"Disconnected: {reason}")
        self._lobby_client = None
        self._clear_remote_players()
        if self._current_screen == "lobby":
            self._show_screen("browser")
            self._start_beacon_listener()
            self._start_relay_polling()

    def _on_lobby_error(self, error: str) -> None:
        """TCP callback: connection error."""
        self.log(f"Lobby error: {error}")
        self._lobby_client = None
        self._clear_remote_players()
        if self._current_screen == "lobby":
            self._show_screen("browser")
            self._start_beacon_listener()
            self._start_relay_polling()

    # ------------------------------------------------------------------
    # File transfer callbacks
    # ------------------------------------------------------------------

    def _on_file_request(self, player_id: int, category: str, name: str) -> None:
        """Host callback: joiner is requesting files."""
        if category == "map":
            self.log(f"Player requested map: {name} — sending...")
            threading.Thread(
                target=self._stream_map_to_player,
                args=(player_id, name),
                daemon=True,
            ).start()

    def _stream_map_to_player(self, player_id: int, map_folder: str) -> None:
        """Background thread: stream a map's files to a specific joiner."""
        if not self._lobby_server:
            return
        map_dir = file_transfer.find_map_directory(map_folder)
        if not map_dir:
            self.after(0, self.log, f"Cannot find map '{map_folder}' to send!")
            return

        manifest = file_transfer.build_file_manifest(map_dir)
        total_size = file_transfer.total_transfer_size(manifest)
        self.after(
            0,
            self.log,
            f"Sending map '{map_folder}' "
            f"({file_transfer.format_size(total_size)}, {len(manifest)} files)",
        )

        # Send manifest
        self._lobby_server.send_to_player(
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
                self._lobby_server.send_to_player(
                    player_id,
                    {
                        "type": "FileChunk",
                        "category": "map",
                        **chunk,
                    },
                )

        # Send completion
        self._lobby_server.send_to_player(
            player_id,
            {"type": "FileComplete", "category": "map", "name": map_folder},
        )
        self.after(0, self.log, f"Map '{map_folder}' sent to player")

    def _on_file_manifest(self, category: str, name: str, files: list[dict[str, Any]]) -> None:
        """Joiner callback: received file manifest from host."""
        total = file_transfer.total_transfer_size(files)
        self.log(f"Downloading {category} '{name}' ({file_transfer.format_size(total)})...")
        # Store manifest for verification
        self._pending_download = {
            "category": category,
            "name": name,
            "files": {f["path"]: f for f in files},
            "received_files": set(),
        }

    def _on_file_chunk(self, category: str, path: str, index: int, total: int, data: str) -> None:
        """Joiner callback: received a file chunk — write to disk."""
        if category == "map":
            dest_dir = file_transfer.get_map_install_dir() / self._pending_download.get("name", "")
            file_transfer.write_chunk_to_disk(dest_dir, path, index, total, data)
            # Log progress for last chunk of each file
            if index == total - 1:
                dl = self._pending_download
                if dl:
                    dl["received_files"].add(path)
                    done = len(dl["received_files"])
                    expected = len(dl.get("files", {}))
                    self.log(f"  [{done}/{expected}] {path}")

    def _on_file_complete(self, category: str, name: str) -> None:
        """Joiner callback: file transfer complete — verify and refresh."""
        if category == "map":
            dest_dir = file_transfer.get_map_install_dir() / name
            dl = self._pending_download
            ok = True
            if dl and dl.get("files"):
                for rel_path, info in dl["files"].items():
                    if not file_transfer.verify_file(dest_dir, rel_path, info["sha256"]):
                        self.log(f"WARNING: Hash mismatch for {rel_path}!")
                        ok = False
            if ok:
                self.log(f"Map '{name}' downloaded and verified!")
                # Refresh map list
                self._all_maps = map_scanner.scan_all_maps()
            else:
                self.log(f"WARNING: Map '{name}' download had errors!")
            self._pending_download = {}

    def _send_chat(self) -> None:
        """Send a chat message from the solo screen chat input."""
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.chat_entry.delete(0, "end")
        name = self.name_entry.get() or "Player"
        if self._is_hosting and self._lobby_server:
            self._lobby_server.broadcast_chat(name, text)
            self._append_chat(name, text)
        elif self._lobby_client and self._lobby_client.is_connected:
            self._lobby_client.send_chat(text)
        else:
            # Solo mode — just show locally
            self._append_chat(name, text)

    def _append_chat(self, sender: str, text: str) -> None:
        """Append a chat message to the log/chat textbox."""
        self.log(f"[{sender}] {text}")

    def _on_chat_received(self, sender: str, text: str) -> None:
        """TCP callback: chat message received."""
        if self._current_screen == "lobby":
            self._append_lobby_chat(sender, text)
        else:
            self._append_chat(sender, text)

    def _on_kicked(self, reason: str) -> None:
        """TCP callback (joiner): kicked from lobby."""
        self.log(f"Kicked from lobby: {reason}")
        self._lobby_client = None
        self._clear_remote_players()
        if self._current_screen == "lobby":
            self._show_screen("browser")
            self._start_beacon_listener()
            self._start_relay_polling()

    def _kick_player(self, player_id: int) -> None:
        """Host kicks a player from the lobby."""
        if self._lobby_server:
            info = self._remote_players.get(player_id)
            name = info["name"] if info else "?"
            self._lobby_server.kick_player(player_id)
            self.log(f"Kicked player: {name}")

    def _on_game_state_received(self, state: dict[str, Any]) -> None:
        """TCP callback (joiner): full game state from host."""
        # Handle partial player updates
        if "player_update" in state:
            return  # For now, we only care about full state updates

        # Update map display and check if joiner has the map
        if "map_name" in state:
            map_name = state["map_name"]
            map_folder = state.get("map_folder", "")
            if hasattr(self, "header_label"):
                self.header_label.configure(text=f"Map: {map_name}")
            if hasattr(self, "lobby_map_label"):
                self.lobby_map_label.configure(text=map_name)
            # Check if joiner has this map — auto-download if missing
            if map_folder:
                has_map = any(m.folder_name == map_folder for m in getattr(self, "_all_maps", []))
                if not has_map:
                    self.log(f"Map '{map_name}' not found locally — requesting from host...")
                    if self._lobby_client:
                        self._lobby_client.request_file("map", map_folder)

        # Update game options display
        if "game_options" in state:
            for key, val in state["game_options"].items():
                if key in self.game_option_vars:
                    self.game_option_vars[key].set(val)
                if key in getattr(self, "lobby_option_vars", {}):
                    self.lobby_option_vars[key].set(val)

        # Update AI slots display for joiner
        if "ai_slots" in state:
            self._apply_remote_ai_slots(state["ai_slots"])

        # Check content packs — warn about missing ones
        if "content_packs" in state:
            host_packs = state["content_packs"]
            local_packs = mods.get_enabled_packs()
            missing = [p for p in host_packs if p not in local_packs]
            extra = [p for p in local_packs if p not in host_packs]
            if missing:
                names = [mods.CONTENT_PACK_LABELS.get(p, p) for p in missing]
                self.log(f"WARNING: Host has content packs you don't: {', '.join(names)}")
                self.log("Enable them in the Mods panel to avoid desyncs!")
            if extra:
                names = [mods.CONTENT_PACK_LABELS.get(p, p) for p in extra]
                self.log(f"NOTE: You have extra packs not on host: {', '.join(names)}")

        # Update player list
        if "players" in state:
            for p in state["players"]:
                pid = p.get("player_id", 0)
                if pid and pid not in self._remote_players:
                    self._add_remote_human_slot(
                        pid, p["name"], p.get("faction", "random"), p["slot"]
                    )

    # ------------------------------------------------------------------
    # Game state snapshot (host builds this for joiners)
    # ------------------------------------------------------------------

    def _build_game_state(self) -> dict[str, Any] | None:
        """Capture the full game configuration for broadcasting to joiners."""
        if not hasattr(self, "game_option_vars"):
            return None
        active_map = prefs.get_active_map()
        # Find display name for the map
        map_display = active_map
        for m in getattr(self, "_all_maps", []):
            if m.folder_name == active_map:
                map_display = m.display_name
                break

        return {
            "map_folder": active_map,
            "map_name": map_display,
            "game_options": self.get_game_options(),
            "ai_slots": (
                self._get_lobby_ai_opponents()
                if self._current_screen == "lobby"
                else self.get_ai_opponents()
            ),
            "players": self._lobby_server.connected_players if self._lobby_server else [],
            "content_packs": mods.get_enabled_packs(),
        }

    def _validate_before_launch(self) -> list[str]:
        """Check pre-launch conditions. Returns list of error strings (empty = OK)."""
        errors: list[str] = []
        # Check map is selected
        active_map = prefs.get_active_map()
        if not active_map:
            errors.append("No map selected")
        # Check all remote players are ready (multiplayer only)
        not_ready = [
            info["name"] for info in self._remote_players.values() if not info.get("ready", False)
        ]
        if not_ready:
            errors.append(f"{', '.join(not_ready)} not ready")
        # Check for duplicate colors
        used_colors: list[str] = []
        for slot in self.player_slots:
            cvar = slot.get("color_var")
            if cvar:
                used_colors.append(cvar.get())
        dupes = {c for c in used_colors if used_colors.count(c) > 1}
        if dupes:
            errors.append(f"Duplicate player colors: {', '.join(sorted(dupes))}")
        # Check WOPC deployment is intact
        if not (config.WOPC_BIN / config.GAME_EXE).exists():
            errors.append("WOPC not deployed — run Install first")
        # Check manifest exists for multiplayer (warns only, doesn't block)
        manifest_path = config.WOPC_ROOT / "manifest.json"
        if self._remote_players and not manifest_path.exists():
            self.log("TIP: Run 'wopc manifest' to generate file hashes for desync prevention")
        return errors

    def _broadcast_game_state(self) -> None:
        """Send the current game state to all connected joiners."""
        if not self._lobby_server or not self._lobby_server.is_running:
            return
        state = self._build_game_state()
        if state:
            self._lobby_server.broadcast_state(state)

    def _apply_remote_ai_slots(self, ai_slots: list[dict[str, Any]]) -> None:
        """Update the joiner's AI slot display to match host's config."""
        # Determine which scroll area and slot list to use
        if self._current_screen == "lobby":
            scroll = self.lobby_slots_scroll
            slots = self.lobby_player_slots
            # Clear all lobby slots
            self._clear_lobby_player_slots()
        else:
            scroll = self.slots_scroll
            slots = self.player_slots
            # Remove existing AI slots (keep human slot at index 0)
            while len(slots) > 1:
                slot = slots.pop()
                for w in slot["widgets"]:
                    w.destroy()

        # Disable add button for joiners
        if hasattr(self, "add_slot_btn"):
            self.add_slot_btn.configure(state="disabled")
        if hasattr(self, "lobby_add_ai_btn"):
            self.lobby_add_ai_btn.configure(state="disabled")

        # Add read-only rows for each AI the host has configured
        for ai in ai_slots:
            row = len(slots) + len(self._remote_players)
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

            faction_lbl = ctk.CTkLabel(
                scroll,
                text=ai.get("faction", "random").capitalize(),
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(size=11),
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

            # Color indicator
            color_idx = ai.get("color", 0)
            color_hex = (
                PLAYER_COLORS[color_idx - 1][0]
                if 1 <= color_idx <= len(PLAYER_COLORS)
                else COLOR_TEXT_MUTED
            )
            color_lbl = ctk.CTkLabel(
                scroll,
                text="\u25cf",
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

    # ------------------------------------------------------------------
    # Remote player display
    # ------------------------------------------------------------------

    def _add_remote_human_slot(self, player_id: int, name: str, faction: str, slot: int) -> None:
        """Insert a row in player slots for a remote human player."""
        row = len(self.player_slots) + len(self._remote_players)
        widgets: list[Any] = []

        slot_lbl = ctk.CTkLabel(
            self.slots_scroll,
            text=str(slot),
            width=20,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        slot_lbl.grid(row=row, column=0, padx=(0, 5), pady=2)
        widgets.append(slot_lbl)

        name_lbl = ctk.CTkLabel(
            self.slots_scroll,
            text=name,
            text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        name_lbl.grid(row=row, column=1, sticky="w", pady=2)
        widgets.append(name_lbl)

        faction_lbl = ctk.CTkLabel(
            self.slots_scroll,
            text=faction.capitalize(),
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        faction_lbl.grid(row=row, column=2, padx=5, pady=2)
        widgets.append(faction_lbl)

        ready_lbl = ctk.CTkLabel(
            self.slots_scroll,
            text="—",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=50,
        )
        ready_lbl.grid(row=row, column=3, padx=5, pady=2)
        widgets.append(ready_lbl)

        # Color indicator (read-only for remote players)
        color_lbl = ctk.CTkLabel(
            self.slots_scroll,
            text="●",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=14),
            width=70,
        )
        color_lbl.grid(row=row, column=4, padx=5, pady=2)
        widgets.append(color_lbl)

        # Kick button (host only) or spacer
        if self._is_hosting:
            pid_capture = player_id

            def kick_this(pid=pid_capture) -> None:
                self._kick_player(pid)

            kick_btn = ctk.CTkButton(
                self.slots_scroll,
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
            spacer = ctk.CTkLabel(self.slots_scroll, text="", width=24)
            spacer.grid(row=row, column=5, pady=2)
            widgets.append(spacer)

        self._remote_players[player_id] = {
            "name": name,
            "faction": faction,
            "slot": slot,
            "ready": False,
            "widgets": widgets,
            "name_lbl": name_lbl,
            "faction_lbl": faction_lbl,
            "ready_lbl": ready_lbl,
        }

    def _clear_remote_players(self) -> None:
        """Remove all remote player UI rows."""
        for info in self._remote_players.values():
            for w in info.get("widgets", []):
                w.destroy()
        self._remote_players.clear()

    def _update_host_button_text(self) -> None:
        """Update lobby launch button to show connected player count."""
        if not self._is_hosting or not self._lobby_server:
            return
        n_remote = len(self._remote_players)
        expected = int(self.expected_var.get())
        total = 1 + n_remote  # host + connected peers
        if self._current_screen == "lobby":
            if n_remote == 0:
                self.lobby_launch_btn.configure(text="▶  LAUNCH GAME (Waiting...)")
            else:
                self.lobby_launch_btn.configure(text=f"▶  LAUNCH ({total}/{expected} players)")

    # ------------------------------------------------------------------
    # Lobby lifecycle management
    # ------------------------------------------------------------------

    def _start_lobby_server(self) -> None:
        """Start the TCP lobby server when hosting a multiplayer game."""
        if self._lobby_server and self._lobby_server.is_running:
            return
        port = int(self.port_entry.get() or "15000")
        prefs.set_host_port(str(port))
        callbacks = self._make_lobby_callbacks(is_host=True)
        self._lobby_server = LobbyServer(
            port, callbacks, game_state_provider=self._build_game_state
        )
        try:
            self._lobby_server.start()
            self.log(f"Lobby server started on port {port}")
            self._update_host_button_text()
        except OSError as exc:
            self.log(f"Failed to start lobby server: {exc}")
            self._lobby_server = None

    def _stop_lobby_server(self) -> None:
        """Stop the TCP lobby server."""
        if self._lobby_server:
            self._lobby_server.stop()
            self._lobby_server = None
            self._clear_remote_players()
            self.log("Lobby server stopped")

    def _connect_lobby_client(self) -> None:
        """Connect to a host's lobby server when joining a multiplayer game."""
        if self._lobby_client and self._lobby_client.is_connected:
            return
        raw_addr = self.address_entry.get().strip()
        if not raw_addr:
            self.log("ERROR: Enter a host address before joining.")
            return
        # Parse "host:port" or just "host" (default port 15000)
        if ":" in raw_addr:
            host, port_str = raw_addr.rsplit(":", 1)
            port = int(port_str)
        else:
            host = raw_addr
            port = 15000
        prefs.set_join_address(raw_addr)
        name = self.name_entry.get() or "Player"
        faction = self.faction_var.get().lower()
        callbacks = self._make_lobby_callbacks()
        self._lobby_client = LobbyClient(host, port, name, faction, callbacks)
        self._lobby_client.connect()
        self.primary_btn.configure(text="CONNECTING...", state="disabled")
        self.log(f"Connecting to {host}:{port}...")

    def _disconnect_lobby_client(self) -> None:
        """Disconnect from the host's lobby."""
        if self._lobby_client:
            self._lobby_client.disconnect()
            self._lobby_client = None
            self._clear_remote_players()

    def _on_mode_change(self, mode: str) -> None:
        """Respond to the SOLO / MULTIPLAYER segmented button."""
        prefs.set_launch_mode(mode.lower())

        if mode == "SOLO":
            # Stop any active multiplayer
            self._stop_lobby_server()
            self._disconnect_lobby_client()
            self._stop_beacon_listener()
            self._stop_beacon_broadcaster()
            self._stop_relay_polling()
            self._stop_relay_registration()
            self._show_screen("solo")
            self.primary_btn.configure(text="PLAY MATCH", fg_color=COLOR_READY, state="normal")
            self.primary_btn.grid()
        elif mode == "MULTIPLAYER":
            self._show_screen("browser")
            self._start_beacon_listener()
            self._start_relay_polling()
            # Hide the play button in sidebar (actions are in the lobby/browser screens)
            self.primary_btn.grid_remove()

    def _update_mode_widgets(self) -> None:
        """Show/hide conditional inputs for the current launch mode."""
        # Hide all old mode widgets — browser/lobby screens handle everything
        self.port_label.grid_forget()
        self.port_entry.grid_forget()
        self.address_label.grid_forget()
        self.address_entry.grid_forget()
        self.expected_label.grid_forget()
        self.expected_menu.grid_forget()

    def _update_play_summary(self) -> None:
        """Update the label on the play tab showing the active config."""
        total = len(mods.get_active_mod_uids())
        self.play_summary.configure(text=f"Active Mods: {total}")

    def log(self, message: str) -> None:
        """Add a message to the GUI text box."""
        self._log_lines.append(message)

        def _update():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
            logger.info(message)

        self.after(0, _update)

    def _reset_status_progress_bars(self) -> None:
        """Show indeterminate progress bars for all status checks."""
        checks = [
            (self.status_scfa, self.progress_scfa, 3, 4, "SCFA"),
            (self.status_bundled, self.progress_bundled, 5, 6, "Assets"),
            (self.status_wopc, self.progress_wopc, 7, 8, "WOPC"),
        ]
        for label, progress, row_l, row_p, name in checks:
            label.configure(
                text=f"◌  {name}: Checking...",
                text_color=COLOR_TEXT_MUTED,
            )
            top_pad = 4 if row_l == 3 else 2
            label.grid(row=row_l, column=0, padx=20, pady=(top_pad, 0), sticky="w")
            progress.configure(mode="indeterminate")
            bot_pad = 8 if row_p == 8 else 2
            progress.grid(row=row_p, column=0, padx=24, pady=(0, bot_pad), sticky="w")
            progress.start()

    def _check_installation_status(self) -> None:
        """Run status checks with staggered UI updates via after() timers."""
        self._reset_status_progress_bars()
        self.after(300, self._do_check_scfa)

    def _do_check_scfa(self) -> None:
        """Check SCFA installation and schedule next check."""
        try:
            self._scfa_ok = (
                config.SCFA_STEAM.exists() and (config.SCFA_BIN / config.GAME_EXE).exists()
            )
            self.log(f"SCFA path: {config.SCFA_STEAM}")
            self._resolve_status_check(
                self.status_scfa,
                self.progress_scfa,
                ok=self._scfa_ok,
                label_ok="✓  SCFA: Found",
                label_fail="✗  SCFA: Missing",
                color_ok=COLOR_LAUNCH,
                color_fail=COLOR_DANGER,
            )
            self.after(300, self._do_check_assets)
        except Exception:
            import traceback

            err = traceback.format_exc()
            _crash_log = config.WOPC_ROOT / "crash.log"
            _crash_log.parent.mkdir(parents=True, exist_ok=True)
            _crash_log.write_text(err)
            self.log(f"ERROR: {err}")

    def _do_check_assets(self) -> None:
        """Check bundled assets and schedule next check."""
        self._assets_ok = (config.WOPC_ROOT / "gamedata").exists()
        self._resolve_status_check(
            self.status_bundled,
            self.progress_bundled,
            ok=self._assets_ok,
            label_ok="✓  Assets: Ready",
            label_fail="✗  Assets: Not Deployed",
            color_ok=COLOR_LAUNCH,
            color_fail=COLOR_TEXT_MUTED,
        )
        self.after(300, self._do_check_wopc)

    def _do_check_wopc(self) -> None:
        """Check WOPC deployment and finalize."""
        wopc_ok = config.WOPC_BIN.exists() and (config.WOPC_BIN / config.GAME_EXE).exists()
        self._resolve_status_check(
            self.status_wopc,
            self.progress_wopc,
            ok=wopc_ok,
            label_ok="✓  WOPC: Ready",
            label_fail="✗  WOPC: Not Setup",
            color_ok=COLOR_LAUNCH,
            color_fail=COLOR_WARN,
        )
        self._finalize_status(self._scfa_ok, self._assets_ok, wopc_ok)

    def _resolve_status_check(
        self,
        label: Any,
        progress: Any,
        *,
        ok: bool,
        label_ok: str,
        label_fail: str,
        color_ok: str,
        color_fail: str,
    ) -> None:
        """Update a single status label and hide its progress bar."""
        progress.stop()
        progress.grid_forget()
        label.configure(
            text=label_ok if ok else label_fail,
            text_color=color_ok if ok else color_fail,
        )

    def _finalize_status(self, scfa_ok: bool, assets_ok: bool, wopc_ok: bool) -> None:
        """Update primary button and populate lists after all checks complete."""
        if not scfa_ok:
            self.primary_btn.configure(
                text="MISSING GAME FILES",
                state="disabled",
                fg_color=COLOR_TEXT_MUTED,
                text_color=COLOR_BG,
            )
            self.log(
                "ERROR: SCFA not found. Place WOPC-Launcher.exe in the "
                "Supreme Commander Forged Alliance install folder."
            )

        if scfa_ok and not wopc_ok:
            self.log("WOPC not deployed — starting automatic installation...")
            self._start_install()
        elif scfa_ok and wopc_ok:
            mode = self.mode_var.get()
            label = self._PLAY_LABELS.get(mode, "PLAY MATCH")
            self.primary_btn.configure(
                text=f"▶  {label}",
                fg_color=COLOR_READY,
                hover_color=COLOR_ACCENT_HOVER,
                text_color=COLOR_BG,
                state="normal",
            )
            self.log("All systems ready.")

        # Always populate maps and mods regardless of setup status
        self._refresh_mods_list()
        self._refresh_map_list()

    def _on_send_logs(self) -> None:
        """Upload captured log lines to Firebase for remote troubleshooting."""
        if not self._log_lines:
            self.log("No log messages to send.")
            return

        self.send_logs_btn.configure(state="disabled", text="Sending...")
        host_name = prefs.get_player_name()

        def _upload():
            from launcher.relay import RelayClient

            ok = RelayClient.upload_logs(self._log_lines, host_name=host_name)
            self.after(
                0,
                lambda: self._on_send_logs_done(ok),
            )

        threading.Thread(target=_upload, daemon=True).start()

    def _on_send_logs_done(self, success: bool) -> None:
        """Handle log upload result."""
        if success:
            self.log("Logs sent successfully — thank you!")
        else:
            self.log("Failed to send logs. Check your connection.")
        self.send_logs_btn.configure(state="normal", text="Send Logs")

    def _on_primary_click(self) -> None:
        """Handle main button action -- SOLO mode only."""
        btn_text = self.primary_btn.cget("text")

        if "INSTALL" in btn_text or "UPDATE" in btn_text:
            self._start_install()
            return

        play_values = (
            {f"▶  {v}" for v in self._PLAY_LABELS.values()}
            | set(self._PLAY_LABELS.values())
            | {"PLAY MATCH"}
        )
        if btn_text in play_values or btn_text.startswith("▶"):
            self.log("Launching game (solo mode)...")
            threading.Thread(target=self._launch_game, daemon=True).start()

    def _start_install(self) -> None:
        """Kick off the WOPC deployment worker."""
        self.log("Starting installation...")
        self.primary_btn.configure(state="disabled", text="⬇  INSTALLING...")
        # Show progress bar
        self.setup_progress.set(0)
        self.setup_progress.grid(row=16, column=0, padx=20, pady=(2, 0), sticky="ew")
        self.setup_progress_label.configure(text="Preparing...")
        self.setup_progress_label.grid(
            row=17,
            column=0,
            padx=20,
            pady=(2, 0),
            sticky="w",
        )
        # Move version label down
        self.version_label.grid(row=18, column=0, padx=20, pady=(0, 20), sticky="w")
        worker = SetupWorker(
            on_complete=self._on_setup_complete,
            on_log=self.log,
            on_progress=self._on_setup_progress,
        )
        worker.start()

    def _on_setup_progress(self, message: str, step: int, total: int) -> None:
        """Callback from SetupWorker — update progress bar from worker thread."""

        def _update():
            self.setup_progress.set(step / total)
            self.setup_progress_label.configure(text=message)
            self.primary_btn.configure(text=f"⬇  {message}")

        self.after(0, _update)

    def _on_setup_complete(self, success: bool) -> None:
        """Callback executed when the SetupWorker finishes."""

        def _update():
            # Hide progress bar
            self.setup_progress.grid_forget()
            self.setup_progress_label.grid_forget()
            self.version_label.grid(row=15, column=0, padx=20, pady=(0, 20), sticky="w")

            self.primary_btn.configure(state="normal")
            if success:
                self._check_installation_status()
            else:
                self.log("Installation failed. Check logs and retry.")
                self.primary_btn.configure(
                    text="⬇  INSTALL / UPDATE",
                    state="normal",
                    fg_color=COLOR_WARN,
                    hover_color="#CC8F00",
                    text_color=COLOR_BG,
                )

        self.after(0, _update)

    # ------------------------------------------------------------------
    # Self-update
    # ------------------------------------------------------------------

    def _check_for_update(self) -> None:
        """Background thread: check GitHub for a new launcher version."""
        info = updater.check_for_update()
        if info is not None:
            self._pending_update = info
            self.after(0, self._show_update_available)

    def _show_update_available(self) -> None:
        """Show an update badge on the version label."""
        info = self._pending_update
        if info is None:
            return
        size_mb = info.size_bytes / 1e6
        self.version_label.configure(
            text=f"v{config.VERSION}  ⬆ Update v{info.version} ({size_mb:.0f} MB)",
            text_color=COLOR_ACCENT,
            cursor="hand2",
        )
        self.version_label.bind("<Button-1>", lambda e: self._start_update())

    def _start_update(self) -> None:
        """Download and apply the update."""
        info = self._pending_update
        if info is None:
            return
        self.version_label.configure(text="Downloading update...", cursor="")
        self.version_label.unbind("<Button-1>")
        self.log(f"Downloading launcher v{info.version} ...")

        def _do_update():
            def _on_progress(downloaded: int, total: int) -> None:
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    self.after(
                        0,
                        lambda p=pct: self.version_label.configure(
                            text=f"Downloading update... {p}%"
                        ),
                    )

            tmp = updater.download_update(info, progress_cb=_on_progress)
            if tmp is not None:
                self.after(0, lambda: self.log("Update downloaded. Restarting..."))
                self.after(500, lambda: updater.apply_update(tmp))
            else:
                self.after(
                    0,
                    lambda: self.version_label.configure(
                        text=f"v{config.VERSION} (update failed)",
                        text_color=COLOR_DANGER,
                    ),
                )
                self.after(0, lambda: self.log("Update download failed."))

        threading.Thread(target=_do_update, daemon=True).start()

    def _launch_game(self) -> None:
        """Run the game in a background thread (solo mode)."""
        self._persist_widget_values()

        # Validate map selection before launching
        active_map = prefs.get_active_map()
        if not active_map:
            self.log("Cannot launch: no map selected. Pick a map first.")
            return

        ai_opponents = self.get_ai_opponents() if hasattr(self, "player_slots") else None
        game_options = self.get_game_options() if hasattr(self, "game_option_vars") else None
        color = self.get_human_color_index()
        start_spot = self.get_human_start_spot() if hasattr(self, "player_slots") else 1
        team = self.get_human_team() if hasattr(self, "player_slots") else 1

        ret = cmd_launch(
            ai_opponents=ai_opponents,
            game_options=game_options,
            player_color=color,
            player_start_spot=start_spot,
            player_team=team,
            launch_mode="solo",
        )
        if ret == 0:
            self.log("Game process started successfully.")
        else:
            self.log("Game failed to launch.")

    def _launch_game_and_cleanup(self) -> None:
        """Run the game in a background thread (host mode), then stop lobby server."""
        self._persist_widget_values()
        ai_opponents = self.get_ai_opponents() if hasattr(self, "player_slots") else None
        game_options = self.get_game_options() if hasattr(self, "game_option_vars") else None
        color = self.get_human_color_index()
        start_spot = self.get_human_start_spot() if hasattr(self, "player_slots") else 1
        team = self.get_human_team() if hasattr(self, "player_slots") else 1

        ret = cmd_launch(
            ai_opponents=ai_opponents,
            game_options=game_options,
            player_color=color,
            player_start_spot=start_spot,
            player_team=team,
            launch_mode="host",
        )
        if ret == 0:
            self.log("Game process started successfully.")
        else:
            self.log("Game failed to launch.")

        # Give peers a moment to receive the Launch message, then stop server
        time.sleep(3)
        self.after(0, self._stop_relay_registration)
        self.after(0, self._stop_lobby_server)
        self.after(
            0,
            lambda: self.lobby_launch_btn.configure(
                text="▶  LAUNCH GAME", fg_color=COLOR_LAUNCH, state="normal"
            ),
        )

    def _persist_widget_values(self) -> None:
        """Save any unsaved widget values to prefs before launching."""
        if hasattr(self, "port_entry") and self.port_entry.get():
            prefs.set_host_port(self.port_entry.get())
        if hasattr(self, "name_entry"):
            prefs.set_player_name(self.name_entry.get())

    # ------------------------------------------------------------------
    # Multiplayer flow methods
    # ------------------------------------------------------------------

    def _on_create_game(self) -> None:
        """Handle CREATE GAME click on browser screen."""
        self._is_hosting = True
        port = int(prefs.get_host_port() or "15000")
        callbacks = self._make_lobby_callbacks(is_host=True)
        self._lobby_server = LobbyServer(
            port, callbacks, game_state_provider=self._build_game_state
        )
        try:
            self._lobby_server.start()
            self.log(f"Lobby server started on port {port}")
        except OSError as exc:
            self.log(f"Failed to start lobby server: {exc}")
            self._lobby_server = None
            return
        self._start_beacon_broadcaster()
        self._stop_beacon_listener()
        self._stop_relay_polling()
        self._start_relay_registration()
        self._show_screen("lobby")
        self._update_lobby_for_host()

    def _on_direct_connect(self) -> None:
        """Handle Direct Connect button click."""
        raw_addr = self.dc_address_entry.get().strip()
        if not raw_addr:
            self.log("ERROR: Enter a host address.")
            return
        # Parse host:port
        if ":" in raw_addr:
            host, port_str = raw_addr.rsplit(":", 1)
            port = int(port_str)
        else:
            host = raw_addr
            port = 15000
        prefs.set_join_address(raw_addr)
        self._join_game(host, port)

    def _join_game(self, host: str, port: int) -> None:
        """Connect to a host's lobby and switch to lobby screen."""
        self._is_hosting = False
        name = self.name_entry.get() or "Player"
        faction = self.faction_var.get().lower()
        callbacks = self._make_lobby_callbacks()
        self._lobby_client = LobbyClient(host, port, name, faction, callbacks)
        self._lobby_client.connect()
        self._stop_beacon_listener()
        self._stop_relay_polling()
        self._show_screen("lobby")
        self._update_lobby_for_joiner()
        self.lobby_launch_btn.configure(text="CONNECTING...", state="disabled")
        self.log(f"Connecting to {host}:{port}...")

    def _join_discovered_game(self, game: Any) -> None:
        """Join a game discovered via LAN beacon."""
        self._join_game(game.host_ip, game.lobby_port)

    def _on_leave_lobby(self) -> None:
        """Leave the current multiplayer lobby."""
        if self._is_hosting:
            self._stop_beacon_broadcaster()
            self._stop_relay_registration()
            if self._lobby_server:
                self._lobby_server.stop()
                self._lobby_server = None
        else:
            if self._lobby_client:
                self._lobby_client.disconnect()
                self._lobby_client = None
        self._clear_remote_players()
        self._clear_lobby_player_slots()
        self._show_screen("browser")
        self._start_beacon_listener()
        self._start_relay_polling()
        self.log("Left the lobby.")

    def _on_lobby_launch_click(self) -> None:
        """Handle the LAUNCH/READY button in the lobby screen."""
        if self._is_hosting:
            # Host launches
            errors = self._validate_before_launch()
            if errors:
                for err in errors:
                    self.log(f"Cannot launch: {err}")
                return
            n_remote = len(self._remote_players)
            prefs.set_expected_humans(1 + n_remote)
            host_port = prefs.get_host_port()
            if self._lobby_server:
                self._lobby_server.broadcast_launch(host_port)
            self.log(f"Broadcasting launch to {n_remote} peer(s)...")
            self.lobby_launch_btn.configure(text="LAUNCHING...", state="disabled")
            threading.Thread(target=self._launch_game_and_cleanup, daemon=True).start()
        else:
            # Joiner toggles ready
            btn_text = self.lobby_launch_btn.cget("text")
            if btn_text == "READY" and self._lobby_client:
                self._lobby_client.send_ready(True)
                self.lobby_launch_btn.configure(
                    text="UNREADY", fg_color=COLOR_DANGER, hover_color="#BF3040"
                )
            elif btn_text == "UNREADY" and self._lobby_client:
                self._lobby_client.send_ready(False)
                self.lobby_launch_btn.configure(
                    text="READY", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER
                )

    def _on_lobby_change_map(self) -> None:
        """Open map picker dialog for the host in lobby mode."""
        if not getattr(self, "_all_maps", None):
            self._all_maps = map_scanner.scan_all_maps()

        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Map")
        dialog.geometry("400x500")
        dialog.transient(self)
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

            for idx, info in enumerate(self._all_maps):
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
                    self.lobby_map_label.configure(text=disp)
                    self._broadcast_game_state()
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

    def _on_lobby_option_change(self, key: str) -> None:
        """Handle game option change in the lobby screen."""
        if self._is_hosting and self._lobby_server:
            self._broadcast_game_state()

    def _send_lobby_chat(self) -> None:
        """Send a chat message from the lobby screen."""
        text = self.lobby_chat_entry.get().strip()
        if not text:
            return
        self.lobby_chat_entry.delete(0, "end")
        name = self.name_entry.get() or "Player"
        if self._is_hosting and self._lobby_server:
            self._lobby_server.broadcast_chat(name, text)
            self._append_lobby_chat(name, text)
        elif self._lobby_client and self._lobby_client.is_connected:
            self._lobby_client.send_chat(text)
        else:
            self._append_lobby_chat(name, text)

    def _append_lobby_chat(self, sender: str, text: str) -> None:
        """Append a message to the lobby chat textbox."""
        self.lobby_chat_textbox.configure(state="normal")
        self.lobby_chat_textbox.insert("end", f"[{sender}] {text}\n")
        self.lobby_chat_textbox.configure(state="disabled")
        self.lobby_chat_textbox.see("end")

    def _update_lobby_for_host(self) -> None:
        """Configure lobby screen widgets for hosting."""
        self.lobby_change_map_btn.grid()
        self.lobby_add_ai_btn.grid()
        self.lobby_launch_btn.configure(
            text="▶  LAUNCH GAME", fg_color=COLOR_LAUNCH, state="normal"
        )
        # Enable option dropdowns
        for w in self.lobby_option_widgets:
            if hasattr(w, "configure") and isinstance(w, ctk.CTkOptionMenu):
                w.configure(state="normal")
        # Update map label
        active_map = prefs.get_active_map()
        self.lobby_map_label.configure(text=active_map or "No map selected")
        # Initialize lobby player slots with host row + one default AI
        self._clear_lobby_player_slots()
        name = self.name_entry.get() if hasattr(self, "name_entry") else "Player"
        host_lbl = ctk.CTkLabel(
            self.lobby_slots_scroll,
            text=f"Host: {name or 'Player'}",
            text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        host_lbl.grid(row=0, column=0, columnspan=6, padx=(0, 5), pady=2, sticky="w")
        self.lobby_player_slots.append({"type": "host", "widgets": [host_lbl]})
        self._add_lobby_ai_slot()

    def _update_lobby_for_joiner(self) -> None:
        """Configure lobby screen widgets for joining."""
        self.lobby_change_map_btn.grid_remove()
        self.lobby_add_ai_btn.grid_remove()
        self.lobby_launch_btn.configure(text="READY", fg_color=COLOR_ACCENT, state="disabled")
        # Disable option dropdowns (host controls)
        for w in self.lobby_option_widgets:
            if hasattr(w, "configure") and isinstance(w, ctk.CTkOptionMenu):
                w.configure(state="disabled")

    def _toggle_direct_connect(self) -> None:
        """Show/hide the direct connect panel on the browser screen."""
        if self._direct_connect_visible:
            self.direct_connect_frame.grid_remove()
            self.direct_connect_toggle.configure(text="\u25b8 Direct Connect")
        else:
            self.direct_connect_frame.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
            self.direct_connect_toggle.configure(text="\u25be Direct Connect")
        self._direct_connect_visible = not self._direct_connect_visible

    def _refresh_game_browser(self, games: list[Any]) -> None:
        """Update the game browser with discovered games (GUI thread)."""
        # Clear old rows
        for row in self.game_rows:
            for w in row.get("widgets", []):
                w.destroy()
        self.game_rows.clear()

        if not games:
            self.no_games_label.grid(row=0, column=0, padx=20, pady=40)
            return
        self.no_games_label.grid_remove()

        for i, game in enumerate(games):
            row_frame = ctk.CTkFrame(self.game_list_frame, fg_color=COLOR_BG, corner_radius=6)
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
            subtitle = f"{game.host_name}  —  {game.map_name}"
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
                    text="🌐",
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
                command=lambda g=game: self._join_discovered_game(g),
            )
            join_btn.grid(row=0, column=2, rowspan=2, padx=(5, 10), pady=8)
            row_widgets.append(join_btn)

            self.game_rows.append({"widgets": row_widgets})

    # ------------------------------------------------------------------
    # Beacon lifecycle methods
    # ------------------------------------------------------------------

    def _start_beacon_broadcaster(self) -> None:
        """Start broadcasting game presence on the LAN."""
        from launcher.discovery import BeaconBroadcaster

        if self._beacon_broadcaster and self._beacon_broadcaster.is_running:
            return
        port_str = prefs.get_host_port() or "15000"
        self._beacon_broadcaster = BeaconBroadcaster(
            lobby_port=int(port_str),
            state_provider=self._beacon_state,
        )
        self._beacon_broadcaster.start()

    def _stop_beacon_broadcaster(self) -> None:
        """Stop broadcasting game presence."""
        if self._beacon_broadcaster:
            self._beacon_broadcaster.stop()
            self._beacon_broadcaster = None

    def _start_beacon_listener(self) -> None:
        """Start listening for LAN game beacons."""
        from launcher.discovery import BeaconListener

        if self._beacon_listener and self._beacon_listener.is_running:
            return
        self._beacon_listener = BeaconListener(on_update=self._on_games_discovered)
        self._beacon_listener.start()

    def _stop_beacon_listener(self) -> None:
        """Stop listening for LAN game beacons."""
        if self._beacon_listener:
            self._beacon_listener.stop()
            self._beacon_listener = None

    def _beacon_state(self) -> dict[str, Any]:
        """Return fresh game info for the beacon broadcaster."""
        game_name = ""
        if hasattr(self, "game_name_entry"):
            game_name = self.game_name_entry.get().strip()
        return {
            "host_name": self.name_entry.get() or "Player",
            "game_name": game_name,
            "map_name": prefs.get_active_map() or "No map",
            "player_count": 1 + len(self._remote_players),
            "max_players": int(self.expected_var.get()),
        }

    # ------------------------------------------------------------------
    # Internet relay lifecycle methods
    # ------------------------------------------------------------------

    def _start_relay_polling(self) -> None:
        """Start the 5-second internet relay poll loop."""
        if self._relay_poll_active:
            return
        self._relay_poll_active = True
        self._poll_relay_once()

    def _stop_relay_polling(self) -> None:
        """Stop the internet relay poll loop and clear cached results."""
        self._relay_poll_active = False
        self._internet_games = []

    def _poll_relay_once(self) -> None:
        """Fetch internet games once, then reschedule the next poll (GUI thread)."""
        if not self._relay_poll_active:
            return

        def _fetch() -> None:
            from launcher import config
            from launcher.relay import RelayClient

            if not config.RELAY_URL:
                return
            games = RelayClient().fetch_games()
            self.after(0, self._on_internet_games_fetched, games)

        threading.Thread(target=_fetch, daemon=True).start()
        self.after(5000, self._poll_relay_once)

    def _on_internet_games_fetched(self, games: list[Any]) -> None:
        """GUI thread callback: relay fetch completed."""
        self._internet_games = games
        self._merge_and_refresh()

    def _start_relay_registration(self) -> None:
        """Register this hosted game on the internet relay (background thread)."""
        from launcher import config

        if not config.RELAY_URL:
            return

        def _register() -> None:
            from launcher.relay import RelayClient, get_public_ip

            public_ip = get_public_ip()
            if not public_ip:
                logger.warning("Relay registration skipped: could not resolve public IP")
                msg = "Internet relay: could not detect public IP — visible on LAN only."
                self.after(0, lambda m=msg: self.log(m))
                return
            port = int(prefs.get_host_port() or "15000")
            state = self._beacon_state()
            client = RelayClient()
            ok = client.register(
                host_name=state["host_name"],
                map_name=state["map_name"],
                player_count=int(state["player_count"]),
                max_players=int(state["max_players"]),
                lobby_port=port,
                public_ip=public_ip,
                game_name=state.get("game_name", ""),
            )
            if ok:
                client.start_heartbeat(self._beacon_state)
                self._relay_client = client
                self.after(0, lambda: self.log("Registered on internet relay."))
            else:
                self.after(
                    0,
                    lambda: self.log("Internet relay unavailable — visible on LAN only."),
                )

        threading.Thread(target=_register, daemon=True).start()

    def _stop_relay_registration(self) -> None:
        """Deregister from the internet relay and stop heartbeat."""
        client = self._relay_client
        if not client:
            return
        self._relay_client = None
        threading.Thread(target=client.deregister, daemon=True).start()

    def _on_games_discovered(self, games: list[Any]) -> None:
        """Callback from BeaconListener (background thread)."""
        self._lan_games = games
        self.after(0, self._merge_and_refresh)

    def _on_refresh_browser(self) -> None:
        """Handle manual refresh button click — force immediate relay + LAN poll."""
        self.refresh_browser_btn.configure(text="Refreshing...", state="disabled")
        # Clear cached games to force a full refresh
        self._internet_games = []
        self._lan_games = []
        self._refresh_game_browser([])

        def _fetch() -> None:
            from launcher import config
            from launcher.relay import RelayClient

            games: list[Any] = []
            if config.RELAY_URL:
                games = RelayClient().fetch_games()
            self.after(0, self._on_manual_refresh_done, games)

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_manual_refresh_done(self, internet_games: list[Any]) -> None:
        """Callback after manual refresh fetch completes."""
        self._internet_games = internet_games
        self._merge_and_refresh()
        self.refresh_browser_btn.configure(text="⟳  Refresh", state="normal")

    def _merge_and_refresh(self) -> None:
        """Merge LAN + internet game lists and refresh the browser (GUI thread).

        LAN games take priority: if the same host:port appears in both lists,
        the LAN entry is shown (and the internet duplicate dropped).
        """
        seen: set[str] = set()
        merged: list[Any] = []
        for g in self._lan_games:
            key = f"{g.host_ip}:{g.lobby_port}"
            seen.add(key)
            merged.append(g)
        for g in self._internet_games:
            if f"{g.host_ip}:{g.lobby_port}" not in seen:
                merged.append(g)
        self._refresh_game_browser(merged)

    def destroy(self) -> None:
        """Save window size and clean up lobby connections before closing."""
        self._save_window_size()
        self._stop_beacon_broadcaster()
        self._stop_beacon_listener()
        self._stop_relay_polling()
        if self._relay_client:
            self._relay_client.deregister()
            self._relay_client = None
        self._stop_lobby_server()
        self._disconnect_lobby_client()
        super().destroy()


def launch_gui() -> None:
    """Instantiate and run the WOPC graphical application."""
    if ctk is None:
        logger.error("FATAL: customtkinter is not installed. Run 'pip install customtkinter'.")
        sys.exit(1)

    app = WopcApp()
    app.mainloop()
