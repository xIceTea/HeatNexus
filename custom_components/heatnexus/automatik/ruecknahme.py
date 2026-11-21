"""Nur Warmwasser zurücknehmen, wenn der Eintrag entfernt wird und keine Automatik mehr läuft.

`3/50` läuft an der Steuerung nicht von selbst ab; ohne Rücknahme bliebe der Heizkreis aus.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from ..client import WindhagerHttpClient
from ..const import CONF_SYSTEMS, DEFAULT_USERNAME
from . import regel
from .steller import OID_BETRIEBSWAHL, PROGRAMM_1, WW_LADUNG, Stand

BETRIEBSART = "/2/9/0"

_LOGGER = logging.getLogger(__name__)


def offene_betriebswahl(zustand: Any) -> tuple[str, str, int, int] | None:
    """Host, Adresse, geschriebener und vorheriger Wert, wenn eigenes nur Warmwasser im Store steht."""
    if not isinstance(zustand, Mapping):
        return None
    g = regel.gedaechtnis_aus_dict(zustand.get("gedaechtnis"))
    stand = Stand.aus_dict(zustand.get("stand"))
    host, prefix = zustand.get("host"), zustand.get("prefix")
    # Nur ein geschriebener Wert setzt `erwartet`; im Beobachten bleibt es leer.
    if (
        g.saison != regel.NUR_WW
        or stand.erwartet is None
        or not host
        or not isinstance(prefix, str)
    ):
        return None
    vorher = PROGRAMM_1 if stand.betriebswahl_vorher is None else stand.betriebswahl_vorher
    return str(host), f"{prefix}{OID_BETRIEBSWAHL}", stand.erwartet, vorher


def _verbindung(host: str, passwort: str, benutzer: str) -> Any:
    return WindhagerHttpClient(host=host, password=passwort, username=benutzer)


def _ganzzahl(wert: Any) -> int | None:
    try:
        return int(float(wert))
    except (TypeError, ValueError):
        return None


async def nach_dem_entfernen(entry: ConfigEntry, zustaende: Iterable[Any]) -> None:
    """Eigenes nur Warmwasser zurückstellen; eine inzwischen geänderte Betriebswahl bleibt stehen."""
    offen = [o for zustand in zustaende if (o := offene_betriebswahl(zustand)) is not None]
    if not offen:
        return
    zugang = {s.get(CONF_HOST): s for s in (entry.data or {}).get(CONF_SYSTEMS) or ()}
    for host, oid, erwartet, vorher in offen:
        if (system := zugang.get(host)) is None:
            _LOGGER.warning("Automatik: Anlage %s unbekannt, %s bleibt auf %s", host, oid, erwartet)
            continue
        benutzer = system.get(CONF_USERNAME) or DEFAULT_USERNAME
        verbindung = _verbindung(host, system.get(CONF_PASSWORD), benutzer)
        try:
            await _zurueckstellen(verbindung, oid, erwartet, vorher)
        except Exception as fehler:  # das Entfernen des Eintrags geht weiter
            _LOGGER.warning("Automatik: %s nicht zurückgestellt: %s", oid, fehler)
        finally:
            await verbindung.close()


async def _zurueckstellen(verbindung: Any, oid: str, erwartet: int, vorher: int) -> None:
    betriebsart = oid.removesuffix(OID_BETRIEBSWAHL) + BETRIEBSART
    werte = await verbindung.fetch_oids([oid, betriebsart])
    aktuell = _ganzzahl(werte.get(oid))
    # Während der Warmwasserladung stellt die Steuerung `3/50` selbst um.
    if aktuell != erwartet and _ganzzahl(werte.get(betriebsart)) not in WW_LADUNG:
        _LOGGER.info("Automatik: %s steht auf %s, nicht zurückgestellt", oid, aktuell)
        return
    await verbindung.update(oid, str(vorher))
    _LOGGER.info("Automatik: %s auf %s zurückgestellt", oid, vorher)
