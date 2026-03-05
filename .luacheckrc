-- Luacheck configuration for SCFA/LOUD Lua files
-- SCFA uses modified Lua 5.0 with nonstandard extensions.
-- This config suppresses false positives while catching real issues.
--
-- Known limitations:
--   SCFA Lua uses != instead of ~= (parse error in luacheck)
--   SCFA Lua supports continue keyword (parse error in luacheck)
--   These cause false positives in CommonDataPath.lua

std = "lua51"  -- Closest standard to SCFA's Lua 5.0 fork

-- Globals provided by the SCFA engine
globals = {
    "LOG",              -- Engine logging function
    "WARN",             -- Engine warning function
    "InitFileDir",      -- Set by engine before running init
    "SCFARoot",         -- Set by wopc_paths.lua (dofile'd)
    "path",             -- VFS mount table
    "hook",             -- Hook paths table
    "protocols",        -- Allowed protocols table
}

read_globals = {
    "io",               -- SCFA provides custom io library
    "dofile",           -- Standard Lua, available in SCFA
    "table",
    "string",
    "math",
}

-- Suppress common false positives
ignore = {
    "211",   -- Unused local variable (SCFA patterns use these)
    "212",   -- Unused argument
    "213",   -- Unused loop variable
    "311",   -- Value assigned to local but never accessed
    "542",   -- Empty if branch
}

-- Only check our init files
include_files = {
    "init/",
}
