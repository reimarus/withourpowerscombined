# Backlog

Items to tackle over time, roughly grouped by priority.

## High Priority — Player Experience

1. **Launcher self-update** — when a new launcher version is available on GitHub Releases, download and replace the exe from within the launcher itself. Players should never need to visit GitHub manually. Check on startup, show update button, download in background, restart.
2. **Content-v2 release build** — run `scripts/build_content_release.py` and upload faf_ui.scd, wopc-maps.zip, strategic icons to `content-v2` GitHub Release so the standalone installer can download them
3. **Player ratings / balancing** — track skill ratings for fairer matchmaking (ELO or similar)

## Multiplayer UX (Phase 6 — complete)

4. ~~**"Add AI" in multiplayer lobby**~~ ✅ — wired to lobby screen with proper slot management
5. ~~**"Change Map" in multiplayer lobby**~~ ✅ — searchable map picker dialog
6. ~~**Remove players from solo screen**~~ ✅ — AI slots have ✕ remove buttons (human slot 1 is protected)
7. ~~**Victory type tooltips**~~ ✅ — descriptions shown on both solo and multiplayer screens
8. ~~**Team auto-assignment**~~ ✅ — new AI slots auto-balanced to team with fewest players via `_next_team()`
9. ~~**Solo ↔ multiplayer UI consistency**~~ ✅ — lobby options now reuse `GAME_OPTION_DEFS`, matching labels/values/defaults; headers and button styles unified
10. ~~**UI polish**~~ ✅ — FAF/SupCom visual redesign (gold + navy palette, dividers, warm cream text)
11. ~~**Map preview in launcher**~~ ✅ — preview image, player count, size, description shown on map selection

## Features

12. **Map Library Browser** — searchable map library where players can browse, preview, and download maps (replaces flat list)
13. **Mini-map size persistence** — remember the user's preferred mini-map size between sessions
14. **Merge LOUD unit mods** — BrewLAN, TotalMayhem, etc. (BlackOps done ✅, though some strategic icons still missing: brb1302, brb1106, brb2306, brb4309, brb4401)
15. **Save game function** — save/load mid-game
16. **Hotkeys for factory queueing** — keyboard shortcuts for build queue management
17. **Discoball Czars** — cosmetic fun
18. **Unit pathing (StarCraft 2 style)** — better pathing than SCFA's stop-and-wait A* (Phase 7 — C++ patch territory)
19. **Game speed controls** — adjust sim speed from launcher or in-game
20. **Voice alerts** — audio callouts for: mex under attack, commander under attack, units under attack, incoming artillery
21. **Mod manager UI** — full UI for enabling/disabling/ordering mods with dependency resolution and conflict detection
22. **Fix scoreboard** — scoreboard issues in-game
23. **Launcher settings persistence** — remember window size, position, panel state, last-used filters across sessions
24. **Modern matchmaking UX** — Steam friends integration, game browser (find visible games), invite system (replaces manual IP/port)
25. **Steam friends integration** — Steam API for multiplayer invites and presence

## Architecture Refactors

26. **Content pack pipeline** — deploy.py `_acquire_content_packs()` should be a proper pipeline: download manager, SCD registry, mod extractor as separate concerns. Will matter when adding BrewLAN, TotalMayhem, etc.
27. **faf_ui.scd build deduplication** — setup produces "Duplicate name" warnings because WOPC patches overlap with FAF files. Need a merge strategy (last-write-wins with explicit override manifest).
28. **Game.prefs management** — SCFA's preference system is not managed by WOPC. We write active_mods at launch but don't own the file. Need a clean strategy.
29. **Asset integrity validation** — content pack SCDs are downloaded once and never verified. Need hash checking on download and periodic validation.
