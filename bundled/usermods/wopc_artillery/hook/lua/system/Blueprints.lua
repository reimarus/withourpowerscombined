-- WOPC Rebalanced Artillery — blueprint modifications
--
-- Reduces T3 artillery range by 1/3 and cost by 1/3.
-- Makes artillery a mid-range siege weapon instead of a map-spanning threat.
--
-- Affected units (all factions):
--   UEB2302 (UEF "Duke")
--   UAB2302 (Aeon "Emissary")
--   URB2302 (Cybran "Disruptor")
--   XSB2302 (Seraphim "Hovatham")

local REDUCTION = 1 / 3   -- 33% reduction

-- T3 artillery blueprint IDs
local T3_ARTILLERY = {
    'ueb2302',  -- UEF
    'uab2302',  -- Aeon
    'urb2302',  -- Cybran
    'xsb2302',  -- Seraphim
}

local oldModBlueprints = ModBlueprints

function ModBlueprints(all_bps)
    oldModBlueprints(all_bps)

    for _, id in T3_ARTILLERY do
        local bp = all_bps.Unit[id]
        if not bp then
            LOG('WOPC Artillery: Blueprint ' .. id .. ' not found, skipping')
            continue
        end

        -- Reduce build cost by 1/3
        local econ = bp.Economy
        if econ then
            econ.BuildCostEnergy = math.floor(econ.BuildCostEnergy * (1 - REDUCTION))
            econ.BuildCostMass = math.floor(econ.BuildCostMass * (1 - REDUCTION))
            econ.BuildTime = math.floor(econ.BuildTime * (1 - REDUCTION))
        end

        -- Reduce weapon range by 1/3
        if bp.Weapon then
            for _, weapon in bp.Weapon do
                if weapon.MaxRadius and weapon.MaxRadius > 100 then
                    weapon.MaxRadius = math.floor(weapon.MaxRadius * (1 - REDUCTION))
                    -- Scale min range proportionally
                    if weapon.MinRadius then
                        weapon.MinRadius = math.floor(weapon.MinRadius * (1 - REDUCTION))
                    end
                end
            end
        end

        LOG('WOPC Artillery: Rebalanced ' .. id
            .. ' — range ' .. tostring(math.floor(825 * (1 - REDUCTION)))
            .. ', cost -' .. tostring(math.floor(REDUCTION * 100)) .. '%')
    end
end
