"""WOPC logging configuration."""

import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the WOPC launcher.

    Args:
        verbose: If True, set DEBUG level. Otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger("wopc")
    root.setLevel(level)
    root.addHandler(handler)
