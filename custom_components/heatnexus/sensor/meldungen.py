"""Sensoren für Störungen und Meldungen: Code, Klartext, Zustand, fortlaufende Liste."""

from __future__ import annotations

import contextlib
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from ..const import ERROR_TEXTS
from ..entity import MeldungsQuelle, WindhagerEntity
from ..error_texts import parse_messages


class WindhagerErrorTextSensor(WindhagerEntity, SensorEntity):
    """Maps a Windhager alarm code (e.g. 0/97) to its German error text."""

    _attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self) -> str | None:
        code = self.int_value
        if code is None:
            return None
        if code == 0:
            return "Keine Störung"
        text = ERROR_TEXTS.get(code)
        if text is None:
            return f"Unbekannter Code {code}"
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
            return "Keine Störung"
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
    """Fortlaufende Liste aller Meldungen, die diese Anlage gezeigt hat.

    **Warum es sie gibt.** ``FE01msg`` nennt nur, was gerade anliegt. Wer die
    Verkleidungstür öffnet und wieder schließt, sieht die Meldung kommen und
    gehen – hinterher steht nirgends, dass sie da war. Das Bediengerät führt
    dafür eine Liste mit Papierkorb; über die Schnittstelle ist sie nicht zu
    bekommen. Geprüft an der Anlage: ``2/96`` – die Adresse, die die
    Weboberfläche der Steuerung dafür benutzt – antwortet an jeder Funktion mit
    ``409 invalid Identifier``, und von 24 denkbaren Endpunktnamen kennt die
    Steuerung keinen einzigen (``errorlog``, ``errors``, ``message``,
    ``messages``, ``alarm``, ``alarms``, ``log``, ``history``).

    **Das hier ist deshalb unsere Liste, nicht die des Kessels.** Sie beginnt,
    wenn die Integration eingerichtet wird, und der Dienst
    ``heatnexus.meldungen_loeschen`` leert *sie* – am Bediengerät ändert das
    nichts. Wer das verwechselt, hält eine geleerte Liste für einen
    quittierten Fehler.

    Je Code ein Eintrag, ohne Dubletten, mit erstem und letztem Auftreten und
    einem Zähler. Der Zustand ist die Anzahl; die Einträge stehen im Attribut.
    Sie überleben einen Neustart über ``RestoreEntity``.
    """

    _attr_icon = "mdi:format-list-bulleted"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "Meldungen"
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
        self._aufnehmen()
        super()._handle_coordinator_update()

    def _aufnehmen(self) -> None:
        roh = (self.coordinator.data or {}).get("status", {}).get(self._node_id)
        if roh is None:
            return
        jetzt = dt_util.utcnow().isoformat(timespec="seconds")
        for meldung in parse_messages(roh, self._descriptor.get("stoerungstexte")):
            vorhanden = self._eintraege.get(meldung["code"])
            if vorhanden is None:
                self._eintraege[meldung["code"]] = {
                    **meldung,
                    "zuerst": jetzt,
                    "zuletzt": jetzt,
                    "anzahl": 1,
                }
                continue
            # Dieselbe Meldung im nächsten Abruf ist kein neues Ereignis –
            # sonst zählte eine offene Tür alle 30 Sekunden weiter hoch.
            vorhanden["zuletzt"] = jetzt

    @callback
    def leeren(self) -> None:
        """Die Liste verwerfen – nur unsere, nicht die der Anlage."""
        self._eintraege.clear()
        # Wie in `entity._nachfassen`: Ohne angemeldete Entität gibt es
        # nichts zu schreiben. Home Assistant leitet einen Dienst zwar nur an
        # angemeldete Entitäten weiter, aber ein Aufruf ohne `hass` wäre ein
        # Absturz statt einer wirkungslosen Zeile.
        if self.hass:
            self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        return len(self._eintraege)

    @property
    def extra_state_attributes(self):
        # Neueste zuerst: Wer nachschaut, sucht meist das Letzte.
        eintraege = sorted(
            self._eintraege.values(), key=lambda e: e.get("zuletzt") or "", reverse=True
        )
        return {"meldungen": eintraege, "eigene_liste": True}
