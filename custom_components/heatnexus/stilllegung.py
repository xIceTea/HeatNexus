"""Entitäten stilllegen, die es nach der aktuellen Auswahl nicht mehr gibt.

Eine abgewählte Ebene ist eine Entscheidung: ihre Einträge fallen weg. Ein
Datenpunkt, den die Anlage nicht mehr liefert, wird nur abgeschaltet.
"""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import geraete, kanonisch, verwaiste
from .client import WindhagerHttpClient
from .const import ADVANCED_LEVELS, DOMAIN, SIGNAL_NEUE_ENTITAETEN
from .erkennungsstand import laufzeitdaten

_LOGGER = logging.getLogger(__name__)


def umfang_verkleinert(alt: dict[str, dict], neu: dict[str, dict]) -> bool:
    """Prüfen, ob der Nutzer am Umfang etwas abgewählt hat.

    Nur dann werden Entitäten wirklich gelöscht. Fällt dagegen ein Datenpunkt
    weg, weil ihn die Anlage nicht mehr liefert, steckt keine Entscheidung
    dahinter – dort wird nur stillgelegt.

    Als Abwahl gilt jeder Schalter des Umfangs, der von an auf aus ging, und
    jede Liste, aus der etwas verschwand. Intervall, Zugang und Sprache sind
    weder Schalter noch Liste und entfernen auch keinen Datenpunkt.
    """
    for host, alt_umfang in alt.items():
        neu_umfang = neu.get(host)
        if neu_umfang is None:
            return True
        for schluessel, alt_wert in alt_umfang.items():
            neu_wert = neu_umfang.get(schluessel)
            if isinstance(alt_wert, bool) and alt_wert and not neu_wert:
                return True
            # Die Differenz statt der echten Teilmenge: Wer eine Ebene abwählt
            # und gleichzeitig eine andere hinzunimmt, hat trotzdem abgewählt.
            if isinstance(alt_wert, list) and set(alt_wert) - set(neu_wert or ()):
                return True
    return False


def _teil_der_abwahl(alt: dict, neu: dict) -> Callable[[dict], bool]:
    """Prüfung, ob eine alte Beschreibung zum abgewählten Teil des Umfangs gehört."""
    ebenen = set(alt.get("levels") or ()) - set(neu.get("levels") or ())
    zusatz = set(alt.get("zusatzwerte") or ()) - set(neu.get("zusatzwerte") or ())
    fach_gesperrt = bool(alt.get("writable_advanced")) and not neu.get("writable_advanced")
    bus_weg = any(alt.get(s) and not neu.get(s) for s in ("lon", "lon_grundumfang"))

    def passt(beschreibung: dict) -> bool:
        kennung = beschreibung.get("id") or ""
        ebene = beschreibung.get("level")
        return (
            ebene in ebenen
            or kennung in zusatz
            or (fach_gesperrt and ebene in ADVANCED_LEVELS)
            or (bus_weg and "-nv-" in kennung)
        )

    return passt


def abgewaehlte_kennungen(
    alt: dict, neu: dict | None, beschreibungen: list[dict]
) -> dict[str, str | None]:
    """Kennung und Gerät jeder alten Beschreibung, die der Nutzer abgewählt hat.

    Das Gerät ist None, wenn die ganze Anlage wegfiel. Sonst schützt es die
    Waisen eines Geräts, das beim neuen Einlesen gar nicht antwortete.
    """
    if neu is None:
        return {d["id"]: None for d in beschreibungen if d.get("id")}
    passt = _teil_der_abwahl(alt, neu)
    return {d["id"]: d.get("device_id") or "" for d in beschreibungen if d.get("id") and passt(d)}


def abwahl_aus_stand(stored, scope: dict) -> dict[str, str | None]:
    """Die abgewählten Kennungen, abgelesen am gespeicherten Stand einer Anlage."""
    if not abwahl_im_stand(stored, scope):
        return {}
    beschreibungen = (stored.get("data") or {}).get("devices") or []
    return abgewaehlte_kennungen(stored["umfang"], scope, beschreibungen)


def abwahl_im_stand(stored, scope: dict) -> bool:
    """Ob der gespeicherte Stand einen größeren Umfang nennt als der aktuelle.

    Der Vergleich im Arbeitsspeicher kennt nur den Moment der Änderung, der
    Stand auf der Platte überlebt den Neustart. Ein Stand ohne `umfang` stammt
    aus einer älteren Fassung und löst nichts aus.
    """
    if not isinstance(stored, dict):
        return False
    alt = stored.get("umfang")
    if not isinstance(alt, dict):
        return False
    return umfang_verkleinert({"anlage": alt}, {"anlage": scope})


