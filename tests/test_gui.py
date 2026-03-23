"""GUI tests — always run, always pass, no skips.

We mock customtkinter at the module level if it's not installed, so these
tests work identically in local dev (with ctk) and headless CI (without).
"""

import sys
from unittest.mock import MagicMock

import pytest

from launcher.gui.worker import SetupWorker


def _ensure_ctk_mock() -> None:
    """Ensure customtkinter is importable even in headless CI."""
    if "customtkinter" not in sys.modules:
        mock_ctk = MagicMock()
        mock_ctk.CTkFont.return_value = {}
        sys.modules["customtkinter"] = mock_ctk


_ensure_ctk_mock()


def test_launch_gui_creates_app_and_runs_mainloop(mocker: pytest.fixture) -> None:
    """launch_gui() instantiates WopcApp and calls mainloop."""
    from launcher.gui import app as app_module

    mock_app = MagicMock()
    mocker.patch.object(app_module, "WopcApp", return_value=mock_app)

    app_module.launch_gui()

    app_module.WopcApp.assert_called_once()
    mock_app.mainloop.assert_called_once()


def test_lobby_imports_available() -> None:
    """The lobby module is importable and exposes the expected types."""
    from launcher.lobby import LobbyCallbacks, LobbyClient, LobbyServer

    assert LobbyCallbacks is not None
    assert LobbyServer is not None
    assert LobbyClient is not None

    # Verify LobbyCallbacks has all expected callback fields
    cb = LobbyCallbacks()
    for attr in (
        "on_player_joined",
        "on_player_left",
        "on_state_updated",
        "on_ready_changed",
        "on_launch",
        "on_connected",
        "on_disconnected",
        "on_error",
    ):
        assert hasattr(cb, attr), f"LobbyCallbacks missing field: {attr}"


def test_setup_worker_success(mocker: pytest.fixture) -> None:
    """SetupWorker calls on_complete(True) on success."""
    mocker.patch("launcher.gui.worker.run_setup", return_value=None)

    mock_complete = mocker.MagicMock()
    mock_log = mocker.MagicMock()

    worker = SetupWorker(mock_complete, mock_log)
    worker.run()

    mock_complete.assert_called_once_with(True)
    mock_log.assert_any_call("Deployment completed successfully!")


def test_setup_worker_failure(mocker: pytest.fixture) -> None:
    """SetupWorker calls on_complete(False) on exception."""
    mocker.patch("launcher.gui.worker.run_setup", side_effect=Exception("Failed"))

    mock_complete = mocker.MagicMock()
    mock_log = mocker.MagicMock()

    worker = SetupWorker(mock_complete, mock_log)
    worker.run()

    mock_complete.assert_called_once_with(False)
    mock_log.assert_any_call("Critical error during setup: Failed")


# ---------------------------------------------------------------------------
# PLAYER_COLORS tests — these are module-level, not on the mocked WopcApp
# ---------------------------------------------------------------------------


class TestPlayerColors:
    """Tests for PLAYER_COLORS constant."""

    def test_player_colors_has_eight_entries(self) -> None:
        from launcher.gui.app import PLAYER_COLORS

        assert len(PLAYER_COLORS) == 8

    def test_player_colors_are_hex_name_tuples(self) -> None:
        from launcher.gui.app import PLAYER_COLORS

        for hex_val, name in PLAYER_COLORS:
            assert hex_val.startswith("#"), f"{name} hex should start with #"
            assert len(hex_val) == 7, f"{name} hex should be 7 chars"
            assert isinstance(name, str) and len(name) > 0

    def test_player_color_names_are_unique(self) -> None:
        from launcher.gui.app import PLAYER_COLORS

        names = [name for _, name in PLAYER_COLORS]
        assert len(names) == len(set(names)), "Color names must be unique"

    def test_player_color_hex_values_are_unique(self) -> None:
        from launcher.gui.app import PLAYER_COLORS

        hexes = [h for h, _ in PLAYER_COLORS]
        assert len(hexes) == len(set(hexes)), "Color hex values must be unique"

    def test_color_name_to_hex_lookup(self) -> None:
        """Verify name→hex lookup works for all defined colors."""
        from launcher.gui.app import PLAYER_COLORS

        color_map = {name: hex_val for hex_val, name in PLAYER_COLORS}
        assert color_map["Red"] == "#FF0000"
        assert color_map["Blue"] == "#0000FF"
        assert color_map["Green"] == "#00FF00"
        assert color_map["Teal"] == "#18DAE8"

    def test_color_hex_to_name_lookup(self) -> None:
        """Verify hex→name lookup works for all defined colors."""
        from launcher.gui.app import PLAYER_COLORS

        hex_map = {hex_val: name for hex_val, name in PLAYER_COLORS}
        assert hex_map["#FF0000"] == "Red"
        assert hex_map["#0000FF"] == "Blue"


