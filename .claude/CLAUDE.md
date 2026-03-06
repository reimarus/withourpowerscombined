# WOPC — Code Standards

This is a game people play with friends. Bugs crash the party. Every line of code must earn its place.

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
7. `git push` + `gh pr create` — CI runs 4 jobs (lint, typecheck, test, lua-check)
8. CodeRabbit reviews PR automatically
9. Merge only when CI is green

## Cross-AI Handoff

When transitioning phases or receiving the development branch from Antigravity (Gemini), I will read `.gemini/GEMINI.md` to understand the overarching architectural context and `docs/architecture.md` for specific planned features before executing code. Gemini designs the engine and maps the territory; I build it flawlessly. Both of us read the project documentation and maintain cross-communication through task checklists.

## Architecture

```
C:\Users\roskv\wopc\          (repo)
  launcher/                    Python CLI
    wopc.py                    Entry point (status/setup/launch/validate/patch)
    config.py                  Path constants, file lists, version
    deploy.py                  Creates C:\ProgramData\WOPC\ game directory
    log.py                     Logging configuration
    toolchain.py               Compiler discovery (Clang, GCC, LD)
    manifest.py                Patch manifest parsing (wopc_patches.toml)
    patcher.py                 Build orchestration for patched exe
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

## Phase Roadmap
- **Phase 0** ✅ Foundation — launcher, init, CI, tests
- **Phase 1** ✅ Game launches from WOPC directory
- **Phase 2** ✅ FAF binary patches integration
- **Phase 3** → WOPC Lua overlay
- **Phase 4** → Multiplayer support
- **Phase 5** → C++ pathfinding patch

## Key Technical Gotchas

- `WOPC_ROOT` is `C:\ProgramData\WOPC\`, NOT inside Steam. `init_wopc.lua` loads `wopc_paths.lua` (generated by setup) to find SCFA.
- `deploy.py` generates `wopc_paths.lua` with escaped backslashes for Lua string literals.
- Symlinks on Windows may need admin. `link_or_copy()` handles the fallback silently.
- The game exe expects `/init init_wopc.lua` as a command-line argument. `InitFileDir` is set by the engine to the directory containing the init file.
- **Patcher uses module-level config.** `patcher.py` uses `from launcher import config` then `config.SCFA_BIN`, same pattern as `deploy.py`. Mock with `patch("launcher.patcher.config")` in tests.
- **Patcher staging is disposable.** `patches/build/staging/` is a temp copy — never modify the submodule sources directly.
- **Toolchain must be 32-bit.** SCFA is a 32-bit game. The patcher compiles with `-m32` flags. x64 compilers will produce incompatible code.
