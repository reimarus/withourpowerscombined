import pytest

try:
    import customtkinter  # noqa: F401

    HAS_CTK = True
except ImportError:
    HAS_CTK = False

from launcher.gui.worker import SetupWorker

# GUI tests require customtkinter — skip in headless CI where it's not installed
pytestmark_ctk = pytest.mark.skipif(not HAS_CTK, reason="customtkinter not installed")


@pytestmark_ctk
def test_launch_gui_mocks_mainloop(mocker):
    """Test that launch_gui instantiates WopcApp and calls mainloop without rendering."""
    from launcher.gui.app import WopcApp, launch_gui

    # Mock the CTk base class to prevent actual window creation in headless CI
    mock_ctk = mocker.patch("launcher.gui.app.ctk.CTk")
    mock_app_instance = mocker.MagicMock()
    mock_ctk.return_value = mock_app_instance

    # We still want to test our WopcApp's __init__ logic, so let's mock just mainloop
    mocker.patch.object(WopcApp, "mainloop")

    # We should also mock the installation status checking so it doesn't fail
    mocker.patch.object(WopcApp, "_check_installation_status")

    launch_gui()
    WopcApp.mainloop.assert_called_once()


@pytestmark_ctk
def test_wopc_app_initialization(mocker):
    """Test the GUI components are built correctly."""
    from launcher.gui.app import WopcApp

    mocker.patch.object(WopcApp, "bind")
    mocker.patch("launcher.gui.app.ctk.CTk")

    app = WopcApp()

    # Verify primary view pieces were created
    assert hasattr(app, "sidebar")
    assert hasattr(app, "main_content")
    assert hasattr(app, "primary_btn")
    assert hasattr(app, "log_textbox")

    # Verify hotkeys were bound
    assert app.bind.call_count >= 2
    app.bind.assert_any_call("<Return>", mocker.ANY)
    app.bind.assert_any_call("<Escape>", mocker.ANY)


def test_setup_worker_success(mocker):
    """Test the SetupWorker thread logic on success."""
    mocker.patch("launcher.gui.worker.run_setup", return_value=None)

    mock_complete = mocker.MagicMock()
    mock_log = mocker.MagicMock()

    worker = SetupWorker(mock_complete, mock_log)
    worker.run()

    mock_complete.assert_called_once_with(True)
    # Check it logged success
    mock_log.assert_any_call("Deployment completed successfully!")


def test_setup_worker_failure(mocker):
    """Test the SetupWorker thread logic on failure."""
    mocker.patch("launcher.gui.worker.run_setup", side_effect=Exception("Failed"))

    mock_complete = mocker.MagicMock()
    mock_log = mocker.MagicMock()

    worker = SetupWorker(mock_complete, mock_log)
    worker.run()

    mock_complete.assert_called_once_with(False)
    mock_log.assert_any_call("Critical error during setup: Failed")
