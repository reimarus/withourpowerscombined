-- WOPC Better Pathing — sim hook
-- Hooks BeginSession to apply movement tuning when this mod is active.

local oldBeginSession = BeginSession

function BeginSession()
    oldBeginSession()

    -- Blocked timer tuning: cap how long units wait when stuck before repathing.
    -- Vanilla uses per-waypoint values (typically 40-80 ticks = 4-8 seconds).
    -- We cap at 20 ticks (~2 seconds) with min 3 ticks to prevent thrashing.
    if SetBlockedTimerTuning then
        SetBlockedTimerTuning(20, 3)
        LOG('WOPC Pathing: Blocked timer capped at 20 ticks, min 3 (vanilla 40-80)')
    else
        LOG('WOPC Pathing: SetBlockedTimerTuning not available (need patched exe)')
    end

    -- Navigator personal position distance: how close a unit must be to its
    -- formation slot to be considered "in position". Lower = tighter groups.
    if SetNavigatorPersonalPosMaxDistance then
        SetNavigatorPersonalPosMaxDistance(10.0)
        LOG('WOPC Pathing: Navigator personal pos max distance = 10.0 (vanilla 50.0)')
    end

    -- Log stats for diagnostics
    if GetPathfindingStats then
        local stats = GetPathfindingStats()
        LOG('WOPC Pathing: Stats API active (max_blocked=' .. tostring(stats.max_blocked_ticks)
            .. ', min_blocked=' .. tostring(stats.min_blocked_ticks) .. ')')
    end
end
