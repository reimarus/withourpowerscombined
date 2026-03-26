"""Regression tests for AI opponent extraction from slot lists.

These tests verify that get_ai_opponents_from() correctly extracts
AI config from both solo and lobby slot structures. This is critical
because the multiplayer host previously read from the wrong slot list
(solo instead of lobby), causing game launch failures.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest


def _make_string_var(value: str) -> Any:
    """Create a mock StringVar-like object."""
    var = MagicMock()
    var.get.return_value = value
    return var


def _make_slot(
    slot_type: str,
    *,
    ai_var: str = "Medium",
    faction_var: str = "Random",
    team_var: str = "1",
    color_var: str = "#FF0000",
    start_spot: int = 0,
) -> dict[str, Any]:
    """Build a minimal slot dict matching the GUI slot structure."""
    return {
        "type": slot_type,
        "ai_var": _make_string_var(ai_var),
        "faction_var": _make_string_var(faction_var),
        "team_var": _make_string_var(team_var),
        "color_var": _make_string_var(color_var),
        "start_spot": start_spot,
        "widgets": [],
    }


@pytest.fixture()
def mock_app() -> Any:
    """Minimal mock app object."""
    app = SimpleNamespace()
    app._remote_players = {}
    app._current_map_info = None
    return app


class TestGetAiOpponentsFrom:
    """Test slot_widget.get_ai_opponents_from() with various slot lists."""

    def test_extracts_ai_from_solo_slots(self, mock_app: Any) -> None:
        """AI opponents are extracted from solo player_slots."""
        from launcher.gui.slot_widget import get_ai_opponents_from

        slots = [
            _make_slot("human"),
            _make_slot("ai", ai_var="Easy", faction_var="Aeon", team_var="2", start_spot=1),
        ]
        result = get_ai_opponents_from(mock_app, slots, engine_offset=True)
        assert len(result) == 1
        assert result[0]["ai"] == "easy"
        assert result[0]["faction"] == "aeon"
        assert result[0]["team"] == 3  # UI team 2 + engine offset 1
        assert result[0]["start_spot"] == 2  # 1 + engine offset 1

    def test_extracts_ai_from_lobby_slots(self, mock_app: Any) -> None:
        """AI opponents are extracted from lobby_player_slots (host + AIs)."""
        from launcher.gui.slot_widget import get_ai_opponents_from

        slots = [
            _make_slot("host"),  # Host slot — should be skipped
            _make_slot("ai", ai_var="Rush", faction_var="Cybran", team_var="1", start_spot=1),
            _make_slot("ai", ai_var="Turtle", faction_var="UEF", team_var="2", start_spot=2),
        ]
        result = get_ai_opponents_from(mock_app, slots, engine_offset=True)
        assert len(result) == 2
        assert result[0]["ai"] == "rush"
        assert result[1]["ai"] == "turtle"

    def test_skips_human_and_host_slots(self, mock_app: Any) -> None:
        """Only 'ai' type slots are extracted."""
        from launcher.gui.slot_widget import get_ai_opponents_from

        slots = [
            _make_slot("human"),
            _make_slot("host"),
            _make_slot("ai", ai_var="Medium"),
        ]
        result = get_ai_opponents_from(mock_app, slots)
        assert len(result) == 1

    def test_empty_slot_list(self, mock_app: Any) -> None:
        """Empty slot list returns empty opponents."""
        from launcher.gui.slot_widget import get_ai_opponents_from

        result = get_ai_opponents_from(mock_app, [])
        assert result == []

    def test_engine_offset_adds_one_to_team(self, mock_app: Any) -> None:
        """engine_offset=True adds 1 to team (UI 1 → engine 2)."""
        from launcher.gui.slot_widget import get_ai_opponents_from

        slots = [_make_slot("ai", team_var="1")]
        result_with = get_ai_opponents_from(mock_app, slots, engine_offset=True)
        result_without = get_ai_opponents_from(mock_app, slots, engine_offset=False)
        assert result_with[0]["team"] == 2
        assert result_without[0]["team"] == 1

    def test_engine_offset_adds_one_to_start_spot(self, mock_app: Any) -> None:
        """engine_offset=True adds 1 to start_spot (0-idx → 1-idx)."""
        from launcher.gui.slot_widget import get_ai_opponents_from

        slots = [_make_slot("ai", start_spot=3)]
        result = get_ai_opponents_from(mock_app, slots, engine_offset=True)
        assert result[0]["start_spot"] == 4

    def test_multiple_ais_get_sequential_names(self, mock_app: Any) -> None:
        """AI opponents get numbered names: 'AI 1: ...', 'AI 2: ...'."""
        from launcher.gui.slot_widget import get_ai_opponents_from

        slots = [
            _make_slot("ai", ai_var="Easy"),
            _make_slot("ai", ai_var="Rush"),
            _make_slot("ai", ai_var="Turtle"),
        ]
        result = get_ai_opponents_from(mock_app, slots, engine_offset=True)
        assert result[0]["name"] == "AI 1: Easy"
        assert result[1]["name"] == "AI 2: Rush"
        assert result[2]["name"] == "AI 3: Turtle"
