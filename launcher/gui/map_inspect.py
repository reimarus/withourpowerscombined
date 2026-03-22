"""Map inspect window — full-screen detailed map view with markers and zoom."""

import logging
import tkinter as tk
from typing import Any

from launcher import map_scanner

logger = logging.getLogger("wopc.gui.map_inspect")

try:
    from PIL import Image as PilImage  # type: ignore[import-not-found]
    from PIL import ImageTk  # type: ignore[import-not-found]

    _PIL_AVAILABLE = True
except ImportError:
    PilImage = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False

# Reuse app color constants
COLOR_BG = "#080C14"
COLOR_PANEL = "#0D1220"
COLOR_TEXT_PRIMARY = "#E8E4D4"
COLOR_TEXT_MUTED = "#4A5A70"
COLOR_TEXT_GOLD = "#C8A84B"
COLOR_ACCENT = "#C8A84B"

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


class MapInspectWindow(tk.Toplevel):
    """Detailed map inspect window with zoom, markers, and legend."""

    def __init__(
        self,
        parent: Any,
        info: map_scanner.MapInfo,
        raw_preview: Any,
    ) -> None:
        super().__init__(parent)
        self.title(f"Map: {info.display_name}")
        self.configure(bg=COLOR_BG)
        self.geometry("700x750")
        self.minsize(400, 450)

        self._info = info
        self._raw_preview = raw_preview
        self._zoom = 1.0
        self._tk_image: Any = None

        # Header with map info
        header = tk.Frame(self, bg=COLOR_PANEL)
        header.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(
            header,
            text=info.display_name,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_GOLD,
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 2))

        parts = []
        if info.max_players:
            parts.append(f"{info.max_players} players")
        if info.size_label and info.size_label != "?":
            parts.append(info.size_label)
        if info.is_campaign:
            parts.append("Campaign")
        detail_text = "  |  ".join(parts) if parts else ""

        tk.Label(
            header,
            text=detail_text,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_MUTED,
            font=("Segoe UI", 11),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 2))

        if info.description:
            tk.Label(
                header,
                text=info.description,
                bg=COLOR_PANEL,
                fg=COLOR_TEXT_MUTED,
                font=("Segoe UI", 10, "italic"),
                anchor="w",
                wraplength=650,
                justify="left",
            ).pack(fill="x", padx=10, pady=(0, 8))

        # Legend
        legend = tk.Frame(self, bg=COLOR_PANEL)
        legend.pack(fill="x", padx=8, pady=(0, 4))

        legend_items = []
        if info.markers:
            legend_items.append(f"Mass: {len(info.markers.mass)}")
            legend_items.append(f"Hydro: {len(info.markers.hydro)}")
            legend_items.append(f"Spawns: {len(info.markers.armies)}")

        tk.Label(
            legend,
            text="    ".join(legend_items) if legend_items else "No marker data",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_PRIMARY,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", padx=10, pady=4)

        # Canvas
        self._canvas = tk.Canvas(
            self,
            bg=COLOR_BG,
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._canvas.bind("<Configure>", self._on_resize)
        self._canvas.bind("<MouseWheel>", self._on_scroll)

        # Zoom label
        self._zoom_label = tk.Label(
            self,
            text="Zoom: 1.0x  (scroll to zoom)",
            bg=COLOR_BG,
            fg=COLOR_TEXT_MUTED,
            font=("Segoe UI", 9),
        )
        self._zoom_label.pack(pady=(0, 6))

        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_set()
        self.after(50, self._redraw)

    def _on_resize(self, event: Any) -> None:
        self._redraw()

    def _on_scroll(self, event: Any) -> None:
        if event.delta > 0:
            self._zoom = min(4.0, self._zoom * 1.15)
        else:
            self._zoom = max(0.5, self._zoom / 1.15)
        self._zoom_label.configure(text=f"Zoom: {self._zoom:.1f}x  (scroll to zoom)")
        self._redraw()

    def _redraw(self) -> None:
        canvas = self._canvas
        canvas.delete("all")

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        base_size = min(cw, ch)
        size = int(base_size * self._zoom)
        ox = (cw - size) // 2
        oy = (ch - size) // 2

        if self._raw_preview is not None and _PIL_AVAILABLE:
            resized = self._raw_preview.resize(
                (size, size),
                PilImage.LANCZOS,  # type: ignore[attr-defined]
            )
            self._tk_image = ImageTk.PhotoImage(resized)
            canvas.create_image(ox, oy, anchor="nw", image=self._tk_image)
        else:
            canvas.create_rectangle(ox, oy, ox + size, oy + size, fill=COLOR_BG, outline="")
            canvas.create_text(
                cw // 2,
                ch // 2,
                text="No Preview",
                fill=COLOR_TEXT_MUTED,
                font=("Segoe UI", 14),
            )
            return

        info = self._info
        if info.markers is None or info.map_width == 0:
            return

        mw = info.map_width
        mh = info.map_height or mw

        def _map_to_px(mx: float, mz: float) -> tuple[int, int]:
            px = ox + int(mx / mw * size)
            py = oy + int(mz / mh * size)
            return px, py

        # Mass points
        r_mass = max(2, size // 100)
        for mx, mz in info.markers.mass:
            px, py = _map_to_px(mx, mz)
            canvas.create_oval(
                px - r_mass,
                py - r_mass,
                px + r_mass,
                py + r_mass,
                fill="#FFFFFF",
                outline="#808080",
                width=1,
            )

        # Hydro points
        r_hydro = max(3, size // 70)
        for mx, mz in info.markers.hydro:
            px, py = _map_to_px(mx, mz)
            canvas.create_oval(
                px - r_hydro,
                py - r_hydro,
                px + r_hydro,
                py + r_hydro,
                fill="#00CC00",
                outline="#006600",
                width=1,
            )

        # Army spawns
        r_army = max(10, size // 35)
        for i, (name, mx, mz) in enumerate(info.markers.armies):
            px, py = _map_to_px(mx, mz)
            color = PLAYER_COLORS[i % len(PLAYER_COLORS)][0]
            canvas.create_oval(
                px - r_army,
                py - r_army,
                px + r_army,
                py + r_army,
                fill=color,
                outline="#FFFFFF",
                width=2,
            )
            num = name.split("_")[1] if "_" in name else str(i + 1)
            canvas.create_text(
                px,
                py,
                text=num,
                fill="#FFFFFF",
                font=("Segoe UI", max(9, size // 45), "bold"),
            )
