import contextlib
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

from launcher import config, prefs, updater
from launcher import wopc as wopc_module
from launcher.gui import browser_screen, lobby_screen, slot_widget
from launcher.gui.constants import (
    AI_DISPLAY_NAMES as _AI_NAMES,
)
from launcher.gui.constants import (
    FACTION_NAMES as _FACTIONS,
)
from launcher.gui.constants import (
    GAME_OPTION_DEFS as _GAME_OPT_DEFS,
)
from launcher.gui.constants import (
    MAX_SLOTS as _MAX_SLOTS,
)
from launcher.gui.constants import (
    PLAY_LABELS,
    PLAYER_COLORS,
    PREVIEW_MIN,
    game_options_to_engine,
)
from launcher.gui.constants import (
    VICTORY_DESCRIPTIONS as _VICTORY_DESCS,
)
from launcher.gui.map_canvas import DictSlotAccessor, MapCanvas
from launcher.gui.supcom_frame import SupComFrame
from launcher.gui.worker import SetupWorker
from launcher.wopc import cmd_launch

logger = logging.getLogger("wopc.gui")

if ctk is not None:
    # Set the default color theme and appearance for the entire application
    ctk.set_appearance_mode("Dark")
    # We'll use the built-in dark-blue theme as a sleek base
    ctk.set_default_color_theme("dark-blue")

# Import the shared palette — one source of truth in constants.py
from launcher.gui.constants import (  # noqa: E402
    COLOR_ACCENT,
    COLOR_ACCENT_DIM,
    COLOR_ACCENT_HOVER,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_LAUNCH,
    COLOR_PANEL,
    COLOR_READY,
    COLOR_SURFACE,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_WARN,
)

_UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000  # Re-check for updates every 30 min


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

        # Thread-safe game state cache — network thread reads snapshot only
        self._cached_game_state: dict[str, Any] | None = None
        self._game_state_lock = threading.Lock()
        # Joiner stores the last GameState received from the host
        self._received_game_state: dict[str, Any] | None = None

        # Map preview state (canvas rendering is in MapCanvas)
        self._current_map_info: map_scanner.MapInfo | None = None

        # Global player state — shared across solo and multiplayer screens.
        # Initialized here so both screens always read/write the same vars.
        saved_color = prefs.get_player_color()
        initial_color = saved_color if saved_color else PLAYER_COLORS[0][0]
        self.player_color_var = ctk.StringVar(value=initial_color)
        saved_faction = prefs.get_player_faction()
        display_faction = "UEF" if saved_faction == "uef" else saved_faction.capitalize()
        self.faction_var = ctk.StringVar(value=display_faction)
        # Trace color changes to sync lobby host indicator widget
        self.player_color_var.trace_add("write", self._on_global_color_change)

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

        self.report_callback_exception = self._on_tk_exception
        self._check_installation_status()
        self._bind_hotkeys()

        # Log startup diagnostics for update troubleshooting
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            logger.info("PyInstaller _MEIPASS: %s", meipass)
        logger.info("Executable: %s", sys.executable)

        # Clean up old exe from previous update — defer 5s to let the old
        # process fully release its _MEI temp directory file handles first.
        self.after(5000, updater.cleanup_old_exe)
        self._pending_update: updater.UpdateInfo | None = None
        self._schedule_update_check()

    def _set_window_icon(self) -> None:
        """Set the application window icon (title bar + taskbar)."""

        # Set Windows AppUserModelID so the taskbar shows our icon
        # instead of the default Python interpreter icon.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("wopc.launcher")  # type: ignore[union-attr]
        except Exception:
            pass

        if getattr(sys, "frozen", False):
            base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        else:
            base_dir = Path(__file__).parent.parent.parent.resolve()

        self._icon_path = base_dir / "launcher" / "gui" / "wopc.ico"
        self._icon_photo = None  # prevent GC of PhotoImage

        if self._icon_path.exists():
            try:
                self.iconbitmap(str(self._icon_path))
            except Exception as exc:
                logger.warning("Failed to set iconbitmap: %s", exc)

            # Also set wm_iconphoto for better taskbar coverage
            if _PIL_AVAILABLE:
                try:
                    from PIL import ImageTk

                    img = PilImage.open(self._icon_path)
                    self._icon_photo = ImageTk.PhotoImage(img)
                    self.wm_iconphoto(True, self._icon_photo)
                except Exception as exc:
                    logger.warning("Failed to set wm_iconphoto: %s", exc)

            # CustomTkinter can override the icon during its own init.
            # Re-apply after the event loop settles (200ms and 1000ms).
            self.after(200, self._reapply_icon)
            self.after(1000, self._reapply_icon)

    def _reapply_icon(self) -> None:
        """Re-apply the window icon (deferred to survive CTk overrides)."""
        try:
            if self._icon_path and self._icon_path.exists():
                self.iconbitmap(str(self._icon_path))
            if self._icon_photo:
                self.wm_iconphoto(True, self._icon_photo)
        except Exception:
            pass

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

    _PREVIEW_MIN = PREVIEW_MIN

    def _update_map_preview(self, info: "map_scanner.MapInfo | None") -> None:
        """Load and display the map preview image and metadata."""
        self._current_map_info = info

        if info is None:
            if hasattr(self, "_map_canvas_widget"):
                self._map_canvas_widget.set_map(None)
            self.map_preview_name.configure(text="No map selected")
            if hasattr(self, "_lobby_map_canvas_widget"):
                self._lobby_map_canvas_widget.set_map(None)
            if hasattr(self, "lobby_map_label"):
                self.lobby_map_label.configure(text="No map selected")
            return

        # Compact metadata: "Syrtis Major — 4p, 20km"
        parts = [info.display_name]
        if info.max_players:
            parts.append(f"{info.max_players}p")
        if info.size_label and info.size_label != "?":
            parts.append(info.size_label)
        label = f"{parts[0]} — {', '.join(parts[1:])}" if len(parts) > 1 else parts[0]
        self.map_preview_name.configure(text=label)

        # Load raw preview image for canvas rendering
        raw_preview = None
        if _PIL_AVAILABLE and info.preview_path and info.preview_path.exists():
            try:
                raw_preview = PilImage.open(info.preview_path).convert("RGB")
            except Exception as exc:
                logger.warning("Failed to load map preview %s: %s", info.preview_path, exc)

        # Delegate rendering to MapCanvas
        if hasattr(self, "_map_canvas_widget"):
            # Sync slot accessor before rendering so spawn markers show player
            # colors on initial load (bug #57)
            self._slot_accessor._slots = self.player_slots if hasattr(self, "player_slots") else []
            self._map_canvas_widget.set_map(info, raw_preview)

        # Update lobby map canvas (4-column layout uses a real MapCanvas)
        if hasattr(self, "_lobby_map_canvas_widget"):
            self._lobby_map_canvas_widget.set_map(info, raw_preview)
        if hasattr(self, "lobby_map_label"):
            self.lobby_map_label.configure(text=info.display_name)

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

    def _swap_spawns_by_index(self, src_spawn: int, dst_spawn: int) -> None:
        """Swap the slot assignments between two spawn positions (callback for MapCanvas)."""
        if not hasattr(self, "player_slots"):
            return
        spawn_to_slot: dict[int, int] = {}
        for si, slot in enumerate(self.player_slots):
            spawn_to_slot[slot.get("start_spot", si)] = si
        src_slot = spawn_to_slot.get(src_spawn)
        dst_slot = spawn_to_slot.get(dst_spawn)
        if src_slot is not None:
            self.player_slots[src_slot]["start_spot"] = dst_spawn
        if dst_slot is not None:
            self.player_slots[dst_slot]["start_spot"] = src_spawn
        logger.info("Swapped spawn %d ↔ %d", src_spawn + 1, dst_spawn + 1)
        self._redraw_canvas()

    def _redraw_canvas(self) -> None:
        """Delegate map canvas redraw to the MapCanvas widget."""
        if hasattr(self, "_map_canvas_widget"):
            # Update the slot accessor with current slot data
            self._slot_accessor._slots = self.player_slots if hasattr(self, "player_slots") else []
            self._map_canvas_widget.redraw()

    def _bind_hotkeys(self) -> None:
        """Bind global keyboard shortcuts."""
        # Enter is NOT bound to game launch — too easy to trigger accidentally.
        # The lobby chat entry has its own <Return> binding for sending messages.
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
        if screen in ("solo", "lobby"):
            target.grid(row=0, column=1, columnspan=2, sticky="nsew", padx=20, pady=20)
        else:
            target.grid(row=0, column=1, sticky="nsew")
        self._current_screen = screen

    def _build_sidebar(self) -> None:
        """Construct the left sidebar navigation and status area."""
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(9, weight=1)

        # Thin gold accent line at the very top of the sidebar
        top_accent = ctk.CTkFrame(self.sidebar, height=2, fg_color=COLOR_ACCENT, corner_radius=0)
        top_accent.place(x=0, y=0, relwidth=1)

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
            border_width=1,
            border_color="#D4A030",
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
        from launcher.__version__ import COMMIT_HASH

        _ver_text = f"v{config.VERSION}"
        if COMMIT_HASH:
            _ver_text += f" ({COMMIT_HASH})"
        self.version_label = ctk.CTkLabel(
            self.sidebar,
            text=_ver_text,
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
        self._config_sf = SupComFrame(self.solo_screen, fg_color=COLOR_SURFACE)
        self._config_sf.frame.grid(row=1, column=0, sticky="nsew")
        self.config_panel = self._config_sf.interior
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
        self._map_sf = SupComFrame(self.config_panel, fg_color=COLOR_PANEL)
        self._map_sf.frame.grid(row=0, column=2, sticky="nsew", padx=4, pady=6)
        map_frame = self._map_sf.interior
        map_frame.grid_columnconfigure(0, weight=1)
        map_frame.grid_rowconfigure(0, weight=1)

        self._slot_accessor = DictSlotAccessor([])
        self._map_canvas_widget = MapCanvas(
            parent=map_frame,
            slot_accessor=self._slot_accessor,
            on_spawn_select=self._select_spawn,
            on_spawn_swap=self._swap_spawns_by_index,
            after_fn=self.after,
            cancel_fn=self.after_cancel,
        )
        self.map_canvas = self._map_canvas_widget.canvas

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
        self._log_sf = SupComFrame(self.solo_screen, fg_color=COLOR_SURFACE)
        self._log_sf.frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.log_chat_frame = self._log_sf.interior
        self.log_chat_frame.grid_columnconfigure(0, weight=1)

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
        browser_screen.build_browser_screen(self)

    def _build_lobby_screen(self) -> None:
        lobby_screen.build_lobby_screen(self)

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

        # Mod panel — collapsible categories with content packs + user mods
        from launcher.gui.mod_panel import ModPanel

        self._mod_panel = ModPanel(col, on_change=self._on_mod_change)
        self._mod_panel.grid(row=4, column=0, sticky="nsew")

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
        # Reuse the global faction_var (initialized in __init__)
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
        # Reuse the global player_color_var (initialized in __init__)
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
        self.map_scroll.grid_columnconfigure(0, weight=1)
        self.map_buttons: list[Any] = []

    # ------------------------------------------------------------------
    # Player Slots
    # ------------------------------------------------------------------

    # Constants imported from launcher.gui.constants
    FACTION_NAMES = _FACTIONS
    AI_DISPLAY_NAMES = _AI_NAMES
    MAX_SLOTS = _MAX_SLOTS
    VICTORY_DESCRIPTIONS = _VICTORY_DESCS

    def _build_player_slots_in(self, parent: Any, grid_row: int = 0) -> None:
        """Build the player slots inside the given parent frame."""
        slot_widget.build_player_slots_in(self, parent, grid_row)

    def _get_color_names(self) -> list[str]:
        return slot_widget.get_color_names()

    def _next_free_color(self) -> str:
        return slot_widget.next_free_color(self.player_slots)

    def _on_global_color_change(self, *_args: Any) -> None:
        """Trace callback: sync lobby host color indicator when color changes."""
        hex_color = self.player_color_var.get()
        indicator = getattr(self, "_lobby_host_color_indicator", None)
        if indicator:
            with contextlib.suppress(Exception):
                indicator.configure(bg=hex_color)

    def _on_color_change(self, _val: str) -> None:
        slot_widget.on_color_change(self, _val)

    def _on_team_change(self, _val: str) -> None:
        slot_widget.on_team_change(self, _val)

    @staticmethod
    def _color_name_to_hex(name: str) -> str:
        return slot_widget.color_to_hex(name)

    def _create_color_swatch(self, parent: Any, color_var: Any, row: int, col: int) -> Any:
        return slot_widget.create_color_swatch(self, parent, color_var, row, col)

    def _show_color_popup(self, anchor: Any, color_var: Any) -> None:
        slot_widget.show_color_popup(self, anchor, color_var)

    def _next_team(self, slots: list[dict[str, Any]]) -> str:
        return slot_widget.next_team(slots)

    def _add_human_slot(self) -> None:
        slot_widget.add_human_slot(self)

    def _first_free_spawn(self) -> int:
        return slot_widget.first_free_spawn(self)

    def _add_ai_slot(self) -> None:
        slot_widget.add_ai_slot(self)

    def _add_lobby_ai_slot(self) -> None:
        slot_widget.add_lobby_ai_slot(self)

    def _add_ai_slot_to(
        self,
        parent: Any,
        slot_list: list[dict[str, Any]],
        *,
        use_swatch: bool = True,
        track_spawn: bool = False,
    ) -> None:
        slot_widget.add_ai_slot_to(
            self, parent, slot_list, use_swatch=use_swatch, track_spawn=track_spawn
        )

    def _remove_slot_from(
        self, slot_list: list[dict[str, Any]], index: int, *, redraw: bool = False
    ) -> None:
        slot_widget.remove_slot_from(self, slot_list, index, redraw=redraw)

    def _get_lobby_ai_opponents(self) -> list[dict[str, Any]]:
        return slot_widget.get_ai_opponents_from(self, self.lobby_player_slots)

    def _clear_lobby_player_slots(self) -> None:
        slot_widget.clear_lobby_player_slots(self)

    @staticmethod
    def _color_name_to_index(val: str) -> int:
        return slot_widget.color_to_index(val)

    def get_human_color_index(self) -> int:
        """Return the human player's selected color index (1-based)."""
        if self.player_slots and self.player_slots[0].get("color_var"):
            return slot_widget.color_to_index(self.player_slots[0]["color_var"].get())
        return 1

    def get_human_start_spot(self) -> int:
        """Return the human player's selected spawn position (1-based)."""
        if self.player_slots:
            return int(self.player_slots[0].get("start_spot", 0)) + 1
        return 1

    def get_human_team(self) -> int:
        """Return the human player's team (engine-format: UI + 1)."""
        if self.player_slots and self.player_slots[0].get("team_var"):
            return int(self.player_slots[0]["team_var"].get()) + 1
        return 2

    def get_ai_opponents(self) -> list[dict[str, Any]]:
        """Collect AI opponent config from the solo slot UI for game_config.py."""
        return slot_widget.get_ai_opponents_from(self, self.player_slots, engine_offset=True)

    def _get_ai_opponents_from(
        self, slot_list: list[dict[str, Any]], *, engine_offset: bool = False
    ) -> list[dict[str, Any]]:
        return slot_widget.get_ai_opponents_from(self, slot_list, engine_offset=engine_offset)

    # ------------------------------------------------------------------
    # Game Options
    # ------------------------------------------------------------------

    GAME_OPTION_DEFS = _GAME_OPT_DEFS

    # _build_game_options and _build_settings_column removed — consolidated
    # into _build_options_column and _build_players_column above.

    def _on_game_option_change(self, key: str) -> None:
        """Broadcast state when a game option changes (host only)."""
        self._broadcast_game_state()

    def get_game_options(self) -> dict[str, str]:
        """Collect game options from the UI for game_config.py."""
        raw: dict[str, str] = {}
        for key, var in self.game_option_vars.items():
            raw[key] = var.get()
        return game_options_to_engine(raw)

    def _sync_bundled_mods(self) -> None:
        """Copy bundled mods/usermods from the exe bundle to WOPC deployment.

        Runs on every startup so new mods from updates appear without re-setup.
        """
        import shutil

        for kind, dest in [
            ("mods", config.WOPC_MODS),
            ("usermods", config.WOPC_USERMODS),
        ]:
            src = config.REPO_BUNDLED / kind
            if not src.exists():
                continue
            dest.mkdir(parents=True, exist_ok=True)
            for mod_dir in sorted(src.iterdir()):
                if mod_dir.is_dir():
                    shutil.copytree(mod_dir, dest / mod_dir.name, dirs_exist_ok=True)

        # Patch LOUD-era mod files on every startup (safety net for installs
        # that ran setup before the mod_compat fix existed).
        from launcher.mod_compat import apply_mod_compat_patches

        apply_mod_compat_patches(config.WOPC_MODS)

    def _on_mod_change(self, _entry: Any, _enabled: bool) -> None:
        """Called when any mod checkbox is toggled in the solo ModPanel."""
        self._update_play_summary()
        # Sync the lobby panel so downloads/toggles propagate across screens
        lobby_panel = getattr(self, "_lobby_mod_panel", None)
        if lobby_panel:
            lobby_panel.refresh()

    def _refresh_mods_list(self) -> None:
        """Rebuild the mod panel from current disk state."""
        try:
            if hasattr(self, "_mod_panel"):
                self._mod_panel.refresh()
            self._update_play_summary()
        except Exception:
            logger.exception("Mod list refresh failed")

    def _refresh_map_list(self) -> None:
        """Scan the maps directory and populate the list + filters.

        Always rescans the filesystem — stale caches caused black map
        previews after setup/update (backlog #50, #53).
        """
        try:
            self._all_maps = map_scanner.scan_all_maps()
        except Exception:
            logger.exception("Map scan failed — map list will be empty")
            self._all_maps = []
            self.log("ERROR: Map scan failed — check launcher.log for details")
            return

        logger.info("Map scan: %d maps in %s", len(self._all_maps), config.WOPC_MAPS)
        if not self._all_maps:
            self.log(f"WARNING: No maps found in {config.WOPC_MAPS}")

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
        """Persist faction preference and update the human slot label."""
        parser = prefs.load_prefs()
        parser.set("Game", "player_faction", choice.lower())
        prefs.save_prefs(parser)
        # Update the human slot faction label + icon (widget index 2)
        if hasattr(self, "player_slots") and self.player_slots:
            from launcher.gui.slot_widget import _get_faction_icon

            faction_lbl = self.player_slots[0]["widgets"][2]
            faction_lbl.configure(text=choice.capitalize())
            icon = _get_faction_icon(choice)
            if icon:
                faction_lbl.configure(image=icon)

    def _on_minimap_toggle(self) -> None:
        """Persist minimap visibility preference when checkbox is toggled."""
        parser = prefs.load_prefs()
        parser.set("Game", "minimap_enabled", str(self.minimap_var.get()))
        prefs.save_prefs(parser)

    # ------------------------------------------------------------------
    # Launch mode helpers
    # ------------------------------------------------------------------

    _PLAY_LABELS = PLAY_LABELS

    def _on_expected_humans_change(self, value: str) -> None:
        """Persist expected humans preference when dropdown changes."""
        prefs.set_expected_humans(int(value))

    # ------------------------------------------------------------------
    # Lobby networking callbacks
    # ------------------------------------------------------------------

    def _make_lobby_callbacks(self, *, is_host: bool = False) -> LobbyCallbacks:
        return lobby_screen.make_lobby_callbacks(self, is_host=is_host)

    def _on_player_joined(self, player_id: int, name: str, faction: str, slot: int) -> None:
        lobby_screen.on_player_joined(self, player_id, name, faction, slot)

    def _on_player_left(self, player_id: int) -> None:
        lobby_screen.on_player_left(self, player_id)

    def _on_ready_changed(self, player_id: int, ready: bool) -> None:
        lobby_screen.on_ready_changed(self, player_id, ready)

    def _on_lobby_launch(self, host_port: str) -> None:
        lobby_screen.on_lobby_launch(self, host_port)

    def _on_lobby_connected(self) -> None:
        lobby_screen.on_lobby_connected(self)

    def _on_lobby_disconnected(self, reason: str) -> None:
        lobby_screen.on_lobby_disconnected(self, reason)

    def _on_lobby_error(self, error: str) -> None:
        lobby_screen.on_lobby_error(self, error)

    def _on_file_request(self, player_id: int, category: str, name: str) -> None:
        lobby_screen.on_file_request(self, player_id, category, name)

    def _on_file_manifest(self, category: str, name: str, files: list[dict[str, Any]]) -> None:
        lobby_screen.on_file_manifest(self, category, name, files)

    def _on_file_chunk(self, category: str, path: str, index: int, total: int, data: str) -> None:
        lobby_screen.on_file_chunk(self, category, path, index, total, data)

    def _on_file_complete(self, category: str, name: str) -> None:
        lobby_screen.on_file_complete(self, category, name)

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
            self._append_chat(name, text)

    def _append_chat(self, sender: str, text: str) -> None:
        self.log(f"[{sender}] {text}")

    def _on_chat_received(self, sender: str, text: str) -> None:
        lobby_screen.on_chat_received(self, sender, text)

    def _on_kicked(self, reason: str) -> None:
        lobby_screen.on_kicked(self, reason)

    def _kick_player(self, player_id: int) -> None:
        lobby_screen.kick_player(self, player_id)

    def _on_game_state_received(self, state: dict[str, Any]) -> None:
        lobby_screen.on_game_state_received(self, state)

    def _build_game_state(self) -> dict[str, Any] | None:
        return lobby_screen.build_game_state(self)

    def _refresh_cached_game_state(self) -> None:
        lobby_screen.refresh_cached_game_state(self)

    def _get_cached_game_state(self) -> dict[str, Any] | None:
        return lobby_screen.get_cached_game_state(self)

    def _validate_before_launch(self) -> list[str]:
        return lobby_screen.validate_before_launch(self)

    def _broadcast_game_state(self) -> None:
        lobby_screen.broadcast_game_state(self)

    def _apply_remote_ai_slots(self, ai_slots: list[dict[str, Any]]) -> None:
        slot_widget.apply_remote_ai_slots(self, ai_slots)

    def _add_remote_human_slot(self, player_id: int, name: str, faction: str, slot: int) -> None:
        slot_widget.add_remote_human_slot(self, player_id, name, faction, slot)

    def _clear_remote_players(self) -> None:
        lobby_screen.clear_remote_players(self)

    def _update_host_button_text(self) -> None:
        lobby_screen.update_host_button_text(self)

    # ------------------------------------------------------------------
    # Lobby lifecycle management
    # ------------------------------------------------------------------

    def _start_lobby_server(self) -> None:
        """Start the TCP lobby server when hosting a multiplayer game."""
        if self._lobby_server and self._lobby_server.is_running:
            return
        port = int(self.port_entry.get() or "15000")
        prefs.set_host_port(str(port))
        self._refresh_cached_game_state()
        callbacks = self._make_lobby_callbacks(is_host=True)
        self._lobby_server = LobbyServer(
            port, callbacks, game_state_provider=self._get_cached_game_state
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
        wopc_core_ok = (config.WOPC_GAMEDATA / config.WOPC_CORE_SCD).exists()
        self._assets_ok = (config.WOPC_ROOT / "gamedata").exists() and wopc_core_ok
        if not wopc_core_ok and (config.WOPC_ROOT / "gamedata").exists():
            label_fail = "✗  Assets: wopc_core.scd missing"
        else:
            label_fail = "✗  Assets: Not Deployed"
        self._resolve_status_check(
            self.status_bundled,
            self.progress_bundled,
            ok=self._assets_ok,
            label_ok="✓  Assets: Ready",
            label_fail=label_fail,
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
        # Check content freshness — stale wopc_core.scd causes BrewLANLOUDPath
        # crashes and other issues.  Force re-download if content_build.txt is
        # missing or doesn't match the expected CONTENT_BUILD.
        if assets_ok and wopc_ok:
            marker = config.WOPC_ROOT / "content_build.txt"
            try:
                current = marker.read_text(encoding="utf-8").strip()
            except (OSError, ValueError):
                current = ""
            expected = str(config.CONTENT_BUILD)
            if current != expected:
                logger.info(
                    "Content outdated (have=%r, need=%r) — forcing re-download",
                    current,
                    expected,
                )
                self.log("Content update available — re-downloading...")
                # Don't delete the existing SCD — it's the only working copy.
                # Instead, remove the staleness marker so setup re-runs.
                # deploy.py will overwrite the SCD atomically on success.
                if marker.exists():
                    marker.unlink()
                assets_ok = False

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

        if scfa_ok and (not wopc_ok or not assets_ok):
            if not assets_ok and wopc_ok:
                self.log("wopc_core.scd missing — re-running setup to repair...")
            else:
                self.log("WOPC not deployed — starting automatic installation...")
            self._start_install()
        elif scfa_ok and wopc_ok and assets_ok:
            # Sync bundled mods on every startup — picks up new mods from updates
            self._sync_bundled_mods()
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

        # Force tkinter to compute widget geometry before rendering maps.
        # After an auto-update restart, the canvas may not be laid out yet
        # when _refresh_map_list() triggers set_map() → redraw(), causing a
        # blank map preview (winfo_width() < 10 → bail out).
        self.update_idletasks()

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

            ok = RelayClient.upload_logs(
                self._log_lines,
                host_name=host_name,
                launch_id=wopc_module.last_launch_id,
            )
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

    def _schedule_update_check(self) -> None:
        """Launch a background update check and schedule periodic re-checks."""
        threading.Thread(target=self._check_for_update, daemon=True).start()
        self.after(_UPDATE_CHECK_INTERVAL_MS, self._maybe_recheck_update)

    def _maybe_recheck_update(self) -> None:
        """Periodically re-check for updates if none found yet."""
        if self._pending_update is None:
            threading.Thread(target=self._check_for_update, daemon=True).start()
        self.after(_UPDATE_CHECK_INTERVAL_MS, self._maybe_recheck_update)

    def _check_for_update(self) -> None:
        """Background thread: check GitHub for a new launcher version."""
        info = updater.check_for_update(retry_on_failure=True)
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

        # Diagnostic: log spawn assignments so we can verify correctness
        if hasattr(self, "player_slots"):
            for si, slot in enumerate(self.player_slots):
                raw_spot = slot.get("start_spot", si)
                slot_type = slot["type"]
                logger.info(
                    "Launch slot %d (%s): start_spot=%d (engine StartSpot=%d)",
                    si,
                    slot_type,
                    raw_spot,
                    raw_spot + 1,
                )
            self.log(f"Spawns: human→ARMY_{start_spot}, team→{team}")

        result = cmd_launch(
            ai_opponents=ai_opponents,
            game_options=game_options,
            player_color=color,
            player_start_spot=start_spot,
            player_team=team,
            launch_mode="solo",
        )
        if isinstance(result, subprocess.Popen):
            self.log("Game process started successfully.")
            self._monitor_game_process(result, launch_id=wopc_module.last_launch_id)
        else:
            self.log("Game failed to launch.")

    def _launch_game_and_cleanup(self) -> None:
        """Run the game in a background thread (host mode), then stop lobby server."""
        self._persist_widget_values()
        # CRITICAL: Use LOBBY slots for multiplayer, not solo player_slots.
        # The host's AI opponents, spawn, and team come from lobby_player_slots.
        lobby_slots = getattr(self, "lobby_player_slots", [])
        ai_opponents = slot_widget.get_ai_opponents_from(self, lobby_slots, engine_offset=True)
        game_options = self.get_game_options() if hasattr(self, "game_option_vars") else None
        color = self.get_human_color_index()
        # Host spawn and team from lobby slot 0
        host_slot = lobby_slots[0] if lobby_slots else {}
        start_spot = int(host_slot.get("start_spot", 0)) + 1  # engine offset
        team_var = host_slot.get("team_var")
        team = int(team_var.get()) + 1 if team_var else 2  # engine offset

        result = cmd_launch(
            ai_opponents=ai_opponents,
            game_options=game_options,
            player_color=color,
            player_start_spot=start_spot,
            player_team=team,
            launch_mode="host",
        )
        if isinstance(result, subprocess.Popen):
            self.log("Game process started successfully.")
            self._monitor_game_process(result, launch_id=wopc_module.last_launch_id)
        else:
            self.log("Game failed to launch.")

        # Give peers a moment to receive the Launch message, then clean up
        time.sleep(3)
        self.after(0, self._stop_beacon_broadcaster)
        self.after(0, self._stop_relay_registration)
        self.after(0, self._stop_lobby_server)
        # Return to browser screen so the lobby doesn't sit with stale state
        self.after(0, self._clear_lobby_player_slots)
        self.after(0, lambda: self._show_screen("browser"))
        self.after(0, self._start_beacon_listener)
        self.after(0, self._start_relay_polling)
        self.after(
            0,
            lambda: self.lobby_launch_btn.configure(
                text="▶  LAUNCH GAME", fg_color=COLOR_LAUNCH, state="normal"
            ),
        )

    def _monitor_game_process(self, proc: subprocess.Popen, launch_id: str = "") -> None:
        """Monitor the game process in a background thread.

        Waits for the game to exit, then logs:
        - Exit code and session duration
        - Warning if duration < 30s (likely failed during loading)
        - Last 20 lines of WOPC.log for engine state at exit time
        """

        def _wait_and_log() -> None:
            start = time.monotonic()
            exit_code = proc.wait()
            duration = time.monotonic() - start
            mins, secs = divmod(int(duration), 60)

            # Log exit code and duration
            logger.info(
                "Game exited: code=%s, duration=%dm%02ds (%.0fs), launch_id=%s",
                exit_code,
                mins,
                secs,
                duration,
                launch_id,
            )

            # GUI message
            if duration < 30:
                msg = (
                    f"Game exited quickly ({int(duration)}s, code={exit_code})"
                    " — likely failed during loading. Check logs."
                )
                logger.warning(
                    "Game exited very quickly (%.1fs) — likely failed during loading",
                    duration,
                )
            else:
                msg = f"Game ended ({mins}m{secs:02d}s, code={exit_code})"

            # Read tail of WOPC.log for engine state at exit
            game_log = config.WOPC_BIN / config.GAME_LOG
            if game_log.exists():
                try:
                    lines = game_log.read_text(encoding="utf-8", errors="replace").splitlines()
                    tail = lines[-20:] if len(lines) > 20 else lines
                    logger.info("=== WOPC.log tail (%d lines) ===", len(tail))
                    for line in tail:
                        logger.info("  %s", line)
                    logger.info("=== end WOPC.log tail ===")
                except OSError as exc:
                    logger.warning("Could not read WOPC.log: %s", exc)
            else:
                logger.info("WOPC.log not found at %s", game_log)

            # Post GUI message on the main thread
            with contextlib.suppress(Exception):
                self.after(0, lambda: self.log(msg))

        t = threading.Thread(target=_wait_and_log, daemon=True, name="game-monitor")
        t.start()

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
        lobby_screen.on_create_game(self)

    def _on_direct_connect(self) -> None:
        lobby_screen.on_direct_connect(self)

    def _join_game(self, host: str, port: int) -> None:
        lobby_screen.join_game(self, host, port)

    def _join_discovered_game(self, game: Any) -> None:
        lobby_screen.join_discovered_game(self, game)

    def _on_leave_lobby(self) -> None:
        lobby_screen.on_leave_lobby(self)

    def _on_lobby_launch_click(self) -> None:
        lobby_screen.on_lobby_launch_click(self)

    def _on_lobby_change_map(self) -> None:
        lobby_screen.on_lobby_change_map(self)

    def _on_lobby_option_change(self, key: str) -> None:
        lobby_screen.on_lobby_option_change(self, key)

    def _send_lobby_chat(self) -> None:
        lobby_screen.send_lobby_chat(self)

    def _append_lobby_chat(self, sender: str, text: str) -> None:
        lobby_screen.append_lobby_chat(self, sender, text)

    def _update_lobby_for_host(self) -> None:
        lobby_screen.update_lobby_for_host(self)

    def _update_lobby_for_joiner(self) -> None:
        lobby_screen.update_lobby_for_joiner(self)

    def _toggle_direct_connect(self) -> None:
        browser_screen.toggle_direct_connect(self)

    def _refresh_game_browser(self, games: list[Any]) -> None:
        browser_screen.refresh_game_browser(self, games)

    def _start_beacon_broadcaster(self) -> None:
        browser_screen.start_beacon_broadcaster(self)

    def _stop_beacon_broadcaster(self) -> None:
        browser_screen.stop_beacon_broadcaster(self)

    def _start_beacon_listener(self) -> None:
        browser_screen.start_beacon_listener(self)

    def _stop_beacon_listener(self) -> None:
        browser_screen.stop_beacon_listener(self)

    def _beacon_state(self) -> dict[str, Any]:
        return browser_screen.beacon_state(self)

    def _start_relay_polling(self) -> None:
        browser_screen.start_relay_polling(self)

    def _stop_relay_polling(self) -> None:
        browser_screen.stop_relay_polling(self)

    def _start_relay_registration(self) -> None:
        browser_screen.start_relay_registration(self)

    def _stop_relay_registration(self) -> None:
        browser_screen.stop_relay_registration(self)

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

    def _on_tk_exception(self, exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
        """Handle uncaught exceptions in tkinter callbacks.

        Logs the full traceback to launcher.log and shows a one-line
        summary in the GUI textbox.  Keeps the app alive instead of
        crashing silently.
        """
        logger.error(
            "Unhandled exception in UI callback",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        with contextlib.suppress(Exception):
            self.log(f"ERROR: {exc_type.__name__}: {exc_value}")


def launch_gui() -> None:
    """Instantiate and run the WOPC graphical application."""
    if ctk is None:
        logger.error("FATAL: customtkinter is not installed. Run 'pip install customtkinter'.")
        sys.exit(1)

    try:
        app = WopcApp()
        app.mainloop()
    except Exception:
        logger.exception("Fatal error in launcher GUI")
        # Show error dialog if tkinter still works
        try:
            import tkinter.messagebox as mb

            mb.showerror(
                "WOPC Launcher",
                "A fatal error occurred.\nCheck launcher.log for details.",
            )
        except Exception:
            pass
        # Try to upload crash info to Firebase
        try:
            import traceback

            from launcher.relay import RelayClient

            RelayClient.upload_logs(["CRASH: " + traceback.format_exc()])
        except Exception:
            pass
        sys.exit(1)
