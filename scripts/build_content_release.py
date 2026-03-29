"""Build content assets for a WOPC GitHub Release.

Developer-only script. Produces release-staging/ with all assets
needed for the content-v2 GitHub Release, then prints the gh commands
to upload them.

Requirements:
    - Full repo with vendor submodules (for wopc_core.scd build)
    - Steam SCFA installed (for vanilla lua.scd merge and stock maps)
    - WOPC setup completed (for deployed maps directory)

Usage:
    python scripts/build_content_release.py
"""

import re
import shutil
import sys
import zipfile
from pathlib import Path

# Add repo root to path so we can import launcher modules
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from launcher import config  # noqa: E402

STAGING = REPO_ROOT / "release-staging"


def build_wopc_core_scd() -> Path:
    """Build wopc_core.scd by merging game logic source + vanilla lua.scd + WOPC patches.

    This is the same logic as deploy.py's Step 4, extracted for release building.
    """
    dst = STAGING / config.WOPC_CORE_SCD
    core_src = config.REPO_WOPC_CORE_SRC

    if not core_src.exists():
        print(f"ERROR: Game logic source not found at {core_src}")
        print("       Run: git submodule update --init --recursive")
        sys.exit(1)

    print(f"Building {config.WOPC_CORE_SCD}...")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as zf:
        # 1. Add game logic source files (lowercase normalized)
        core_count = 0
        for target_dir in [
            "etc",
            "lua",
            "modules",
            "ui",
            "loc",
            "units",
            "projectiles",
            "effects",
            "env",
            "meshes",
            "schook",
            "textures",
        ]:
            dir_path = core_src / target_dir
            if dir_path.exists():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        rel = file_path.relative_to(core_src)
                        arcname = str(rel).replace("\\", "/").lower()
                        zf.write(file_path, arcname)
                        core_count += 1
        print(f"  Added {core_count} game logic source files")

        # 2. Merge vanilla lua.scd files not present in our source
        vanilla_lua_scd = config.SCFA_STEAM / "gamedata" / "lua.scd"
        if vanilla_lua_scd.exists():
            existing = {name.replace("\\", "/").lower() for name in zf.namelist()}
            merged = 0
            with zipfile.ZipFile(vanilla_lua_scd, "r") as vanilla_zf:
                for info in vanilla_zf.infolist():
                    if info.is_dir():
                        continue
                    normalized = info.filename.replace("\\", "/").lower()
                    if normalized not in existing:
                        zf.writestr(normalized, vanilla_zf.read(info))
                        merged += 1
            print(f"  Merged {merged} vanilla lua.scd files")
        else:
            print(f"  WARNING: vanilla lua.scd not found at {vanilla_lua_scd}")

        # 3. Add WOPC patches (override base + vanilla)
        wopc_patches = config.REPO_WOPC_PATCHES
        if wopc_patches.exists():
            patched = 0
            for file_path in wopc_patches.rglob("*"):
                if file_path.is_file() and file_path.name != ".gitkeep":
                    rel = file_path.relative_to(wopc_patches)
                    arcname = str(rel).replace("\\", "/").lower()
                    zf.write(file_path, arcname)
                    patched += 1
            print(f"  Added {patched} WOPC patch files")

    # Patch SCD for engine-level overrides (first-entry wins for C++ doscript)
    wopc_patches = config.REPO_WOPC_PATCHES
    uimain_src = wopc_patches / "lua" / "ui" / "uimain.lua"
    if uimain_src.exists():
        from launcher.deploy import _patch_scd

        _patch_scd(dst, "lua/ui/uimain.lua", uimain_src)
        print("  Patched wopc_core.scd with WOPC uimain.lua")

    structure_src = wopc_patches / "lua" / "sim" / "units" / "StructureUnit.lua"
    if structure_src.exists():
        from launcher.deploy import _patch_scd

        _patch_scd(dst, "lua/sim/units/structureunit.lua", structure_src)
        print("  Patched wopc_core.scd with fixed StructureUnit.lua")

    siminit_src = wopc_patches / "lua" / "simInit.lua"
    if siminit_src.exists():
        from launcher.deploy import _patch_scd

        _patch_scd(dst, "lua/siminit.lua", siminit_src)
        print("  Patched wopc_core.scd with WOPC simInit.lua")

    size_mb = dst.stat().st_size / 1e6
    print(f"  Output: {dst} ({size_mb:.1f} MB)")
    return dst


def build_maps_zip() -> Path:
    """Create wopc-maps.zip from deployed WOPC maps and SCFA stock maps."""
    dst = STAGING / "wopc-maps.zip"

    print("Building wopc-maps.zip...")
    map_count = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add maps from the deployed WOPC maps directory
        wopc_maps = config.WOPC_MAPS
        if wopc_maps.exists():
            for map_dir in sorted(wopc_maps.iterdir()):
                if not map_dir.is_dir():
                    continue
                for file_path in map_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(wopc_maps)).replace("\\", "/")
                        zf.write(file_path, arcname)
                map_count += 1
        else:
            print(f"  WARNING: WOPC maps not found at {wopc_maps}")

        # Also add SCFA stock maps (if not already present from WOPC dir)
        scfa_maps = config.SCFA_STEAM / "maps"
        if scfa_maps.exists():
            existing_maps = {name.split("/")[0].lower() for name in zf.namelist() if "/" in name}
            for map_dir in sorted(scfa_maps.iterdir()):
                if map_dir.is_dir() and map_dir.name.lower() not in existing_maps:
                    for file_path in map_dir.rglob("*"):
                        if file_path.is_file():
                            arcname = str(file_path.relative_to(scfa_maps)).replace("\\", "/")
                            zf.write(file_path, arcname)
                    map_count += 1

    size_mb = dst.stat().st_size / 1e6
    print(f"  Output: {dst} ({size_mb:.1f} MB, {map_count} maps)")
    return dst


