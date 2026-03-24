"""Tests for launcher.upnp — UPnP port mapping."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from launcher import upnp


@pytest.fixture(autouse=True)
def _reset_has_upnp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure _HAS_UPNP is True for tests that mock miniupnpc."""
    monkeypatch.setattr(upnp, "_HAS_UPNP", True)


# ---------------------------------------------------------------------------
# _get_upnp
# ---------------------------------------------------------------------------


def test_get_upnp_no_library(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upnp, "_HAS_UPNP", False)
    assert upnp._get_upnp() is None


@patch("launcher.upnp.miniupnpc", create=True)
def test_get_upnp_no_devices(mock_lib: MagicMock) -> None:
    u = MagicMock()
    u.discover.return_value = 0
    mock_lib.UPnP.return_value = u
    assert upnp._get_upnp() is None


@patch("launcher.upnp.miniupnpc", create=True)
def test_get_upnp_success(mock_lib: MagicMock) -> None:
    u = MagicMock()
    u.discover.return_value = 1
    mock_lib.UPnP.return_value = u
    result = upnp._get_upnp()
    assert result is u
    u.selectigd.assert_called_once()


@patch("launcher.upnp.miniupnpc", create=True)
def test_get_upnp_exception(mock_lib: MagicMock) -> None:
    mock_lib.UPnP.side_effect = RuntimeError("router on fire")
    assert upnp._get_upnp() is None


# ---------------------------------------------------------------------------
# try_open_port
# ---------------------------------------------------------------------------


@patch("launcher.upnp._get_upnp")
def test_try_open_port_no_upnp(mock_get: MagicMock) -> None:
    mock_get.return_value = None
    assert upnp.try_open_port(15000) is False


@patch("launcher.upnp._get_upnp")
def test_try_open_port_success(mock_get: MagicMock) -> None:
    u = MagicMock()
    u.lanaddr = "192.168.1.50"
    u.addportmapping.return_value = True
    mock_get.return_value = u
    assert upnp.try_open_port(15000) is True
    u.addportmapping.assert_called_once_with(15000, "TCP", "192.168.1.50", 15000, "WOPC Lobby", "")


@patch("launcher.upnp._get_upnp")
def test_try_open_port_fails(mock_get: MagicMock) -> None:
    u = MagicMock()
    u.lanaddr = "192.168.1.50"
    u.addportmapping.return_value = False
    mock_get.return_value = u
    assert upnp.try_open_port(15000) is False


@patch("launcher.upnp._get_upnp")
def test_try_open_port_exception(mock_get: MagicMock) -> None:
    u = MagicMock()
    u.lanaddr = "192.168.1.50"
    u.addportmapping.side_effect = RuntimeError("denied")
    mock_get.return_value = u
    assert upnp.try_open_port(15000) is False


# ---------------------------------------------------------------------------
# close_port
# ---------------------------------------------------------------------------


@patch("launcher.upnp._get_upnp")
def test_close_port_no_upnp(mock_get: MagicMock) -> None:
    mock_get.return_value = None
    upnp.close_port(15000)  # should not raise


@patch("launcher.upnp._get_upnp")
def test_close_port_success(mock_get: MagicMock) -> None:
    u = MagicMock()
    mock_get.return_value = u
    upnp.close_port(15000)
    u.deleteportmapping.assert_called_once_with(15000, "TCP")


@patch("launcher.upnp._get_upnp")
def test_close_port_exception(mock_get: MagicMock) -> None:
    u = MagicMock()
    u.deleteportmapping.side_effect = RuntimeError("nope")
    mock_get.return_value = u
    upnp.close_port(15000)  # should not raise
