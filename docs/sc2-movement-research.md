# StarCraft 2 Movement System: Technical Research

Research compiled for the WOPC project (Supreme Commander: Forged Alliance modding).
Goal: understand SC2-style unit movement to inform Phase 7 pathfinding improvements.

---

## 1. Pathfinding Algorithm: Hierarchical Navmesh + Flow Fields

SC2 does **not** use a single algorithm. It uses a multi-layered hybrid system:

### Layer 1: Triangulated Navigation Mesh (Navmesh)

The world is represented as a **constrained Delaunay triangulation** of the terrain and
static obstacles. This was confirmed by James Anhalt (Lead Software Engineer, Blizzard)
at GDC 2011 in the talk "AI Navigation: It's Not a Solved Problem - Yet."

Key details from the GDC talk:
- **Memory layout**: Statically allocated, 16 bytes per triangle face, 4 bytes per vertex.
  Supports up to 64,000 faces and 32,000 vertices.
- **Variable unit sizes**: Portal edges between adjacent triangles define corridor widths.
  Larger units (e.g., Ultralisks) cannot pass through corridors narrower than their radius.
  The system narrows portal edges by the agent radius on both ends.
- **Dynamic obstacles**: Buildings and destructible rocks modify the navmesh at runtime.
  SC2 rebuilds the entire navmesh by resetting to the base mesh and re-inserting all
  dynamic obstacles. (More modern approaches rebuild only the affected subset.)
- **Funnel algorithm**: After A* finds a sequence of triangles, the "Simple Stupid Funnel
  Algorithm" (SSFA) converts the triangle path into a smooth waypoint sequence via
  string-pulling through portal edges.

### Layer 2: Hierarchical A*

For long-distance paths, SC2 does NOT run A* on every triangle. Instead:

1. The navmesh is divided into **regions** connected by **portals** (chokepoints).
2. A coarse A* runs on the region graph (far fewer nodes).
3. The coarse path identifies which regions/portals the unit must traverse.
4. Fine-grained local A* or flow fields are computed only for the regions the unit
   actually enters.

This hierarchical decomposition is critical for performance. A 256x256 map might have
tens of thousands of navmesh triangles, but only a few hundred regions.

### Layer 3: Flow Fields for Group Movement

When many units share the same destination, SC2 generates **flow fields** instead of
computing individual A* paths for each unit:

- A flow field is a grid of directional vectors pointing toward the goal.
- Generated via **Dijkstra flood-fill** from the goal outward.
- Each cell stores a direction vector derived from the integrated cost of reaching the goal.
- All units heading to the same destination sample the same flow field, making the cost
  independent of unit count.
- Flow fields are generated **per-tile/region**, not for the entire map. The hierarchical
  A* determines which tiles need flow fields, and only those are computed.

**When flow fields are used vs. individual A***:
- Small groups (1-5 units): Individual A* paths on the navmesh.
- Large groups (10+ units to same destination): Flow field for the group.
- The exact threshold is not publicly documented.

### Comparison to Supreme Commander

SupCom FA uses a tile-based grid with per-unit A* pathfinding. This is fundamentally
different from SC2's approach:

| Aspect | SupCom FA | StarCraft 2 |
|--------|-----------|-------------|
| World representation | Square grid tiles | Triangulated navmesh |
| Pathfinding | Per-unit A* on grid | Hierarchical A* on navmesh + flow fields |
| Group movement | Each unit paths independently | Shared flow fields for groups |
| Dynamic obstacles | Grid cell blocking | Navmesh rebuild |
| Unit size handling | Footprint-based grid blocking | Portal width filtering |

Supreme Commander 2 (not FA) switched to flow fields, as documented by Elijah Emerson
in Game AI Pro Chapter 23 ("Crowd Pathfinding and Steering Using Flow Field Tiles").
The SupCom2 approach used 10x10 grid sectors with portals, similar in spirit to SC2's
hierarchical decomposition.

---

## 2. Collision and Separation

SC2 uses a **soft collision** model with intentional overlap tolerance:

