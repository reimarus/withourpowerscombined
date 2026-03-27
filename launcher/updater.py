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

# GitHub API endpoint — search for releases with the launcher tag prefix
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


def check_for_update() -> UpdateInfo | None:
    """Query GitHub for a newer launcher release.

    Returns an :class:`UpdateInfo` if an update is available, else *None*.
    This is safe to call from a background thread.
    """
    current = _current_version_tuple()
    LOG.info("Checking for updates (current: %s) ...", config.VERSION)

    try:
        req = urllib.request.Request(
            _RELEASES_URL,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp = urllib.request.urlopen(req, timeout=_CHECK_TIMEOUT)
        releases = json.loads(resp.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        LOG.warning("Update check failed: %s", exc)
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

    if best:
        LOG.info("Update available: %s (current: %s)", best.version, config.VERSION)
    else:
        LOG.info("No update available.")
    return best


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
        req = urllib.request.urlopen(info.download_url, timeout=60)
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
            LOG.info("Scheduling _MEI cleanup + restart: %s", meipass)
            subprocess.Popen(
                f"cmd /c ("
                f'echo [%date% %time%] Starting update restart >>"{restart_log}"'
                f" & ping -n 4 127.0.0.1 >nul"
                f' & echo [%date% %time%] Deleting _MEI: {meipass} >>"{restart_log}"'
                f' & rmdir /s /q "{meipass}" 2>>"{restart_log}"'
                f" & ping -n 3 127.0.0.1 >nul"
                f' & rmdir /s /q "{meipass}" 2>>"{restart_log}"'
                f' & echo [%date% %time%] Launching new exe: {exe_path} >>"{restart_log}"'
                f' & start "" "{exe_path}"'
                f' & echo [%date% %time%] Launch command issued >>"{restart_log}"'
                f")",
                shell=True,
            )
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
