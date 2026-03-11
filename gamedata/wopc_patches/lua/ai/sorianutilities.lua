-- sorianutilities.lua — WOPC stub
-- FAF's AI brain files import this module. In real FAF it's part of the
-- distribution build. This stub provides no-op implementations so the
-- AI system doesn't crash during quickstart matches.

function AIHandlePing(aiBrain, pingData)
    -- no-op: Sorian AI ping handling not needed
end

function AddCustomUnitSupport(aiBrain)
    -- no-op: extended AI unit support not needed for quickstart
end

function AISendChat(towho, nickname, message)
    -- no-op: AI chat not needed
end
