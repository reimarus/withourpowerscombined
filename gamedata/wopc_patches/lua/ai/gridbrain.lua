-- gridbrain.lua — WOPC stub
-- FAF's AI brains (medium-ai, easy-ai, etc.) call Setup() during
-- OnBeginSession. This only exists in FAF's distribution build.
--
-- All callers nil-check the return value before use, so returning
-- nil is safe. The real GridBrain manages AI engineer reclaim
-- assignments — not critical for quickstart matches.

function Setup()
    -- no-op: return nil (all callers nil-check before use)
    return nil
end
