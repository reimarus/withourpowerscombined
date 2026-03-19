"""WOPC deploy - creates the WOPC game directory and copies/symlinks content."""

import logging
import shutil
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


def _download_file(
    url: str, dst: Path, *, progress_cb: Callable[[int, int], None] | None = None
) -> bool:
    """Download a file from *url* to *dst* with optional progress callback.

    Returns True on success, False on failure.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    try:
        logger.info("  downloading %s ...", dst.name)
        req = urllib.request.urlopen(url)
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
                        logger.info("  %s: %d%% (%.1f / %.1f MB)", dst.name, pct, mb_done, mb_total)
                        if progress_cb:
                            progress_cb(downloaded, total)

        tmp.replace(dst)
        size_mb = dst.stat().st_size / 1e6
        logger.info("  saved %s (%.1f MB)", dst.name, size_mb)
        return True
    except (OSError, urllib.error.URLError) as exc:
        logger.warning("  WARNING: download failed for %s: %s", dst.name, exc)
        if tmp.exists():
            tmp.unlink()
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
        dst_subdir = info["dst"]
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
            _download_and_extract(info["url"], dst_dir)
        else:
            dst_file = dst_dir / name
            if dst_file.exists():
                logger.info("  %s already exists, skipping", name)
                continue
            _download_file(info["url"], dst_file)


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
    """Build ``content_icons.scd`` containing unit icons for all content packs.

    SCFA looks for unit icons at ``/textures/ui/{faction}/icons/units/{id}_icon.dds``
    with a fallback to ``/textures/ui/common/icons/units/{id}_icon.dds``.  Content
    pack SCDs (like TotalMayhem.scd) don't include these icon textures — LOUD stores
    them separately in its own ``textures.scd``.

    This function:
    1. Scans all extracted content-pack mods for unit IDs.
    2. Extracts matching icon DDS files from LOUD's ``textures.scd``.
    3. Packs them into ``WOPC/gamedata/content_icons.scd``.

    If LOUD is not installed, downloads a pre-built SCD from GitHub.
    """
    dst = config.WOPC_GAMEDATA / config.CONTENT_ICONS_SCD
    unit_ids = _collect_content_unit_ids()
    if not unit_ids:
        logger.info("  no content pack units found, skipping icon extraction")
        return

    if config.LOUD_TEXTURES_SCD.exists():
        logger.info(
            "  building %s from LOUD textures.scd (%d unit IDs)",
            config.CONTENT_ICONS_SCD,
            len(unit_ids),
        )
        _build_icons_from_loud(dst, unit_ids)
    elif not dst.exists():
        logger.info("  LOUD not installed, downloading %s", config.CONTENT_ICONS_SCD)
        _download_file(config.CONTENT_ICONS_URL, dst)


def _build_icons_from_loud(dst: Path, unit_ids: set[str]) -> None:
    """Extract matching unit icons from LOUD's textures.scd into a new SCD."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    extracted = 0
    try:
        with zipfile.ZipFile(config.LOUD_TEXTURES_SCD, "r") as src_zf:
            # Index icon entries by lowercase unit ID
            icon_map: dict[str, list[zipfile.ZipInfo]] = {}
            for info in src_zf.infolist():
                lower = info.filename.lower()
                if "/icons/units/" in lower and lower.endswith(".dds"):
                    # Extract unit ID from filename like "brmt1pd_icon.dds"
                    fname = lower.rsplit("/", 1)[-1]
                    uid = fname.replace("_icon.dds", "")
                    icon_map.setdefault(uid, []).append(info)

            with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as out_zf:
                for uid in sorted(unit_ids):
                    for info in icon_map.get(uid, []):
                        # Preserve original path (textures/ui/common/icons/units/...)
                        arcname = info.filename.lower()
                        out_zf.writestr(arcname, src_zf.read(info))
                        extracted += 1

        logger.info("  packed %d icon textures into %s", extracted, config.CONTENT_ICONS_SCD)
    except (zipfile.BadZipFile, OSError) as exc:
        logger.warning("  WARNING: could not build %s: %s", config.CONTENT_ICONS_SCD, exc)


def _acquire_content_packs() -> None:
    """Copy content packs from local LOUD install or download from GitHub.

    Also extracts mod directories from SCDs to WOPC/usermods/ so the
    engine's mount_mods() can discover and activate them.
    """
    config.WOPC_GAMEDATA.mkdir(parents=True, exist_ok=True)
    config.WOPC_SOUNDS.mkdir(parents=True, exist_ok=True)

    for scd_name, asset_info in config.CONTENT_PACK_ASSETS.items():
        scd_dst = config.WOPC_GAMEDATA / scd_name
        if not scd_dst.exists():
            # Try local LOUD install first
            local_scd = config.LOUD_GAMEDATA / scd_name
            if local_scd.exists():
                logger.info("  copying %s from LOUD install", scd_name)
                shutil.copy2(local_scd, scd_dst)
            else:
                _download_file(asset_info["url"], scd_dst)

        # Extract mods/ subtree so mount_mods() can find them
        if scd_dst.exists():
            _extract_mods_from_scd(scd_dst)

        for sound_name, sound_url in asset_info.get("sounds", {}).items():
            sound_dst = config.WOPC_SOUNDS / sound_name
            if not sound_dst.exists():
                local_sound = config.LOUD_SOUNDS / sound_name
                if local_sound.exists():
                    logger.info("  copying %s from LOUD install", sound_name)
                    shutil.copy2(local_sound, sound_dst)
                else:
                    _download_file(sound_url, sound_dst)

    # Clean up excluded mods from previous extractions (e.g. BlackopsACUs
    # was extracted before we added the exclusion list).
    for excluded in sorted(mods.EXCLUDED_SCD_MODS):
        excluded_path = config.WOPC_MODS / excluded
        if excluded_path.exists():
            shutil.rmtree(excluded_path)
            logger.info("  removed excluded mod: %s", excluded)


