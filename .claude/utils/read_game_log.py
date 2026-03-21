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


def _find_log() -> Path:
    """Find WOPC.log at the current install location.

    After the directory relocation (commit 4b869e4), the game directory moved
    from C:\\ProgramData\\WOPC\\ to SCFA\\WOPC\\.  Try the launcher's config
    module first, then fall back to known paths.
    """
    try:
        from launcher import config

        path = config.WOPC_BIN / config.GAME_LOG
        if path.exists():
            return path
    except Exception:
        pass

    # Known paths — new location first, then legacy
    candidates = [
        Path(
            r"C:\Program Files (x86)\Steam\steamapps\common"
            r"\Supreme Commander Forged Alliance\WOPC\bin\WOPC.log"
        ),
        Path(r"C:\ProgramData\WOPC\bin\WOPC.log"),
    ]
    for p in candidates:
        if p.exists():
            return p

    # Default to new location even if missing (gives clear error message)
    return candidates[0]


LOG_PATH = _find_log()


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