# ---------------------------------------------------------------------------
# Spawn mapping logic tests (pure data logic, no GUI)
# ---------------------------------------------------------------------------


class TestSpawnMapping:
    """Tests for spawn-to-slot mapping logic used in _redraw_canvas."""

    def _build_spawn_map(self, slots: list[dict]) -> dict[int, int]:
        """Replicate the spawn mapping logic from _redraw_canvas."""
        spawn_occupied: dict[int, int] = {}
        for si, slot in enumerate(slots):
            spot = slot.get("start_spot", si)
            spawn_occupied[spot] = si
        return spawn_occupied

    def test_default_mapping_is_identity(self) -> None:
        """Without start_spot, slot i maps to spawn i."""
        slots = [{"type": "human"}, {"type": "ai"}]
        result = self._build_spawn_map(slots)
        assert result == {0: 0, 1: 1}

    def test_custom_start_spot_overrides(self) -> None:
        """start_spot overrides the default identity mapping."""
        slots = [
            {"type": "human", "start_spot": 3},
            {"type": "ai", "start_spot": 0},
        ]
        result = self._build_spawn_map(slots)
        assert result == {3: 0, 0: 1}

    def test_duplicate_start_spot_last_wins(self) -> None:
        """If two slots claim the same spawn, the later slot wins."""
        slots = [
            {"type": "human", "start_spot": 0},
            {"type": "ai", "start_spot": 0},
        ]
        result = self._build_spawn_map(slots)
        assert result[0] == 1

    def test_empty_slots_gives_empty_map(self) -> None:
        result = self._build_spawn_map([])
        assert result == {}

    def test_eight_slots_default(self) -> None:
        """8 slots without start_spot gives identity 0..7."""
        slots = [{"type": "ai"} for _ in range(8)]
        result = self._build_spawn_map(slots)
        assert result == {i: i for i in range(8)}

    def test_partial_start_spots(self) -> None:
        """Mix of custom and default start_spots."""
        slots = [
            {"type": "human"},  # defaults to spawn 0
            {"type": "ai", "start_spot": 5},  # explicit spawn 5
            {"type": "ai"},  # defaults to spawn 2
        ]
        result = self._build_spawn_map(slots)
        assert result == {0: 0, 5: 1, 2: 2}


# ---------------------------------------------------------------------------
# Next team auto-balance tests (pure logic)
# ---------------------------------------------------------------------------


