"""Pure-data player slot model for the WOPC launcher.

This module contains ZERO widget references.  All player-slot logic
(add, remove, swap, team balance, color allocation, engine-format
conversion) lives here so it can be tested without a running GUI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from launcher.gui.constants import (
    PLAYER_COLORS,
    color_hex_to_index,
)

logger = logging.getLogger("wopc.gui.models")


@dataclass
class PlayerSlot:
    """One player slot — human or AI."""

    slot_type: Literal["human", "ai"]
    name: str = "Player"
    faction: str = "Random"  # "Random"|"UEF"|"Aeon"|"Cybran"|"Seraphim"
    team: int = 1  # UI format: 1-4
    color_hex: str = "#FF0000"
    start_spot: int = 0  # 0-based internal (UI)
    ai_key: str = "easy"  # only meaningful for AI slots

    # Engine format helpers --------------------------------------------------

    @property
    def team_engine(self) -> int:
        """UI team → engine team.  SCFA: Team 1 = FFA, Team 2+ = allied."""
        return self.team + 1

    @property
    def start_spot_engine(self) -> int:
        """0-based internal → 1-based engine StartSpot."""
        return self.start_spot + 1

    @property
    def color_index(self) -> int:
        """Hex color → 1-based SCFA engine color index."""
        return color_hex_to_index(self.color_hex)


@dataclass
class PlayerSlotManager:
    """Manages an ordered list of player slots with no widget dependencies.

    All slot manipulation (add, remove, swap, auto-balance, etc.) goes
    through this class.  The GUI reads slot state from here and writes
    UI-triggered changes back.
    """

    slots: list[PlayerSlot] = field(default_factory=list)
    max_positions: int = 16  # updated when map changes

    # -- Mutation -----------------------------------------------------------

    def add_human(
        self,
        name: str = "Player",
        faction: str = "Random",
        team: int = 1,
        color_hex: str = "#FF0000",
        start_spot: int = 0,
    ) -> int:
        """Add a human slot.  Returns the slot index."""
        slot = PlayerSlot(
            slot_type="human",
            name=name,
            faction=faction,
            team=team,
            color_hex=color_hex,
            start_spot=start_spot,
        )
        self.slots.append(slot)
        return len(self.slots) - 1

    def add_ai(
        self,
        faction: str = "Random",
        team: int | None = None,
        color_hex: str | None = None,
        start_spot: int | None = None,
        ai_key: str = "easy",
        name: str | None = None,
    ) -> int:
        """Add an AI slot with auto-defaults for team/color/spawn.

        Returns the slot index.
        """
        if team is None:
            team = self.next_team()
        if color_hex is None:
            color_hex = self.next_free_color()
        if start_spot is None:
            free = self.first_free_spawn()
            start_spot = free if free >= 0 else len(self.slots)
        if name is None:
            ai_count = sum(1 for s in self.slots if s.slot_type == "ai")
            name = f"AI {ai_count + 1}: {ai_key.capitalize()}"

        slot = PlayerSlot(
            slot_type="ai",
            name=name,
            faction=faction,
            team=team,
            color_hex=color_hex,
            start_spot=start_spot,
            ai_key=ai_key,
        )
        self.slots.append(slot)
        return len(self.slots) - 1

    def remove(self, index: int) -> None:
        """Remove slot at *index*.  Raises IndexError if invalid."""
        if index < 0 or index >= len(self.slots):
            raise IndexError(f"Slot index {index} out of range")
        if self.slots[index].slot_type == "human":
            raise ValueError("Cannot remove the human slot")
        self.slots.pop(index)

    # -- Spawn logic --------------------------------------------------------

    def select_spawn(self, slot_index: int, spawn: int) -> None:
        """Set *slot_index*'s spawn to *spawn*, swapping if occupied."""
        if spawn < 0 or spawn >= self.max_positions:
            return
        old_spawn = self.slots[slot_index].start_spot
        if old_spawn == spawn:
            return
        # Find occupant and swap
        for si, slot in enumerate(self.slots):
            if si == slot_index:
                continue
            if slot.start_spot == spawn:
                slot.start_spot = old_spawn
                logger.info("Swapped slot %d to spawn %d", si + 1, old_spawn + 1)
                break
        self.slots[slot_index].start_spot = spawn
        logger.info("Slot %d start spot set to %d", slot_index + 1, spawn + 1)

    def swap_spawns(self, idx_a: int, idx_b: int) -> None:
        """Swap spawn positions between two slots."""
        self.slots[idx_a].start_spot, self.slots[idx_b].start_spot = (
            self.slots[idx_b].start_spot,
            self.slots[idx_a].start_spot,
        )

    def first_free_spawn(self) -> int:
        """Return the first unoccupied spawn index, or -1 if all taken."""
        occupied = {s.start_spot for s in self.slots}
        for i in range(self.max_positions):
            if i not in occupied:
                return i
        return -1

    # -- Auto-balance helpers -----------------------------------------------

    def next_team(self) -> int:
        """Return the UI team number (1-4) with the fewest players.

        Ties break to the lower-numbered team.
        """
        counts: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
        for slot in self.slots:
            if slot.team in counts:
                counts[slot.team] += 1
        return min(counts, key=lambda t: (counts[t], t))

    def next_free_color(self) -> str:
        """Return the first hex color not already used by a slot."""
        used = {s.color_hex for s in self.slots}
        for hex_val, _name in PLAYER_COLORS:
            if hex_val not in used:
                return hex_val
        return PLAYER_COLORS[0][0]

    # -- Engine-format output -----------------------------------------------

    def get_human_slot(self) -> PlayerSlot | None:
        """Return the first human slot, or None."""
        for s in self.slots:
            if s.slot_type == "human":
                return s
        return None

    def get_human_color_index(self) -> int:
        """Human player's color as a 1-based SCFA index."""
        human = self.get_human_slot()
        return human.color_index if human else 1

    def get_human_team_engine(self) -> int:
        """Human player's team in engine format (UI + 1)."""
        human = self.get_human_slot()
        return human.team_engine if human else 2

    def get_human_start_spot_engine(self) -> int:
        """Human player's spawn position (1-based engine)."""
        human = self.get_human_slot()
        return human.start_spot_engine if human else 1

    def to_ai_opponents(self) -> list[dict[str, Any]]:
        """Build the AI opponents list for game_config.py."""
        opponents: list[dict[str, Any]] = []
        for slot in self.slots:
            if slot.slot_type != "ai":
                continue
            opponents.append(
                {
                    "name": slot.name,
                    "faction": slot.faction.lower(),
                    "ai": slot.ai_key,
                    "team": slot.team_engine,
                    "color": slot.color_index,
                    "start_spot": slot.start_spot_engine,
                }
            )
        return opponents
