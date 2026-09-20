"""Erkennung: welche Geräte und Datenpunkte die Anlage hat.

Aus Struktur (`GET /1`), kuratierten Tabellen, Menü-Ebenen und Netzwerkvariablen
entsteht die flache Deskriptorliste, die alle Plattformen lesen.
`DESKRIPTOR_VORGABE` nennt die Felder, die jeder Deskriptor trägt.
"""

from __future__ import annotations

import asyncio
import logging
import re as _re
from xml.etree import ElementTree

from .. import geraete, geraetetexte
from ..const import ADVANCED_LEVELS, EXTRA_OIDS_BY_FCT, FCT_CLIMATE, FCT_ENTITY_MAP, FCT_NV
from ..device_db import get_enum, get_layers, get_name
from ..helpers import messgroesse
from .gemeinsam import MELDUNGS_SENSOREN

_LOGGER = logging.getLogger(__name__)


# Die Felder eines Datenpunkt-Deskriptors und ihre Vorgabe. Plattformen, Panel,
# Dashboard und Diagnose lesen sie; fehlt eines, fällt das erst dort auf.
DESKRIPTOR_VORGABE: dict = {
    "id": None,
    "alt_id": None,
    "oid": None,
    "name": None,
    "type": "auto",
    # Die Bedienebene, aus der der Datenpunkt stammt. `None` heißt: aus einer
    # kuratierten Tabelle, nicht aus einer Ebene der Anlage.
    "level": None,
    "enabled_default": True,
    "enum": None,
    "enum_texte": None,
    "unit": None,
    "device_class": None,
    "state_class": None,
    "kanonisch": None,
    "category": None,
    "icon": None,
    "min": None,
    "max": None,
    "step": None,
    "press_value": None,
    # Schaltwerte eines Schalters auf einer Betriebswahl. Ohne Angabe gelten
    # 1 und 0.
    "ein_wert": None,
    "aus_wert": None,
    "write_prot": None,
    "nv_name": None,
    # Abruftakt, wo die Einstufung nach Art und Name danebenliegt: Ein
    # Eingriff in die Betriebswahl ist ein Stellwert und zugleich der
    # Zustand, den man nach dem Schalten sofort sehen will.
    "poll_class": None,
    # Abgeleitete Werte: Bezugsadresse bzw. die Codes, die als Lauf gelten.
    "ausloeser_oid": None,
    # Bruchteil und Vorzeichen der Hysterese bei einem Schaltpunkt, dazu ihr
    # beim Einlesen gelesener Wert als Rückfall.
    "anteil": None,
    "hysterese_vorgabe": None,
    "laufphasen": None,
    "gruppe": None,
    # Beim Einlesen meldete die Anlage keinen Wert – der Eingang ist frei.
    "leer_beim_einlesen": None,
    "device_id": None,
    "alt_device_id": None,
    "device_name": None,
    "fct_type": None,
}


# Klarere, gruppierende Namen für einzelne auto-entdeckte Datenpunkte.
# HA sortiert Entities auf der Geräteseite nach dem Namen – mit gemeinsamem
# Präfix landen zusammengehörige Werte (z.B. WW-Zirkulation) beieinander.
NAME_OVERRIDES = {
    "5/6": "WW-Zirkulationspumpe Modus",
    # 39/107 meldet, ob das Befüllen gerade freigegeben ist; die Anforderung
    # läuft über die Betriebswahl des Kessels. Ohne eigenen Namen hießen beide
    # gleich und bekämen ihre Adresse angehängt.
    "39/107": "Lagerraum befüllen Freigabe",
    "39/5": "Lagerraumbefüllung Restlaufzeit",
    "5/70": "WW-Zirkulation Einschaltzeit",
    "5/71": "WW-Zirkulation Ausschaltzeit",
    # Die Herstellertabelle nennt 5/0 nur „Hysterese Ein". Sie gehört zur
    # Warmwasserladung: Geladen wird ab Sollwert minus diesem Wert.
    "5/0": "WW-Hysterese Ein",
    # 2/10 und 3/4 heißen in der Tabelle nur „Dauer" und „Temperatur". Sie sind
    # die beiden Einsteller der Funktion, die die Anleitung „Eco / Comfort"
    # nennt: eine Raumtemperatur, die für die eingestellte Zeit gilt.
    "2/10": "Eco/Comfort Dauer",
    "3/4": "Eco/Comfort Temperatur",
}