### Collision Properties (per unit in the SC2 Data Editor)

- **Movement - Radius**: Collision radius with other units.
- **Movement - Inner Radius**: Collision radius with structures (separate from unit-unit).
- **Movement - Collide flags**: Which unit types this unit collides with.

### Separation Force

Units apply a **separation steering force** (Reynolds-style) that pushes them apart:
- Each unit calculates a repulsive vector from all neighbors within its separation radius.
- The force magnitude is **inversely proportional to distance** -- closer neighbors push harder.
- This creates a natural spacing without hard collision walls.

### Overlap Tolerance (Collision Softening)

SC2 deliberately allows **small overlaps** between units rather than enforcing hard
non-penetration constraints. This is a critical design choice:

- Units can temporarily overlap when moving through each other.
- Dense formations are possible without units getting stuck.
- The overlap tolerance prevents the "traffic jam" problem common in hard-collision systems.
- When units are stationary, separation forces gradually resolve overlaps.

### Chokepoint Behavior

At narrow passages:
1. Units queue and stream through in a line (flocking-style).
2. Units do NOT maintain formation through chokepoints -- they break into a stream.
3. Collision radii may be temporarily reduced to allow more units through.
4. Units on the far side re-form as space becomes available.

This is one of the most visible differences from SupCom FA, where units at chokepoints
tend to jam, stop, and struggle to path around each other.

---

## 3. Steering Behaviors

SC2 uses a **modified Reynolds flocking model** with three core behaviors:

### Separation
- Repulsive force from nearby units.
- Scaled inversely with distance (stronger when closer).
- Prevents clustering and overlap.

### Cohesion
- Attractive force toward the center of mass of nearby allies.
- Keeps groups together during movement.
- **Weighted lower than separation** (typically ~0.1x weight) to prevent front-line units
  from being pulled backward and slowing down.

### Alignment
- Steers toward the average velocity direction of nearby units.
- Creates the "streaming" effect where units flow in the same direction.
- Only considers units with similar destinations (not passing traffic).

### Steering Pipeline

The final steering vector is a weighted sum:

```
steer = w_separation * separation
      + w_cohesion * cohesion
      + w_alignment * alignment
      + w_path * path_following
      + w_avoidance * obstacle_avoidance
```

The path-following component steers toward the next waypoint (from A*) or follows the
flow field direction at the unit's current position.

### What Creates the "Sliding" Feel

SC2 units slide around each other rather than stopping. This comes from:
1. **Separation force pushes sideways**, not backward. Units deflect around obstacles
   rather than decelerating.
2. **No hard stop on collision**. Units adjust velocity smoothly rather than halting.
3. **Velocity-based steering**. Changes are applied to velocity, not position, creating
   smooth acceleration curves.

---

## 4. Formation Movement

SC2's formation system is **intentionally loose** compared to games like Total War:

### Default Behavior (No Formation)

When you move-command a group, SC2 does NOT use strict formations:
1. Each unit seeks a position near the destination.
2. Units maintain relative positions loosely via cohesion.
3. The group moves as a **blob/swarm**, not a rectangle or line.
4. Fast units naturally arrive first; slow units trail behind.

### Formation Movement (Editor Feature, Patch 5.0+)

SC2's Galaxy Editor supports formation movement, but it is NOT used in standard gameplay:
- Units form up in a specified pattern before moving.
- Once in formation, they move together maintaining spacing.
- Formations break apart at obstacles and re-form on the other side.
- This feature was added primarily for custom maps and campaigns.

### Group Destination Assignment

When a group is ordered to a point:
1. The system computes a **cluster of destination points** around the target.
2. Each unit is assigned a specific destination within the cluster.
3. Assignment considers unit's current position to minimize crossing paths.
4. Units at the destination spread out to avoid stacking.

### Dynamic Stopping Radius

As more units arrive at a destination, the acceptable stopping radius **increases
dynamically**. This prevents the pathological case where late-arriving units endlessly
circle trying to reach the exact target point that's already occupied.

---

