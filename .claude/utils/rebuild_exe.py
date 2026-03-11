#!/usr/bin/env python3
"""Rebuild WOPC-Launcher.exe from current source.

Usage: python .claude/utils/rebuild_exe.py
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    print("Rebuilding WOPC-Launcher.exe...")
    result = subprocess.run(
        [sys.executable, str(REPO / "build_exe.py")],
        cwd=str(REPO),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
