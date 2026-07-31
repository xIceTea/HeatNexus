# Datenpunkte

Die Integration erkennt Datenpunkte auf zwei Wegen: über kuratierte Tabellen
(fester Name, Einheit, Kategorie, Symbol) und über die mitgelieferte
Geräte-Datenbank, die die Info-, Betreiber- und Serviceebene je Funktionstyp
beschreibt. Welche Datenpunkte tatsächlich angelegt werden, entscheidet die
Anlage: nicht vorhandene werden entfernt, schreibgeschützte nur lesend angelegt.

| fctType | Funktion | kuratiert | Info | Betreiber | Service |
|---|---|---|---|---|---|
| 1 | Systemwerte | – | 14 | 17 | 30 |
| 2 | Kessel (allgemein) | – | 11 | 13 | 7 |
| 4 | Kaskade (KAS) | – | 7 | 17 | 25 |
| 5 | Warmwasser | – | 15 | 6 | 8 |
| 7 | Solar | – | 19 | 6 | 39 |
| 8 | Zusatzmodul | – | 11 | – | 10 |
| 9 | Kessel (BioWIN) | – | 18 | 13 | 41 |
| 10 | Kessel (Zusatz/Kaskade) | – | 12 | 5 | 10 |
| 14 | Heizkreis (UML/UMLZ) | 22 | 16 | 18 | 29 |
| 15 | Heizkreis-Umschaltung | – | 8 | 1 | 20 |
| 16 | Puffer (B-PLMi) | 16 | 10 | 2 | 14 |
| 20 | Zirkulationssteuerung | 3 | 6 | 16 | 6 |
| 21 | Solar/Zusatz | – | 13 | 5 | 13 |
| 24 | Sonderfunktion | – | 5 | – | 15 |
| 25 | Kessel (PuroWIN) | 44 | 15 | 24 | 61 |
| 26 | Wärmepumpe | – | 7 | 19 | 5 |
| 27 | Wärmepumpe | – | 23 | 10 | 38 |

Datenbestand: 635 Datenpunktnamen, 162 Enum-Tabellen, 217 Störungstexte.

## Kategorien

- **Info** – Messwerte und Zustände, immer aktiv.
- **Betreiber** – bedienbare Parameter der Betreiberebene, als Select, Number,
  Switch, Time oder Date, aktiv.
- **Service** – Serviceparameter (Heizkurve, Grenzwerte, Estrichprogramm).
  Vorhanden, aber deaktiviert; pro Entity in Home Assistant aktivierbar.

## Nicht enthalten

- Datenpunkte, die die Anlage nicht bereitstellt (Antwort 404 oder 409).
- Datenpunkte der OEM-Ebene.
- Das gepackte Statusregister `/32/0/14`; Gerätemeldungen werden stattdessen aus
  dem Feld `FE01msg` der Anlagenstruktur gelesen.

## Eigene Anlage prüfen

```bash
python tools/heatnexus_probe.py all <host>
```

Das Werkzeug liest die Anlage menüweise aus und schreibt JSON, eine CSV aller
Datenpunkte sowie einen Bericht, der gegenüberstellt, was die Anlage liefert und
was die Geräte-Datenbank kennt. Unter Windows genügt `tools/probe.cmd`.