## 5. Blocked/Stuck Unit Handling

### Repath Triggers

Units repath when:
1. Their current path is invalidated (building placed, terrain changed).
2. They are blocked by other units for longer than a threshold.
3. They detect the path ahead is congested (predictive avoidance).

### Stuck Resolution Hierarchy

When a unit cannot reach its destination:

1. **Local detour**: Try a sideways offset to get around the immediate blocker.
2. **Speed adjustment**: Slow down or speed up to let blocking units pass.
3. **Partial repath**: Recompute only the blocked segment, not the entire path.
4. **Full repath**: If local fixes fail, run a complete new pathfinding query.
5. **Collision ignore**: In worst-case scenarios, temporarily reduce or ignore collision
   radius to push through (visible as units briefly overlapping).
6. **Stop**: If the destination is truly unreachable (e.g., walled off), the unit stops
   and the order is cancelled.

### Path Caching and Repair

- Computed paths are **cached** and reused.
- Small invalidations trigger **local path repair** rather than full re-planning.
- This amortization is critical for performance -- full A* re-plans are expensive.

### The "Wiggle"

In multiplayer, units sometimes exhibit a small wiggle or jitter. This can be caused by
different clients in the deterministic lockstep reaching slightly different intermediate
positions during pathfinding, then correcting to agreement. The lockstep model requires
all pathfinding decisions to be deterministic given the same inputs.

---

## 6. Local Avoidance vs. Global Pathing

SC2 clearly separates these two concerns:

### Global Pathing (Strategic Layer)

- **Input**: Start position, goal position, unit size.
- **Output**: Sequence of waypoints through the navmesh.
- **Algorithm**: Hierarchical A* on navmesh triangles, funnel algorithm for smoothing.
- **Frequency**: Computed once per move command; repaired on path invalidation.
- **Scope**: Considers only static geometry (terrain, buildings, destructible rocks).

### Local Avoidance (Tactical Layer)

- **Input**: Current velocity, nearby dynamic obstacles (other units).
- **Output**: Adjusted velocity that avoids immediate collisions.
- **Algorithm**: Velocity obstacle approximations (related to RVO/ORCA family).
- **Frequency**: Every simulation frame (runs at ~22.4 Hz in game-speed "Faster").
- **Scope**: Only considers nearby neighbors within a detection radius.

### How They Interact

```
Each frame:
  1. Global path provides a "desired velocity" (direction toward next waypoint).
  2. Local avoidance modifies the desired velocity to avoid nearby units.
  3. Steering behaviors (separation, cohesion, alignment) further adjust velocity.
  4. The final velocity is applied to the unit's position.
```

### Velocity Obstacles (VO/RVO/ORCA)

The local avoidance layer uses techniques from the **velocity obstacle** family:

- **VO (Velocity Obstacle)**: For each nearby unit, compute a cone of velocities that
  would cause a collision. Avoid those velocities.
- **RVO (Reciprocal Velocity Obstacle)**: Each unit assumes the other will also avoid,
  so each only adjusts by half. Prevents oscillation.
- **ORCA (Optimal Reciprocal Collision Avoidance)**: Uses half-planes instead of cones
  for faster computation (linear programming instead of cone intersection).

SC2 likely uses an approximation of RVO rather than full ORCA, based on the observed
behavior (occasional oscillation that ORCA would prevent). The exact implementation is
not publicly documented.

---

## 7. Performance Optimizations

SC2 handles 200 supply (~100-400 units) per player with these optimizations:

### Amortized Pathfinding

- **Not all units path every frame.** Path requests are queued and processed across
  multiple frames.
- A limited number of A* queries run per frame (budget-based).
- Units waiting for a path continue along their last known good direction.

### Flow Field Sharing

- Units with the same destination share a single flow field.
- Flow field cost is independent of unit count -- 1 unit or 200 units cost the same.
- Flow fields are computed per-tile, so only active tiles incur cost.

### Hierarchical Decomposition

- Coarse region graph reduces A* search space by 10-100x.
- Most path queries never touch the full navmesh.
- Region connectivity is precomputed and updated only when structures change.

