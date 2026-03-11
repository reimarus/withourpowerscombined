-- transportutilities.lua — WOPC stub
-- FAF's platoon.lua imports this file, but it only exists in FAF's
-- distribution build (not in the source repo or vanilla lua.scd).
--
-- platoon.lua calls SendPlatoonWithTransports() for AI transport logic.
-- This stub returns false (failure) so AI platoons skip transport and
-- use ground movement instead. Adequate for quickstart matches.

function SendPlatoonWithTransports(aiBrain, platoon, destination, numRequired, usePrimary)
    -- no-op: always return false = "no transports available"
    return false
end
