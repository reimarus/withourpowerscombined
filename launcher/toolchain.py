"""WOPC toolchain discovery — finds Clang, GCC, and LD for binary patch compilation."""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("wopc.toolchain")


class ToolchainError(Exception):
    """Raised when required compilers cannot be found or validated."""


@dataclass(frozen=True)
class Toolchain:
    """Paths to the C++ build tools needed for binary patching."""

    clangpp: Path
    gpp: Path
    ld: Path

    def __str__(self) -> str:
        return (
            f"Toolchain(\n"
            f"  clang++ = {self.clangpp}\n"
            f"  g++     = {self.gpp}\n"
            f"  ld      = {self.ld}\n"
            f")"
        )


# --- Well-known install locations on Windows ---

_MSYS2_MINGW32 = Path(r"C:\msys64\mingw32\bin")
_LLVM_DEFAULT = Path(r"C:\Program Files\LLVM\bin")

_SEARCH_PATHS: list[Path] = [
    # LLVM first for clang++: standalone LLVM targets MSVC (SEH exceptions),
    # which is what the binary patches expect.  MSYS2 Clang targets MinGW (DWARF)
    # and produces _Unwind_Resume references that break with -nostdlib.
    # LLVM's bin/ has no g++/ld, so those still come from MSYS2.
    _LLVM_DEFAULT,
    _MSYS2_MINGW32,
]


def _find_executable(name: str, env_var: str | None = None) -> Path | None:
    """Search for an executable by env var, well-known paths, then PATH.

    Args:
        name: Executable filename (e.g. "g++.exe").
        env_var: Optional environment variable override (e.g. "WOPC_GPP").

    Returns:
        Path to the executable, or None if not found.
    """
    # 1. Environment variable override
    if env_var:
        env_path = os.environ.get(env_var)
        if env_path:
            p = Path(env_path)
            if p.is_file():
                logger.debug("  %s found via $%s: %s", name, env_var, p)
                return p
            logger.warning("  $%s set to %s but file not found", env_var, p)

    # 2. Well-known install locations
    for search_dir in _SEARCH_PATHS:
        candidate = search_dir / name
        if candidate.is_file():
            logger.debug("  %s found at %s", name, candidate)
            return candidate

    # 3. System PATH
    which_result = shutil.which(name)
    if which_result:
        p = Path(which_result)
        logger.debug("  %s found on PATH: %s", name, p)
        return p

    return None


def _get_version(exe: Path) -> str:
    """Run --version and return the first line of output."""
    try:
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        first_line = (result.stdout or result.stderr).strip().split("\n")[0]
        return first_line
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"<error: {exc}>"


def find_toolchain() -> Toolchain:
    """Locate clang++, g++, and ld on the system.

    Search order for each tool:
      1. Environment variable (WOPC_CLANGPP, WOPC_GPP, WOPC_LD)
      2. MSYS2 mingw32 default location
      3. LLVM default location
      4. System PATH

    Returns:
        A Toolchain with validated paths.

    Raises:
        ToolchainError: If any required tool cannot be found.
    """
    logger.info("Searching for build toolchain...")

    clangpp = _find_executable("clang++.exe", env_var="WOPC_CLANGPP")
    gpp = _find_executable("g++.exe", env_var="WOPC_GPP")
    ld = _find_executable("ld.exe", env_var="WOPC_LD")

    missing = []
    if not clangpp:
        missing.append("clang++ (install LLVM: winget install LLVM.LLVM)")
    if not gpp:
        missing.append("g++ (install MSYS2: pacman -S mingw-w64-i686-gcc)")
    if not ld:
        missing.append("ld (comes with g++ / MSYS2 mingw-w64-i686-binutils)")

    if missing:
        raise ToolchainError(
            "Missing required build tools:\n  " + "\n  ".join(missing) + "\n\n"
            "See docs/patching.md for installation instructions."
        )

    # All found — validate by printing versions
    assert clangpp is not None  # for mypy
    assert gpp is not None
    assert ld is not None

    logger.info("  clang++: %s", clangpp)
    logger.info("    %s", _get_version(clangpp))
    logger.info("  g++:     %s", gpp)
    logger.info("    %s", _get_version(gpp))
    logger.info("  ld:      %s", ld)
    logger.info("    %s", _get_version(ld))

    return Toolchain(clangpp=clangpp, gpp=gpp, ld=ld)


def check_toolchain() -> bool:
    """Check if the toolchain is available without raising.

    Returns:
        True if all tools found, False otherwise.
    """
    try:
        find_toolchain()
        return True
    except ToolchainError:
        return False
