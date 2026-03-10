#!/usr/bin/env python3
"""Regenerate init_wopc.lua and print it.

Usage: python .claude/utils/regenerate_init.py
       python .claude/utils/regenerate_init.py --print   (also print contents)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))


def main() -> None:
    from launcher.init_generator import generate_init_lua

    output = generate_init_lua()
    print(f"Generated: {output}")
    print(f"Size: {output.stat().st_size} bytes")

    if "--print" in sys.argv:
        print()
        print(output.read_text())


if __name__ == "__main__":
    main()
