-- =============================================================================
-- multilobby.lua — WOPC Multiplayer Quickstart (P2P connection handler)
--
-- When quickstart.lua detects ExpectedHumans > 1, it delegates here instead
-- of launching directly.  We create a LobbyComm instance (same pattern as
-- FAF's AutolobbyController) and wait for all peers to connect before
-- launching the sim automatically.
--
-- Host flow:
--   Hosting() → populate gameInfo from config → LaunchThread polls until
--   all peers connected → BroadcastData(Launch) → LaunchGame()
--
-- Joiner flow:
--   ConnectionToHostEstablished() → send AddPlayer → receive config from
--   host → wait for host's Launch signal → LaunchGame()
--
-- No interactive UI — just a "Connecting..." status via waitingroom.lua.
-- =============================================================================

local LobbyCommModule = import("/lua/ui/lobby/lobbyComm.lua")
local Mods = import("/lua/mods.lua")

-- Max connections for InternalCreateLobby (matches lobbyComm.lua)
local maxConnections = 16

local WaitingRoom = import("/lua/wopc/waitingroom.lua")

--- Resolve faction 5 (random) to a real faction (1-4).
local function ResolveFaction(faction)
    if faction == 5 then
        return Random(1, 4)
    end
    return faction
end

--- Resolve mod UIDs to full ModInfo tables.
local function ResolveGameMods(uidList)
    if not uidList or table.getn(uidList) == 0 then
        return {}
    end
    local uidSet = {}
    for _, uid in uidList do
        uidSet[uid] = true
    end
    return Mods.GetGameMods(uidSet)
end

--- Build the flat gameInfo table that LobbyComm:LaunchGame() expects.
--- CRITICAL: OwnerID must map to real peer IDs, not synthetic indices.
--- The engine waits for ALL unique OwnerIDs to connect before starting
--- the sim.  AI slots must use the host's peer ID (host "owns" the AI).
--- Human slots must use the actual peer ID of that player.
---@param cfg table        Game config from launcher
---@param hostPeerId any   Host's peer ID from GetLocalPlayerID()
---@param connectedPeers table  peerId → true map of connected peers
local function BuildGameInfo(cfg, hostPeerId, connectedPeers)
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

    if cfg.GameOptions then
        for k, v in cfg.GameOptions do
            options[k] = v
        end
    end

    -- Build ordered list of real peer IDs: host first, then connected peers.
    local peerIds = { tostring(hostPeerId) }
    for peerId, _ in connectedPeers do
        table.insert(peerIds, tostring(peerId))
    end
    LOG("WOPC MultiLobby: BuildGameInfo — peerIds: host=" .. peerIds[1] .. " +" .. (table.getn(peerIds) - 1) .. " remote")

    local playerOptions = {}
    local humanIdx = 1  -- tracks which peer ID to assign to human slots
    for i, p in cfg.Players do
        local isHuman = p.Human != false
        local faction = ResolveFaction(p.Faction or 1)
        -- Human slots get their actual peer ID; AI slots get the host's peer ID.
        local ownerID
        if isHuman and peerIds[humanIdx] then
            ownerID = peerIds[humanIdx]
            humanIdx = humanIdx + 1
        else
            ownerID = tostring(hostPeerId)
        end
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
            OwnerID = ownerID,
        }
        LOG("WOPC MultiLobby: Slot " .. i .. " OwnerID=" .. ownerID .. " Human=" .. tostring(isHuman))
    end

    local gameMods = ResolveGameMods(cfg.ActiveMods)

    return {
        GameOptions = options,
        PlayerOptions = playerOptions,
        Observers = {},
        GameMods = gameMods,
    }
end

-- =============================================================================
-- State tracking for the P2P lobby
-- =============================================================================

local _comm = nil           -- LobbyComm instance
local _cfg = nil            -- game config from launcher
local _isHost = true
local _expectedHumans = 2
local _localPeerId = "-2"
local _hostPeerId = "-2"
local _connectedPeers = {}  -- peerId → true
local _receivedConfig = nil -- joiner: config received from host
local _launched = false

-- =============================================================================
-- LobbyComm callback class (engine callbacks)
-- =============================================================================

