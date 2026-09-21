"""Abgeleitete Werte: Datenpunkte, die von einem anderen leben.

Schaltpunkte, der Abstand bis zum nächsten Schaltpunkt, Zuwächse je Zähler
und Laufzeiten aus dem Zustand. Sie teilen die Adresse ihres Ursprungs und
tragen einen eigenen Namen und Typ.
"""

from __future__ import annotations

from ..const import (
    GRUPPE_LAUFZEIT,
    GRUPPE_SCHALTPUNKT,
    GRUPPE_ZAEHLER,
    LAUFPHASEN,
    LAUFZEIT_ERSETZT,
    SCHALTPUNKTE,
    STARTZAEHLER,
    TAGESWERTE,
    TAGESZAEHLER,
    VERBRAUCHER_ABSTAND,
)
from ..device_db import get_ruecksetzwerte
from ..kanonisch import ist_ableitung
from .gemeinsam import gnmn_aus_oid


class AbleitungenMixin:
    """Werte, die aus anderen Datenpunkten entstehen."""

    # Zählerstände, aus denen sich ein Zuwachs bilden lässt.
    _ZAEHLERKLASSEN = ("total", "total_increasing")

    # Endung der Kennung -> Name des Werts, der daraus entsteht.
    _LAUFZEITEN = {
        "laufzeit": "Laufzeit Zyklus",
        "laufzeit-heute": "Laufzeit heute",
    }

    # Deskriptorarten, die aus einem anderen Wert abgeleitet sind.
    ZUSATZTYPEN = (
        "zaehler_heute",
        "zaehler_start",
        "laufzeit",
        "laufzeit_heute",
        "schaltpunkt",
        "schaltpunkt_abstand",
        "ww_abstand",
    )

    def _ableitung(self, quelle: dict, endung: str, typ: str, zusatz: str, **felder) -> dict:
        """Ein Deskriptor, der von einem anderen lebt: gleiche Adresse, eigener Name.

        `name_ersetzen` setzt einen eigenen Namen, statt den der Quelle zu
        verlängern — ein Schaltpunkt heißt nicht „Puffertemperatur Sollwert ab".
        """
        eigener = felder.pop("name_ersetzen", None)
        return self._deskriptor(
            id=f"{quelle['id']}-{endung}",
            alt_id=f"{quelle.get('alt_id') or quelle['id']}-{endung}",
            oid=quelle["oid"],
            type=typ,
            name=eigener or f"{quelle['name']} {zusatz}".strip(),
            enabled_default=False,
            device_id=quelle.get("device_id"),
            alt_device_id=quelle.get("alt_device_id"),
            device_name=quelle.get("device_name"),
            fct_type=quelle.get("fct_type"),
            **felder,
        )

    def _schaltpunkte(self, meta: dict) -> None:
        """Die Temperatur, bei der die Anlage schaltet, als eigener Wert.

        Die Hysterese wird beim Einlesen mitgenommen: Sie liegt auf der
        Serviceebene und käme sonst erst nach dem ersten langsamen Durchlauf.
        """
        nach_praefix = self._nach_praefix()

        neu = []
        for regel in SCHALTPUNKTE:
            for adressen in nach_praefix.values():
                quelle = adressen.get(regel["bezug"])
                hysterese = adressen.get(regel["hysterese"])
                if not quelle or not hysterese or quelle.get("fct_type") != regel["fct_type"]:
                    continue
                gelesen = (meta.get(hysterese["oid"]) or {}).get("value")
                try:
                    vorgabe = float(gelesen)
                except (TypeError, ValueError):
                    vorgabe = None
                neu.append(
                    self._ableitung(
                        quelle,
                        "schaltpunkt",
                        "schaltpunkt",
                        "",
                        name_ersetzen=str(regel["name"]),
                        ausloeser_oid=hysterese["oid"],
                        anteil=regel["anteil"],
                        hysterese_vorgabe=vorgabe,
                        unit="°C",
                        device_class="temperature",
                        gruppe=GRUPPE_SCHALTPUNKT,
                    )
                )
                # Der Abstand hängt an der gemessenen Temperatur, nicht am
                # Sollwert – deshalb eine eigene Ableitung von dort.
                messwert = adressen.get(regel.get("messwert"))
                if messwert and regel.get("abstand_name"):
                    neu.append(
                        self._ableitung(
                            messwert,
                            "schaltpunkt-abstand",
                            "schaltpunkt_abstand",
                            "",
                            name_ersetzen=str(regel["abstand_name"]),
                            bezugs_oid=quelle["oid"],
                            ausloeser_oid=hysterese["oid"],
                            anteil=regel["anteil"],
                            hysterese_vorgabe=vorgabe,
                            unit="K",
                            icon="mdi:delta",
                            gruppe=GRUPPE_SCHALTPUNKT,
                        )
                    )
        self._zusatzwerte_uebernehmen(neu)
        for d in neu:
            self.oids.add(d["oid"])

    def _verbraucherabstand(self, meta: dict) -> None:
        """Der Abstand bis zum nächsten Schaltpunkt eines Verbrauchers.

        Entsteht nur, wo alle vier Adressen der Regel vorhanden sind — ein
        Heizkreis ohne Warmwasserfühler bekommt den Wert nicht.
        """
        nach_praefix = self._nach_praefix()

        neu = []
        for regel in VERBRAUCHER_ABSTAND:
            for adressen in nach_praefix.values():
                teile = {
                    rolle: adressen.get(regel[rolle])
                    for rolle in ("ist", "soll", "hysterese", "zustand")
                }
                if not all(teile.values()):
                    continue
                if teile["ist"].get("fct_type") != regel["fct_type"]:
                    continue
                gelesen = (meta.get(teile["hysterese"]["oid"]) or {}).get("value")
                try:
                    vorgabe = float(gelesen)
                except (TypeError, ValueError):
                    vorgabe = None
                neu.append(
                    self._ableitung(
                        teile["ist"],
                        "ww-abstand",
                        "ww_abstand",
                        "",
                        name_ersetzen=str(regel["name"]),
                        soll_oid=teile["soll"]["oid"],
                        hysterese_oid=teile["hysterese"]["oid"],
                        zustand_oid=teile["zustand"]["oid"],
                        hysterese_vorgabe=vorgabe,
                        unit="K",
                        icon="mdi:delta",
                        gruppe=GRUPPE_SCHALTPUNKT,
                    )
                )
                # Der Abstand nennt einen Punkt – den soll man auch ablesen
                # können. Er entsteht aus denselben zwei Adressen.
                if regel.get("schaltpunkt_name"):
                    neu.append(
                        self._ableitung(
                            teile["soll"],
                            "ww-schaltpunkt",
                            "schaltpunkt",
                            "",
                            name_ersetzen=str(regel["schaltpunkt_name"]),
                            ausloeser_oid=teile["hysterese"]["oid"],
                            anteil=regel["schaltpunkt_anteil"],
                            hysterese_vorgabe=vorgabe,
                            unit="°C",
                            device_class="temperature",
                            gruppe=GRUPPE_SCHALTPUNKT,
                        )
                    )
        self._zusatzwerte_uebernehmen(neu)
        for d in neu:
            self.oids.add(d["oid"])

    def _abgeleitete_zaehler(self) -> None:
        """Je Zählerstand zwei Zuwächse: heute und seit dem letzten Start.

        Die Anlage führt nur Gesamtstände. Der Zuwachs entsteht deshalb hier,
        aus derselben Adresse – ohne einen zusätzlichen Abruf.
        """
        # Startzähler des Geräts sind der Bezugspunkt: Steigt der Stand, läuft
        # ein neuer Lauf. Welche Adresse das ist, sagt die kuratierte Tabelle.
        ausloeser = {
            d["device_id"]: d["oid"]
            for d in self.devices
            if d.get("device_id") and self._kennung_aus_oid(d.get("oid")) in STARTZAEHLER
        }
        # Je Gerät die Stundenzähler, die die Laufzeit aus dem Zustand ersetzt.
        # Sie ist minutengenau und damit die bessere Antwort; jeder andere
        # Stundenzähler desselben Geräts misst etwas anderes und bleibt.
        ersetzt = {
            (d["device_id"], kennung)
            for d in self.devices
            if d.get("device_id")
            for kennung in LAUFZEIT_ERSETZT.get(str(d.get("enum") or ""), ())
        }
        # Tageswerte, die die Anlage selbst führt, je Gerät.
        vom_geraet = {
            (d.get("device_id"), kennung)
            for d in self.devices
            if (kennung := self._kennung_aus_oid(d.get("oid"))) in TAGESWERTE
        }
        neu = []
        for d in self.devices:
            if not d.get("oid") or not d.get("name"):
                continue
            if d.get("state_class") not in self._ZAEHLERKLASSEN:
                continue
            kennung = self._kennung_aus_oid(d["oid"])
            # Ein Tageswert der Anlage braucht keine Ableitung seiner selbst.
            if kennung in TAGESWERTE:
                continue
            # Stunden sind Laufzeit, alles andere zählt Stück oder Menge.
            stunden = (d.get("unit") or "") == "h"
            if (d.get("device_id"), kennung) in ersetzt:
                continue
            gruppe = GRUPPE_LAUFZEIT if stunden else GRUPPE_ZAEHLER
            gemeinsam = {
                "unit": d.get("unit"),
                "device_class": d.get("device_class"),
                "gruppe": gruppe,
            }
            bezug = ausloeser.get(d.get("device_id"))
            # Der Bezugszähler selbst bekommt keinen Bezug auf sich: Jeder
            # Start setzte die Basis neu, der Wert bliebe immer null.
            if bezug and bezug != d["oid"]:
                neu.append(
                    self._ableitung(
                        d, "start", "zaehler_start", "seit Start", ausloeser_oid=bezug, **gemeinsam
                    )
                )
            # Führt die Anlage den Tageswert selbst, gilt ihrer.
            if (d.get("device_id"), TAGESZAEHLER.get(kennung)) not in vom_geraet:
                neu.append(self._ableitung(d, "heute", "zaehler_heute", "heute", **gemeinsam))
        self._zusatzwerte_uebernehmen(neu)

    def _ruecksetztasten(self, meta: dict) -> None:
        """Eine Taste je rücksetzbarem Zähler, wie der Hersteller sie anbietet.

        Abgeschaltet angelegt: Ein Rücksetzen löscht den Zählerstand endgültig.
        """
        neu = []
        for d in self.devices:
            if d.get("type") == "button" or ist_ableitung(d.get("id")):
                continue
            wert = get_ruecksetzwerte(d.get("fct_type")).get(gnmn_aus_oid(d.get("oid")))
            if wert is None or (meta.get(d.get("oid")) or {}).get("writeProt") is not False:
                continue
            neu.append(
                self._ableitung(
                    d,
                    "zuruecksetzen",
                    "button",
                    "zurücksetzen",
                    press_value=wert,
                    category="config",
                    icon="mdi:counter",
                )
            )
        self.devices += neu

    def _laufzeit(self) -> None:
        """Wie lange das Aggregat läuft – aus dem Zustand, nicht aus Stunden.

        Der Stundenzähler der Anlage steht in ganzen Stunden und wird träge
        gelesen; der Zustand kommt alle 30 s. Verglichen werden Zahlencodes,
        nicht Beschriftungen.
        """
        neu = []
        for d in self.devices:
            phasen = LAUFPHASEN.get(str(d.get("enum") or ""))
            if not phasen or not d.get("oid"):
                continue
            for endung, name in self._LAUFZEITEN.items():
                neu.append(
                    self._ableitung(
                        {**d, "name": ""},
                        endung,
                        endung.replace("-", "_"),
                        name,
                        unit="min",
                        laufphasen=sorted(phasen),
                        icon="mdi:fire-circle",
                        gruppe=GRUPPE_LAUFZEIT,
                    )
                )
        self._zusatzwerte_uebernehmen(neu)
