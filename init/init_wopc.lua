-- =============================================================================
-- init_wopc.lua — WOPC init file (STATIC FALLBACK)
-- With Our Powers Combined: Standalone gameplay + FAF engine patches
--
-- This file is copied by `wopc setup` and overwritten by the launcher's
-- init_generator before each game launch.  It exists as a fallback if the
-- user launches the exe directly without the launcher.
--
-- Mount order determines content priority (first-added = highest priority
-- for the engine's VFS file lookup — earlier mounts shadow later ones):
--   1. Bundled strategic icons  (from WOPC/bin/)
--   2. Bundled maps and sounds
--   3. WOPC core SCD            (game logic + patches + vanilla gap-fills)
--   4. Vanilla SCFA content     (fonts, textures, effects, units, loc, etc.)
--   5. User maps
--   6. User mods                (separate namespace via mount_mods)
-- =============================================================================

do
dofile(InitFileDir.."\\CommonDataPath.lua");

-- Resolve WOPC root: bin's parent directory
WOPCRoot = InitFileDir .. '\\..'

-- Load SCFA path from generated config (written by setup.py)
-- This file sets: SCFARoot = WOPCRoot .. "\\.."
dofile(InitFileDir.."\\wopc_paths.lua");

-- =========================================================================
-- 1. Bundled strategic icons
-- =========================================================================
mount_dir(InitFileDir .. '\\BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd', '/')

-- =========================================================================
-- 2. Bundled maps and sounds
-- =========================================================================
mount_dir(WOPCRoot .. '\\maps', '/maps')
mount_dir(WOPCRoot .. '\\sounds', '/sounds')

-- =========================================================================
-- 3. WOPC core SCD (game logic + patches + vanilla gap-fills)
-- Must be mounted BEFORE vanilla SCDs so the engine's VFS finds our
-- files first (first-added = highest priority in SCFA's VFS).
-- =========================================================================
local wopc_core = WOPCRoot .. '\\gamedata\\wopc_core.scd'
mount_dir(wopc_core, '/')

-- =========================================================================
-- 5. Vanilla SCFA content (assets + gameplay data from Steam install)
-- Mounted AFTER wopc_core so our files take priority.  Vanilla provides
-- assets we don't replace (unmodified units, textures, etc.).
-- wopc_core.scd replaces lua.scd, mohodata.scd, moholua.scd, and
-- schook.scd — those are NOT mounted here.
-- =========================================================================
mount_dir(SCFARoot .. '\\fonts', '/fonts')
mount_dir(SCFARoot .. '\\gamedata\\textures.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\effects.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\env.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\projectiles.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\props.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\meshes.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\units.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\objects.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\mods.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\loc_us.scd', '/')
mount_dir(SCFARoot .. '\\movies', '/movies')
mount_dir(SCFARoot .. '\\sounds', '/sounds')

-- =========================================================================
-- 6. User maps
-- =========================================================================
mount_dir(WOPCRoot .. '\\usermaps', '/maps')

-- =========================================================================
-- 7. User mods (separate namespace — loaded via mount_mods)
-- =========================================================================
mount_mods(WOPCRoot .. '\\usermods')

-- =========================================================================
-- Hook paths and protocols
-- =========================================================================
hook = {
    '/schook'
}

protocols = {
    'http',
    'https',
}
end
