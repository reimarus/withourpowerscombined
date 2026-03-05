"""WOPC patcher — orchestrates building the patched game executable."""

import logging
import shutil
import subprocess
import sys
from pathlib import Path

from launcher import config
from launcher.manifest import PatchManifest, apply_exclusions
from launcher.toolchain import Toolchain

logger = logging.getLogger("wopc.patcher")


class PatchBuildError(Exception):
    """Raised when the patch build fails."""


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

    # Copy asm.h (root-level header used by hooks)
    asm_h = patches_src / "asm.h"
    if asm_h.is_file():
        shutil.copy2(asm_h, staging_dir / "asm.h")

    # Create build output directory
    (staging_dir / "build").mkdir(exist_ok=True)


def _copy_base_exe(staging_dir: Path) -> Path:
    """Copy the stock SCFA exe to the staging directory as ForgedAlliance_base.exe.

    Returns:
        Path to the copied base exe.

    Raises:
        PatchBuildError: If the source exe doesn't exist.
    """
    src_exe = config.SCFA_BIN / "SupremeCommander.exe"
    dst_exe = staging_dir / "ForgedAlliance_base.exe"

    if not src_exe.is_file():
        raise PatchBuildError(
            f"Stock SCFA executable not found at {src_exe}. "
            f"Check your SCFA_STEAM path: {config.SCFA_STEAM}"
        )

    # Always copy fresh to ensure correct version
    shutil.copy2(src_exe, dst_exe)
    logger.info("  Copied base exe from %s", src_exe)
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

    cmd = [
        sys.executable,
        str(patcher_main),
        str(staging_dir),
        str(toolchain.clangpp),
        str(toolchain.ld),
        str(toolchain.gpp),
    ]

    logger.info("  Running patcher: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for compilation
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
