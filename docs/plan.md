# Current Plan

> This is a living document. It should reflect the active implementation plan at all times.

## Lifecycle

1. **When a new plan is created** in `.claude/plans/`, copy the key details here so any session (human or AI) can see what's in progress at a glance.
2. **While executing**, update the status of each step as it completes.
3. **When the final step is committed**, clear this file and replace with a brief summary of what was completed, then mark it as "No active plan."

---

## Completed: Phase 6 — Modern Multiplayer UX

**PRs:** #17 (core), #19 (tech debt), #20 (lobby buttons), #21 (auto-assign + consistency), #57-#61 (solo polish + bug fixes)

All Phase 6 items are complete:
- ✅ LAN discovery via UDP beacons
- ✅ Game browser screen with auto-discovery
- ✅ Lobby room (map, players, options, chat)
- ✅ Add AI / Change Map buttons wired
- ✅ Victory tooltips, team auto-assignment
- ✅ Solo ↔ multiplayer UI consistency
- ✅ Icon-based map markers (tinted commander icons, strategic icons)
- ✅ Spawn position selection on minimap
- ✅ Player color persistence + HSV picker
- ✅ Spawn position → ARMY_N mapping fix (gap-filling)
- ✅ Team numbering offset fix (UI→engine +1)

---

## Active: Solo Launcher Refactor — Testing, Maintainability, Stability

**Full plan:** `.claude/plans/gentle-enchanting-bengio.md`

`app.py` has grown to 4,320 lines / 105 methods. Refactoring to improve testability, eliminate duplication, and fix 3 new bugs.

### Steps (7 commits):
1. ⬜ Doc updates + backlog (Phase 1)
2. ⬜ Extract `launcher/gui/constants.py` — lookup tables + color mappings
3. ⬜ Extract `launcher/gui/models.py` — PlayerSlotManager (pure data, no widgets)
4. ⬜ Extract `launcher/gui/map_canvas.py` — canvas rendering, zoom/pan, spawn clicks
5. ⬜ Unify solo/multiplayer slot code → `launcher/gui/slot_widget.py`
6. ⬜ Bug fixes: map black screen, send logs, color palette mismatch
7. ⬜ Test coverage improvements (target 80%+ on extracted modules)

### Bug fixes included:
- Map black screen after ready check / auto-update
- "Send Logs" failure after auto-update
- Player color mismatch (PLAYER_COLORS vs SCFA engine palette)
