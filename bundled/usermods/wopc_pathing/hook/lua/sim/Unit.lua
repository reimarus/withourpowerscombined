-- WOPC Soft Collision — shrink collision radius for moving units
--
-- When units are in motion, their collision shape is temporarily reduced.
-- This allows units to overlap slightly while moving, preventing the
-- "traffic jam" effect where units block each other and stop.
-- When units stop, collision reverts to blueprint defaults.
--
-- Inspired by StarCraft 2's soft collision model.
-- See docs/sc2-movement-research.md for technical background.
--
-- Configuration:
--   WopcSoftCollisionFactor (global, set in simInit.lua)
--     0.0 = no collision while moving (units pass through each other)
--     0.5 = 50% collision radius while moving (default)
--     1.0 = full collision, soft collision disabled

local Unit = Unit

-- Cache the original methods (upvalue for performance, per FAF convention)
local OriginalOnMotionHorzEventChange = Unit.OnMotionHorzEventChange
local OriginalOnCreate = Unit.OnCreate

-- Upvalue engine functions for performance
local EntitySetCollisionShape = moho.entity_methods.SetCollisionShape
local UnitRevertCollisionShape = moho.unit_methods.RevertCollisionShape
local EntityCategoryContains = EntityCategoryContains

--- Apply reduced collision shape to a moving unit.
-- Uses the blueprint's SizeX/Y/Z scaled by the soft collision factor.
-- Falls back to SizeSphere if the unit uses spherical collision.
local function ApplySoftCollision(self)
    local bp = self.Blueprint
    if not bp then return end

    local factor = WopcSoftCollisionFactor or 0.5
    if factor >= 1.0 then return end

    -- Units with spherical collision (bp.SizeSphere)
    if bp.SizeSphere then
        EntitySetCollisionShape(self, 'Sphere',
            bp.CollisionSphereOffsetX or 0,
            bp.CollisionSphereOffsetY or 0,
            bp.CollisionSphereOffsetZ or 0,
            bp.SizeSphere * factor
        )
        return
    end

    -- Units with box collision (default)
    local sx = bp.SizeX
    local sy = bp.SizeY
    local sz = bp.SizeZ
    if not sx or not sy or not sz then return end

    EntitySetCollisionShape(self, 'Box',
        bp.CollisionOffsetX or 0,
        bp.CollisionOffsetY or 0,
        bp.CollisionOffsetZ or 0,
        sx * factor * 0.5,
        sy * 0.5,        -- keep full Y height (don't shrink vertically)
        sz * factor * 0.5
    )
end

--- Hooked OnCreate — mark ENGINEER units for permanent zero collision.
-- Uses the C++ WopcMarkZeroCollision which:
--   1. Registers the entity ID in a C++ array
--   2. Calls SetCollisionShape('None') immediately
-- The C++ system prevents any future collision restoration.
Unit.OnCreate = function(self)
    OriginalOnCreate(self)

    -- Mark engineers for zero collision via C++ API
    if self.WopcMarkZeroCollision
        and EntityCategoryContains(categories.ENGINEER, self)
    then
        self:WopcMarkZeroCollision()
    end
end

--- Hooked OnMotionHorzEventChange — applies soft collision during movement.
Unit.OnMotionHorzEventChange = function(self, new, old)
    -- Call original (sounds, effects, weapon state)
    OriginalOnMotionHorzEventChange(self, new, old)

    -- Skip if dead or soft collision disabled
    if self.Dead then return end
    if not WopcSoftCollisionFactor or WopcSoftCollisionFactor >= 1.0 then return end

    -- Skip structures — they don't move and shouldn't have collision modified
    if self.Blueprint.Physics and self.Blueprint.Physics.MotionType == 'RULEUMT_None' then
        return
    end

    -- Zero collision units: always keep collision removed, never revert
    if self.WopcIsZeroCollision and self:WopcIsZeroCollision() then
        EntitySetCollisionShape(self, 'None')
        return
    end

    -- Moving or decelerating: shrink collision
    if new == 'TopSpeed' or new == 'Cruise' or new == 'Stopping' then
        ApplySoftCollision(self)
    -- Fully stopped: revert to blueprint collision
    elseif new == 'Stopped' then
        UnitRevertCollisionShape(self)
    end
end