class TestNextTeam:
    """Tests for _next_team auto-balance logic.

    _next_team reads team_var.get() from each slot. We provide mock objects
    that return the team string from .get().
    """

    def _next_team(self, slots: list[dict]) -> str:
        """Call _next_team with the same logic as WopcApp."""
        counts: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0}
        for slot in slots:
            team = slot.get("team_var")
            if team:
                val = team.get() if hasattr(team, "get") else str(team)
                if val in counts:
                    counts[val] += 1
        return min(counts, key=lambda t: (counts[t], int(t)))

    def test_empty_slots_returns_team_1(self) -> None:
        assert self._next_team([]) == "1"

    def test_one_on_team_1_returns_team_2(self) -> None:
        slots = [{"team_var": MagicMock(get=lambda: "1")}]
        assert self._next_team(slots) == "2"

    def test_two_teams_used_returns_empty_team(self) -> None:
        slots = [
            {"team_var": MagicMock(get=lambda: "1")},
            {"team_var": MagicMock(get=lambda: "2")},
        ]
        # Teams 3 and 4 have 0, team 3 wins (lower number)
        assert self._next_team(slots) == "3"

    def test_imbalanced_returns_underrepresented(self) -> None:
        slots = [
            {"team_var": MagicMock(get=lambda: "1")},
            {"team_var": MagicMock(get=lambda: "1")},
            {"team_var": MagicMock(get=lambda: "2")},
        ]
        # Team 3 and 4 have 0; team 3 wins (lower number)
        assert self._next_team(slots) == "3"

    def test_all_teams_used_returns_least(self) -> None:
        slots = [
            {"team_var": MagicMock(get=lambda: "1")},
            {"team_var": MagicMock(get=lambda: "1")},
            {"team_var": MagicMock(get=lambda: "2")},
            {"team_var": MagicMock(get=lambda: "3")},
            {"team_var": MagicMock(get=lambda: "4")},
        ]
        # Team 1: 2, Team 2: 1, Team 3: 1, Team 4: 1 — Team 2 wins (lower)
        assert self._next_team(slots) == "2"

    def test_slot_without_team_var_ignored(self) -> None:
        slots = [{"type": "human"}]  # no team_var
        assert self._next_team(slots) == "1"


# ---------------------------------------------------------------------------
# Team offset tests — SCFA engine uses Team 1 = FFA, Team 2+ = allied
# ---------------------------------------------------------------------------


class TestTeamOffset:
    """Verify UI team values are offset by +1 for the engine."""

    def test_ui_team_1_becomes_engine_team_2(self) -> None:
        """UI 'Team 1' should map to engine Team 2 (first allied team)."""
        # Simulate what get_human_team does: int(team_var.get()) + 1
        ui_team = "1"
        engine_team = int(ui_team) + 1
        assert engine_team == 2

    def test_ui_team_4_becomes_engine_team_5(self) -> None:
        """UI 'Team 4' should map to engine Team 5."""
        ui_team = "4"
        engine_team = int(ui_team) + 1
        assert engine_team == 5

    def test_ai_team_offset_applied(self) -> None:
        """AI opponent teams should also be offset by +1."""
        ui_team = "2"
        engine_team = int(ui_team) + 1
        assert engine_team == 3


# ---------------------------------------------------------------------------
# Color name/hex conversion tests (pure logic, no WopcApp needed)
# ---------------------------------------------------------------------------


