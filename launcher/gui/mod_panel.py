"""Mod panel widget — collapsible categories with checkbox rows.

Reusable across solo and multiplayer screens. Shows all known mods
(content packs + user mods) grouped by category, with download
buttons for missing content packs.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import customtkinter as ctk  # type: ignore[import-untyped,import-not-found]
else:
    try:
        import customtkinter as ctk  # type: ignore[import-untyped]
    except ImportError:
        ctk = None  # type: ignore[assignment]

from launcher import config, mods
from launcher.gui.constants import (
    COLOR_ACCENT,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
)

logger = logging.getLogger("wopc.gui.mod_panel")


# ---------------------------------------------------------------------------
# CollapsibleCategory
# ---------------------------------------------------------------------------


class CollapsibleCategory(ctk.CTkFrame):
    """A collapsible section with a header row and stacked mod rows."""

    def __init__(
        self,
        parent: Any,
        category_key: str,
        category_label: str,
        *,
        expanded: bool = True,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.category_key = category_key
        self._expanded = expanded
        self._rows: list[ModRow] = []

        self.grid_columnconfigure(0, weight=1)

        # Header row
        self._header = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        self._header.grid(row=0, column=0, sticky="ew")
        self._header.grid_columnconfigure(1, weight=1)

        self._arrow = ctk.CTkLabel(
            self._header,
            text="▾" if expanded else "▸",
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=11),
            width=14,
        )
        self._arrow.grid(row=0, column=0, padx=(0, 2))

        self._label = ctk.CTkLabel(
            self._header,
            text=category_label,
            text_color=COLOR_TEXT_GOLD,
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        )
        self._label.grid(row=0, column=1, sticky="w")

        self._count = ctk.CTkLabel(
            self._header,
            text="(0)",
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=10),
        )
        self._count.grid(row=0, column=2, padx=(4, 0))

        # Body frame (holds mod rows)
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.grid_columnconfigure(0, weight=1)
        if expanded:
            self._body.grid(row=1, column=0, sticky="ew", padx=(12, 0))

        # Click header to toggle
        for widget in (self._header, self._arrow, self._label, self._count):
            widget.bind("<Button-1>", self._toggle)

    def _toggle(self, _event: Any = None) -> None:
        self._expanded = not self._expanded
        self._arrow.configure(text="▾" if self._expanded else "▸")
        if self._expanded:
            self._body.grid(row=1, column=0, sticky="ew", padx=(12, 0))
        else:
            self._body.grid_forget()

    def add_row(self, row: ModRow) -> None:
        """Add a mod row to this category's body."""
        row_idx = len(self._rows)
        row.grid(row=row_idx, column=0, sticky="ew", pady=1)
        self._rows.append(row)

    def update_count(self) -> None:
        """Update the count badge in the header."""
        self._count.configure(text=f"({len(self._rows)})")


# ---------------------------------------------------------------------------
# ModRow
# ---------------------------------------------------------------------------


