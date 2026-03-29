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


FIREBASE_VERSION_DATA = {
    "tag": "launcher-v2.0.0",
    "version": "2.0.0",
    "download_url": "https://wopc-cdn.roskvarek.workers.dev/launcher/WOPC-Launcher.exe",
    "size_bytes": 30_000_000,
}


class TestCheckFirebase:
    """Tests for _check_firebase() — Firebase version manifest check."""

    def test_newer_version_returns_update_info(self) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(FIREBASE_VERSION_DATA).encode()

        with patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp):
            result = updater._check_firebase((1, 0, 0))
            assert result is not None
            assert result.version == "2.0.0"
            assert result.tag == "launcher-v2.0.0"
            assert result.download_url.endswith("WOPC-Launcher.exe")
            assert result.size_bytes == 30_000_000

    def test_same_version_returns_none(self) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(FIREBASE_VERSION_DATA).encode()

        with patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp):
            assert updater._check_firebase((2, 0, 0)) is None

    def test_older_version_returns_none(self) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(FIREBASE_VERSION_DATA).encode()

        with patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp):
            assert updater._check_firebase((3, 0, 0)) is None

    def test_null_response_returns_none(self) -> None:
        """Firebase returns 'null' when the node doesn't exist."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"null"

        with patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp):
            assert updater._check_firebase((1, 0, 0)) is None

    def test_network_error_returns_none(self) -> None:
        with patch(
            "launcher.updater.urllib.request.urlopen",
            side_effect=OSError("no network"),
        ):
            assert updater._check_firebase((1, 0, 0)) is None

    def test_malformed_data_returns_none(self) -> None:
        """Missing tag field means we can't parse the version."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"version": "2.0.0"}).encode()

        with patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp):
            # tag="" -> _parse_version returns None -> returns None
            assert updater._check_firebase((1, 0, 0)) is None


class TestCheckForUpdate:
    def test_firebase_checked_before_github(self) -> None:
        """Firebase is the primary source; GitHub is not called if Firebase succeeds."""
        firebase_data = {
            "tag": "launcher-v2.0.0",
            "version": "2.0.0",
            "download_url": "https://cdn.example.com/exe",
            "size_bytes": 30_000_000,
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(firebase_data).encode()

        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp),
        ):
            info = updater.check_for_update()
            assert info is not None
            assert info.version == "2.0.0"
            assert info.download_url == "https://cdn.example.com/exe"

    def test_github_fallback_when_firebase_fails(self) -> None:
        """When Firebase fails, falls back to GitHub API."""
        github_releases = [
            {
                "tag_name": "launcher-v2.0.0",
                "draft": False,
                "prerelease": False,
                "body": "",
                "assets": [
                    {
                        "name": "WOPC-Launcher.exe",
                        "browser_download_url": "https://github.com/example/exe",
                        "size": 30_000_000,
                    }
                ],
            }
        ]

        call_count = 0

        def urlopen_side_effect(req, **kwargs):
            nonlocal call_count
            call_count += 1
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "firebase" in url:
                raise OSError("Firebase down")
            mock = MagicMock()
            mock.read.return_value = json.dumps(github_releases).encode()
            return mock

        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch("launcher.updater.urllib.request.urlopen", side_effect=urlopen_side_effect),
        ):
            info = updater.check_for_update()
            assert info is not None
            assert info.version == "2.0.0"
            assert "github.com" in info.download_url
            assert call_count == 2  # Firebase attempt + GitHub attempt

    def test_finds_newer_version(self) -> None:
        """End-to-end: Firebase returns newer version."""
        firebase_data = {
            "tag": "launcher-v2.0.0",
            "version": "2.0.0",
            "download_url": "https://example.com/WOPC-Launcher.exe",
            "size_bytes": 30_000_000,
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(firebase_data).encode()

        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch("launcher.updater.urllib.request.urlopen", return_value=mock_resp),
        ):
            info = updater.check_for_update()
            assert info is not None
            assert info.version == "2.0.0"

    def test_no_update_when_current(self) -> None:
        firebase_data = {
            "tag": "launcher-v2.0.0",
            "version": "2.0.0",
            "download_url": "https://example.com/exe",
            "size_bytes": 30_000_000,
        }

        call_count = 0

        def urlopen_side_effect(req, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            data = firebase_data if call_count == 1 else FAKE_RELEASES
            mock.read.return_value = json.dumps(data).encode()
            return mock

        with (
            patch.object(updater.config, "VERSION", "2.0.0"),
            patch("launcher.updater.urllib.request.urlopen", side_effect=urlopen_side_effect),
        ):
            info = updater.check_for_update()
            assert info is None

    def test_skips_draft_releases(self) -> None:
        """GitHub fallback skips draft releases."""
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

        call_count = 0

        def urlopen_side_effect(req, **kwargs):
            nonlocal call_count
            call_count += 1
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "firebase" in url:
                raise OSError("Firebase down")
            mock = MagicMock()
            mock.read.return_value = json.dumps(releases).encode()
            return mock

        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch("launcher.updater.urllib.request.urlopen", side_effect=urlopen_side_effect),
        ):
            assert updater.check_for_update() is None

    def test_handles_total_network_failure(self) -> None:
        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch(
                "launcher.updater.urllib.request.urlopen",
                side_effect=OSError("no network"),
            ),
        ):
            assert updater.check_for_update() is None

    def test_retries_on_network_failure(self) -> None:
        """With retry_on_failure=True, GitHub fallback retries once."""
        releases = [
            {
                "tag_name": "launcher-v2.0.0",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "WOPC-Launcher.exe",
                        "browser_download_url": "https://example.com/exe",
                        "size": 30_000_000,
                    }
                ],
                "body": "",
            }
        ]

        call_count = 0

        def side_effect(req, **kwargs):
            nonlocal call_count
            call_count += 1
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "firebase" in url:
                raise OSError("Firebase down")
            # GitHub: fail first attempt, succeed second
            if call_count == 2:
                raise OSError("no network")
            mock = MagicMock()
            mock.read.return_value = json.dumps(releases).encode()
            return mock

        with (
            patch.object(updater.config, "VERSION", "1.0.0"),
            patch("launcher.updater.urllib.request.urlopen", side_effect=side_effect),
            patch("launcher.updater.time.sleep"),
        ):
            result = updater.check_for_update(retry_on_failure=True)
            assert result is not None
            assert result.version == "2.0.0"


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

    def test_cleanup_removes_stale_restart_log_paren(self, tmp_path: Path) -> None:
        """Stale 'restart.log)' from old cmd /c (...) code is cleaned up."""
        stale = tmp_path / "restart.log)"
        stale.write_text("stale content")

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(tmp_path / "WOPC-Launcher.exe")),
        ):
            updater.cleanup_old_exe()

        assert not stale.exists(), "restart.log) should be deleted"

    def test_cleanup_removes_restart_script(self, tmp_path: Path) -> None:
        """_wopc_restart.cmd from previous update is cleaned up."""
        script = tmp_path / "_wopc_restart.cmd"
        script.write_text("@echo off\nrem old script")

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(tmp_path / "WOPC-Launcher.exe")),
        ):
            updater.cleanup_old_exe()

        assert not script.exists(), "_wopc_restart.cmd should be deleted"


