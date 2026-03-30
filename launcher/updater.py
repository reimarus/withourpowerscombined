"""WOPC Launcher self-update via GitHub Releases.

Checks for new launcher versions on startup (background thread), and
provides download + replace + restart when an update is available.

The update flow on Windows:
1. Download new exe to a temp file next to the running exe
2. Verify the download (size + PE header check)
3. Rename the running exe to ``*.old`` (Windows allows renaming a running exe)
4. Rename the temp file to the original name
5. Spawn a cmd restart script that logs every step to ``restart.log``
6. ``os._exit(0)`` — hard exit
7. On next startup, ``cleanup_old_exe()`` reads ``restart.log``, cleans
   up the ``.old`` file, and removes stale ``_MEI`` temp dirs
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from launcher import config

LOG = logging.getLogger("wopc.updater")

# Minimum acceptable exe size (10 MB).  Our launcher is ~30 MB; a truncated
# or corrupt download will be much smaller.
_MIN_EXE_SIZE = 10 * 1024 * 1024

# PE header magic bytes — every valid Windows exe starts with "MZ".
_PE_MAGIC = b"MZ"

# Firebase version manifest — primary source for update checks
_FIREBASE_VERSION_URL = f"{config.RELAY_URL}/launcher_version.json"

# GitHub API endpoint — fallback when Firebase is unavailable
_RELEASES_URL = "https://api.github.com/repos/reimarus/withourpowerscombined/releases"
_TAG_PREFIX = "launcher-v"
_CHECK_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# Version parsing
# ---------------------------------------------------------------------------


def _parse_version(tag: str) -> tuple[int, ...] | None:
    """Parse a version tag like ``launcher-v1.2.3`` into a comparable tuple."""
    if not tag.startswith(_TAG_PREFIX):
        return None
    ver_str = tag[len(_TAG_PREFIX) :]
    try:
        return tuple(int(x) for x in ver_str.split("."))
    except ValueError:
        return None


def _current_version_tuple() -> tuple[int, ...]:
    """Return the current launcher version as a comparable tuple."""
    # Strip any dev suffix
    ver = config.VERSION.split("-")[0]
    try:
        return tuple(int(x) for x in ver.split("."))
    except ValueError:
        return (0, 0, 0)


# ---------------------------------------------------------------------------
# Exe verification
# ---------------------------------------------------------------------------


class VerificationError(Exception):
    """Raised when a downloaded exe fails integrity checks."""


def _verify_exe(path: Path) -> None:
    """Verify a downloaded exe is valid before applying.

    Checks:
    - File size is above ``_MIN_EXE_SIZE`` (truncated download guard)
    - First 2 bytes are ``MZ`` (PE header magic)

    Raises :class:`VerificationError` on failure.
    """
    size = path.stat().st_size
    if size < _MIN_EXE_SIZE:
        raise VerificationError(
            f"Downloaded exe is only {size / 1e6:.1f} MB "
            f"(expected >{_MIN_EXE_SIZE / 1e6:.0f} MB) — likely truncated"
        )

    with path.open("rb") as f:
        magic = f.read(2)
    if magic != _PE_MAGIC:
        raise VerificationError(
            f"Downloaded exe has invalid PE header: {magic!r} (expected {_PE_MAGIC!r})"
        )

    LOG.info("Exe verification passed: %.1f MB, valid PE header", size / 1e6)


# ---------------------------------------------------------------------------
# Update check
# ---------------------------------------------------------------------------


class UpdateInfo:
    """Information about an available update."""

    __slots__ = ("body", "download_url", "size_bytes", "tag", "version")

    def __init__(
        self,
        tag: str,
        version: str,
        download_url: str,
        size_bytes: int,
        body: str,
    ):
        self.tag = tag
        self.version = version
        self.download_url = download_url
        self.size_bytes = size_bytes
        self.body = body

    def __repr__(self) -> str:
        return f"UpdateInfo(tag={self.tag!r}, size={self.size_bytes})"


def _check_firebase(current: tuple[int, ...]) -> UpdateInfo | None:
    """Check Firebase for the latest launcher version (primary source).

    Returns an :class:`UpdateInfo` if a newer version exists, else *None*.
    """
    try:
        req = urllib.request.Request(_FIREBASE_VERSION_URL)
        resp = urllib.request.urlopen(req, timeout=_CHECK_TIMEOUT)
        data = json.loads(resp.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        LOG.warning("Firebase version check failed: %s", exc)
        return None

    if not isinstance(data, dict):
        LOG.warning("Firebase returned non-dict: %r", type(data).__name__)
        return None

    tag = data.get("tag", "")
    ver = _parse_version(tag)
    if ver is None or ver <= current:
        return None

    return UpdateInfo(
        tag=tag,
        version=data.get("version", ""),
        download_url=data.get("download_url", ""),
        size_bytes=data.get("size_bytes", 0),
        body="",
    )


def _check_github(current: tuple[int, ...], *, retry_on_failure: bool = False) -> UpdateInfo | None:
    """Check GitHub API for a newer launcher release (fallback source)."""
    releases = None
    for attempt in range(2 if retry_on_failure else 1):
        try:
            req = urllib.request.Request(
                _RELEASES_URL,
                headers={"Accept": "application/vnd.github+json"},
            )
            resp = urllib.request.urlopen(req, timeout=_CHECK_TIMEOUT)
            releases = json.loads(resp.read())
            break
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            LOG.warning("GitHub update check failed (attempt %d): %s", attempt + 1, exc)
            if attempt == 0 and retry_on_failure:
                time.sleep(5)
                LOG.info("Retrying GitHub update check ...")

    if releases is None:
        return None

    best: UpdateInfo | None = None
    best_ver: tuple[int, ...] = current

    for release in releases:
        tag = release.get("tag_name", "")
        ver = _parse_version(tag)
        if ver is None or ver <= current:
            continue
        if release.get("draft") or release.get("prerelease"):
            continue

        # Find the exe asset
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name.lower().endswith(".exe"):
                if ver > best_ver:
                    best_ver = ver
                    ver_str = tag[len(_TAG_PREFIX) :]
                    best = UpdateInfo(
                        tag=tag,
                        version=ver_str,
                        download_url=asset["browser_download_url"],
                        size_bytes=asset.get("size", 0),
                        body=release.get("body", ""),
                    )
                break

    return best


def check_for_update(*, retry_on_failure: bool = False) -> UpdateInfo | None:
    """Check for a newer launcher version.

    Tries Firebase first (fast, reliable), falls back to GitHub API.
    Returns an :class:`UpdateInfo` if an update is available, else *None*.
    This is safe to call from a background thread.

    When *retry_on_failure* is True, a failed network request is retried
    once after a 5-second delay (useful for startup when the network may
    not be ready yet).
    """
    current = _current_version_tuple()
    LOG.info("Checking for updates (current: %s) ...", config.VERSION)

    # Primary: Firebase version manifest
    result = _check_firebase(current)
    if result is not None:
        LOG.info("Update available (Firebase): %s (current: %s)", result.version, config.VERSION)
        return result

    # Fallback: GitHub releases API
    LOG.info("Firebase had no update, trying GitHub API fallback ...")
    result = _check_github(current, retry_on_failure=retry_on_failure)
    if result is not None:
        LOG.info("Update available (GitHub): %s (current: %s)", result.version, config.VERSION)
        return result

    LOG.info("No update available.")
    return None


# ---------------------------------------------------------------------------
# Download and apply
# ---------------------------------------------------------------------------


def download_update(
    info: UpdateInfo,
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> Path | None:
    """Download the update exe to a temp file.

    Returns the path to the downloaded file, or *None* on failure.
    """
    if not getattr(sys, "frozen", False):
        LOG.warning("Cannot self-update in non-frozen mode")
        return None

    exe_path = Path(sys.executable)
    tmp_path = exe_path.with_suffix(".update")

    try:
        LOG.info("Downloading update from %s ...", info.download_url)
        dl_req = urllib.request.Request(
            info.download_url,
            headers={"User-Agent": f"WOPC-Launcher/{config.VERSION}"},
        )
        req = urllib.request.urlopen(dl_req, timeout=60)
        total = int(req.headers.get("Content-Length", info.size_bytes))
        downloaded = 0
        chunk_size = 256 * 1024

        with tmp_path.open("wb") as f:
            while True:
                chunk = req.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(downloaded, total)

        LOG.info("Downloaded update: %s (%.1f MB)", tmp_path.name, tmp_path.stat().st_size / 1e6)

        # Verify before returning — catch truncated/corrupt downloads
        try:
            _verify_exe(tmp_path)
        except VerificationError as exc:
            LOG.error("Update verification failed: %s", exc)
            tmp_path.unlink(missing_ok=True)
            return None

        return tmp_path
    except (OSError, urllib.error.URLError) as exc:
        LOG.error("Update download failed: %s", exc)
        if tmp_path.exists():
            tmp_path.unlink()
        return None


def apply_update(tmp_path: Path) -> bool:
    """Replace the running exe with the downloaded update and restart.

    On Windows, a running exe can be renamed (but not deleted).
    The restart is handled by a cmd script that logs every step to
    ``restart.log`` next to the exe for post-mortem debugging.
    """
    if not getattr(sys, "frozen", False):
        return False

    exe_path = Path(sys.executable)
    old_path = exe_path.with_suffix(".old")

    try:
        # Remove previous .old if it exists
        if old_path.exists():
            old_path.unlink()

        # Rename running exe → .old
        exe_path.rename(old_path)
        LOG.info("Renamed %s -> %s", exe_path.name, old_path.name)

        # Move downloaded update into place
        tmp_path.rename(exe_path)
        LOG.info("Moved update into %s", exe_path.name)

        # Restart with the new exe after cleaning up our _MEI temp dir.
        # os._exit(0) skips Python's atexit handlers, so PyInstaller never
        # removes the _MEIPASS extraction directory. On next launch, the
        # bootloader finds the stale _MEI dir and shows a warning dialog.
        # Fix: spawn a cmd script that (1) waits for this process to die,
        # (2) deletes the stale _MEI dir, (3) launches the new exe.
        #
        # The script writes each step to restart.log for debugging.
        # ``start ""`` launches the new exe non-blocking — the old cmd
        # approach ran the exe directly, which blocked until it exited
        # (observed 68s restart delay).
        meipass = getattr(sys, "_MEIPASS", None)
        restart_log = exe_path.parent / "restart.log"
        if meipass:
            LOG.info("Scheduling restart (old _MEI: %s)", meipass)
            restart_script = exe_path.parent / "_wopc_restart.cmd"
            # Simple restart: wait for old process to exit, then launch
            # new exe directly (inherits elevation from admin cmd).
            # Do NOT delete _MEI here — cleanup_old_exe() handles it
            # safely on next startup, avoiding bootloader race conditions.
            script_text = (
                f"@echo off\n"
                f'echo [%date% %time%] Starting update restart >>"{restart_log}"\n'
                f'echo [%date% %time%] Old _MEI was: {meipass} >>"{restart_log}"\n'
                f"ping -n 4 127.0.0.1 >nul\n"
                f'echo [%date% %time%] Launching: {exe_path} >>"{restart_log}"\n'
                f'"{exe_path}"\n'
                f"echo [%date% %time%] Exe exited (code: %ERRORLEVEL%)"
                f' >>"{restart_log}"\n'
            )
            restart_script.write_text(script_text, encoding="utf-8")
            LOG.info("Restart script:\n%s", script_text.rstrip())
            subprocess.Popen(["cmd", "/c", str(restart_script)])
        else:
            LOG.info("Restarting launcher (non-frozen) ...")
            subprocess.Popen([str(exe_path)])
        LOG.info("Restart scheduled, exiting old process.")
        os._exit(0)  # Hard exit — avoid tkinter cleanup issues

        return True  # pragma: no cover
    except OSError as exc:
        LOG.error("Failed to apply update: %s", exc)
        # Try to restore the old exe
        if old_path.exists() and not exe_path.exists():
            try:
                old_path.rename(exe_path)
                LOG.info("Restored original exe")
            except OSError as restore_exc:
                LOG.error("Failed to restore original exe: %s", restore_exc)
        return False


def cleanup_old_exe() -> None:
    """Remove the ``.old`` leftover from a previous update and stale _MEI dirs.

    Also reads and logs ``restart.log`` (written by the cmd restart script)
    so we have visibility into what happened between the old process exiting
    and this new process starting.

    PyInstaller ``--onefile`` extracts to a temp ``_MEI*`` directory. If the
    process crashes, these dirs accumulate and PyInstaller shows a warning
    dialog on next launch. Clean up any that aren't ours.
    """
    if not getattr(sys, "frozen", False):
        return

    exe_dir = Path(sys.executable).parent

    # --- Read and log restart.log from the cmd restart script ---
    restart_log = exe_dir / "restart.log"
    if restart_log.exists():
        try:
            content = restart_log.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                LOG.info("--- restart.log from previous update ---")
                for line in content.splitlines():
                    LOG.info("  %s", line)
                LOG.info("--- end restart.log ---")
            restart_log.unlink()
            LOG.info("Cleaned up restart.log")
        except OSError as exc:
            LOG.warning("Failed to read/delete restart.log: %s", exc)

    # --- Clean up stale restart.log) from old cmd /c (...) code ---
    stale_log = exe_dir / "restart.log)"
    if stale_log.exists():
        try:
            stale_log.unlink()
            LOG.info("Cleaned up stale restart.log)")
        except OSError:
            pass

    # --- Clean up _wopc_restart.cmd from previous update ---
    restart_cmd = exe_dir / "_wopc_restart.cmd"
    if restart_cmd.exists():
        try:
            restart_cmd.unlink()
            LOG.info("Cleaned up _wopc_restart.cmd")
        except OSError:
            pass

    # --- Clean up .old file ---
    old_path = Path(sys.executable).with_suffix(".old")
    if old_path.exists():
        try:
            old_path.unlink()
            LOG.info("Cleaned up %s", old_path.name)
        except OSError as exc:
            LOG.warning("Failed to clean up %s: %s", old_path.name, exc)

    # --- Clean up stale _MEI temp directories from previous PyInstaller runs ---
    import shutil
    import tempfile

    our_meipass = getattr(sys, "_MEIPASS", None)
    temp_dir = Path(tempfile.gettempdir())
    try:
        for entry in temp_dir.iterdir():
            if entry.name.startswith("_MEI") and entry.is_dir():
                # Don't delete our own extraction directory
                if our_meipass and str(entry) == our_meipass:
                    continue
                try:
                    shutil.rmtree(entry)
                    LOG.info("Cleaned up stale PyInstaller temp dir: %s", entry.name)
                except OSError as exc:
                    LOG.warning("Failed to clean up %s: %s", entry.name, exc)
    except OSError as exc:
        LOG.warning("Failed to scan temp dir for stale _MEI dirs: %s", exc)