--- We create a custom class extending moho.lobby_methods.
--- The engine calls these methods as peers connect/disconnect.
local WopcMultilobby = Class(moho.lobby_methods) {

    __init = function(self)
        self.Trash = TrashBag()
    end,

    --- Called by the engine when hosting is ready.
    Hosting = function(self)
        LOG("WOPC MultiLobby: Hosting callback fired")
        _localPeerId = self:GetLocalPlayerID()
        _hostPeerId = _localPeerId

        WaitingRoom.SetStatus("Hosting — waiting for " .. (_expectedHumans - 1) .. " player(s)...")

        -- Start the launch polling thread
        self.Trash:Add(ForkThread(self.LaunchThread, self))
    end,

    --- Called by the engine when we (joiner) connect to the host.
    --- Engine may pass 2 or 3 args depending on version.
    ConnectionToHostEstablished = function(self, localPeerId, nameOrHostPeerId, hostPeerId)
        -- Handle both 2-arg (localPeerId, hostPeerId) and 3-arg (localPeerId, newLocalName, hostPeerId) forms
        local actualHostPeerId = hostPeerId or nameOrHostPeerId
        LOG("WOPC MultiLobby: Connected to host, localPeer=" .. tostring(localPeerId) .. " hostPeer=" .. tostring(actualHostPeerId))
        _localPeerId = localPeerId
        _hostPeerId = actualHostPeerId

        WaitingRoom.SetStatus("Connected to host — waiting for game launch...")

        -- Send our player info to the host
        local Prefs = import('/lua/user/prefs.lua')
        local playerName = self:GetLocalPlayerName() or "Player"
        self:SendData(_hostPeerId, {
            Type = "AddPlayer",
            PlayerName = playerName,
            PeerId = localPeerId,
        })
    end,

    --- Called by the engine when a peer establishes a connection.
    EstablishedPeers = function(self, peerId, peerConnectedTo)
        LOG("WOPC MultiLobby: EstablishedPeers — peer " .. tostring(peerId))
        _connectedPeers[peerId] = true

        local count = 0
        for _ in _connectedPeers do
            count = count + 1
        end
        -- +1 for ourselves
        local totalConnected = count + 1

        if _isHost then
            WaitingRoom.SetStatus("Players connected: " .. totalConnected .. "/" .. _expectedHumans)
        end
    end,

    --- Called by the engine when we receive data from other players.
    DataReceived = function(self, data)
        LOG("WOPC MultiLobby: DataReceived type=" .. tostring(data.Type) .. " from=" .. tostring(data.SenderID))

        if data.Type == "AddPlayer" then
            -- Host: a joiner is telling us their info
            LOG("WOPC MultiLobby: Player joined — " .. tostring(data.PlayerName))

        elseif data.Type == "Launch" then
            -- Joiner: host is telling us to launch
            LOG("WOPC MultiLobby: Received Launch signal from host")
            if data.GameConfig then
                _receivedConfig = data.GameConfig
            end
            self:DoLaunch()

        elseif data.Type == "GameConfig" then
            -- Joiner: host is syncing the game config
            LOG("WOPC MultiLobby: Received GameConfig from host")
            _receivedConfig = data
        end
    end,

    --- Called by the engine when the game is about to launch.
    GameLaunched = function(self)
        LOG("WOPC MultiLobby: GameLaunched callback — transitioning to sim")
        WaitingRoom.Destroy()
    end,

    --- Called by the engine when connecting fails.
    ConnectionFailed = function(self, reason)
        LOG("WOPC MultiLobby: ConnectionFailed — " .. tostring(reason))
        WaitingRoom.SetStatus("Connection failed: " .. tostring(reason))
    end,

    --- Called by the engine when the connection to host is lost.
    Ejected = function(self, reason)
        LOG("WOPC MultiLobby: Ejected — " .. tostring(reason))
        WaitingRoom.SetStatus("Disconnected: " .. tostring(reason))
    end,

    SystemMessage = function(self, text)
        LOG("WOPC MultiLobby: SystemMessage — " .. tostring(text))
    end,

    Connecting = function(self)
        LOG("WOPC MultiLobby: Connecting...")
        WaitingRoom.SetStatus("Connecting to host...")
    end,

    MakeValidGameName = function(self, name)
        return moho.lobby_methods.MakeValidGameName(self, name)
    end,

    MakeValidPlayerName = function(self, peerId, name)
        return moho.lobby_methods.MakeValidPlayerName(self, peerId, name)
    end,

    SendData = function(self, peerId, data)
        return moho.lobby_methods.SendData(self, peerId, data)
    end,

    BroadcastData = function(self, data)
        return moho.lobby_methods.BroadcastData(self, data)
    end,

    LaunchGame = function(self, gameConfig)
        return moho.lobby_methods.LaunchGame(self, gameConfig)
    end,

    -- =========================================================================
    -- Custom methods
    -- =========================================================================

    --- Host: poll until all peers are connected, then launch.
    LaunchThread = function(self)
        LOG("WOPC MultiLobby: LaunchThread started, waiting for " .. _expectedHumans .. " players")
        while not IsDestroyed(self) and not _launched do
            local peerCount = 0
            for _ in _connectedPeers do
                peerCount = peerCount + 1
            end
            -- +1 for us (the host)
            local total = peerCount + 1

            if total >= _expectedHumans then
                -- Wait a few seconds for connections to stabilize
                LOG("WOPC MultiLobby: All " .. _expectedHumans .. " players connected, launching in 3s...")
                WaitingRoom.SetStatus("All players connected! Launching in 3 seconds...")
                WaitSeconds(3.0)

                -- Re-check after wait
                if not IsDestroyed(self) and not _launched then
                    self:DoLaunch()
                end
                return
            end

            WaitSeconds(1.0)
        end
    end,

    --- Actually launch the game.
    DoLaunch = function(self)
        if _launched then return end
        _launched = true

        local gameInfo
        if _isHost then
            gameInfo = BuildGameInfo(_cfg, _localPeerId, _connectedPeers)
            -- Broadcast the launch signal + config to all peers
            LOG("WOPC MultiLobby: Broadcasting Launch to all peers")
            self:BroadcastData({ Type = "Launch", GameConfig = gameInfo })
        else
            -- Use config received from host, or fall back to our local config
            gameInfo = _receivedConfig or BuildGameInfo(_cfg, _localPeerId, _connectedPeers)
        end

        LOG("WOPC MultiLobby: Launching game...")
        WaitingRoom.SetStatus("Launching game...")

        local ok, err = pcall(function()
            self:LaunchGame(gameInfo)
        end)

        if not ok then
            LOG("WOPC MultiLobby: LaunchGame failed — " .. tostring(err))
            WaitingRoom.SetStatus("Launch failed: " .. tostring(err))
            _launched = false
        end
    end,
}

