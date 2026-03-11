"""WOPC manifest builder - generates and validates content hashes for multiplayer sync."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from launcher import config

logger = logging.getLogger("wopc.manifest_builder")


def _hash_file(filepath: Path) -> str:
    """Calculate the SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with filepath.open("rb") as f:
        # Read in chunks to avoid memory issues with large SCD files
        for chunk in iter(lambda: f.read(4096 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_manifest(output_path: Path) -> None:
    """Generate a manifest.json file containing hashes of all loaded WOPC files."""
    logger.info("Generating content manifest...")
    manifest: dict[str, Any] = {"version": config.VERSION, "files": {}}

    # Files to hash
    targets = []

    # 1. Critical Binaries
    for fname in ["SupremeCommander.exe", "MohoEngine.dll", "init_wopc.lua"]:
        targets.append(config.WOPC_BIN / fname)

    # 2. Gamedata SCDs (Base Bundled Assets + WOPC Overlay)
    if config.WOPC_GAMEDATA.exists():
        targets.extend(list(config.WOPC_GAMEDATA.glob("*.scd")))

    # Hash everything
    for target in targets:
        if target.is_file():
            # Store relative path (e.g. gamedata/lua.scd or bin/SupremeCommander.exe)
            rel_path = target.relative_to(config.WOPC_ROOT).as_posix()
            manifest["files"][rel_path] = _hash_file(target)
            logger.info("  hashed %s", rel_path)
        else:
            logger.warning("  WARNING: missing file %s", target)

    # Write output
    with output_path.open("w") as f:
        json.dump(manifest, f, indent=4)
    logger.info("Manifest written to %s", output_path)


def verify_manifest(manifest_path: Path) -> int:
    """Verify the local WOPC installation against a manifest file.

    Returns:
        Number of error/mismatch occurrences (0 means ready for multiplayer).
    """
    if not manifest_path.is_file():
        logger.error("ERROR: Manifest file not found at %s", manifest_path)
        return 1

    logger.info("Verifying WOPC installation against %s", manifest_path.name)
    with manifest_path.open("r") as f:
        try:
            manifest = json.load(f)
        except json.JSONDecodeError:
            logger.error("ERROR: Invalid JSON in manifest.")
            return 1

    expected_files = manifest.get("files", {})
    if not expected_files:
        logger.error("ERROR: Manifest contains no file hashes.")
        return 1

    errors = 0

    for rel_path, expected_hash in expected_files.items():
        # Reconstruct path and normalize to correct OS slashes
        local_path = config.WOPC_ROOT / Path(rel_path)

        if not local_path.is_file():
            logger.error("  FAIL: Missing file %s", rel_path)
            errors += 1
            continue

        local_hash = _hash_file(local_path)
        if local_hash != expected_hash:
            logger.error("  FAIL: Hash mismatch for %s", rel_path)
            errors += 1
        else:
            logger.info("  OK:   %s", rel_path)

    if errors == 0:
        logger.info("\nSUCCESS: All files match the manifest. Ready for multiplayer!")
    else:
        logger.error("\nFAILURE: %d file(s) failed validation. You will desync.", errors)

    return errors
