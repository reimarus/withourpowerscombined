"""Tests for launcher.updater — self-update mechanism."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from launcher import updater

# ---------------------------------------------------------------------------
# Version parsing
# ---------------------------------------------------------------------------


class TestVersionParsing:
    def test_parse_valid_tag(self) -> None:
        assert updater._parse_version("launcher-v1.2.3") == (1, 2, 3)

    def test_parse_two_part(self) -> None:
        assert updater._parse_version("launcher-v1.0") == (1, 0)

    def test_parse_single(self) -> None:
        assert updater._parse_version("launcher-v5") == (5,)

    def test_rejects_bad_prefix(self) -> None:
        assert updater._parse_version("content-v1") is None

    def test_rejects_non_numeric(self) -> None:
        assert updater._parse_version("launcher-vfoo") is None

    def test_rejects_empty(self) -> None:
        assert updater._parse_version("") is None

    def test_current_version_tuple(self) -> None:
        with patch.object(updater.config, "VERSION", "1.2.3"):
            assert updater._current_version_tuple() == (1, 2, 3)

    def test_current_version_dev(self) -> None:
        with patch.object(updater.config, "VERSION", "0.1.0-dev"):
            assert updater._current_version_tuple() == (0, 1, 0)


# ---------------------------------------------------------------------------
# Update check
# ---------------------------------------------------------------------------

FAKE_RELEASES = [
    {
        "tag_name": "launcher-v2.0.0",
        "draft": False,
        "prerelease": False,
        "body": "New features!",
        "assets": [
            {
                "name": "WOPC-Launcher.exe",
                "browser_download_url": "https://example.com/WOPC-Launcher.exe",
                "size": 30_000_000,
            }
        ],
    },
    {
        "tag_name": "launcher-v1.0.0",
        "draft": False,
        "prerelease": False,
        "body": "Initial release",
        "assets": [
            {
                "name": "WOPC-Launcher.exe",
                "browser_download_url": "https://example.com/old.exe",
                "size": 20_000_000,
            }
        ],
    },
    {
        "tag_name": "content-v1",
        "draft": False,
        "prerelease": False,
        "body": "Content pack",
        "assets": [],
    },
]


class TestCheckForUpdate:
    def test_finds_newer_version(self) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(FAKE_RELEASES).encode()

        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp),
        ):
            info = updater.check_for_update()
            assert info is not None
            assert info.version == "2.0.0"
            assert info.download_url == "https://example.com/WOPC-Launcher.exe"
            assert info.size_bytes == 30_000_000

    def test_no_update_when_current(self) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(FAKE_RELEASES).encode()

        with (
            patch.object(updater.config, "VERSION", "2.0.0"),
            patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp),
        ):
            info = updater.check_for_update()
            assert info is None

    def test_skips_draft_releases(self) -> None:
        releases = [
            {
                "tag_name": "launcher-v3.0.0",
                "draft": True,
                "prerelease": False,
                "body": "",
                "assets": [
                    {
                        "name": "WOPC-Launcher.exe",
                        "browser_download_url": "https://example.com/draft.exe",
                        "size": 30_000_000,
                    }
                ],
            }
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(releases).encode()

        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp),
        ):
            assert updater.check_for_update() is None

    def test_handles_network_error(self) -> None:
        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch(
                "launcher.updater.urllib.request.urlopen",
                side_effect=OSError("no network"),
            ),
        ):
            assert updater.check_for_update() is None


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


class TestDownloadUpdate:
    def test_skips_in_non_frozen(self) -> None:
        info = updater.UpdateInfo(
            tag="launcher-v2.0.0",
            version="2.0.0",
            download_url="https://example.com/exe",
            size_bytes=1000,
            body="",
        )
        with patch.object(updater.sys, "frozen", False, create=True):
            result = updater.download_update(info)
            assert result is None


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_cleanup_removes_old(self, tmp_path: Path) -> None:
        old_file = tmp_path / "WOPC-Launcher.old"
        old_file.write_bytes(b"OLD")

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(tmp_path / "WOPC-Launcher.exe")),
        ):
            updater.cleanup_old_exe()
            assert not old_file.exists()

    def test_cleanup_noop_without_old(self, tmp_path: Path) -> None:
        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(tmp_path / "WOPC-Launcher.exe")),
        ):
            updater.cleanup_old_exe()  # Should not raise

    def test_cleanup_noop_non_frozen(self) -> None:
        # Should silently do nothing
        updater.cleanup_old_exe()