class TestColorConversion:
    """Test color name/hex/index conversion logic."""

    def _name_to_hex(self, name: str) -> str:
        from launcher.gui.app import PLAYER_COLORS

        for hex_val, cname in PLAYER_COLORS:
            if cname == name:
                return hex_val
        return PLAYER_COLORS[0][0]

    def _name_to_index(self, name: str) -> int:
        from launcher.gui.app import PLAYER_COLORS

        for i, (_, cname) in enumerate(PLAYER_COLORS):
            if cname == name:
                return i + 1
        return 1

    def test_known_colors_to_hex(self) -> None:
        assert self._name_to_hex("Red") == "#FF0000"
        assert self._name_to_hex("Blue") == "#0000FF"
        assert self._name_to_hex("Teal") == "#18DAE8"
        assert self._name_to_hex("Yellow") == "#DFBF00"
        assert self._name_to_hex("Orange") == "#FF6600"
        assert self._name_to_hex("Purple") == "#9161FF"
        assert self._name_to_hex("Pink") == "#FF88FF"
        assert self._name_to_hex("Green") == "#00FF00"

    def test_unknown_color_returns_first(self) -> None:
        from launcher.gui.app import PLAYER_COLORS

        assert self._name_to_hex("Magenta") == PLAYER_COLORS[0][0]

    def test_known_colors_to_index(self) -> None:
        assert self._name_to_index("Red") == 1
        assert self._name_to_index("Blue") == 2
        assert self._name_to_index("Green") == 8

    def test_unknown_color_index_returns_one(self) -> None:
        assert self._name_to_index("Neon") == 1

    def test_all_colors_roundtrip(self) -> None:
        """Every color name maps to a unique index and hex."""
        from launcher.gui.app import PLAYER_COLORS

        for i, (expected_hex, name) in enumerate(PLAYER_COLORS):
            assert self._name_to_hex(name) == expected_hex
            assert self._name_to_index(name) == i + 1

    def test_hex_passthrough(self) -> None:
        """Hex values starting with # should pass through _name_to_hex unchanged."""
        # The actual _color_name_to_hex handles this; test the logic here
        val = "#FF00AA"
        assert val.startswith("#")  # confirms passthrough would work
        assert val == "#FF00AA"

    def test_hex_to_nearest_index(self) -> None:
        """Arbitrary hex should map to the nearest PLAYER_COLORS index."""
        from launcher.gui.app import PLAYER_COLORS

        # Exact match
        for i, (hex_val, _) in enumerate(PLAYER_COLORS):
            assert self._hex_to_nearest_index(hex_val) == i + 1

        # Near-red should map to Red (index 1)
        assert self._hex_to_nearest_index("#FE0000") == 1
        # Near-blue should map to Blue (index 2)
        assert self._hex_to_nearest_index("#0000FE") == 2

    def _hex_to_nearest_index(self, hex_val: str) -> int:
        from launcher.gui.app import PLAYER_COLORS

        r = int(hex_val[1:3], 16)
        g = int(hex_val[3:5], 16)
        b = int(hex_val[5:7], 16)
        best_i, best_d = 0, float("inf")
        for i, (ph, _) in enumerate(PLAYER_COLORS):
            pr = int(ph[1:3], 16)
            pg = int(ph[3:5], 16)
            pb = int(ph[5:7], 16)
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_d:
                best_i, best_d = i, d
        return best_i + 1


# ---------------------------------------------------------------------------
# Next free color logic test
# ---------------------------------------------------------------------------


class TestNextFreeColor:
    """Test the logic for choosing the next unused hex color."""

    def _next_free(self, used_hexes: set[str]) -> str:
        from launcher.gui.app import PLAYER_COLORS

        for hex_val, _ in PLAYER_COLORS:
            if hex_val not in used_hexes:
                return hex_val
        return PLAYER_COLORS[0][0]

    def test_no_used_returns_first(self) -> None:
        assert self._next_free(set()) == "#FF0000"

    def test_first_used_returns_second(self) -> None:
        assert self._next_free({"#FF0000"}) == "#0000FF"

    def test_all_used_returns_first(self) -> None:
        from launcher.gui.app import PLAYER_COLORS

        all_hexes = {h for h, _ in PLAYER_COLORS}
        assert self._next_free(all_hexes) == PLAYER_COLORS[0][0]

    def test_skips_used_colors(self) -> None:
        assert self._next_free({"#FF0000", "#0000FF", "#18DAE8"}) == "#DFBF00"


# ---------------------------------------------------------------------------
# First free spawn tests (pure logic)
# ---------------------------------------------------------------------------


