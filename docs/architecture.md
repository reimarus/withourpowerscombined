# WOPC Architecture

## Overview

WOPC is a self-contained, standalone Supreme Commander: Forged Alliance game distribution. It merges the best gameplay aspects of the LOUD conversion mod with the engine stability and capabilities of FAF's binary-patched engine. Moving forward, WOPC provides all necessary assets internally, replacing the need for separate LOUD or FAF installations. The game is deployed to `C:\ProgramData\WOPC\` leaving Steam SCFA untouched.

## Directory Layout

### Repository (github.com/reimarus/withourpowerscombined)

```
withourpowerscombined/
  launcher/
    wopc.py              Main CLI entry point
    config.py            Path constants and version info
    setup.py             WOPC directory creation and file copying
  init/
    init_wopc.lua        Custom init file (replaces LoudDataPath.lua)
    CommonDataPath.lua   VFS helper functions (from LOUD)
  patches/               FAF binary patches (Phase 2)
    hooks/               ASM hooks into ForgedAlliance.exe
    section/             C++ code sections
    include/             moho.h, global.h, LuaAPI.h
  gamedata/
    wopc_patches/        Our Lua overlay (zipped to .scd on build)
  tools/
    setup_toolchain.py   Installs MSYS2/clang/gcc for binary patching
  docs/
    architecture.md      This file
    setup-guide.md       User-facing setup instructions
    engine-analysis.md   SCFA engine reverse engineering notes
```

### Deployed Game Directory (C:\ProgramData\WOPC)

```
C:\ProgramData\WOPC\
  bin\
    SupremeCommander.exe    Copied from Steam (Phase 0) or FAF-patched (Phase 2+)
    init_wopc.lua           Our custom init file
    CommonDataPath.lua      VFS helper functions
    MohoEngine.dll          Core engine (copied from Steam)
    *.dll                   All runtime DLLs from Steam SCFA/bin
    game.dat                Engine configuration
  gamedata\
    lua.scd                 Core WOPC Lua
    units.scd               WOPC units
    ... (Additional SCD files bundled via repository releases)
    wopc_patches.scd        Our overlay patches
  maps\                     Custom WOPC map library
  sounds\                   Custom WOPC sound banks
  usermods\                 Bundled UI and gameplay mods
```

## Content Mount Order

SCFA's VFS (Virtual File System) loads content in a priority order. When multiple SCDs contain the same file path, the **last mount wins** (shadows earlier mounts). Our init file preserves LOUD's mount order:

