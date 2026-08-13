"""LON-Netzwerkvariablen: benannte Werte vom Bus statt aus einer OID-Tabelle.

**Warum es das gibt.** Eine OID bedeutet nur etwas, wenn für ihren
Funktionstyp eine Tabelle vorliegt – `2/59` heißt am Kessel etwas anderes als
am Heizkreis. Ein Name aus dem LON-Adressraum trägt seine Bedeutung dagegen
selbst: `FS_nviMfoerder` ist die Fördermenge, an welcher Baureihe auch immer
er hängt. Deshalb ist diese Tabelle nach **Namen** geschlüsselt und nicht nach
Adresse, und deshalb trägt sie über Baureihen hinweg, die hier nie standen.

Gemessen an einem Vollabzug einer fremden BioWIN: 201 Einträge über fünf
Knoten, 99 verschiedene Namen, 95 als Sensor brauchbar, 49 davon ohne
Entsprechung im OID-Raum.

**Was hier bewusst fehlt.** Benannt wird nur, was die Abkürzung eindeutig
hergibt. `FA_nvoTk`, `NIC_nvoValue` oder `RUE_cntEntaZue` bleiben draußen,
obwohl sie Werte führen – ein falsch geratener Name wäre schlimmer als der
Rohname, weil er eine Bedeutung behauptet, die niemand geprüft hat. Was nicht
hier steht, wird trotzdem angelegt: mit dem Namen der Anlage und ab Werk
deaktiviert.

Ein kanonischer Schlüssel steht nur dort, wo der Wert **derselbe Begriff** ist
wie sein OID-Gegenstück. Er entscheidet, ob der LON-Wert ab Werk aktiv ist:
Führt ein Datenpunkt denselben Schlüssel bereits, bleibt der LON-Wert
deaktiviert, statt dieselbe Größe ein zweites Mal anzuzeigen.
"""

from __future__ import annotations

import re

from .const import POLL_NORMAL, POLL_SLOW

# Der Index steht am Namen (`LX_nvoPump[0]`) und nennt den Kreis.
_INDEX = re.compile(r"^(?P<name>.+?)\[(?P<index>\d+)\]$")

