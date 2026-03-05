"""WOPC patcher — orchestrates building the patched game executable."""

import ctypes
import logging
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from launcher import config
from launcher.manifest import PatchManifest, apply_exclusions
from launcher.toolchain import Toolchain

logger = logging.getLogger("wopc.patcher")


class PatchBuildError(Exception):
    """Raised when the patch build fails."""


def _short_path(path: Path) -> str:
    """Convert to 8.3 short path on Windows to avoid spaces in os.system() calls.

    The FAF patcher uses ``os.system()`` which passes commands through
    ``cmd.exe``.  Paths containing spaces (e.g. ``C:\\Program Files\\...``)
    break because they are interpolated unquoted into f-strings.  Short
    path names (e.g. ``PROGRA~1``) side-step the limitation entirely.

    Falls back to the original string if short names are unavailable or
    if the path doesn't contain spaces.
    """
    path_str = str(path)
    if " " not in path_str:
        return path_str

    try:
        buf_size = ctypes.windll.kernel32.GetShortPathNameW(path_str, None, 0)  # type: ignore[union-attr]
        if buf_size == 0:
            return path_str
        buf = ctypes.create_unicode_buffer(buf_size)
        ctypes.windll.kernel32.GetShortPathNameW(path_str, buf, buf_size)  # type: ignore[union-attr]
        return buf.value
    except (AttributeError, OSError):
        return path_str


def _prepare_staging(staging_dir: Path, patches_src: Path, clean: bool = False) -> None:
    """Copy patch sources to the staging directory.

    Args:
        staging_dir: Target staging directory (patches/build/staging/).
        patches_src: Source directory (vendor/FA-Binary-Patches/).
        clean: If True, delete and recreate staging from scratch.
    """
    if clean and staging_dir.exists():
        logger.info("  Cleaning staging directory...")
        shutil.rmtree(staging_dir)

    if staging_dir.exists():
        logger.info("  Staging directory already exists, reusing")
        return

    staging_dir.mkdir(parents=True, exist_ok=True)

    # Copy the directories the patcher expects
    for subdir in ("include", "hooks", "section"):
        src = patches_src / subdir
        dst = staging_dir / subdir
        if src.is_dir():
            shutil.copytree(src, dst)
            logger.info("  Copied %s/ (%d files)", subdir, sum(1 for _ in dst.rglob("*")))

    # Copy SigPatches.txt
    sig = patches_src / "SigPatches.txt"
    if sig.is_file():
        shutil.copy2(sig, staging_dir / "SigPatches.txt")
        logger.info("  Copied SigPatches.txt")

    # Copy root-level source files expected by includes
    for root_file in ("asm.h", "workflow.cpp"):
        src_file = patches_src / root_file
        if src_file.is_file():
            shutil.copy2(src_file, staging_dir / root_file)
            logger.info("  Copied %s", root_file)

    # Create build output directory
    (staging_dir / "build").mkdir(exist_ok=True)

    # Apply MinGW Clang compatibility fixups to staging copies.
    # FAF upstream targets MSVC-hosted Clang where <cstddef> (NULL, offsetof)
    # is implicitly available.  MinGW Clang needs an explicit include.
    _apply_mingw_compat(staging_dir)


def _apply_mingw_compat(staging_dir: Path) -> None:
    """Patch staging headers for MinGW-targeted Clang compatibility.

    FAF patches are developed against MSVC-hosted Clang where standard
    macros like ``NULL`` and ``offsetof`` are implicitly available.
    MinGW Clang requires an explicit ``#include <cstddef>`` for these.

    Modifies files **in-place** in the staging copy (never the submodule).
    """
    lua_h = staging_dir / "include" / "lua" / "lua.h"
    if not lua_h.is_file():
        return

    content = lua_h.read_text(encoding="utf-8")
    shim = (
        "// WOPC MinGW compat: provide NULL and offsetof for non-MSVC targets\n#include <cstddef>\n"
    )

    # Insert after the first #pragma once (if present), otherwise at the top
    if "#pragma once" in content:
        content = content.replace("#pragma once", "#pragma once\n" + shim, 1)
    else:
        content = shim + content

    lua_h.write_text(content, encoding="utf-8")
    logger.info("  Applied MinGW compatibility shim to include/lua/lua.h")


def _download_faf_base_exe(cache_path: Path) -> Path:
    """Download FAF's base exe if not already cached.

    FAF binary patches use hardcoded addresses for a specific base exe
    distributed by FAF.  The Steam SupremeCommander.exe has different code
    layout and cannot be used.

    Returns:
        Path to the cached FAF base exe.

    Raises:
        PatchBuildError: If the download fails.
    """
    if cache_path.is_file():
        logger.info("  Using cached FAF base exe: %s", cache_path)
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    url = config.FAF_BASE_EXE_URL
    logger.info("  Downloading FAF base exe from %s ...", url)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WOPC-Patcher/1.0"})
        with urllib.request.urlopen(req) as resp, cache_path.open("wb") as f:
            shutil.copyfileobj(resp, f)
    except (urllib.error.URLError, OSError) as exc:
        raise PatchBuildError(
            f"Failed to download FAF base exe from {url}: {exc}\n"
            "Check your internet connection, or manually place "
            f"ForgedAlliance_base.exe at {cache_path}"
        ) from exc

    logger.info("  Downloaded %s (%d bytes)", cache_path.name, cache_path.stat().st_size)
    return cache_path