| Priority | Source | Content |
|----------|--------|---------|
| 1 (lowest) | Steam SCFA | Vanilla textures, effects, env, meshes, movies, sounds, fonts |
| 2 | LOUD gamedata/*.scd | All 17 LOUD content packs (lua, units, brewlan, etc.) |
| 3 | LOUD maps/sounds | LOUD-specific maps and sounds |
| 4 | BrewLAN icons | Strategic icon overhaul |
| 5 | **WOPC overlay** | wopc_patches.scd - our compatibility fixes and enhancements |
| 6 | User mods | BetterPathing and other usermods |
| 7 (highest) | User maps | Custom user maps |

## Key Design Decisions

### Why Python for the launcher?

- Python 3.12 is already installed on the target machine
- No additional toolchain needed for Phase 0-1
- `zipfile`, `shutil`, `subprocess`, `hashlib` provide everything needed
- FAF's `fa-python-binary-patcher` is also Python
- FAF's Java launcher is 100K+ lines - massive overkill for our needs
- A GUI can be added later with tkinter or PyQt

### Why C:\ProgramData\WOPC?

- Follows FAF's precedent (they use `%PROGRAMDATA%\FAForever\`)
- Not inside the Steam directory (non-destructive to SCFA)
- Not inside LOUD directory (non-destructive to LOUD)
- Writable without admin on Windows 10/11
- Survives user profile resets

### Why bundle content directly?

- WOPC is designed to fully replace both FAF and LOUD.
- Eliminates dependency on external mod projects that may break compatibility.
- Ensures all users play on an identical, checksum-verified baseline of gamedata, maps, and UI.
- Simplifies the launcher deployment process to a single self-contained application.

### Why fork FA-Binary-Patches instead of using FAF's patcher directly?

- FAF's patches were designed for FAF's Lua codebase
- Some patches may conflict with LOUD's Lua (needs testing)
- We want to add our own C++ patches alongside FAF's
- Forking gives us control over which FAF patches to include

## Phase Details

### Phase 0: Foundation (Complete)

Build the launcher and init file. The game launches from `C:\ProgramData\WOPC\` with LOUD content using the stock (unpatched) exe.

### Phase 1: Validation (Complete)

Play-test LOUD gameplay from the WOPC directory. Fix any path issues. Add content validation (checksums).

### Phase 2: FAF Binary Patching (Complete)

Install the C++ build toolchain (MSYS2 + mingw-w64-i686-gcc + clang). Fork FA-Binary-Patches. Build a FAF-patched exe. Test compatibility with LOUD content.

**Potential conflicts to watch:**
- `FAExtLoad.cpp` tries to load `FAExt.dll` - will fail gracefully (LoadLibrary returns NULL)
- `FixCollisions.cpp` modifies projectile collision - LOUD's projectile Lua may differ
- `PathfindingTweaks.cpp` exposes `SetNavigatorPersonalPosMaxDistance` - harmless addition
- `TableFuncs.cxx` adds optimized table functions - backward compatible

### Phase 3: WOPC Lua Overlay (Complete)

Create `wopc_patches.scd` containing Lua files that:
- Fix any LOUD/FAF incompatibilities found in Phase 2
- Expose new FAF engine functions to LOUD's AI
- Add WOPC-specific enhancements

### Phase 4: Multiplayer (Complete)

Content manifest system for multiplayer sync validation. Players compare checksums before connecting.

### Phase 5: WOPC Advanced Launcher (Complete)

Evolve the command-line script into a graphical interface using CustomTkinter. Provide discrete selection of mod preferences and seamless launching.

### Phase 6: In-Game FAF UI Integration (Complete)

Import FAF's Lua UI as a submodule, compile it into an SCD, and inject it via the VFS layer to provide a modern interface overlapping the legacy LOUD UI. Built a custom Mod Manager config UI.

### Phase 7: deLOUDing & Standalone Overhaul (Complete)

Severing all dependencies on local LOUD installations. All necessary gamedata and assets are sourced directly from the WOPC repository and GitHub releases. Overhauled the CustomTkinter launcher into a modern, Discord-style dark match lobby with direct map launching.

### Phase 8: C++ Engine Patches & Pathfinding

Using FAF's binary patching infrastructure to hook into Moho:
1. **Proof of concept**: Hook `CAiNavigatorImpl::SetGoal()`, log pathfinding requests
2. **"Don't stop, repath"**: Replace the A* "stop and wait on collision" branch with perpendicular repath
3. **Personal space steering**: Add SC2-style unit repulsion at the C++ steering level
4. **Flowfield pathfinding**: Replace A* entirely with a flowfield system (long-term goal)

### Phase 9: Generative Campaign & Deep Refactoring

Introduce a persistent, generative meta-campaign using custom initialization hooks. Push the engine to extreme limits by optimizing rendering bottlenecks and simulation tick rates for 10,000+ unit fields.

### Phase 10: Scoring System Overhaul

Investigate and rewrite the end-game and in-game scoring metrics calculation systems, which currently generate erratic or 'wacky' data, ensuring that both the UI and backend telemetry perfectly match actual in-game performance.

### Engine Architecture (from reverse engineering)

SCFA runs on the Moho engine (GPG, ~2006). Original source is lost.

**Pathfinding**: A* algorithm. Units compute a single fixed path. When blocked by another unit, the engine stops the unit and waits rather than recomputing. This is the root cause of all pathing issues.

**Navigator Lua API** (exposed methods of `CAiNavigatorImpl`):
- `SetGoal(vector)`, `SetDestUnit(entity)`, `AbortMove()`
- `GetStatus()`, `GetGoalPos()`, `GetCurrentTargetPos()`
- `HasGoodPath()`, `FollowingLeader()`, `AtGoal()`, `CanPathToGoal(vector)`
- `IgnoreFormation()`, `BroadcastResumeTaskEvent()`, `SetSpeedThroughGoal(bool)`

**FAF's binary patch infrastructure**:
- FA_Patcher: C++ tool using TCC + AsmJit for code injection
- fa-python-binary-patcher: Python alternative using clang + gcc
- moho.h: Reverse-engineered engine structures
- /hooks: ASM patches at specific exe addresses
- /section: New C/C++ code sections injected into the exe

**Supreme Commander 2 reference**: Used flowfield pathfinding (Eikonal equation, sector/portal decomposition). Documented in Game AI Pro Chapter 23 by Elijah Emerson. The target for Phase 5.
