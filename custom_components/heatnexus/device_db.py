"""Access to the bundled Windhager device database (device_db.json).

The database is generated from the official Windhager files
de-parameters.json (OID names + enum texts) and parameterLayer.json
(which datapoints belong to the Info-/Betreiberebene of each function
type). It enables automatic discovery of function types that have no
hand-curated entity table, e.g. BioWIN or AeroWIN devices.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _db() -> dict:
    path = os.path.join(os.path.dirname(__file__), "device_db.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_name(gnmn: str) -> str | None:
    """German display name for a 'gn/mn' datapoint."""
    return _db()["names"].get(gnmn)


def get_enum(gnmn: str) -> dict[int, str] | None:
    """Enum value->text mapping for a 'gn/mn' datapoint, if any."""
    e = _db()["enums"].get(gnmn)
    if not e:
        return None
    return {int(k): v for k, v in e.items()}


def get_layers(fct_type: int) -> dict | None:
    """Info/operate datapoint lists for a function type."""
    return _db()["layers"].get(str(fct_type))
