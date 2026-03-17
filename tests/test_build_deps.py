"""Tests that all runtime dependencies required for the launcher exe are importable.

These catch silent failures where PyInstaller's --collect-all succeeds but
bundles nothing because the package isn't installed in the build environment.
"""

import importlib

import pytest

# Every package that the launcher exe needs at runtime.
# If any of these fail to import, the built exe will crash on launch.
REQUIRED_PACKAGES = [
    ("customtkinter", "GUI framework — launcher window won't open without it"),
    ("PIL", "Pillow — required by customtkinter for image handling"),
    ("darkdetect", "OS theme detection — required by customtkinter"),
]


@pytest.mark.parametrize(
    "module_name,reason",
    REQUIRED_PACKAGES,
    ids=[p[0] for p in REQUIRED_PACKAGES],
)
def test_runtime_dependency_importable(module_name, reason):
    """Verify that required runtime dependency is installed.

    If this test fails, install the missing package before building the exe.
    PyInstaller's --collect-all silently bundles nothing for missing packages,
    producing a broken exe that crashes on launch.
    """
    try:
        importlib.import_module(module_name)
    except ImportError:
        pytest.fail(
            f"Required package '{module_name}' is not installed. "
            f"Reason: {reason}. "
            f"Install it with: pip install {module_name}"
        )