def run_setup(repo_init_dir: Path) -> None:
    """Create the WOPC game directory at C:\\ProgramData\\WOPC\\ and populate it.

    Args:
        repo_init_dir: path to the init/ directory in the repo (contains init_wopc.lua)
    """
    logger.info("\n=== WOPC Setup v%s ===\n", config.VERSION)
    logger.info("WOPC directory: %s", config.WOPC_ROOT)

    # Create directory structure
    for d in [config.WOPC_ROOT, config.WOPC_BIN, config.WOPC_GAMEDATA, config.WOPC_MODS]:
        d.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Copy exe + DLLs from Steam SCFA/bin/ ---
    # Prefer FAF-patched exe if available, fall back to stock
    patched_exe = config.PATCH_BUILD_DIR / "ForgedAlliance_exxt.exe"
    exe_dst = config.WOPC_BIN / config.GAME_EXE
    if patched_exe.is_file():
        logger.info("\n[1/6] Copying FAF-patched game binaries")
        # Always overwrite exe with latest patched version
        shutil.copy2(patched_exe, exe_dst)
        logger.info("  copied  %s (FAF-patched)", config.GAME_EXE)
    else:
        logger.info("\n[1/6] Copying game binaries from %s", config.SCFA_BIN)
        logger.info("  NOTE: Using stock exe. Run 'wopc patch' to build FAF-patched version.")

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
    logger.info("\n[2/6] Copying bundled bin files")
    if config.REPO_BUNDLED_BIN.exists():
        for f in config.REPO_BUNDLED_BIN.iterdir():
            if f.is_file():
                copy_file(f, config.WOPC_BIN / f.name)

    # Download strategic icons if not bundled and not already present
    icons_name = "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd"
    icons_dst = config.WOPC_BIN / icons_name
    if not icons_dst.exists():
        # Try LOUD first
        loud_icons = config.LOUD_ROOT / "bin" / icons_name
        if loud_icons.exists():
            shutil.copy2(loud_icons, icons_dst)
            logger.info("  copied %s from LOUD", icons_name)
        else:
            icons_info = config.CORE_CONTENT_ASSETS.get(icons_name)
            if icons_info:
                _download_file(icons_info["url"], icons_dst)

    # --- Step 3: Copy init files from repo ---
    logger.info("\n[3/6] Copying init files from repo")
    for fname in ["init_wopc.lua", "CommonDataPath.lua"]:
        src = repo_init_dir / fname
        dst = config.WOPC_BIN / fname
        if src.exists():
            # Always overwrite init files (they may have been updated in repo)
            shutil.copy2(src, dst)
            logger.info("  copied  %s", fname)
        else:
            logger.warning("  WARNING: missing %s in repo init/ directory", fname)

    # Generate wopc_paths.lua with the absolute SCFA path
    # (WOPC lives in ProgramData, not inside SCFA, so we need this)
    scfa_escaped = str(config.SCFA_STEAM).replace("\\", "\\\\")
    paths_lua = config.WOPC_BIN / "wopc_paths.lua"
    paths_lua.write_text(
        f'-- Auto-generated by WOPC setup -- do not edit\nSCFARoot = "{scfa_escaped}"\n'
    )
    logger.info("  generated wopc_paths.lua (SCFA = %s)", config.SCFA_STEAM)

    # --- Step 4: Copy bundled content ---
    logger.info("\n[4/6] Copying bundled content")

    # Gamedata: copy individual SCD files
    if config.REPO_BUNDLED_GAMEDATA.exists():
        for scd in sorted(config.REPO_BUNDLED_GAMEDATA.glob("*.scd")):
            copy_file(scd, config.WOPC_GAMEDATA / scd.name)
    else:
        logger.warning("  WARNING: Bundled gamedata not found at %s", config.REPO_BUNDLED_GAMEDATA)

    # Build faf_ui.scd
    # This merges FAF source files with vanilla lua.scd files that FAF
    # doesn't replace.  The real FAF distribution (.nx2 files) does the
    # same thing — our faf_ui.scd is the equivalent single-file package.
    faf_ui_src = config.REPO_FAF_UI
    faf_ui_dst = config.WOPC_GAMEDATA / config.FAF_UI_SCD
    if faf_ui_src.exists():
        logger.info("  building %s", config.FAF_UI_SCD)
        with zipfile.ZipFile(faf_ui_dst, "w", zipfile.ZIP_STORED) as zf:
            # 1. Add FAF source files (these take priority over vanilla).
            # Normalize arcnames to lowercase — FAF's import() lowercases all
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
                dir_path = faf_ui_src / target_dir
                if dir_path.exists():
                    for file_path in dir_path.rglob("*"):
                        if file_path.is_file():
                            rel = file_path.relative_to(faf_ui_src)
                            arcname = str(rel).replace("\\", "/").lower()
                            zf.write(file_path, arcname)

            # 2. Merge vanilla lua.scd files that FAF doesn't replace.
            # FAF's simInit.lua imports AI files (lua/AI/*) that exist in
            # vanilla lua.scd but not in FAF's source repo.  Without these,
            # the sim crashes on import errors.
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
                logger.info("  merged %d vanilla lua.scd files into %s", merged, config.FAF_UI_SCD)
            else:
                logger.warning("  WARNING: vanilla lua.scd not found at %s", vanilla_lua_scd)

            # 3. Add WOPC patches (override FAF + vanilla files where needed).
            # These are our own fixes and additions — quickstart.lua, uimain.lua
            # hook, StructureUnit fix, AI stubs, etc.  Written LAST so they
            # overwrite any FAF or vanilla duplicate with the same arcname.
            wopc_patches_src = config.REPO_WOPC_PATCHES
            if wopc_patches_src.exists():
                patched = 0
                for file_path in wopc_patches_src.rglob("*"):
                    if file_path.is_file() and file_path.name != ".gitkeep":
                        rel = file_path.relative_to(wopc_patches_src)
                        arcname = str(rel).replace("\\", "/").lower()
                        zf.write(file_path, arcname)
                        patched += 1
                logger.info("  added %d WOPC patch files into %s", patched, config.FAF_UI_SCD)
            else:
                logger.warning("  WARNING: WOPC patches not found at %s", wopc_patches_src)
    else:
        # Standalone mode: download pre-built faf_ui.scd from GitHub release
        logger.info("  FAF source not available — downloading pre-built %s", config.FAF_UI_SCD)
        if not faf_ui_dst.exists():
            _download_file(config.CORE_CONTENT_ASSETS["faf_ui.scd"]["url"], faf_ui_dst)

    # Patch SCDs with WOPC engine-level overrides.
    # The SCFA engine's C++ code loads files like uimain.lua using
    # first-added search order (earliest mount = highest priority),
    # which is the OPPOSITE of Lua's import() function.
    # Even though the files are now inside faf_ui.scd (step 3 above),
    # ZIP archives list entries in write order — the engine finds the
    # FIRST matching entry, which is FAF's original from step 1.
    # _patch_scd() replaces that first entry with our patched version.
    wopc_patches_src = config.REPO_WOPC_PATCHES
    if wopc_patches_src.exists():
        uimain_src = wopc_patches_src / "lua" / "ui" / "uimain.lua"
        if uimain_src.exists():
            # Patch faf_ui.scd — in FAF-only mode this is the first (and only)
            # SCD providing uimain.lua, so the engine C++ doscript finds it.
            if faf_ui_dst.exists():
                _patch_scd(faf_ui_dst, "lua/ui/uimain.lua", uimain_src)
                logger.info("  patched faf_ui.scd with WOPC uimain.lua")

            # Also patch LOUD's lua.scd if present — when LOUD content packs
            # are enabled, lua.scd is mounted before faf_ui.scd, so the engine
            # would find LOUD's uimain.lua first without this patch.
            lua_scd_path = config.WOPC_GAMEDATA / "lua.scd"
            if lua_scd_path.exists():
                _patch_scd(lua_scd_path, "lua/ui/uimain.lua", uimain_src)
                logger.info("  patched lua.scd with WOPC uimain.lua")

        # Patch any other files that the engine C++ loads via doscript
        # (first-added priority). These have bugs in FAF source that we fix.
        # Arcname must be lowercase to match our normalized SCD contents.
        structure_src = wopc_patches_src / "lua" / "sim" / "units" / "StructureUnit.lua"
        if structure_src.exists() and faf_ui_dst.exists():
            _patch_scd(faf_ui_dst, "lua/sim/units/structureunit.lua", structure_src)
            logger.info("  patched faf_ui.scd with fixed StructureUnit.lua")

    # --- Step 4b: Acquire content packs (LOUD mods) ---
    logger.info("\n[4b] Acquiring content packs")
    _acquire_content_packs()

    # --- Step 4c: Build unit icon SCD for content packs ---
    logger.info("\n[4c] Building content pack icons")
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
            _download_and_extract(maps_info["url"], config.WOPC_MAPS)

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
    logger.info("\n[5/6] Copying user mods")
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
    logger.info("\n[6/6] Setting up user maps")
    config.WOPC_USERMAPS.mkdir(parents=True, exist_ok=True)
    logger.info("  ensured empty usermaps/ exists")

    logger.info("\n=== Setup complete ===")
    logger.info("Game directory: %s", config.WOPC_ROOT)
    logger.info("Launch with:    wopc launch")
