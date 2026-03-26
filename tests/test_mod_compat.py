"""Tests for launcher.mod_compat — LOUD-era mod compatibility patches."""

from __future__ import annotations

from pathlib import Path

from launcher.mod_compat import apply_mod_compat_patches


def _write_lua(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_patch_replaces_old_text(tmp_path: Path) -> None:
    """The LOUD BrewLANLOUDPath() call is replaced with literal path."""
    mods = tmp_path / "mods"
    lua = mods / "BrewLAN_LOUD" / "hook" / "lua" / "factions.lua"
    _write_lua(
        lua,
        "if not import(import( '/lua/game.lua' ).BrewLANLOUDPath()"
        " .. '/lua/legacy/VersionCheck.lua').VersionIsSC() then\n",
    )

    count = apply_mod_compat_patches(mods)

    assert count == 1
    result = lua.read_text(encoding="utf-8")
    assert "BrewLANLOUDPath" not in result
    assert "'/mods/BrewLAN_LOUD'" in result


def test_patch_replaces_no_space_variant(tmp_path: Path) -> None:
    """The no-space variant is also replaced."""
    mods = tmp_path / "mods"
    lua = mods / "BrewLAN_LOUD" / "lua" / "weapons.lua"
    _write_lua(
        lua,
        "local beams = import(import('/lua/game.lua').BrewLANLOUDPath() .. '/lua/beams.lua')\n",
    )

    count = apply_mod_compat_patches(mods)

    assert count == 1
    result = lua.read_text(encoding="utf-8")
    assert "import('/lua/game.lua').BrewLANLOUDPath()" not in result
    assert "'/mods/BrewLAN_LOUD'" in result


def test_patch_idempotent(tmp_path: Path) -> None:
    """Running the patcher twice doesn't double-modify files."""
    mods = tmp_path / "mods"
    lua = mods / "BrewLAN_LOUD" / "hook" / "lua" / "factions.lua"
    _write_lua(
        lua,
        "import( '/lua/game.lua' ).BrewLANLOUDPath()\n",
    )

    count1 = apply_mod_compat_patches(mods)
    text_after_first = lua.read_text(encoding="utf-8")
    count2 = apply_mod_compat_patches(mods)
    text_after_second = lua.read_text(encoding="utf-8")

    assert count1 == 1
    assert count2 == 0  # Already patched, nothing to do
    assert text_after_first == text_after_second


def test_patch_skips_missing_mod(tmp_path: Path) -> None:
    """If the mod directory doesn't exist, returns 0 with no error."""
    mods = tmp_path / "mods"
    mods.mkdir()
    # No BrewLAN_LOUD directory

    count = apply_mod_compat_patches(mods)
    assert count == 0


def test_patch_skips_missing_mods_dir(tmp_path: Path) -> None:
    """If the mods root doesn't exist, returns 0 with no error."""
    count = apply_mod_compat_patches(tmp_path / "nonexistent")
    assert count == 0


def test_patch_counts_multiple_files(tmp_path: Path) -> None:
    """Counts each file patched, not each patch entry."""
    mods = tmp_path / "mods"
    for name in ["a.lua", "b.lua", "c.lua"]:
        _write_lua(
            mods / "BrewLAN_LOUD" / name,
            f"-- {name}\nimport( '/lua/game.lua' ).BrewLANLOUDPath()\n",
        )
    # One file without the pattern
    _write_lua(mods / "BrewLAN_LOUD" / "clean.lua", "-- already clean\n")

    count = apply_mod_compat_patches(mods)
    assert count == 3


def test_patch_both_variants_in_one_file(tmp_path: Path) -> None:
    """A file with both space and no-space variants gets both replaced."""
    mods = tmp_path / "mods"
    lua = mods / "BrewLAN_LOUD" / "mixed.lua"
    _write_lua(
        lua,
        "local a = import( '/lua/game.lua' ).BrewLANLOUDPath()\n"
        "local b = import('/lua/game.lua').BrewLANLOUDPath()\n",
    )

    count = apply_mod_compat_patches(mods)

    # Both patches matched the same file — counted twice (once per patch entry)
    assert count == 2
    result = lua.read_text(encoding="utf-8")
    assert "BrewLANLOUDPath" not in result
    assert result.count("'/mods/BrewLAN_LOUD'") == 2
