"""Sensoren für Störungen und Meldungen: Code, Klartext, Zustand, fortlaufende Liste."""

from __future__ import annotations

import contextlib
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from ..const import ERROR_TEXTS
from ..entity import MeldungsQuelle, WindhagerEntity
from ..error_texts import keine_stoerung, klartext, parse_messages, textsprache, unbekannt
from .stoerspeicher import eintraege_aufbereiten, zuruecksetzen_erlaubt


class WindhagerErrorTextSensor(WindhagerEntity, SensorEntity):
    """Maps a Windhager alarm code (e.g. 0/97) to its error text."""

    _attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self) -> str | None:
        code = self.int_value
        if code is None:
            return None
        sprache = self._sprache
        if code == 0:
            return keine_stoerung(sprache)
        # Die gepflegte deutsche Tabelle ist ausführlicher; andere Sprachen
        # nehmen die Herstellertabelle und erst ohne Eintrag die deutsche.
        deutsch = ERROR_TEXTS.get(code)
        text = deutsch if textsprache(sprache) == "de" else klartext(code, sprache) or deutsch
        if text is None:
            return unbekannt(code, sprache)
        return f"{code}: {text}"

    @property
    def extra_state_attributes(self):
        return {"code": self.int_value}


class WindhagerDeviceStatusSensor(MeldungsQuelle, WindhagerEntity, SensorEntity):
    """Per-device status/notification from the FE01msg field.

    Die /1-Discovery liefert je Gerät ein FE01msg, z.B. "PUR 09  OK" oder
    "PCM 00  OK". Endet es auf "OK", liegt keine Störung an; sonst steht hier
    die anstehende Meldung (InfoWIN-Benachrichtigung). Attribut `ok` erlaubt
    einfache Automationen ("ist eine Störung aktiv?").
    """

    _attr_icon = "mdi:message-alert-outline"

    @property
    def native_value(self) -> str | None:
        msg = self._raw
        if msg is None:
            return None
        return msg.strip()[:255]

    @property
    def extra_state_attributes(self):
        msg = self._raw
        if msg is None:
            return None
        return {"ok": msg.strip().upper().endswith("OK"), "raw": msg}


class WindhagerMessageTextSensor(MeldungsQuelle, WindhagerEntity, SensorEntity):
    """Klartext der aktiven Störungen aus dem FE01msg (Code -> Text).

    State zeigt nur den Klartext, z.B. "Verkleidungstür offen" (mehrere getrennt
    durch " | "), bzw. "Keine Störung". Code, Art (Fehler/Alarm/Info) und
    Handlungsempfehlung stehen im Attribut `meldungen` (Liste) für die
    Markdown-Darstellung bzw. zum Nachschlagen.
    """

    _attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self) -> str | None:
        if self._raw is None:
            return None
        msgs = self._meldungen
        if not msgs:
            return keine_stoerung(self._sprache)
        # Nur der Klartext (Code/Art stehen im Attribut 'meldungen').
        parts = [m["text"] for m in msgs]
        return " | ".join(parts)[:255]

    @property
    def extra_state_attributes(self):
        if self._raw is None:
            return None
        msgs = self._meldungen
        return {
            "anzahl": len(msgs),
            "stoerung_aktiv": len(msgs) > 0,
            "meldungen": msgs,
            "rohwert": self._raw,
        }


