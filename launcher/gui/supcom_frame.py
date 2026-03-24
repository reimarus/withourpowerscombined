"""SupCom-style 9-slice metallic frame widget.

Renders UEF metallic chrome borders around content panels using pre-extracted
frame PNGs from the game's UI textures.  The interior is a standard CTkFrame
that accepts child widgets normally.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from typing import Any

logger = logging.getLogger("wopc.gui.supcom_frame")

# Optional PIL — gracefully degrade to plain frame if unavailable.
try:
    from PIL import Image as PilImage
    from PIL import ImageTk

    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_ICONS_DIR = Path(__file__).parent / "icons"

# Corner size after scaling (pixels).  The source PNGs are 80x80; we shrink
# them so the chrome doesn't overwhelm small panels.
_CORNER = 12
_EDGE_THICKNESS = 4  # How thick the edge borders appear after scaling


def _load_frame_parts(
    corner: int = _CORNER,
) -> dict[str, PilImage.Image] | None:
    """Load and scale the 8 frame PNGs.  Returns None if any are missing."""
    if not _PIL_OK:
        return None
    names = [
        "topleft",
        "top",
        "topright",
        "left",
        "right",
        "bottomleft",
        "bottom",
        "bottomright",
    ]
    parts: dict[str, PilImage.Image] = {}
    for name in names:
        p = _ICONS_DIR / f"frame_{name}.png"
        if not p.exists():
            logger.debug("Missing frame asset: %s", p)
            return None
        img = PilImage.open(p).convert("RGBA")
        # Scale corners to target size, edges to strip thickness
        if name in ("topleft", "topright", "bottomleft", "bottomright"):
            img = img.resize((corner, corner), PilImage.LANCZOS)
        elif name in ("top", "bottom"):
            img = img.resize((corner, _EDGE_THICKNESS), PilImage.LANCZOS)
        elif name in ("left", "right"):
            img = img.resize((_EDGE_THICKNESS, corner), PilImage.LANCZOS)
        parts[name] = img
    return parts


# Module-level cache — loaded once.
_frame_parts: dict[str, Any] | None | bool = False  # False = not yet loaded


def _get_parts() -> dict[str, Any] | None:
    global _frame_parts
    if _frame_parts is False:
        _frame_parts = _load_frame_parts()
    return _frame_parts  # type: ignore[return-value]


class SupComFrame:
    """A panel with SupCom-style 9-slice metallic chrome borders.

    Usage::

        sf = SupComFrame(parent, fg_color="#162030")
        sf.frame.grid(row=0, column=0, sticky="nsew")
        # Place children inside sf.interior
        ctk.CTkLabel(sf.interior, text="Hello").grid(...)

    If PIL is unavailable or frame assets are missing, falls back to a plain
    CTkFrame with ``border_width=1``.
    """

    def __init__(
        self,
        parent: Any,
        *,
        fg_color: str = "#162030",
        border_accent: str = "#1E2D42",
        corner: int = _CORNER,
        **grid_kwargs: Any,
    ) -> None:
        import customtkinter as ctk

        parts = _get_parts()

        if parts is None:
            # Fallback: plain frame with subtle border
            self.frame = ctk.CTkFrame(
                parent,
                fg_color=fg_color,
                corner_radius=4,
                border_width=1,
                border_color=border_accent,
            )
            self.interior = self.frame
            self._canvas = None
            return

        # Outer frame holds the canvas
        self.frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)

        self._canvas = tk.Canvas(
            self.frame,
            highlightthickness=0,
            bg=fg_color,
            bd=0,
        )
        self._canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Interior frame for child widgets — inset by edge thickness
        self.interior = ctk.CTkFrame(
            self.frame,
            fg_color=fg_color,
            corner_radius=0,
        )
        pad = _EDGE_THICKNESS
        self.interior.place(x=pad, y=pad, relwidth=1, relheight=1, width=-2 * pad, height=-2 * pad)

        self._fg_color = fg_color
        self._corner = corner
        self._parts = parts
        self._tk_images: list[Any] = []  # prevent GC
        self._last_size = (0, 0)

        self._canvas.bind("<Configure>", self._on_resize)

    def _on_resize(self, event: Any) -> None:
        """Redraw 9-slice border when canvas size changes."""
        w, h = event.width, event.height
        # Skip tiny redraws and no-change redraws
        if w < 20 or h < 20:
            return
        if (w, h) == self._last_size:
            return
        self._last_size = (w, h)
        self._draw_border(w, h)

    def _draw_border(self, w: int, h: int) -> None:
        """Composite and render the 9-slice metallic border."""
        if not _PIL_OK or self._parts is None or self._canvas is None:
            return

        canvas = self._canvas
        canvas.delete("border")
        self._tk_images.clear()

        c = self._corner
        parts = self._parts
        et = _EDGE_THICKNESS

        # Corners
        for name, x, y, anchor in [
            ("topleft", 0, 0, "nw"),
            ("topright", w, 0, "ne"),
            ("bottomleft", 0, h, "sw"),
            ("bottomright", w, h, "se"),
        ]:
            tk_img = ImageTk.PhotoImage(parts[name])
            self._tk_images.append(tk_img)
            canvas.create_image(x, y, image=tk_img, anchor=anchor, tags="border")

        # Edges — stretch to fill between corners
        top_w = max(1, w - 2 * c)
        bottom_w = max(1, w - 2 * c)
        left_h = max(1, h - 2 * c)
        right_h = max(1, h - 2 * c)

        if top_w > 0:
            top_img = parts["top"].resize((top_w, et), PilImage.LANCZOS)
            tk_top = ImageTk.PhotoImage(top_img)
            self._tk_images.append(tk_top)
            canvas.create_image(c, 0, image=tk_top, anchor="nw", tags="border")

        if bottom_w > 0:
            bot_img = parts["bottom"].resize((bottom_w, et), PilImage.LANCZOS)
            tk_bot = ImageTk.PhotoImage(bot_img)
            self._tk_images.append(tk_bot)
            canvas.create_image(c, h - et, image=tk_bot, anchor="nw", tags="border")

        if left_h > 0:
            left_img = parts["left"].resize((et, left_h), PilImage.LANCZOS)
            tk_left = ImageTk.PhotoImage(left_img)
            self._tk_images.append(tk_left)
            canvas.create_image(0, c, image=tk_left, anchor="nw", tags="border")

        if right_h > 0:
            right_img = parts["right"].resize((et, right_h), PilImage.LANCZOS)
            tk_right = ImageTk.PhotoImage(right_img)
            self._tk_images.append(tk_right)
            canvas.create_image(w - et, c, image=tk_right, anchor="nw", tags="border")
