"""Hybridmanager (fctType 26).

Ohne gepflegte Datenpunkttabelle: Die Datenpunkte kommen aus den Menü-Ebenen
der Anlage, dazu die Außentemperatur der Regelung und der SG-Ready-Zustand.
"""

from __future__ import annotations

FCT_TYPE = 26
# Name wie in den AeroWIN-Anleitungen („Hybridmanager → Betreiberebene“).
MODELL = "Hybridmanager"
RANG = 16
SYMBOL = "mdi:valve"
# Er erzeugt keine Wärme, sondern schaltet zwischen BioWIN und AeroWIN um –
# im Schaubild deshalb wie die Kaskade, nicht als dritter Wärmeerzeuger.
SCHAUBILD = "umschaltung"

# Beide stehen in keinem Menü der Steuerung; abgeglichen mit der App an einer BioWIN Hybrid.
EXTRA_OIDS: tuple[str, ...] = ("52/10", "54/49")
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