class ModRow(ctk.CTkFrame):
    """A single mod row with checkbox and optional download button."""

    def __init__(
        self,
        parent: Any,
        entry: mods.ModEntry,
        on_change: Callable[[mods.ModEntry, bool], None],
        *,
        readonly: bool = False,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.entry = entry
        self._on_change = on_change
        self.grid_columnconfigure(0, weight=1)

        self._var = ctk.StringVar(value="on" if entry.enabled else "off")

        state = "disabled" if (not entry.on_disk or readonly) else "normal"
        text_color = COLOR_TEXT_MUTED if not entry.on_disk else COLOR_TEXT_PRIMARY

        self._cb = ctk.CTkCheckBox(
            self,
            text=entry.name,
            variable=self._var,
            onvalue="on",
            offvalue="off",
            command=self._on_toggle,
            text_color=text_color,
            state=state,
            font=ctk.CTkFont(size=11),
        )
        self._cb.grid(row=0, column=0, sticky="w", padx=(0, 4))

        # Download button for missing content packs
        self._download_btn: Any | None = None
        if not entry.on_disk and entry.mod_type == "content_pack":
            self._download_btn = ctk.CTkButton(
                self,
                text="Download",
                width=60,
                height=20,
                font=ctk.CTkFont(size=10),
                fg_color=COLOR_ACCENT,
                command=self._start_download,
            )
            self._download_btn.grid(row=0, column=1, padx=(2, 0))

    def _on_toggle(self) -> None:
        enabled = self._var.get() == "on"
        self._on_change(self.entry, enabled)

    def _start_download(self) -> None:
        """Download a missing content pack SCD in a background thread."""
        if self._download_btn is None:
            return

        self._download_btn.configure(text="...", state="disabled")
        scd_name = self.entry.key
        asset_info = config.CONTENT_PACK_ASSETS.get(scd_name)
        if not asset_info:
            logger.warning("No download URL for %s", scd_name)
            self._download_btn.configure(text="Error", state="disabled")
            return

        def _do_download() -> None:
            from launcher.deploy import _download_file

            dst = config.WOPC_GAMEDATA / scd_name
            config.WOPC_GAMEDATA.mkdir(parents=True, exist_ok=True)
            ok = _download_file(asset_info["url"], dst)

            if ok and dst.exists():
                mods.extract_mods_from_scd(dst)
                # Download sounds if any
                for sound_name, sound_url in asset_info.get("sounds", {}).items():
                    sound_dst = config.WOPC_SOUNDS / sound_name
                    if not sound_dst.exists():
                        config.WOPC_SOUNDS.mkdir(parents=True, exist_ok=True)
                        _download_file(sound_url, sound_dst)

            # Update UI on main thread
            self.after(0, lambda: self._download_complete(ok and dst.exists()))

        thread = threading.Thread(target=_do_download, daemon=True)
        thread.start()

    def _download_complete(self, success: bool) -> None:
        """Called on main thread after download finishes."""
        if success:
            self.entry = mods.ModEntry(
                key=self.entry.key,
                name=self.entry.name,
                category=self.entry.category,
                enabled=self.entry.enabled,
                on_disk=True,
                mod_type=self.entry.mod_type,
            )
            self._cb.configure(state="normal", text_color=COLOR_TEXT_PRIMARY)
            if self._download_btn:
                self._download_btn.destroy()
                self._download_btn = None
            logger.info("Downloaded %s", self.entry.key)
        else:
            if self._download_btn:
                self._download_btn.configure(text="Retry", state="normal")
            logger.warning("Failed to download %s", self.entry.key)

    def set_enabled(self, enabled: bool) -> None:
        """Programmatically set the checkbox state."""
        self._var.set("on" if enabled else "off")

    def set_readonly(self, readonly: bool) -> None:
        """Enable or disable interaction."""
        state = "disabled" if readonly or not self.entry.on_disk else "normal"
        self._cb.configure(state=state)


# ---------------------------------------------------------------------------
# ModPanel (the main reusable widget)
# ---------------------------------------------------------------------------


class ModPanel(ctk.CTkFrame):
    """Grouped mod list with collapsible categories.

    Shared between solo and multiplayer screens.
    """

    def __init__(
        self,
        parent: Any,
        *,
        on_change: Callable[[mods.ModEntry, bool], None] | None = None,
        readonly: bool = False,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._on_change = on_change or (lambda _e, _v: None)
        self._readonly = readonly
        self._categories: dict[str, CollapsibleCategory] = {}
        self._rows: dict[str, ModRow] = {}  # key -> ModRow

        self.grid_columnconfigure(0, weight=1)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the panel from current mod state."""
        # Destroy existing widgets
        for widget in self.winfo_children():
            widget.destroy()
        self._categories.clear()
        self._rows.clear()

        entries = mods.get_all_mods()

        # Group by category
        groups: dict[str, list[mods.ModEntry]] = {}
        for entry in entries:
            groups.setdefault(entry.category, []).append(entry)

        grid_row = 0
        for cat_key, cat_label in mods.MOD_CATEGORIES.items():
            cat_entries = groups.get(cat_key, [])
            if not cat_entries:
                continue

            cat_widget = CollapsibleCategory(self, cat_key, cat_label, expanded=True)
            cat_widget.grid(row=grid_row, column=0, sticky="ew", pady=(2, 0))
            self._categories[cat_key] = cat_widget

            for entry in cat_entries:
                row = ModRow(
                    cat_widget._body,
                    entry,
                    self._handle_change,
                    readonly=self._readonly,
                )
                cat_widget.add_row(row)
                self._rows[entry.key] = row

            cat_widget.update_count()
            grid_row += 1

    def _handle_change(self, entry: mods.ModEntry, enabled: bool) -> None:
        """Route checkbox toggles to the appropriate state setter."""
        if entry.mod_type == "content_pack":
            mods.set_pack_state(entry.key, enabled)
        else:
            mods.set_user_mod_enabled(entry.key, enabled)
        self._on_change(entry, enabled)

    def get_enabled_state(self) -> dict[str, bool]:
        """Return {key: enabled} for all mods (for multiplayer sync)."""
        return {key: row._var.get() == "on" for key, row in self._rows.items()}

    def apply_state(self, state: dict[str, bool]) -> None:
        """Set checkbox states from a host-provided dict (joiner sync)."""
        for key, enabled in state.items():
            row = self._rows.get(key)
            if row:
                row.set_enabled(enabled)

    def set_readonly(self, readonly: bool) -> None:
        """Enable or disable all checkboxes (joiners can't change mods)."""
        self._readonly = readonly
        for row in self._rows.values():
            row.set_readonly(readonly)
