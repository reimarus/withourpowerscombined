"""WOPC release automation.

Version format: major.minor.build  (e.g. 2.01.0001)
- major: breaking changes
- minor: 2-digit, new features
- build: 4-digit, auto-increments on every release

Bumps the build number automatically, or specify minor/major:

    py scripts/release.py           # 2.01.0001 -> 2.01.0002
    py scripts/release.py minor     # 2.01.0042 -> 2.02.0001
    py scripts/release.py major     # 2.01.0042 -> 3.00.0001

Then: runs tests + builds exe (in parallel), optionally rebuilds content-v2
(only when content source files changed), commits, creates GitHub release, pushes.
"""

from __future__ import annotations

import concurrent.futures
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
EXE_NAME = "WOPC-Launcher.exe"

# Paths whose changes require a content-v2 rebuild.
CONTENT_SOURCE_PREFIXES = (
    "gamedata/",
    "vendor/faf-ui/",
    "init/",
    "launcher/deploy.py",
    "launcher/mods.py",
    "scripts/build_content_release.py",
)


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
    # Embed the short commit hash for build provenance
    commit = (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT)
        .decode()
        .strip()
    )
    ver_updated = re.sub(
        r'^(COMMIT_HASH\s*=\s*)"[^"]*"',
        rf'\1"{commit}"',
        ver_updated,
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


def run(cmd: str, *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a shell command and stream output."""
    print(f"\n  $ {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=REPO_ROOT,
        capture_output=capture,
        text=True,
    )
    if check and result.returncode != 0:
        raise SystemExit(f"Command failed (exit {result.returncode}): {cmd}")
    return result


# ---------------------------------------------------------------------------
# Content change detection
# ---------------------------------------------------------------------------


def _content_changed_since_last_release() -> bool:
    """Check if any content source files changed since the last content-v2 build.

    Uses a lightweight marker tag 'content-v2-built' to track the last commit
    that triggered a content rebuild. Falls back to always rebuilding if the
    tag doesn't exist.
    """
    result = subprocess.run(
        "git diff --name-only content-v2-built..HEAD",
        shell=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Tag doesn't exist — rebuild to be safe
        return True

    changed_files = result.stdout.strip().splitlines()
    for f in changed_files:
        normalized = f.replace("\\", "/")
        if any(normalized.startswith(p) for p in CONTENT_SOURCE_PREFIXES):
            return True
    return False


def _update_content_built_tag() -> None:
    """Move the content-v2-built tag to HEAD."""
    subprocess.run(
        "git tag -f content-v2-built HEAD",
        shell=True,
        cwd=REPO_ROOT,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Pip install skip
# ---------------------------------------------------------------------------


def _is_editable_installed() -> bool:
    """Check if the package is already installed in editable mode."""
    result = subprocess.run(
        "py -m pip show wopc",
        shell=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return "Editable project location" in (result.stdout or "")


# ---------------------------------------------------------------------------
# R2 upload + Firebase version manifest
# ---------------------------------------------------------------------------


def _upload_to_r2(exe_path: Path, version: str, tag: str) -> None:
    """Upload the launcher exe to Cloudflare R2 and update Firebase version manifest.

    Requires env vars: R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID.
    Falls back gracefully if env vars are missing or upload fails.
    """
    import json
    import os
    import urllib.request

    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    if not all([account_id, access_key, secret_key]):
        print("\n  SKIP: R2 env vars not set (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, ...)")
        print("        Exe not uploaded to R2, Firebase manifest not updated.")
        return

    # Upload exe to R2 via boto3 (S3-compatible)
    print("\n-- Uploading exe to R2 --")
    try:
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
        r2_key = "launcher/WOPC-Launcher.exe"
        s3.upload_file(
            str(exe_path),
            "wopc-releases",
            r2_key,
            ExtraArgs={"ContentType": "application/octet-stream"},
        )
        size_mb = exe_path.stat().st_size / 1_000_000
        print(f"  OK: Uploaded {r2_key} to R2 ({size_mb:.1f} MB)")
    except Exception as exc:
        print(f"  WARNING: R2 upload failed: {exc}")
        print("           Users will fall back to GitHub download.")
        return

    # Update Firebase version manifest
    download_url = "https://wopc-cdn.roskvarek.workers.dev/launcher/WOPC-Launcher.exe"
    manifest = {
        "tag": tag,
        "version": version,
        "download_url": download_url,
        "size_bytes": exe_path.stat().st_size,
    }
    firebase_url = "https://wopc-75b65-default-rtdb.firebaseio.com/launcher_version.json"
    try:
        data = json.dumps(manifest).encode()
        req = urllib.request.Request(firebase_url, data=data, method="PUT")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)
        print(f"  OK: Firebase version manifest updated ({tag})")
    except Exception as exc:
        print(f"  WARNING: Firebase manifest update failed: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    t0 = time.monotonic()

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

    # 2. Reinstall package (skip if already editable)
    if _is_editable_installed():
        print("\n  SKIP: Package already installed in editable mode")
    else:
        run("py -m pip install -e . -q")

    # 3. Run tests + build exe IN PARALLEL
    print("\n-- Running tests + building exe (parallel) --")
    t_parallel = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        test_future = pool.submit(run, "py -m pytest tests/ -x -q --no-header --no-cov")
        build_future = pool.submit(run, "py build_exe.py")
        # Wait for both — raise if either fails
        test_future.result()
        build_future.result()
    parallel_sec = time.monotonic() - t_parallel
    print(f"  OK: Tests + build completed in {parallel_sec:.0f}s")

    exe_path = REPO_ROOT / EXE_NAME
    if not exe_path.exists():
        raise SystemExit(f"Build failed: {exe_path} not found")

    size_mb = exe_path.stat().st_size / 1_000_000
    print(f"  OK: Built {EXE_NAME} ({size_mb:.1f} MB)")

    # 4. Rebuild content-v2 ONLY if content source files changed
    if _content_changed_since_last_release():
        print("\n-- Rebuilding content-v2 (content files changed) --")
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

            _update_content_built_tag()
        else:
            print("  WARNING: Content build failed — content-v2 not updated")
            print("           (This is non-fatal; launcher release continues)")
    else:
        print("\n  SKIP: No content source changes — content-v2 rebuild skipped")

    # 5. Commit the version bump
    run(f"git add {PYPROJECT.name} launcher/__version__.py")
    run(f'git commit -m "release: v{new_ver}" --no-verify')

    # 6. Create GitHub release and upload exe
    print("\n-- Creating GitHub release --")
    title = f"WOPC Launcher v{new_ver}"
    run(f'gh release create {tag} "{exe_path}" --title "{title}" --generate-notes --latest')

    # 7. Upload exe to R2 + update Firebase version manifest
    _upload_to_r2(exe_path, new_ver, tag)

    # 8. Push the commit
    run("git push")

    elapsed = time.monotonic() - t0
    print(f"\n  DONE: Released {tag} in {elapsed:.0f}s")
    print(f"     https://github.com/reimarus/withourpowerscombined/releases/tag/{tag}")


if __name__ == "__main__":
    main()
