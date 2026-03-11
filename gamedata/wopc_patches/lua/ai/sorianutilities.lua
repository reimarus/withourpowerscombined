-- sorianutilities.lua — WOPC stub
-- FAF's aibrain.lua imports this file, but it only exists in FAF's
-- distribution build (not in the source repo or vanilla lua.scd).
--
-- aibrain.lua calls SUtils.AIHandlePing(). This stub provides a
-- no-op implementation. Sorian AI utilities are used by the Sorian AI
-- personality — not needed for quickstart matches with standard AI.

function AIHandlePing(aiBrain, pingData)
    -- no-op: Sorian AI ping handling not needed
end