-- =============================================================================
-- Public API — called from quickstart.lua
-- =============================================================================

--- Host entry point: create LobbyComm, set up game, wait for peers.
---@param cfg table          Game config from launcher
---@param protocol string
---@param port number
---@param playerName string
---@param gameName string
---@param mapFile string
---@param natTraversalProvider userdata?
function HostGame(cfg, protocol, port, playerName, gameName, mapFile, natTraversalProvider)
    LOG("WOPC MultiLobby: HostGame — expecting " .. tostring(cfg.ExpectedHumans) .. " humans")
    _cfg = cfg
    _isHost = true
    _expectedHumans = cfg.ExpectedHumans or 2
    _launched = false
    _connectedPeers = {}

    -- Show the waiting room UI
    WaitingRoom.Create("Hosting game — waiting for players...")

    -- Create the LobbyComm with our custom class via InternalCreateLobby
    -- (same approach as FAF's AutolobbyController — pass our class as first arg)
    _comm = InternalCreateLobby(WopcMultilobby, protocol, port, maxConnections, playerName, nil, natTraversalProvider)
    if not _comm then
        LOG("WOPC MultiLobby: ERROR — failed to create LobbyComm")
        WaitingRoom.SetStatus("Error: Failed to create lobby")
        return
    end

    -- Tell the engine we're hosting.
    -- Stock SCFA: HostGame() takes no args.
    -- FAF-patched: HostGame(friendsOnly) accepts one bool.
    -- Use pcall to support both engine variants.
    local hostOk, hostErr = pcall(function() _comm:HostGame(false) end)
    if not hostOk then
        _comm:HostGame()
    end
end

--- Joiner entry point: connect to host, wait for launch signal.
---@param cfg table          Game config from launcher (minimal)
---@param protocol string
---@param address string     Host address (ip:port)
---@param playerName string
---@param natTraversalProvider userdata?
function JoinGame(cfg, protocol, address, playerName, natTraversalProvider)
    LOG("WOPC MultiLobby: JoinGame — connecting to " .. tostring(address))
    _cfg = cfg
    _isHost = false
    _expectedHumans = cfg.ExpectedHumans or 2
    _launched = false
    _connectedPeers = {}

    -- Show the waiting room UI
    WaitingRoom.Create("Connecting to host...")

    -- Create the LobbyComm with our custom class via InternalCreateLobby
    local localPort = 0  -- let the engine pick a port for the joiner
    _comm = InternalCreateLobby(WopcMultilobby, protocol, localPort, maxConnections, playerName, nil, natTraversalProvider)
    if not _comm then
        LOG("WOPC MultiLobby: ERROR — failed to create LobbyComm")
        WaitingRoom.SetStatus("Error: Failed to create lobby")
        return
    end

    -- Tell the engine to join the host.
    -- Stock SCFA: JoinGame(address) takes one arg.
    -- FAF-patched: JoinGame(address, useNAT) accepts two.
    local joinOk, joinErr = pcall(function() _comm:JoinGame(address, false) end)
    if not joinOk then
        _comm:JoinGame(address)
    end
end
