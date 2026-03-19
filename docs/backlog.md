backlog of items for us to do over time.

things to add: 
couple other items for the backlog. add ai to players in the multiplayer screen doesnt work. change map button in multiplayer screen doesnt work, i dont know what each of the different victory types mean, I cant remove players from the solo map, there is no team auto assignment, we dont have player ratings for balancing, UI style is still very basic need to make it fancier, and solo and multiplayer games ui isnt consistent between them(that should be a rule for you so you remember)
another rule to add, always review and update backlog.md with what we accomplished, ideas since the last PR, and one peice of improvement that we can work on in the future.
I want you to use claude.md to make you an expert on this project as quickly as possible so you are as efficient as possible in navigating it. make sure you are always considering things that can be CRUDed to improve your ability to work with this project. 

## Features
1. mini map size persistance
2. merge loud unit mods (BlackOps integrated; remaining: BrewLAN, TotalMayhem, etc.)
    - ~~BlackOps ACU mod forces commander to spawn fully upgraded, invisible, and uncontrollable~~ ✅ Fixed — BlackopsACUs excluded from SCD extraction (`EXCLUDED_SCD_MODS`). The mod replaces vanilla ACUs with LOUD-specific units that depend on LOUD's extended Unit base class (`PlayCommanderWarpInEffect`, `SetValidTargetsForCurrentLayer`, etc.) which don't exist in FAF-only mode.
    - Several BlackOps units show placeholder/missing strategic icons (brb1302, brb1106, brb2306, brb4309, brb4401)
3. save game function
4. hotkeys for factory queueing
5. discoball czars
6. unit pathing - starcraft 2
7. Game speed controls
8. multiplayer
9. voice alerts
    a. mex attack
    b. commander under attack
    c. units under attack
    d. incoming artillary
10. map preview in launcher
11. mod manager (full UI for enabling/disabling/ordering mods)
12. fix score board

## Architecture Refactors
13. ~~**Mod system consolidation**~~ ✅ Done — `launcher/mods.py` now owns the
    full mod lifecycle: discovery (ModInfo dataclass + UID parsing), content
    pack management (labels, toggling), mod extraction from SCDs, UID-based
    state management, and migration from folder-name prefs to UIDs.
    Fixed critical bug where wopc.py mixed UIDs with folder names.
14. **Content pack pipeline** — deploy.py `_acquire_content_packs()` handles
    download + extraction + mod extraction in one function. Should be a proper
    pipeline: download manager, SCD registry, mod extractor as separate concerns.
    Will matter when adding BrewLAN, TotalMayhem, etc.
15. **faf_ui.scd build deduplication** — Setup produces "Duplicate name" warnings
    because WOPC patches overlap with FAF files. Need a proper merge strategy
    (last-write-wins with explicit override manifest) instead of appending.
16. **Multiplayer architecture** — Currently quickstart.lua creates its own
    LobbyComm and bypasses FAF's lobby entirely. For real multiplayer, need:
    lobby discovery, peer-to-peer connection, mod/version sync validation,
    shared game config negotiation. This is the largest refactor.
17. **User mod activation** — ~~User mods toggled by folder name~~ ✅ Fixed —
    mods.py now uses UIDs consistently. Includes prefs migration from folder
    names to UIDs. Still need: proper dependency resolution (mod A requires
    mod B) and conflict detection in the launcher UI.
18. **Game.prefs management** — SCFA's preference system (Game.prefs) is not
    managed by WOPC. We write active_mods at launch time but don't own the
    file. Need a clean strategy: either fully manage Game.prefs from the
    launcher, or ensure our quickstart always overrides whatever is on disk.
19. **Launcher settings persistence** — Window size, position, panel state,
    last-used filters should persist across sessions. Currently only game
    prefs are saved (map, faction, mods).
20. **Asset integrity validation** — Content pack SCDs are downloaded once and
    never verified. Need hash checking on download and periodic validation
    (corruption from disk errors, partial downloads, etc.).
