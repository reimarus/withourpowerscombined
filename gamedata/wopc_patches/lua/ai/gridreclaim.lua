-- gridreclaim.lua — WOPC stub
-- FAF's simInit.lua imports this file, but it only exists in FAF's
-- distribution build (not in the source repo or vanilla lua.scd).
--
-- Prop.lua imports GridReclaimInstance and nil-checks it before use.
-- We export false so the nil-check skips the calls.
-- The real GridReclaim optimizes AI reclaim behavior — not needed
-- for quickstart matches with simple AI.

GridReclaimInstance = false

function Setup(aiBrain)
    -- no-op: return nil (callers nil-check before use)
    return nil
end
