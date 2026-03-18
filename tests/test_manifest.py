"""Tests for launcher.manifest — TOML manifest parsing and exclusion logic."""

from pathlib import Path

import pytest

from launcher.manifest import ManifestError, PatchManifest, apply_exclusions, load_manifest


class TestLoadManifest:
    """Tests for loading and validating wopc_patches.toml."""

    def test_valid_manifest(self, tmp_path: Path) -> None:
        """Well-formed TOML produces correct PatchManifest."""
        toml_path = tmp_path / "patches.toml"
        toml_path.write_text(
            '[build]\nstrategy = "include_all"\n\n'
            "[exclude]\n"
            'hooks = ["gpg_net.cpp"]\n'
            'sections = ["HashChecker.cpp", "gpg_net.cpp"]\n'
        )
        m = load_manifest(toml_path)
        assert m.strategy == "include_all"
        assert m.exclude_hooks == ["gpg_net.cpp"]
        assert m.exclude_sections == ["HashChecker.cpp", "gpg_net.cpp"]

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """Nonexistent manifest should raise ManifestError."""
        with pytest.raises(ManifestError, match="not found"):
            load_manifest(tmp_path / "nope.toml")

    def test_invalid_toml_raises(self, tmp_path: Path) -> None:
        """Malformed TOML should raise ManifestError."""
        bad = tmp_path / "bad.toml"
        bad.write_text("[build\nstrategy = oops")
        with pytest.raises(ManifestError, match="Invalid TOML"):
            load_manifest(bad)

    def test_unknown_strategy_raises(self, tmp_path: Path) -> None:
        """Unrecognized strategy value should raise ManifestError."""
        toml_path = tmp_path / "patches.toml"
        toml_path.write_text('[build]\nstrategy = "yolo"\n')
        with pytest.raises(ManifestError, match="Unknown strategy"):
            load_manifest(toml_path)

    def test_defaults_when_sections_missing(self, tmp_path: Path) -> None:
        """Manifest with no [exclude] section should default to empty lists."""
        toml_path = tmp_path / "minimal.toml"
        toml_path.write_text('[build]\nstrategy = "include_all"\n')
        m = load_manifest(toml_path)
        assert m.exclude_hooks == []
        assert m.exclude_sections == []

    def test_exclude_hooks_not_list_raises(self, tmp_path: Path) -> None:
        """exclude.hooks must be a list of strings."""
        toml_path = tmp_path / "bad_type.toml"
        toml_path.write_text(
            '[build]\nstrategy = "include_all"\n\n[exclude]\nhooks = "not_a_list"\n'
        )
        with pytest.raises(ManifestError, match="list of strings"):
            load_manifest(toml_path)

    def test_real_manifest_loads(self) -> None:
        """The actual wopc_patches.toml in the repo should parse successfully."""
        repo_manifest = Path(__file__).parent.parent / "wopc_patches.toml"
        assert repo_manifest.is_file(), "wopc_patches.toml missing from repo root"
        m = load_manifest(repo_manifest)
        assert m.strategy == "include_all"
        assert "gpg_net.cpp" in m.exclude_hooks
        assert "HashChecker.cpp" in m.exclude_sections


class TestApplyExclusions:
    """Tests for removing excluded patches from the staging directory."""

    def _make_staging(self, tmp_path: Path) -> Path:
        """Create a fake staging directory with hooks and sections."""
        staging = tmp_path / "staging"
        hooks = staging / "hooks"
        section = staging / "section"
        hooks.mkdir(parents=True)
        section.mkdir(parents=True)

        # Create some fake patch files
        for name in ("gpg_net.cpp", "gpg_net.h", "FixCollisions.cpp", "CameraPerf.cpp"):
            (hooks / name).write_text(f"// {name}")
        for name in ("gpg_net.cpp", "HashChecker.cpp", "PathfindingTweaks.cpp", "DesyncFix.cpp"):
            (section / name).write_text(f"// {name}")

        return staging

    def test_excludes_listed_files(self, tmp_path: Path) -> None:
        """Files in the exclude lists should be removed from staging."""
        staging = self._make_staging(tmp_path)
        manifest = PatchManifest(
            strategy="include_all",
            exclude_hooks=["gpg_net.cpp", "gpg_net.h"],
            exclude_sections=["gpg_net.cpp", "HashChecker.cpp"],
        )

        removed = apply_exclusions(staging, manifest)

        assert removed == 4
        assert not (staging / "hooks" / "gpg_net.cpp").exists()
        assert not (staging / "hooks" / "gpg_net.h").exists()
        assert not (staging / "section" / "gpg_net.cpp").exists()
        assert not (staging / "section" / "HashChecker.cpp").exists()

    def test_preserves_non_excluded_files(self, tmp_path: Path) -> None:
        """Files NOT in the exclude lists should remain untouched."""
        staging = self._make_staging(tmp_path)
        manifest = PatchManifest(
            exclude_hooks=["gpg_net.cpp"],
            exclude_sections=["HashChecker.cpp"],
        )

        apply_exclusions(staging, manifest)

        # These should still exist
        assert (staging / "hooks" / "FixCollisions.cpp").exists()
        assert (staging / "hooks" / "CameraPerf.cpp").exists()
        assert (staging / "section" / "PathfindingTweaks.cpp").exists()
        assert (staging / "section" / "DesyncFix.cpp").exists()

    def test_excludes_nonexistent_file_no_error(self, tmp_path: Path) -> None:
        """Excluding a file that doesn't exist should not raise."""
        staging = self._make_staging(tmp_path)
        manifest = PatchManifest(
            exclude_hooks=["does_not_exist.cpp"],
            exclude_sections=[],
        )

        removed = apply_exclusions(staging, manifest)
        assert removed == 0

    def test_empty_exclude_lists(self, tmp_path: Path) -> None:
        """Empty exclude lists should remove nothing."""
        staging = self._make_staging(tmp_path)
        manifest = PatchManifest()

        removed = apply_exclusions(staging, manifest)
        assert removed == 0
        # All original files should remain
        assert len(list((staging / "hooks").iterdir())) == 4
        assert len(list((staging / "section").iterdir())) == 4
