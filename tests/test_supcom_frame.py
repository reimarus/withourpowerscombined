"""Tests for launcher.gui.supcom_frame — 9-slice metallic frame widget."""

from __future__ import annotations

import pytest

from launcher.gui import supcom_frame


def test_load_frame_parts_no_pil(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns None when PIL is unavailable."""
    monkeypatch.setattr(supcom_frame, "_PIL_OK", False)
    assert supcom_frame._load_frame_parts() is None


def test_load_frame_parts_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    """Returns None when frame PNGs are missing."""
    monkeypatch.setattr(supcom_frame, "_ICONS_DIR", tmp_path)
    assert supcom_frame._load_frame_parts() is None


def test_get_parts_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """_get_parts() caches the result after first call."""
    monkeypatch.setattr(supcom_frame, "_frame_parts", False)
    sentinel = {"test": True}
    monkeypatch.setattr(supcom_frame, "_load_frame_parts", lambda: sentinel)
    result = supcom_frame._get_parts()
    assert result is sentinel
    # Second call returns cached value
    assert supcom_frame._frame_parts is sentinel


def test_get_parts_returns_none_when_no_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_get_parts() returns None when assets can't be loaded."""
    monkeypatch.setattr(supcom_frame, "_frame_parts", False)
    monkeypatch.setattr(supcom_frame, "_load_frame_parts", lambda: None)
    assert supcom_frame._get_parts() is None


def test_constants() -> None:
    """Edge thickness and corner size are reasonable."""
    assert supcom_frame._CORNER > 0
    assert supcom_frame._EDGE_THICKNESS > 0
    assert supcom_frame._CORNER > supcom_frame._EDGE_THICKNESS
