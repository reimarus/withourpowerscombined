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
