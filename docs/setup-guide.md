# WOPC Setup Guide

## Prerequisites

1. **Supreme Commander: Forged Alliance** installed via Steam
2. **LOUD mod** installed (follow LOUD's installation guide first)
3. **Python 3.10+** installed and on PATH

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/reimarus/withourpowerscombined.git
cd withourpowerscombined
```

### 2. Check your installation

```bash
cd launcher
python wopc.py status
```

This will detect your Steam SCFA installation and LOUD mod, and print the paths it found. Verify they are correct.

### 3. Set up the WOPC game directory

```bash
python wopc.py setup
```

This creates `C:\ProgramData\WOPC\` and:
- Copies the game executable and DLLs from your Steam installation
- Symlinks (or copies) LOUD's gamedata, maps, sounds, and usermods
- Copies the init file and VFS helpers

### 4. Launch the game

```bash
python wopc.py launch
```

The game starts with LOUD gameplay running from the isolated WOPC directory.

## Troubleshooting

### "SCFA installation not found"

The launcher looks for SCFA at the default Steam path:
`C:\Program Files (x86)\Steam\steamapps\common\Supreme Commander Forged Alliance\`

If your Steam library is elsewhere, set the `SCFA_STEAM` environment variable:
```bash
set SCFA_STEAM=D:\SteamLibrary\steamapps\common\Supreme Commander Forged Alliance
python wopc.py setup
```

### "LOUD installation not found"

LOUD must be installed at `<SCFA_ROOT>\LOUD\`. If you haven't installed LOUD yet, follow the LOUD installation guide first.

### Symlink errors on setup

Creating symlinks on Windows may require administrator privileges. If you see "A required privilege is not held by the client", either:
- Run the command prompt as Administrator, or
- The launcher will fall back to copying files (uses more disk space but works without admin)

### Game crashes on launch

Check the log file at `C:\ProgramData\WOPC\bin\WOPC.log` for error messages.

Common issues:
- Missing DLL: re-run `python wopc.py setup` to copy all required DLLs
- Init file error: check that `init_wopc.lua` paths match your installation

## Development Setup (Phase 2+)

To build FAF binary patches, you'll need the C++ toolchain:

```bash
# Install MSYS2 (provides mingw-w64-i686-gcc for 32-bit compilation)
winget install MSYS2.MSYS2

# From MSYS2 terminal:
pacman -S mingw-w64-i686-gcc

# Install LLVM/clang (for fa-python-binary-patcher)
winget install LLVM.LLVM
```
