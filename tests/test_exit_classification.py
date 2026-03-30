"""Tests for game exit classification and exit code interpretation."""

from __future__ import annotations

from launcher.gui.app import _EXIT_CODE_NAMES, _classify_exit


class TestClassifyExit:
    """Tests for _classify_exit() — exit code + duration → human-readable reason."""

    def test_clean_exit(self) -> None:
        assert _classify_exit(0, 300.0) == "clean exit"

    def test_clean_exit_short_duration(self) -> None:
        """Exit code 0 is always 'clean exit', even if duration < 10s."""
        assert _classify_exit(0, 3.0) == "clean exit"

    def test_access_violation_long_session(self) -> None:
        result = _classify_exit(-1073741819, 120.0)
        assert "crashed" in result
        assert "ACCESS_VIOLATION" in result

    def test_dll_not_found_quick_exit(self) -> None:
        result = _classify_exit(-1073741515, 2.0)
        assert "failed to start" in result
        assert "DLL_NOT_FOUND" in result

    def test_dll_not_found_long_session(self) -> None:
        """DLL_NOT_FOUND after 10s+ is classified as crashed, not failed to start."""
        result = _classify_exit(-1073741515, 15.0)
        assert "crashed" in result
        assert "DLL_NOT_FOUND" in result

    def test_control_c_exit(self) -> None:
        result = _classify_exit(-1073741510, 60.0)
        assert "CONTROL_C_EXIT" in result

    def test_unknown_code_quick(self) -> None:
        result = _classify_exit(42, 5.0)
        assert "failed to start" in result
        assert "42" in result

    def test_unknown_code_long(self) -> None:
        result = _classify_exit(42, 60.0)
        assert "crashed" in result
        assert "42" in result

    def test_general_error(self) -> None:
        result = _classify_exit(1, 30.0)
        assert "crashed" in result
        assert "general error" in result


class TestExitCodeNames:
    """Verify the _EXIT_CODE_NAMES dict has expected entries."""

    def test_contains_common_codes(self) -> None:
        assert 0 in _EXIT_CODE_NAMES
        assert -1073741819 in _EXIT_CODE_NAMES  # ACCESS_VIOLATION
        assert -1073741515 in _EXIT_CODE_NAMES  # DLL_NOT_FOUND

    def test_clean_exit_name(self) -> None:
        assert _EXIT_CODE_NAMES[0] == "clean exit"
