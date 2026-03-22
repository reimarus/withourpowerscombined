"""WOPC release automation.

Version format: major.minor.build  (e.g. 2.01.0001)
- major: breaking changes
- minor: 2-digit, new features
- build: 4-digit, auto-increments on every release

Bumps the build number automatically, or specify minor/major:

    py scripts/release.py           # 2.01.0001 -> 2.01.0002
    py scripts/release.py minor     # 2.01.0042 -> 2.02.0001
    py scripts/release.py major     # 2.01.0042 -> 3.00.0001

Then: runs tests, builds exe, commits, creates GitHub release, pushes.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
EXE_NAME = "WOPC-Launcher.exe"


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


def _read_version() -> str:
    """Read the current version from pyproject.toml."""
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("Could not find version in pyproject.toml")
    return match.group(1)


def _write_version(new_ver: str) -> None:
    """Write a new version into pyproject.toml and launcher/__version__.py."""
    # Update pyproject.toml
    text = PYPROJECT.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(version\s*=\s*)"[^"]+"',
        rf'\1"{new_ver}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    PYPROJECT.write_text(updated, encoding="utf-8")

    # Update launcher/__version__.py (preserves leading zeros for GUI display)
    ver_file = REPO_ROOT / "launcher" / "__version__.py"
    ver_text = ver_file.read_text(encoding="utf-8")
    ver_updated = re.sub(
        r'^(VERSION\s*=\s*)"[^"]+"',
        rf'\1"{new_ver}"',
        ver_text,
        count=1,
        flags=re.MULTILINE,
    )
    ver_file.write_text(ver_updated, encoding="utf-8")


def _parse(ver: str) -> tuple[int, int, int]:
    """Parse 'N.NN.NNNN' into (major, minor, build)."""
    parts = ver.split(".")
    return (
        int(parts[0]) if len(parts) > 0 else 0,
        int(parts[1]) if len(parts) > 1 else 0,
        int(parts[2]) if len(parts) > 2 else 0,
    )


def _format(major: int, minor: int, build: int) -> str:
    """Format as 'N.NN.NNNN'."""
    return f"{major}.{minor:02d}.{build:04d}"


def bump(current: str, part: str) -> str:
    """Bump a version string by the given part."""
    major, minor, build = _parse(current)

    if part == "major":
        return _format(major + 1, 0, 1)
    if part == "minor":
        return _format(major, minor + 1, 1)
    # Default: bump build
    return _format(major, minor, build + 1)


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------


def run(cmd: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a shell command and stream output."""
    print(f"\n  $ {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=REPO_ROOT,
        capture_output=False,
        text=True,
    )
    if check and result.returncode != 0:
        raise SystemExit(f"Command failed (exit {result.returncode}): {cmd}")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "build"
    if part not in ("build", "minor", "major"):
        raise SystemExit(f"Usage: py scripts/release.py [build|minor|major]  (got '{part}')")

    old_ver = _read_version()
    new_ver = bump(old_ver, part)
    tag = f"launcher-v{new_ver}"

    print(f"  Version: {old_ver} -> {new_ver}")
    print(f"  Tag:     {tag}")
    print()

    # 1. Bump version in pyproject.toml
    _write_version(new_ver)
    print(f"  OK: Updated pyproject.toml to {new_ver}")

    # 2. Reinstall package so importlib.metadata picks up the new version
    run("py -m pip install -e . -q")

    # 3. Run tests
    print("\n-- Running tests --")
    run("py -m pytest tests/ -x -q --no-header")

    # 4. Build exe
    print("\n-- Building exe --")
    run("py build_exe.py")

    exe_path = REPO_ROOT / EXE_NAME
    if not exe_path.exists():
        raise SystemExit(f"Build failed: {exe_path} not found")

    size_mb = exe_path.stat().st_size / 1_000_000
    print(f"  OK: Built {EXE_NAME} ({size_mb:.1f} MB)")

    # 5. Rebuild content-v2 assets and update the content release
    print("\n-- Rebuilding content-v2 --")
    content_result = run("py scripts/build_content_release.py", check=False)
    if content_result.returncode == 0:
        staging = REPO_ROOT / "release-staging"
        scd = staging / "wopc_core.scd"
        scd_zip = staging / "wopc_core.scd.zip"
        maps_zip = staging / "wopc-maps.zip"
        icons_scd = staging / "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd"

        # Zip the SCD if not already zipped
        if scd.exists() and not scd_zip.exists():
            import zipfile

            with zipfile.ZipFile(scd_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
                zf.write(scd, "wopc_core.scd")
            size_mb = scd_zip.stat().st_size / 1_000_000
            print(f"  OK: Zipped wopc_core.scd ({size_mb:.1f} MB)")

        # Upload assets to content-v2 (delete old, re-upload)
        assets = [f for f in [scd_zip, maps_zip, icons_scd] if f.exists()]
        if assets:
            # Delete existing assets first
            for asset in assets:
                run(f'gh release delete-asset content-v2 "{asset.name}" --yes', check=False)
            # Upload new assets
            asset_args = " ".join(f'"{a}"' for a in assets)
            run(f"gh release upload content-v2 {asset_args} --clobber")
            print("  OK: Updated content-v2 release")
    else:
        print("  WARNING: Content build failed — content-v2 not updated")
        print("           (This is non-fatal; launcher release continues)")

    # 6. Commit the version bump
    run(f"git add {PYPROJECT.name} launcher/__version__.py")
    run(f'git commit -m "release: v{new_ver}" --no-verify')

    # 7. Create GitHub release and upload exe
    print("\n-- Creating GitHub release --")
    title = f"WOPC Launcher v{new_ver}"
    run(f'gh release create {tag} "{exe_path}" --title "{title}" --generate-notes --latest')

    # 8. Push the commit
    run("git push")

    print(f"\n  DONE: Released {tag}")
    print(f"     https://github.com/reimarus/withourpowerscombined/releases/tag/{tag}")


if __name__ == "__main__":
    main()
