# Backlog

Items to tackle over time, roughly grouped by priority.

## Critical Bugs — First-Time Setup Broken

1. ~~**Asset download stuck / no progress shown**~~ ✅ — progress bar + step labels in GUI (PR #26)
2. ~~**Auto-discover SCFA install path**~~ ✅ — superseded: exe now lives in SCFA folder, no discovery needed (PR #30)
3. ~~**WOPC asset download failing**~~ ✅ — 30s timeout, 3 retries with backoff, clear error messages (PR #26)
4. **Publish launcher exe to GitHub Release** — the exe must be the most prominent download on the repo. Upload `WOPC-Launcher.exe` to a pinned release so players can find it immediately.
5. ~~**Map preview not working (solo)**~~ ✅ — Pillow bundled in exe (PR #26)
6. ~~**Map preview not working (multiplayer)**~~ ✅ — lobby preview image widget added (PR #26)
7. **Move launcher exe out of dist/** — `build_exe.py` outputs to `dist/WOPC-Launcher.exe`. Move the final exe to the repo root or a more obvious location so it's easy to find.

## High Priority — Player Experience

5. ~~**Launcher self-update**~~ ✅ — check GitHub Releases on startup, download and replace exe, restart (PR #28)
6. **SupCom-authentic UI assets** — the launcher currently uses generic CustomTkinter buttons and backgrounds. Extract and implement actual Supreme Commander design assets (metallic button frames, brushed-metal backgrounds, faction-themed borders, glowing hover states) so the launcher feels like a modern SupCom experience, not a generic app with a color theme.
7. ~~**Remember launcher window size**~~ ✅ — persist width/height in wopc_prefs.ini Window section, restore on launch (PR #29)
8. **LOUD color picker** — use LOUD's color palette/picker for faction and player colors instead of the generic one.
9. **Content-v2 release build** — run `scripts/build_content_release.py` and upload wopc_core.scd, wopc-maps.zip, strategic icons to `content-v2` GitHub Release so the standalone installer can download them
10. **Player ratings / balancing** — track skill ratings for fairer matchmaking (ELO or similar)

## Multiplayer UX (Phase 6 — complete)

11. ~~**"Add AI" in multiplayer lobby**~~ ✅ — wired to lobby screen with proper slot management
12. ~~**"Change Map" in multiplayer lobby**~~ ✅ — searchable map picker dialog
13. ~~**Remove players from solo screen**~~ ✅ — AI slots have ✕ remove buttons (human slot 1 is protected)
14. ~~**Victory type tooltips**~~ ✅ — descriptions shown on both solo and multiplayer screens
15. ~~**Team auto-assignment**~~ ✅ — new AI slots auto-balanced to team with fewest players via `_next_team()`
16. ~~**Solo ↔ multiplayer UI consistency**~~ ✅ — lobby options now reuse `GAME_OPTION_DEFS`, matching labels/values/defaults; headers and button styles unified
17. ~~**UI polish**~~ ✅ — FAF/SupCom visual redesign (gold + navy palette, dividers, warm cream text)
18. ~~**Map preview in launcher**~~ ✅ — preview image, player count, size, description shown on map selection

## Features

19. **Map Library Browser** — searchable map library where players can browse, preview, and download maps (replaces flat list)
20. **Mini-map size persistence** — remember the user's preferred mini-map size between sessions
21. **Merge LOUD unit mods** — BrewLAN, TotalMayhem, etc. (BlackOps done ✅, though some strategic icons still missing: brb1302, brb1106, brb2306, brb4309, brb4401)
22. **Save game function** — save/load mid-game
23. **Hotkeys for factory queueing** — keyboard shortcuts for build queue management
24. **Discoball Czars** — cosmetic fun
25. **Unit pathing (StarCraft 2 style)** — better pathing than SCFA's stop-and-wait A* (Phase 7 — C++ patch territory)
26. **Game speed controls** — adjust sim speed from launcher or in-game
27. **Voice alerts** — audio callouts for: mex under attack, commander under attack, units under attack, incoming artillery
28. **Mod manager UI** — full UI for enabling/disabling/ordering mods with dependency resolution and conflict detection
29. **Fix scoreboard** — scoreboard issues in-game
30. **Launcher settings persistence** — remember window size, position, panel state, last-used filters across sessions
31. **Modern matchmaking UX** — Steam friends integration, game browser (find visible games), invite system (replaces manual IP/port)
32. **Steam friends integration** — Steam API for multiplayer invites and presence
35. **Internet multiplayer** — replace LAN-only UDP beacons with internet-capable matchmaking. Phase A: simple relay/matchmaking server (host registers, joiners discover — no port forwarding for discovery). Phase B: ICE/STUN NAT traversal (like FAF's java-ice-adapter — eliminates port forwarding for gameplay). Phase C: Steam P2P API for zero-config multiplayer.
33. **"Leave a comment or idea" feature** — in-launcher feedback button that lets players submit ideas, bug reports, or feature requests (e.g. opens a GitHub Issue template or a simple form that creates an issue). We review and implement what makes sense.

## Platform Support

34. **Linux support** — port the launcher and game setup to run on Linux (Wine/Proton for SCFA, native Python launcher, path discovery for Linux Steam libraries, .desktop integration)

## Architecture Refactors

26. **Content pack pipeline** — deploy.py `_acquire_content_packs()` should be a proper pipeline: download manager, SCD registry, mod extractor as separate concerns. Will matter when adding BrewLAN, TotalMayhem, etc.
27. **wopc_core.scd build deduplication** — setup produces "Duplicate name" warnings because WOPC patches overlap with game logic files. Need a merge strategy (last-write-wins with explicit override manifest).
28. **Game.prefs management** — SCFA's preference system is not managed by WOPC. We write active_mods at launch but don't own the file. Need a clean strategy.
29. **Asset integrity validation** — content pack SCDs are downloaded once and never verified. Need hash checking on download and periodic validation.
