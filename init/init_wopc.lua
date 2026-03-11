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
--   3. WOPC patches overlay     (our Lua fixes — highest priority for '/')
--   4. FAF UI + Lua engine      (FAF game logic — shadows vanilla)
--   5. Vanilla SCFA content     (fonts, textures, effects, units, loc, etc.)
--   6. User maps
--   7. User mods                (separate namespace via mount_mods)
-- =============================================================================

do
dofile(InitFileDir.."\\CommonDataPath.lua");

-- Resolve WOPC root: bin's parent directory
local WOPCRoot = InitFileDir .. '\\..'

-- Load SCFA path from generated config (written by setup.py)
-- This file sets: SCFARoot = "C:\\Program Files (x86)\\Steam\\..."
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
-- 3. WOPC patches overlay (first-added = highest VFS priority)
-- =========================================================================
local wopc_patches = WOPCRoot .. '\\gamedata\\wopc_patches.scd'
mount_dir(wopc_patches, '/')

-- =========================================================================
-- 4. FAF Lua engine + UI (shadows vanilla for all game logic + unit scripts)
-- Must be mounted BEFORE vanilla SCDs so the engine's VFS finds FAF's
-- files first (first-added = highest priority in SCFA's VFS).
-- =========================================================================
local faf_ui = WOPCRoot .. '\\gamedata\\faf_ui.scd'
mount_dir(faf_ui, '/')

-- =========================================================================
-- 5. Vanilla SCFA content (assets + gameplay data from Steam install)
-- Mounted AFTER FAF so FAF's files take priority.  Vanilla provides
-- assets that FAF doesn't replace (unmodified units, textures, etc.).
-- FAF replaces lua.scd, mohodata.scd, moholua.scd, and schook.scd
-- with its own code in faf_ui.scd — those are NOT mounted here.
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