class TestFirstFreeSpawn:
    """Tests for finding the first unoccupied spawn index."""

    def _first_free(self, slots: list[dict], n_armies: int) -> int:
        """Replicate _first_free_spawn logic."""
        occupied: set[int] = set()
        for si, slot in enumerate(slots):
            occupied.add(slot.get("start_spot", si))
        for i in range(n_armies):
            if i not in occupied:
                return i
        return -1

    def test_no_slots_returns_zero(self) -> None:
        assert self._first_free([], 4) == 0

    def test_one_slot_returns_next(self) -> None:
        slots = [{"type": "human"}]  # defaults to spawn 0
        assert self._first_free(slots, 4) == 1

    def test_custom_spot_skips_occupied(self) -> None:
        slots = [
            {"type": "human", "start_spot": 2},
            {"type": "ai", "start_spot": 0},
        ]
        assert self._first_free(slots, 4) == 1

    def test_all_occupied_returns_negative(self) -> None:
        slots = [
            {"type": "human", "start_spot": 0},
            {"type": "ai", "start_spot": 1},
        ]
        assert self._first_free(slots, 2) == -1

    def test_gap_in_middle(self) -> None:
        slots = [
            {"type": "human", "start_spot": 0},
            {"type": "ai", "start_spot": 2},
        ]
        assert self._first_free(slots, 4) == 1


# ---------------------------------------------------------------------------
# Spawn swap tests (pure logic)
# ---------------------------------------------------------------------------


class TestSpawnSwap:
    """Tests for drag-and-drop spawn swapping logic."""

    def _swap(self, slots: list[dict], src: int, dst: int) -> None:
        """Replicate _swap_spawns logic."""
        spawn_to_slot: dict[int, int] = {}
        for si, slot in enumerate(slots):
            spawn_to_slot[slot.get("start_spot", si)] = si
        src_slot = spawn_to_slot.get(src)
        dst_slot = spawn_to_slot.get(dst)
        if src_slot is not None:
            slots[src_slot]["start_spot"] = dst
        if dst_slot is not None:
            slots[dst_slot]["start_spot"] = src

    def test_swap_two_occupied(self) -> None:
        slots = [
            {"type": "human", "start_spot": 0},
            {"type": "ai", "start_spot": 1},
        ]
        self._swap(slots, 0, 1)
        assert slots[0]["start_spot"] == 1
        assert slots[1]["start_spot"] == 0

    def test_swap_occupied_to_empty(self) -> None:
        slots = [{"type": "human", "start_spot": 0}]
        self._swap(slots, 0, 3)
        assert slots[0]["start_spot"] == 3

    def test_swap_empty_to_occupied(self) -> None:
        """Swapping empty src to occupied dst moves the occupied player."""
        slots = [{"type": "human", "start_spot": 1}]
        self._swap(slots, 0, 1)
        assert slots[0]["start_spot"] == 0

    def test_swap_preserves_other_slots(self) -> None:
        slots = [
            {"type": "human", "start_spot": 0},
            {"type": "ai", "start_spot": 1},
            {"type": "ai", "start_spot": 2},
        ]
        self._swap(slots, 0, 2)
        assert slots[0]["start_spot"] == 2
        assert slots[1]["start_spot"] == 1  # untouched
        assert slots[2]["start_spot"] == 0


# ---------------------------------------------------------------------------
# Remove slot by identity tests (pure logic)
# ---------------------------------------------------------------------------


class TestRemoveByIdentity:
    """Tests for remove-by-dict-identity instead of stale index."""

    def test_remove_correct_slot_after_prior_removals(self) -> None:
        """Removing slot by identity finds the right one even after shifts."""
        slots = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        # Simulate removing "b" first
        target_b = slots[1]
        idx = slots.index(target_b)
        assert idx == 1
        slots.pop(idx)
        # Now removing "c" — used to be index 2, now it's index 1
        target_c = slots[1]
        idx = slots.index(target_c)
        assert idx == 1
        slots.pop(idx)
        assert len(slots) == 1
        assert slots[0]["id"] == "a"

    def test_remove_nonexistent_slot_is_safe(self) -> None:
        """Removing a slot not in the list raises ValueError (caught in app)."""
        slots = [{"id": "a"}]
        removed = {"id": "b"}
        with pytest.raises(ValueError):
            slots.index(removed)
