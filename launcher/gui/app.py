import logging
import threading

import customtkinter as ctk

from launcher import config
from launcher.gui.worker import SetupWorker
from launcher.wopc import cmd_launch

logger = logging.getLogger("wopc.gui")

# Set the default color theme and appearance for the entire application
ctk.set_appearance_mode("Dark")
# We'll use the built-in dark-blue theme as a sleek base
ctk.set_default_color_theme("dark-blue")

# Custom colors for our WOPC aesthetic
COLOR_BG = "#1A1A1A"
COLOR_PANEL = "#2B2B2B"
COLOR_ACCENT = "#00D4FF"  # Cyan accent for interactive elements
COLOR_READY = "#00FF66"  # Neon green for PLAY state
COLOR_WARN = "#FFB300"  # Orange for UPDATE/INSTALL state


class WopcApp(ctk.CTk):
    """The main Graphical User Interface for the WOPC Launcher."""

    def __init__(self) -> None:
        super().__init__()

        self.title("WOPC - With Our Powers Combined")
        self.geometry("800x600")
        self.minsize(600, 450)
        self.configure(fg_color=COLOR_BG)

        # Configure 2x2 grid layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)

        self._build_sidebar()
        self._build_main_view()
        self._check_installation_status()

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
        """Construct the central content area and primary action button."""
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=20, pady=20)
        self.main_content.grid_rowconfigure(0, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        # Container for the big button to center it
        self.center_frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
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

        self.log_textbox = ctk.CTkTextbox(
            self.main_content, height=150, fg_color=COLOR_PANEL, text_color="white"
        )
        self.log_textbox.grid(row=1, column=0, sticky="ew")
        self.log_textbox.insert("0.0", "Welcome to the WOPC Launcher...\n")
        self.log_textbox.configure(state="disabled")

    def log(self, message: str) -> None:
        """Add a message to the GUI text box."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        logger.info(message)

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
                text="PLAY WOPC", fg_color=COLOR_READY, hover_color="#00CC52", text_color="black"
            )
            self.log("All systems ready.")

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
        self.primary_btn.configure(state="normal")
        if success:
            self._check_installation_status()
        else:
            self.primary_btn.configure(text="INSTALL FAILED", fg_color=COLOR_WARN)

    def _launch_game(self) -> None:
        """Run the game in a background thread."""
        ret = cmd_launch()
        if ret == 0:
            self.log("Game exited normally.")
        else:
            self.log("Game exited with an error.")


def launch_gui() -> None:
    """Instantiate and run the WOPC graphical application."""
    app = WopcApp()
    app.mainloop()
