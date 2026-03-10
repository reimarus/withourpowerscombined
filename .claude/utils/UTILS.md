# WOPC Session Utilities

Quick-access scripts that reduce token cost and speed up common operations.
All paths relative to repo root (`C:\Users\roskv\wopc\`).

## Available Utilities

| Script | Purpose | Usage |
|--------|---------|-------|
| `rebuild_exe.py` | Rebuild `dist/WOPC-Launcher.exe` from current source | `python .claude/utils/rebuild_exe.py` |
| `run_checks.py` | Run pytest + ruff + mypy in one pass | `python .claude/utils/run_checks.py` (or `--quick` to skip coverage) |
| `deploy_and_launch.py` | Deploy WOPC + launch game | `python .claude/utils/deploy_and_launch.py` (or `--launch-only`) |
| `regenerate_init.py` | Regenerate `init_wopc.lua` and optionally print it | `python .claude/utils/regenerate_init.py --print` |
| `read_game_log.py` | Read/filter WOPC.log | `--errors`, `--mounts`, `--all`, `--tail N` |

## When to Use

- **After code changes**: `run_checks.py` → `rebuild_exe.py` → `deploy_and_launch.py`
- **Quick log check**: `read_game_log.py --errors` or `--mounts`
- **Just regenerate init**: `regenerate_init.py --print`

## Adding New Utilities

1. Create the script in `.claude/utils/`
2. Add it to this table
3. Commit with the feature it supports
