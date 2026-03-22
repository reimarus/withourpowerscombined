"""Build a single-file WOPC Launcher executable using PyInstaller.

This is the *only* way to build the launcher exe. Do not invoke
PyInstaller directly — use this script so the flags stay consistent.

Output: WOPC-Launcher.exe (repo root)
"""

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    entry_point = repo_root / "launcher" / "wopc.py"

    if not entry_point.exists():
        print(f"Error: {entry_point} not found.")
        return 1

    print("Building WOPC Launcher (single-file) ...")

    # UAC manifest — the exe lives in "Program Files" and needs write access
    manifest = repo_root / "launcher" / "gui" / "uac.manifest"
    if not manifest.exists():
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">\n'
            '  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">\n'
            "    <security>\n"
            "      <requestedPrivileges>\n"
            '        <requestedExecutionLevel level="requireAdministrator"'
            ' uiAccess="false"/>\n'
            "      </requestedPrivileges>\n"
            "    </security>\n"
            "  </trustInfo>\n"
            "</assembly>\n"
        )

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "WOPC-Launcher",
        "--icon",
        str(repo_root / "launcher" / "gui" / "wopc.ico"),
        # Embed UAC manifest so Windows prompts for admin on launch
        "--manifest",
        str(manifest),
        # Bundle CustomTkinter theme assets (required for the GUI)
        "--collect-all",
        "customtkinter",
        # Bundle Pillow for map preview image rendering
        "--hidden-import",
        "PIL",
        # Bundle init scripts (needed by deploy.py at runtime)
        "--add-data",
        f"{repo_root / 'init'}{os.pathsep}init",
        # Bundle gamedata overlay (needed by deploy.py at runtime)
        "--add-data",
        f"{repo_root / 'gamedata'}{os.pathsep}gamedata",
        # Bundle GUI icon assets (map markers, faction icons, chrome)
        "--add-data",
        f"{repo_root / 'launcher' / 'gui' / 'icons'}{os.pathsep}launcher/gui/icons",
        # Output directly to repo root (not dist/)
        "--distpath",
        str(repo_root),
        str(entry_point),
    ]

    print(f"  Entry point: {entry_point}")
    print(f"  Command:     {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(repo_root))
    if result.returncode == 0:
        exe_path = repo_root / "WOPC-Launcher.exe"
        print(f"\nBuild successful: {exe_path}")
        print(f"  Size: {exe_path.stat().st_size / 1_048_576:.1f} MB")
        print("  Copy to your Supreme Commander Forged Alliance install folder to use.")
        # Clean up leftover dist/ directory if present
        dist_dir = repo_root / "dist"
        if dist_dir.exists():
            import shutil

            shutil.rmtree(dist_dir, ignore_errors=True)
        return 0
    else:
        print("\nBuild failed.")
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
