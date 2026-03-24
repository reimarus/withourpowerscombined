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

## Completed: Solo Launcher Refactor (PRs #63, #65-#68)

Refactored `app.py` from 4,320 → 1,913 lines (56% reduction). Extracted 6 modules: `constants.py`, `models.py`, `map_canvas.py`, `slot_widget.py`, `browser_screen.py`, `lobby_screen.py`. Fixed bugs #50 (map black screen), #51 (Send Logs), #52 (color palette mismatch), #53 (map list after restart).

---

## No active plan.

Next candidates (see `docs/backlog.md`):
- Bug #57: Spawn markers not auto-assigned on initial load
- Bug #59: Multiplayer NAT traversal (UPnP)
- Bug #60: Structured launch logging
- Feature #25: SC2-style unit movement (Phase 7)