# Name ohne Index -> Klarname und, wo der Begriff derselbe ist, kanonischer
# Schlüssel. Alles Weitere (Einheit, Geräteklasse, Genauigkeit) kommt vom
# Gerät und läuft durch `helpers.messgroesse` wie bei jedem anderen Wert.
LON_NAMEN: dict[str, dict] = {
    # Wärmeerzeuger. `nvo` ist der Ausgang des Knotens, `nvi` der Eingang;
    # beide führen denselben Messwert, deshalb bekommt nur der Ausgang den
    # kanonischen Schlüssel.
    "WET_nvoTist": {"name": "Kesseltemperatur Ist", "kanonisch": "boiler_temperature"},
    "WET_nvoTsoll": {
        "name": "Kesseltemperatur Soll",
        "kanonisch": "boiler_temperature_target",
    },
    "WET_nviTist": {"name": "Kesseltemperatur Ist (Bus-Eingang)"},
    "WET_nviTsoll": {"name": "Kesseltemperatur Soll (Bus-Eingang)"},
    # Verbrennungsregler PMX.
    "PMX_eeBetrStd": {
        "name": "Betriebsstunden",
        "state_class": "total_increasing",
        "kanonisch": "operating_hours",
    },
    "PMX_eeNbrAnhz": {"name": "Anzahl Anheizungen", "state_class": "total_increasing"},
    "PMX_nvoLstg": {"name": "Kesselleistung", "kanonisch": "boiler_power"},
    "PMX_nviLstg": {"name": "Kesselleistung Vorgabe"},
    "PMX_PwrAvg": {"name": "Kesselleistung Mittelwert"},
    "PMX_InModTmr": {"name": "Zeit in Modulation"},
    # Gebläse.
    "GB_nvoNist": {"name": "Gebläsedrehzahl"},
    "GB_nvoNsoll": {"name": "Gebläsedrehzahl Soll"},
    "GB_nviNsoll": {"name": "Gebläsedrehzahl Vorgabe"},
    # Lambdasonde.
    "OXY_nvoHeating": {"name": "Lambdasonde Heizung"},
    # Brennstoffförderung und Vorrat.
    "FS_nviMfoerder": {"name": "Fördermenge", "state_class": "measurement"},
    "FS_nviMsoll": {"name": "Fördermenge Soll", "state_class": "measurement"},
    "PZS_Restmenge": {"name": "Pelletsvorrat Restmenge", "state_class": "measurement"},
    # Wartung. Eine Restlaufzeit zählt herunter – als Zählerstand geführt
    # ergäbe sie einen Verlauf, der bei jeder Reinigung zurückspringt.
    "FWN_nviRunTm2Cln": {
        "name": "Restlaufzeit bis Reinigung",
        "state_class": "measurement",
        "kanonisch": "maintenance_cleaning_hours",
    },
    # Puffer: oben, Mitte, unten.
    "WVF_nviTPO": {"name": "Puffer oben", "kanonisch": "buffer_top"},
    "WVF_nviTPM": {"name": "Puffer Mitte"},
    "WVF_nviTPU": {"name": "Puffer unten", "kanonisch": "buffer_bottom"},
    # Raum und Außen.
    "nvoTa": {"name": "Außentemperatur", "kanonisch": "outdoor_temperature"},
    "nviTaFb": {"name": "Außentemperatur (Rückmeldung)"},
    "nvoTi": {"name": "Raumtemperatur", "kanonisch": "room_temperature"},
    "nvoTiStpt": {"name": "Raumtemperatur Soll", "kanonisch": "room_temperature_target"},
    # Mischerkreis.
    "M_nvoPump": {"name": "Mischerkreis Pumpe", "poll_class": POLL_NORMAL},
    "M_nvoValve": {"name": "Mischerventil", "poll_class": POLL_NORMAL},
    "M_nviTVist": {"name": "Vorlauftemperatur Mischerkreis"},
    "M_nviTVsoll": {"name": "Vorlauftemperatur Soll Mischerkreis"},
    # Kreise mit Index. `LX` ist am Namen nicht eindeutig einem Heizkreis
    # zuzuordnen – der Index nennt den Kreis, der Begriff bleibt neutral und
    # ohne kanonischen Schlüssel, bis eine zweite Anlage ihn belegt.
    "LX_nvoPump": {"name": "Kreis Pumpe", "poll_class": POLL_NORMAL},
    "LX_nvoValve": {"name": "Kreis Ventil", "poll_class": POLL_NORMAL},
    "LX_nviTist": {"name": "Kreis Temperatur Ist"},
    "LX_nviTsoll": {"name": "Kreis Temperatur Soll"},
    "LX_nvoSetPt": {"name": "Kreis Sollwert"},
}


def kennungsteil(nv_name: str | None, menu_id: str, index) -> str:
    """Der Teil der Kennung, der eine Netzwerkvariable unterscheidbar macht.

    **Warum nicht die Adresse.** Eine Kennung aus vier Zahlen liest
    `kanonisch.gnmn` als Datenpunktadresse: Aus `…-32-0-7-0` würde `0/7`, die
    Kesseltemperatur – an einer Netzwerkvariablen, die nichts damit zu tun
    hat. Schaubild und Kennwerte hingen sich daran. Der Name unterbricht den
    Zahlenlauf und ist zugleich das Beständigere: Er benennt den
    Funktionsblock, während der Index von der Firmware vergeben wird.
    """
    rumpf = re.sub(r"[^a-z0-9]+", "-", str(nv_name or "").lower()).strip("-")
    return f"nv-{menu_id}-{index}-{rumpf}" if rumpf else f"nv-{menu_id}-{index}"


def zuordnen(nv_name: str | None) -> dict | None:
    """Kuratierter Eintrag zu einem Namen aus dem LON-Adressraum.

    Gibt ``None`` zurück, wenn der Name nicht in der Tabelle steht – dann
    bleibt es beim Namen der Anlage. Der Index in eckigen Klammern zählt den
    Kreis und steht als ``index`` in der Rückgabe; er gehört zum Namen, nicht
    zur Bedeutung, und wird für den Tabellenzugriff abgeschnitten.
    """
    if not nv_name:
        return None
    rest = str(nv_name).strip()
    index = None
    if treffer := _INDEX.match(rest):
        rest = treffer["name"]
        index = int(treffer["index"])
    eintrag = LON_NAMEN.get(rest)
    if eintrag is None:
        return None
    name = eintrag["name"]
    if index is not None:
        name = f"{name} {index + 1}"
    return {
        "name": name,
        "device_class": eintrag.get("device_class"),
        "state_class": eintrag.get("state_class"),
        "poll_class": eintrag.get("poll_class", POLL_SLOW),
        "kanonisch": eintrag.get("kanonisch"),
        "index": index,
    }
