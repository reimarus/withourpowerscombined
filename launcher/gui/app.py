import logging
import sys
import threading
from typing import Any

try:
    import customtkinter as ctk  # type: ignore[import-untyped]
except ImportError:
    ctk = None  # type: ignore[assignment]

from launcher import config, prefs
from launcher.gui.worker import SetupWorker
from launcher.wopc import cmd_launch

logger = logging.getLogger("wopc.gui")

if ctk is not None:
    # Set the default color theme and appearance for the entire application
    ctk.set_appearance_mode("Dark")
    # We'll use the built-in dark-blue theme as a sleek base
    ctk.set_default_color_theme("dark-blue")
    BaseApp: Any = ctk.CTk
else:
    BaseApp = object  # type: ignore[misc, no-redef]

# Custom colors for our WOPC aesthetic
COLOR_BG = "#1A1A1A"
COLOR_PANEL = "#2B2B2B"
COLOR_ACCENT = "#00D4FF"  # Cyan accent for interactive elements
COLOR_READY = "#00FF66"  # Neon green for PLAY state
COLOR_WARN = "#FFB300"  # Orange for UPDATE/INSTALL state


class WopcApp(BaseApp):  # type: ignore
    """The main Graphical User Interface for the WOPC Launcher."""

    def __init__(self) -> None:
        super().__init__()

        self.title("WOPC - With Our Powers Combined")
        self.geometry("800x600")
        self.minsize(600, 450)
        self.configure(fg_color=COLOR_BG)
        self._set_window_icon()

    def _set_window_icon(self) -> None:
        """Set the application window icon if it exists."""
        from pathlib import Path

        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).parent.resolve()
        else:
            base_dir = Path(__file__).parent.parent.parent.resolve()

        icon_path = base_dir / "launcher" / "gui" / "wopc.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception as exc:
                logger.warning("Failed to set window icon: %s", exc)

        # Configure 2x2 grid layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)

        self._build_sidebar()
        self._build_main_view()
        self._check_installation_status()
        self._bind_hotkeys()

    def _bind_hotkeys(self) -> None:
        """Bind global keyboard shortcuts."""
        self.bind("<Return>", lambda e: self._on_primary_click())
        self.bind("<Escape>", lambda e: self.destroy())

    def _build_sidebar(self) -> None:
        """Construct the left sidebar navigation and status area."""
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        # Logo / Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar, text="WOPC\nLAUNCHER", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Status indicators
        self.status_scfa = ctk.CTkLabel(self.sidebar, text="SCFA: Checking...")
        self.status_scfa.grid(row=1, column=0, padx=20, pady=5, sticky="w")

        self.status_loud = ctk.CTkLabel(self.sidebar, text="LOUD: Checking...")
        self.status_loud.grid(row=2, column=0, padx=20, pady=5, sticky="w")

        self.status_wopc = ctk.CTkLabel(self.sidebar, text="WOPC: Checking...")
        self.status_wopc.grid(row=3, column=0, padx=20, pady=5, sticky="w")

        # Version tag
        self.version_label = ctk.CTkLabel(
            self.sidebar, text=f"v{config.VERSION}", text_color="gray"
        )
        self.version_label.grid(row=5, column=0, padx=20, pady=20, sticky="s")

    def _build_main_view(self) -> None:
        """Construct the central content area with tabbed navigation."""
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=20, pady=20)
        self.main_content.grid_rowconfigure(0, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        # Tab View
        self.tabview = ctk.CTkTabview(self.main_content)
        self.tabview.grid(row=0, column=0, sticky="nsew")
        self.tabview.add("Play")
        self.tabview.add("Mods")
        self.tabview.add("Maps")

        self._build_play_tab()
        self._build_mods_tab()
        self._build_maps_tab()

        # Log Window at the bottom
        self.log_textbox = ctk.CTkTextbox(
            self.main_content, height=120, fg_color=COLOR_PANEL, text_color="white"
        )
        self.log_textbox.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.log_textbox.insert("0.0", "Welcome to the WOPC Launcher...\\n")
        self.log_textbox.configure(state="disabled")

    def _build_play_tab(self) -> None:
        """Construct the main Play tab."""
        play_tab = self.tabview.tab("Play")
        play_tab.grid_rowconfigure(0, weight=1)
        play_tab.grid_columnconfigure(0, weight=1)

        self.center_frame = ctk.CTkFrame(play_tab, fg_color="transparent")
        self.center_frame.grid(row=0, column=0)

        self.primary_btn = ctk.CTkButton(
            self.center_frame,
            text="PLAY WOPC",
            font=ctk.CTkFont(size=28, weight="bold"),
            height=80,
            width=300,
            fg_color=COLOR_READY,
            hover_color="#00CC52",
            text_color="black",
            command=self._on_primary_click,
        )
        self.primary_btn.pack(pady=20)

        # Summary Status
        self.play_summary = ctk.CTkLabel(
            self.center_frame, text="Active Mods: 0", text_color="gray"
        )
        self.play_summary.pack()

    def _build_mods_tab(self) -> None:
        """Construct the Mod manager tab."""
        mods_tab = self.tabview.tab("Mods")
        mods_tab.grid_rowconfigure(0, weight=1)
        mods_tab.grid_columnconfigure(0, weight=1)

        # Scrollable frame for mod list
        self.mods_scroll = ctk.CTkScrollableFrame(mods_tab, fg_color="transparent")
        self.mods_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.mod_checkboxes: dict[str, Any] = {}

    def _build_maps_tab(self) -> None:
        """Construct the Map selector tab."""
        maps_tab = self.tabview.tab("Maps")
        label = ctk.CTkLabel(maps_tab, text="Map Selection Coming Soon...")
        label.pack(pady=50)

    def _refresh_mods_list(self) -> None:
        """Read available mods from disk and update the Mods tab."""
        # Clear existing checkboxes
        for cb in self.mod_checkboxes.values():
            cb.destroy()
        self.mod_checkboxes.clear()

        if not config.WOPC_USERMODS.exists():
            return

        enabled_mods = prefs.get_enabled_mods()

        # Find all mod folders or SCDs
        available = []
        for d in config.WOPC_USERMODS.iterdir():
            if d.is_dir() or d.name.endswith(".scd") or d.name.endswith(".zip"):
                available.append(d.name)

        available.sort()

        for idx, mod_name in enumerate(available):
            is_enabled = mod_name in enabled_mods

            # Create a localized callback using default arguments to capture `mod_name` correctly
            def on_toggle(name=mod_name):
                cb = self.mod_checkboxes[name]
                prefs.set_mod_state(name, bool(cb.get()))
                self._update_play_summary()

            cb = ctk.CTkCheckBox(self.mods_scroll, text=mod_name, command=on_toggle)
            if is_enabled:
                cb.select()
            cb.grid(row=idx, column=0, pady=5, padx=10, sticky="w")
            self.mod_checkboxes[mod_name] = cb

        self._update_play_summary()

    def _update_play_summary(self) -> None:
        """Update the label on the play tab showing the active config."""
        enabled = len(prefs.get_enabled_mods())
        self.play_summary.configure(text=f"Active Mods: {enabled}")

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
        loud_ok = config.LOUD_ROOT.exists() and (config.LOUD_ROOT / "gamedata" / "lua.scd").exists()
        wopc_ok = config.WOPC_BIN.exists() and (config.WOPC_BIN / config.GAME_EXE).exists()

        self.status_scfa.configure(
            text=f"SCFA: {'FOUND' if scfa_ok else 'MISSING'}",
            text_color="white" if scfa_ok else COLOR_WARN,
        )
        self.status_loud.configure(
            text=f"LOUD: {'FOUND' if loud_ok else 'MISSING'}",
            text_color="white" if loud_ok else COLOR_WARN,
        )
        self.status_wopc.configure(
            text=f"WOPC: {'READY' if wopc_ok else 'NOT SETUP'}",
            text_color="white" if wopc_ok else COLOR_WARN,
        )

        if not scfa_ok or not loud_ok:
            self.primary_btn.configure(text="MISSING GAME FILES", state="disabled", fg_color="gray")
            self.log("ERROR: Master game files (SCFA or LOUD) not found.")
        elif not wopc_ok:
            self.primary_btn.configure(
                text="INSTALL / UPDATE",
                fg_color=COLOR_WARN,
                hover_color="#CC8F00",
                text_color="black",
            )
            self.log("WOPC is not deployed. Click Install to begin.")
        else:
            self.primary_btn.configure(
                text="PLAY WOPC",
                fg_color=COLOR_READY,
                hover_color="#00CC52",
                text_color="black",
                state="normal",
            )
            self.log("All systems ready.")
            self._refresh_mods_list()

    def _on_primary_click(self) -> None:
        """Handle main button action depending on current state."""
        btn_text = self.primary_btn.cget("text")
        if btn_text == "PLAY WOPC":
            self.log("Launching game...")
            # Run launch command and check return code
            # Note: cmd_launch currently blocks until game closes.
            # Subprocess logic will be moved to the worker later.
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
