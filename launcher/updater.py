"""WOPC Launcher self-update via GitHub Releases.

Checks for new launcher versions on startup (background thread), and
provides download + replace + restart when an update is available.

The update flow on Windows:
1. Download new exe to a temp file next to the running exe
2. Rename the running exe to ``*.old`` (Windows allows renaming a running exe)
3. Rename the temp file to the original name
4. Launch the new exe
5. Exit the old process
6. On next startup, clean up the ``.old`` file
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
        return tmp_path
    except (OSError, urllib.error.URLError) as exc:
        LOG.error("Update download failed: %s", exc)
        if tmp_path.exists():
            tmp_path.unlink()
        return None


def apply_update(tmp_path: Path) -> bool:
    """Replace the running exe with the downloaded update and restart.

    On Windows, a running exe can be renamed (but not deleted).
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

        # Restart with the new exe.
        # On Windows, os.execv doesn't truly replace the process — it spawns
        # a child and the parent continues.  Use subprocess + sys.exit instead.
        LOG.info("Restarting launcher ...")
        subprocess.Popen([str(exe_path)])
        LOG.info("New process launched, exiting old process.")
        os._exit(0)  # Hard exit — avoid tkinter cleanup issues

        return True  # pragma: no cover
    except OSError as exc:
        LOG.error("Failed to apply update: %s", exc)
        # Try to restore the old exe
        if old_path.exists() and not exe_path.exists():
            try:
                old_path.rename(exe_path)
                LOG.info("Restored original exe")
            except OSError:
                pass
        return False


def cleanup_old_exe() -> None:
    """Remove the ``.old`` leftover from a previous update."""
    if not getattr(sys, "frozen", False):
        return
    old_path = Path(sys.executable).with_suffix(".old")
    if old_path.exists():
        try:
            old_path.unlink()
            LOG.info("Cleaned up %s", old_path.name)
        except OSError:
            pass  # Still locked, will try next launch