### Spatial Partitioning

- Neighbor queries for steering use spatial hashing or grid-based bucketing.
- Each unit only considers neighbors within a fixed radius.
- This keeps per-unit steering cost O(k) where k = nearby neighbors, not O(n) total units.

### Path Caching

- Computed paths are stored and reused.
- Path segments are shared between units on similar routes.
- Local repairs are cheaper than full re-plans.

### Deterministic Lockstep Constraints

- All computations must be **bit-for-bit deterministic** across all clients.
- No floating-point non-determinism allowed (some engines use fixed-point for positions).
- This constrains which optimizations are possible (no parallel non-deterministic updates).

---

## 8. Movement Priority

### Command Recency Priority

- Units executing **newer commands** have priority over those with older commands.
- If a freshly-ordered unit collides with one on an old patrol, the newly-ordered unit
  gets right-of-way.

### Unit Type Priority

- **Workers yield to military units** in contested spaces.
- **Small units yield to large units** when collision resolution requires someone to move.
- SC2's resource harvesters (like SC1) have **reduced collision** when gathering, inheriting
  the original StarCraft hack where harvesters ignore each other near mineral patches.

### Push Mechanics

When two units collide:
1. Both receive a push force in opposite directions.
2. The lighter/lower-priority unit receives a **larger push force**.
3. Stationary units yield to moving units (a stopped unit will shift aside).
4. If both are moving, the one with the older command yields.

This asymmetric push is why attacking armies seem to "flow through" defending armies --
the attacker's fresh commands give them movement priority.

---

## 9. What Makes SC2 Movement Feel "Smooth"

The "flow" feeling in SC2 comes from several deliberate design choices:

### No Hard Stops

Units never abruptly stop when encountering another unit. They decelerate smoothly,
deflect sideways, or find alternate routes. The velocity-based steering model ensures
continuous motion.

### Acceleration/Deceleration Curves

Each unit has tuned **acceleration** and **deceleration** values:
- Workers and air units have lower acceleration (feel heavier).
- Small ground units have high acceleration (snappy response).
- Deceleration applies when approaching a stop point, preventing overshoot.

### Turning Rate

Units have a **turning rate** (yaw speed) that determines how quickly they can change
direction. This creates smooth arcing turns rather than instant direction changes.

### Intentional Overlap Tolerance

The soft collision model means units can briefly overlap, which prevents the "gridlock"
feeling of hard-collision systems. Units flow through each other slightly rather than
jamming.

### Stream-Based Group Movement

Rather than trying to move as a rigid formation, SC2 lets units **stream** toward the
destination. Faster units lead, slower units trail, and the group naturally finds
efficient paths through narrow spaces. This feels organic rather than robotic.

### Responsive Command Latency

SC2's simulation runs at approximately 22.4 Hz (on "Faster" game speed), but input
is processed every frame. Units begin responding to commands immediately (within 1-2
simulation steps), creating a sense of responsiveness.

### Flocking Coherence

The alignment steering behavior makes nearby units move in the same direction, creating
a visually coherent "flowing army" rather than chaotic individual paths.

---

## 10. Key References and Sources

### GDC Talks

- **"AI Navigation: It's Not a Solved Problem - Yet"** (GDC 2011)
  - Speakers: James Anhalt (Blizzard), Alexander Kring (Nihilistic), Nathan Sturtevant (U. Denver)
  - Anhalt covered SC2's navmesh architecture, memory layout, and hierarchical pathfinding.
  - https://gdcvault.com/play/1014514/AI-Navigation-It-s-Not

- **"Pathing in Age of Empires IV: Flow Fields and Steering Behaviors"** (GDC 2022)
  - Speaker: Frank Cheng (Relic Entertainment)
  - Covers a modern flow field + steering implementation in a shipping RTS.
  - Relevant because AoE4 faces similar scale challenges to SC2.

### Books and Papers

