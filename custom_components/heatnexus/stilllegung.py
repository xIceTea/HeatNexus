"""Entitäten stilllegen, die es nach der aktuellen Auswahl nicht mehr gibt.

Eine abgewählte Ebene ist eine Entscheidung: ihre Einträge fallen weg. Ein
Datenpunkt, den die Anlage nicht mehr liefert, wird nur abgeschaltet.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import verwaiste
from .client import WindhagerHttpClient
from .const import DOMAIN, SIGNAL_NEUE_ENTITAETEN
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


def abwahl_vormerken(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Merken, dass der nächste Ladevorgang nach einer Abwahl aufräumen darf."""
    hass.data.setdefault(DOMAIN, {}).setdefault("_abwahl", set()).add(entry.entry_id)


def abwahl_abholen(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Die Vormerkung einlösen – sie gilt genau einmal."""
    offen = hass.data.get(DOMAIN, {}).get("_abwahl")
    if not isinstance(offen, set) or entry.entry_id not in offen:
        return False
    offen.discard(entry.entry_id)
    return True


def abgewaehlte_entitaeten_stilllegen(
    hass: HomeAssistant, entry: ConfigEntry, coordinators: dict
) -> None:
    """Entitäten aufräumen, die es nach der aktuellen Auswahl nicht mehr gibt.

    Was mit ihnen geschieht, hängt davon ab, **warum** sie weg sind:

    * Der Nutzer hat eine Bedienebene **abgewählt** – eine bewusste
      Entscheidung. Dann werden die Einträge gelöscht, sonst stünden sie
      dauerhaft als abgeschaltete Zeilen in der Integrationsübersicht.
    * Die Anlage liefert den Datenpunkt nicht mehr (Umbau, andere Firmware).
      Dann werden sie nur **stillgelegt**: Kommt er zurück, sind eigene Namen,
      Symbole, Bereichszuordnung und Verlauf noch da.
    """
    vollstaendig = all(getattr(c.client, "_vollstaendig", False) for c in coordinators.values())
    if not vollstaendig:
        # Vor dem Vollabzug ist die Liste noch unvollständig – nichts anfassen.
        return

    # **Keine Daten heißt nicht: keine Datenpunkte.** Kommt der Erkennungsstand
    # aus dem Zwischenspeicher, gilt die Anlage sofort als vollständig
    # eingelesen – der erste Abruf kann trotzdem in die Zeitüberschreitung
    # laufen, und `data` bleibt leer. Ohne diese Prüfung ist die Liste der
    # bekannten Datenpunkte dann leer und **jede** Entität des Eintrags gilt
    # als abgewählt – die ganze Anlage läge still und zeigte keinen Wert mehr.
    # Aufgeräumt wird deshalb erst, wenn jede Anlage etwas gemeldet hat.
    if any(not (coordinator.data or {}).get("devices") for coordinator in coordinators.values()):
        _LOGGER.debug("Abruf noch ohne Daten – es wird nichts stillgelegt")
        # Ein Hinweis aus einem früheren Lauf nennt eine Zahl, die hier
        # niemand nachrechnen kann. Kein Hinweis ist besser als ein falscher.
        verwaiste.hinweis_pflegen(hass, entry, 0)
        return

    loeschen = abwahl_abholen(hass, entry)

    # Entitäten der Serviceebene sind absichtlich deaktiviert angelegt; sie
    # dürfen beim Wiederdazuwählen nicht versehentlich eingeschaltet werden.
    standardmaessig_an = verwaiste.bekannte_kennungen(entry, coordinators)
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
    entfernt = 0
    ohne_datenpunkt = 0
    wieder_an = 0
    # Dieselbe Regel wie der Reparatureintrag: Kennung **und** Domäne. Sonst
    # gilt eine Zeile hier als vorhanden, die dort verwaist heißt.
    verwaiste_ids = {e.entity_id for e in verwaiste.finden(hass, entry, coordinators)}
    for eintrag in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
        if eintrag.entity_id in verwaiste_ids:
            if loeschen or quelle_abgeschaltet(eintrag.unique_id, umfaenge):
                registry.async_remove(eintrag.entity_id)
                entfernt += 1
                continue
            ohne_datenpunkt += 1
            if eintrag.disabled_by is None:
                _LOGGER.debug("Lege abgewählte Entität %s still", eintrag.entity_id)
                registry.async_update_entity(
                    eintrag.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
        elif eintrag.unique_id in zusatzwerte and eintrag.disabled_by in (
            None,
            er.RegistryEntryDisabler.INTEGRATION,
        ):
            # Zusatzwerte folgen der Auswahl in den Optionen, auch wenn sie
            # jemand von Hand eingeschaltet hat: Das Häkchen ist die
            # Entscheidung, und ohne diesen Zweig ließe es sich nie zurücknehmen.
            gewuenscht = (
                None
                if standardmaessig_an[eintrag.unique_id]
                else er.RegistryEntryDisabler.INTEGRATION
            )
            if eintrag.disabled_by is not gewuenscht:
                registry.async_update_entity(eintrag.entity_id, disabled_by=gewuenscht)
                wieder_an += gewuenscht is None
        elif (
            standardmaessig_an[eintrag.unique_id]
            and eintrag.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        ):
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