class TestRestartSafety:
    """Test that the restart mechanism doesn't use shell=True."""

    def test_restart_uses_script_file_not_shell(self, tmp_path: Path) -> None:
        """apply_update writes a .cmd script instead of inline shell=True."""
        exe = tmp_path / "WOPC-Launcher.exe"
        exe.write_bytes(b"MZ" + b"\x00" * 1000)

        new_exe = tmp_path / "update.exe"
        new_exe.write_bytes(b"MZ" + b"\x00" * 1000)

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(exe)),
            patch.object(updater.sys, "_MEIPASS", str(tmp_path / "_MEI123"), create=True),
            patch("launcher.updater.subprocess.Popen") as mock_popen,
            patch("launcher.updater.os._exit"),
        ):
            updater.apply_update(new_exe)

            # Popen should have been called without shell=True
            assert mock_popen.called, "Popen should have been called for restart"
            call_kwargs = mock_popen.call_args
            assert call_kwargs.kwargs.get("shell") is not True, (
                "shell=True must not be used in restart"
            )
            # First arg should be a list (not a string)
            args = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("args")
            assert isinstance(args, list), "Popen should be called with a list, not a string"

    def test_restart_script_no_mei_deletion(self, tmp_path: Path) -> None:
        """Restart script must NOT delete _MEI dirs (cleanup is deferred)."""
        exe = tmp_path / "WOPC-Launcher.exe"
        exe.write_bytes(b"MZ" + b"\x00" * 1000)
        new_exe = tmp_path / "update.exe"
        new_exe.write_bytes(b"MZ" + b"\x00" * 1000)

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(exe)),
            patch.object(updater.sys, "_MEIPASS", str(tmp_path / "_MEI999"), create=True),
            patch("launcher.updater.subprocess.Popen"),
            patch("launcher.updater.os._exit"),
        ):
            updater.apply_update(new_exe)

        script = (tmp_path / "_wopc_restart.cmd").read_text(encoding="utf-8")
        assert "rmdir /s /q" not in script, "Must not delete _MEI dirs in restart script"

    def test_restart_script_no_start_command(self, tmp_path: Path) -> None:
        """Restart script must launch exe directly, not via 'start'."""
        exe = tmp_path / "WOPC-Launcher.exe"
        exe.write_bytes(b"MZ" + b"\x00" * 1000)
        new_exe = tmp_path / "update.exe"
        new_exe.write_bytes(b"MZ" + b"\x00" * 1000)

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(updater.sys, "executable", str(exe)),
            patch.object(updater.sys, "_MEIPASS", str(tmp_path / "_MEI999"), create=True),
            patch("launcher.updater.subprocess.Popen"),
            patch("launcher.updater.os._exit"),
        ):
            updater.apply_update(new_exe)

        script = (tmp_path / "_wopc_restart.cmd").read_text(encoding="utf-8")
        assert 'start ""' not in script, "Must not use 'start' for exe launch"
        assert f'"{exe}"' in script, "Exe should be invoked directly"