class WindhagerMessageListSensor(WindhagerEntity, SensorEntity):
    """Die Meldungen dieses Geräts, wie sie das Bediengerät gesammelt hat.

    Führt die Steuerung einen Störspeicher, spiegelt die Liste dessen Einträge.
    Sonst sammelt sie selbst aus ``FE01msg``: je Code ein Eintrag mit Zähler.
    """

    _attr_icon = "mdi:format-list-bulleted"
    _attr_state_class = SensorStateClass.MEASUREMENT
    # Die Liste steht für den Neustart im Zustand, gehört aber nicht in den Verlauf.
    _unrecorded_attributes = frozenset({"meldungen"})
    # Quelle ist die /1-Discovery, nicht das OID-Polling.
    _register_poll_oid = False
    # Der Zustand ist die Länge der eigenen Liste, kein Wert der Anlage. Ohne
    # das gälte die Entität als wertlos und damit dauerhaft als nicht
    # verfügbar – auch dann, wenn sie Einträge führt.
    _require_value_for_available = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._node_id = str(device_info.get("node_id"))
        # code -> Eintrag. Ein Wörterbuch, damit derselbe Fehler beim zweiten
        # Auftreten seinen Zähler hochsetzt statt eine Dublette anzulegen.
        self._eintraege: dict[int, dict] = {}

    async def async_added_to_hass(self) -> None:
        """Die gesammelten Meldungen über einen Neustart hinweg mitnehmen."""
        await super().async_added_to_hass()
        letzter = await self.async_get_last_state()
        if letzter is None:
            return
        for eintrag in letzter.attributes.get("meldungen") or []:
            with contextlib.suppress(TypeError, ValueError, AttributeError):
                self._eintraege[int(eintrag["code"])] = dict(eintrag)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Neue Meldungen aufnehmen, bevor der Zustand geschrieben wird."""
        if self._spiegel is None:
            self._aufnehmen()
        super()._handle_coordinator_update()

    @property
    def _spiegel(self) -> list[dict] | None:
        """Die Einträge dieses Geräts im Störspeicher; `None` ohne Störspeicher."""
        alle = (self.coordinator.data or {}).get("stoerspeicher")
        if alle is None:
            return None
        return [e for e in alle if str(e.get("knoten")) == self._node_id]

    def _aufnehmen(self) -> None:
        roh = (self.coordinator.data or {}).get("status", {}).get(self._node_id)
        if roh is None:
            return
        jetzt = dt_util.utcnow().isoformat(timespec="seconds")
        texte = self._descriptor.get("stoerungstexte")
        anstehend = set()
        for meldung in parse_messages(roh, texte, self._descriptor.get("sprache") or "de"):
            anstehend.add(meldung["code"])
            vorhanden = self._eintraege.get(meldung["code"])
            if vorhanden is None:
                self._eintraege[meldung["code"]] = {
                    **meldung,
                    "zuerst": jetzt,
                    "zuletzt": jetzt,
                    "anzahl": 1,
                    "aktiv": True,
                }
                continue
            # Nur ein Wiederauftreten zählt: Dieselbe Meldung im nächsten Abruf
            # ist kein neues Ereignis.
            if not vorhanden.get("aktiv"):
                vorhanden["anzahl"] = int(vorhanden.get("anzahl") or 0) + 1
            vorhanden["zuletzt"] = jetzt
        for code, eintrag in self._eintraege.items():
            eintrag["aktiv"] = code in anstehend

    async def leeren(self) -> None:
        """Mit Störspeicher dessen erledigte Einträge löschen, sonst die eigene Liste."""
        if (spiegel := self._spiegel) is not None:
            for eintrag in spiegel:
                if eintrag.get("loeschbar"):
                    await self.coordinator.client.stoerung_loeschen(eintrag["id"])
            await self.coordinator.async_request_refresh()
            return
        self._eintraege.clear()
        # Wie in `entity._nachfassen`: Ohne angemeldete Entität gibt es
        # nichts zu schreiben. Home Assistant leitet einen Dienst zwar nur an
        # angemeldete Entitäten weiter, aber ein Aufruf ohne `hass` wäre ein
        # Absturz statt einer wirkungslosen Zeile.
        if self.hass:
            self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        spiegel = self._spiegel
        return len(self._eintraege) if spiegel is None else len(spiegel)

    @property
    def extra_state_attributes(self):
        if (spiegel := self._spiegel) is not None:
            erlaubt = zuruecksetzen_erlaubt(self.coordinator)
            eintraege = eintraege_aufbereiten(self.coordinator.client, spiegel, erlaubt)
            return {
                "meldungen": [{**e, "kind": e.get("art"), "anzahl": 1} for e in eintraege],
                "eigene_liste": False,
            }
        # Neueste zuerst: Wer nachschaut, sucht meist das Letzte. Kopien, denn
        # Home Assistant vergleicht mit dem geschriebenen Stand und schreibt nur bei Abweichung.
        eintraege = [
            dict(e)
            for e in sorted(
                self._eintraege.values(), key=lambda e: e.get("zuletzt") or "", reverse=True
            )
        ]
        return {"meldungen": eintraege, "eigene_liste": True}
