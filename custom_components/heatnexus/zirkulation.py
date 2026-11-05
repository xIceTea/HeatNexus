"""Die Zirkulationspumpe, die nach ihren Schaltzeiten nie läuft."""

from __future__ import annotations

from typing import Any

_MODUS = "5/6/0"
_PROGRAMM = "5/65/0"
# `5/6`: 1 Zeitsteuerung, 3 Impulssteuerung. Beide folgen den Schaltzeiten aus `5/65`.
_MODI_MIT_SCHALTZEITEN = (1, 3)


def _schaltet_nie(bloecke: list[dict[str, Any]]) -> bool:
    """Schaltzeiten sind da, aber keine schaltet ein."""
    punkte = [punkt for block in bloecke for punkt in block.get("switchPoints") or []]
    return bool(punkte) and all(punkt.get("value") == 0 for punkt in punkte)


def steht_still(daten: dict[str, Any]) -> bool | None:
    """Ob eine Zirkulationspumpe der Anlage nie läuft; `None`, solange Modus oder Programm fehlen."""
    stillstand = None
    for oid, bloecke in (daten.get("objects") or {}).items():
        if not oid.endswith(f"/{_PROGRAMM}") or not isinstance(bloecke, list):
            continue
        modus = (daten.get("oids") or {}).get(oid.removesuffix(_PROGRAMM) + _MODUS)
        try:
            modus = int(float(modus))
        except (TypeError, ValueError):
            continue
        stillstand = bool(stillstand) or (
            modus in _MODI_MIT_SCHALTZEITEN and _schaltet_nie(bloecke)
        )
    return stillstand
