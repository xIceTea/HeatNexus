"""Die vergangenen Stunden des heutigen Tages aus der Aufzeichnung nachtragen.

Die Stundenprognose beginnt mit der laufenden Stunde, und gesammelt wird erst
ab dem Start. Einmal je Start liest die Automatik deshalb den heutigen Tag nach.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import eingaben

if TYPE_CHECKING:
    from .laufzeit import Laufzeit

_LOGGER = logging.getLogger(__name__)
UNGUELTIG = frozenset({"unavailable", "unknown", "none", ""})


def _zahl(wert: Any) -> float | None:
    try:
        return None if wert is None or str(wert) in UNGUELTIG else float(wert)
    except (TypeError, ValueError):
        return None


def _reihe(zustaende: list[Any], merkmal: str | None = None) -> list[tuple[datetime, float]]:
    """Zeitreihe aus Zuständen; mit `merkmal` aus einem Attribut statt dem Zustand."""
    reihe = []
    for zustand in zustaende:
        roh = zustand.attributes.get(merkmal) if merkmal else zustand.state
        if (wert := _zahl(roh)) is not None:
            reihe.append((dt_util.as_local(zustand.last_updated), wert))
    return reihe


async def heute_nachtragen(hass: HomeAssistant, laufzeit: Laufzeit) -> None:
    """Fehlende Stunden von heute mit Wetter, Außen- und Raumtemperatur füllen."""
    if "recorder" not in hass.config.components:
        return
    from homeassistant.components.recorder import get_instance, history

    jetzt = dt_util.now()
    anfang = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    k = laufzeit.konfig
    aussen = laufzeit.aussen_entitaet()
    kennungen = [k["wetter"], *k["raeume"], *([aussen] if aussen else [])]
    abfrage = partial(
        history.get_significant_states,
        hass,
        anfang,
        jetzt,
        kennungen,
        significant_changes_only=False,
    )
    try:
        zustaende = await get_instance(hass).async_add_executor_job(abfrage)
    except Exception as fehler:  # die Aufzeichnung ist eine Zugabe, kein Muss
        _LOGGER.debug("Automatik %s: heutiger Tag nicht nachladbar: %s", laufzeit.name, fehler)
        return
    wetter = zustaende.get(k["wetter"], [])
    temperaturen = _reihe(wetter, "temperature")
    wolken = _reihe(wetter, "cloud_coverage")
    aussenreihe = _reihe(zustaende.get(aussen, [])) if aussen else []
    raeume = [_reihe(zustaende.get(raum, [])) for raum in k["raeume"]]
    stufen = None
    for stunde in range(jetzt.hour):
        zeit = anfang + timedelta(hours=stunde)
        at = eingaben.wert_zur_stunde(aussenreihe, zeit)
        # Die gedämpfte AT der vergangenen Stunden aus den Messwerten nachrechnen.
        if at is not None:
            stufen = eingaben.daempfen(stufen, at, 3600, laufzeit.werte.tau_h)
        laufzeit.stunde_nachtragen(
            stunde,
            gedaempft=round(stufen[1], 2) if stufen else None,
            prognose=eingaben.wert_zur_stunde(temperaturen, zeit),
            wolken=eingaben.wert_zur_stunde(wolken, zeit),
            at=at,
            raum=eingaben.raumwert(
                [eingaben.wert_zur_stunde(reihe, zeit) for reihe in raeume], k["raum_art"]
            ),
        )
    if stufen is not None:
        laufzeit.stufen_uebernehmen(stufen, anfang + timedelta(hours=max(jetzt.hour - 1, 0)))
    laufzeit.nachgetragen()
