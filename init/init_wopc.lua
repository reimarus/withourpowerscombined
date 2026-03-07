-- =============================================================================
-- init_wopc.lua — WOPC init file
-- With Our Powers Combined: Standalone gameplay + FAF engine patches
--
-- This file is the /init argument passed to SupremeCommander.exe.
-- It defines the VFS mount order for the WOPC game directory.
--
-- Mount order determines content priority (later mounts shadow earlier ones):
--   1. Bundled strategic icons  (from WOPC/bin/)
--   2. Bundled gamedata SCDs    (lua.scd, units.scd, brewlan.scd, etc.)
--   3. Bundled maps and sounds
--   4. Vanilla SCFA content     (fonts, textures, effects, env, etc.)
--   5. WOPC patches overlay     (our Lua fixes/enhancements)
--   6. User maps
--   7. User mods                (loaded LAST — shadow everything above)
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
-- 2. Bundled gamedata (Core gameplay content)
-- =========================================================================
mount_dir(WOPCRoot .. '\\gamedata\\*.scd', '/')

-- =========================================================================
-- 3. Bundled maps and sounds
-- =========================================================================
mount_dir(WOPCRoot .. '\\maps', '/maps')
mount_dir(WOPCRoot .. '\\sounds', '/sounds')

-- =========================================================================
-- 4. Vanilla SCFA content (fonts, textures, effects, etc.)
--    These paths point back to the Steam SCFA installation.
--    The setup script places a marker file so we know where SCFA lives,
--    but the standard layout is two directories up from WOPC root.
-- =========================================================================
mount_dir(SCFARoot .. '\\fonts', '/fonts')
mount_dir(SCFARoot .. '\\gamedata\\textures.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\effects.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\env.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\projectiles.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\props.scd', '/')
mount_dir(SCFARoot .. '\\gamedata\\meshes.scd', '/')
mount_dir(SCFARoot .. '\\movies', '/movies')
mount_dir(SCFARoot .. '\\sounds', '/sounds')

-- =========================================================================
-- 5. FAF UI Integration (shadows vanilla and bundled content)
-- =========================================================================
local faf_ui = WOPCRoot .. '\\gamedata\\faf_ui.scd'
mount_dir(faf_ui, '/')

-- =========================================================================
-- 6. WOPC patches overlay (our custom Lua fixes — shadows everything above)
-- =========================================================================
-- This SCD is built from gamedata/wopc_patches/ and mounted AFTER all bundled
-- and FAF content, so our files take priority.
local wopc_patches = WOPCRoot .. '\\gamedata\\wopc_patches.scd'
-- Only mount if the patches SCD exists (Phase 3+)
mount_dir(wopc_patches, '/')

-- =========================================================================
-- 6. User maps
-- =========================================================================
mount_dir(WOPCRoot .. '\\usermaps', '/maps')

-- =========================================================================
-- 7. User mods (loaded LAST — shadow everything, including maps)
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