def copy_icons_scd() -> Path:
    """Copy the strategic icons SCD from the deployed WOPC bin directory."""
    name = "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd"
    dst = STAGING / name

    # Try deployed WOPC location first, then bundled repo location
    for src in [config.WOPC_BIN / name, config.REPO_BUNDLED_BIN / name]:
        if src.exists():
            shutil.copy2(src, dst)
            size_mb = dst.stat().st_size / 1e6
            print(f"Copied {name} from {src.parent} ({size_mb:.1f} MB)")
            return dst

    print(f"WARNING: {name} not found in WOPC/bin/ or bundled/bin/")
    return dst


_IMPORT_RE = re.compile(r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""")

# Vanilla SCDs that are always mounted (engine loads these automatically).
# Files inside these SCDs are valid import targets even if not in wopc_core.scd.
_VANILLA_SCDS = [
    "textures.scd",
    "effects.scd",
    "units.scd",
    "loc_US.scd",
    "env.scd",
    "meshes.scd",
    "mods.scd",
    "schook.scd",
    "projectiles.scd",
]

# Paths that are resolved at runtime and can't be statically verified.
_DYNAMIC_PREFIXES = [
    "/units/",  # Unit blueprints — loaded dynamically from unit SCDs
    "/projectiles/",  # Projectile blueprints
    "/effects/",  # Effect templates from vanilla effects.scd
    "/env/",  # Environment textures/meshes
    "/meshes/",  # 3D models
    "/textures/",  # Texture files (not Lua)
    "/mods/",  # Mod directories (loaded at runtime)
    "/sounds/",  # Sound files
    "/maps/",  # Map-specific files
    "/loc/",  # Localization files
]


def verify_scd_imports(scd_path: Path) -> list[str]:
    """Scan all Lua files in an SCD for import() calls and verify targets exist.

    Returns a list of unresolvable import paths (targets not found in the SCD
    or in vanilla SCDs that are always mounted).
    """
    print(f"\nVerifying import() targets in {scd_path.name}...")

    # Collect all file paths in the built SCD
    with zipfile.ZipFile(scd_path, "r") as zf:
        scd_files = {name.replace("\\", "/").lower() for name in zf.namelist()}

        # Extract all import() targets from Lua files
        imports: dict[str, set[str]] = {}  # target -> set of source files
        for name in zf.namelist():
            if not name.lower().endswith(".lua"):
                continue
            try:
                content = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue
            for match in _IMPORT_RE.finditer(content):
                target = match.group(1)
                imports.setdefault(target, set()).add(name)

    print(f"  Found {len(imports)} unique import targets across {len(scd_files)} files")

    # Collect files from vanilla SCDs
    vanilla_files: set[str] = set()
    vanilla_scd_dir = config.SCFA_STEAM / "gamedata"
    if vanilla_scd_dir.exists():
        for scd_name in _VANILLA_SCDS:
            scd = vanilla_scd_dir / scd_name
            if scd.exists():
                try:
                    with zipfile.ZipFile(scd, "r") as vzf:
                        for name in vzf.namelist():
                            vanilla_files.add(name.replace("\\", "/").lower())
                except zipfile.BadZipFile:
                    print(f"  WARNING: {scd_name} is not a valid zip — skipping")
    else:
        print("  WARNING: SCFA gamedata dir not found — cannot check vanilla SCDs")

    # Check each import target
    unresolved: list[str] = []
    for target, _sources in sorted(imports.items()):
        # Normalize: strip leading / and lowercase
        normalized = target.lstrip("/").lower()

        # Skip non-Lua imports (textures, meshes, etc.)
        if not normalized.endswith(".lua"):
            continue

        # Skip dynamically-resolved paths
        target_lower = target.lower()
        if any(target_lower.startswith(prefix) for prefix in _DYNAMIC_PREFIXES):
            continue

        # Check in wopc_core.scd
        if normalized in scd_files:
            continue

        # Check in vanilla SCDs
        if normalized in vanilla_files:
            continue

        unresolved.append(target)

    if unresolved:
        print(f"  WARNING: {len(unresolved)} unresolved import(s):")
        for target in sorted(unresolved):
            sources = imports[target]
            source_list = ", ".join(sorted(sources)[:3])
            if len(sources) > 3:
                source_list += f" (+{len(sources) - 3} more)"
            print(f"    {target}  ← {source_list}")
    else:
        print("  All import targets resolved successfully")

    return unresolved


def main() -> None:
    """Build all content assets and print upload commands."""
    print("=== WOPC Content Release Builder ===\n")

    # Clean and create staging directory
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)

    # Build assets
    core_scd = build_wopc_core_scd()
    build_maps_zip()
    copy_icons_scd()

    # Post-build verification
    unresolved = verify_scd_imports(core_scd)
    if unresolved:
        print(f"\n⚠ {len(unresolved)} unresolved import(s) — review above for details")
        print("  These files are referenced by import() but not found in any mounted SCD.")

    # Summary
    print("\n=== Staging complete ===")
    print(f"Output directory: {STAGING}")
    total_mb = sum(f.stat().st_size / 1e6 for f in STAGING.iterdir() if f.is_file())
    print(f"Total size: {total_mb:.1f} MB")

    # Print gh commands
    files = " ".join(f'"{f}"' for f in sorted(STAGING.iterdir()) if f.is_file())
    print("\nTo upload:\n")
    print("  gh release create content-v2 --title 'Content v2' \\")
    print("    --notes 'Core game content for standalone WOPC installer' \\")
    print(f"    {files}")


if __name__ == "__main__":
    main()
