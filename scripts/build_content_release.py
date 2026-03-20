"""Build content assets for a WOPC GitHub Release.

Developer-only script. Produces release-staging/ with all assets
needed for the content-v2 GitHub Release, then prints the gh commands
to upload them.

Requirements:
    - LOUD installed (for strategic icons SCD)
    - Full repo with vendor submodules (for wopc_core.scd build)
    - Steam SCFA installed (for vanilla lua.scd merge)

Usage:
    python scripts/build_content_release.py
"""

import shutil
import sys
import zipfile
from pathlib import Path

# Add repo root to path so we can import launcher modules
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from launcher import config  # noqa: E402

STAGING = REPO_ROOT / "release-staging"

# Curated multiplayer maps — popular maps for day-one play
CURATED_MAPS = [
    "Seton's Clutch",
    "Dual Gap",
    "Fields of Isis",
    "Emerald Crater 40",
    "Gap of Rohan",
    "Burial Mounds 40",
    "Cold Valley",
    "Amazonia",
    "Battle Isles 40",
    "Caldera",
]


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

        # 2. Merge vanilla lua.scd files that FAF doesn't replace
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

        # 3. Add WOPC patches (override FAF + vanilla)
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

    size_mb = dst.stat().st_size / 1e6
    print(f"  Output: {dst} ({size_mb:.1f} MB)")
    return dst


def build_maps_zip() -> Path:
    """Create wopc-maps.zip with curated multiplayer maps from LOUD."""
    dst = STAGING / "wopc-maps.zip"
    loud_maps = config.LOUD_ROOT / "maps"

    if not loud_maps.exists():
        print(f"WARNING: LOUD maps not found at {loud_maps}, skipping maps zip")
        return dst

    print("Building wopc-maps.zip...")
    map_count = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for map_dir in sorted(loud_maps.iterdir()):
            if not map_dir.is_dir():
                continue
            # Check against curated list (case-insensitive)
            if not any(map_dir.name.lower() == cm.lower() for cm in CURATED_MAPS):
                continue
            # Add all files in the map directory
            for file_path in map_dir.rglob("*"):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(loud_maps)).replace("\\", "/")
                    zf.write(file_path, arcname)
            map_count += 1
            print(f"  Added map: {map_dir.name}")

    # Also add SCFA stock maps
    scfa_maps = config.SCFA_STEAM / "maps"
    if scfa_maps.exists():
        for map_dir in sorted(scfa_maps.iterdir()):
            if map_dir.is_dir():
                for file_path in map_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(scfa_maps)).replace("\\", "/")
                        zf.write(file_path, arcname)
                map_count += 1

    size_mb = dst.stat().st_size / 1e6
    print(f"  Output: {dst} ({size_mb:.1f} MB, {map_count} maps)")
    return dst


def copy_icons_scd() -> Path:
    """Copy the strategic icons SCD from LOUD."""
    name = "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd"
    src = config.LOUD_ROOT / "bin" / name
    dst = STAGING / name

    if src.exists():
        shutil.copy2(src, dst)
        size_mb = dst.stat().st_size / 1e6
        print(f"Copied {name} ({size_mb:.1f} MB)")
    else:
        print(f"WARNING: {name} not found at {src}")
    return dst


def main() -> None:
    """Build all content assets and print upload commands."""
    print("=== WOPC Content Release Builder ===\n")

    # Clean and create staging directory
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)

    # Build assets
    build_wopc_core_scd()
    build_maps_zip()
    copy_icons_scd()

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
