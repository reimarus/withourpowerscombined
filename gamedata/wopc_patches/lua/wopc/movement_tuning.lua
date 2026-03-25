-- WOPC Movement Tuning — Phase 1 navigator tuning + Phase 1.5 zero-collision experiment
--
-- This module is imported by quickstart.lua after the game launches.
-- It applies movement improvements and exposes experimental features.
--
-- Phase 1: Navigator distance tuning (safe, ships to all players)
-- Phase 1.5: Zero-collision experiment (dev-only, for testing)

local WopcMovement = {}

-- Internal state
local zeroCollisionEnabled = false
local zeroCollisionThread = nil

--- Phase 1: Apply navigator distance tuning
-- Uses existing PathfindingTweaks.cpp SimRegFunc API
function WopcMovement.TuneNavigator()
    if SetNavigatorPersonalPosMaxDistance then
        SetNavigatorPersonalPosMaxDistance(25.0)
        LOG('WOPC Movement: Navigator personal pos max distance set to 25.0 (vanilla 50.0)')
    else
        LOG('WOPC Movement: SetNavigatorPersonalPosMaxDistance not available (patched exe required)')
    end
end

--- Phase 1.5: Zero-collision experiment
-- Periodically scans all units and sets collision to near-zero.
-- This lets units walk through each other to test if the collision system
-- is the source of stop-and-wait behavior.
--
-- Call from sim console: import('/lua/wopc/movement_tuning.lua').EnableZeroCollision()
function WopcMovement.EnableZeroCollision()
    if zeroCollisionEnabled then
        LOG('WOPC Movement: Zero-collision already enabled')
        return
    end
    zeroCollisionEnabled = true
    LOG('WOPC Movement: *** ZERO-COLLISION EXPERIMENT ENABLED ***')
    LOG('WOPC Movement: Units will pass through each other. Visual clipping expected.')
    LOG('WOPC Movement: This is a diagnostic tool, NOT a gameplay feature.')

    -- Fork a thread that applies zero collision to all units every 2 seconds
    -- This catches newly built units automatically
    zeroCollisionThread = ForkThread(function()
        while zeroCollisionEnabled do
            local armies = ListArmies()
            for _, armyName in armies do
                local brain = GetArmyBrain(armyName)
                if brain then
                    local units = brain:GetListOfUnits(categories.ALLUNITS, false)
                    for _, unit in units do
                        if unit and not unit.Dead then
                            unit:SetCollisionShape('Sphere', 0, 0, 0, 0.01)
                        end
                    end
                end
            end
            WaitSeconds(2.0)
        end
        LOG('WOPC Movement: Zero-collision thread stopped')
    end)
end

--- Disable zero-collision experiment
-- Existing units keep their zero collision until the game ends.
-- New units will get normal collision.
function WopcMovement.DisableZeroCollision()
    zeroCollisionEnabled = false
    LOG('WOPC Movement: Zero-collision experiment DISABLED')
end

--- Apply zero collision to a single unit (for manual testing)
function WopcMovement.ZeroCollision(unit)
    if unit and not unit.Dead then
        unit:SetCollisionShape('Sphere', 0, 0, 0, 0.01)
    end
end

--- Revert a unit to its blueprint collision shape
function WopcMovement.RevertCollision(unit)
    if unit and not unit.Dead then
        unit:RevertCollisionShape()
    end
end

return WopcMovement
