#!/usr/bin/env python3
"""Read and filter WOPC.log for quick analysis.

Usage: python .claude/utils/read_game_log.py              (last 50 lines)
       python .claude/utils/read_game_log.py --errors      (only warnings/errors)
       python .claude/utils/read_game_log.py --mounts      (VFS mount lines)
       python .claude/utils/read_game_log.py --all         (full log)
       python .claude/utils/read_game_log.py --tail N      (last N lines)
"""

import sys
from pathlib import Path

LOG_PATH = Path(r"C:\ProgramData\WOPC\bin\WOPC.log")


def main() -> None:
    if not LOG_PATH.exists():
        print(f"No log file found at {LOG_PATH}")
        sys.exit(1)

    lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()

    if "--errors" in sys.argv:
        lines = [line for line in lines if line.startswith(("warning:", "error:", "ASSERT"))]
    elif "--mounts" in sys.argv:
        lines = [line for line in lines if "AddSearchPath" in line or "Mounting mod" in line]
    elif "--all" not in sys.argv:
        tail = 50
        for i, arg in enumerate(sys.argv):
            if arg == "--tail" and i + 1 < len(sys.argv):
                tail = int(sys.argv[i + 1])
        lines = lines[-tail:]

    for line in lines:
        print(line)

    print(f"\n--- {LOG_PATH} ({LOG_PATH.stat().st_size:,} bytes) ---")


if __name__ == "__main__":
    main()
