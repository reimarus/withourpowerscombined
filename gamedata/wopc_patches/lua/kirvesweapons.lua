-- WOPC stub for /lua/kirvesweapons.lua
-- Weapon classes used by Black Ops Seraphim units.
-- When LOUD's lua.scd is enabled, its real implementation shadows this file.

local WeaponFile = import('/lua/sim/DefaultWeapons.lua')

local DefaultProjectileWeapon = WeaponFile.DefaultProjectileWeapon
local DefaultBeamWeapon = WeaponFile.DefaultBeamWeapon

local OriginalEffectTemplate = import('/lua/EffectTemplates.lua')
local EffectTemplate = import('/lua/kirveseffects.lua')

local CollisionBeamFile = import('/lua/kirvesbeams.lua')


TAAPhalanxWeapon = Class(DefaultProjectileWeapon) {
    FxMuzzleFlash = EffectTemplate.TPhalanxGunMuzzleFlash,
    FxShellEject = EffectTemplate.TPhalanxGunShells,

    PlayFxMuzzleSequence = function(self, muzzle)
        DefaultProjectileWeapon.PlayFxMuzzleSequence(self, muzzle)
        for k, v in self.FxShellEject do
            CreateAttachedEmitter(self.unit, 'Shells_Left', self.unit:GetArmy(), v)
            CreateAttachedEmitter(self.unit, 'Shells_Right', self.unit:GetArmy(), v)
        end
    end,
}

SDFUnstablePhasonBeam = Class(DefaultBeamWeapon) {
    BeamType = CollisionBeamFile.UnstablePhasonLaserCollisionBeam,

    FxMuzzleFlash = {},
    FxChargeMuzzleFlash = {},
    FxUpackingChargeEffects = OriginalEffectTemplate.CMicrowaveLaserCharge01,
    FxUpackingChargeEffectScale = 0.2,
}

Dummy = Class(DefaultBeamWeapon) {
    BeamType = CollisionBeamFile.TargetingCollisionBeam,

    FxBeamEndPointScale = 0.01,
}
