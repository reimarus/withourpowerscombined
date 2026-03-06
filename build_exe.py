"""Build a single-file WOPC Launcher executable using PyInstaller.

This is the *only* way to build the launcher exe. Do not invoke
PyInstaller directly — use this script so the flags stay consistent.

Output: dist/WOPC-Launcher.exe
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
        # Bundle CustomTkinter theme assets (required for the GUI)
        "--collect-all",
        "customtkinter",
        # Bundle init scripts (needed by deploy.py at runtime)
        "--add-data",
        f"{repo_root / 'init'}{os.pathsep}init",
        # Bundle gamedata overlay (needed by deploy.py at runtime)
        "--add-data",
        f"{repo_root / 'gamedata'}{os.pathsep}gamedata",
        str(entry_point),
    ]

    print(f"  Entry point: {entry_point}")
    print(f"  Command:     {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(repo_root))
    if result.returncode == 0:
        exe_path = repo_root / "dist" / "WOPC-Launcher.exe"
        print(f"\nBuild successful: {exe_path}")
        print(f"  Size: {exe_path.stat().st_size / 1_048_576:.1f} MB")
        return 0
    else:
        print("\nBuild failed.")
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
