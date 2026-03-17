import logging
import sys
import threading
from typing import TYPE_CHECKING, Any, ClassVar

from launcher import map_scanner, mods

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

from launcher import config, prefs
from launcher.gui.worker import SetupWorker
from launcher.wopc import cmd_launch

logger = logging.getLogger("wopc.gui")

if ctk is not None:
    # Set the default color theme and appearance for the entire application
    ctk.set_appearance_mode("Dark")
    # We'll use the built-in dark-blue theme as a sleek base
    ctk.set_default_color_theme("dark-blue")

# Custom colors for Discord-style aesthetic
COLOR_BG = "#1E1F22"  # Deepest background (Sidebar)
COLOR_PANEL = "#313338"  # Main chat/content area
COLOR_MOD_PANEL = "#2B2D31"  # Secondary sidebar (Mods/Members lists)
COLOR_ACCENT = "#5865F2"  # Discord Blurple for interactive elements
COLOR_READY = "#23A559"  # Discord Green for PLAY state
COLOR_WARN = "#FEE75C"  # Discord Yellow for UPDATE/INSTALL state
COLOR_TEXT_PRIMARY = "#F2F3F5"
COLOR_TEXT_MUTED = "#949BA4"


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
    main_content: Any
    header_label: Any
    config_panel: Any
    selected_map_label: Any
    map_scroll: Any
    map_buttons: list[Any]
    log_textbox: Any
    mod_pane: Any
    mod_header: Any
    mods_scroll: Any
    mod_checkboxes: dict[str, Any]
    play_summary: Any

    def __init__(self) -> None:
        super().__init__()

        self.title("WOPC - Match Lobby")
        self.geometry("1024x768")
        self.minsize(800, 600)
        self.configure(fg_color=COLOR_PANEL)
        self._set_window_icon()

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

        # Configure 3x3 grid layout (Sidebar | Lobby | Mod Pane)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=240)  # Left Sidebar
        self.grid_columnconfigure(1, weight=3)  # Main Lobby Area
        self.grid_columnconfigure(2, weight=1, minsize=260)  # Right Mod Pane

        self._build_sidebar()
        self._build_main_lobby()
        self._build_mod_pane()

        self._check_installation_status()
        self._bind_hotkeys()

    def _bind_hotkeys(self) -> None:
        """Bind global keyboard shortcuts."""
        self.bind("<Return>", lambda e: self._on_primary_click())
        self.bind("<Escape>", lambda e: self.destroy())

    def _build_sidebar(self) -> None:
        """Construct the left sidebar navigation and status area."""
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(9, weight=1)

        # Logo / Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="WOPC",
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 0), sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar,
            text="LOBBY TERMINAL",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        # Status indicators
        self.status_scfa = ctk.CTkLabel(
            self.sidebar, text="SCFA: Checking...", text_color=COLOR_TEXT_MUTED
        )
        self.status_scfa.grid(row=2, column=0, padx=20, pady=5, sticky="w")

        self.status_bundled = ctk.CTkLabel(
            self.sidebar, text="Assets: Checking...", text_color=COLOR_TEXT_MUTED
        )
        self.status_bundled.grid(row=3, column=0, padx=20, pady=5, sticky="w")

        self.status_wopc = ctk.CTkLabel(
            self.sidebar, text="WOPC: Checking...", text_color=COLOR_TEXT_MUTED
        )
        self.status_wopc.grid(row=4, column=0, padx=20, pady=5, sticky="w")

        # --- Launch Mode Selector ---
        self.mode_label = ctk.CTkLabel(
            self.sidebar,
            text="LAUNCH MODE",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.mode_label.grid(row=5, column=0, padx=20, pady=(20, 5), sticky="w")

        saved_mode = prefs.get_launch_mode()
        self.mode_var = ctk.StringVar(value=saved_mode.upper())
        self.mode_selector = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["SOLO", "HOST", "JOIN"],
            variable=self.mode_var,
            command=self._on_mode_change,
        )
        self.mode_selector.grid(row=6, column=0, padx=20, pady=(0, 5), sticky="ew")

        # Conditional widgets for HOST/JOIN modes
        self.mode_widgets_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.mode_widgets_frame.grid(row=7, column=0, padx=20, sticky="ew")

        self.port_label = ctk.CTkLabel(
            self.mode_widgets_frame, text="Port:", text_color=COLOR_TEXT_MUTED
        )
        self.port_entry = ctk.CTkEntry(self.mode_widgets_frame, width=120, placeholder_text="15000")
        self.port_entry.insert(0, prefs.get_host_port())
        self.port_entry.bind("<FocusOut>", lambda e: prefs.set_host_port(self.port_entry.get()))

        self.address_label = ctk.CTkLabel(
            self.mode_widgets_frame, text="Host Address:", text_color=COLOR_TEXT_MUTED
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

        self._update_mode_widgets()

        # Play Button (Bottom of Sidebar)
        self.primary_btn = ctk.CTkButton(
            self.sidebar,
            text="PLAY MATCH",
            font=ctk.CTkFont(size=18, weight="bold"),
            height=50,
            fg_color=COLOR_READY,
            hover_color="#1F8B4C",
            text_color="white",
            command=self._on_primary_click,
        )
        self.primary_btn.grid(row=8, column=0, padx=20, pady=(10, 10), sticky="ew")

        # Version tag
        self.version_label = ctk.CTkLabel(
            self.sidebar,
            text=f"v{config.VERSION}",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.version_label.grid(row=10, column=0, padx=20, pady=(0, 20), sticky="w")

    def _build_main_lobby(self) -> None:
        """Construct the central matching routing/configuration area."""
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.main_content.grid_rowconfigure(1, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        self.header_label = ctk.CTkLabel(
            self.main_content,
            text="Game Configuration",
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.header_label.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Config Panel (Map / Players / Settings Placeholder)
        self.config_panel = ctk.CTkFrame(
            self.main_content, fg_color=COLOR_MOD_PANEL, corner_radius=8
        )
        self.config_panel.grid(row=1, column=0, sticky="nsew")
        self.config_panel.grid_rowconfigure(1, weight=1)
        self.config_panel.grid_columnconfigure(0, weight=1)

        # Selected Map Header
        self.selected_map_label = ctk.CTkLabel(
            self.config_panel,
            text="Selected Map: None",
            text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.selected_map_label.grid(row=0, column=0, pady=(10, 5), padx=20, sticky="w")

        # Map Filters
        self.filter_frame = ctk.CTkFrame(self.config_panel, fg_color="transparent")
        self.filter_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.filter_frame.grid_columnconfigure(0, weight=1)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._apply_map_filters)
        self.search_entry = ctk.CTkEntry(
            self.filter_frame,
            textvariable=self.search_var,
            placeholder_text="Search maps...",
            height=28,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.type_var = ctk.StringVar(value="All")
        self.type_menu = ctk.CTkOptionMenu(
            self.filter_frame,
            values=["All", "Skirmish", "Campaign"],
            variable=self.type_var,
            command=self._apply_map_filters,
            width=100,
            height=28,
        )
        self.type_menu.grid(row=0, column=1, padx=(0, 10))

        self.players_var = ctk.StringVar(value="Any")
        self.players_menu = ctk.CTkOptionMenu(
            self.filter_frame,
            values=["Any", "2", "4", "6", "8", "10", "12", "14", "16"],
            variable=self.players_var,
            command=self._apply_map_filters,
            width=70,
            height=28,
        )
        self.players_menu.grid(row=0, column=2, padx=(0, 10))

        self.size_var = ctk.StringVar(value="Any")
        self.size_menu = ctk.CTkOptionMenu(
            self.filter_frame,
            values=["Any", "5km", "10km", "20km", "40km", "81km"],
            variable=self.size_var,
            command=self._apply_map_filters,
            width=80,
            height=28,
        )
        self.size_menu.grid(row=0, column=3)

        # Scrollable Map Selector
        self.map_scroll = ctk.CTkScrollableFrame(self.config_panel, fg_color="transparent")
        self.map_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.map_buttons: list[Any] = []

        # Log Window at the bottom
        self.log_textbox = ctk.CTkTextbox(
            self.main_content,
            height=140,
            fg_color=COLOR_MOD_PANEL,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.log_textbox.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        self.log_textbox.insert("0.0", "Welcome to the WOPC Match Lobby.\\n")
        self.log_textbox.configure(state="disabled")

    def _build_mod_pane(self) -> None:
        """Construct the right-hand sidebar for Mod management."""
        self.mod_pane = ctk.CTkFrame(self, fg_color=COLOR_MOD_PANEL, corner_radius=0)
        self.mod_pane.grid(row=0, column=2, sticky="nsew")
        self.mod_pane.grid_rowconfigure(1, weight=1)  # Content packs
        self.mod_pane.grid_rowconfigure(3, weight=1)  # User mods

        # --- Content Packs Section ---
        self.packs_header = ctk.CTkLabel(
            self.mod_pane,
            text="CONTENT PACKS",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.packs_header.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        self.packs_scroll = ctk.CTkScrollableFrame(self.mod_pane, fg_color="transparent")
        self.packs_scroll.grid(row=1, column=0, sticky="nsew", padx=10)
        self.pack_checkboxes: dict[str, Any] = {}

        # --- User Mods Section ---
        self.mod_header = ctk.CTkLabel(
            self.mod_pane,
            text="USER MODS",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.mod_header.grid(row=2, column=0, padx=20, pady=(15, 5), sticky="w")

        self.mods_scroll = ctk.CTkScrollableFrame(self.mod_pane, fg_color="transparent")
        self.mods_scroll.grid(row=3, column=0, sticky="nsew", padx=10)
        self.mod_checkboxes: dict[str, Any] = {}

        # --- Player Settings Section ---
        self.settings_header = ctk.CTkLabel(
            self.mod_pane,
            text="PLAYER SETTINGS",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.settings_header.grid(row=4, column=0, padx=20, pady=(15, 5), sticky="w")

        # Player name
        self.name_label = ctk.CTkLabel(
            self.mod_pane,
            text="Name:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.name_label.grid(row=5, column=0, padx=30, pady=(3, 0), sticky="w")
        self.name_entry = ctk.CTkEntry(self.mod_pane, width=160, placeholder_text="Player")
        saved_name = prefs.get_player_name()
        if saved_name and saved_name != "Player":
            self.name_entry.insert(0, saved_name)
        self.name_entry.bind(
            "<FocusOut>",
            lambda e: prefs.set_player_name(self.name_entry.get()),
        )
        self.name_entry.grid(row=6, column=0, padx=30, pady=(0, 5), sticky="w")

        # Faction selector
        saved_faction = prefs.get_player_faction()
        display_faction = "UEF" if saved_faction == "uef" else saved_faction.capitalize()
        self.faction_var = ctk.StringVar(value=display_faction)
        self.faction_label = ctk.CTkLabel(
            self.mod_pane,
            text="Faction:",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.faction_label.grid(row=7, column=0, padx=30, pady=(3, 0), sticky="w")
        self.faction_menu = ctk.CTkOptionMenu(
            self.mod_pane,
            values=["Random", "UEF", "Aeon", "Cybran", "Seraphim"],
            variable=self.faction_var,
            command=self._on_faction_change,
            width=160,
        )
        self.faction_menu.grid(row=8, column=0, padx=30, pady=(0, 5), sticky="w")

        # Minimap toggle
        self.minimap_var = ctk.BooleanVar(value=prefs.get_minimap_enabled())
        self.minimap_cb = ctk.CTkCheckBox(
            self.mod_pane,
            text="Show minimap on launch",
            command=self._on_minimap_toggle,
            variable=self.minimap_var,
        )
        self.minimap_cb.grid(row=9, column=0, padx=30, pady=3, sticky="w")

        # Summary Status
        self.play_summary = ctk.CTkLabel(
            self.mod_pane,
            text="Enabled: 0",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.play_summary.grid(row=10, column=0, padx=20, pady=10, sticky="w")

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

        for idx, mod_info in enumerate(user_mods_on_disk):
            is_enabled = mod_info.uid in enabled_uids

            def on_toggle(uid=mod_info.uid) -> None:
                cb = self.mod_checkboxes[uid]
                mods.set_user_mod_enabled(uid, bool(cb.get()))
                self._update_play_summary()

            cb = ctk.CTkCheckBox(self.mods_scroll, text=mod_info.name, command=on_toggle)
            if is_enabled:
                cb.select()
            cb.grid(row=idx, column=0, pady=3, padx=10, sticky="w")
            self.mod_checkboxes[mod_info.uid] = cb

        self._update_play_summary()

    def _refresh_map_list(self) -> None:
        """Scan the maps directory and cache the list, then apply filters."""
        self._all_maps = getattr(self, "_all_maps", [])
        if not self._all_maps:
            self._all_maps = map_scanner.scan_all_maps()

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

        for idx, info in enumerate(filtered_maps):
            is_active = info.folder_name == active_map

            # Rich label: "Setons Clutch — 8p, 20km"
            parts = [info.display_name]
            if info.max_players:
                parts.append(f"{info.max_players}p")
            if info.size_label != "?":
                parts.append(info.size_label)
            label = f"{parts[0]} — {', '.join(parts[1:])}" if len(parts) > 1 else parts[0]

            def on_select(name=info.folder_name, disp=info.display_name) -> None:
                prefs.set_active_map(name)
                for map_btn in self.map_buttons:
                    map_btn.configure(
                        fg_color="transparent",
                        text_color=COLOR_TEXT_PRIMARY,
                    )
                # Re-highlight selected
                for map_btn in self.map_buttons:
                    if getattr(map_btn, "_wopc_folder", None) == name:
                        map_btn.configure(fg_color=COLOR_ACCENT, text_color="white")
                self.selected_map_label.configure(text=f"Selected Map: {disp}")

            color = COLOR_ACCENT if is_active else "transparent"
            tcolor = "white" if is_active else COLOR_TEXT_PRIMARY

            btn = ctk.CTkButton(
                self.map_scroll,
                text=label,
                fg_color=color,
                text_color=tcolor,
                anchor="w",
                command=on_select,
            )
            btn._wopc_folder = info.folder_name
            btn.grid(row=idx, column=0, sticky="ew", pady=2)
            self.map_buttons.append(btn)

            if is_active:
                self.selected_map_label.configure(text=f"Selected Map: {info.display_name}")

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
        "HOST": "HOST GAME",
        "JOIN": "JOIN GAME",
    }

    def _on_mode_change(self, mode: str) -> None:
        """Respond to the SOLO / HOST / JOIN segmented button."""
        prefs.set_launch_mode(mode.lower())
        self._update_mode_widgets()
        # Update the play button text (only when installation is ready)
        btn_text = self.primary_btn.cget("text")
        if btn_text in self._PLAY_LABELS.values():
            self.primary_btn.configure(text=self._PLAY_LABELS.get(mode, "PLAY MATCH"))

    def _update_mode_widgets(self) -> None:
        """Show/hide conditional inputs for the current launch mode."""
        mode = self.mode_var.get()  # "SOLO", "HOST", or "JOIN"

        # Clear previous layout
        self.port_label.grid_forget()
        self.port_entry.grid_forget()
        self.address_label.grid_forget()
        self.address_entry.grid_forget()

        if mode == "HOST":
            self.port_label.grid(row=0, column=0, sticky="w", pady=(5, 0))
            self.port_entry.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        elif mode == "JOIN":
            self.address_label.grid(row=0, column=0, sticky="w", pady=(5, 0))
            self.address_entry.grid(row=1, column=0, sticky="ew", pady=(0, 5))

        # Toggle map selector visibility — host picks the map in JOIN mode
        map_visible = mode != "JOIN"
        if hasattr(self, "config_panel"):
            if map_visible:
                self.config_panel.grid()
            else:
                self.config_panel.grid_remove()
            # Show a hint in the header when joining
            if hasattr(self, "header_label"):
                if mode == "JOIN":
                    self.header_label.configure(text="Joining — host controls the map")
                else:
                    self.header_label.configure(text="Game Configuration")

    def _update_play_summary(self) -> None:
        """Update the label on the play tab showing the active config."""
        total = len(mods.get_active_mod_uids())
        self.play_summary.configure(text=f"Active Mods: {total}")

    def log(self, message: str) -> None:
        """Add a message to the GUI text box."""

        def _update():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
            logger.info(message)

        self.after(0, _update)

    def _check_installation_status(self) -> None:
        """Check directories and update UI states appropriately."""
        scfa_ok = config.SCFA_STEAM.exists() and (config.SCFA_BIN / config.GAME_EXE).exists()
        wopc_ok = config.WOPC_BIN.exists() and (config.WOPC_BIN / config.GAME_EXE).exists()

        self.status_scfa.configure(
            text=f"SCFA: {'FOUND' if scfa_ok else 'MISSING'}",
            text_color="white" if scfa_ok else COLOR_WARN,
        )
        self.status_wopc.configure(
            text=f"WOPC: {'READY' if wopc_ok else 'NOT SETUP'}",
            text_color="white" if wopc_ok else COLOR_WARN,
        )

        if not scfa_ok:
            self.primary_btn.configure(text="MISSING GAME FILES", state="disabled", fg_color="gray")
            self.log("ERROR: SCFA installation not found.")
        elif not wopc_ok:
            self.primary_btn.configure(
                text="INSTALL / UPDATE",
                fg_color=COLOR_WARN,
                hover_color="#CC8F00",
                text_color="black",
            )
            self.log("WOPC is not deployed. Click Install to begin.")
        else:
            mode = self.mode_var.get()
            self.primary_btn.configure(
                text=self._PLAY_LABELS.get(mode, "PLAY MATCH"),
                fg_color=COLOR_READY,
                hover_color="#1F8B4C",
                text_color="white",
                state="normal",
            )
            self.log("All systems ready.")

        # Always populate maps and mods regardless of setup status
        self._refresh_mods_list()
        self._refresh_map_list()

    def _on_primary_click(self) -> None:
        """Handle main button action depending on current state."""
        btn_text = self.primary_btn.cget("text")

        if btn_text in self._PLAY_LABELS.values():
            mode = self.mode_var.get()
            # Validate JOIN address before launching
            if mode == "JOIN" and not self.address_entry.get().strip():
                self.log("ERROR: Enter a host address before joining.")
                return
            self.log(f"Launching game ({mode.lower()} mode)...")
            threading.Thread(target=self._launch_game, daemon=True).start()

        elif btn_text == "INSTALL / UPDATE":
            self.log("Starting asynchronous installation...")
            self.primary_btn.configure(state="disabled", text="INSTALLING...")
            worker = SetupWorker(on_complete=self._on_setup_complete, on_log=self.log)
            worker.start()

    def _on_setup_complete(self, success: bool) -> None:
        """Callback executed when the SetupWorker finishes."""

        def _update():
            self.primary_btn.configure(state="normal")
            if success:
                self._check_installation_status()
            else:
                self.log("Installation failed. Check logs and retry.")
                self.primary_btn.configure(
                    text="INSTALL / UPDATE",
                    state="normal",
                    fg_color=COLOR_WARN,
                    hover_color="#CC8F00",
                    text_color="black",
                )

        self.after(0, _update)

    def _launch_game(self) -> None:
        """Run the game in a background thread."""
        # Persist any unsaved widget values before launch
        mode = self.mode_var.get()
        if mode == "HOST":
            prefs.set_host_port(self.port_entry.get())
        elif mode == "JOIN":
            prefs.set_join_address(self.address_entry.get())
        if hasattr(self, "name_entry"):
            prefs.set_player_name(self.name_entry.get())

        ret = cmd_launch()
        if ret == 0:
            self.log("Game process started successfully.")
        else:
            self.log("Game failed to launch.")


def launch_gui() -> None:
    """Instantiate and run the WOPC graphical application."""
    if ctk is None:
        logger.error("FATAL: customtkinter is not installed. Run 'pip install customtkinter'.")
        sys.exit(1)

    app = WopcApp()
    app.mainloop()
