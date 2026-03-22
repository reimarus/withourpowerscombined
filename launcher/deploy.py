"""WOPC deploy - creates the WOPC game directory and copies/symlinks content."""

import logging
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from launcher import config, mods

logger = logging.getLogger("wopc.deploy")


def _patch_scd(scd_path: Path, arcname: str, replacement: Path) -> bool:
    """Replace a single file inside an SCD (ZIP) archive.

    Rewrites the archive to a temp file, then atomically replaces the original.
    Returns True on success, False if the SCD couldn't be patched.
    """
    tmp_path = scd_path.with_suffix(".tmp")
    try:
        with (
            zipfile.ZipFile(scd_path, "r") as zr,
            zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zw,
        ):
            for info in zr.infolist():
                if info.filename == arcname:
                    zw.write(replacement, arcname)
                else:
                    zw.writestr(info, zr.read(info))
        tmp_path.replace(scd_path)
    except (zipfile.BadZipFile, OSError) as exc:
        logger.warning("  WARNING: Could not patch %s: %s", scd_path.name, exc)
        if tmp_path.exists():
            tmp_path.unlink()
        return False
    return True


def link_or_copy(src: Path, dst: Path) -> None:
    """Create a symlink, falling back to copy if symlinks need admin."""
    if dst.exists() or dst.is_symlink():
        return  # already exists
    try:
        if src.is_dir():
            dst.symlink_to(src, target_is_directory=True)
        else:
            dst.symlink_to(src)
        logger.info("  symlink %s -> %s", dst.name, src)
    except OSError:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        logger.info("  copied  %s", dst.name)


def copy_file(src: Path, dst: Path) -> None:
    """Copy a single file, skip if already exists."""
    if dst.exists():
        return
    shutil.copy2(src, dst)
    logger.info("  copied  %s", dst.name)


_DL_MAX_RETRIES = 3
_DL_TIMEOUT = 30  # seconds


def _download_file(
    url: str,
    dst: Path,
    *,
    progress_cb: Callable[[int, int], None] | None = None,
    max_retries: int = _DL_MAX_RETRIES,
    timeout: int = _DL_TIMEOUT,
) -> bool:
    """Download a file from *url* to *dst* with retry and progress.

    Retries up to *max_retries* times with exponential backoff (1s, 2s, 4s).
    Returns True on success, False on failure.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("  downloading %s (attempt %d/%d) ...", dst.name, attempt, max_retries)
            req = urllib.request.urlopen(url, timeout=timeout)
            total = int(req.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 256 * 1024  # 256 KB chunks
            last_pct = -1

            with tmp.open("wb") as f:
                while True:
                    chunk = req.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded * 100 / total)
                        if pct >= last_pct + 5:  # Report every 5%
                            last_pct = pct
                            mb_done = downloaded / 1e6
                            mb_total = total / 1e6
                            logger.info(
                                "  %s: %d%% (%.1f / %.1f MB)",
                                dst.name,
                                pct,
                                mb_done,
                                mb_total,
                            )
                            if progress_cb:
                                progress_cb(downloaded, total)

            tmp.replace(dst)
            size_mb = dst.stat().st_size / 1e6
            logger.info("  saved %s (%.1f MB)", dst.name, size_mb)
            return True
        except (OSError, urllib.error.URLError) as exc:
            logger.warning(
                "  WARNING: download attempt %d/%d failed for %s: %s",
                attempt,
                max_retries,
                dst.name,
                exc,
            )
            if tmp.exists():
                tmp.unlink()
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s
                logger.info("  retrying in %ds ...", backoff)
                time.sleep(backoff)

    logger.error(
        "  FAILED: could not download %s after %d attempts from %s",
        dst.name,
        max_retries,
        url,
    )
    return False


def _download_and_extract(url: str, dst_dir: Path) -> bool:
    """Download a zip file and extract it to dst_dir. Returns True on success."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    tmp_zip = dst_dir / "_download.zip"
    if not _download_file(url, tmp_zip):
        return False
    try:
        logger.info("  extracting to %s ...", dst_dir)
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(dst_dir)
        logger.info("  extracted %d files", len(zipfile.ZipFile(tmp_zip).namelist()))
        return True
    except (zipfile.BadZipFile, OSError) as exc:
        logger.warning("  WARNING: extraction failed: %s", exc)
        return False
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink()


