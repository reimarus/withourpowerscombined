# WOPC Architecture

## Overview

WOPC merges LOUD's gameplay (545 modified Lua files, 888MB of content packs, complete AI overhaul) with FAF's binary-patched engine (66 hooks + 53 C++ code sections). The result is a self-contained game distribution at `C:\ProgramData\WOPC\` that leaves both Steam SCFA and LOUD installations untouched.

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
    lua.scd                 LOUD core Lua (symlinked from LOUD)
    units.scd               LOUD units (symlinked)
    brewlan.scd             BrewLAN content (symlinked)
    ... (17 SCD files)
    wopc_patches.scd        Our overlay patches
  maps\                     Symlinked from LOUD
  sounds\                   Symlinked from LOUD
  usermods\                 Copied from LOUD (BetterPathing etc.)
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

### Why symlinks for content?

- 888MB of SCD files cannot go in a git repo
- LOUD is actively maintained - users get latest content automatically
- Symlinks avoid disk space duplication
- Fallback to file copy when symlinks require admin

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

### Phase 5: C++ Engine Patches

The main event. Using FAF's binary patching infrastructure:

1. **Proof of concept**: Hook `CAiNavigatorImpl::SetGoal()`, log pathfinding requests
2. **"Don't stop, repath"**: Replace the A* "stop and wait on collision" branch with perpendicular repath
3. **Personal space steering**: Add SC2-style unit repulsion at the C++ steering level
4. **Flowfield pathfinding**: Replace A* entirely with a flowfield system (long-term goal)

### Phase 6: WOPC Advanced Launcher

Evolve the command-line script into a graphical interface:
- Discrete selection of mod preferences
- Toggling of experimental engine patches
- Profile saving and sharing

### Phase 7: Roguelike Campaign System

Introduce a persistent, generative meta-campaign using our custom initialization hooks:
- Randomized tech trees and AI threats
- Persistent commander upgrades between skirmishes
- Cooperative progression with friends

### Phase 8: Deep C++ Refactoring

Beyond pathfinding, push the engine to its absolute limits:
- Rewrite rendering bottlenecks
- Optimize simulation tick rate for 10,000+ unit fields
- Expose new multi-threading capabilities to the Lua AI

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
