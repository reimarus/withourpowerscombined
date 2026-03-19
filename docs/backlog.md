# Backlog

Items to tackle over time, roughly grouped by priority.

## Multiplayer UX (Phase 6 — in progress)

1. **"Add AI" in multiplayer lobby** — button exists but not wired up; needs to add AI slots to game state and sync to all players
2. **"Change Map" in multiplayer lobby** — button exists but not wired up; needs map picker dialog and state broadcast
3. **Remove players from solo screen** — no way to delete a player slot once added
4. **Victory type tooltips** — players can't tell what "Assassination" vs "Supremacy" vs "Sandbox" actually mean; add descriptions
5. **Team auto-assignment** — automatically balance teams as players join instead of manual assignment
6. **Player ratings / balancing** — track skill ratings for fairer matchmaking (ELO or similar)
7. **UI polish** — modern styling, better spacing, visual hierarchy, fancier look overall
8. **Solo ↔ multiplayer UI consistency** — shared concepts (map selector, player slots, game options) must look and behave the same in both screens (see CLAUDE.md rule #5)

things to add: 
couple other items for the backlog. add ai to players in the multiplayer screen doesnt work. change map button in multiplayer screen doesnt work, i dont know what each of the different victory types mean, I cant remove players from the solo map, there is no team auto assignment, we dont have player ratings for balancing, UI style is still very basic need to make it fancier, and solo and multiplayer games ui isnt consistent between them(that should be a rule for you so you remember)
another rule to add, always review and update backlog.md with what we accomplished, ideas since the last PR, and one peice of improvement that we can work on in the future.
I want you to use claude.md to make you an expert on this project as quickly as possible so you are as efficient as possible in navigating it. make sure you are always considering things that can be CRUDed to improve your ability to work with this project. 

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
