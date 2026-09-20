"""Metadaten der Datenpunkte: was das Gerät über sich selbst sagt.

Jede Adresse wird einmal gelesen; daraus entstehen Grenzen, Einheit, Auswahl
und die endgültige Plattform. Fehlende Adressen fallen weg, schreibgeschützte
werden auf ihr lesendes Gegenstück zurückgestuft.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re as _re

from ..const import (
    ADVANCED_LEVELS,
    OID_HARDWAREVERSION,
    OID_SOFTWAREVERSION,
    ROLLEN_FILTER,
    SYSTEMZEIT_NAMEN,
)
from ..const import ENUMS as ENUMS_FALLBACK
from ..device_db import get_conditions, get_enum
from ..helpers import READONLY_FALLBACK, lesetyp, messgroesse
from ..kanonisch import ist_ableitung

_LOGGER = logging.getLogger(__name__)


class MetadatenMixin:
    """Was das Gerät über seine Datenpunkte sagt, und was daraus folgt."""

    # writeProt=True turns a writable platform into its read-only sibling
    _READONLY_FALLBACK = READONLY_FALLBACK

    async def _apply_metadata(self):
        """Read metadata for every OID once and refine the descriptors.

        - min/max/step/unit reported by the device override the static defaults
        - writeProt=True converts writable entities into read-only ones
        - OIDs answered with 404 are dropped entirely (e.g. Sonden ohne Saugzuführung)
        """
        # Alles, was schon aus den Menü-Ebenen bekannt ist, muss nicht erneut
        # gelesen werden – das spart den Großteil der Anfragen beim Start.
        meta = {oid: m for oid, m in self.menu_meta.items() if oid in self.oids}
        offen = [oid for oid in self.oids if oid not in meta]
        _LOGGER.debug(
            "Metadaten: %d aus Menü-Ebenen, %d werden einzeln gelesen", len(meta), len(offen)
        )

        results = await asyncio.gather(*(self._fetch_json(oid) for oid in offen))
        missing = set()
        for oid, data, status in results:
            reason = (data or {}).get("reason", "") if isinstance(data, dict) else ""
            if status == 404 or (status == 409 and "invalid Identifier" in reason):
                # Datenpunkt existiert auf dieser Anlage nicht
                missing.add(oid)
            elif isinstance(data, dict) and "code" not in data:
                meta[oid] = data

        kept = []
        for d in self.devices:
            oid = d.get("oid")
            if oid in missing and d["type"] != "climate":
                _LOGGER.debug("%s (%s) entfällt: an dieser Anlage nicht vorhanden", d["name"], oid)
                continue
            m = meta.get(oid)
            if d["type"] == "auto":
                if not m:
                    _LOGGER.debug("%s (%s) entfällt: keine Metadaten", d["name"], oid)
                    continue
                resolved = self._resolve_auto_type(d, m)
                if not resolved:
                    _LOGGER.debug("%s (%s) entfällt: unlesbare Datenpunktart", d["name"], oid)
                    continue
                d["type"] = resolved
                if d["type"] == "time_program":
                    # Gelesen/geschrieben über ?OID=<vollständige OID>.
                    d["enabled_default"] = True
                    # für den PUT-Envelope beim Schreiben merken
                    d["typeId"] = m.get("typeId", 30)
                    d["subtypeId"] = m.get("subtypeId", 14)
                    d["write_prot"] = m.get("writeProt")
                elif d["type"] in ("select", "number", "switch", "time", "date") and d.get(
                    "level"
                ) in ("operate", "service"):
                    d["category"] = "config"
                # `string_sensor` gehört dazu: Eine schreibgeschützte Systemuhr
                # wird als Text gelesen und liefe sonst an der Auswahl vorbei.
                if d["type"] in ("time", "date", "string_sensor") and (
                    d.get("name") in SYSTEMZEIT_NAMEN
                ):
                    # **Systemuhr und Systemdatum sind Einstellwerte, keine
                    # Messwerte.** Man stellt sie einmal und danach jahrelang
                    # nicht mehr. Standardmäßig angelegt füllten sie die
                    # Entitätsliste und kosteten in jedem Durchlauf eine
                    # Anfrage an eine Anlage, die ohnehin knapp zwei Sekunden
                    # je Anfrage braucht.
                    #
                    # Nur diese beiden: Ein Feld mit Datum darin ist noch kein
                    # Systemdatum. „Urlaubsprogramm bis" und die
                    # Zirkulationszeiten stellt man ein, um sie danach
                    # anzusehen.
                    d["enabled_default"] = self.zeitwerte
            if m:
                # Text aus dem object-Endpunkt, gleich ob der Typ aus der
                # kuratierten Tabelle oder aus den Metadaten stammt. Die Marke
                # hält die Adresse aus dem lookup-Abruf heraus.
                if d["type"] == "string_sensor" and m.get("typeId") == 30:
                    d["objekt"] = True
                    d["typeId"] = 30
                    d["subtypeId"] = m.get("subtypeId", 9)
                    d["write_prot"] = m.get("writeProt")
                # Device reports the actually allowed enum values, e.g. "[1,2]"
                enum_raw = m.get("enum")
                if enum_raw and d["type"] in ("select", "enum_sensor", "switch"):
                    try:
                        allowed = [int(v) for v in __import__("json").loads(enum_raw)]
                        if allowed:
                            d["allowed"] = allowed
                    except (ValueError, TypeError):
                        _LOGGER.debug("Enum-Tabelle %r für %s unlesbar", enum_raw, oid)
                if d["type"] in ("select", "enum_sensor") and not d.get("allowed"):
                    # Gerät meldet zwar keine Enum-Liste, aber einen Wertebereich
                    with contextlib.suppress(TypeError, ValueError, KeyError):
                        lo, hi = int(float(m["minValue"])), int(float(m["maxValue"]))
                        emap = (
                            ENUMS_FALLBACK.get(d.get("enum") or "")
                            or get_enum(d.get("enum") or "")
                            or {}
                        )
                        allowed = [v for v in emap if lo <= v <= hi]
                        if allowed:
                            d["allowed"] = allowed
                if d["type"] == "number":
                    with contextlib.suppress(ValueError, TypeError, KeyError):
                        lo = float(m["minValue"]) if m.get("minValue") not in (None, "") else None
                        hi = float(m["maxValue"]) if m.get("maxValue") not in (None, "") else None
                        st = float(m["step"]) if m.get("step") not in (None, "") else None
                        if lo is not None and hi is not None and lo < hi:
                            d["min"], d["max"] = lo, hi
                        if st and st > 0:
                            d["step"] = st
                if m.get("unit") and d["type"] in ("number", "sensor"):
                    d["unit"] = m["unit"]
                if m.get("writeProt") is True and d["type"] in self._READONLY_FALLBACK:
                    fallback = lesetyp(d["type"], m.get("unit") or d.get("unit"))
                    _LOGGER.debug(
                        "%s (%s) ist schreibgeschützt und wird nur angezeigt", d["name"], oid
                    )
                    d["type"] = fallback
                    # Nur bedienbare Entitäten dürfen die Kategorie
                    # "Konfiguration" tragen; Home Assistant lehnt sie
                    # bei reinen Sensoren ab.
                    if d.get("category") == "config":
                        d["category"] = None
                d["write_prot"] = m.get("writeProt")
                # Ein Fühlereingang ohne Fühler meldet die Leermarke. Die
                # Entität entsteht abgeschaltet statt dauerhaft „nicht
                # verfügbar"; wer sie einmal einschaltet, behält sie.
                if (
                    m.get("value") in ("-.-", "-")
                    and d["type"] not in ("select", "number", "switch", "time", "date", "button")
                    and d.get("enabled_default", True)
                ):
                    d["enabled_default"] = False
                    d["leer_beim_einlesen"] = True
                # read-only-Punkt ganz ohne Wert (z.B. Softwareversion).
                # Objekte ausgenommen: Sie tragen im lookup nie einen Wert;
                # ohne die Ausnahme fiele der Gerätetyp jeder Baureihe weg.
                if (
                    "value" not in m
                    and m.get("writeProt") is True
                    and not d.get("objekt")
                    and d["type"]
                    not in ("select", "number", "switch", "time", "button", "time_program")
                ):
                    _LOGGER.debug("%s (%s) entfällt: kein Wert geliefert", d["name"], oid)
                    continue
            # Service- und Werksebene bleiben nur lesbar, solange der Nutzer sie
            # in den Optionen nicht ausdrücklich freigegeben hat.
            if (
                d.get("level") in ADVANCED_LEVELS
                and not self.writable_advanced
                and d["type"] in self._READONLY_FALLBACK
            ):
                d["type"] = lesetyp(d["type"], d.get("unit"))
                if d.get("category") == "config":
                    d["category"] = None

            if d["type"] == "climate":
                m50 = meta.get(f"{d['prefix']}/3/50/0")
                if m50 and m50.get("enum"):
                    with contextlib.suppress(ValueError, TypeError):
                        d["preset_allowed"] = [int(v) for v in json.loads(m50["enum"])]
            # Zum Schluss, wenn der endgültige Typ feststeht: Einheit in die
            # HA-Schreibweise bringen und Geräte-/Statistikklasse setzen.
            messgroesse(d)
            kept.append(d)
        self.devices = kept
        self.oids -= missing
        self._rollen_filter(meta)
        # Erst die Doppelten heraus, dann der Fühlertest: Er kostet eine Anfrage
        # je Netzwerkvariable, und was ein Datenpunkt schon führt, wird nicht
        # erst gemessen und dann verworfen.
        self._nv_doppelte_stilllegen()
        await self._nv_ohne_fuehler_verwerfen()
        # Die alte Liste bleibt stehen, bis die neue vollständig ist: Ein
        # Optionsdialog, der währenddessen offen ist, sähe sonst keine
        # Zusatzwerte und verlöre beim Bestätigen die Auswahl.
        self._zusatz_neu, self._zusatz_lauft = [], True
        try:
            self._abgeleitete_zaehler()
            self._schaltpunkte(meta)
            self._verbraucherabstand(meta)
            self._laufzeit()
            self._namen_vereindeutigen()
        finally:
            self._zusatz_lauft = False
        # Erst nach dem letzten Schritt: Bricht einer ab, bleibt die alte
        # Liste stehen statt einer halben.
        self.zusatzkandidaten = self._zusatz_neu

    @staticmethod
    def _resolve_auto_type(d: dict, m: dict) -> str | None:
        """Map an auto-discovered datapoint to a HA platform via metadata."""
        writable = m.get("writeProt") is False
        value = m.get("value")
        unit = m.get("unit") or ""
        has_enum = bool(m.get("enum")) or bool(get_enum(d.get("enum") or ""))
        if has_enum:
            return "select" if writable else "enum_sensor"
        if isinstance(value, str) and _re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", value):
            return "time" if writable else "string_sensor"
        if isinstance(value, str) and _re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value):
            return "date" if writable else "string_sensor"
        if m.get("typeId") == 30 and ("value" not in m or m.get("subtypeId") == 14):
            # `typeId 30` heißt „über den object-Endpunkt lesen"; erst
            # `subtypeId` sagt was: 9 Text, 10 Funktionsliste (unlesbar), 14
            # Zeitprogramm – auch wo die Baureihe ein leeres `value` mitschickt.
            if m.get("subtypeId") == 10:
                return None
            if m.get("subtypeId") == 9:
                return "string_sensor"
            return "time_program"
        if writable:
            try:
                if float(m.get("minValue")) < float(m.get("maxValue")):
                    return "number"
            except (TypeError, ValueError):
                pass
        if m.get("typeId") == 30:
            return "string_sensor"
        # Eine Fassungsnummer ist keine Messgröße. Manche Baureihen melden sie
        # als gewöhnlichen Datenpunkt, dessen Wert wie eine Kommazahl aussieht.
        if d.get("oid", "").endswith((f"/{OID_SOFTWAREVERSION}/0", f"/{OID_HARDWAREVERSION}/0")):
            return "string_sensor"
        # Ein Ausgang, der nur 0 oder 1 kennt, ist ein Schaltzustand. Die
        # Steuerung führt Schaltzustände und Drehzahlen unter derselben
        # `typeId`; erst Bereich und fehlende Einheit trennen sie.
        if (
            not writable
            and not unit
            and str(m.get("minValue")) == "0"
            and str(m.get("maxValue")) == "1"
        ):
            return "binary_sensor"
        try:
            if value not in (None, "-.-", "-", ""):
                float(value)
            return "temperature" if unit == "°C" else "sensor"
        except (TypeError, ValueError):
            return "string_sensor"

    def _rollen_filter(self, meta: dict) -> None:
        """Datenpunkte verwerfen, die an dieser Anlage keine Aufgabe haben.

        Zwei Quellen: die Bedingungen der Herstellerdatei und `ROLLEN_FILTER`
        für das, was dort fehlt. Beide brauchen einen lesbaren Schaltwert —
        ohne ihn bleibt alles stehen.
        """
        weg_je_praefix: dict[str, set[str]] = {}

        def wert(praefix: str, adresse: str) -> str | None:
            return (meta.get(f"{praefix}/{adresse}/0") or {}).get("value")

        for fct_type in {d.get("fct_type") for d in self.devices if d.get("fct_type")}:
            praefixe = {
                p
                for d in self.devices
                if d.get("fct_type") == fct_type and (p := self._praefix_aus_oid(d.get("oid")))
            }
            bedingungen = get_conditions(fct_type)
            regel = ROLLEN_FILTER.get(fct_type)
            for praefix in praefixe:
                weg = weg_je_praefix.setdefault(praefix, set())
                # Die Herstellerdatei nennt je Adresse, welche Einstellung sie
                # freischaltet. Trifft kein Satz zu, ist sie ohne Aufgabe.
                for adresse, saetze in bedingungen.items():
                    geprueft = [
                        (str(wert(praefix, s["oid"])), s["values"])
                        for s in saetze
                        if wert(praefix, s["oid"]) is not None
                    ]
                    if geprueft and not any(ist in erlaubt for ist, erlaubt in geprueft):
                        weg.add(adresse)
                if not regel:
                    continue
                try:
                    rolle = int(float(wert(praefix, regel["quelle"])))
                except (TypeError, ValueError):
                    continue
                weg |= {
                    adresse for adresse, erlaubt in regel["nur_bei"].items() if rolle not in erlaubt
                }

        if not any(weg_je_praefix.values()):
            return
        behalten = []
        for d in self.devices:
            praefix = self._praefix_aus_oid(d.get("oid"))
            if self._kennung_aus_oid(d.get("oid")) in weg_je_praefix.get(praefix, ()):
                _LOGGER.debug(
                    "%s (%s) entfällt: an dieser Anlage ohne Aufgabe", d["name"], d.get("oid")
                )
                self.oids.discard(d.get("oid"))
                continue
            behalten.append(d)
        self.devices = behalten

    def _nach_praefix(self) -> dict[str, dict[str, dict]]:
        """Deskriptoren nach Funktionspräfix und Kennung sortiert.

        Ableitungen bleiben draußen: Sie tragen die Adresse ihrer Quelle und
        verdrängten sie sonst unter demselben Schlüssel.
        """
        sortiert: dict[str, dict[str, dict]] = {}
        for d in self.devices:
            if not d.get("oid") or ist_ableitung(d.get("id")):
                continue
            praefix = self._praefix_aus_oid(d["oid"])
            if praefix:
                sortiert.setdefault(praefix, {})[self._kennung_aus_oid(d["oid"])] = d
        return sortiert

    def _namen_vereindeutigen(self) -> None:
        """Gleichnamige Datenpunkte eines Geräts unterscheidbar machen.

        Die Parameterliste des Herstellers vergibt denselben Namen mehrfach:
        „Betriebswahl" gibt es als Bedienung (3/50) und als Anzeige der
        Serviceebene (4/14), „WW-Zirkulationsprogramm" zweimal (5/64, 5/65).
        Bei Gleichstand wird die Datenpunktadresse angehängt.
        """
        namen_je_geraet: dict[tuple, list] = {}
        for d in self.devices:
            if not d.get("oid") or not d.get("name"):
                continue
            # Verglichen wird vereinheitlicht: Die kuratierte Tabelle schreibt
            # „Außentemperatur", die Gerätetabelle „Aussentemperatur" – für den
            # Leser derselbe Name, für einen Zeichenvergleich nicht.
            schluessel = (d.get("device_id"), d["name"].casefold().replace("ß", "ss"))
            namen_je_geraet.setdefault(schluessel, []).append(d)

        for (_geraet, _name), gruppe in namen_je_geraet.items():
            if len(gruppe) < 2:
                continue
            for d in gruppe:
                praefix = d["oid"].rsplit("/", 3)[0]
                d["name"] = f"{d['name']} ({self._gnmn(praefix, d['oid'])})"

    def _zusatzwerte_uebernehmen(self, kandidaten: list[dict]) -> None:
        """Angekreuzte Werte einschalten, die übrigen abgeschaltet anlegen.

        Wie beim Schalter für die Zeitwerte: Ein weggenommenes Häkchen schaltet
        ab und wirft nichts weg – Verlauf und eigener Name bleiben.
        """
        for kandidat in kandidaten:
            kandidat["enabled_default"] = kandidat["id"] in self.zusatzwerte
        self._zusatz_neu += kandidaten
        # Während eines Einlesens sammelt `_zusatz_neu`; ein einzelner Aufruf
        # schreibt sofort in die gültige Liste.
        if not self._zusatz_lauft:
            self.zusatzkandidaten += kandidaten
        self.devices += kandidaten
