# Backlog

Items to tackle over time, roughly grouped by priority.

## Critical Bugs

87. ~~**Standalone DLL audit — missing dependencies break fresh installs**~~ — **DONE** (PRs #104, #105, #106). Pre-launch DLL validation, setup aborts on missing critical DLLs, `wopc validate` checks all 19 critical binaries + wopc_core.scd size, build-time SCD import verification, runtime import() wrapper for crash diagnostics. Moved to Archive.
4. **Publish launcher exe to GitHub Release** — the exe must be the most prominent download on the repo. Upload `WOPC-Launcher.exe` to a pinned release so players can find it immediately.
7. **Move launcher exe out of dist/** — `build_exe.py` outputs to `dist/WOPC-Launcher.exe`. Move the final exe to the repo root or a more obvious location so it's easy to find.
42. **Setup crash: wopc_core.scd.zip download fails silently** — `_download_file()` returns `False` on 404/network error but callers in `deploy.py` don't check the return value. Also: the `content-v2` GitHub Release must have `wopc_core.scd.zip`, `wopc-maps.zip`, and strategic icons so first-time setup works.

## High Priority — Player Experience

9. **Content-v2 release build** — run `scripts/build_content_release.py` and upload wopc_core.scd, wopc-maps.zip, strategic icons to `content-v2` GitHub Release so the standalone installer can download them
10. **Player ratings / balancing** — track skill ratings for fairer matchmaking (ELO or similar)
62. **Multiplayer: Color picker not rendering correctly** — color picker widget has visual issues in the multiplayer lobby. Needs investigation.
72. **Global player settings** — Move player settings (name, faction, color, team) to a global scope that carries across solo and multiplayer modes. A unified player profile model would reduce duplication and ensure consistency.
75. **Solo color picker doesn't update swatch** — Selecting a new color in the solo player options doesn't visually update the color indicator, though the value is saved correctly.
76. **Auto-include content packs in `wopc setup`** — Content pack SCDs (BlackOps, TotalMayhem, BrewLAN, etc.) require manual download via mod panel. Should be auto-downloaded during `wopc setup`.

## UI Polish

46. **Design asset library** — `launcher/gui/icons/ASSETS.md` indexes all available game textures. Expand as new UI features need assets.
48. **Rearrange Player Settings layout** — Name inline with Faction (same row), Color inline with minimap preference (same row). Reduces vertical space.
54. **Civilian filler armies investigation** — gap-filling in `game_config.py` creates `Civilian=true` entries for unused ARMY positions. Investigate whether the engine spawns idle commanders.

## Features

19. **Map Library Browser** — searchable map library where players can browse, preview, and download maps (replaces flat list)
20. **Mini-map size persistence** — remember the user's preferred mini-map size between sessions
21. **Merge unit mods** — BrewLAN, TotalMayhem, etc. (BlackOps done, though some strategic icons still missing)
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
33. **"Leave a comment or idea" feature** — in-launcher feedback button that lets players submit ideas, bug reports, or feature requests
35. **Internet multiplayer** — Phase A done (Firebase relay). Phase B: ICE/STUN NAT traversal (eliminates port forwarding). Phase C: Steam P2P API for zero-config multiplayer.

## Platform Support

34. **Linux support** — port the launcher and game setup to run on Linux (Wine/Proton for SCFA, native Python launcher, path discovery for Linux Steam libraries, .desktop integration)

## Architecture Refactors

26. **Content pack pipeline** — deploy.py `_acquire_content_packs()` should be a proper pipeline: download manager, SCD registry, mod extractor as separate concerns.
27. **wopc_core.scd build deduplication** — setup produces "Duplicate name" warnings because WOPC patches overlap with game logic files. Need a merge strategy.
28. **Game.prefs management** — SCFA's preference system is not managed by WOPC. We write active_mods at launch but don't own the file. Need a clean strategy.
29. **Asset integrity validation** — content pack SCDs are downloaded once and never verified. Need hash checking on download and periodic validation.
32. **PyInstaller _MEI temp directory cleanup failure** — `--onefile` mode extracts to temp dir; unclean exits leave it behind. Long-term: consider `--onedir` mode.
33. **AI reclaim grid reference missing** — `Build condition ('ReclaimAvailableInGrid') requires a reference to the reclaim grid in the brain` warning. Low priority (cosmetic, AI still functions).
36. **Refactor `deploy.py:run_setup()` into step functions** — Extract each setup step into a named function. Add isolated unit tests for `_patch_scd()`.
37. **Delete unused `deploy.py:_acquire_core_content()`** — Dead code, never called.
38. **Test coverage push: deploy.py + relay.py** — `_patch_scd()` has no isolated tests. After refactoring (#36), add tests for edge cases.
39. **Extract hard-coded arcnames in `deploy.py:_patch_scd()`** — Move string literals to config constants.
88. **Standardize config import pattern in wopc.py** — `wopc.py` uses `from launcher.config import WOPC_BIN, GAME_EXE, ...` (direct imports), while CLAUDE.md rule says to use `from launcher import config` then `config.WOPC_BIN`. The direct import creates local name copies; tests compensate by patching `launcher.wopc.WOPC_BIN` instead of `launcher.config.WOPC_BIN`. Both patterns work but having two conventions is confusing. Refactor `wopc.py` to use the module-level pattern (`from launcher import config` → `config.X`), then tests can patch `launcher.config.X` uniformly. Medium effort (~30 import sites in wopc.py + all test patches).

---

## Archive (completed)

<details>
<summary>Click to expand completed items</summary>

### Critical Bugs
- #1 **Asset download stuck / no progress shown** — progress bar + step labels in GUI (PR #26)
- #2 **Auto-discover SCFA install path** — superseded: exe now lives in SCFA folder (PR #30)
- #3 **WOPC asset download failing** — 30s timeout, 3 retries with backoff (PR #26)
- #5 **Map preview not working (solo)** — Pillow bundled in exe (PR #26)
- #6 **Map preview not working (multiplayer)** — lobby preview image widget (PR #26)
- #43 **"Send Logs" button** — one-click upload to Firebase `/reports/` (v2.01.0014)
- #58 **Game.prefs corruption causes black screen** — auto-repair before every launch

### Player Experience
- #5 **Launcher self-update** — check GitHub Releases, download/replace exe, restart (PR #28)
- #6 **SupCom-authentic UI assets** — 9-slice chrome borders, faction icons, beveled buttons
- #7 **Remember launcher window size** — persist in wopc_prefs.ini (PR #29)
- #8 **SupCom color picker** — HSV wheel, nearest SCFA palette match (v2.01.0027)

### Multiplayer UX (Phase 6)
- #11 **"Add AI" in multiplayer lobby** — wired with proper slot management
- #12 **"Change Map" in multiplayer lobby** — searchable map picker
- #13 **Remove players from solo screen** — AI slots have remove buttons
- #14 **Victory type tooltips** — descriptions on both screens
- #15 **Team auto-assignment** — `_next_team()` auto-balancing
- #16 **Solo/multiplayer UI consistency** — shared `GAME_OPTION_DEFS`
- #17 **UI polish** — SupCom visual redesign (gold + navy palette)
- #18 **Map preview in launcher** — preview image, player count, size, description
- #18b **Interactive map preview** — canvas with mass/hydro/spawn overlays, DDS extraction

### UI Polish
- #36 **Map preview too small** — enlarged with 5:1 column ratio
- #37 **Map list should be narrower** — compact sidebar, minsize=200
- #38 **Game browser refresh button** — manual refresh + 5s auto-poll
- #39 **SupCom-authentic UI chrome** — 9-slice frames on all screens
- #40 **Marker visibility at small sizes** — increased radii and outlines
- #41 **Map description panel** — in inspect window header
- #44 **Icon-based map markers** — commander icons, strategic icons
- #45 **Unify lobby map UI with solo** — unified 4-column layout
- #47 **Show player name in slot** — from prefs, updates on change (v2.01.0027)
- #49 **Spawn position bug** — ARMY_N index matching with civilian gap-fill (v2.01.0032)
- #50 **Map black screen after ready check** — always-rescan + deferred redraw
- #51 **Send Logs failure — Firebase 401** — security rules updated
- #52 **Player color mismatch in-game** — aligned with GameColors.lua
- #53 **Auto-updater map list not loading** — fixed by #50's rescan
- #55 **Refactor app.py monolith** — 4,320 to 1,913 lines (PR #63 + #68)

### Multiplayer Bugs
- #56 **Multiplayer join broken** — six bugs fixed (TCP coalescing, thread safety, etc.)
- #57 **Map spawn markers not assigned on initial load** — slot accessor sync fix
- #59 **TCP port 15000 unreachable** — UPnP auto-port-forwarding + NAT error messages
- #60 **Launcher log verbosity for game launch** — structured logging before Popen()
- #61 **Can't select spawn slot on map** — wired spawn callbacks in lobby MapCanvas
- #63 **Player options missing in multiplayer** — host slot matched solo structure
- #64 **AI slots don't show on map** — sequential start_spot + accessor redraw
- #65 **Enter key launches game instead of chat** — removed global Return binding
- #66 **Friend can't join game** — wopc_core.scd health check + auto-repair (v2.01.0045)
- #67 **Game not cleaned from lobby on launch** — stop server + return to browser
- #68 **Friend's wopc_core.scd missing** — health check + auto-repair (v2.01.0045)
- #69 **Send Logs should include WOPC.log** — engine/scfa/launcher logs in Firebase (v2.01.0055)
- #70 **MEI temp directory warning on update** — ping delay + retry rmdir
- #71 **Failed to load Python DLL on auto-update** — restart.log + non-blocking launch (v2.01.0060)
- #73 **MEI Python DLL load failure** — duplicate of #71 (v2.01.0060)
- #74 **Solo map preview broken** — CONTENT_BUILD marker for stale content (v2.01.0055)

### Observability
- #78 **Launch ID correlation** — 12-char UUID threaded through launcher/engine/Firebase
- #79 **Game exe not starting / vanilla lobby** — VFS mount order bug + download resilience (v2.01.0057-0059)
- #80 **aibrain.lua import cascade** — lazy-load Factions in FactoryManagerBrainComponent.lua
- #81 **Game exit monitoring** — daemon thread monitors exit code + session duration (v2.01.0061)
- #82 **PhxLib.lua division-by-nil** — patched via _patch_scd() (v2.01.0061)

### Security
- #77 **Firebase security rules** — schema validation, write-once reports/logs, deny-all default
- #83 **Path traversal in file_transfer.py** — resolve + is_relative_to guard
- #84 **Unbound network buffer in lobby.py** — MAX_BUFFER (1 MB) + MAX_MESSAGE (256 KB)
- #85 **ZIP path traversal in deploy.py** — member path validation before extraction
- #86 **Command injection in updater.py** — .cmd script file replaces shell=True

### Architecture
- #30 **Remove or fix post-commit hook** — already removed, pre-commit framework remains
- #31 **Speed up release script** — skip content rebuild, parallel tests+build, skip pip
- #34 **Game.prefs boolean corruption** — three-layer fix (Python + Lua UI + quickstart)
- #35 **Refactor relay.py:upload_logs()** — extracted 4 static helpers, 96% coverage

</details>
