-- sorianutilities.lua — WOPC stub
-- FAF's AI brain files import this module. In real FAF it's part of the
-- distribution build. This stub provides no-op implementations so the
-- AI system doesn't crash during quickstart matches.
--
-- Every function here must return a safe value so callers don't crash.
-- If callers use the return value in an if-guard, nil is fine. If they
-- index into the return value, return an empty table instead.

function AIHandlePing(aiBrain, pingData)
    -- no-op: Sorian AI ping handling not needed
end

function AddCustomUnitSupport(aiBrain)
    -- no-op: extended AI unit support not needed for quickstart
end

function AISendChat(towho, nickname, message)
    -- no-op: AI chat not needed
end

function GetEngineerFaction(engineer)
    -- Return nil — callers guard with `if aiBrain.CustomUnits[v]`
    -- which is nil in vanilla, so this code path is never reached.
    -- But if it is reached, nil faction causes the `else` branch
    -- to fire in platoon.lua which builds with default templates.
    return nil
end

function GetTemplateReplacement(aiBrain, building, faction, buildingTmpl)
    -- Return nil — caller falls through to default build template
    return nil
end

function FindUnfinishedUnits(aiBrain, location, category)
    -- Return empty table — caller iterates the result
    return {}
end

function FindDamagedShield(aiBrain, location, category)
    -- Return empty table — caller iterates the result
    return {}
end