# Dasselbe je Funktionstyp, wo eine Adresse nur dort eindeutig ist. Die
# Herstellertabelle führt Namen ohne den Menütitel, unter dem sie am Gerät
# stehen – am Heizkreis heißt der Grenzwert sonst wie sein Messwert.
NAME_OVERRIDES_JE_FCT: dict[int, dict[str, str]] = geraete.NAMEN


def name_override(fct_type: object, gnmn: str) -> str | None:
    """Gepflegter Name eines Datenpunkts, Funktionstyp vor flacher Tabelle."""
    je_fct = NAME_OVERRIDES_JE_FCT.get(fct_type) or {}
    return je_fct.get(gnmn) or NAME_OVERRIDES.get(gnmn)


# Adressangaben in der statischen Navigation der Steuerung. Zwei Schreibweisen
# für dasselbe: `oidextension="4/80/0"` in der Zuordnung, `gnmn="03:61"` in der
# Navigation selbst.
_STATISCHE_ADRESSE = _re.compile(r"^0*(\d+)[:/]0*(\d+)(?:/\d+)?$")


def statische_positionen(xml: str) -> set[str]:
    """Adressen aus einer Ressourcendatei der statischen Navigation lesen.

    Die Steuerung führt einige Datenpunkte ausschließlich hier – der Menü-Abzug
    kennt sie nicht. Gelesen wird jedes Element, das eine Adresse trägt; welche
    Art dahinter steckt, entscheidet später die Metadatenabfrage.

    Fehlt oder taugt die Datei nichts, bleibt die Menge leer: Die Erkennung
    verliert dann nur diese Ergänzung, statt abzubrechen.
    """
    try:
        wurzel = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return set()

    positionen = set()
    for element in wurzel.iter():
        for schluessel in ("oidextension", "gnmn"):
            if (treffer := _STATISCHE_ADRESSE.match(element.get(schluessel, ""))) is not None:
                positionen.add(f"{treffer.group(1)}/{treffer.group(2)}")
    return positionen


