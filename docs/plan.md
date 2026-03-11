# Current Plan

> This is a living document. It should reflect the active implementation plan at all times.

## Lifecycle

1. **When a new plan is created** in `.claude/plans/`, copy the key details here so any session (human or AI) can see what's in progress at a glance.
2. **While executing**, update the status of each step as it completes.
3. **When the final step is committed**, clear this file and replace with a brief summary of what was completed, then mark it as "No active plan."

---

## Active Plan: Merge vanilla lua.scd into faf_ui.scd

**Source:** `.claude/plans/merge-vanilla-lua-into-faf-ui.md`
**Branch:** `feature/phase-6-advanced-launcher`
**Goal:** Resolve AI import errors by merging vanilla lua.scd files into the faf_ui.scd build.

### Steps

- [x] Modify `deploy.py` to merge vanilla `lua.scd` files into `faf_ui.scd` during build
- [x] Create stub files for FAF-specific AI imports (`gridreclaim.lua`, `sorianutilities.lua`)
- [x] Tests pass (105), ruff clean
- [ ] Verify rebuilt `faf_ui.scd` contains vanilla AI files
- [ ] Launch game and confirm AI import errors are resolved
- [ ] Commit implementation
- [ ] Update QUICKSTART_STATE.md

### Context

FAF's source repo (`vendor/faf-ui/`) only contains FAF's modifications (1157 files), not the merged distribution. The real FAF distribution includes vanilla `lua.scd` files (102 files — mostly AI). Our `deploy.py` now merges these during the `faf_ui.scd` build step, with FAF files taking priority over vanilla duplicates.
