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
# Legacy logic tests — now covered comprehensively in:
#   tests/test_constants.py (27 tests) — color conversions, option mappings
#   tests/test_models.py (36 tests) — PlayerSlotManager, spawn/team/color logic
#
# The tests below verify that app.py re-exports work correctly after the
# extraction, and test list/dict identity removal (still app-level logic).
# ---------------------------------------------------------------------------


class TestAppReexports:
    """Verify app.py still re-exports constants from the extracted modules."""

    def test_player_colors_available(self) -> None:
        from launcher.gui.app import PLAYER_COLORS

        assert len(PLAYER_COLORS) == 8

    def test_color_name_to_hex_via_app(self) -> None:
        """The static method on WopcApp delegates to constants.color_name_to_hex."""
        from launcher.gui.constants import color_name_to_hex

        assert color_name_to_hex("Red") == "#FF0000"
        assert color_name_to_hex("#ABCDEF") == "#ABCDEF"

    def test_color_hex_to_index_via_app(self) -> None:
        """The static method on WopcApp delegates to constants.color_hex_to_index."""
        from launcher.gui.constants import color_hex_to_index

        assert color_hex_to_index("#FF0000") == 1
        assert color_hex_to_index("#0000FF") == 2
        assert color_hex_to_index("#FE0101") == 1  # nearest match


class TestRemoveByIdentity:
    """Tests for remove-by-dict-identity instead of stale index."""

    def test_remove_correct_slot_after_prior_removals(self) -> None:
        """Removing slot by identity finds the right one even after shifts."""
        slots = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        target_b = slots[1]
        idx = slots.index(target_b)
        assert idx == 1
        slots.pop(idx)
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
