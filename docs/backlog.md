backlog of items for us to do over time.

## Features
1. mini map size persistance
2. merge loud unit mods (BlackOps integrated but has issues — see below; remaining: BrewLAN, TotalMayhem, etc.)
    - BlackOps ACU mod forces commander to spawn fully upgraded, invisible, and uncontrollable
    - Several BlackOps units show placeholder/missing strategic icons
    - Likely need to disable BlackopsACUs mod or strip its ACU upgrade hooks
    - Unit icon issue may require adding missing strategic icon assets
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
13. **Mod system consolidation** — Current mod handling is spread across prefs.py
    (UID scanning), init_generator.py (VFS mounting), deploy.py (extraction),
    game_config.py (UID serialization), and quickstart.lua (activation).
    Consolidate into a single `launcher/mods.py` module that owns the full
    lifecycle: discovery, extraction, activation, and state management.
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
17. **User mod activation** — User mods (WOPC/usermods/) are toggled by folder
    name in prefs but passed to GameMods by name, not UID. Should use UIDs
    consistently like server mods. Also need proper dependency resolution
    (mod A requires mod B).
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
