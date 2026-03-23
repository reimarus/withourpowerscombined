"""Tests for launcher.gui.models — PlayerSlot and PlayerSlotManager.

These tests run without any GUI or tkinter dependency.  They exercise all
the pure-logic that was extracted from app.py.
"""

from __future__ import annotations

import pytest

from launcher.gui.models import PlayerSlot, PlayerSlotManager

# ---------------------------------------------------------------------------
# PlayerSlot dataclass
# ---------------------------------------------------------------------------


class TestPlayerSlot:
    """Unit tests for the PlayerSlot dataclass and its properties."""

    def test_defaults(self) -> None:
        slot = PlayerSlot(slot_type="human")
        assert slot.name == "Player"
        assert slot.faction == "Random"
        assert slot.team == 1
        assert slot.color_hex == "#FF0000"
        assert slot.start_spot == 0
        assert slot.ai_key == "easy"

    def test_team_engine_offset(self) -> None:
        """UI team 1 → engine team 2 (Rule #14)."""
        for ui_team in range(1, 5):
            slot = PlayerSlot(slot_type="human", team=ui_team)
            assert slot.team_engine == ui_team + 1

    def test_start_spot_engine_offset(self) -> None:
        """0-based internal → 1-based engine."""
        slot = PlayerSlot(slot_type="human", start_spot=3)
        assert slot.start_spot_engine == 4

    def test_color_index_exact_match(self) -> None:
        slot = PlayerSlot(slot_type="human", color_hex="#0000FF")
        assert slot.color_index == 2  # Blue is index 2

    def test_color_index_nearest_match(self) -> None:
        slot = PlayerSlot(slot_type="human", color_hex="#FE0101")
        assert slot.color_index == 1  # Nearest to Red


# ---------------------------------------------------------------------------
# PlayerSlotManager — add / remove
# ---------------------------------------------------------------------------


