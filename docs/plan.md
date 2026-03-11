# Current Plan

> This is a living document. It should reflect the active implementation plan at all times.

## Lifecycle

1. **When a new plan is created** in `.claude/plans/`, copy the key details here so any session (human or AI) can see what's in progress at a glance.
2. **While executing**, update the status of each step as it completes.
3. **When the final step is committed**, clear this file and replace with a brief summary of what was completed, then mark it as "No active plan."

---

## Active Plan: Fix FAF GUI — missing panels and broken layout

**Source:** `.claude/plans/calm-doodling-honey.md`
**Branch:** TBD
**Goal:** Package FAF textures into faf_ui.scd so UI panels render correctly.

### Root Cause

`deploy.py` builds `faf_ui.scd` from 10 directories but omits `textures/` (3,801 files — DDS textures, PNG assets, skinnable layout Lua files). FAF's UI code references paths like `/textures/ui/common/game/resource-bars/...` that don't exist in the VFS. Vanilla `textures.scd` provides partial fallback but lacks FAF's custom borders, panels, faction skins, and icons. Result: blank panels, invisible controls, wrong layout.

### Steps

- [ ] Add `"textures"` to `target_dir` list in `launcher/deploy.py` (~line 156)
- [ ] Add fake textures dir + missing config keys to test fixture (`tests/conftest.py`)
- [ ] Add test verifying textures included in faf_ui.scd (`tests/test_deploy.py`)
- [ ] Run tests + lint
- [ ] Delete `C:\ProgramData\WOPC\gamedata\`, run `wopc setup`
- [ ] Verify faf_ui.scd contains texture entries (~900 MB, was 609 MB)
- [ ] Rebuild launcher exe: `python build_exe.py`
- [ ] Launch match — UI panels visible with proper FAF styling
