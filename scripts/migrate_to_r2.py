"""One-time migration: upload all WOPC assets from GitHub Releases to Cloudflare R2.

Since the GitHub account is returning 404 for unauthenticated requests,
this script uses the authenticated `gh` CLI to download assets and then
uploads them to R2 via boto3 (S3-compatible API).

Requirements:
    pip install boto3
    gh auth login  (GitHub CLI, authenticated)

Environment variables:
    R2_ACCOUNT_ID       Cloudflare account ID
    R2_ACCESS_KEY_ID    R2 API token access key
    R2_SECRET_ACCESS_KEY R2 API token secret key

Usage:
    python scripts/migrate_to_r2.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Assets to migrate: (github_release_tag, asset_filename, r2_key)
ASSETS: list[tuple[str, str, str]] = [
    # --- content-v1 ---
    ("content-v1", "blackops.scd", "content-v1/blackops.scd"),
    ("content-v1", "blackopssb.xsb", "content-v1/blackopssb.xsb"),
    ("content-v1", "blackopswb.xwb", "content-v1/blackopswb.xwb"),
    ("content-v1", "TotalMayhem.scd", "content-v1/TotalMayhem.scd"),
    ("content-v1", "tm_aeonweapons.xsb", "content-v1/tm_aeonweapons.xsb"),
    ("content-v1", "tm_aeonweaponsounds.xwb", "content-v1/tm_aeonweaponsounds.xwb"),
    ("content-v1", "tm_aircrafts.xsb", "content-v1/tm_aircrafts.xsb"),
    ("content-v1", "tm_aircraftsounds.xwb", "content-v1/tm_aircraftsounds.xwb"),
    ("content-v1", "tm_cybranweapons.xsb", "content-v1/tm_cybranweapons.xsb"),
    ("content-v1", "tm_cybranweaponsounds.xwb", "content-v1/tm_cybranweaponsounds.xwb"),
    ("content-v1", "tm_explosions.xsb", "content-v1/tm_explosions.xsb"),
    ("content-v1", "tm_explosionsounds.xwb", "content-v1/tm_explosionsounds.xwb"),
    ("content-v1", "tm_uefweapons.xsb", "content-v1/tm_uefweapons.xsb"),
    ("content-v1", "tm_uefweaponsounds.xwb", "content-v1/tm_uefweaponsounds.xwb"),
    ("content-v1", "content_icons.scd", "content-v1/content_icons.scd"),
    # --- content-v2 ---
    ("content-v2", "wopc_core.scd.zip", "content-v2/wopc_core.scd.zip"),
    ("content-v2", "wopc-maps.zip", "content-v2/wopc-maps.zip"),
    (
        "content-v2",
        "BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd",
        "content-v2/BrewLAN-StrategicIconsOverhaul-LARGE-classic.scd",
    ),
    # --- content-v3 ---
    ("content-v3", "lua.scd", "content-v3/lua.scd"),
    ("content-v3", "loc_US.scd", "content-v3/loc_US.scd"),
    ("content-v3", "brewlan.scd", "content-v3/brewlan.scd"),
    ("content-v3", "loud_units.scd", "content-v3/loud_units.scd"),
    ("content-v3", "WyvernBattlePack.scd", "content-v3/WyvernBattlePack.scd"),
    ("content-v3", "BattlePackSB.xsb", "content-v3/BattlePackSB.xsb"),
    ("content-v3", "BattlePackWB.xwb", "content-v3/BattlePackWB.xwb"),
    ("content-v3", "4D-CompatibilityPack.scd", "content-v3/4D-CompatibilityPack.scd"),
]

BUCKET = "wopc-releases"


def main() -> None:
    import boto3

    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    if not all([account_id, access_key, secret_key]):
        print("ERROR: Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY env vars")
        sys.exit(1)

    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )

    # Check which assets already exist in R2
    print("Checking existing R2 objects...")
    existing: set[str] = set()
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BUCKET):
            for obj in page.get("Contents", []):
                existing.add(obj["Key"])
    except Exception as exc:
        print(f"WARNING: Could not list R2 objects: {exc}")

    succeeded = 0
    skipped = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for release_tag, filename, r2_key in ASSETS:
            if r2_key in existing:
                print(f"  SKIP: {r2_key} (already in R2)")
                skipped += 1
                continue

            local_path = Path(tmpdir) / filename
            print(f"\n  Downloading {filename} from {release_tag}...")

            result = subprocess.run(
                [
                    "gh",
                    "release",
                    "download",
                    release_tag,
                    "--repo",
                    "reimarus/withourpowerscombined",
                    "--pattern",
                    filename,
                    "--dir",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or not local_path.exists():
                print(f"  FAILED to download {filename}: {result.stderr.strip()}")
                failed += 1
                continue

            size_mb = local_path.stat().st_size / 1_000_000
            print(f"  Uploading {r2_key} ({size_mb:.1f} MB)...")
            try:
                s3.upload_file(str(local_path), BUCKET, r2_key)
                print(f"  OK: {r2_key}")
                succeeded += 1
            except Exception as exc:
                print(f"  FAILED to upload {r2_key}: {exc}")
                failed += 1
            finally:
                local_path.unlink(missing_ok=True)

    print(f"\n=== Migration complete: {succeeded} uploaded, {skipped} skipped, {failed} failed ===")


if __name__ == "__main__":
    main()
