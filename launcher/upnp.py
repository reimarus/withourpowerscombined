"""UPnP port mapping for multiplayer lobby.

Attempts to automatically open a TCP port on the user's router via UPnP.
Falls back gracefully if the ``miniupnpc`` library is unavailable or if the
router doesn't support UPnP.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("wopc.upnp")

# Best-effort import — miniupnpc is an optional dependency.
try:
    import miniupnpc  # type: ignore[import-untyped]

    _HAS_UPNP = True
except ImportError:
    _HAS_UPNP = False


def _get_upnp() -> miniupnpc.UPnP | None:
    """Create and discover a UPnP device, or return *None* on failure."""
    if not _HAS_UPNP:
        logger.info("miniupnpc not installed — UPnP unavailable")
        return None
    try:
        u = miniupnpc.UPnP()
        u.discoverdelay = 2000  # ms
        n = u.discover()
        if n == 0:
            logger.warning("No UPnP devices found on the network")
            return None
        u.selectigd()
        return u
    except Exception as exc:
        logger.warning("UPnP discovery failed: %s", exc)
        return None


def try_open_port(port: int, description: str = "WOPC Lobby") -> bool:
    """Try to add a UPnP port mapping for *port* (TCP).

    Returns ``True`` if the mapping was successfully added, ``False`` otherwise.
    Never raises — all errors are caught and logged.
    """
    u = _get_upnp()
    if u is None:
        return False
    try:
        local_ip = u.lanaddr
        result = u.addportmapping(port, "TCP", local_ip, port, description, "")
        if result:
            logger.info("UPnP: mapped external TCP %d → %s:%d", port, local_ip, port)
            return True
        logger.warning("UPnP: addportmapping returned falsy for port %d", port)
        return False
    except Exception as exc:
        logger.warning("UPnP: failed to map port %d: %s", port, exc)
        return False


def close_port(port: int) -> None:
    """Remove a previously added UPnP port mapping.  Best-effort."""
    u = _get_upnp()
    if u is None:
        return
    try:
        u.deleteportmapping(port, "TCP")
        logger.info("UPnP: removed mapping for TCP port %d", port)
    except Exception as exc:
        logger.debug("UPnP: failed to remove mapping for port %d: %s", port, exc)
