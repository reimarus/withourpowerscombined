-- WOPC stub for /lua/loudutilities.lua
-- Provides minimal API surface so Black Ops units work without LOUD's lua.scd.
-- When LOUD's lua.scd is enabled, its real implementation shadows this file
-- via VFS mount order (content packs mount before faf_ui.scd).

function TeleportLocationBlocked(self, targetPos)
    -- LOUD checks for anti-teleport jammers along the path.
    -- In FAF-only mode there are no such structures, so always return false.
    return false
end
