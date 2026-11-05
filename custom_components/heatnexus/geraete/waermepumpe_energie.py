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
# Er erzeugt keine Wärme und speichert keine, sondern schaltet zwischen BioWIN
# und AeroWIN um – im Schaubild als Ventilgruppe mit Pumpe im Rücklauf.
SCHAUBILD = "hybridmanager"

# Keiner steht in einer Bedienebene der Datenbank; abgeglichen mit der App an einer
# BioWIN Hybrid. 50/54 ist die Kessel-/Bypasspumpe, die das Schaubild dreht.
EXTRA_OIDS: tuple[str, ...] = ("52/10", "54/49", "50/54")
KESSELART: str | None = None

# Interne Rechenwerte: Datenbank, App und Display führen sie nicht. Benannt
# nach Nachrechnung: Pelletpreis ÷ (Heizwert × Wirkungsgrad) und Strompreis ÷
# Wärmepreis. Danach wählt der Hybridmanager zwischen Kessel und Wärmepumpe.
NAMEN: dict[str, str] = {
    "54/3": "Wärmepreis Pellets (ct/kWh)",
    "54/4": "Grenz-COP",
}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
