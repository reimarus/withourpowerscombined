# Plan: Documentation Refresh + Continue Game Launch

## Context
The project has evolved significantly over the last few sessions (FAF-only mode, vanilla lua.scd merge, session utilities, quickstart system). Documentation needs to catch up. After docs are updated, we resume the in-progress task: getting the game to launch cleanly from the WOPC launcher.

---

## Part 1: Documentation Updates (5 files)

### 1. Update `docs/architecture.md`
- **Add `dist/WOPC-Launcher.exe` section** — explain what it is, how it's built (`python build_exe.py`), what it bundles (Python + CustomTkinter + init/ + gamedata/), size (~18 MB), and that it must be rebuilt after code changes
- **Add `gamedata/wopc_patches/lua/ai/` stubs** to the repo layout (gridreclaim.lua, sorianutilities.lua) since they were added
- **Update deployed faf_ui.scd description** — now merges vanilla lua.scd files during build (102 files including AI)

### 2. Create `docs/utils-list.md`
- Move the utils reference out of `.claude/utils/UTILS.md` into a project-visible doc
- List all current utils with purpose and usage
- Add a section encouraging building reusable tools to save on token cost during development sessions
- Add instructions for how to add new utils (create script → add to this list → commit together)

### 3. Update `.claude/CLAUDE.md` — Session Startup
- Add instruction to read all `docs/*.md` files during session startup
- This ensures every new session has full architectural context
- Keep the existing numbered list, add one entry after the architecture.md entry

### 4. Create `docs/plan.md`
- A living document that tracks the current implementation plan
- Should be updated whenever a new plan is created in `.claude/plans/`
- Should be replaced/cleared when the final step of a plan is executed and committed
- This gives any session (human or AI) a quick view of "what are we working on right now?"

### 5. Update `docs/setup-guide.md`
- Fix Python version: `3.10+` → `3.12+` (pyproject.toml requires `>=3.12`)
- Add GUI launcher option: `dist/WOPC-Launcher.exe` as the primary way to play
- Add dev dependencies install: `pip install -e ".[dev,gui]"`
- Add CLI entry: `wopc` command available after pip install
- Update the launch step to mention both CLI and GUI options
- Add a "Development Utilities" section pointing to `docs/utils-list.md`

---

## Part 2: Continue Game Launch Work

After committing the docs, resume the vanilla lua.scd merge test:

1. **Verify** `faf_ui.scd` was rebuilt with vanilla AI files (check zip contents)
2. **Launch game** and check WOPC.log for AI import errors being resolved
3. **If sim loads** → raw FAF is running from our launcher → commit the implementation
4. **If new errors** → diagnose and fix iteratively
5. **Update** QUICKSTART_STATE.md with results

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `docs/architecture.md` | Edit — add dist/launcher.exe section, update repo layout |
| `docs/utils-list.md` | **Create** — utils catalog + encouragement to build tools |
| `docs/plan.md` | **Create** — living plan tracker |
| `docs/setup-guide.md` | Edit — Python 3.12+, GUI launcher, dev setup |
| `.claude/CLAUDE.md` | Edit — add `docs/*.md` to session startup reads |

## Verification
- All docs render cleanly as markdown
- No broken cross-references between docs
- CLAUDE.md session startup list includes docs/ reading
- Commit all doc changes together, then continue with game launch work
