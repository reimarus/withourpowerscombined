"""Tests for launcher.game_prefs_repair — Game.prefs corruption detection and repair."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.game_prefs_repair import repair_game_prefs

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def prefs_dir(tmp_path: Path) -> Path:
    """Return a temporary directory simulating the SCFA prefs folder."""
    return tmp_path


def _write_prefs(prefs_dir: Path, content: str) -> Path:
    """Write content to a fake Game.prefs and return its path."""
    p = prefs_dir / "Game.prefs"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# No-op cases
# ---------------------------------------------------------------------------


class TestNoOp:
    """Cases where repair should do nothing."""

    def test_missing_file_returns_empty(self, prefs_dir: Path) -> None:
        result = repair_game_prefs(prefs_dir / "Game.prefs")
        assert result == []

    def test_clean_file_returns_empty(self, prefs_dir: Path) -> None:
        content = """\
active_mods = {
    ['9e8ea941-c306-4751-b367-a11000000502'] = true,
    ['62e2j64a-53a2-y6sg-32h5-146as555a18u3'] = true
}
Options = {
    Log = { Debug = false }
}
"""
        p = _write_prefs(prefs_dir, content)
        result = repair_game_prefs(p)
        assert result == []
        # Content unchanged
        assert p.read_text(encoding="utf-8") == content

    def test_empty_active_mods_table_returns_empty(self, prefs_dir: Path) -> None:
        content = "active_mods = { }\n"
        p = _write_prefs(prefs_dir, content)
        result = repair_game_prefs(p)
        assert result == []


# ---------------------------------------------------------------------------
# Corruption: active_mods = true/false
# ---------------------------------------------------------------------------


class TestActiveMosdBoolean:
    """Test repair of active_mods set to boolean instead of table."""

    def test_top_level_true(self, prefs_dir: Path) -> None:
        content = """\
Options = { }
active_mods = true
CPUBenchmark = 145
"""
        p = _write_prefs(prefs_dir, content)
        result = repair_game_prefs(p)
        assert len(result) == 1
        assert "active_mods" in result[0]
        repaired = p.read_text(encoding="utf-8")
        assert "active_mods = { }" in repaired
        assert "active_mods = true" not in repaired

    def test_top_level_false(self, prefs_dir: Path) -> None:
        content = "active_mods = false\n"
        p = _write_prefs(prefs_dir, content)
        result = repair_game_prefs(p)
        assert len(result) == 1
        repaired = p.read_text(encoding="utf-8")
        assert "active_mods = { }" in repaired

    def test_nested_in_profile(self, prefs_dir: Path) -> None:
        """active_mods inside a profile block should also be repaired."""
        content = """\
profile = {
    current = 1,
    profiles = {
        {
            Name = 'Player',
            active_mods = true,
            Notify_all_disabled = false
        }
    }
}
"""
        p = _write_prefs(prefs_dir, content)
        result = repair_game_prefs(p)
        assert len(result) == 1
        repaired = p.read_text(encoding="utf-8")
        assert "active_mods = { }," in repaired
        assert "active_mods = true" not in repaired

    def test_multiple_occurrences(self, prefs_dir: Path) -> None:
        """Multiple active_mods = true in different profiles."""
        content = """\
profile = {
    profiles = {
        { active_mods = true },
        { active_mods = false }
    }
}
active_mods = true
"""
        p = _write_prefs(prefs_dir, content)
        result = repair_game_prefs(p)
        assert len(result) >= 1
        repaired = p.read_text(encoding="utf-8")
        assert "active_mods = true" not in repaired
        assert "active_mods = false" not in repaired

    def test_preserves_other_content(self, prefs_dir: Path) -> None:
        """Repair should only touch the corrupted field."""
        content = """\
CPUBenchmark = 145
active_mods = true
Options = {
    Log = {
        Debug = false,
        Warn = true
    }
}
"""
        p = _write_prefs(prefs_dir, content)
        repair_game_prefs(p)
        repaired = p.read_text(encoding="utf-8")
        assert "CPUBenchmark = 145" in repaired
        assert "Debug = false" in repaired
        assert "Warn = true" in repaired

    def test_case_insensitive(self, prefs_dir: Path) -> None:
        """Handle True/False (capitalized)."""
        content = "active_mods = True\n"
        p = _write_prefs(prefs_dir, content)
        result = repair_game_prefs(p)
        assert len(result) == 1
        repaired = p.read_text(encoding="utf-8")
        assert "active_mods = { }" in repaired


# ---------------------------------------------------------------------------
# Backup behavior
# ---------------------------------------------------------------------------


class TestBackup:
    """Test that corrupted files are backed up before repair."""

    def test_backup_created(self, prefs_dir: Path) -> None:
        content = "active_mods = true\n"
        p = _write_prefs(prefs_dir, content)
        repair_game_prefs(p)
        backup = p.with_suffix(".prefs.bak")
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == content

    def test_no_backup_when_clean(self, prefs_dir: Path) -> None:
        content = "active_mods = { }\n"
        p = _write_prefs(prefs_dir, content)
        repair_game_prefs(p)
        backup = p.with_suffix(".prefs.bak")
        assert not backup.exists()
