# Pathfinding Research — Phase 7

## Current State

SCFA uses a stop-and-wait A* pathfinding algorithm. Units path to one waypoint at a time, stop, then path to the next. This feels sluggish compared to modern RTS games like StarCraft 2 which use continuous movement.

## Engine Navigator API

The `CAiNavigatorImpl` class handles unit navigation. Known function addresses:

| Function | Address | Purpose |
|----------|---------|---------|
| `SetGoal` | `0x5A5860` | Set movement destination |
| `SetDestUnit` | `0x5A5A90` | Follow a unit |
| `AbortMove` | `0x5A5BF0` | Cancel movement |
| `SetSpeedThroughGoal` | `0x5A5E50` | Speed at arrival |
| `GetCurrentTargetPos` | `0x5A5F90` | Current target |
| `GetGoalPos` | `0x5A6100` | Final destination |
| `GetStatus` | `0x5A6270` | Navigator state |
| `HasGoodPath` | `0x5A63C0` | Path quality |
| `FollowingLeader` | `0x5A6500` | Formation state |
| `AtGoal` | `0x5A68C0` | Arrived check |
| `CanPathToGoal` | `0x5A6A00` | Pathability check |
| `UnitGetNavigator` | `0x6CC2D0` | Get from unit |

## Unit Struct Layout

Key offsets in the `Unit` struct (0x6A8 bytes total):
- `0x4B0`: `MotionEngine*` — physical movement controller
- `0x4B4`: `CommandQueue*` — command dispatch
- `0x4B8`: `int Enum` — state (0..4)

## WOPC Pathfinding Patch

### Files

| File | Purpose |
|------|---------|
| `vendor/FA-Binary-Patches/section/WopcPathfinding.cpp` | C++ section — Lua API + counters |
| `vendor/FA-Binary-Patches/hooks/WopcPathfinding.hook` | ASM hook — SetGoal instrumentation |

### New Lua Functions

```lua
-- Get pathfinding performance counters
local stats = GetPathfindingStats()
-- stats.calls_per_tick: SetGoal calls in the last tick
-- stats.total_requests: Total path requests since game start

-- Control path smoothing (future use)
SetPathSmoothingDistance(100.0)  -- 0 = vanilla behavior

-- Reset counters
ResetPathfindingStats()
```

### Build

```bash
wopc patch --clean   # Build with new patches
wopc setup           # Deploy patched exe
```

## Next Steps

1. **Observe**: Launch games and call `GetPathfindingStats()` to understand pathing load
2. **Reverse engineer**: Disassemble `SetGoal` to understand the internal A* implementation
3. **Path smoothing**: Hook the per-tick movement update to skip unnecessary waypoints
4. **Continuous movement**: Replace stop-at-waypoint with smooth interpolation
5. **Local avoidance**: Add RVO2-style unit collision avoidance
6. **Flowfield**: For large groups, generate shared flowfields instead of per-unit A*

## Key Constraints

- **32-bit only**: All code must target i686
- **Deterministic**: Pathfinding changes must produce identical results on all clients (multiplayer desync prevention)
- **No new dependencies**: C++ patches compile standalone with Clang/GCC
- **Backward compatible**: Existing save games and replays must still work
