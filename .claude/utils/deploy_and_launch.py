#!/usr/bin/env python3
"""Deploy WOPC and launch the game in one step.

Usage: python .claude/utils/deploy_and_launch.py
       python .claude/utils/deploy_and_launch.py --launch-only   (skip deploy)
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))


def main() -> None:
    from launcher.wopc import cmd_launch, cmd_setup

    if "--launch-only" not in sys.argv:
        print("Running setup...")
        cmd_setup()
        print()

    print("Launching game...")
    cmd_launch()


if __name__ == "__main__":
    main()
