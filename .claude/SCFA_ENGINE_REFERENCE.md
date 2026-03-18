# SCFA Engine API Reference (Curated for WOPC Development)

> Extracted from FAF engine annotations (`vendor/faf-ui/engine/`), FAF source code,
> and hard-won debugging experience. This file is the authoritative quick-reference
> for writing SCFA Lua code in the WOPC project.

---

## 1. SCFA Lua Dialect (NOT Standard Lua)

SCFA uses a **modified Lua 5.0 fork**. Key differences from standard Lua:

| Feature | Standard Lua | SCFA Lua |
|---------|-------------|----------|
| Not-equal | `~=` | `!=` |
| Loop continue | not available | `continue` keyword works |
| Table length | `#t` | `table.getn(t)` |
| Random numbers | `math.random()` | `Random(min, max)` global |
| Modulo | `%` operator | not available; use `math.mod(a, b)` |
| String format | `string.format()` | works, same as Lua 5.0 |
| Pairs iteration | `for k, v in pairs(t)` | `for k, v in t do` (pairs is implicit) |
| Import | `require()` | `import('/path/to/module.lua')` |

**Other quirks:**
- `repr(object)` pretty-prints any Lua value (engine global)
- `dofile(path)` executes a file and returns its result
- `doscript(path, env?)` runs a script with optional environment table
- String concatenation: `..` operator works normally
- `tostring()` and `tonumber()` work normally
- `pcall(func)` works for error handling
- No `xpcall`, no `setfenv`, no `getfenv`

---

## 2. Engine Globals (Available Everywhere)

### Threading & Timing
```lua
ForkThread(callback, ...)        --> thread    -- Spawn async coroutine
WaitSeconds(seconds)                           -- Pause thread (float seconds)
WaitTicks(ticks)                               -- Pause thread (sim ticks or UI frames)
WaitFrames(frames)                             -- Pause for N frames (UI state only)
WaitFor(manipulator)                           -- Pause until manipulator reaches goal
CurrentThread()                  --> thread?   -- Get current running thread
KillThread(thread)                             -- Destroy a thread
SuspendCurrentThread()                         -- Suspend indefinitely (use ResumeThread to wake)
ResumeThread(thread)                           -- Resume a suspended thread
```

### Logging
```lua
LOG(...)                                       -- Standard log output
WARN(...)                                      -- Warning level
SPEW(...)                                      -- Debug/verbose level
repr(object)                     --> string    -- Pretty-print any Lua object
```

### Random & Math
```lua
Random()                         --> number    -- Random float [0, 1]
Random(max)                      --> number    -- Random int [1, max]
Random(min, max)                 --> number    -- Random int [min, max]
MATH_IRound(number)              --> integer   -- Banker's rounding (half-round-even)
MATH_Lerp(s, a, b)              --> number    -- Linear interpolation
```

### Command Line & Preferences
```lua
GetCommandLineArg(option, maxArgs) --> string[] | false  -- Parse CLI args after option
HasCommandLineArg(option)          --> boolean            -- Check if CLI arg exists
GetPreference(key, default?)       --> any                -- Read from prefs file
SetPreference(key, value)                                 -- Write to prefs file (delayed disk write)
SavePreferences()                                         -- Force immediate disk write
```

### Entity & Destruction
```lua
IsDestroyed(entity?)             --> boolean   -- Check if C-side object is deallocated
TrashBag()                       --> TrashBag  -- Destruction container
  -- TrashBag:Add(destroyable)                 -- Add item for cleanup
  -- TrashBag:Destroy()                        -- Destroy all added items
```

### Class System
```lua
Class(BaseClass, ...) { ... }    --> class     -- Create class (sim or shared)
ClassUI(BaseClass, ...) { ... }  --> class     -- Create UI class
State(BaseClass, ...) { ... }    --> state     -- Create state variant
```

