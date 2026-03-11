# WOPC Developer Utilities

Session utility scripts that automate common operations during development. These live in `.claude/utils/` and are designed to reduce token cost and speed up iterative work.

**Building utilities is encouraged.** If you find yourself repeating a multi-step operation (rebuild, deploy, check logs, run tests), write a script for it. A 20-line utility pays for itself in the first session. Future sessions inherit the savings.

## Available Utilities

All scripts run from repo root (`C:\Users\roskv\wopc\`).

| Script | Purpose | Usage |
|--------|---------|-------|
| `rebuild_exe.py` | Rebuild `dist/WOPC-Launcher.exe` from current source | `python .claude/utils/rebuild_exe.py` |
| `run_checks.py` | Run pytest + ruff + mypy in one pass | `python .claude/utils/run_checks.py` (or `--quick` to skip coverage) |
| `deploy_and_launch.py` | Deploy WOPC to ProgramData + launch game | `python .claude/utils/deploy_and_launch.py` (or `--launch-only`) |
| `regenerate_init.py` | Regenerate `init_wopc.lua` and optionally print it | `python .claude/utils/regenerate_init.py --print` |
| `read_game_log.py` | Read/filter `WOPC.log` | `--errors`, `--mounts`, `--all`, `--tail N` |

## Common Workflows

| Task | Commands |
|------|----------|
| After code changes | `run_checks.py` then `rebuild_exe.py` then `deploy_and_launch.py` |
| Quick log check | `read_game_log.py --errors` or `--mounts` |
| Verify init file | `regenerate_init.py --print` |
| Launch without redeploy | `deploy_and_launch.py --launch-only` |

## Adding New Utilities

1. Create the script in `.claude/utils/`
2. Add it to the table above in this file
3. Commit the script alongside the feature it supports

### Good candidates for new utilities

- Anything you do more than twice in a session
- Multi-step operations that can be combined into one command
- Log analysis or diagnostic tools
- Build/deploy shortcuts with common flag combinations