- **Game AI Pro, Chapter 23**: "Crowd Pathfinding and Steering Using Flow Field Tiles"
  by Elijah Emerson. Describes the Supreme Commander 2 flow field system.
  - http://www.gameaipro.com/GameAIPro/GameAIPro_Chapter23_Crowd_Pathfinding_and_Steering_Using_Flow_Field_Tiles.pdf

- **Game AI Pro 3, Chapter 19**: "RVO and ORCA: How They Really Work"
  by Ben Sunshine-Hill. Technical deep-dive on reciprocal velocity obstacles.
  - http://www.gameaipro.com/GameAIPro3/GameAIPro3_Chapter19_RVO_and_ORCA_How_They_Really_Work.pdf

- **"Reciprocal Collision Avoidance for Real-Time Multi-Agent Simulation"**
  (RVO2 Library, UNC Chapel Hill). The academic foundation for ORCA.
  - https://gamma.cs.unc.edu/RVO2/

### Developer Blogs and Community Analysis

- **"Pathfinding in Starcraft 2"** by Dean Harding (2010). Early analysis of SC2 beta
  pathfinding with flocking observations.
  - https://codeka.com/blog/2010/03/pathfinding-in-starcraft-2

- **"The StarCraft Path-Finding Hack"** by Patrick Wyatt (original SC1 developer).
  Documents the harvester collision hack that SC2 inherited.
  - https://www.codeofhonor.com/blog/the-starcraft-path-finding-hack

- **RTS Pathfinding series** by jdxdev. Practical implementation of flow fields and
  dynamic navmesh for RTS games, with SC2 comparisons.
  - https://www.jdxdev.com/blog/2020/05/03/flowfields/
  - https://www.jdxdev.com/blog/2021/07/06/rts-pathfinding-2-dynamic-navmesh-with-constrained-delaunay-triangles/

- **"Movements and Collisions in RTS"** by Simon Picarter. Covers ORCA-based collision
  with weight-based priority, directly referencing SC2's approach.
  - https://simonpicarter.itch.io/fair-and-square/devlog/540419/movements-and-collisions-in-rts

- **Group Movement research** by Aitor Simona. Academic-quality breakdown of SC2's
  movement layers with references to the Anhalt GDC talk.
  - https://aitorsimona.github.io/Research_GroupMovement/

### GameDev.net Forum Threads

- **"What's StarCraft 2's pathfinding tech?"** - Community analysis thread.
  - https://gamedev.net/forums/topic/563819-whats-starcraft2s-pathfinding-tech/
- **"Does SC2 use navmesh A* or grid A*?"** - Confirms navmesh with Anhalt GDC details.
  - https://gamedev.net/forums/topic/624135-does-starcraft2-use-navmesh-a-or-grid-a-for-pathfinding/
- **"How to do StarCraft 2 pathfinding?"** - Implementation discussion.
  - https://www.gamedev.net/forums/topic/648438-how-to-do-starcraft-2-pathfinding/

---

## Applicability to WOPC / Supreme Commander: Forged Alliance

### What We Can Realistically Implement (Engine Constraints)

SCFA's engine is a fixed C++ binary that we patch via binary hooks. We cannot rewrite
the core pathfinding. However, we can:

1. **Tune unit movement parameters** via Lua blueprints (speed, acceleration, turn rate).
2. **Modify formation behavior** via Lua scripts in the sim layer.
3. **Adjust collision/separation distances** via blueprint values.
4. **Hook into C++ pathfinding** via binary patches to modify behavior at key decision points.

### Key Takeaways for WOPC Phase 7

1. **Soft collision is essential.** SC2's overlap tolerance prevents gridlock. SCFA's
   hard collision model is a major contributor to unit jamming. Even small overlap
   tolerance (10-20% of unit radius) would dramatically improve flow.

2. **Steering behaviors matter more than pathing algorithms.** SC2's global pathing is
   good, but the smooth feel comes from the local steering layer (separation + alignment +
   cohesion). Adding Reynolds-style flocking to SCFA units would have outsized impact.

