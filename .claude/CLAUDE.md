# WOPC — Code Standards

This is a game people play with friends. Bugs crash the party. Every line of code must earn its place.

## Session Startup (MANDATORY)

**Step 1 — Read project context (do this FIRST, before any work):**
1. `C:\Users\roskv\wopc\.claude\CLAUDE.md` — this file (code standards, rules, architecture)
2. `C:\Users\roskv\wopc\.claude\SCFA_ENGINE_REFERENCE.md` — SCFA engine API reference (moho methods, callbacks, Lua dialect, VFS)
3. `C:\Users\roskv\wopc\.claude\QUICKSTART_STATE.md` — session recovery breadcrumbs
4. `C:\Users\roskv\wopc\docs\architecture.md` — system architecture and VFS design
5. `C:\Users\roskv\wopc\docs\plan.md` — current implementation plan (what are we working on?)
6. `C:\Users\roskv\wopc\docs\backlog.md` — prioritized feature/fix backlog
7. `C:\Users\roskv\wopc\docs\utils-list.md` — available developer utilities
8. All other `C:\Users\roskv\wopc\docs\*.md` files — setup guide, vision, patching
9. `C:\Users\roskv\.claude\projects\C--Users-roskv-loudmod\memory\MEMORY.md` — cross-session memory
10. Any `.claude/plans/*.md` files — active implementation plans

