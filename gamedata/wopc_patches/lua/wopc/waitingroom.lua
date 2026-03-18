-- =============================================================================
-- waitingroom.lua — WOPC Waiting Room (transition screen for multiplayer)
--
-- Displays a simple background + centered status text while multilobby.lua
-- coordinates P2P connections.  Auto-destroyed when GameLaunched() fires.
-- =============================================================================

local UIUtil = import("/lua/ui/uiutil.lua")
local LayoutHelpers = import("/lua/maui/layouthelpers.lua")
local Bitmap = import("/lua/maui/bitmap.lua").Bitmap
local Text = import("/lua/maui/text.lua").Text

local _bg = nil
local _statusText = nil

--- Create the waiting room UI overlay.
---@param initialStatus string  Initial status message to display
function Create(initialStatus)
    if _bg then
        Destroy()
    end

    local parent = GetFrame(0)

    -- Full-screen dark background
    _bg = Bitmap(parent)
    _bg:SetSolidColor("ff000000")
    LayoutHelpers.FillParent(_bg, parent)
    _bg.Depth:Set(500)

    -- Centered status text
    _statusText = UIUtil.CreateText(_bg, initialStatus or "Connecting...", 24, UIUtil.bodyFont)
    LayoutHelpers.AtCenterIn(_statusText, _bg, 0, 0)
    _statusText:SetColor("ffffffff")
    _statusText:SetDropShadow(true)

    LOG("WOPC WaitingRoom: Created with status = " .. tostring(initialStatus))
end

--- Update the status text.
---@param text string  New status message
function SetStatus(text)
    if _statusText then
        _statusText:SetText(text or "")
        LOG("WOPC WaitingRoom: Status = " .. tostring(text))
    end
end

--- Destroy the waiting room UI.
function Destroy()
    if _bg then
        _bg:Destroy()
        _bg = nil
        _statusText = nil
        LOG("WOPC WaitingRoom: Destroyed")
    end
end
