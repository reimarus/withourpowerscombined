# SCFA Pathfinding & Movement — Reverse Engineering Notes

> Living document. Every struct offset documented here has been derived from
> existing binary patch source (inline asm in hooks/sections) or from
> `include/moho.h`. Offsets marked ❓ are inferred but unverified.

## Key Classes

### Unit (0x6A8 bytes, moho.h line 925)

```
+0x070: uint32_t UnitID
+0x074: RUnitBlueprint* Blueprint
+0x08C: Vector3f Scale
+0x090: float CurHealth
+0x094: float MaxHealth
+0x0A4: Vector4f Rot1
+0x0B4: Vector3f Pos1
+0x0E0: float FractionComplete
+0x150: Sim* sim
+0x154: SimArmy* owner
+0x4B0: void* MotionEngine       // CMotorLand* for land units
+0x4B4: void* CommandQueue
+0x4B8: int Enum                 // 0..4
+0x544: void* IAiAttacker
+0x548: void* IAiCommandDispatch
```

Note: `Unit+0x4B0` (MotionEngine) is key. The WayPointArrive hook at 0x598E80
receives the MotionEngine as `this` (ecx register), NOT the Unit.

### CMotorLand (size unknown, partial layout from WayPointArrive.cpp)

The WayPointArrive hook at `0x598E80` uses `edi` = `this` = CMotorLand instance.

```
+0x1C: void* parentUnit          // CUnit* — back-pointer to owning unit
+0x2C: int status                // compared against 2 (moving vs arrived?)
+0x40: byte arrivalFlag          // set/cleared on waypoint arrive
+0x44: void* waypointContainer   // navigator or waypoint list pointer
```

From `[waypointContainer+0x10]` and `[waypointContainer+0x14]`:
- `+0x10`: pointer to start of waypoint array
- `+0x14`: pointer to end of waypoint array
- Waypoints are 8-byte entries (sar edx, 0x3 for count)

From the waypoint entry (via `[array_start]`):
```
waypoint_obj = [array_start] - 0x4    // pointer with -4 adjustment
waypoint_obj+0x98:  int commandType   // compared against 0xA (10), 0x10 (16), 0x12 (18)
waypoint_obj+0xE0:  int maxBlockedTicks  // original countdown value
waypoint_obj+0xE4:  int blockedTicks     // countdown, decrements each tick when blocked
waypoint_obj+0x11C: int ❓unk           // compared against 2
waypoint_obj+0x141: byte needsRepath     // set to 1 when blocked timer expires
```

The blocked-timer logic (WayPointArrive lines 49-64):
1. Read `blockedTicks` at `+0xE4`
2. If > 1: decrement by 1, set `needsRepath` flag at `+0x141`
3. If == 1: check various conditions, then either reload from `maxBlockedTicks` (+0xE0)
   or call repath function at `0x6EDE70` or `0x6EDFC0`

### Key engine functions (from LuaCFuncs.h)

Navigator (CAiNavigatorImpl):
```
0x5A5860: SetGoal(x, y, z)
0x5A5A90: SetDestUnit(unit)
0x5A5BF0: AbortMove()
0x5A5D20: BroadcastResumeTaskEvent()
0x5A5E50: SetSpeedThroughGoal()
0x5A5F90: GetCurrentTargetPos() → x, y, z
0x5A6100: GetGoalPos() → x, y, z
0x5A6270: GetStatus() → 0=Idle, 1=Thinking, 2=Steering
0x5A6500: HasGoodPath() → bool
0x5A6640: IgnoreFormation()
0x5A6780: IsIgnoringFormation() → bool
0x5A68C0: AtGoal() → bool
0x5A6A00: CanPathToGoal() → bool
```

Motor:
```
0x695720: MotorFallDown:Whack(x, y, z, depth, flag)
```

Unit → Navigator access:
```
0x6CC2D0: UnitGetNavigator(lua_State*) — gets navigator from unit
```

Repath/navigation internal:
```
0x6EDE70: ❓ repath function (called when blocked timer expires, no good path)
0x6EDFC0: ❓ advance/pop waypoint (called on successful waypoint arrival)
0x598B90: ❓ check function (returns bool, called near end of WayPointArrive)
0x6EDBF0: ❓ get next waypoint info
0x608EF0: ❓ transition to new movement state (takes waypoint_info, motor_ptr)
```

Guard/formation:
```
0x6ACC95: GuardFix hook — reads Unit+0x4B4 (CommandQueue), then
          command[0]+0x94 (formation flags, AND 0x30 test)
          command+0x460 (GuardScanRadius float via MOVSS)
```

### REntityBlueprint::SFootprint (moho.h line 385)

```
+0x00: char SizeX
+0x01: char SizeZ
+0x02: char OccupancyCaps
+0x03: char Flags
+0x04: float MaxSlope
+0x08: float MinWaterDepth
+0x0C: float unk1
```

Blueprint footprint is at `REntityBlueprint+0xD8` (and AltFootprint at +0xE8).
For a Unit: `unit->Blueprint->Footprint.SizeX` etc.

### SimArmy pathCap fields (moho.h line 744)

```
SimArmy+0x278: int pathCap_Land
SimArmy+0x27C: int pathCap_Sea
SimArmy+0x280: int pathCap_Both
```

## Debug Tools

- `ren_Steering` — enabled by `EnableConsoleCommands.cpp`, renders steering vectors in-game
- `PathfindingTweaks.cpp` — exposes `SetNavigatorPersonalPosMaxDistance(float)` to Lua (default 50.0)

## TODO — Needs Verification

1. Map the full CAiNavigatorImpl struct by disassembling the Lua binding functions
   (0x5A5860 through 0x5A6A00). Each reads `this+offset` to access navigator fields.
2. Find the spatial grid / collision query system for nearby-unit lookups.
3. Map the steering update function that runs each tick for moving units.
4. Determine exact relationship between MotionEngine and Navigator — is Navigator
   a member of MotionEngine, or accessed through waypointContainer?
5. Verify `blockedTicks` field (+0xE4) default value by observing in-game with
   diagnostic patch.