### File System (VFS)
```lua
DiskFindFiles(directory, pattern) --> FileName[]   -- Find files matching pattern
DiskGetFileInfo(filename)         --> table|false   -- File metadata or false
DiskToLocal(systemPath)           --> FileName      -- System path to VFS path
exists(name)                      --> boolean       -- Check if VFS resource exists
import(path)                      --> module        -- Import Lua module (last-added priority!)
```

### VFS Mount (Init File ONLY)
```lua
mount_dir(archivePath, mountPoint)  -- Mount archive/directory in VFS
mount_mods(modsPath)                -- Mount user mods directory
-- NOTE: These are ONLY available during init file execution, NOT in UI/sim state
```

---

## 3. LobbyComm API (Multiplayer Networking)

### Creating a Lobby
```lua
-- InternalCreateLobby is THE way to create P2P lobby instances.
-- First arg is the Lua class table that will receive engine callbacks.
---@generic T
---@param lobbyClass T              -- Custom class extending moho.lobby_methods
---@param protocol "UDP"|"TCP"      -- Network protocol
---@param localPort number          -- Port to bind (0 = engine picks)
---@param maxConnections number     -- Max peers (16 typical)
---@param playerName string         -- Local player display name
---@param playerUID? string         -- Player unique ID (nil for LAN)
---@param natTraversal? userdata    -- NAT traversal provider (nil for LAN)
---@return T
InternalCreateLobby(lobbyClass, protocol, localPort, maxConnections, playerName, playerUID, natTraversal)
```

