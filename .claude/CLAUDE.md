# WOPC — Code Standards

This is a game people play with friends. Bugs crash the party. Every line of code must earn its place.

## Session Startup (MANDATORY)

**Before doing ANY work in a new session, read these files:**
1. `C:\Users\roskv\wopc\.claude\CLAUDE.md` — this file (code standards, architecture)
2. `C:\Users\roskv\wopc\.claude\SCFA_ENGINE_REFERENCE.md` — SCFA engine API reference (moho methods, callbacks, Lua dialect, VFS)
3. `C:\Users\roskv\wopc\.claude\QUICKSTART_STATE.md` — session recovery breadcrumbs
3. `C:\Users\roskv\wopc\docs\architecture.md` — system architecture and VFS design
4. `C:\Users\roskv\wopc\docs\plan.md` — current implementation plan (what are we working on?)
5. `C:\Users\roskv\wopc\docs\utils-list.md` — available developer utilities
6. All other `C:\Users\roskv\wopc\docs\*.md` files — setup guide, vision, patching
7. `C:\Users\roskv\.claude\projects\C--Users-roskv-loudmod\memory\MEMORY.md` — cross-session memory
8. Any `.claude/plans/*.md` files — active implementation plans

**Before executing any implementation plan:**
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

1. Feature branch off `main`
2. Write code + tests
3. `pytest` — all pass, coverage ≥ 70%
4. `ruff check launcher/ tests/` — clean
5. `mypy launcher/` — clean
6. `git commit` — pre-commit hooks auto-run (ruff, trailing whitespace, large file check)
7. `python build_exe.py` — rebuild `dist/WOPC-Launcher.exe` and smoke-test launch
8. `git push` + `gh pr create` — CI runs 4 jobs (lint, typecheck, test, lua-check)
9. CodeRabbit reviews PR automatically
10. Merge only when CI is green

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
| `launcher/deploy.py` | `_patch_scd()` patches faf_ui.scd + lua.scd with our uimain.lua |
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

## Key Technical Gotchas

- `WOPC_ROOT` is `C:\ProgramData\WOPC\`, NOT inside Steam. `init_wopc.lua` loads `wopc_paths.lua` (generated by setup) to find SCFA.
- `deploy.py` generates `wopc_paths.lua` with escaped backslashes for Lua string literals.
- Symlinks on Windows may need admin. `link_or_copy()` handles the fallback silently.
- The game exe expects `/init init_wopc.lua` as a command-line argument. `InitFileDir` is set by the engine to the directory containing the init file.
- **VFS has TWO search orders (critical!):**
  - **Engine C++ file loading** (uimain.lua, etc.): **first-added = highest priority** — earlier mounts win
  - **Lua `import()` function**: **last-added = highest priority** — later mounts shadow earlier ones
  - This means VFS overlays (wopc_patches.scd) work for Lua `import()` but NOT for engine-loaded files
  - To override engine-loaded files like uimain.lua, you must **patch the SCD directly** using `_patch_scd()` in deploy.py (patches both faf_ui.scd and lua.scd)
  - Mount order in init_wopc.lua: (1) icons → (2) content packs (LOUD, disabled by default) → (3) maps/sounds → (4) vanilla SCFA (units, textures, loc, etc.) → (5) faf_ui.scd → (6) wopc_patches.scd → (7) usermaps → (8) usermods
- **`InitFileDir` is NOT available in the UI Lua state.** It only exists during init file execution. Use `GetCommandLineArg()` to pass paths from the launcher.
- **Patcher uses module-level config.** `patcher.py` uses `from launcher import config` then `config.SCFA_BIN`, same pattern as `deploy.py`. Mock with `patch("launcher.patcher.config")` in tests.
- **Patcher staging is disposable.** `patches/build/staging/` is a temp copy — never modify the submodule sources directly.
- **Toolchain must be 32-bit.** SCFA is a 32-bit game. The patcher compiles with `-m32` flags. x64 compilers will produce incompatible code.
