# Current Plan

> This is a living document. It should reflect the active implementation plan at all times.

## Lifecycle

1. **When a new plan is created** in `.claude/plans/`, copy the key details here so any session (human or AI) can see what's in progress at a glance.
2. **While executing**, update the status of each step as it completes.
3. **When the final step is committed**, clear this file and replace with a brief summary of what was completed, then mark it as "No active plan."

---

## Active Plan: Fix match loading — ZIP case normalization

**Source:** `.claude/plans/calm-doodling-honey.md`
**Branch:** `fix/match-loading-bugs`
**Goal:** Fix commander spawn failures and UI errors by normalizing filenames to lowercase in all SCD builds.

### Root Cause

833 of 1264 files in `faf_ui.scd` have mixed-case names (e.g., `lua/sim/Unit.lua`). FAF's `import()` lowercases all paths (line 116: `name = name:lower()`), but ZIP lookups are case-sensitive. Result: imports silently fail → nil → cascade of errors (no Unit class, no StructureUnit, no commanders, broken weapons).

### Steps

- [ ] Normalize filenames to lowercase in faf_ui.scd build (`deploy.py` lines 156-159)
- [ ] Normalize vanilla lua.scd merged files to lowercase (`deploy.py` line 175)
- [ ] Normalize wopc_patches.scd build (`deploy.py` lines 189-192)
- [ ] Update `_patch_scd()` calls to use lowercase arcnames
- [ ] Update tests
- [ ] Verify 0 mixed-case files in built faf_ui.scd
- [ ] Deploy + launch game — commanders spawn, no import errors
