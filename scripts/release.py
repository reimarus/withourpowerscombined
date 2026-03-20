"""WOPC release automation.

Version format: major.minor.build  (e.g. 2.01.0001)
- major: breaking changes
- minor: 2-digit, new features
- build: 4-digit, auto-increments on every release

Bumps the build number automatically, or specify minor/major:

    py scripts/release.py           # 2.01.0001 → 2.01.0002
    py scripts/release.py minor     # 2.01.0042 → 2.02.0001
    py scripts/release.py major     # 2.01.0042 → 3.00.0001

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
    """Write a new version into pyproject.toml."""
    text = PYPROJECT.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(version\s*=\s*)"[^"]+"',
        rf'\1"{new_ver}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    PYPROJECT.write_text(updated, encoding="utf-8")


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

    print(f"  Version: {old_ver} → {new_ver}")
    print(f"  Tag:     {tag}")
    print()

    # 1. Bump version in pyproject.toml
    _write_version(new_ver)
    print(f"  ✓ Updated pyproject.toml to {new_ver}")

    # 2. Reinstall package so importlib.metadata picks up the new version
    run("py -m pip install -e . -q")

    # 3. Run tests
    print("\n— Running tests —")
    run("py -m pytest tests/ -x -q --no-header")

    # 4. Build exe
    print("\n— Building exe —")
    run("py build_exe.py")

    exe_path = REPO_ROOT / EXE_NAME
    if not exe_path.exists():
        raise SystemExit(f"Build failed: {exe_path} not found")

    size_mb = exe_path.stat().st_size / 1_000_000
    print(f"  ✓ Built {EXE_NAME} ({size_mb:.1f} MB)")

    # 5. Commit the version bump
    run(f"git add {PYPROJECT.name}")
    run(f'git commit -m "release: v{new_ver}" --no-verify')

    # 6. Create GitHub release and upload exe
    print("\n— Creating GitHub release —")
    title = f"WOPC Launcher v{new_ver}"
    run(f'gh release create {tag} "{exe_path}" --title "{title}" --generate-notes --latest')

    # 7. Push the commit
    run("git push")

    print(f"\n  ✅ Released {tag}")
    print(f"     https://github.com/reimarus/withourpowerscombined/releases/tag/{tag}")


if __name__ == "__main__":
    main()
