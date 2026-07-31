"""Helper functions for Windhager integration."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def parse_value(value: Any, as_type: type = float, oid: str | None = None) -> Any | None:
    """Safely parse a value with error handling."""
    if value is None:
        return None
    try:
        if as_type is int:
            return int(float(value))
        return as_type(value)
    except (ValueError, TypeError):
        _LOGGER.debug("Invalid value %r for %s", value, oid)
        return None


def get_oid_raw(coordinator: Any, oid: str, prefix: str = "") -> str | None:
    """Get the raw string value for an OID (or None)."""
    if not coordinator.data:
        return None
    return coordinator.data.get("oids", {}).get(f"{prefix}{oid}")


def get_oid_value(
    coordinator: Any, oid: str, prefix: str = "", default: Any = None
) -> float | None:
    """Get OID value as float with error handling.

    NOTE: default is None on purpose. The old default of "0" masked missing
    values as 0.0, which made frozen/broken datapoints look like real data.
    """
    full_path = f"{prefix}{oid}"
    value = get_oid_raw(coordinator, oid, prefix)
    if value is None:
        value = default
    return parse_value(value, float, full_path)
