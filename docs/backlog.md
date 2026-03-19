# Backlog

Items to tackle over time, roughly grouped by priority.

## Multiplayer UX (Phase 6 — in progress)

1. ~~**"Add AI" in multiplayer lobby**~~ ✅ — wired to lobby screen with proper slot management
2. ~~**"Change Map" in multiplayer lobby**~~ ✅ — searchable map picker dialog
3. ~~**Remove players from solo screen**~~ ✅ — AI slots have ✕ remove buttons (human slot 1 is protected)
4. ~~**Victory type tooltips**~~ ✅ — descriptions shown on both solo and multiplayer screens
5. ~~**Team auto-assignment**~~ ✅ — new AI slots auto-balanced to team with fewest players via `_next_team()`
6. **Player ratings / balancing** — track skill ratings for fairer matchmaking (ELO or similar)
7. **UI polish** — modern styling, better spacing, visual hierarchy, fancier look overall
8. ~~**Solo ↔ multiplayer UI consistency**~~ ✅ — lobby options now reuse `GAME_OPTION_DEFS`, matching labels/values/defaults; headers and button styles unified

## Features

9. **Map Library Browser** — searchable map library where players can browse, preview, and download maps (replaces flat list)
10. **Mini-map size persistence** — remember the user's preferred mini-map size between sessions
11. **Merge LOUD unit mods** — BrewLAN, TotalMayhem, etc. (BlackOps done ✅, though some strategic icons still missing: brb1302, brb1106, brb2306, brb4309, brb4401)
12. **Save game function** — save/load mid-game
13. **Hotkeys for factory queueing** — keyboard shortcuts for build queue management
14. **Discoball Czars** — cosmetic fun
15. **Unit pathing (StarCraft 2 style)** — better pathing than SCFA's stop-and-wait A* (Phase 7 — C++ patch territory)
16. **Game speed controls** — adjust sim speed from launcher or in-game
17. **Voice alerts** — audio callouts for: mex under attack, commander under attack, units under attack, incoming artillery
18. **Map preview in launcher** — show a visual preview of the selected map
19. **Mod manager UI** — full UI for enabling/disabling/ordering mods with dependency resolution and conflict detection
20. **Fix scoreboard** — scoreboard issues in-game
21. **Launcher settings persistence** — remember window size, position, panel state, last-used filters across sessions
22. **Modern matchmaking UX** — Steam friends integration, game browser (find visible games), invite system (replaces manual IP/port)
23. **Steam friends integration** — Steam API for multiplayer invites and presence

## Architecture Refactors

24. **Content pack pipeline** — deploy.py `_acquire_content_packs()` should be a proper pipeline: download manager, SCD registry, mod extractor as separate concerns. Will matter when adding BrewLAN, TotalMayhem, etc.
25. **faf_ui.scd build deduplication** — setup produces "Duplicate name" warnings because WOPC patches overlap with FAF files. Need a merge strategy (last-write-wins with explicit override manifest).
26. **Game.prefs management** — SCFA's preference system is not managed by WOPC. We write active_mods at launch but don't own the file. Need a clean strategy.
27. **Asset integrity validation** — content pack SCDs are downloaded once and never verified. Need hash checking on download and periodic validation.
