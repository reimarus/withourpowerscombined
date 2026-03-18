-- =============================================================================
-- quickstart.lua — WOPC Quick Start (bypass lobby, launch directly into game)
--
-- Called from uimain.lua when /wopcquickstart is on the command line.
-- Reads the game configuration written by the WOPC Python launcher at
-- <WOPC_BIN>/wopc_game_config.lua and launches straight into the sim.
--
-- We create our own LobbyComm instance (like FAF's autolobby does) rather
-- than going through lobby.lua, because lobby.lua's lobbyComm is a private
-- local variable inaccessible from outside.
-- =============================================================================

local LobbyComm = import("/lua/ui/lobby/lobbyComm.lua")
local Mods = import("/lua/mods.lua")

--- Resolve faction 5 (random) to a real faction (1-4).
--- The lobby normally does this before LaunchGame; we must do it ourselves.
--- SCFA Lua has no math.random — use the engine's Random() global.
---@param faction number
---@return number
local function ResolveFaction(faction)
    if faction == 5 then
        return Random(1, 4)
    end
    return faction
end

--- Resolve a list of mod UIDs to full ModInfo tables via FAF's mods.lua.
--- This is the same data structure that LaunchGame expects in gameInfo.GameMods
--- and that the engine copies into __active_mods for blueprint loading.
---@param uidList string[]  List of mod UIDs from the launcher config
---@return ModInfo[]
local function ResolveGameMods(uidList)
    if not uidList or table.getn(uidList) == 0 then
        return {}
    end

    -- Build a UID set for GetGameMods (same format GetSelectedMods returns)
    local uidSet = {}
    for _, uid in uidList do
        uidSet[uid] = true
    end

    -- Use FAF's mod resolution — handles dependency sorting, validation,
    -- and filtering to sim-only mods (excludes ui_only).
    local resolved = Mods.GetGameMods(uidSet)

    LOG("WOPC QuickStart: Resolved " .. table.getn(resolved) .. " active game mods:")
    for _, mod in resolved do
        LOG("  - " .. tostring(mod.name) .. " (" .. tostring(mod.uid) .. ")")
    end

    return resolved
end

--- Build the flat gameInfo table that LobbyComm:LaunchGame() expects.
---@param cfg table  The config table loaded from wopc_game_config.lua
---@return table gameInfo
local function BuildGameInfo(cfg)
    -- Game options — sensible skirmish defaults, overridden by config
    local options = {
        Score = 'no',
        TeamSpawn = 'fixed',
        TeamLock = 'locked',
        Victory = 'demoralization',
        Timeouts = '3',
        CheatsEnabled = 'false',
        CivilianAlliance = 'enemy',
        GameSpeed = 'normal',
        FogOfWar = 'explored',
        UnitCap = '1500',
        Share = 'FullShare',
        PrebuiltUnits = 'Off',
        NoRushOption = 'Off',
        RestrictedCategories = {},
        ScenarioFile = cfg.ScenarioFile,
    }

    -- Merge any option overrides from config
    if cfg.GameOptions then
        for k, v in cfg.GameOptions do
            options[k] = v
        end
    end

    -- Build player options array.
    -- Types must match what the C++ engine expects in moho.lobby_methods.LaunchGame.
    -- Key insight: OwnerID is a string (peer ID), not a number.
    -- Fields like Team, Faction, StartSpot, PlayerColor are numbers.
    local playerOptions = {}
    for i, p in cfg.Players do
        local isHuman = p.Human != false
        local faction = ResolveFaction(p.Faction or 1)
        playerOptions[i] = {
            Team = p.Team or 1,
            PlayerColor = p.PlayerColor or i,
            ArmyColor = p.PlayerColor or i,
            StartSpot = p.StartSpot or i,
            Ready = true,
            Faction = faction,
            PlayerName = p.PlayerName or ("Player " .. i),
            AIPersonality = p.AIPersonality or '',
            Human = isHuman,
            Civilian = false,
            -- OwnerID must be a string (peer ID). Use "0" for host, tostring(i) for others.
            OwnerID = isHuman and tostring(i - 1) or tostring(i - 1),
        }
    end

    -- Resolve active mods from config UIDs via FAF's mods.lua.
    -- The engine copies GameMods into __active_mods in the sim state,
    -- which blueprints.lua and ruleinit.lua use for blueprint loading.
    local gameMods = ResolveGameMods(cfg.ActiveMods)

    return {
        GameOptions = options,
        PlayerOptions = playerOptions,
        Observers = {},
        GameMods = gameMods,
    }
end

--- Fallback: open the standard lobby UI so the user can configure manually.
local function FallbackToLobby(protocol, port, playerName, gameName, mapFile, natTraversalProvider)
    LOG("WOPC QuickStart: Falling back to standard lobby UI")
    local lobby = import("/lua/ui/lobby/lobby.lua")
    lobby.CreateLobby(protocol, port, playerName, nil, natTraversalProvider, GetFrame(0),
        import("/lua/ui/uimain.lua").StartFrontEndUI)
    lobby.HostGame(gameName, mapFile, false)
end

--- Entry point — create our own LobbyComm, build game config, launch.
---@param protocol string
---@param port number
---@param playerName string
---@param gameName string
---@param mapFile string
---@param natTraversalProvider userdata?
function Launch(protocol, port, playerName, gameName, mapFile, natTraversalProvider)
    LOG("WOPC QuickStart: Loading game configuration...")

    -- Load the config file written by the Python launcher.
    -- Path is passed on the command line as /wopcconfig <path>.
    -- (InitFileDir is only available in the init Lua state, not the UI state.)
    local configArg = GetCommandLineArg("/wopcconfig", 1)
    if not configArg then
        LOG("WOPC QuickStart: ERROR — /wopcconfig not on command line")
        FallbackToLobby(protocol, port, playerName, gameName, mapFile, natTraversalProvider)
        return
    end
    local configPath = configArg[1]
    LOG("WOPC QuickStart: Config path = " .. tostring(configPath))
    local ok, cfg = pcall(dofile, configPath)
    if not ok or not cfg then
        LOG("WOPC QuickStart: Failed to load config from " .. configPath)
        LOG("WOPC QuickStart: Error: " .. tostring(cfg))
        FallbackToLobby(protocol, port, playerName, gameName, mapFile, natTraversalProvider)
        return
    end

    LOG("WOPC QuickStart: Map = " .. tostring(cfg.ScenarioFile))
    LOG("WOPC QuickStart: Players = " .. table.getn(cfg.Players))

    -- Multiplayer dispatch: if ExpectedHumans > 1, delegate to multilobby.lua.
    -- multilobby handles P2P connection setup via LobbyComm, then auto-launches.
    -- Note: joiners enter via JoinLaunch() below, not here — this path is host-only.
    local expectedHumans = cfg.ExpectedHumans or 1
    if expectedHumans > 1 then
        LOG("WOPC QuickStart: Multiplayer host mode — dispatching to multilobby.lua (ExpectedHumans=" .. expectedHumans .. ")")
        local multilobby = import("/lua/wopc/multilobby.lua")
        multilobby.HostGame(cfg, protocol, port, playerName, gameName, mapFile, natTraversalProvider)
        return
    end

    -- Validate the scenario file exists
    local MapUtil = import("/lua/ui/maputil.lua")
    local scenarioInfo = MapUtil.LoadScenario(cfg.ScenarioFile)
    if not scenarioInfo then
        LOG("WOPC QuickStart: ERROR — could not load scenario: " .. tostring(cfg.ScenarioFile))
        FallbackToLobby(protocol, port, playerName, gameName, mapFile, natTraversalProvider)
        return
    end

    -- Create our own LobbyComm instance (bypasses lobby.lua entirely).
    -- This is the same approach FAF's autolobby uses.
    local comm = LobbyComm.CreateLobbyComm(protocol, port, playerName, nil, natTraversalProvider)
    if not comm then
        LOG("WOPC QuickStart: ERROR — failed to create LobbyComm")
        FallbackToLobby(protocol, port, playerName, gameName, mapFile, natTraversalProvider)
        return
    end

    -- Tell the engine we're hosting a game
    comm:HostGame()

    -- Apply WOPC player settings to engine profile prefs.
    -- These must be set before LaunchGame() transitions to game state,
    -- because FAF UI modules read profile prefs at import time.
    local Prefs = import('/lua/user/prefs.lua')
    if cfg.GameOptions and cfg.GameOptions.minimap_enabled then
        local enabled = (cfg.GameOptions.minimap_enabled == 'True')
        Prefs.SetToCurrentProfile('stratview', enabled)
        LOG('WOPC QuickStart: Set minimap visibility to ' .. tostring(enabled))
    end

    -- Persist active mods to profile prefs so FAF's GetSelectedMods()
    -- returns them correctly for any code path that reads preferences
    -- (e.g. blueprint pre-game data loading).
    if cfg.ActiveMods and table.getn(cfg.ActiveMods) > 0 then
        local activeModsTable = {}
        for _, uid in cfg.ActiveMods do
            activeModsTable[uid] = true
        end
        Prefs.SetToCurrentProfile('active_mods', activeModsTable)
        LOG("WOPC QuickStart: Set " .. table.getn(cfg.ActiveMods) .. " active mods in preferences")
    end

    -- Build the flat gameInfo and launch directly into the simulation
    local gameInfo = BuildGameInfo(cfg)

    LOG("WOPC QuickStart: Launching game with " .. table.getn(cfg.Players) .. " players...")
    local launchOk, launchErr = pcall(function()
        comm:LaunchGame(gameInfo)
    end)

    if not launchOk then
        LOG("WOPC QuickStart: LaunchGame failed: " .. tostring(launchErr))
        -- Cannot fall back to lobby here — port is already bound by our LobbyComm.
        -- Just log the error; the user will see the error in WOPC.log.
        LOG("WOPC QuickStart: Cannot recover. Check WOPC.log for details.")
    end
end

--- Joiner entry point — called from uimain.lua's StartJoinLobbyUI when
--- /wopcquickstart is on the command line.
---@param protocol string
---@param address string     Host address (ip:port)
---@param playerName string
---@param natTraversalProvider userdata?
function JoinLaunch(protocol, address, playerName, natTraversalProvider)
    LOG("WOPC QuickStart: JoinLaunch — loading config for join mode...")

    local configArg = GetCommandLineArg("/wopcconfig", 1)
    if not configArg then
        LOG("WOPC QuickStart: ERROR — /wopcconfig not on command line")
        -- Fall back to standard join lobby
        local lobby = import("/lua/ui/lobby/lobby.lua")
        lobby.CreateLobby(protocol, 0, playerName, nil, natTraversalProvider, GetFrame(0),
            import("/lua/ui/uimain.lua").StartFrontEndUI)
        lobby.JoinGame(address, false)
        return
    end

    local configPath = configArg[1]
    LOG("WOPC QuickStart: Config path = " .. tostring(configPath))
    local ok, cfg = pcall(dofile, configPath)
    if not ok or not cfg then
        LOG("WOPC QuickStart: Failed to load config: " .. tostring(cfg))
        return
    end

    -- Always dispatch to multilobby for join mode
    LOG("WOPC QuickStart: Joining multiplayer game at " .. tostring(address))
    local multilobby = import("/lua/wopc/multilobby.lua")
    multilobby.JoinGame(cfg, protocol, address, playerName, natTraversalProvider)
end