**IMPORTANT:** `LobbyComm.CreateLobbyComm()` in `lobbyComm.lua` does NOT accept a custom class.
It always uses the built-in `LobbyComm` class. For custom lobby behavior (like WOPC's multilobby),
use `InternalCreateLobby()` directly with your own class table.

### moho.lobby_methods (Base Class)

Methods you **call** on the lobby instance:
```lua
comm:HostGame()                                    -- Begin hosting (makes lobby discoverable)
comm:JoinGame(address, remoteName?, remotePeerId?) -- Join a hosted game
comm:SendData(peerId, data)                        -- Send table to one peer
comm:BroadcastData(data)                           -- Send table to all peers
comm:LaunchGame(gameConfig)                        -- Launch into simulation
comm:GetLocalPlayerID()     --> UILobbyPeerId      -- Your peer ID (string like "0", "1", etc.)
comm:GetLocalPlayerName()   --> string             -- Your display name
comm:GetLocalPort()         --> number|nil         -- Bound port
comm:GetPeer(peerId)        --> Peer               -- Get specific peer info
comm:GetPeers()             --> Peer[]             -- Get all peer info
comm:IsHost()               --> boolean            -- Are we the host?
comm:ConnectToPeer(address, name, peerId)          -- Manual peer connection
comm:DisconnectFromPeer(peerId)                    -- Disconnect specific peer
comm:EjectPeer(peerId, reason)                     -- Kick a peer
comm:MakeValidGameName(name)    --> string         -- Sanitize game name
comm:MakeValidPlayerName(peerId, name) --> string  -- Sanitize player name
comm:Destroy()                                     -- Destroy lobby, disconnect all
```

### Engine Callbacks (Override These)

These are called BY the engine on your lobby class instance:
```lua
Hosting(self)
    -- Host is ready to accept connections.
    -- Set up game state, start launch polling thread.

ConnectionToHostEstablished(self, localPeerId, nameOrHostPeerId, hostPeerId?)
    -- Joiner: successfully connected to host.
    -- Engine may pass 2 or 3 args depending on version.
    -- Handle both: actualHostPeerId = hostPeerId or nameOrHostPeerId

EstablishedPeers(self, peerId, peerConnectedTo)
    -- A new peer has connected to the lobby mesh.
    -- Track in your connected peers table.

DataReceived(self, data)
    -- Received data from another peer.
    -- data.SenderID = peer ID (string)
    -- data.SenderName = peer display name
    -- data.Type = message type string (your protocol)

GameLaunched(self)
    -- Engine has transitioned to simulation state.
    -- Clean up lobby UI here.

ConnectionFailed(self, reason)
    -- Connection attempt failed. Show error to user.

Ejected(self, reason)
    -- Disconnected from host. Show error to user.

SystemMessage(self, text)
    -- Engine system notification.

LaunchFailed(self, reasonKey)
    -- LaunchGame() failed.

PeerDisconnected(self, peerName, uid)
    -- A peer has left the lobby.

Connecting(self)
    -- Joiner: attempting to connect to host.

GameConfigRequested(self)
    -- Engine is requesting game configuration.
```

### Peer Object Structure
```lua
---@class Peer
---@field id UILobbyPeerId           -- "-1" when status is pending
---@field name string                 -- Display name
---@field status UIPeerConnectionStatus  -- 'None'|'Pending'|'Connecting'|'Answering'|'Established'|'TimedOut'|'Errored'
---@field ping number                 -- Latency in ms
---@field quiet number                -- Time since last message
---@field establishedPeers UILobbyPeerId[]  -- Peers this peer is connected to
```

### Launch Configuration (gameConfig)

The table passed to `comm:LaunchGame(gameConfig)`:
```lua
---@class UILobbyLaunchConfiguration
gameConfig = {
    GameOptions = {
        ScenarioFile = '/maps/mapname/mapname_scenario.lua',  -- REQUIRED by engine
        UnitCap = '1500',           -- string! Engine reads this
        CheatsEnabled = 'false',    -- string!
        FogOfWar = 'explored',      -- 'explored' | 'unexplored' | 'none'
        NoRushOption = 'Off',
        PrebuiltUnits = 'Off',
        Timeouts = '3',
        CivilianAlliance = 'enemy',
        GameSpeed = 'normal',       -- 'normal' | 'fast' | 'adjustable'
        Score = 'no',
        TeamSpawn = 'fixed',
        TeamLock = 'locked',
        Victory = 'demoralization', -- 'demoralization' | 'domination' | 'eradication' | 'sandbox'
        Share = 'FullShare',
        RestrictedCategories = {},
    },

    PlayerOptions = {
        [1] = {
            StartSpot = 1,            -- number: spawn position index
            Team = 1,                 -- number: team number
            Faction = 1,              -- number: 1=UEF, 2=Aeon, 3=Cybran, 4=Seraphim
            PlayerName = 'Player 1',  -- string
            Human = true,             -- boolean
            Civilian = false,         -- boolean
            AIPersonality = '',       -- string: AI type (empty for humans)
            OwnerID = '0',            -- string! Peer ID. MUST be string, not number.
            PlayerColor = 1,          -- number: color index
            ArmyColor = 1,            -- number: color index
            Ready = true,             -- boolean
        },
        -- ... more players
    },

    Observers = {},  -- Same structure as PlayerOptions but for observers

    GameMods = {
        -- Array of ModInfo tables (from Mods.GetGameMods)
        { name = 'ModName', uid = 'mod-uid-string', ... },
    },
}
```

**CRITICAL:** `OwnerID` MUST be a **string** (peer ID like `"0"`, `"1"`), NOT a number.
The engine will crash or behave incorrectly if it receives a number.

---

## 4. UI Framework (MAUI)

### Getting the Root Frame
```lua
GetFrame(0)                      --> Frame     -- Primary display adapter
GetFrame(1)                      --> Frame     -- Secondary adapter (dual monitor)
GetNumRootFrames()               --> number    -- Usually 1
```

### Creating UI Controls
```lua
-- All UI controls are created via Internal* functions, but typically
-- you use the Lua wrapper classes:
local Bitmap = import('/lua/maui/bitmap.lua').Bitmap
local Text = import('/lua/maui/text.lua').Text
local Group = import('/lua/maui/group.lua').Group
local Edit = import('/lua/maui/edit.lua').Edit

-- Create controls with parent
local bg = Bitmap(parentControl)
bg:SetSolidColor('ff000000')     -- ARGB hex string

-- Layout helpers
local LayoutHelpers = import('/lua/maui/layouthelpers.lua')
LayoutHelpers.FillParent(child, parent)
LayoutHelpers.AtCenterIn(child, parent, yOffset, xOffset)
LayoutHelpers.AtTopIn(child, parent, offset)
LayoutHelpers.AtLeftIn(child, parent, offset)
LayoutHelpers.AtRightIn(child, parent, offset)
LayoutHelpers.AtBottomIn(child, parent, offset)
LayoutHelpers.RightOf(child, anchor, offset)
LayoutHelpers.Below(child, anchor, offset)

-- UIUtil convenience
local UIUtil = import('/lua/ui/uiutil.lua')
local text = UIUtil.CreateText(parent, 'Hello', fontSize, UIUtil.bodyFont)
text:SetColor('ffffffff')        -- ARGB hex
text:SetDropShadow(true)
```

### Control Depth (Z-Order)
```lua
control.Depth:Set(500)           -- Higher = on top
```

### Destroying Controls
```lua
control:Destroy()                -- Remove from UI tree
```

---

## 5. Preferences System (In-Game)

```lua
local Prefs = import('/lua/user/prefs.lua')

-- Profile-scoped preferences (per-player)
Prefs.GetFromCurrentProfile(key)          --> value
Prefs.SetToCurrentProfile(key, value)

-- Global preferences
GetPreference(key, default?)              --> value    -- Engine global
SetPreference(key, value)                              -- Engine global
```

---

## 6. Map & Scenario

```lua
local MapUtil = import('/lua/ui/maputil.lua')
local scenarioInfo = MapUtil.LoadScenario(scenarioFilePath)

-- scenarioInfo contains:
--   .name, .description, .map (path to .scmap)
--   .size = {width, height}
--   .Configurations.standard.teams[1].armies = {'ARMY_1', 'ARMY_2', ...}
```

---

## 7. Mod System

```lua
local Mods = import('/lua/mods.lua')

-- Resolve mod UIDs to full ModInfo tables for LaunchGame
---@param uidSet table<string, boolean>  -- {['mod-uid'] = true, ...}
---@return ModInfo[]                     -- Sorted, validated, sim-only mods
Mods.GetGameMods(uidSet)

-- Get user's selected mods from preferences
Mods.GetSelectedMods()           --> table<string, boolean>
```

---

## 8. Game State & Session (UI State Only)

```lua
GetCurrentUIState()              --> 'splash'|'frontend'|'game'|'none'
SessionIsActive()                --> boolean
SessionIsMultiplayer()           --> boolean
SessionIsReplay()                --> boolean
SessionIsPaused()                --> boolean
SessionIsGameOver()              --> boolean
GameTime()                       --> number (seconds, pauses when game paused)
GameTick()                       --> number (sim ticks)
GetGameSpeed()                   --> number
CurrentTime()                    --> number (wall-clock seconds since app start)
ExitApplication()                                -- Force quit
ExitGame()                                       -- Quit sim, not app
```

---

## 9. Unit Commands (Sim State)

```lua
-- These are the primary sim-side unit command functions:
IssueMove(units, position)       --> SimCommand
IssueAttack(units, target)       --> SimCommand
IssueGuard(units, target)        --> SimCommand
IssuePatrol(units, position)     --> SimCommand
IssueReclaim(units, target)      --> SimCommand
IssueRepair(units, target)       --> SimCommand
IssueCapture(units, target)      --> SimCommand
IssueTransportLoad(units, transport) --> SimCommand
IssueTransportUnload(units, pos) --> SimCommand
IssueUpgrade(units, blueprintID) --> SimCommand
IssueBuildFactory(units, bpID, count) --> SimCommand
IssueClearCommands(units)        --> SimCommand
IssueStop(units)
IssueNuke(units, position)       --> SimCommand
IssueTactical(units, target)     --> SimCommand

-- NEVER use these (they bypass command system and corrupt queues):
-- nav:SetGoal()
-- nav:AbortMove()
```

---

## 10. Common Patterns

### Custom Lobby Class (WOPC Pattern)
```lua
local MyLobby = Class(moho.lobby_methods) {
    __init = function(self)
        self.Trash = TrashBag()
    end,

    Hosting = function(self)
        -- Host setup: start polling thread
        self.Trash:Add(ForkThread(self.LaunchThread, self))
    end,

    ConnectionToHostEstablished = function(self, localId, nameOrHostId, hostId)
        local actualHostId = hostId or nameOrHostId
        -- Joiner: send player info to host
        self:SendData(actualHostId, { Type = "AddPlayer", ... })
    end,

    DataReceived = function(self, data)
        if data.Type == "Launch" then
            self:LaunchGame(data.GameConfig)
        end
    end,

    LaunchThread = function(self)
        while not IsDestroyed(self) do
            -- Check if all players connected
            if allConnected then
                WaitSeconds(3.0)
                self:BroadcastData({ Type = "Launch", GameConfig = gameInfo })
                self:LaunchGame(gameInfo)
                return
            end
            WaitSeconds(1.0)
        end
    end,
}

-- Create instance
local comm = InternalCreateLobby(MyLobby, 'UDP', 15000, 16, 'PlayerName', nil, nil)
comm:HostGame()  -- or comm:JoinGame(address)
```

### Safe Error Handling
```lua
local ok, err = pcall(function()
    comm:LaunchGame(gameInfo)
end)
if not ok then
    LOG("Launch failed: " .. tostring(err))
end
```

### Counting Table Entries (No # Operator!)
```lua
local count = 0
for _ in myTable do
    count = count + 1
end
-- OR for arrays:
local count = table.getn(myArray)
```

---

## 11. VFS Mount Order & Priority

**CRITICAL: Two different priority systems!**

| System | Priority Rule | Used By |
|--------|--------------|---------|
| Engine C++ file loading | **First-added = highest** | `uimain.lua`, engine-loaded files |
| Lua `import()` | **Last-added = highest** | All Lua `import()` calls |

This means:
- VFS overlays (like `wopc_patches.scd` mounted AFTER `faf_ui.scd`) work for Lua `import()`
- But they do NOT work for engine-loaded files like `uimain.lua`
- To override engine-loaded files, patch the original `.scd` directly (deploy.py's `_patch_scd()`)

**WOPC mount order** (from `init_wopc.lua`):
1. Strategic icons (first = highest C++ priority)
2. Content packs (LOUD, etc.)
3. Maps, sounds
4. Vanilla SCFA assets (fonts, textures, effects)
5. `faf_ui.scd` (FAF UI code)
6. `wopc_patches.scd` (WOPC overlay - shadows FAF for Lua import)
7. User maps
8. User mods (via `mount_mods`)

---

## 12. Discovery Service

```lua
-- For finding LAN games (not currently used by WOPC)
InternalCreateDiscoveryService(serviceClass)  --> UILobbyDiscoveryService
```

---

## 13. GpgNet Integration (FAF Matchmaker)

```lua
GpgNetActive()                   --> boolean   -- Is GpgNet connected?
GpgNetSend(command, ...)                       -- Send command to GpgNet
-- Not used by WOPC (we handle networking ourselves)
```

---

## 14. Source File Locations

| File | What It Contains |
|------|-----------------|
| `vendor/faf-ui/engine/Core.lua` | Core globals (both sim+UI) |
| `vendor/faf-ui/engine/User.lua` | UI-state globals (commands, lobby, UI creation) |
| `vendor/faf-ui/engine/Sim.lua` | Sim-state globals (unit commands, terrain, armies) |
| `vendor/faf-ui/engine/User/CLobby.lua` | `moho.lobby_methods` full API |
| `vendor/faf-ui/engine/User/CMauiControl.lua` | Base UI control methods |
| `vendor/faf-ui/engine/Sim/Unit.lua` | Unit entity methods |
| `vendor/faf-ui/engine/Sim/Entity.lua` | Base entity methods |
| `vendor/faf-ui/lua/ui/lobby/lobbyComm.lua` | LobbyComm wrapper class |
| `vendor/faf-ui/lua/ui/lobby/autolobby/AutolobbyController.lua` | FAF autolobby pattern |
| `vendor/faf-ui/lua/system/config.lua` | System configuration |
