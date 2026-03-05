# Binary Patching Guide

WOPC integrates FAF (Forged Alliance Forever) C++ binary patches into the SCFA
game executable. These patches fix pathfinding, collisions, memory limits,
performance, and add new Lua API functions.

## Architecture

```
Python launcher (wopc patch)
    |
    v
fa-python-binary-patcher (vendor/)
    |
    +-- Clang (compiles .cxx files)
    +-- GCC/MinGW (compiles .cpp files, links)
    |
    v
ForgedAlliance_exxt.exe (patched output)
```

The stock `SupremeCommander.exe` from Steam is the input. The patcher compiles
C++ patch sources from `FA-Binary-Patches`, injects them into the executable,
and produces a patched version with an `.exxt` PE section.

## Toolchain Setup

You need two compilers. Both must target **32-bit x86** (i686).

### Option A: MSYS2 (Recommended)

```powershell
# Install MSYS2
winget install MSYS2.MSYS2

# Open MSYS2 MinGW32 shell and install GCC
pacman -S mingw-w64-i686-gcc mingw-w64-i686-binutils

# Install LLVM/Clang
winget install LLVM.LLVM
```

### Option B: Manual Install

- **GCC**: Download MinGW-w64 i686 from https://www.mingw-w64.org/
- **Clang**: Download from https://releases.llvm.org/

### Verify

```
wopc patch --check
```

This will search for `g++.exe`, `clang++.exe`, and `ld.exe` in:
1. Environment variables: `WOPC_CLANGPP`, `WOPC_GPP`, `WOPC_LD`
2. MSYS2 default: `C:\msys64\mingw32\bin\`
3. LLVM default: `C:\Program Files\LLVM\bin\`
4. System PATH

## Building Patches

```
# First time — initialize submodules
git submodule update --init

# Build the patched exe
wopc patch

# Force rebuild from scratch
wopc patch --clean

# See what would be built without building
wopc patch --dry-run
```

The patched exe is saved to `patches/build/ForgedAlliance_exxt.exe`.

## Deploying

After building, run setup to deploy the patched exe:

```
wopc setup
```

Setup automatically detects the patched exe and uses it instead of the stock
one. If no patched exe exists, it falls back to the stock SCFA executable.

## Patch Selection

The file `wopc_patches.toml` in the repo root controls which patches are
included. By default, all FAF patches are included except those explicitly
excluded:

```toml
[build]
strategy = "include_all"

[exclude]
hooks = ["gpg_net.cpp", "gpg_net.h"]
sections = ["gpg_net.cpp", "HashChecker.cpp"]
```

### Excluded Patches

| File | Reason |
|------|--------|
| `gpg_net.cpp` / `gpg_net.h` | FAF lobby networking protocol |
| `HashChecker.cpp` | FAF client hash verification |

### Key Patches Included

| Patch | What It Does |
|-------|-------------|
| `PathfindingTweaks.cpp` | Exposes pathfinding distance control to Lua |
| `FixCollisions.cpp` | Fixes projectile collision bugs |
| `HFix4GB.cpp` | Removes 2GB memory limit (Large Address Aware) |
| `CameraPerf.cpp` | Camera rendering optimization |
| `DesyncFix.cpp` | Multiplayer desync prevention |
| `TableFuncs.cxx` | Optimized Lua table functions |

## Troubleshooting

### "Missing required build tools"

Install the toolchain per the instructions above, or set environment variables:

```powershell
$env:WOPC_GPP = "C:\msys64\mingw32\bin\g++.exe"
$env:WOPC_LD = "C:\msys64\mingw32\bin\ld.exe"
$env:WOPC_CLANGPP = "C:\Program Files\LLVM\bin\clang++.exe"
```

### "Patcher failed with exit code 1"

Check the patcher output for compilation errors. Common causes:
- Wrong compiler architecture (must be 32-bit/i686, not x64)
- Missing headers (ensure submodules are initialized)
- Incompatible compiler version

### "Stock SCFA executable not found"

The patcher needs the original `SupremeCommander.exe` from Steam. Ensure
SCFA is installed and the `SCFA_STEAM` path is correct:

```
wopc status
```
