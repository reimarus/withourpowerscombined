# WOPC: Vision and Future Horizons

## The Core Philosophy
*Supreme Commander: Forged Alliance* is an amazing, enduring masterpiece of the RTS genre, kept alive for over a decade by a dedicated community. Playing this game with friends remains a profoundly unique experience.

The **With Our Powers Combined (WOPC)** project is born out of a love for the game and a desire to see what is possible when we push the Moho Engine to its absolute limits, assisted by modern AI tools.

## Phase 0-2: The Unification
LOUD and FAF are two monumental achievements in the game's history:
- **LOUD** fundamentally rewrote the AI and added hundreds of new gameplay elements, optimizing the Lua simulation for massive scale.
- **FAF** reverse-engineered and patched the compiled C++ engine, yielding critical collision fixes, memory improvements, and a faster binary.

Our first major hurdle is unification. By safely combining LOUD's massive content and Lua simulation with FAF's optimized engine patches, WOPC creates the definitive underlying platform for the future of the game.

## The Future Horizons
Once LOUD and FAF feel like they belong together, WOPC will expand its scope into entirely new territories.

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
FAF opened the door to patching the engine; we intend to blow it wide open. As an AI-assisted development team, we can tackle the most complex legacy C++ systems in the engine to squeeze out every drop of performance:
- **Pathfinding:** Replacing the "stop and wait" A* logic with a multi-threaded Flowfield or advanced steering system.
- **Memory & Rendering:** Identifying and patching legacy rendering bottlenecks.
- **Sim Speed:** Pushing the simulation tick rate to remain stable even with 10,000+ units on the field.

WOPC is where the past's greatest RTS meets the future of AI-driven game engine development.
