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
42. **Setup crash: wopc_core.scd.zip download fails silently** — `_download_file()` returns `False` on 404/network error but callers at lines 194, 303, 317, 398 in `deploy.py` don't check the return value. The immediate crash (`FileNotFoundError` at line 522) is fixed (PR #42), but other download calls still fail silently. Also: the `content-v2` GitHub Release doesn't exist yet — must create it with `wopc_core.scd.zip`, `wopc-maps.zip`, and strategic icons so first-time setup works for new users.
43. **"Send Logs" button** — one-click button in the launcher that uploads the launcher log (`WOPC.log` or Python log) to Firebase `/reports/` node. Lets us diagnose remote issues (setup crashes, multiplayer failures) without asking users to copy-paste logs.

## High Priority — Player Experience

5. ~~**Launcher self-update**~~ ✅ — check GitHub Releases on startup, download and replace exe, restart (PR #28)
6. **SupCom-authentic UI assets** — the launcher currently uses generic CustomTkinter buttons and backgrounds. Extract and implement actual Supreme Commander design assets (metallic button frames, brushed-metal backgrounds, faction-themed borders, glowing hover states) so the launcher feels like a modern SupCom experience, not a generic app with a color theme.
7. ~~**Remember launcher window size**~~ ✅ — persist width/height in wopc_prefs.ini Window section, restore on launch (PR #29)
8. **SupCom color picker** — use a SupCom-authentic color palette/picker for faction and player colors instead of the generic one.
9. **Content-v2 release build** — run `scripts/build_content_release.py` and upload wopc_core.scd, wopc-maps.zip, strategic icons to `content-v2` GitHub Release so the standalone installer can download them
10. **Player ratings / balancing** — track skill ratings for fairer matchmaking (ELO or similar)

## Multiplayer UX (Phase 6 — complete)

11. ~~**"Add AI" in multiplayer lobby**~~ ✅ — wired to lobby screen with proper slot management
12. ~~**"Change Map" in multiplayer lobby**~~ ✅ — searchable map picker dialog
13. ~~**Remove players from solo screen**~~ ✅ — AI slots have ✕ remove buttons (human slot 1 is protected)
14. ~~**Victory type tooltips**~~ ✅ — descriptions shown on both solo and multiplayer screens
15. ~~**Team auto-assignment**~~ ✅ — new AI slots auto-balanced to team with fewest players via `_next_team()`
16. ~~**Solo ↔ multiplayer UI consistency**~~ ✅ — lobby options now reuse `GAME_OPTION_DEFS`, matching labels/values/defaults; headers and button styles unified
17. ~~**UI polish**~~ ✅ — SupCom visual redesign (gold + navy palette, dividers, warm cream text)
18. ~~**Map preview in launcher**~~ ✅ — preview image, player count, size, description shown on map selection
18b. ~~**Interactive map preview**~~ ✅ — canvas-based hero preview with mass/hydro/spawn overlays, click-to-inspect zoom window, DDS extraction from .scmap, dynamic filters, stable layout

## High Priority — UI Polish

> Based on side-by-side comparison with other SupCom launchers (2026-03-21 screenshots)

36. **Map preview too small** — map needs to be 2-3x larger and dominate the left side of the config panel. Currently ~200px, should be ~40% of the dialog. The map is the most important visual element.
37. **Map list should be narrower** — map list competes with preview for horizontal space. Make the list a compact sidebar on the right, give the map the lion's share.
38. **Game browser refresh button** — users need a manual "Refresh" to force re-poll for games. Currently only auto-polls every 5s, but first-time users need instant feedback.
39. **SupCom-authentic UI chrome** — use metallic SupCom frames/borders. Our launcher feels like a generic app with a color theme. Extract and render actual game UI textures for borders, buttons, and panel backgrounds.
40. **Marker visibility at small sizes** — mass/hydro/spawn markers are hard to distinguish at current preview size. Scale marker radius with canvas size and use thicker outlines.
41. **Map description panel** — show map description text below the preview. We stripped description to reduce clutter but should show it in the inspect window.

## Features

19. **Map Library Browser** — searchable map library where players can browse, preview, and download maps (replaces flat list)
20. **Mini-map size persistence** — remember the user's preferred mini-map size between sessions
21. **Merge unit mods** — BrewLAN, TotalMayhem, etc. (BlackOps done ✅, though some strategic icons still missing: brb1302, brb1106, brb2306, brb4309, brb4401)
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
35. **Internet multiplayer** — ~~Phase A: Firebase relay for internet game discovery~~ ✅ (merged: `launcher/relay.py`, `RELAY_URL` in config, 🌐 badge in browser, LAN+internet merge). **Needs**: Firebase project created + `RELAY_URL` set in config to activate. Phase B: ICE/STUN NAT traversal (eliminates port forwarding for gameplay). Phase C: Steam P2P API for zero-config multiplayer.
33. **"Leave a comment or idea" feature** — in-launcher feedback button that lets players submit ideas, bug reports, or feature requests (e.g. opens a GitHub Issue template or a simple form that creates an issue). We review and implement what makes sense.

## Platform Support

34. **Linux support** — port the launcher and game setup to run on Linux (Wine/Proton for SCFA, native Python launcher, path discovery for Linux Steam libraries, .desktop integration)

## Architecture Refactors

26. **Content pack pipeline** — deploy.py `_acquire_content_packs()` should be a proper pipeline: download manager, SCD registry, mod extractor as separate concerns. Will matter when adding BrewLAN, TotalMayhem, etc.
27. **wopc_core.scd build deduplication** — setup produces "Duplicate name" warnings because WOPC patches overlap with game logic files. Need a merge strategy (last-write-wins with explicit override manifest).
28. **Game.prefs management** — SCFA's preference system is not managed by WOPC. We write active_mods at launch but don't own the file. Need a clean strategy.
29. **Asset integrity validation** — content pack SCDs are downloaded once and never verified. Need hash checking on download and periodic validation.
