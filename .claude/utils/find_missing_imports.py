#!/usr/bin/env python3
"""Find FAF imports that aren't satisfied by any SCD or wopc_patches."""

import re
import zipfile
from pathlib import Path

FAF_UI = Path(r"C:\ProgramData\WOPC\gamedata\faf_ui.scd")
WOPC_PATCHES = Path(r"C:\ProgramData\WOPC\gamedata\wopc_patches.scd")

import_re = re.compile(r"""import\(["'](/[^"']+)["']\)""")


def main() -> None:
    # Collect all files across both SCDs
    all_files: set[str] = set()

    for scd_path in [FAF_UI, WOPC_PATCHES]:
        if scd_path.exists():
            with zipfile.ZipFile(scd_path, "r") as zf:
                for name in zf.namelist():
                    all_files.add(name.lower().replace("\\", "/"))

    # Scan all Lua files in faf_ui.scd for import() calls
    missing: dict[str, list[str]] = {}

    with zipfile.ZipFile(FAF_UI, "r") as zf:
        for name in zf.namelist():
            if not name.endswith(".lua"):
                continue
            try:
                data = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue

            for match in import_re.finditer(data):
                imp_path = match.group(1).lstrip("/").lower()
                if imp_path not in all_files:
                    if imp_path not in missing:
                        missing[imp_path] = []
                    missing[imp_path].append(name)

    # Report
    ai_missing = {k: v for k, v in missing.items() if k.startswith("lua/ai/")}
    other_missing = {k: v for k, v in missing.items() if not k.startswith("lua/ai/")}

    print(f"Missing lua/ai/ imports ({len(ai_missing)}):")
    for path in sorted(ai_missing):
        importers = ai_missing[path]
        print(f"  /{path}  (imported by {len(importers)} file(s))")
        for imp in importers[:3]:
            print(f"    <- {imp}")

    if other_missing:
        print(f"\nOther missing imports ({len(other_missing)}):")
        for path in sorted(other_missing):
            importers = other_missing[path]
            print(f"  /{path}  (imported by {len(importers)} file(s))")
            for imp in importers[:2]:
                print(f"    <- {imp}")


if __name__ == "__main__":
    main()
