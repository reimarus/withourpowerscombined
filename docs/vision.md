# WOPC: Vision and Future Horizons

## The Core Philosophy
*Supreme Commander: Forged Alliance* is an amazing, enduring masterpiece of the RTS genre, kept alive for over a decade by a dedicated community. Playing this game with friends remains a profoundly unique experience.

The **With Our Powers Combined (WOPC)** project is born out of a love for the game and a desire to see what is possible when we push the Moho Engine to its absolute limits, assisted by modern AI tools.

## Phase 0-2: The Foundation
WOPC stands on the shoulders of the SupCom modding community. We inherited engine patches that fix critical bugs (collisions, memory, pathfinding) and a massive library of gameplay content (units, AI, maps). These are now maintained as part of WOPC — a standalone project, free to evolve independently.

## The Future Horizons
With a solid standalone foundation, WOPC expands into entirely new territories.

### 1. The Advanced WOPC Launcher
Currently, a command-line script, the WOPC Launcher will evolve into a proper interface allowing players to configure their game precisely:
- Discrete selection of mod preferences and content packs.
- Easy toggling of experimental engine patches.
- Manifest validation to ensure all friends in a lobby have perfectly synchronized game data.

### 2. A Roguelike Campaign System
Leveraging WOPC's control over the game's initialization and Lua mount order, we aim to introduce a persistent, generative, *Roguelike* meta-campaign to the game.
- Randomized tech trees, modifiers, and escalating AI threats.
- Persistent commander upgrades between skirmishes.
- A completely new way to experience Supreme Commander cooperatively with friends.

### 3. Deep C++ Refactoring
The existing engine patches opened the door; we intend to blow it wide open. As an AI-assisted development team, we can tackle the most complex legacy C++ systems in the engine to squeeze out every drop of performance:
- **Pathfinding:** Replacing the "stop and wait" A* logic with a multi-threaded Flowfield or advanced steering system.
- **Memory & Rendering:** Identifying and patching legacy rendering bottlenecks.
- **Sim Speed:** Pushing the simulation tick rate to remain stable even with 10,000+ units on the field.

WOPC is where the past's greatest RTS meets the future of AI-driven game engine development.