class TestSlotManagerAddRemove:
    """Test adding and removing slots."""

    def test_add_human(self) -> None:
        mgr = PlayerSlotManager()
        idx = mgr.add_human(name="Alice", color_hex="#0000FF")
        assert idx == 0
        assert len(mgr.slots) == 1
        assert mgr.slots[0].slot_type == "human"
        assert mgr.slots[0].name == "Alice"

    def test_add_ai_auto_defaults(self) -> None:
        mgr = PlayerSlotManager(max_positions=8)
        mgr.add_human(start_spot=0, team=1, color_hex="#FF0000")
        idx = mgr.add_ai()
        assert idx == 1
        ai = mgr.slots[1]
        assert ai.slot_type == "ai"
        # Auto-balanced to team 2 (team 1 has the human)
        assert ai.team == 2
        # First free color (Red taken → Blue)
        assert ai.color_hex == "#0000FF"
        # First free spawn (0 taken → 1)
        assert ai.start_spot == 1

    def test_add_ai_explicit_values(self) -> None:
        mgr = PlayerSlotManager(max_positions=8)
        mgr.add_human()
        idx = mgr.add_ai(faction="UEF", team=3, color_hex="#00FF00", start_spot=5, ai_key="rush")
        ai = mgr.slots[idx]
        assert ai.faction == "UEF"
        assert ai.team == 3
        assert ai.color_hex == "#00FF00"
        assert ai.start_spot == 5
        assert ai.ai_key == "rush"

    def test_remove_ai(self) -> None:
        mgr = PlayerSlotManager(max_positions=8)
        mgr.add_human()
        mgr.add_ai()
        mgr.add_ai()
        assert len(mgr.slots) == 3
        mgr.remove(1)
        assert len(mgr.slots) == 2

    def test_remove_human_raises(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human()
        with pytest.raises(ValueError, match="Cannot remove the human"):
            mgr.remove(0)

    def test_remove_invalid_index_raises(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human()
        with pytest.raises(IndexError):
            mgr.remove(5)

    def test_remove_negative_index_raises(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human()
        with pytest.raises(IndexError):
            mgr.remove(-1)


# ---------------------------------------------------------------------------
# Spawn logic
# ---------------------------------------------------------------------------


class TestSpawnLogic:
    """Test spawn selection, swapping, and free-spawn detection."""

    def _make_manager(self, n_ai: int = 2, max_pos: int = 4) -> PlayerSlotManager:
        mgr = PlayerSlotManager(max_positions=max_pos)
        mgr.add_human(start_spot=0, color_hex="#FF0000", team=1)
        for i in range(n_ai):
            mgr.add_ai(start_spot=i + 1)
        return mgr

    def test_select_spawn_simple(self) -> None:
        mgr = self._make_manager()
        mgr.select_spawn(0, 3)  # human moves to spawn 3
        assert mgr.slots[0].start_spot == 3

    def test_select_spawn_swaps_occupant(self) -> None:
        """Clicking an occupied spawn swaps the two players."""
        mgr = self._make_manager()
        # Human at 0, AI-1 at 1, AI-2 at 2
        mgr.select_spawn(0, 1)  # human takes AI-1's spawn
        assert mgr.slots[0].start_spot == 1
        assert mgr.slots[1].start_spot == 0  # AI-1 got human's old spawn

    def test_select_spawn_no_op_if_same(self) -> None:
        mgr = self._make_manager()
        mgr.select_spawn(0, 0)  # already at 0
        assert mgr.slots[0].start_spot == 0

    def test_select_spawn_out_of_range(self) -> None:
        mgr = self._make_manager(max_pos=4)
        mgr.select_spawn(0, 10)  # out of range, no change
        assert mgr.slots[0].start_spot == 0

    def test_swap_spawns(self) -> None:
        mgr = self._make_manager()
        mgr.swap_spawns(0, 1)
        assert mgr.slots[0].start_spot == 1
        assert mgr.slots[1].start_spot == 0

    def test_first_free_spawn(self) -> None:
        mgr = self._make_manager(n_ai=2, max_pos=4)
        # Occupied: 0, 1, 2 → first free = 3
        assert mgr.first_free_spawn() == 3

    def test_first_free_spawn_none_available(self) -> None:
        mgr = self._make_manager(n_ai=3, max_pos=4)
        # Occupied: 0, 1, 2, 3 → all taken
        assert mgr.first_free_spawn() == -1

    def test_first_free_spawn_gap(self) -> None:
        """When there's a gap in the middle, finds it."""
        mgr = PlayerSlotManager(max_positions=4)
        mgr.add_human(start_spot=0)
        mgr.add_ai(start_spot=2)  # skip 1
        assert mgr.first_free_spawn() == 1


# ---------------------------------------------------------------------------
# Team auto-balance
# ---------------------------------------------------------------------------


class TestTeamBalance:
    """Test the next_team() auto-balancing."""

    def test_empty_returns_1(self) -> None:
        mgr = PlayerSlotManager()
        assert mgr.next_team() == 1

    def test_single_team_balances_to_other(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human(team=1)
        assert mgr.next_team() == 2

    def test_balanced_breaks_tie_low(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human(team=1)
        mgr.add_ai(team=2)
        # Both have 1 player, next should be team 3 (lowest with 0)
        assert mgr.next_team() == 3

    def test_all_teams_balanced(self) -> None:
        mgr = PlayerSlotManager(max_positions=8)
        for t in [1, 2, 3, 4]:
            mgr.add_ai(team=t, start_spot=t - 1)
        # All have 1, tie breaks to lowest = 1
        assert mgr.next_team() == 1


# ---------------------------------------------------------------------------
# Color auto-allocation
# ---------------------------------------------------------------------------


class TestColorAllocation:
    """Test next_free_color() allocation."""

    def test_first_slot_gets_red(self) -> None:
        mgr = PlayerSlotManager()
        assert mgr.next_free_color() == "#FF0000"

    def test_skips_used_colors(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human(color_hex="#FF0000")  # Red taken
        assert mgr.next_free_color() == "#0000FF"  # Blue is next

    def test_all_taken_wraps_to_first(self) -> None:
        mgr = PlayerSlotManager(max_positions=16)
        from launcher.gui.constants import PLAYER_COLORS

        for i, (hex_val, _) in enumerate(PLAYER_COLORS):
            mgr.add_ai(color_hex=hex_val, start_spot=i)
        # All 8 used → returns first
        assert mgr.next_free_color() == "#FF0000"


# ---------------------------------------------------------------------------
# Engine-format output
# ---------------------------------------------------------------------------


class TestEngineOutput:
    """Test engine-format conversion methods."""

    def test_get_human_slot(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human(name="Test")
        assert mgr.get_human_slot() is not None
        assert mgr.get_human_slot().name == "Test"  # type: ignore[union-attr]

    def test_get_human_slot_none(self) -> None:
        mgr = PlayerSlotManager()
        assert mgr.get_human_slot() is None

    def test_human_color_index(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human(color_hex="#0000FF")
        assert mgr.get_human_color_index() == 2  # Blue

    def test_human_team_engine(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human(team=3)
        assert mgr.get_human_team_engine() == 4  # UI 3 → engine 4

    def test_human_start_spot_engine(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human(start_spot=5)
        assert mgr.get_human_start_spot_engine() == 6  # 0-based 5 → 1-based 6

    def test_to_ai_opponents(self) -> None:
        mgr = PlayerSlotManager(max_positions=8)
        mgr.add_human(start_spot=0, team=1, color_hex="#FF0000")
        mgr.add_ai(
            faction="UEF",
            team=2,
            color_hex="#0000FF",
            start_spot=3,
            ai_key="medium",
            name="AI 1: Medium",
        )
        opponents = mgr.to_ai_opponents()
        assert len(opponents) == 1
        ai = opponents[0]
        assert ai["name"] == "AI 1: Medium"
        assert ai["faction"] == "uef"
        assert ai["ai"] == "medium"
        assert ai["team"] == 3  # UI 2 → engine 3
        assert ai["color"] == 2  # Blue is index 2
        assert ai["start_spot"] == 4  # 0-based 3 → 1-based 4

    def test_to_ai_opponents_multiple(self) -> None:
        mgr = PlayerSlotManager(max_positions=8)
        mgr.add_human(start_spot=0)
        mgr.add_ai(start_spot=1, ai_key="easy")
        mgr.add_ai(start_spot=2, ai_key="rush")
        opponents = mgr.to_ai_opponents()
        assert len(opponents) == 2
        assert opponents[0]["ai"] == "easy"
        assert opponents[1]["ai"] == "rush"

    def test_to_ai_opponents_skips_human(self) -> None:
        mgr = PlayerSlotManager()
        mgr.add_human()
        opponents = mgr.to_ai_opponents()
        assert len(opponents) == 0


# ---------------------------------------------------------------------------
# Integration: realistic 4-player setup
# ---------------------------------------------------------------------------


class TestRealisticSetup:
    """Test a realistic game setup scenario end-to-end."""

    def test_4_player_2v2(self) -> None:
        """Set up a 2v2 game and verify all engine output."""
        mgr = PlayerSlotManager(max_positions=8)

        # Human on team 1 at spawn 0
        mgr.add_human(name="Player", team=1, color_hex="#FF0000", start_spot=0)

        # AI ally on team 1 at spawn 2
        mgr.add_ai(team=1, color_hex="#DFBF00", start_spot=2, ai_key="medium")

        # Two enemies on team 2
        mgr.add_ai(team=2, color_hex="#0000FF", start_spot=1, ai_key="adaptive")
        mgr.add_ai(team=2, color_hex="#18DAE8", start_spot=3, ai_key="rush")

        assert len(mgr.slots) == 4
        assert mgr.get_human_team_engine() == 2  # UI 1 → engine 2
        assert mgr.get_human_start_spot_engine() == 1  # 0-based 0 → 1-based 1
        assert mgr.get_human_color_index() == 1  # Red

        opponents = mgr.to_ai_opponents()
        assert len(opponents) == 3

        # Verify team offsets
        assert opponents[0]["team"] == 2  # UI team 1 → engine 2
        assert opponents[1]["team"] == 3  # UI team 2 → engine 3
        assert opponents[2]["team"] == 3  # UI team 2 → engine 3

        # Verify start spots (1-based)
        assert opponents[0]["start_spot"] == 3  # 0-based 2 → 1-based 3
        assert opponents[1]["start_spot"] == 2  # 0-based 1 → 1-based 2
        assert opponents[2]["start_spot"] == 4  # 0-based 3 → 1-based 4