def quelle_abgeschaltet(unique_id: str | None, umfaenge: dict[str, dict]) -> bool:
    """Ob eine Waise zu einer Quelle gehört, die der Nutzer abgeschaltet hat.

    Netzwerkvariablen tragen `-nv-` in der Kennung (`lon.kennungsteil`); bei
    abgewähltem Bus sind sie der Rest einer Entscheidung und werden gelöscht.
    Für alles andere entscheidet der Umfangsvergleich.
    """
    if "-nv-" not in (unique_id or ""):
        return False
    return not any(umfang.get("lon") for umfang in umfaenge.values())


# Was HeatNexus selbst aus dem Umfang genommen hat, je Domäne und Adresse. Verwaist ist das
# keine Lücke der Anlage, sondern eine Entscheidung: Es wird gelöscht, nicht stillgelegt.
# Ein Eingabefeld auf einer Adresse, die nur Anzeige ist, gehört dazu.
BEWUSST_ENTFALLEN: frozenset[tuple[str, str]] = frozenset(
    {("select", "9/75"), ("select", "39/94")}
    | {("number", adresse) for adressen in geraete.NUR_ANZEIGE.values() for adresse in adressen}
)

# Einzelne Entitäten, die HeatNexus durch eine andere ersetzt hat: Domäne und Kennungsende.
# Der Schalter der Automatik ging in der Auswahl „Automatik-Modus" auf.
ERSETZT: frozenset[tuple[str, str]] = frozenset({("switch", "-automatik-schalter")})


def endgueltig_weg(eintrag: er.RegistryEntry, umfaenge: dict[str, dict]) -> bool:
    """Ob eine Waise gelöscht wird statt stillgelegt, ohne dass der Nutzer etwas abwählte."""
    if (eintrag.domain, kanonisch.gnmn(eintrag.unique_id)) in BEWUSST_ENTFALLEN:
        return True
    kennung = eintrag.unique_id or ""
    if any(eintrag.domain == d and kennung.endswith(ende) for d, ende in ERSETZT):
        return True
    return quelle_abgeschaltet(eintrag.unique_id, umfaenge)


def abwahl_vormerken(
    hass: HomeAssistant, entry: ConfigEntry, kennungen: dict[str, str | None]
) -> None:
    """Merken, welche Kennungen der nächste Ladevorgang nach einer Abwahl löschen darf."""
    offen = hass.data.setdefault(DOMAIN, {}).setdefault("_abwahl", {})
    offen[entry.entry_id] = {**offen.get(entry.entry_id, {}), **kennungen}


def abwahl_abholen(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, str | None]:
    """Die Vormerkung einlösen – sie gilt genau einmal."""
    offen = hass.data.get(DOMAIN, {}).get("_abwahl")
    if not isinstance(offen, dict):
        return {}
    return offen.pop(entry.entry_id, {})


def _abgewaehlt(unique_id: str | None, abgewaehlt: dict[str, str | None], geantwortet: set) -> bool:
    """Ob eine Waise zum abgewählten Teil gehört und ihr Gerät beim Einlesen antwortete."""
    if unique_id not in abgewaehlt:
        return False
    geraet = abgewaehlt[unique_id]
    # Ein Gerät ohne jeden Datenpunkt hat nicht geantwortet; seine Entitäten bleiben.
    return geraet is None or geraet in geantwortet


def _abgleich_moeglich(hass: HomeAssistant, entry: ConfigEntry, coordinators: dict) -> bool:
    """Ob der Bestand der Anlage für den Abgleich taugt."""
    if not all(getattr(c.client, "_vollstaendig", False) for c in coordinators.values()):
        # Vor dem Vollabzug ist die Liste noch unvollständig – nichts anfassen.
        return False
    # Keine Daten heißen nicht: keine Datenpunkte. Ein Erkennungsstand aus dem
    # Zwischenspeicher gilt sofort als vollständig, der erste Abruf kann aber
    # in die Zeitüberschreitung laufen. Dann gälte jede Entität als abgewählt.
    if any(not (coordinator.data or {}).get("devices") for coordinator in coordinators.values()):
        _LOGGER.debug("Abruf noch ohne Daten – es wird nichts stillgelegt")
        # Ein früherer Hinweis nennt eine Zahl, die hier niemand nachrechnen kann.
        verwaiste.hinweis_pflegen(hass, entry, 0)
        return False
    return True


def _zusatzwert_nachziehen(
    registry: er.EntityRegistry, eintrag: er.RegistryEntry, standardmaessig_an: bool
) -> int:
    """Einen Zusatzwert der Auswahl in den Optionen folgen lassen; 1, wenn er wieder an ist.

    Das Häkchen ist die Entscheidung, auch wenn jemand den Wert von Hand
    eingeschaltet hat. Sonst ließe es sich nie zurücknehmen.
    """
    gewuenscht = None if standardmaessig_an else er.RegistryEntryDisabler.INTEGRATION
    if eintrag.disabled_by is gewuenscht:
        return 0
    registry.async_update_entity(eintrag.entity_id, disabled_by=gewuenscht)
    return int(gewuenscht is None)


