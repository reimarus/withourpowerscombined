# WOPC Setup Guide

## Prerequisites

1. **Supreme Commander: Forged Alliance** installed via Steam
2. **Python 3.12+** installed and on PATH (for development only — players just need the exe)

## For Players

Download `WOPC-Launcher.exe` from the latest release and run it. The launcher handles setup, map selection, and game launch — no Python or command-line knowledge needed.

## For Developers

### 1. Clone the repository

```bash
git clone https://github.com/reimarus/withourpowerscombined.git
cd withourpowerscombined
```

### 2. Set up the dev environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,gui]"
```

This installs the `wopc` CLI command and all development dependencies (pytest, ruff, mypy, pyinstaller, customtkinter).

### 3. Check your installation

```bash
wopc status
```

This detects your Steam SCFA installation and prints the paths it found. Verify they are correct.

### 4. Set up the WOPC game directory

```bash
wopc setup
```

This creates `C:\ProgramData\WOPC\` and:
- Copies the game executable and DLLs from your Steam installation
- Builds `wopc_core.scd` from game logic source (merged with vanilla lua.scd)
- WOPC patches are baked into `wopc_core.scd` at build time
- Symlinks (or copies) maps, sounds, and usermods
- Copies init files and VFS helpers

### 5. Launch the game

**GUI (recommended):**
```bash
# Dev mode (uses live source — no rebuild needed):
python -c "from launcher.gui.app import launch_gui; launch_gui()"

# Or build and run the exe:
python build_exe.py
dist\WOPC-Launcher.exe
```

**CLI:**
```bash
wopc launch
```

## Troubleshooting

### "SCFA installation not found"

The launcher looks for SCFA at the default Steam path:
`C:\Program Files (x86)\Steam\steamapps\common\Supreme Commander Forged Alliance\`

If your Steam library is elsewhere, set the `SCFA_STEAM` environment variable:
```bash
set SCFA_STEAM=D:\SteamLibrary\steamapps\common\Supreme Commander Forged Alliance
python wopc.py setup
```

### Symlink errors on setup

Creating symlinks on Windows may require administrator privileges. If you see "A required privilege is not held by the client", either:
- Run the command prompt as Administrator, or
- The launcher will fall back to copying files (uses more disk space but works without admin)

### Game crashes on launch

Check the log file at `C:\ProgramData\WOPC\bin\WOPC.log` for error messages.

Common issues:
- Missing DLL: re-run `wopc setup` to copy all required DLLs
- Init file error: check that `init_wopc.lua` paths match your installation
- AI import errors: re-run `wopc setup` to rebuild `wopc_core.scd` with vanilla files merged

## C++ Toolchain Setup (Binary Patching)

To build binary patches, you'll need the 32-bit C++ toolchain:

```bash
# Install MSYS2 (provides mingw-w64-i686-gcc for 32-bit compilation)
winget install MSYS2.MSYS2

# From MSYS2 terminal:
pacman -S mingw-w64-i686-gcc

# Install LLVM/clang (for fa-python-binary-patcher)
winget install LLVM.LLVM
```

## Developer Utilities

Session utility scripts are available to speed up common operations. See `docs/utils-list.md` for the full catalog, or run directly:

```bash
python .claude/utils/run_checks.py          # pytest + ruff + mypy
python .claude/utils/rebuild_exe.py         # rebuild dist/WOPC-Launcher.exe
python .claude/utils/deploy_and_launch.py   # deploy + launch game
python .claude/utils/read_game_log.py --errors  # check for errors in game log
```
