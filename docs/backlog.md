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
43. ~~**"Send Logs" button**~~ ✅ — one-click button in launcher uploads log to Firebase `/reports/` node for remote troubleshooting (v2.01.0014)
58. ~~**Game.prefs corruption causes black screen**~~ ✅ — `active_mods = true` (boolean) in Game.prefs instead of `active_mods = { }` (table) crashes prefs.lua/optionslogic.lua with "attempt to index a boolean value". Auto-repair runs before every game launch, backs up corrupted file, replaces boolean with empty table.

## High Priority — Player Experience

5. ~~**Launcher self-update**~~ ✅ — check GitHub Releases on startup, download and replace exe, restart (PR #28)
6. ~~**SupCom-authentic UI assets**~~ ✅ — 9-slice metallic chrome borders (SupComFrame widget), faction icons in player slots, beveled button accents on all primary actions, gold sidebar accent. Chrome PNGs rendered via PIL compositing on tk.Canvas.
7. ~~**Remember launcher window size**~~ ✅ — persist width/height in wopc_prefs.ini Window section, restore on launch (PR #29)
8. ~~**SupCom color picker**~~ ✅ — HSV color wheel popup with brightness slider, click/drag to pick any color, nearest-match to SCFA engine palette for game config (v2.01.0027)
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

36. ~~**Map preview too small**~~ ✅ — enlarged preview with 5:1 column weight ratio, reduced padding, preview dominates left side
37. ~~**Map list should be narrower**~~ ✅ — compact sidebar with minsize=200, map list no longer competes with preview
38. ~~**Game browser refresh button**~~ ✅ — manual "⟳ Refresh" button + auto-poll every 5s
39. ~~**SupCom-authentic UI chrome**~~ ✅ — 9-slice metallic frames applied to solo screen (config, map, log panels), lobby screen (map, players, options, chat), and browser screen (game list). SupComFrame widget in `launcher/gui/supcom_frame.py`.
40. ~~**Marker visibility at small sizes**~~ ✅ — increased marker radii and outline widths with better scaling formulas
41. ~~**Map description panel**~~ ✅ — description shown in inspect window header (map_inspect.py lines 102-112)
44. ~~**Icon-based map markers**~~ ✅ — tinted commander icons with preserved outlines, hover halo, click-to-select spawn. Mass/hydro use strategic icons from `launcher/gui/icons/marker_*.png`.
45. ~~**Unify lobby map UI with solo**~~ ✅ — unified 4-column layout with inline map canvas, zoom/pan, searchable map list. Map inspect window removed.
46. **Design asset library** — `launcher/gui/icons/ASSETS.md` indexes all available game textures. Faction icons (`faction_*.png`), strategic icons, chrome borders all pre-converted. Expand as new UI features need assets.
47. ~~**Show player name in slot**~~ ✅ — human slot shows player name from prefs, updates on name change (v2.01.0027)

48. **Rearrange Player Settings layout** — Name inline with Faction (same row), Color inline with minimap preference (same row). Reduces vertical space and groups related settings logically.
49. ~~**Spawn position bug**~~ ✅ — Players array index must match ARMY_N for correct spawn. Gap-filling with civilian entries ensures contiguous array. (v2.01.0032)
50. ~~**Map black screen after ready check**~~ ✅ — Two fixes: (1) `_refresh_map_list()` always rescans filesystem (stale cache), (2) `MapCanvas.set_map()` deferred redraw when canvas not yet laid out. Also fixes #53.
51. ~~**"Send Logs" failure — Firebase 401 on writes**~~ ✅ — Firebase security rules updated in console to allow writes to `/reports/` and `/logs/` nodes.
52. ~~**Player color mismatch in-game**~~ ✅ — Root cause: launcher used a custom 8-color palette that didn't match the engine's 19-color `GameColors.lua`. Aligned `PLAYER_COLORS` in `constants.py` with `vendor/faf-ui/lua/GameColors.lua` exactly.
53. ~~**Auto-updater map list not loading after restart**~~ ✅ — Fixed by #50's always-rescan change to `_refresh_map_list()`.
54. **Civilian filler armies investigation** — gap-filling in `game_config.py` creates `Civilian=true` entries for unused ARMY positions. Investigate whether the engine spawns idle commanders for these entries (gameplay impact).
55. ~~**Refactor app.py monolith**~~ ✅ — 4,320 → 1,913 lines (56% reduction). Extracted 6 modules: `constants.py` (205), `models.py` (226), `map_canvas.py` (578), `slot_widget.py` (832), `browser_screen.py` (458), `lobby_screen.py` (1,070). PR #63 + PR #68.
56. ~~**Multiplayer join broken**~~ ✅ — Six bugs fixed: (1) GameState silently dropped during Welcome wait (TCP coalescing), (2) `_build_game_state()` called from network thread (thread safety), (3) joiner launch reading solo-screen widgets instead of host config, (4) joiner map never written to prefs, (5) `_all_maps` empty causing false map-missing, (6) joiner `expected_humans` never set. See PR for details.
57. ~~**Map spawn markers not assigned on initial load**~~ ✅ — Root cause: `_slot_accessor._slots` was empty `[]` when `set_map()` triggered `redraw()`. Fixed by syncing slot accessor in `_update_map_preview()` before calling `set_map()`.
59. ~~**Multiplayer join: TCP port 15000 unreachable for remote players**~~ ✅ — Added UPnP auto-port-forwarding (`launcher/upnp.py` wrapping `miniupnpc`), actionable NAT error messages on timeout/refused, and `upnp_ok` field in Firebase relay for remote diagnostics. Remaining: relay-based TCP tunneling for 100% NAT coverage (Phase C in #35).
60. ~~**Launcher log verbosity for game launch**~~ ✅ — Structured logging before `Popen()`: launch mode, exe, map, expected humans, player name, mods, config path, full command line.

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

## Multiplayer Bugs (Reported 2026-03-25)

61. ~~**Multiplayer: Can't select spawn slot on map**~~ ✅ — Wired `on_spawn_select` and `on_spawn_swap` callbacks in lobby MapCanvas. Host slot and AI slots now get `start_spot` assignments. Lobby canvas accessor synced on map change, slot add/remove.
62. **Multiplayer: Color picker not rendering correctly** — color picker widget has visual issues in the multiplayer lobby. Needs investigation.
63. ~~**Multiplayer: Player options missing in multiplayer**~~ ✅ — Host slot now has the same structure as solo (team_var, color_var, faction label, color indicator). Map canvas renders spawn colors and teams for host + AI slots. Faction/name/color changes in lobby settings sync to the host slot row.
64. ~~**Multiplayer: AI slots don't show on map**~~ ✅ — Lobby AI slots now assigned sequential `start_spot` values. `_redraw_lobby_canvas()` syncs the slot accessor and redraws after add/remove. Canvas shows colored markers for all lobby slots.
65. ~~**Multiplayer: Enter key launches game instead of sending chat**~~ ✅ — Removed global `<Return>` → launch binding entirely. Enter only sends chat via the lobby chat entry's own `<Return>` binding. Game launch is button-only.
66. ~~**Multiplayer: Friend can't join game**~~ ✅ — wopc_core.scd health check + auto-repair shipped in v2.01.0045. Friend needs to restart launcher to auto-update.
67. ~~**Multiplayer: Game not cleaned from lobby on launch**~~ ✅ — `_launch_game_and_cleanup` now stops server, clears lobby slots, and returns to browser screen after launch. Beacon/relay discovery restarts so the player can immediately create or join a new game.
68. ~~**Friend's wopc_core.scd missing**~~ ✅ — Fixed in v2.01.0045: health check verifies wopc_core.scd exists, auto-repair re-runs setup if missing.
69. ~~**Send Logs should include WOPC.log from game directory**~~ ✅ — Firebase reports now include engine_log (WOPC.log last 300 lines), scfa_log (SupCom.sclog last 200 lines), launcher_file_log (launcher.log last 300 lines), engine_errors, and system_info with commit_hash. Shipped in v2.01.0055.
70. ~~**MEI temp directory warning on update**~~ ✅ — Fixed: `cmd /c timeout` doesn't work in non-interactive shells. Replaced with `ping -n` delay + retry `rmdir` to reliably clean up old _MEI dir before launching new exe. Also added 8s final deferred retry for map canvas rendering after update restart.
71. **Failed to load Python DLL on auto-update restart** — `Failed to load Python DLL 'C:\...\Temp\_MEI#####\python312.dll' LoadLibrary: The specified module could not be found.` during auto-update restart. PyInstaller extracts the new exe to a temp _MEI dir but python312.dll isn't found. Likely causes: Windows Defender quarantining the DLL during extraction, or extraction interrupted by a race. May need to add a Windows Defender exclusion hint, retry logic, or switch from `--onefile` to `--onedir` mode (avoids temp extraction entirely).
72. **Global player settings** — Move player settings (name, faction, color, team) to a global scope that carries across solo and multiplayer modes. Currently each screen has its own settings widgets that are synced manually. A unified player profile model would reduce duplication and ensure consistency. Settings should persist in `wopc_prefs.ini` and auto-apply when entering any game mode.
73. **MEI Python DLL load failure on auto-update restart** — `Failed to load Python DLL '..._MEI#####\python312.dll'` on relaunch after auto-update. Persists across multiple fix attempts (longer delays, triple rmdir retry). May need `--onedir` mode or Windows Defender exclusion. Related to #71.
74. ~~**Solo map preview broken**~~ ✅ — Root cause: stale wopc_core.scd from content-v2 pre-BrewLANLOUDPath fix. Added CONTENT_BUILD marker system (v2.01.0055) to detect stale content and force re-download. Map scan now finds 61 maps after fresh content.
75. **Solo color picker doesn't update swatch** — Selecting a new color in the solo player options doesn't visually update the color indicator, though the value is saved correctly.
76. **Auto-include content packs in `wopc setup`** — Content pack SCDs (BlackOps, TotalMayhem, BrewLAN, etc.) require manual download via mod panel. Should be auto-downloaded during `wopc setup` so players get the full experience out of the box.

## Observability

78. **Launch ID correlation (PK/FK for launcher ↔ engine)** — Generate a unique launch UUID per game launch attempt. Write it to launcher.log, pass it via the game config, and have the engine write it to WOPC.log on startup. Firebase reports include both, so we can correlate "launcher said it launched" with "engine actually ran." Currently there's no link between the two log streams — the launcher says "Launching game..." but we can't tell if the exe actually started or what session the engine log belongs to.
79. ~~**Game exe not starting after launch / vanilla lobby instead of quickstart**~~ ✅ — Root cause: content staleness check (v2.01.0055) destructively deleted wopc_core.scd before confirming the replacement was ready. When re-download failed at 100%, the SCD was gone — engine loaded vanilla uimain.lua with no quickstart hook, showing the vanilla SCFA lobby. Fix: (1) staleness check deletes only the marker, not the SCD (keep old as fallback), (2) deploy.py always re-downloads in standalone mode with fallback on failure, (3) pre-launch validation aborts if SCD missing, (4) _patch_scd return values checked and logged. Also added missing simInit.lua patching to build_content_release.py.
80. **aibrain.lua import cascade failure** — Engine warning: `Error importing /lua/aibrain.lua` → cascades to `factorymanagerbraincomponent.lua` and `/lua/factions.lua`. Persists across v2.01.0054 and v2.01.0055 with fresh content-v2. Related to backlog #33 (AI reclaim grid) but broader — the entire AI brain initialization is failing. Low priority if only affecting AI (games still launch), but needs investigation if it prevents game startup.

## Security

77. **Firebase anonymous auth** — All Firebase REST requests are unauthenticated. Anyone who finds the hardcoded URL can read/write/delete game listings and reports. Add Firebase anonymous auth (POST to `identitytoolkit.googleapis.com/v1/accounts:signUp?key=API_KEY` → returns ID token, append `?auth=TOKEN` to all requests). Set Firebase security rules to `"auth != null"`. Needs: Web API Key from Firebase Console (Project Settings), `FIREBASE_API_KEY` in config.py, auth token helper in relay.py, server-side rules update.

## Platform Support

34. **Linux support** — port the launcher and game setup to run on Linux (Wine/Proton for SCFA, native Python launcher, path discovery for Linux Steam libraries, .desktop integration)

## Architecture Refactors

26. **Content pack pipeline** — deploy.py `_acquire_content_packs()` should be a proper pipeline: download manager, SCD registry, mod extractor as separate concerns. Will matter when adding BrewLAN, TotalMayhem, etc.
27. **wopc_core.scd build deduplication** — setup produces "Duplicate name" warnings because WOPC patches overlap with game logic files. Need a merge strategy (last-write-wins with explicit override manifest).
28. **Game.prefs management** — SCFA's preference system is not managed by WOPC. We write active_mods at launch but don't own the file. Need a clean strategy.
29. **Asset integrity validation** — content pack SCDs are downloaded once and never verified. Need hash checking on download and periodic validation.
30. **Remove or fix post-commit hook** — the background `build_exe.py` post-commit hook causes persistent `index.lock` conflicts on Windows. The background process outlives the hook, fights with subsequent git commands, and MSYS2 bash can't release the lock even after the process dies. Either delete the hook entirely (per Rule #9 we use releases, not manual exe rebuilds) or replace it with a non-blocking approach.
31. ~~**Speed up release script**~~ ✅ — Three optimizations: (1) skip content-v2 rebuild when no content source files changed (~3 min saved), (2) run tests + exe build in parallel (~40s saved), (3) skip pip install if already editable (~5s saved). Launcher-only releases now ~2 min instead of ~5 min.
32. **PyInstaller _MEI temp directory cleanup failure** — `Failed to remove temporary directory: C:\TEMP\_MEI######` warning dialog on exe exit. Caused by PyInstaller `--onefile` mode: the exe extracts to a temp dir, and if the process crashes or exits uncleanly the temp dir isn't removed. Root cause is usually a crash (e.g., the SupComFrame ValueError in v2.01.0039). Workaround: fix crashes so cleanup runs. Long-term: consider `--onedir` mode instead of `--onefile` (avoids temp extraction entirely, faster startup, no cleanup issues).
33. **AI reclaim grid reference missing** — `Build condition ('ReclaimAvailableInGrid') requires a reference to the reclaim grid in the brain` warning repeated many times during AI games. The LOUD AI's reclaim system expects a grid object that isn't initialized. Low priority (cosmetic warning, AI still functions) but should be investigated.
34. ~~**Game.prefs "attempt to index a boolean value" still recurring**~~ ✅ — Three-layer fix: (1) Python repair before launch (existing), (2) Lua UI repair in `uimain.lua:SetupUI()` catches corruption before any prefs code reads it, (3) quickstart.lua always writes `active_mods` to prefs (even when empty) and added to JoinLaunch path.
