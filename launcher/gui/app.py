import logging
import sys
import threading
import time
from typing import TYPE_CHECKING, Any, ClassVar

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

        # Lobby networking state
        self._lobby_server: LobbyServer | None = None
        self._lobby_client: LobbyClient | None = None
        self._remote_players: dict[int, dict[str, Any]] = {}

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

        # Expected Players dropdown (HOST mode only)
        self.expected_label = ctk.CTkLabel(
            self.mode_widgets_frame, text="Expected Players:", text_color=COLOR_TEXT_MUTED
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
        # Row 0: header, Row 1: config_panel (map), Row 2: players+options, Row 3: log
        self.main_content.grid_rowconfigure(1, weight=2)
        self.main_content.grid_rowconfigure(2, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        self.header_label = ctk.CTkLabel(
            self.main_content,
            text="Game Configuration",
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.header_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # --- Map Selector Panel ---
        self.config_panel = ctk.CTkFrame(
            self.main_content, fg_color=COLOR_MOD_PANEL, corner_radius=8
        )
        self.config_panel.grid(row=1, column=0, sticky="nsew")
        self.config_panel.grid_rowconfigure(2, weight=1)
        self.config_panel.grid_columnconfigure(0, weight=1)

        self.selected_map_label = ctk.CTkLabel(
            self.config_panel,
            text="Selected Map: None",
            text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.selected_map_label.grid(row=0, column=0, pady=(10, 5), padx=20, sticky="w")

        # Map Filters
        self.filter_frame = ctk.CTkFrame(self.config_panel, fg_color="transparent")
        self.filter_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 5))
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

        self.map_scroll = ctk.CTkScrollableFrame(self.config_panel, fg_color="transparent")
        self.map_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.map_buttons: list[Any] = []

        # --- Player Slots + Game Options Panel ---
        self.lower_panel = ctk.CTkFrame(
            self.main_content, fg_color=COLOR_MOD_PANEL, corner_radius=8
        )
        self.lower_panel.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self.lower_panel.grid_columnconfigure(0, weight=1)
        self.lower_panel.grid_columnconfigure(1, weight=1)
        self.lower_panel.grid_rowconfigure(1, weight=1)

        self._build_player_slots()
        self._build_game_options()

        # --- Log Window ---
        self.log_textbox = ctk.CTkTextbox(
            self.main_content,
            height=100,
            fg_color=COLOR_MOD_PANEL,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.log_textbox.grid(row=3, column=0, sticky="ew", pady=(10, 0))
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

    def _build_player_slots(self) -> None:
        """Build the player slots panel (left half of lower_panel)."""
        slots_frame = ctk.CTkFrame(self.lower_panel, fg_color="transparent")
        slots_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(10, 5), pady=10)
        slots_frame.grid_columnconfigure(0, weight=1)
        slots_frame.grid_rowconfigure(1, weight=1)

        header_row = ctk.CTkFrame(slots_frame, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew")
        header_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_row,
            text="PLAYER SLOTS",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.add_slot_btn = ctk.CTkButton(
            header_row,
            text="+ Add AI",
            width=70,
            height=24,
            font=ctk.CTkFont(size=11),
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

        type_lbl = ctk.CTkLabel(
            self.slots_scroll,
            text="Human",
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
            width=50,
            height=24,
        )
        team_menu.grid(row=row, column=3, padx=5, pady=2)
        widgets.append(team_menu)

        # No remove button for human
        spacer = ctk.CTkLabel(self.slots_scroll, text="", width=24)
        spacer.grid(row=row, column=4, pady=2)
        widgets.append(spacer)

        self.player_slots.append({"type": "human", "team_var": team_var, "widgets": widgets})

    def _add_ai_slot(self) -> None:
        """Add an AI opponent slot row."""
        if len(self.player_slots) >= self.MAX_SLOTS:
            return

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

        # Team
        team_var = ctk.StringVar(value="2")
        team_menu = ctk.CTkOptionMenu(
            self.slots_scroll,
            values=["1", "2", "3", "4"],
            variable=team_var,
            width=50,
            height=24,
        )
        team_menu.grid(row=row, column=3, padx=5, pady=2)
        widgets.append(team_menu)

        # Remove button
        slot_index = row  # capture for closure

        def remove_this() -> None:
            self._remove_slot(slot_index)

        remove_btn = ctk.CTkButton(
            self.slots_scroll,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color="#ED4245",
            text_color=COLOR_TEXT_MUTED,
            command=remove_this,
        )
        remove_btn.grid(row=row, column=4, pady=2)
        widgets.append(remove_btn)

        self.player_slots.append(
            {
                "type": "ai",
                "ai_var": ai_var,
                "faction_var": faction_var,
                "team_var": team_var,
                "widgets": widgets,
            }
        )

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

    def get_ai_opponents(self) -> list[dict[str, Any]]:
        """Collect AI opponent config from the slot UI for game_config.py."""
        opponents: list[dict[str, Any]] = []
        for _i, slot in enumerate(self.player_slots):
            if slot["type"] != "ai":
                continue
            ai_display = slot["ai_var"].get()
            ai_key = ai_display.lower()
            faction = slot["faction_var"].get().lower()
            team = int(slot["team_var"].get())
            opponents.append(
                {
                    "name": f"AI {len(opponents) + 1}: {ai_display}",
                    "faction": faction,
                    "ai": ai_key,
                    "team": team,
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

    def _build_game_options(self) -> None:
        """Build the game options panel (right half of lower_panel)."""
        opts_frame = ctk.CTkFrame(self.lower_panel, fg_color="transparent")
        opts_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 10), pady=10)
        opts_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            opts_frame,
            text="GAME OPTIONS",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        self.game_option_vars: dict[str, ctk.StringVar] = {}

        for idx, (key, label, values, default) in enumerate(self.GAME_OPTION_DEFS):
            ctk.CTkLabel(
                opts_frame,
                text=f"{label}:",
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(size=12),
            ).grid(row=idx + 1, column=0, sticky="w", padx=(0, 10), pady=2)

            var = ctk.StringVar(value=default)
            menu = ctk.CTkOptionMenu(
                opts_frame,
                values=values,
                variable=var,
                width=130,
                height=24,
            )
            menu.grid(row=idx + 1, column=1, sticky="w", pady=2)
            self.game_option_vars[key] = var

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
            elif key in ("Victory", "GameSpeed"):
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

    def _on_expected_humans_change(self, value: str) -> None:
        """Persist expected humans preference when dropdown changes."""
        prefs.set_expected_humans(int(value))

    # ------------------------------------------------------------------
    # Lobby networking callbacks
    # ------------------------------------------------------------------

    def _make_lobby_callbacks(self) -> LobbyCallbacks:
        """Create callbacks that marshal onto the GUI thread via self.after()."""
        return LobbyCallbacks(
            on_player_joined=lambda pid, name, faction, slot: self.after(
                0, self._on_player_joined, pid, name, faction, slot
            ),
            on_player_left=lambda pid: self.after(0, self._on_player_left, pid),
            on_ready_changed=lambda pid, ready: self.after(0, self._on_ready_changed, pid, ready),
            on_launch=lambda host_port: self.after(0, self._on_lobby_launch, host_port),
            on_connected=lambda: self.after(0, self._on_lobby_connected),
            on_disconnected=lambda reason: self.after(0, self._on_lobby_disconnected, reason),
            on_error=lambda err: self.after(0, self._on_lobby_error, err),
        )

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
        self.primary_btn.configure(text="LAUNCHING...", state="disabled")

        def _delayed_launch() -> None:
            time.sleep(2)
            ai_opponents = self.get_ai_opponents() if hasattr(self, "player_slots") else None
            game_options = self.get_game_options() if hasattr(self, "game_option_vars") else None
            ret = cmd_launch(ai_opponents=ai_opponents, game_options=game_options)
            if ret == 0:
                self.log("Game process started successfully.")
            else:
                self.log("Game failed to launch.")
            self.after(0, lambda: self.primary_btn.configure(text="JOIN GAME", state="normal"))

        threading.Thread(target=_delayed_launch, daemon=True).start()

    def _on_lobby_connected(self) -> None:
        """TCP callback (joiner): connected to host."""
        self.log("Connected to host lobby!")
        self.primary_btn.configure(text="READY", fg_color=COLOR_ACCENT)

    def _on_lobby_disconnected(self, reason: str) -> None:
        """TCP callback: connection lost."""
        self.log(f"Disconnected: {reason}")
        self._lobby_client = None
        self._clear_remote_players()
        mode = self.mode_var.get()
        if mode == "JOIN":
            self.primary_btn.configure(text="JOIN GAME", fg_color=COLOR_READY, state="normal")

    def _on_lobby_error(self, error: str) -> None:
        """TCP callback: connection error."""
        self.log(f"Lobby error: {error}")
        self._lobby_client = None
        self._clear_remote_players()
        mode = self.mode_var.get()
        if mode == "JOIN":
            self.primary_btn.configure(text="JOIN GAME", fg_color=COLOR_READY, state="normal")

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

        # Empty column 4 (no remove button for remote players)
        spacer = ctk.CTkLabel(self.slots_scroll, text="", width=24)
        spacer.grid(row=row, column=4, pady=2)
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
        """Update HOST button to show connected player count."""
        mode = self.mode_var.get()
        if mode != "HOST" or not self._lobby_server:
            return
        n_remote = len(self._remote_players)
        expected = int(self.expected_var.get())
        total = 1 + n_remote  # host + connected peers
        if n_remote == 0:
            self.primary_btn.configure(text="HOST GAME (Waiting...)")
        else:
            self.primary_btn.configure(text=f"LAUNCH ({total}/{expected} players)")

    # ------------------------------------------------------------------
    # Lobby lifecycle management
    # ------------------------------------------------------------------

    def _start_lobby_server(self) -> None:
        """Start the TCP lobby server for HOST mode."""
        if self._lobby_server and self._lobby_server.is_running:
            return
        port = int(self.port_entry.get() or "15000")
        prefs.set_host_port(str(port))
        callbacks = self._make_lobby_callbacks()
        self._lobby_server = LobbyServer(port, callbacks)
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
        """Connect to a host's lobby server for JOIN mode."""
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
        """Respond to the SOLO / HOST / JOIN segmented button."""
        old_mode = prefs.get_launch_mode().upper()
        prefs.set_launch_mode(mode.lower())
        self._update_mode_widgets()

        # Stop previous lobby connections on mode switch
        if old_mode == "HOST" and mode != "HOST":
            self._stop_lobby_server()
        if old_mode == "JOIN" and mode != "JOIN":
            self._disconnect_lobby_client()

        # Start lobby server when switching to HOST
        if mode == "HOST":
            self._start_lobby_server()

        # Update the play button text (only when installation is ready)
        btn_text = self.primary_btn.cget("text")
        play_labels = set(self._PLAY_LABELS.values())
        transitional = {"CONNECTING...", "READY", "LAUNCHING...", "HOST GAME (Waiting...)"}
        if btn_text in play_labels or btn_text in transitional or "LAUNCH (" in btn_text:
            self.primary_btn.configure(
                text=self._PLAY_LABELS.get(mode, "PLAY MATCH"),
                fg_color=COLOR_READY,
                state="normal",
            )

    def _update_mode_widgets(self) -> None:
        """Show/hide conditional inputs for the current launch mode."""
        mode = self.mode_var.get()  # "SOLO", "HOST", or "JOIN"

        # Clear previous layout
        self.port_label.grid_forget()
        self.port_entry.grid_forget()
        self.address_label.grid_forget()
        self.address_entry.grid_forget()
        self.expected_label.grid_forget()
        self.expected_menu.grid_forget()

        if mode == "HOST":
            self.port_label.grid(row=0, column=0, sticky="w", pady=(5, 0))
            self.port_entry.grid(row=1, column=0, sticky="ew", pady=(0, 5))
            self.expected_label.grid(row=2, column=0, sticky="w", pady=(5, 0))
            self.expected_menu.grid(row=3, column=0, sticky="w", pady=(0, 5))
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

        if btn_text == "INSTALL / UPDATE":
            self.log("Starting asynchronous installation...")
            self.primary_btn.configure(state="disabled", text="INSTALLING...")
            worker = SetupWorker(on_complete=self._on_setup_complete, on_log=self.log)
            worker.start()
            return

        mode = self.mode_var.get()

        # --- HOST mode ---
        if mode == "HOST":
            if not self._lobby_server or not self._lobby_server.is_running:
                self._start_lobby_server()
                return
            # Server running — broadcast launch to all peers, then launch SCFA
            n_remote = len(self._remote_players)
            prefs.set_expected_humans(1 + n_remote)
            host_port = self.port_entry.get() or "15000"
            self._lobby_server.broadcast_launch(host_port)
            self.log(f"Broadcasting launch to {n_remote} peer(s)...")
            self.primary_btn.configure(text="LAUNCHING...", state="disabled")
            threading.Thread(target=self._launch_game_and_cleanup, daemon=True).start()
            return

        # --- JOIN mode ---
        if mode == "JOIN":
            if not self._lobby_client or not self._lobby_client.is_connected:
                # Not connected yet — connect
                self._connect_lobby_client()
                return
            # Connected — toggle ready state
            # Check if we're currently "READY" vs just connected
            if btn_text == "READY":
                self._lobby_client.send_ready(True)
                self.primary_btn.configure(
                    text="UNREADY", fg_color="#ED4245", hover_color="#C53030"
                )
            elif btn_text == "UNREADY":
                self._lobby_client.send_ready(False)
                self.primary_btn.configure(
                    text="READY", fg_color=COLOR_ACCENT, hover_color="#4752C4"
                )
            return

        # --- SOLO mode (default) ---
        if btn_text in self._PLAY_LABELS.values():
            self.log("Launching game (solo mode)...")
            threading.Thread(target=self._launch_game, daemon=True).start()

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
        """Run the game in a background thread (solo mode)."""
        self._persist_widget_values()
        ai_opponents = self.get_ai_opponents() if hasattr(self, "player_slots") else None
        game_options = self.get_game_options() if hasattr(self, "game_option_vars") else None

        ret = cmd_launch(ai_opponents=ai_opponents, game_options=game_options)
        if ret == 0:
            self.log("Game process started successfully.")
        else:
            self.log("Game failed to launch.")

    def _launch_game_and_cleanup(self) -> None:
        """Run the game in a background thread (host mode), then stop lobby server."""
        self._persist_widget_values()
        ai_opponents = self.get_ai_opponents() if hasattr(self, "player_slots") else None
        game_options = self.get_game_options() if hasattr(self, "game_option_vars") else None

        ret = cmd_launch(ai_opponents=ai_opponents, game_options=game_options)
        if ret == 0:
            self.log("Game process started successfully.")
        else:
            self.log("Game failed to launch.")

        # Give peers a moment to receive the Launch message, then stop server
        time.sleep(3)
        self.after(0, self._stop_lobby_server)
        self.after(
            0,
            lambda: self.primary_btn.configure(
                text="HOST GAME", fg_color=COLOR_READY, state="normal"
            ),
        )

    def _persist_widget_values(self) -> None:
        """Save any unsaved widget values to prefs before launching."""
        mode = self.mode_var.get()
        if mode == "HOST":
            prefs.set_host_port(self.port_entry.get())
        elif mode == "JOIN":
            prefs.set_join_address(self.address_entry.get())
        if hasattr(self, "name_entry"):
            prefs.set_player_name(self.name_entry.get())

    def destroy(self) -> None:
        """Clean up lobby connections before closing the window."""
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
