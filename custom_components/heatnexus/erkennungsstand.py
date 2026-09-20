"""Der Stand einer Anlage: gespeicherte Erkennung und Laufzeitdaten.

Der Erkennungsstand liegt je Anlage im `Store`; sein Umfang (Ebenen,
Freigaben, Intervall, Zugang) entscheidet, ob er noch gilt.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_ADVANCED,
    CONF_KESSELART,
    CONF_KESSELWERT,
    CONF_LEVELS,
    CONF_LON,
    CONF_LON_GRUNDUMFANG,
    CONF_MODULPUMPE,
    CONF_SPRACHE,
    CONF_SYSTEMS,
    CONF_UPDATE_INTERVAL,
    CONF_WRITABLE_ADVANCED,
    CONF_ZEITWERTE,
    CONF_ZUSATZWERTE,
    DEFAULT_LEVELS,
    DEFAULT_USERNAME,
    DISCOVERY_MAX_AGE_DAYS,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .geraetetexte import sprache_aufloesen


def store_key(entry: ConfigEntry, host: str) -> str:
    """Ablageort des Erkennungsstands einer Anlage."""
    return f"{DOMAIN}_discovery_{entry.entry_id}_{host.replace('.', '_')}"


def systems(entry: ConfigEntry) -> list[dict]:
    """Anlagen dieses Eintrags."""
    return list(entry.data.get(CONF_SYSTEMS, []))


# Optionen, die allein das Schaubild betreffen: Sie ändern keine Entität und
# keinen Abruf, also braucht ihre Änderung kein Neuladen.
NUR_ANZEIGE_OPTIONEN = frozenset({CONF_KESSELART, CONF_KESSELWERT, CONF_MODULPUMPE})


def umfang_der_anlage(hass: HomeAssistant, entry: ConfigEntry, host: str) -> dict:
    """Gewählter Umfang einer Anlage (Ebenen, Freigaben, Intervall, Zugang)."""
    options = entry.options or {}
    je_anlage = options.get(host) or {}
    system = next((s for s in systems(entry) if s.get(CONF_HOST) == host), {})
    return {
        "levels": list(je_anlage.get(CONF_LEVELS, DEFAULT_LEVELS)),
        "enable_advanced": bool(je_anlage.get(CONF_ENABLE_ADVANCED, False)),
        "writable_advanced": bool(je_anlage.get(CONF_WRITABLE_ADVANCED, False)),
        "zeitwerte": bool(je_anlage.get(CONF_ZEITWERTE, False)),
        "zusatzwerte": list(je_anlage.get(CONF_ZUSATZWERTE, [])),
        "lon": bool(je_anlage.get(CONF_LON, False)),
        "lon_grundumfang": bool(je_anlage.get(CONF_LON_GRUNDUMFANG, True)),
        "update_interval": int(options.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
        "username": system.get(CONF_USERNAME) or DEFAULT_USERNAME,
        # Aufgelöst, nicht „auto": Sonst läse die Wahl von „auto" auf die
        # gleiche Sprache neu ein, obwohl sich nichts ändert.
        "sprache": sprache_aufloesen(
            options.get(CONF_SPRACHE), getattr(hass.config, "language", None)
        ),
    }


def umfang_fingerprint(scope: dict) -> str:
    """Kennung des Umfangs – ändert er sich, ist der Erkennungsstand ungültig.

    Der Zugang gehört dazu. An der geprüften Baureihe liefern „USER" und
    „Service" zwar dasselbe, für andere ist das nicht belegt – ein Wechsel
    liest deshalb neu ein, statt sich auf eine ungeprüfte Annahme zu stützen.

    Die Sprache gehört nicht dazu. Sie ändert die Bezeichnungen, nicht den
    Bestand an Datenpunkten. Ein Wechsel löst deshalb den Abgleich im
    Hintergrund aus (siehe `abgleich_noetig`) und kein Neueinlesen.
    """
    return (
        ",".join(scope["levels"])
        + f"|{int(scope['enable_advanced'])}{int(scope['writable_advanced'])}"
        + f"{int(scope.get('zeitwerte', False))}{int(scope.get('lon', False))}"
        + f"|{scope.get('username', DEFAULT_USERNAME)}"
        # Nur die Abwahl steht drin. Angehakt ist der Normalfall; stünde er
        # ebenfalls hier, verlöre jede vorhandene Anlage beim Aktualisieren
        # ihren Erkennungsstand und läse minutenlang neu ein.
        + ("" if scope.get("lon_grundumfang", True) else "|ohne-grundumfang")
    )


def discovery_cache_valid(stored, host: str, fingerprint: str) -> bool:
    """Gespeicherten Erkennungsstand auf Gültigkeit prüfen.

    Die Version der Integration steht bewusst **nicht** in dieser Prüfung:
    Sonst läse HeatNexus nach jeder Aktualisierung die ganze Anlage neu ein –
    30 bis 120 Sekunden, in denen kaum etwas dasteht, obwohl sich an der
    Anlage nichts geändert hat. Ein Versionswechsel löst stattdessen einen
    Abgleich im Hintergrund aus (siehe `abgleich_noetig`): Die bekannten Werte
    sind sofort da, Neues kommt nach. Dasselbe gilt für einen Sprachwechsel –
    er ändert Bezeichnungen, nicht den Bestand.

    Was den Stand weiterhin verwirft: eine andere Anlage, ein geänderter
    Umfang (Ebenen, Freigaben, Zugang), zu hohes Alter – und der Dienst
    `heatnexus.rediscover`.
    """
    if not isinstance(stored, dict) or "data" not in stored:
        return False
    if stored.get("host") != host:
        return False
    if stored.get("scope") != fingerprint:
        return False
    saved = dt_util.parse_datetime(stored.get("saved") or "")
    if saved is None:
        return False
    return (dt_util.utcnow() - saved).days <= DISCOVERY_MAX_AGE_DAYS


def abgleich_noetig(stored, version: str, sprache: str) -> bool:
    """Prüfen, ob der Stand im Hintergrund gegen die Anlage abzugleichen ist.

    Zwei Gründe: Er stammt aus einer anderen Fassung der Integration, oder aus
    einer anderen Sprache. Beide ändern nur, was in den Deskriptoren steht –
    nicht, welche Datenpunkte es gibt. Der gespeicherte Stand bleibt also
    gültig und ist sofort da; was sich geändert hat, kommt nach.
    """
    if not isinstance(stored, dict):
        return False
    return stored.get("version") != version or stored.get("sprache", "de") != sprache


def neustart_hinweis(hass: HomeAssistant, entry: ConfigEntry, host: str, faellig: bool) -> None:
    """Reparatureintrag: Die Sprache wurde gewechselt, ein Neustart fehlt noch.

    Ein Entitätsname entsteht bei der Erzeugung. Der Abgleich im Hintergrund
    schreibt die neuen Bezeichnungen in den Erkennungsstand; sichtbar werden
    sie erst, wenn die Entitäten das nächste Mal entstehen. Der Eintrag löst
    sich beim nächsten Start von selbst auf.
    """
    kennung = f"sprache_neustart_{entry.entry_id}_{host}"
    if not faellig:
        ir.async_delete_issue(hass, DOMAIN, kennung)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        kennung,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="sprache_neustart",
    )


def laufzeitdaten(entry: ConfigEntry) -> dict | None:
    """Die Laufzeitdaten eines Konfigurationseintrags, falls er geladen ist.

    `runtime_data` gibt es erst, wenn `async_setup_entry` durchgelaufen ist –
    ein direkter Zugriff scheitert vorher mit `AttributeError`. Aufgerufen wird
    das auch aus Pfaden, die während des Ladens laufen (Dashboard, Panel,
    Meldung nach dem Einlesen).
    """
    daten = getattr(entry, "runtime_data", None)
    return daten if isinstance(daten, dict) else None


def nur_anzeige_geaendert(alt: dict, neu: dict) -> bool:
    """Ob sich ausschließlich Optionen des Schaubilds geändert haben.

    Sie ändern kein Entität und keinen Abruf – nur die Zeichnung. Ein
    Neuladen dafür risse jeden Verlauf für einen Takt auf „nicht verfügbar".
    """
    if not alt or set(alt) != set(neu):
        return False
    nur_anzeige = True
    for schluessel, wert in neu.items():
        vorher = alt.get(schluessel)
        if wert == vorher:
            continue
        if not isinstance(wert, dict) or not isinstance(vorher, dict):
            return False
        geaendert = {k for k in set(wert) | set(vorher) if wert.get(k) != vorher.get(k)}
        if geaendert - NUR_ANZEIGE_OPTIONEN:
            return False
        nur_anzeige = nur_anzeige and bool(geaendert)
    return nur_anzeige