def _verwaiste_behandeln(
    registry: er.EntityRegistry, eintrag: er.RegistryEntry, entfernen: bool
) -> bool:
    """Eine Waise löschen oder stilllegen; True, wenn sie stehen bleibt."""
    if entfernen:
        registry.async_remove(eintrag.entity_id)
        return False
    if eintrag.disabled_by is None:
        _LOGGER.debug("Lege abgewählte Entität %s still", eintrag.entity_id)
        registry.async_update_entity(
            eintrag.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
        )
    return True


def abgewaehlte_entitaeten_stilllegen(
    hass: HomeAssistant, entry: ConfigEntry, coordinators: dict
) -> None:
    """Entitäten aufräumen, die es nach der aktuellen Auswahl nicht mehr gibt.

    Was mit ihnen geschieht, hängt davon ab, **warum** sie weg sind:

    * Der Nutzer hat eine Bedienebene **abgewählt** – eine bewusste
      Entscheidung. Dann werden ihre Einträge gelöscht, sonst stünden sie
      dauerhaft als abgeschaltete Zeilen in der Integrationsübersicht.
    * Die Anlage liefert den Datenpunkt nicht mehr (Umbau, andere Firmware).
      Dann werden sie nur **stillgelegt**: Kommt er zurück, sind eigene Namen,
      Symbole, Bereichszuordnung und Verlauf noch da.
    """
    if not _abgleich_moeglich(hass, entry, coordinators):
        return

    abgewaehlt = abwahl_abholen(hass, entry)
    geantwortet = {
        beschreibung.get("device_id")
        for coordinator in coordinators.values()
        for beschreibung in (coordinator.data or {}).get("devices", [])
    }
    # Entitäten der Serviceebene sind absichtlich deaktiviert angelegt; sie
    # dürfen beim Wiederdazuwählen nicht versehentlich eingeschaltet werden.
    standardmaessig_an = verwaiste.bekannte_kennungen(entry, coordinators, hass)
    # Die selbst gebildeten Werte: Nur bei ihnen schlägt die Auswahl eine
    # Einschaltung von Hand.
    zusatzwerte = {
        beschreibung.get("id")
        for coordinator in coordinators.values()
        for beschreibung in (coordinator.data or {}).get("devices", [])
        if beschreibung.get("type") in WindhagerHttpClient.ZUSATZTYPEN
    }
    umfaenge = (laufzeitdaten(entry) or {}).get("umfang") or {}
    registry = er.async_get(hass)
    entfernt = ohne_datenpunkt = wieder_an = 0
    # Dieselbe Regel wie der Reparatureintrag: Kennung **und** Domäne. Sonst
    # gilt eine Zeile hier als vorhanden, die dort verwaist heißt.
    verwaiste_ids = {e.entity_id for e in verwaiste.finden(hass, entry, coordinators)}
    von_integration = er.RegistryEntryDisabler.INTEGRATION
    for eintrag in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
        if eintrag.entity_id in verwaiste_ids:
            entfernen = endgueltig_weg(eintrag, umfaenge) or _abgewaehlt(
                eintrag.unique_id, abgewaehlt, geantwortet
            )
            if _verwaiste_behandeln(registry, eintrag, entfernen):
                ohne_datenpunkt += 1
            else:
                entfernt += 1
        elif eintrag.unique_id in zusatzwerte and eintrag.disabled_by in (None, von_integration):
            wieder_an += _zusatzwert_nachziehen(
                registry, eintrag, standardmaessig_an[eintrag.unique_id]
            )
        elif standardmaessig_an[eintrag.unique_id] and eintrag.disabled_by is von_integration:
            # Wieder dazugewählt – die eigene Stilllegung wird aufgehoben.
            # Eine Abschaltung durch den Nutzer (disabled_by USER) bleibt.
            _LOGGER.debug("Nehme %s wieder in Betrieb", eintrag.entity_id)
            registry.async_update_entity(eintrag.entity_id, disabled_by=None)
            wieder_an += 1

    if entfernt:
        _LOGGER.info(
            "%d Entitäten entfernt, weil ihre Bedienebene abgewählt wurde. "
            "Beim Wiederdazuwählen werden sie neu angelegt.",
            entfernt,
        )
    # Die Plattformen stehen zu diesem Zeitpunkt schon; eine gerade
    # eingeschaltete Entität entstünde sonst erst beim nächsten Laden.
    if wieder_an:
        async_dispatcher_send(hass, SIGNAL_NEUE_ENTITAETEN.format(entry.entry_id))
    # Stillgelegte ohne Datenpunkt bleiben stehen. Ob sie verschwinden, ist
    # eine Entscheidung des Nutzers – der Reparatureintrag holt sie ein.
    verwaiste.hinweis_pflegen(hass, entry, ohne_datenpunkt)