3. **Flow fields are the gold standard for group movement.** Per-unit A* does not scale.
   If binary patching allows it, replacing group pathfinding with flow fields would be the
   single largest improvement.

4. **Asymmetric push priority** creates intuitive behavior. Fresh commands should have
   priority; larger units should push smaller ones. This is implementable in Lua.

5. **Stream, don't form.** SC2 deliberately avoids rigid formations for army movement.
   Units stream through chokepoints naturally. Trying to maintain formation through tight
   spaces causes jams.

6. **Dynamic stopping radius** prevents the "circling" problem where late-arriving units
   endlessly seek an occupied destination point. Expand the acceptable arrival radius as
   more units arrive.

---

## Current WOPC Phase 7 Status vs. SC2 Reference

### What We've Already Done

| SC2 Concept | WOPC Implementation | Status |
|-------------|-------------------|--------|
| Blocked timer tuning | `WayPointArrive.cpp` — caps blocked ticks at 20 (vanilla 40-80) | ✅ Working |
| Formation tightness | `SetNavigatorPersonalPosMaxDistance(10.0)` (vanilla 50.0) | ✅ Working |
| Lua stats API | `GetPathfindingStats()` — calls/tick, total requests, blocked repaths | ✅ Working |
| Toggleable mod | `bundled/usermods/wopc_pathing/` with `selectable = true` | ✅ Working |
| Zero-collision diagnostic | `movement_tuning.lua` — removes collision shapes for testing | ✅ Diagnostic only |

### What We Should Build Next (Priority Order)

**Tier 1 — High impact, achievable via binary hooks:**

1. **Soft collision tolerance** — Hook the collision response function to allow 10-20%
   radius overlap before applying push forces. This is the single highest-impact change
   from SC2's model. SCFA's hard collision is the #1 cause of unit jamming.
   - Target: `CAiNavigatorImpl` collision check functions (addresses mapped in Phase 7)
   - Approach: Reduce effective collision radius by a configurable percentage during movement

2. **Asymmetric push priority** — When two units collide, the one with the newer move
   command gets priority. Stationary units yield to moving units.
   - Target: Collision response handler in the navigator
   - Approach: Hook collision resolution to weight push force by command age

3. **Faster repath on block** — We already cap the blocked timer at 20 ticks. SC2 goes
   further: blocked units try a sideways detour before full repath. Can we hook the
   "blocked" state to issue a lateral offset move?
   - Target: `WayPointArrive.cpp` blocked state handler
   - Approach: When blocked timer fires, offset the next waypoint perpendicular to the path

**Tier 2 — Medium impact, requires more reverse engineering:**

4. **Separation steering** — Add a Reynolds-style separation force that pushes units apart
   smoothly rather than using hard collision stops. This would run in Lua sim, not C++.
   - Approach: Periodic Lua thread that applies `IssueMove()` nudges based on neighbor proximity
   - Risk: May conflict with existing movement commands (the navigator API corruption issue)

5. **Dynamic stopping radius** — When multiple units arrive at the same destination,
   expand the acceptable arrival zone. Prevents the "circling" behavior.
   - Approach: Hook `SetGoal()` to expand the arrival tolerance based on nearby unit density

**Tier 3 — Transformative but requires deep engine work:**

6. **Flow fields for group movement** — Replace per-unit A* with shared flow fields for
   groups moving to the same destination. This is the holy grail but requires significant
   reverse engineering of the pathfinding grid.
   - Would need: Grid accessor hooks, flow field generation in C++, integration with navigator
   - Complexity: Very high. This is a multi-month effort.

### SC2 Techniques We Cannot Implement

- **Navmesh replacement**: SCFA uses a tile grid, not a navmesh. Replacing the world
  representation would require rewriting core engine systems. Not feasible via hooks.
- **Funnel algorithm**: Requires a navmesh. Our grid doesn't have portal edges to pull through.
- **Per-frame velocity steering**: SCFA's sim loop doesn't expose a velocity-based steering
  interface. Units receive move commands, not velocity adjustments. We can approximate
  steering via rapid `IssueMove()` but it's not the same fidelity.