class ErkennungMixin:
    """Geräte und Datenpunkte der Anlage ermitteln."""

    # Ressourcendateien der statischen Navigation. Die erste ordnet die
    # Positionen den Funktionsarten zu, die zweite benennt sie; welche eine
    # Steuerung ausliefert, hängt an ihrer Fassung.
    _STATISCHE_RESSOURCEN = ("xml/StaticNavAssignment.xml", "xml/StaticNav.xml")

    async def _lade_geraetetexte(self) -> geraetetexte.Texte:
        """Das Textwerk der Steuerung lesen.

        Die Klartexte der Datenpunkte passen zur Fassung der Anlage und zur
        gewählten Sprache; die mitgelieferte Datenbank kennt nur Deutsch.

        Wie die statischen Positionen gehört das **nicht** in den
        Kurzdurchlauf: Der soll mit wenigen Anfragen stehen.
        """
        return await geraetetexte.laden(self._ressource, self.sprache)

    async def _statische_adressen(self) -> set[str]:
        """Positionen ermitteln, die die Anlage außerhalb der Menüs führt.

        Die Menü-Abfrage ist die Hauptquelle der Erkennung, aber nicht die
        einzige: Sonderzeitprogramm, Störspeicher und Passwort stehen in keiner
        Menü-Ebene. Die Anlage benennt sie selbst, deshalb steht hier keine
        gepflegte Liste – eine neuere Fassung bringt ihre Ergänzungen mit.
        """
        dateien = await asyncio.gather(
            *(self._ressource(pfad) for pfad in self._STATISCHE_RESSOURCEN)
        )
        adressen: set[str] = set()
        for xml in dateien:
            if xml:
                adressen |= statische_positionen(xml)
        _LOGGER.debug("Statische Navigation nennt %d Positionen", len(adressen))
        return adressen

    async def _lese_geraeteinfo(self) -> None:
        """Modell und Firmwarestand der Steuerung holen.

        Eine Anfrage, und die einzige Stelle, an der sich die Steuerung
        maschinenlesbar zu erkennen gibt: `lookup /1` nennt nur die Knoten.
        Ältere Fassungen kennen den Endpunkt nicht – dann bleibt die Auskunft
        leer und die Geräteseite zeigt weiterhin nur „Steuerung".
        """
        daten, status = await self._get(f"http://{self.host}/api/1.0/info/deviceinfo")
        self.geraeteinfo = daten if status == 200 and isinstance(daten, dict) else {}

    async def _lese_knotendaten(self) -> None:
        """Die Werksbezeichnung je Knoten holen.

        `lookup /1` nennt unter `device` nur eine Zahl und unter `name` den
        vergebenen Namen; `nodes` nennt zusätzlich, wie der Hersteller den
        Baustein nennt. Für Baureihen, die die kuratierte Tabelle nicht kennt,
        ist das die einzige belastbare Modellangabe.
        """
        daten, status = await self._get(f"http://{self.host}/api/1.0/nodes")
        if status != 200 or not isinstance(daten, list):
            self.werksbezeichnung = {}
            return
        self.werksbezeichnung = {
            str(knoten["nodeId"]): str(bezeichnung).strip()
            for knoten in daten
            if isinstance(knoten, dict)
            and knoten.get("nodeId") is not None
            and (bezeichnung := (knoten.get("device") or {}).get("name"))
        }

    def _name_fuer(self, gnmn: str, vorgabe: str | None) -> str | None:
        """Anzeigename eines Datenpunkts.

        Auf Deutsch führt die gepflegte Bezeichnung; der Gerätetext springt nur
        dort ein, wo keine vorliegt. Bei fremder Sprache ist es umgekehrt –
        sonst stünde die halbe Oberfläche weiter deutsch da.
        """
        geraet = self._texte.namen.get(gnmn)
        if self.sprache == "de":
            return vorgabe or geraet
        return geraet or vorgabe

    def _enum_texte_fuer(self, gnmn: str) -> dict[int, str] | None:
        """Zustandstexte, die die Anlage selbst für diesen Datenpunkt führt.

        Nur bei fremder Sprache: Auf Deutsch gilt die gepflegte Tabelle, die
        mehr Datenpunkte abdeckt als das Textwerk der Steuerung.
        """
        if self.sprache == "de":
            return None
        return self._texte.enums.get(gnmn)

    def _stoerungstexte(self) -> dict[int, str] | None:
        """Störungstexte der Anlage, für die Meldungssensoren.

        Nur bei fremder Sprache. Die gepflegte deutsche Tabelle führt deutlich
        mehr Codes als das Textwerk der Steuerung; auf Deutsch wäre der
        Wechsel ein Rückschritt.

        Sie hängt am Deskriptor und nicht an einem eigenen Speicher: So trägt
        der Erkennungsstand sie mit, und nach einem Neustart aus dem
        Zwischenspeicher steht sie ohne neuen Abruf wieder da.
        """
        if self.sprache == "de":
            return None
        return self._texte.stoerungen or None

    @staticmethod
    def _deskriptor(**felder) -> dict:
        """Ein Datenpunkt-Deskriptor mit allen Feldern, die er führen muss.

        Die Beschreibung entstand an drei Stellen – kuratierte Tabelle, Menü-
        Erkennung, LON-Adressraum – und lief auseinander: Die eine führte
        `level` und `enabled_default`, die andere nicht. Ein neues Feld musste
        dreimal nachgezogen werden, und wer eines vergaß, merkte es erst an
        einer Anlage.

        Was hier steht, ist die Form. Was ein Aufrufer nicht nennt, bleibt auf
        der Vorgabe.
        """
        return {**DESKRIPTOR_VORGABE, **felder}

    def _add_entity(self, definition: dict, prefix: str, device_id: str, fct: dict):
        """Create a device/entity descriptor from a curated table entry."""
        base = device_id if definition.get("node_level") else prefix
        oid = f"{base}{definition['oid']}"
        unique_id = self._kennung(oid)
        alt = self._alte_kennung(oid)
        if definition.get("key_suffix"):
            unique_id = f"{unique_id}-{definition['key_suffix']}"
            alt = f"{alt}-{definition['key_suffix']}"
        descriptor = self._deskriptor(
            id=unique_id,
            alt_id=alt,
            oid=oid,
            # `base`, nicht `prefix`: Knotenweite Datenpunkte hängen am Gerät,
            # nicht an der Funktion – sonst schneidet `_gnmn` die falsche
            # Länge ab.
            name=self._name_fuer(self._gnmn(base, oid), definition["name"]),
            type=definition["platform"],
            unit=definition.get("unit"),
            enum=definition.get("enum"),
            enum_texte=self._enum_texte_fuer(self._gnmn(base, oid)),
            device_class=definition.get("device_class"),
            state_class=definition.get("state_class"),
            category=definition.get("category"),
            icon=definition.get("icon"),
            min=definition.get("min"),
            max=definition.get("max"),
            step=definition.get("step"),
            press_value=definition.get("press_value"),
            ein_wert=definition.get("ein_wert"),
            aus_wert=definition.get("aus_wert"),
            device_id=self._geraetekennung(prefix),
            alt_device_id=self._alte_kennung(prefix),
            device_name=fct["name"],
            fct_type=fct.get("fctType"),
        )
        self.devices.append(descriptor)
        self.oids.add(oid)

    async def _discover(self, nur_kern: bool = False):
        """Geräte und Datenpunkte der Anlage ermitteln.

        Mit ``nur_kern`` werden ausschließlich die kuratierten Datenpunkte
        angelegt – ohne die Menü-Ebenen zu lesen.
        """
        self.oids = set()
        self.devices = []
        json_devices = await self.fetch("/1")
        if not self.geraeteinfo:
            await self._lese_geraeteinfo()
        if not self.werksbezeichnung:
            await self._lese_knotendaten()
        if nur_kern:
            statisch = set()
        else:
            statisch = await self._statische_adressen()
            self._texte = await self._lade_geraetetexte()

        # Erst die Seriennummern einsammeln – alle Kennungen hängen daran.
        for device in json_devices:
            if (neuron := device.get("neuronId")) and device.get("nodeId") is not None:
                self.neuron_by_node[str(device["nodeId"])] = str(neuron)

        for device in json_devices:
            node_id = device["nodeId"]
            device_id = f"/1/{node_id}"
            primary_prefix = None
            primary_name = None
            primary_type = None

            nv_funktionen: list[dict] = []
            funktionen = list(device.get("functions", []))
            brauchbar = any(
                not f.get("lock")
                and (f.get("fctType") in FCT_ENTITY_MAP or get_layers(f.get("fctType")))
                for f in funktionen
            )
            if not brauchbar and not nur_kern:
                funktionen += await self._ungemeldete_funktionen(device_id, funktionen)

            for fct in funktionen:
                fct_type = fct.get("fctType")
                if fct.get("lock"):
                    continue
                if fct_type == FCT_NV:
                    # Der LON-Adressraum kennt keine Bedienebenen und keine
                    # kuratierte Tabelle; er läuft über seinen eigenen Weg –
                    # und erst, wenn die Funktionen dieses Knotens gelesen
                    # sind: Seine Werte gehören an das Gerät der Funktion,
                    # nicht in ein zweites daneben.
                    nv_funktionen.append(fct)
                    continue
                if fct_type not in FCT_ENTITY_MAP and not get_layers(fct_type):
                    continue

                prefix = f"{device_id}/{fct['fctId']}"

                # erste verwertbare Funktion des Knotens = Primärgerät
                # (daran hängt der Geräte-Meldungssensor aus FE01msg)
                if primary_prefix is None:
                    primary_prefix = prefix
                    primary_name = fct["name"]
                    primary_type = fct_type

                # Kuratierte Tabellen: beim Kurzdurchlauf übersprungen, damit
                # die Einrichtung nur wenige Anfragen kostet. Thermostat und
                # Meldungen entstehen weiter unten und reichen für den Start.
                if not nur_kern:
                    for definition in FCT_ENTITY_MAP.get(fct_type, []):
                        self._add_entity(definition, prefix, device_id, fct)

                # Sammel-Lesezugriff: Die Menü-Ebenen der Funktion liefern
                # sämtliche vorhandenen Datenpunkte inklusive Metadaten in
                # wenigen Anfragen. Das ist die Hauptquelle der Erkennung.
                # Eine nicht gemeldete Funktion wurde schon gelesen – ihr Typ
                # stammt aus genau diesen Datenpunkten. Ein zweiter Abruf
                # brächte nichts und kostete die Anlage ein Menü mehr.
                menu_data = fct.get("_menus")
                if menu_data is None:
                    menu_data = (
                        {} if nur_kern else await self._read_function_menus(prefix, fct_type)
                    )
                self.menu_meta.update(menu_data)

                layers = get_layers(fct_type) or {}
                # Die Herstellerliste führt Datenpunkte mehrfach: `9/57` steht
                # an der Serviceebene *und* an der Werksebene. Es gilt die
                # zugänglichste, sonst verschluckt die Werksebene sie alle.
                level_of: dict[str, str] = {}
                for level in ("info", "operate", "service", "oem"):
                    for gnmn in layers.get(level, []):
                        level_of.setdefault(gnmn, level)
                # Bereichsnamen der Bedienebenen als Rückfall für Datenpunkte
                # ohne eigenen Namen (z.B. "Zündung 39/4").
                gruppe_of = {
                    gnmn: bereich
                    for bereich, adressen in (layers.get("groups") or {}).items()
                    for gnmn in adressen
                }

                # Datenpunkte, die die Anlage meldet, plus die bekannten
                # Ergänzungen, die in keinem Menü stehen (Zeitprogramme u. a.).
                candidates = {oid: self._gnmn(prefix, oid) for oid in menu_data}
                # Die Ergänzungen stehen in keiner Bedienebene – sonst wären sie
                # im Menü. Ohne eigenen Vermerk fielen sie deshalb gleich unten
                # als „Werksebene" wieder heraus, und das war kein theoretischer
                # Fall: `39/107` („Lagerraum befüllen: freigegeben/gesperrt")
                # und `39/5` (Restlaufzeit der Freigabe) wurden abgefragt,
                # angelegt wurden sie nie. Die Karte „Lagerraum befüllen" zeigte
                # deshalb weder Freigabe noch Restzeit – genau die zwei Angaben,
                # wegen derer man beim Befüllen überhaupt hinschaut.
                ergaenzt: set[str] = set()
                if not nur_kern:
                    # Die statische Navigation gilt für die ganze Anlage und
                    # nennt nicht, an welcher Funktion eine Position tatsächlich
                    # sitzt. Sie wird deshalb überall angeboten; wo es sie nicht
                    # gibt, antwortet die Anlage mit 404 oder 409 und die
                    # Metadatenabfrage wirft den Datenpunkt wieder heraus.
                    for gnmn in (*EXTRA_OIDS_BY_FCT.get(fct_type, ()), *statisch):
                        candidates.setdefault(f"{prefix}/{gnmn}/0", gnmn)
                        ergaenzt.add(gnmn)

                if not menu_data and not nur_kern:
                    # Ältere Firmware ohne Menüliste: auf die Datenbank
                    # zurückfallen und jeden Datenpunkt einzeln prüfen.
                    for level in self.levels:
                        for gnmn in layers.get(level, []):
                            candidates.setdefault(f"{prefix}/{gnmn}/0", gnmn)

                for oid, gnmn in candidates.items():
                    if oid in self.oids:
                        continue
                    # Datenpunkte, die keiner Bedienebene zugeordnet sind,
                    # gehören zur Werksebene: Sie erscheinen nur, wenn diese
                    # ausdrücklich gewählt wurde. Die ausdrücklich ergänzten
                    # sind davon ausgenommen – sie stehen von Hand in
                    # `EXTRA_OIDS_BY_FCT`, gerade *weil* die Anlage sie in
                    # keiner Ebene führt, und das ist eine Entscheidung und
                    # kein Zufall.
                    level = level_of.get(gnmn) or ("operate" if gnmn in ergaenzt else "oem")
                    if level not in self.levels:
                        continue
                    self.devices.append(
                        self._deskriptor(
                            id=self._kennung(oid),
                            alt_id=self._alte_kennung(oid),
                            oid=oid,
                            name=(
                                self._name_fuer(
                                    gnmn, name_override(fct_type, gnmn) or get_name(gnmn)
                                )
                                or (f"{gruppe_of[gnmn]} {gnmn}" if gnmn in gruppe_of else None)
                                or f"Datenpunkt {gnmn}"
                            ),
                            level=level,
                            # Service- und Werksebene sind vorhanden, aber
                            # standardmäßig deaktiviert (pro Entity in Home
                            # Assistant aktivierbar oder über die Optionen).
                            enabled_default=(level not in ADVANCED_LEVELS or self.enable_advanced),
                            enum=gnmn if get_enum(gnmn) else None,
                            enum_texte=self._enum_texte_fuer(gnmn),
                            device_id=self._geraetekennung(prefix),
                            alt_device_id=self._alte_kennung(prefix),
                            device_name=fct["name"],
                            fct_type=fct_type,
                        )
                    )
                    self.oids.add(oid)

                # Heizkreis additionally gets a climate entity
                if fct_type == FCT_CLIMATE:
                    self.devices.append(
                        {
                            "id": f"{self._geraetekennung(prefix)}-thermostat",
                            "alt_id": self._alte_kennung(device_id),
                            "name": fct["name"],
                            "type": "climate",
                            "prefix": prefix,
                            "device_id": self._geraetekennung(prefix),
                            "alt_device_id": self._alte_kennung(prefix),
                            "device_name": fct["name"],
                            "fct_type": fct_type,
                        }
                    )
                    self.oids.update(
                        [
                            f"{prefix}/0/1/0",  # Raumtemperatur Ist
                            f"{prefix}/1/1/0",  # Raumtemperatur Soll
                            f"{prefix}/3/50/0",  # Betriebswahl
                            f"{prefix}/2/10/0",  # Dauer Eco/Party (Resthandzeit)
                            f"{prefix}/3/58/0",  # Behaglichkeitskorrektur
                        ]
                    )

            # Der LON-Adressraum, jetzt mit bekanntem Primärgerät. Ein Knoten
            # ohne brauchbare Funktion – das Bedienteil – bekommt darüber sein
            # eigenes Gerät; einen Kessel ergänzen die Werte an seinem.
            if not nur_kern and (self.lon or self.lon_grundumfang):
                for fct in nv_funktionen:
                    await self._lese_nv(
                        f"{device_id}/{fct['fctId']}",
                        primary_prefix,
                        primary_name,
                        primary_type,
                    )

            # Geräte-Meldung (FE01msg, z.B. "PUR 09  OK") als Sensoren je Knoten,
            # angehängt an das Primärgerät. Quelle ist die /1-Discovery selbst.
            if device.get("FE01msg") is not None and primary_prefix is not None:
                for suffix, typ, name, icon in MELDUNGS_SENSOREN:
                    self.devices.append(
                        self._deskriptor(
                            id=f"{self._neuron(node_id)}-{suffix}",
                            alt_id=self._alte_kennung(f"{device_id}-{suffix}"),
                            type=typ,
                            node_id=str(node_id),
                            name=name,
                            stoerungstexte=self._stoerungstexte(),
                            category="diagnostic",
                            icon=icon,
                            device_id=self._geraetekennung(primary_prefix),
                            alt_device_id=self._alte_kennung(primary_prefix),
                            device_name=primary_name,
                            fct_type=primary_type,
                        )
                    )

        self._abfragetasten()

    def _abfragetasten(self) -> None:
        """Je Anlagenteil eine Taste, die seine Werte sofort liest.

        Der zyklische Abruf staffelt nach Poll-Klasse; ein Zählerstand ist erst
        nach einer Viertelstunde wieder frisch.
        """
        for kennung, muster in {
            d["device_id"]: d
            for d in self.devices
            if d.get("device_id") and d.get("device_name") and d.get("oid")
        }.items():
            self.devices.append(
                {
                    "id": f"{kennung}-abfragen",
                    "alt_id": f"{muster.get('alt_device_id') or kennung}-abfragen",
                    "type": "refresh",
                    "name": "Werte jetzt abfragen",
                    # Ohne Kategorie steht die Taste im Abschnitt Steuerung,
                    # und der liegt auf der Geräteseite ganz oben.
                    "icon": "mdi:refresh",
                    "enabled_default": True,
                    "device_id": kennung,
                    "alt_device_id": muster.get("alt_device_id"),
                    "device_name": muster["device_name"],
                    "fct_type": muster.get("fct_type"),
                }
            )

    def export_discovery(self) -> dict:
        """Discovery-Ergebnis für die Wiederverwendung (RAM- und Platten-Cache).

        Bewusst JSON-tauglich (Listen statt Sets), damit es per HA-Store
        persistiert werden kann.
        """
        return {
            "oids": sorted(self.oids) if self.oids is not None else None,
            "devices": [dict(d) for d in self.devices],
            "poll_oids": sorted(self.poll_oids),
            "objects_supported": self._objects_supported,
            "neuron_by_node": dict(self.neuron_by_node),
            "geraeteinfo": dict(self.geraeteinfo),
            "werksbezeichnung": dict(self.werksbezeichnung),
            "zusatzkandidaten": list(self.zusatzkandidaten),
        }

    def restore_discovery(self, data: dict) -> None:
        """Discovery-Ergebnis aus dem Cache übernehmen (überspringt async_init)."""
        self.oids = set(data["oids"]) if data.get("oids") is not None else set()
        # Einheiten und Klassen werden neu bestimmt, nicht aus dem Cache
        # übernommen: Ein gespeicherter Stand kann von einer Fassung stammen,
        # die die Einheitentabelle noch nicht kannte. Der Aufruf ist
        # wiederholbar und ändert an einem aktuellen Stand nichts.
        self.devices = [messgroesse(dict(d)) for d in data.get("devices", [])]
        self.neuron_by_node = dict(data.get("neuron_by_node") or {})
        self.geraeteinfo = dict(data.get("geraeteinfo") or {})
        self.werksbezeichnung = dict(data.get("werksbezeichnung") or {})
        self.zusatzkandidaten = [dict(k) for k in data.get("zusatzkandidaten") or []]
        # Die Auswahl kann sich seit dem Speichern geändert haben.
        for d in self.devices:
            if d.get("type") in self.ZUSATZTYPEN:
                d["enabled_default"] = d["id"] in self.zusatzwerte
        # Abrufplan, Poll-Klassen und Zeitprogramme leiten sich aus den
        # Deskriptoren ab und werden deshalb neu bestimmt. Aus dem Zwischen-
        # speicher übernommen überlebte ein lückenhafter Plan jeden Neustart.
        self._compute_poll_oids()
        # object-Unterstützung aus dem Cache übernehmen (kein erneutes Probing).
        self._objects_supported = data.get("objects_supported")
        self._vollstaendig = True
