"""Build wopc_core.scd from vendor/faf-ui + vanilla lua.scd + wopc_patches.

This creates the consolidated SCD that the game needs. Run this when
updating the game logic source or WOPC patches, then upload to a content release.

Usage:
    py scripts/build_wopc_core.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = REPO_ROOT / "vendor" / "faf-ui"
WOPC_PATCHES = REPO_ROOT / "gamedata" / "wopc_patches"
VANILLA_LUA_SCD = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common"
    r"\Supreme Commander Forged Alliance\gamedata\lua.scd"
)
OUTPUT = REPO_ROOT / "build" / "wopc_core.scd"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    print(f"  Source:  {CORE_SRC}")
    print(f"  Patches: {WOPC_PATCHES}")
    print(f"  Vanilla: {VANILLA_LUA_SCD}")
    print(f"  Output:  {OUTPUT}")
    print()

    core_count = 0
    merged_count = 0
    patched_count = 0

    # Use ZIP_STORED — the SCFA engine's VFS may not support DEFLATED
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_STORED) as zf:
        # 1. Game logic source files
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
            dir_path = CORE_SRC / target_dir
            if dir_path.exists():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        rel = file_path.relative_to(CORE_SRC)
                        arcname = str(rel).replace("\\", "/").lower()
                        zf.write(file_path, arcname)
                        core_count += 1

        print(f"  Added {core_count} game logic source files")

        # 2. Merge vanilla lua.scd gap-fills (AI files etc.)
        if VANILLA_LUA_SCD.exists():
            existing = {name.replace("\\", "/").lower() for name in zf.namelist()}
            with zipfile.ZipFile(VANILLA_LUA_SCD, "r") as vanilla_zf:
                for info in vanilla_zf.infolist():
                    if info.is_dir():
                        continue
                    normalized = info.filename.replace("\\", "/").lower()
                    if normalized not in existing:
                        zf.writestr(normalized, vanilla_zf.read(info))
                        merged_count += 1
            print(f"  Merged {merged_count} vanilla lua.scd gap-fill files")
        else:
            print(f"  WARNING: vanilla lua.scd not found at {VANILLA_LUA_SCD}")

        # 3. WOPC patches (override everything)
        if WOPC_PATCHES.exists():
            for file_path in WOPC_PATCHES.rglob("*"):
                if file_path.is_file() and file_path.name != ".gitkeep":
                    rel = file_path.relative_to(WOPC_PATCHES)
                    arcname = str(rel).replace("\\", "/").lower()
                    zf.write(file_path, arcname)
                    patched_count += 1
            print(f"  Added {patched_count} WOPC patch files")

    size_mb = OUTPUT.stat().st_size / 1_000_000
    print(f"\n  Built wopc_core.scd: {size_mb:.1f} MB")
    print(f"  Total entries: {core_count + merged_count + patched_count}")


if __name__ == "__main__":
    main()
