"""Tests for launcher.updater — self-update mechanism."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
# Exe verification
# ---------------------------------------------------------------------------


class TestVerifyExe:
    """Tests for _verify_exe() — size + PE header checks."""

    def test_valid_exe(self, tmp_path: Path) -> None:
        """A file >10 MB with MZ header passes verification."""
        exe = tmp_path / "WOPC-Launcher.exe"
        # Write MZ header + padding to exceed _MIN_EXE_SIZE
        exe.write_bytes(b"MZ" + b"\x00" * (updater._MIN_EXE_SIZE + 100))
        updater._verify_exe(exe)  # Should not raise

    def test_rejects_truncated_file(self, tmp_path: Path) -> None:
        """A file smaller than _MIN_EXE_SIZE is rejected."""
        exe = tmp_path / "small.exe"
        exe.write_bytes(b"MZ" + b"\x00" * 1000)
        with pytest.raises(updater.VerificationError, match="truncated"):
            updater._verify_exe(exe)

    def test_rejects_invalid_pe_header(self, tmp_path: Path) -> None:
        """A large file without MZ magic bytes is rejected."""
        exe = tmp_path / "not-a-pe.exe"
        exe.write_bytes(b"PK" + b"\x00" * (updater._MIN_EXE_SIZE + 100))
        with pytest.raises(updater.VerificationError, match="invalid PE header"):
            updater._verify_exe(exe)

    def test_rejects_empty_file(self, tmp_path: Path) -> None:
        """An empty file is rejected (too small)."""
        exe = tmp_path / "empty.exe"
        exe.write_bytes(b"")
        with pytest.raises(updater.VerificationError, match="truncated"):
            updater._verify_exe(exe)


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

    def test_cleanup_reads_restart_log(self, tmp_path: Path) -> None:
        """restart.log from cmd script is read, logged, and deleted."""
        restart_log = tmp_path / "restart.log"
        restart_log.write_text(
            "[03/27/2026 15:44:49] Starting update restart\n"
            "[03/27/2026 15:44:52] Deleting _MEI: C:\\Temp\\_MEI172122\n"
            "[03/27/2026 15:44:53] Launching new exe\n"
            "[03/27/2026 15:44:53] Launch command issued\n",
            encoding="utf-8",
        )

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(tmp_path / "WOPC-Launcher.exe")),
        ):
            updater.cleanup_old_exe()

        assert not restart_log.exists(), "restart.log should be deleted after reading"

    def test_cleanup_logs_old_file_failure(self, tmp_path: Path, caplog) -> None:
        """Failed .old cleanup is logged as a warning, not silently swallowed."""
        old_file = tmp_path / "WOPC-Launcher.old"
        old_file.write_bytes(b"OLD")

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(tmp_path / "WOPC-Launcher.exe")),
            patch.object(Path, "unlink", side_effect=OSError("Permission denied")),
        ):
            updater.cleanup_old_exe()

        assert any("Failed to clean up" in r.message for r in caplog.records)