**Step 2 — Verify project state (catch stale info before it bites):**
- Run `git branch` + `gh pr list --state open` — know what branch you're on and what's in flight
- If `QUICKSTART_STATE.md` references a merged PR or deleted branch, **update it immediately**
- If `docs/plan.md` shows completed items with no active next step, flag it to the user
- If any doc references architecture that no longer exists (e.g., "FAF lobby"), fix it before proceeding (see Rule #2)

**Step 3 — Before executing any implementation plan:**
- Write or update the plan in `.claude/plans/`
- **Commit the plan FIRST** before writing any code
- Plans are committed artifacts, not throwaway notes

**Session utilities** (see `.claude/utils/UTILS.md` for full list):
- `python .claude/utils/run_checks.py` — pytest + ruff + mypy in one pass
- `python .claude/utils/rebuild_exe.py` — rebuild launcher exe
- `python .claude/utils/deploy_and_launch.py` — deploy + launch game
- `python .claude/utils/read_game_log.py --errors` — quick log analysis

## Project

**WOPC** (With Our Powers Combined) merges LOUD gameplay with FAF engine patches for Supreme Commander: Forged Alliance.

- Repo: https://github.com/reimarus/withourpowerscombined
- Local: `C:\Users\roskv\wopc\`
- Python 3.12+, Windows-only target
- Venv: `.venv\Scripts\activate`, install: `pip install -e ".[dev]"`
- CLI: `wopc status | setup | launch | validate | patch`

## Quality Bar

**No slop. No junk. No "good enough."**

- Every test must prove something real. If a test can't fail meaningfully, delete it.
- Every function must be testable. If it can't be tested without the real game installed, refactor it.
- Every error must be handled. Silent failures are bugs.
- Every change must pass CI before merge. No exceptions.

## Testing Standards

- Framework: pytest + pytest-cov + pytest-mock
- Coverage floor: 70% (enforced in pyproject.toml)
- **No junk tests.** A test that just checks a function doesn't throw is worthless. Test behavior, edge cases, and failure modes.
- **No real filesystem.** Use `tmp_path` fixtures with fake directory trees. Tests must run without SCFA, LOUD, or WOPC installed.
- **Mock at the right level.** `deploy.py` uses `config.ATTR` access (not `from config import ATTR`) so `patch("launcher.config.X")` works. If you import names directly, patching breaks.
- **Test the sad path.** Missing files, missing directories, permission errors, corrupt data. These are the bugs that ruin game night.
- Run tests: `pytest` (coverage included via pyproject.toml addopts)

## Code Patterns

### Python
- **Logging, not print.** All output through `logging.getLogger("wopc.*")`. The `T201` ruff rule will catch print() if it sneaks back in.
- **Module-level config access.** `from launcher import config` then `config.WOPC_ROOT` — never `from launcher.config import WOPC_ROOT`. The latter creates local copies that can't be patched in tests.
- **Type hints on public functions.** Return types, parameter types. mypy checks these in CI.
- **pathlib everywhere.** No `os.path.join`, no string concatenation for paths.
- **Ruff formatting.** Line length 100, double quotes, sorted imports. Don't fight the formatter.

### Lua (SCFA engine)
- **SCFA Lua is NOT standard Lua.** It's a modified Lua 5.0 fork with:
  - `!=` instead of `~=` for not-equal
  - `continue` keyword in loops
  - No `math.fmod` — use `math.sin`/`math.cos` for modular arithmetic
  - No `#` operator — use `table.getn()`
  - No `math.random` — use `Random()`
  - No `%` modulo operator
- **VFS mount order matters.** Later mounts shadow earlier ones. The order in `init_wopc.lua` is critical to gameplay. Don't reorder without understanding the cascade.
- **Never commit game binaries.** `.gitignore` blocks `.exe`, `.dll`, `.scd`, `.zip`. If git wants to add a binary, something is wrong.

## Workflow

### Development cycle
1. `git checkout main && git pull` — always start from fresh main
2. `git checkout -b <type>/<short-name>` — feature branch off main (types: `feature/`, `fix/`, `docs/`, `refactor/`)
3. Write code + tests
4. `pytest` — all pass, coverage ≥ 70%
5. `ruff check launcher/ tests/` — clean
6. `mypy launcher/` — clean
7. `git commit` — pre-commit hooks auto-run (ruff, trailing whitespace, large file check)
8. `python build_exe.py` — rebuild `dist/WOPC-Launcher.exe` and smoke-test launch
9. Update `docs/backlog.md` — mark completed items, add new ideas, identify next improvement (Rule #6)
10. `git push -u origin <branch>` + `gh pr create`
11. CI runs 4 jobs (lint, typecheck, test, lua-check). CodeRabbit reviews automatically.
12. Merge only when CI is green

### GitHub hygiene (keep the repo clean)
- **Never commit directly to main.** All work goes through feature branches + PRs.
- **One active feature branch at a time** unless explicitly working on parallel efforts.
- **After merge, delete the branch** — both local (`git branch -d`) and remote (`git push origin --delete`).
- **After merge, update main** — `git checkout main && git pull`.
- **No stale PRs.** If a PR sits unmerged for more than a session, either merge it, close it, or note why it's blocked in the PR description.
- **No orphan branches.** Run `git branch -a` at session start. If remote branches exist for merged PRs, delete them.
- **Update `QUICKSTART_STATE.md` after merge** — clear references to the old branch/PR, update "Current State" to reflect what's on main now.

## Cross-AI Handoff

When transitioning phases or receiving the development branch from Antigravity (Gemini), I will read `.gemini/GEMINI.md` to understand the overarching architectural context and `docs/architecture.md` for specific planned features before executing code. Gemini designs the engine and maps the territory; I build it flawlessly. Both of us read the project documentation and maintain cross-communication through task checklists.

## Architecture

```
C:\Users\roskv\wopc\          (repo)
  launcher/                    Python CLI + GUI
    wopc.py                    Entry point (status/setup/launch/validate/patch)
    config.py                  Path constants, file lists, version
    mods.py                    Mod system — discovery, activation, content packs, extraction
    deploy.py                  Creates C:\ProgramData\WOPC\ game directory
    game_config.py             Generates wopc_game_config.lua (quickstart config)
    init_generator.py          init_wopc.lua template (delegates to mods.py)
    prefs.py                   INI prefs (map, player, display, launch mode)
    log.py                     Logging configuration
    toolchain.py               Compiler discovery (Clang, GCC, LD)
    manifest.py                Patch manifest parsing (wopc_patches.toml)
    patcher.py                 Build orchestration for patched exe
    gui/                       GUI launcher (customtkinter)
      app.py                   WopcApp — main window, map selector, multiplayer lobby, game browser
      worker.py                SetupWorker — async setup in background thread
      wopc.ico                 Application icon
  build_exe.py                 PyInstaller build script → dist/WOPC-Launcher.exe
  dist/WOPC-Launcher.exe       Built GUI launcher (rebuild after code changes!)
  init/                        Lua init files (deployed to WOPC\bin\)
    init_wopc.lua              VFS mount order
    CommonDataPath.lua         VFS helper functions
  vendor/                      Git submodules
    FA-Binary-Patches/         FAF C++ patches (66 hooks + 53 sections)
    fa-python-binary-patcher/  Python patcher tool (compiles + injects patches)
  wopc_patches.toml            Patch manifest (exclude list)
  patches/build/               Build output (gitignored)
  gamedata/wopc_patches/       WOPC Lua overlay (Phase 3+)
  tests/                       pytest suite
```

### GUI Launcher

**Build:** `python build_exe.py` → `dist/WOPC-Launcher.exe` (~18 MB)
**Run (dev):** `.venv/Scripts/python.exe -c "from launcher.gui.app import launch_gui; launch_gui()"`
**Run (built):** `dist/WOPC-Launcher.exe`
**IMPORTANT:** The exe bundles Python code at build time. After ANY code changes to `launcher/`, `init/`, or `gamedata/`, you MUST rebuild with `python build_exe.py` before testing the exe. Running from dev mode (`launch_gui()`) always uses current source.

### Patch Build Flow

```
wopc patch
  1. Copy FA-Binary-Patches → staging dir
  2. Remove excluded patches (per wopc_patches.toml)
  3. Copy stock exe from Steam as base
  4. Run fa-python-binary-patcher (Clang + GCC → patched exe)
  5. Output → patches/build/ForgedAlliance_exxt.exe

wopc setup
  → Detects patched exe and deploys it (falls back to stock if not built)
```

### Quick-Start System (bypass lobby, launch directly into match)

The WOPC launcher can launch games directly — no in-game lobby UI needed.

**Flow:**
```
Python launcher (wopc.py)
  → writes wopc_game_config.lua (map, players, AI, options)
  → passes /wopcquickstart /wopcconfig <path> on command line
  → engine loads init_wopc.lua → mounts VFS → loads uimain.lua

uimain.lua (our patched copy in lua.scd)
  → SetupUI() — cursor, skin, layout (called by engine C++)
  → StartHostLobbyUI() — detects /wopcquickstart flag
  → calls quickstart.lua:Launch()

quickstart.lua
  → reads config via GetCommandLineArg("/wopcconfig")
  → creates LobbyComm via lobbyComm.lua:CreateLobbyComm()
  → builds gameInfo table (GameOptions + PlayerOptions)
  → calls comm:LaunchGame(gameInfo) → engine enters simulation
```

**Key files:**
| File | Role |
|------|------|
| `launcher/wopc.py` | Writes config, passes /wopcquickstart + /wopcconfig |
| `launcher/game_config.py` | Generates wopc_game_config.lua (Lua table) |
| `launcher/deploy.py` | `_patch_scd()` patches wopc_core.scd + lua.scd with our uimain.lua |
| `gamedata/wopc_patches/lua/ui/uimain.lua` | Full FAF copy + quickstart hook |
| `gamedata/wopc_patches/lua/wopc/quickstart.lua` | LobbyComm-based game launcher |

**Critical discoveries (hard-won):**
- `InitFileDir` is only in the init Lua state, NOT the UI state. Use command-line args.
- `OwnerID` in PlayerOptions must be a **string** (peer ID), not a number.
- `moho.lobby_methods.LaunchGame` is the actual C++ entry point.

## Phase Roadmap
- **Phase 0** ✅ Foundation — launcher, init, CI, tests
- **Phase 1** ✅ Game launches from WOPC directory
- **Phase 2** ✅ FAF binary patches integration
- **Phase 3** ✅ WOPC Lua overlay (quickstart system + content packs)
- **Phase 4** ✅ Multiplayer support — TCP lobby, game state sync, file transfer, chat, kick, ready
- **Phase 5** ✅ Player slot management + game options (colors, teams, victory, unit cap, share)
- **Phase 6** 🔧 Modern multiplayer UX — game browser, LAN discovery, unified lobby room
- **Phase 7** → C++ pathfinding patch

## Rules (MUST follow)

1. **Plan files live in HOME, not project.** `ExitPlanMode` reads from `C:\Users\roskv\.claude\plans\`, NOT `C:\Users\roskv\wopc\.claude\plans\`. Always write/update plans at the HOME path. Stale content at the wrong path caused 4 consecutive plan rejections.
2. **Stale docs poison context.** When architecture changes (e.g., dropping FAF lobby), update ALL docs that reference the old approach: `QUICKSTART_STATE.md`, `CLAUDE.md`, `docs/plan.md`, `docs/architecture.md`, and any `.claude/plans/*.md` files. If Claude keeps producing wrong plans, the root cause is almost always stale documentation.
3. **When you hit a recurring problem, add a rule here.** If you spend more than 2 rounds fixing the same class of issue, add a numbered entry to this section so future sessions avoid the trap. This is mandatory — don't just fix the problem, encode the fix as a rule.
4. **Before submitting any plan via ExitPlanMode, verify the plan file content at the HOME path.** Read `C:\Users\roskv\.claude\plans\<filename>.md` back AFTER writing it to confirm the content matches intent. Never assume a write succeeded — stale content at that path has caused repeated plan rejections.
5. **Solo and multiplayer UI must be visually consistent.** Shared concepts (map selector, player slots, game options, victory conditions) must use the same widgets, styling, and layout patterns in both solo and multiplayer screens. If you change a UI element in one screen, update the other to match. No visual drift between modes.
6. **Always review and update `docs/backlog.md` at PR time.** Before every PR: (a) mark completed items, (b) add new ideas discovered during the work, (c) identify one improvement to work on next. The backlog is a living document — never let it go stale.
7. **Continuously improve project docs to maximize efficiency.** Always consider what can be created, updated, or deleted in `CLAUDE.md`, `QUICKSTART_STATE.md`, `docs/backlog.md`, `docs/plan.md`, and `docs/architecture.md` to make navigating this project faster. If you learn something that would save time in future sessions, encode it immediately. The goal: any new session should become an expert on this project as quickly as possible by reading these files.
8. **NEVER commit to main directly — always create a branch FIRST.** Before writing ANY code, run `git checkout -b <branch-name>`. All work on feature branches, no exceptions. This is the FIRST thing you do when starting work, before reading files, before planning. After merge: delete branch (local + remote), pull main, update `QUICKSTART_STATE.md`. No stale PRs, no orphan branches. Run `git branch` at session start to verify you're NOT on main.
9. **Never rebuild the exe to test changes — use releases.** The launcher has auto-update from GitHub Releases. To test code changes: (a) run from dev mode (`python -c "from launcher.gui.app import launch_gui; launch_gui()"`), or (b) create a release via `scripts/release.py` and let the launcher self-update. Rebuilding and manually copying the exe is wasted effort and bypasses the update pipeline we built.
10. **Delete dead code, don't just stop referencing it.** When removing a feature or consolidating code (e.g. wopc_patches.scd into wopc_core.scd), actually delete the dead files, functions, constants, and stale config entries. Leaving them around creates confusion and maintenance burden. Grep the codebase for old names after any rename.
11. **After merging a PR, always create a release.** The standard flow is: merge PR → `git checkout main && git pull` → `py scripts/release.py`. The release script handles everything (version bump, tests, exe build, GitHub release, push). Never skip the release step — users get updates via the launcher's auto-updater, so an unrelased merge is invisible to them. If Lua files changed (quickstart.lua, multilobby.lua, etc.), also run `python -c "from launcher.wopc import cmd_setup; cmd_setup()"` to rebuild `wopc_core.scd` before releasing.
12. **Never duplicate information on screen.** Screen real estate is limited. Every piece of text, label, or widget must earn its place. If data is already visible (e.g., map name in the list), don't repeat it in the preview panel. If a button's function is obvious from context (e.g., clicking a map opens inspect), don't add a separate button. UI layout must be stable — no dynamic resizing that causes elements to jump around. Redraws should only happen on window resize, not on data changes.

## Key Technical Gotchas

- `WOPC_ROOT` is `SCFA\WOPC\` (inside the Steam install folder). The launcher exe sits in SCFA root; when frozen, `sys.executable.parent` = SCFA root, so `WOPC_ROOT = SCFA / "WOPC"`. `init_wopc.lua` loads `wopc_paths.lua` to resolve `SCFARoot`.
- `deploy.py` generates `wopc_paths.lua` with escaped backslashes for Lua string literals.
- Symlinks on Windows may need admin. `link_or_copy()` handles the fallback silently.
- The game exe expects `/init init_wopc.lua` as a command-line argument. `InitFileDir` is set by the engine to the directory containing the init file.
- **VFS has TWO search orders (critical!):**
  - **Engine C++ file loading** (uimain.lua, etc.): **first-added = highest priority** — earlier mounts win
  - **Lua `import()` function**: **last-added = highest priority** — later mounts shadow earlier ones
  - This means VFS overlays work for Lua `import()` but NOT for engine-loaded files
  - To override engine-loaded files like uimain.lua, `_patch_scd()` in deploy.py rewrites the SCD so our version is the first entry (first-added wins)
  - Mount order in init_wopc.lua: (1) icons → (2) content packs (LOUD, disabled by default) → (3) maps/sounds → (4) wopc_core.scd → (5) vanilla SCFA (units, textures, loc, etc.) → (6) usermaps → (7) server mods → (8) usermods
- **`InitFileDir` is NOT available in the UI Lua state.** It only exists during init file execution. Use `GetCommandLineArg()` to pass paths from the launcher.
- **Patcher uses module-level config.** `patcher.py` uses `from launcher import config` then `config.SCFA_BIN`, same pattern as `deploy.py`. Mock with `patch("launcher.patcher.config")` in tests.
- **Patcher staging is disposable.** `patches/build/staging/` is a temp copy — never modify the submodule sources directly.
- **Toolchain must be 32-bit.** SCFA is a 32-bit game. The patcher compiles with `-m32` flags. x64 compilers will produce incompatible code.
