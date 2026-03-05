"""WOPC patch manifest — reads wopc_patches.toml and applies exclusion logic."""

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("wopc.manifest")


class ManifestError(Exception):
    """Raised when the manifest file is invalid or missing."""


@dataclass(frozen=True)
class PatchManifest:
    """Parsed patch manifest from wopc_patches.toml."""

    strategy: str = "include_all"
    exclude_hooks: list[str] = field(default_factory=list)
    exclude_sections: list[str] = field(default_factory=list)


def load_manifest(path: Path) -> PatchManifest:
    """Load and validate the patch manifest from a TOML file.

    Args:
        path: Path to wopc_patches.toml.

    Returns:
        A validated PatchManifest.

    Raises:
        ManifestError: If the file is missing, unreadable, or invalid.
    """
    if not path.is_file():
        raise ManifestError(f"Manifest not found: {path}")

    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"Invalid TOML in {path}: {exc}") from exc

    # Extract build strategy
    build = data.get("build", {})
    strategy = build.get("strategy", "include_all")
    if strategy not in ("include_all", "explicit"):
        raise ManifestError(
            f"Unknown strategy '{strategy}' in {path}. Must be 'include_all' or 'explicit'."
        )

    # Extract exclude lists
    exclude = data.get("exclude", {})
    exclude_hooks = exclude.get("hooks", [])
    exclude_sections = exclude.get("sections", [])

    if not isinstance(exclude_hooks, list) or not all(isinstance(h, str) for h in exclude_hooks):
        raise ManifestError(f"exclude.hooks must be a list of strings in {path}")
    if not isinstance(exclude_sections, list) or not all(
        isinstance(s, str) for s in exclude_sections
    ):
        raise ManifestError(f"exclude.sections must be a list of strings in {path}")

    manifest = PatchManifest(
        strategy=strategy,
        exclude_hooks=exclude_hooks,
        exclude_sections=exclude_sections,
    )

    logger.info("Loaded patch manifest from %s", path)
    logger.info("  Strategy: %s", manifest.strategy)
    if manifest.exclude_hooks:
        logger.info("  Excluded hooks: %s", ", ".join(manifest.exclude_hooks))
    if manifest.exclude_sections:
        logger.info("  Excluded sections: %s", ", ".join(manifest.exclude_sections))

    return manifest


def apply_exclusions(staging_dir: Path, manifest: PatchManifest) -> int:
    """Remove excluded patches from the staging directory.

    Args:
        staging_dir: Path to the staging directory containing hooks/ and section/.
        manifest: The loaded patch manifest with exclusion lists.

    Returns:
        Number of files removed.
    """
    removed = 0

    hooks_dir = staging_dir / "hooks"
    if hooks_dir.is_dir():
        for filename in manifest.exclude_hooks:
            target = hooks_dir / filename
            if target.is_file():
                target.unlink()
                logger.info("  Excluded hook: %s", filename)
                removed += 1
            else:
                logger.debug("  Hook not found (already absent): %s", filename)

    section_dir = staging_dir / "section"
    if section_dir.is_dir():
        for filename in manifest.exclude_sections:
            target = section_dir / filename
            if target.is_file():
                target.unlink()
                logger.info("  Excluded section: %s", filename)
                removed += 1
            else:
                logger.debug("  Section not found (already absent): %s", filename)

    return removed