def _acquire_core_content() -> None:
    """Download core content assets from GitHub Releases when running standalone.

    This is the download-first path for frozen exe / no-repo installs.
    Iterates CORE_CONTENT_ASSETS and downloads anything missing.
    """
    for name, info in config.CORE_CONTENT_ASSETS.items():
        dst_subdir = str(info["dst"])
        dst_dir = config.WOPC_ROOT / dst_subdir
        dst_dir.mkdir(parents=True, exist_ok=True)

        if info.get("extract"):
            # For zip archives, check if extraction target has content
            # (we can't easily check if the specific zip was already extracted,
            # so we check if the dst_dir has any subdirectories)
            if any(dst_dir.iterdir()):
                logger.info("  %s already populated, skipping %s", dst_subdir, name)
                continue
            logger.info("  downloading and extracting %s", name)
            _download_and_extract(str(info["url"]), dst_dir)
        else:
            dst_file = dst_dir / name
            if dst_file.exists():
                logger.info("  %s already exists, skipping", name)
                continue
            _download_file(str(info["url"]), dst_file)


def _extract_mods_from_scd(scd_path: Path) -> list[str]:
    """Extract mod directories from an SCD to WOPC/mods/.

    Delegates to ``mods.extract_mods_from_scd()`` — the canonical
    implementation lives in the consolidated mods module.
    """
    return mods.extract_mods_from_scd(scd_path)


def _collect_content_unit_ids() -> set[str]:
    """Scan all extracted content-pack mods for unit IDs.

    Returns lowercase unit IDs found in ``WOPC_MODS/*/units/*/`` directories.
    """
    unit_ids: set[str] = set()
    if not config.WOPC_MODS.exists():
        return unit_ids
    for mod_dir in config.WOPC_MODS.iterdir():
        units_dir = mod_dir / "units"
        if units_dir.is_dir():
            for unit_dir in units_dir.iterdir():
                if unit_dir.is_dir():
                    unit_ids.add(unit_dir.name.lower())
    return unit_ids


def _build_content_icons_scd() -> None:
    """Download ``content_icons.scd`` containing unit icons for content packs.

    SCFA looks for unit icons at ``/textures/ui/{faction}/icons/units/{id}_icon.dds``
    with a fallback to ``/textures/ui/common/icons/units/{id}_icon.dds``.  Content
    pack SCDs (like TotalMayhem.scd) don't include these icon textures — they are
    distributed separately via GitHub releases.
    """
    dst = config.WOPC_GAMEDATA / config.CONTENT_ICONS_SCD
    unit_ids = _collect_content_unit_ids()
    if not unit_ids:
        logger.info("  no content pack units found, skipping icon download")
        return

    if not dst.exists():
        logger.info("  downloading %s", config.CONTENT_ICONS_SCD)
        _download_file(config.CONTENT_ICONS_URL, dst)


def _acquire_content_packs() -> None:
    """Download content packs from GitHub releases.

    Also extracts mod directories from SCDs to WOPC/mods/ so the
    engine's mount_mods() can discover and activate them.
    """
    config.WOPC_GAMEDATA.mkdir(parents=True, exist_ok=True)
    config.WOPC_SOUNDS.mkdir(parents=True, exist_ok=True)

    for scd_name, asset_info in config.CONTENT_PACK_ASSETS.items():
        scd_dst = config.WOPC_GAMEDATA / scd_name
        if not scd_dst.exists():
            _download_file(asset_info["url"], scd_dst)

        # Extract mods/ subtree so mount_mods() can find them
        if scd_dst.exists():
            _extract_mods_from_scd(scd_dst)

        for sound_name, sound_url in asset_info.get("sounds", {}).items():
            sound_dst = config.WOPC_SOUNDS / sound_name
            if not sound_dst.exists():
                _download_file(sound_url, sound_dst)

    # Clean up excluded mods from previous extractions (e.g. BlackopsACUs
    # was extracted before we added the exclusion list).
    for excluded in sorted(mods.EXCLUDED_SCD_MODS):
        excluded_path = config.WOPC_MODS / excluded
        if excluded_path.exists():
            shutil.rmtree(excluded_path)
            logger.info("  removed excluded mod: %s", excluded)