def _copy_base_exe(staging_dir: Path) -> Path:
    """Copy the FAF base exe to the staging directory as ForgedAlliance_base.exe.

    Downloads from FAF's content server on first use (cached for future builds).

    Returns:
        Path to the copied base exe.

    Raises:
        PatchBuildError: If the download or copy fails.
    """
    src_exe = _download_faf_base_exe(config.FAF_BASE_EXE_CACHE)
    dst_exe = staging_dir / "ForgedAlliance_base.exe"

    shutil.copy2(src_exe, dst_exe)
    logger.info("  Copied base exe to staging")
    return dst_exe


def _run_patcher(
    staging_dir: Path,
    patcher_dir: Path,
    toolchain: Toolchain,
) -> Path:
    """Invoke fa-python-binary-patcher on the staging directory.

    Args:
        staging_dir: Directory with prepared patch sources + base exe.
        patcher_dir: Path to vendor/fa-python-binary-patcher/.
        toolchain: Validated build toolchain paths.

    Returns:
        Path to the output patched exe.

    Raises:
        PatchBuildError: If the patcher process fails.
    """
    patcher_main = patcher_dir / "main.py"
    if not patcher_main.is_file():
        raise PatchBuildError(
            f"Patcher not found at {patcher_main}. "
            f"Did you initialize submodules? Run: git submodule update --init"
        )

    # The FAF patcher uses os.system() which can't handle spaces in paths.
    # Convert toolchain paths to 8.3 short names to avoid this limitation.
    cmd = [
        sys.executable,
        str(patcher_main),
        str(staging_dir),
        _short_path(toolchain.clangpp),
        _short_path(toolchain.ld),
        _short_path(toolchain.gpp),
    ]

    logger.info("  Running patcher: %s", " ".join(cmd))

    # The FAF patcher invokes compilers via os.system() which spawns
    # subprocesses (cc1plus.exe, as.exe, etc.) that need the toolchain's
    # DLLs on PATH.  Ensure the toolchain bin directories are available.
    env = os.environ.copy()
    toolchain_dirs = {str(p.parent) for p in (toolchain.clangpp, toolchain.gpp, toolchain.ld)}
    env["PATH"] = os.pathsep.join(toolchain_dirs) + os.pathsep + env.get("PATH", "")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for compilation
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise PatchBuildError("Patcher timed out after 10 minutes") from exc

    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            logger.info("  [patcher] %s", line)
    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            logger.warning("  [patcher] %s", line)

    if result.returncode != 0:
        raise PatchBuildError(
            f"Patcher failed with exit code {result.returncode}.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    output_exe = staging_dir / "ForgedAlliance_exxt.exe"
    if not output_exe.is_file():
        raise PatchBuildError(
            "Patcher completed but output exe not found at "
            f"{output_exe}. Check patcher output above."
        )

    return output_exe


def build_patches(
    toolchain: Toolchain,
    manifest: PatchManifest,
    clean: bool = False,
) -> Path:
    """Build the patched SCFA executable.

    This is the main entry point for the patch build process:
      1. Prepare staging directory from FA-Binary-Patches submodule
      2. Apply exclusions from the manifest
      3. Copy the stock exe as the base
      4. Run the patcher
      5. Copy the output to the build directory

    Args:
        toolchain: Validated build toolchain.
        manifest: Loaded patch manifest with exclusions.
        clean: Force rebuild from scratch.

    Returns:
        Path to the final patched exe (in patches/build/).

    Raises:
        PatchBuildError: If any step fails.
    """
    patches_src = config.FA_PATCHES_DIR
    patcher_dir = config.FA_PATCHER_DIR
    build_dir = config.PATCH_BUILD_DIR
    staging_dir = build_dir / "staging"

    # Check if output already exists (skip build unless --clean)
    output_path = build_dir / "ForgedAlliance_exxt.exe"
    if output_path.is_file() and not clean:
        logger.info("Patched exe already exists: %s", output_path)
        logger.info("Use --clean to force rebuild.")
        return output_path

    if not patches_src.is_dir():
        raise PatchBuildError(
            f"FA-Binary-Patches not found at {patches_src}. "
            f"Did you initialize submodules? Run: git submodule update --init"
        )

    logger.info("\n=== Building patched exe ===\n")

    # Step 1: Prepare staging
    logger.info("[1/4] Preparing staging directory...")
    _prepare_staging(staging_dir, patches_src, clean=clean)

    # Step 2: Apply exclusions
    logger.info("[2/4] Applying patch exclusions...")
    removed = apply_exclusions(staging_dir, manifest)
    logger.info("  Removed %d excluded file(s)", removed)

    # Step 3: Copy base exe
    logger.info("[3/4] Copying base executable...")
    _copy_base_exe(staging_dir)

    # Step 4: Run patcher
    logger.info("[4/4] Running binary patcher...")
    patched_exe = _run_patcher(staging_dir, patcher_dir, toolchain)

    # Copy output to build dir (outside staging)
    build_dir.mkdir(parents=True, exist_ok=True)
    final_path = build_dir / "ForgedAlliance_exxt.exe"
    shutil.copy2(patched_exe, final_path)
    logger.info("\nPatched exe: %s", final_path)
    logger.info("Run 'wopc setup' to deploy it to your WOPC directory.")

    return final_path
