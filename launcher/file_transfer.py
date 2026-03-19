"""Lobby file transfer — stream maps and mods between host and joiner.

The host serves files from its local disk via the existing TCP lobby
connection.  Files are chunked, base64-encoded, and wrapped in JSON-line
messages so the existing ``lobby.py`` protocol can carry them unchanged.

Typical flow
------------
1. Joiner discovers it's missing a map via ``GameState`` broadcast.
2. Joiner sends ``{"type": "FileRequest", "category": "map", "name": "Theta Passage"}``.
3. Host receives the request, builds a file manifest (list of files + sizes),
   and sends ``{"type": "FileManifest", ...}`` back.
4. Host streams ``{"type": "FileChunk", ...}`` messages (64 KB raw → ~85 KB base64).
5. After the last chunk, host sends ``{"type": "FileComplete", ...}``.
6. Joiner writes files to disk and notifies the GUI.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("wopc.file_transfer")

# Chunk size for binary data (before base64 encoding)
CHUNK_SIZE = 64 * 1024  # 64 KB


def build_file_manifest(root_dir: Path) -> list[dict[str, Any]]:
    """Scan a directory and return a manifest of files with sizes and hashes.

    Returns a list of dicts, each with:
    - ``path``: relative path from root_dir (forward slashes)
    - ``size``: file size in bytes
    - ``sha256``: hex digest of file contents
    """
    manifest: list[dict[str, Any]] = []
    if not root_dir.is_dir():
        return manifest

    for fpath in sorted(root_dir.rglob("*")):
        if not fpath.is_file():
            continue
        rel = fpath.relative_to(root_dir).as_posix()
        size = fpath.stat().st_size
        sha = hashlib.sha256(fpath.read_bytes()).hexdigest()
        manifest.append({"path": rel, "size": size, "sha256": sha})

    return manifest


def iter_file_chunks(
    root_dir: Path, relative_path: str, chunk_size: int = CHUNK_SIZE
) -> list[dict[str, Any]]:
    """Read a file and yield base64-encoded chunk messages.

    Each chunk dict has:
    - ``path``: relative file path
    - ``index``: 0-based chunk index
    - ``total``: total number of chunks for this file
    - ``data``: base64-encoded chunk data
    """
    fpath = root_dir / relative_path
    if not fpath.is_file():
        return []

    raw = fpath.read_bytes()
    total = max(1, (len(raw) + chunk_size - 1) // chunk_size)
    chunks: list[dict[str, Any]] = []

    for i in range(total):
        start = i * chunk_size
        end = min(start + chunk_size, len(raw))
        b64 = base64.b64encode(raw[start:end]).decode("ascii")
        chunks.append(
            {
                "path": relative_path,
                "index": i,
                "total": total,
                "data": b64,
            }
        )

    return chunks


def write_chunk_to_disk(
    dest_dir: Path,
    relative_path: str,
    index: int,
    total: int,
    b64_data: str,
) -> Path:
    """Decode a base64 chunk and append it to the destination file.

    Creates parent directories as needed.  On the first chunk (index=0),
    truncates any existing file.

    Returns the full path of the file being written.
    """
    fpath = dest_dir / relative_path
    fpath.parent.mkdir(parents=True, exist_ok=True)

    mode = "wb" if index == 0 else "ab"
    raw = base64.b64decode(b64_data)
    with Path.open(fpath, mode) as f:
        f.write(raw)

    return fpath


def verify_file(dest_dir: Path, relative_path: str, expected_sha256: str) -> bool:
    """Verify a downloaded file matches its expected SHA256 hash."""
    fpath = dest_dir / relative_path
    if not fpath.is_file():
        return False
    actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
    return actual == expected_sha256


def total_transfer_size(manifest: list[dict[str, Any]]) -> int:
    """Sum up the total bytes to transfer from a file manifest."""
    return sum(f.get("size", 0) for f in manifest)


def format_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def find_map_directory(map_folder: str) -> Path | None:
    """Find the map directory on disk given a folder name.

    Checks both the WOPC maps directory and the user maps directory.
    """
    from launcher.config import WOPC_ROOT

    for maps_dir in [WOPC_ROOT / "maps", WOPC_ROOT / "usermaps"]:
        candidate = maps_dir / map_folder
        if candidate.is_dir():
            return candidate
    return None


def missing_map_check(map_folder: str) -> bool:
    """Return True if the map folder is NOT found locally."""
    return find_map_directory(map_folder) is None


def get_map_install_dir() -> Path:
    """Return the directory where downloaded maps should be saved."""
    from launcher.config import WOPC_ROOT

    dest = WOPC_ROOT / "usermaps"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


# ---------------------------------------------------------------------------
# Content pack helpers
# ---------------------------------------------------------------------------


def missing_content_packs(required_packs: list[str]) -> list[str]:
    """Return list of content pack SCD names that are not present locally."""
    from launcher.config import WOPC_GAMEDATA

    missing: list[str] = []
    for scd_name in required_packs:
        if not (WOPC_GAMEDATA / scd_name).exists():
            missing.append(scd_name)
    return missing


def get_pack_download_url(scd_name: str) -> str | None:
    """Look up the GitHub download URL for a content pack SCD.

    Returns None if the pack isn't in the known URL registry.
    Content packs can also be transferred from host over TCP.
    """
    # Content pack download URLs are managed in deploy.py.
    # For now, content packs transfer over TCP like maps.
    _ = scd_name
    return None