def run_setup(
    repo_init_dir: Path,
    *,
    progress_cb: Callable[[str, int, int], None] | None = None,
) -> None:
    """Create the WOPC game directory at C:\\ProgramData\\WOPC\\ and populate it.

    Args:
        repo_init_dir: path to the init/ directory in the repo (contains init_wopc.lua)
        progress_cb: optional ``(message, step, total_steps)`` callback for GUI updates
    """

    def _report(msg: str, step: int) -> None:
        logger.info(msg)
        if progress_cb:
            progress_cb(msg, step, 6)

    logger.info("\n=== WOPC Setup v%s ===\n", config.VERSION)
    logger.info("WOPC directory: %s", config.WOPC_ROOT)

    # Create directory structure
    for d in [config.WOPC_ROOT, config.WOPC_BIN, config.WOPC_GAMEDATA, config.WOPC_MODS]:
        d.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Copy exe + DLLs from Steam SCFA/bin/ ---
    # Prefer patched exe if available, fall back to stock
    patched_exe = config.PATCH_BUILD_DIR / "ForgedAlliance_exxt.exe"
    exe_dst = config.WOPC_BIN / config.GAME_EXE
    if patched_exe.is_file():
        _report("[1/6] Copying patched game binaries", 1)
        # Always overwrite exe with latest patched version
        shutil.copy2(patched_exe, exe_dst)
        logger.info("  copied  %s (patched)", config.GAME_EXE)
    else:
        _report("[1/6] Copying game binaries from SCFA", 1)
        logger.info("  NOTE: Using stock exe. Run 'wopc patch' to build patched version.")

    missing = []
    for fname in config.BIN_FILES:
        src = config.SCFA_BIN / fname
        dst = config.WOPC_BIN / fname
        # Skip exe if we already copied the patched version
        if fname == config.GAME_EXE and dst.exists():
            continue
        if src.exists():
            copy_file(src, dst)
        else:
            missing.append(fname)
    if missing:
        logger.warning("  WARNING: missing files: %s", ", ".join(missing))

    # --- Step 2: Copy bundled bin files (icons SCD, etc) ---
    _report("[2/6] Copying bundled bin files", 2)
    if config.REPO_BUNDLED_BIN.exists():
        for f in config.REPO_BUNDLED_BIN.iterdir():
            if f.is_file():
                copy_file(f, config.WOPC_BIN / f.name)

    # Download strategic icons if not bundled and not already present
    icons_name = "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd"
    icons_dst = config.WOPC_BIN / icons_name
    if not icons_dst.exists():
        icons_info = config.CORE_CONTENT_ASSETS.get(icons_name)
        if icons_info:
            _download_file(str(icons_info["url"]), icons_dst)

    # --- Step 3: Copy init files from repo ---
    _report("[3/6] Copying init files", 3)
    for fname in ["init_wopc.lua", "CommonDataPath.lua"]:
        src = repo_init_dir / fname
        dst = config.WOPC_BIN / fname
        if src.exists():
            # Always overwrite init files (they may have been updated in repo)
            shutil.copy2(src, dst)
            logger.info("  copied  %s", fname)
        else:
            logger.warning("  WARNING: missing %s in repo init/ directory", fname)

    # Generate wopc_paths.lua — SCFA root is the parent of the WOPC directory.
    # Uses a relative path so the installation is fully relocatable.
    paths_lua = config.WOPC_BIN / "wopc_paths.lua"
    paths_lua.write_text(
        "-- Auto-generated by WOPC setup -- do not edit\n"
        "-- SCFA root is the parent of the WOPC directory\n"
        'SCFARoot = WOPCRoot .. "\\\\.."\n'
    )
    logger.info("  generated wopc_paths.lua (relative to WOPC)")

    # --- Step 4: Copy bundled content ---
    _report("[4/6] Downloading and building game content", 4)

    # Gamedata: copy individual SCD files
    if config.REPO_BUNDLED_GAMEDATA.exists():
        for scd in sorted(config.REPO_BUNDLED_GAMEDATA.glob("*.scd")):
            copy_file(scd, config.WOPC_GAMEDATA / scd.name)
    else:
        logger.warning("  WARNING: Bundled gamedata not found at %s", config.REPO_BUNDLED_GAMEDATA)

    # Build wopc_core.scd
    # Merges game logic source, vanilla lua.scd gap-fills, and WOPC patches
    # into a single SCD that the engine mounts before vanilla content.
    wopc_core_src = config.REPO_WOPC_CORE_SRC
    wopc_core_dst = config.WOPC_GAMEDATA / config.WOPC_CORE_SCD
    if wopc_core_src.exists():
        logger.info("  building %s", config.WOPC_CORE_SCD)
        with zipfile.ZipFile(wopc_core_dst, "w", zipfile.ZIP_STORED) as zf:
            # 1. Add game logic source files (these take priority over vanilla).
            # Normalize arcnames to lowercase — the engine's import() lowercases all
            # paths before lookup (import.lua line 116), but ZIP lookups are
            # case-sensitive.  Without this, 833/1264 files are unreachable.
            for target_dir in [
                "etc",
                "lua",
                "modules",
                "ui",
                "loc",
                "units",
                "projectiles",
                "effects",
                "env",
                "meshes",
                "schook",
                "textures",
            ]:
                dir_path = wopc_core_src / target_dir
                if dir_path.exists():
                    for file_path in dir_path.rglob("*"):
                        if file_path.is_file():
                            rel = file_path.relative_to(wopc_core_src)
                            arcname = str(rel).replace("\\", "/").lower()
                            zf.write(file_path, arcname)

            # 2. Merge vanilla lua.scd gap-fills.
            # simInit.lua imports AI files (lua/AI/*) that exist in vanilla
            # lua.scd but not in our source repo.  Without these, the sim
            # crashes on import errors.
            # Arcnames are lowercased to match step 1 normalization.
            vanilla_lua_scd = config.SCFA_STEAM / "gamedata" / "lua.scd"
            if vanilla_lua_scd.exists():
                existing = {name.replace("\\", "/").lower() for name in zf.namelist()}
                merged = 0
                with zipfile.ZipFile(vanilla_lua_scd, "r") as vanilla_zf:
                    for info in vanilla_zf.infolist():
                        if info.is_dir():
                            continue
                        normalized = info.filename.replace("\\", "/").lower()
                        if normalized not in existing:
                            zf.writestr(normalized, vanilla_zf.read(info))
                            merged += 1
                logger.info(
                    "  merged %d vanilla lua.scd files into %s", merged, config.WOPC_CORE_SCD
                )
            else:
                logger.warning("  WARNING: vanilla lua.scd not found at %s", vanilla_lua_scd)

            # 3. Add WOPC patches (override base + vanilla files where needed).
            # These are our own fixes and additions — quickstart.lua, uimain.lua
            # hook, StructureUnit fix, AI stubs, etc.  Written LAST so they
            # overwrite any base or vanilla duplicate with the same arcname.
            wopc_patches_src = config.REPO_WOPC_PATCHES
            if wopc_patches_src.exists():
                patched = 0
                for file_path in wopc_patches_src.rglob("*"):
                    if file_path.is_file() and file_path.name != ".gitkeep":
                        rel = file_path.relative_to(wopc_patches_src)
                        arcname = str(rel).replace("\\", "/").lower()
                        zf.write(file_path, arcname)
                        patched += 1
                logger.info("  added %d WOPC patch files into %s", patched, config.WOPC_CORE_SCD)
            else:
                logger.warning("  WARNING: WOPC patches not found at %s", wopc_patches_src)
    else:
        # Standalone mode: no source tree available — migrate or download
        if not wopc_core_dst.exists():
            # Try migrating from the old ProgramData location first
            old_gamedata = Path(r"C:\ProgramData\WOPC\gamedata")
            old_scd = old_gamedata / "faf_ui.scd"  # pre-rename name
            if not old_scd.exists():
                old_scd = old_gamedata / config.WOPC_CORE_SCD
            if old_scd.exists():
                logger.info("  migrating %s from old install", config.WOPC_CORE_SCD)
                shutil.copy2(old_scd, wopc_core_dst)
            else:
                # Download pre-built wopc_core.scd.zip from GitHub release
                logger.info("  downloading %s", config.WOPC_CORE_SCD)
                asset_info = config.CORE_CONTENT_ASSETS["wopc_core.scd.zip"]
                zip_dst = config.WOPC_GAMEDATA / "wopc_core.scd.zip"
                if not _download_file(str(asset_info["url"]), zip_dst):
                    raise RuntimeError(
                        f"Failed to download {config.WOPC_CORE_SCD} — "
                        "check your internet connection and try again."
                    )
                with zipfile.ZipFile(zip_dst, "r") as zf:
                    zf.extractall(config.WOPC_GAMEDATA)
                zip_dst.unlink()
                logger.info("  extracted %s", config.WOPC_CORE_SCD)

    # Patch SCDs with WOPC engine-level overrides.
    # The SCFA engine's C++ code loads files like uimain.lua using
    # first-added search order (earliest mount = highest priority),
    # which is the OPPOSITE of Lua's import() function.
    # Even though the files are now inside wopc_core.scd (step above),
    # ZIP archives list entries in write order — the engine finds the
    # FIRST matching entry, which is the original from step 1.
    # _patch_scd() replaces that first entry with our patched version.
    wopc_patches_src = config.REPO_WOPC_PATCHES
    if wopc_patches_src.exists():
        uimain_src = wopc_patches_src / "lua" / "ui" / "uimain.lua"
        if uimain_src.exists() and wopc_core_dst.exists():
            _patch_scd(wopc_core_dst, "lua/ui/uimain.lua", uimain_src)
            logger.info("  patched wopc_core.scd with WOPC uimain.lua")

        # Patch any other files that the engine C++ loads via doscript
        # (first-added priority). These have bugs we fix.
        # Arcname must be lowercase to match our normalized SCD contents.
        structure_src = wopc_patches_src / "lua" / "sim" / "units" / "StructureUnit.lua"
        if structure_src.exists() and wopc_core_dst.exists():
            _patch_scd(wopc_core_dst, "lua/sim/units/structureunit.lua", structure_src)
            logger.info("  patched wopc_core.scd with fixed StructureUnit.lua")

    # --- Step 4b: Acquire content packs ---
    _report("[4/6] Downloading content packs", 4)
    _acquire_content_packs()

    # --- Step 4c: Build unit icon SCD for content packs ---
    _report("[4/6] Building content pack icons", 4)
    _build_content_icons_scd()

    # Maps, sounds: copy entire directories
    config.WOPC_MAPS.mkdir(parents=True, exist_ok=True)
    if config.REPO_BUNDLED_MAPS.exists():
        shutil.copytree(config.REPO_BUNDLED_MAPS, config.WOPC_MAPS, dirs_exist_ok=True)
    elif not any(config.WOPC_MAPS.iterdir()):
        # No bundled maps and maps dir is empty — download from release
        maps_info = config.CORE_CONTENT_ASSETS.get("wopc-maps.zip")
        if maps_info:
            logger.info("  downloading curated map pack")
            _download_and_extract(str(maps_info["url"]), config.WOPC_MAPS)

    # Copy SCFA stock maps (from Steam installation)
    scfa_maps = config.SCFA_STEAM / "maps"
    if scfa_maps.exists():
        logger.info("  Copying SCFA stock maps from %s", scfa_maps)
        shutil.copytree(scfa_maps, config.WOPC_MAPS, dirs_exist_ok=True)
    else:
        logger.warning("  WARNING: SCFA maps directory not found at %s", scfa_maps)
    if config.REPO_BUNDLED_SOUNDS.exists():
        shutil.copytree(config.REPO_BUNDLED_SOUNDS, config.WOPC_SOUNDS, dirs_exist_ok=True)

    # --- Step 5: Copy usermods (not symlink - user may add/remove mods) ---
    _report("[5/6] Copying user mods", 5)
    if config.REPO_BUNDLED_USERMODS.exists() and not config.WOPC_USERMODS.exists():
        shutil.copytree(config.REPO_BUNDLED_USERMODS, config.WOPC_USERMODS)
        logger.info(
            "  copied usermods/ (%d files)", sum(1 for _ in config.WOPC_USERMODS.rglob("*"))
        )
    elif config.WOPC_USERMODS.exists():
        logger.info("  usermods/ already exists, skipping")
    else:
        config.WOPC_USERMODS.mkdir(parents=True, exist_ok=True)
        logger.info("  created empty usermods/")

    # --- Step 6: Setup user maps ---
    _report("[6/6] Setting up user maps", 6)
    config.WOPC_USERMAPS.mkdir(parents=True, exist_ok=True)
    logger.info("  ensured empty usermaps/ exists")

    logger.info("\n=== Setup complete ===")
    logger.info("Game directory: %s", config.WOPC_ROOT)
    logger.info("Launch with:    wopc launch")
