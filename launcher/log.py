"""WOPC logging configuration."""

import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the WOPC launcher.

    Args:
        verbose: If True, set DEBUG level. Otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO

    root = logging.getLogger("wopc")
    root.setLevel(level)

    # Console handler (visible in dev mode, silent in frozen exe)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console)

    # File handler — always write to disk so we can diagnose frozen exe issues.
    # Without this, all logger.info/exception calls vanish in a windowed exe.
    try:
        from logging.handlers import RotatingFileHandler

        from launcher import config

        log_dir = config.WOPC_ROOT
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "launcher.log",
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(fh)
    except Exception:
        pass  # Can't log about logging failure — just proceed without file log
