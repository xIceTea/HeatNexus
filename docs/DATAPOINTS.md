# Datenpunkte

**Erzeugt aus `device_db.json` – nicht von Hand ändern.**
Neu erzeugen mit `python tools/build_datenpunkte_doku.py`.

Die Integration erkennt Datenpunkte auf zwei Wegen: über kuratierte Tabellen
in `const.py` (fester Name, Einheit, Kategorie, Symbol) und über diese
Geräte-Datenbank, die die Bedienebenen je Funktionstyp beschreibt. Welche
davon tatsächlich angelegt werden, entscheidet die Anlage: Nicht vorhandene
werden entfernt, schreibgeschützte nur lesend angelegt.

Eine OID ist `<gn>/<mn>`; die vollständige Adresse lautet
`/1/<nodeId>/<fctId>/<gn>/<mn>/0`. Siehe [API.md](API.md).

## Funktionstypen

Die Anlage meldet je Funktion nur eine Zahl. Was sie bedeutet, ist aus der
Parameterliste des Herstellers abgeleitet – welche Datenpunkte ein Typ führt,
sagt, was er ist. **Nicht aus dem Namen raten**, den ein Installateur vergeben
hat.

| fctType | Funktion | woran erkennbar | Info | Betreiber | Service | Werk |
|---|---|---|---|---|---|---|
| 1 | Heizkreis (Infinity PLUS) | Heizkurve, Kühlgrenzen, Estrichprogramm | 14 | 17 | 35 | – |
| 2 | Warmwasser | WW-Programm, Hygiene-Programm, Zirkulationspumpe | 11 | 17 | 8 | 4 |
| 4 | Kaskade / hydraulische Weiche | Folgeschaltung, Zusatzkessel ZSK | 7 | 17 | 25 | – |
| 5 | Solar | Kollektortemperatur, Kollektor spülen, Hydraulikschema | 15 | 6 | 8 | – |
| 6 | Kessel (Gas / Öl) | Ionisationsstrom, Anlagendruck, Netzbetriebsstunden | 10 | – | 13 | – |
| 7 | Wärmepumpe | COP, Silentmode, Betriebsstunden Heizen/Warmwasser | 23 | 10 | 50 | 74 |
| 8 | E-Heizung / Zusatzheizung | Aktuelle Stufe, Betriebsstunden Stufe 1–3 | 9 | – | 10 | 23 |
| 9 | Kessel (BioWIN) | Laufzeit bis Reinigung, Brennstoffverbrauch, Sonden | 21 | 27 | 103 | 376 |
| 10 | Kessel (Automatik-/Zusatzkessel) | Startverzögerung, O2-Signal | 17 | 5 | 39 | – |
| 14 | Heizkreis (UML / UMLZ) | wie 1, ältere Baureihe, Warmwasser inbegriffen | 19 | 28 | 49 | 13 |
| 15 | Umschaltung | Automatikkessel / Festbrennstoff / Puffer, Umschaltventil | 8 | 1 | 20 | – |
| 16 | Puffer (B-PLMi) | TPE, TPA, TPT, Pufferladepumpe | 15 | 2 | 16 | – |
| 20 | ZSP Pumpen-/Relaismodul | Pumpensteuerung, ext. Wärmeanforderung, Sammelstörung | 6 | 16 | 6 | – |
| 21 | Puffer | Puffertemperatur oben/mitte/unten, Beladegrad | 13 | 5 | 21 | – |
| 24 | Pumpe Wärmeerzeuger / Schichtladung | Rücklaufhochhaltung, Mischer | 5 | – | 16 | – |
| 25 | Kessel (PuroWIN) | Hackgut und Pellets | 10 | 24 | 64 | 289 |
| 26 | Wärmepumpe (Energiemanagement) | Stromtarife, PV-Eingang, SG Ready | 5 | 19 | 5 | 57 |
| 27 | Wärmepumpe | Betriebsphase, Wärmemenge Heizen/Kühlen, E-Heizung | 21 | 15 | 47 | – |

`fctType -1` sind die internen Netzwerkvariablen (`NV's`); sie tragen keine
Datenpunkte und werden übersprungen.

## Bedienebenen

- **Info** – Messwerte und Zustände, immer aktiv.
- **Betreiber** – bedienbare Parameter, als Select, Number, Switch, Time oder
  Date, aktiv.
- **Service** – Fachparameter (Heizkurve, Grenzwerte, Estrichprogramm).
  Angelegt, aber deaktiviert; je Entität in Home Assistant aktivierbar.
- **Werk** – Herstellerparameter. Nur sichtbar, wenn ausdrücklich gewählt.

## Datenpunkte je Funktionstyp

### fctType 1 – Heizkreis (Infinity PLUS)

| OID | Name | Ebene |
|---|---|---|
| `0/0` | Aussentemperatur | Info |
| `0/1` | Raumtemperatur Aktueller Wert | Info |
| `0/2` | Vorlauftemperatur Aktueller Wert | Info |
| `1/1` | Raumtemperatur Sollwert Heizen | Info |
| `1/2` | Vorlauftemperatur Sollwert | Info |
| `2/9` | Betriebsart | Info |
| `2/10` | Dauer | Betreiber |
| `2/70` | Datum | Info |
| `2/72` | Uhrzeit | Info |
| `3/2` | TA Absenkbetrieb | Service |
| `3/4` | Temperatur | Betreiber |
| `3/7` | Kompensation | Service |
| `3/21` | TA Heizbetrieb | Service |
| `3/30` | Nachstellzeit | Service |
| `3/50` | Betriebswahl | Betreiber |
| `3/51` | Heizbetrieb | Betreiber |
| `3/53` | Absenkbetrieb | Betreiber |
| `3/58` | Behaglichkeit Korrekturwert | Betreiber |
| `3/61` | Programm 1 | Betreiber |
| `3/62` | Programm 2 | Betreiber |
| `3/63` | Programm 3 | Betreiber |
| `3/78` | Urlaubsprogramm bis Datum | Betreiber |
| `4/60` | Programm | Service |
| `4/63` | T-Beharrung | Service |
| `4/64` | Dauer Beharrung | Service |
| `4/65` | T-Aufheizphase | Service |
| `4/66` | T-Abkühlphase | Service |
| `4/67` | Dauer T-Änderung | Service |
| `4/77` | Anzahl Heizkreise | Service |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `5/8` | WW-Ladung max. Ladevorrang | Service |
| `7/1` | Kesseltemp.-Überhöhung Heizkreis | Service |
| `7/2` | Vorlauf min. | Service |
| `7/8` | Vorlauf max. | Service |
| `7/76` | Heizkreis | Service |
| `39/112` | MAC-Adresse | Info |
| `58/28` | Heizkurve Niveau | Service |
| `58/29` | Heizkurve Neigung | Service |
| `58/48` | Heizkreispumpe | Info |
| `58/49` | Mischer | Info |
| `58/70` | Solar | Service |
| `58/78` | Programm 1 | Betreiber |
| `58/79` | Programm 2 | Betreiber |
| `58/80` | Programm 3 | Betreiber |
| `58/81` | Heizbetrieb | Betreiber |
| `58/82` | Absenkbetrieb | Betreiber |
| `58/83` | Motor Mischventil | Service |
| `58/84` | Mischerlaufzeit | Service |
| `58/87` | T-Start | Service |
| `58/101` | Warmwasser | Service |
| `58/102` | Kühlen | Service |
| `59/46` | Minimale Vorlauftemperatur Kühlen | Service |
| `59/47` | Kühlen bei Programm 1 - 3 aktiv | Betreiber |
| `59/48` | Kühlprogramm | Betreiber |
| `59/50` | TA Kühlbetrieb | Service |
| `59/52` | Raumtemperatur Sollwert Kühlen | Info |
| `59/64` | Kühlkurve Aussentemperatur 1 | Service |
| `59/65` | Kühlkurve Vorlauftemperatur 1 | Service |
| `59/66` | Kühlkurve Aussentemperatur 2 | Service |
| `59/67` | Kühlkurve Vorlauftemperatur 2 | Service |
| `60/3` | Aktueller Offset Heizkreis Energy Pilot | Service |
| `60/4` | Aktueller Offset Kältekreis Energy Pilot | Service |
| `60/14` | Wärmeerzeuger einbinden | Service |
| `60/26` | Mischventil vorhanden | Service |
| `63/2` | Mischer | Service |

### fctType 2 – Warmwasser

| OID | Name | Ebene |
|---|---|---|
| `0/4` | WW-Temperatur Aktueller Wert | Info |
| `0/118` | WW-Zirkulationstemperatur Aktueller Wert | Info |
| `1/4` | WW-Temperatur Sollwert | Info, Betreiber |
| `1/118` | WW-Zirkulationstemperatur Sollwert | Info |
| `2/2` | Aktive Aktoren | Service |
| `2/16` | Freigabe starten | Betreiber |
| `2/70` | Datum | Info |
| `2/72` | Uhrzeit | Info |
| `3/78` | Urlaubsprogramm bis Datum | Betreiber |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `5/0` | Hysterese Ein | Service |
| `5/1` | WW-Überhöhung | Service |
| `5/6` | WW-Zirkulationspumpe | Service |
| `5/51` | Temperatur | Betreiber |
| `5/61` | WW-Programm | Betreiber |
| `5/64` | WW-Zirkulationsprogramm | Betreiber |
| `5/65` | WW-Zirkulationsprogramm | Betreiber |
| `5/70` | Einschaltzeit | Service |
| `5/71` | Ausschaltzeit | Service |
| `5/76` | WW-Kreis | Service |
| `39/112` | MAC-Adresse | Info |
| `51/104` | WW-Temperatur Sollwert | Betreiber |
| `51/109` | Zeitprogramm WW | Betreiber |
| `51/112` | Betriebswahl | Betreiber |
| `51/123` | AEW Evo Message ID of the top temperature sensor | Werk |
| `51/124` | AEW Evo Excess energy target temp | Werk |
| `52/115` | TerraWIN Hot Water Tank Use Excess Energy | Werk |
| `52/116` | TerraWIN Hot Water reduced Set temperature | Werk |
| `58/38` | Betriebswahl | Betreiber |
| `58/52` | WW-Ladepumpe | Info |
| `58/89` | WW-Temperatur Maximalwert | Service |
| `58/107` | Wochentag | Betreiber |
| `58/108` | Startzeit | Betreiber |
| `58/109` | Solltemperatur | Betreiber |
| `58/110` | Zirkulationspumpenlaufzeit | Betreiber |
| `58/111` | Mit Zeitsteuerung | Betreiber |
| `58/113` | Freigabe starten | Betreiber |
| `59/18` | WW-Zirkulationspumpe | Info |

### fctType 4 – Kaskade / hydraulische Weiche

| OID | Name | Ebene |
|---|---|---|
| `0/7` | Kesseltemperatur | Info |
| `2/2` | Aktive Aktoren | Info |
| `2/9` | Betriebsart | Info |
| `2/70` | Datum | Betreiber |
| `2/72` | Uhrzeit | Betreiber |
| `4/12` | Systemzeit | Service |
| `4/82` | Zeitprogramm | Betreiber |
| `4/92` | Softwareversion | Service |
| `4/93` | Hardwareversion | Service |
| `5/2` | P-Vorrang | Service |
| `6/4` | Überhöhung | Service |
| `6/6` | Minimalwert | Service |
| `6/17` | Sollwertrampe | Service |
| `6/19` | Sollwertsprung | Service |
| `6/20` | Zeitverzögerung | Service |
| `6/25` | Maximalwert | Service |
| `6/32` | Anzahl der WEZ | Service |
| `7/12` | Drehzahlregelung | Betreiber |
| `7/21` | – | Service |
| `9/0` | Nachlaufzeit | Service |
| `9/19` | Hysterese | Service |
| `9/31` | Mindestlaufzeit mit Pufferspeicher | Service |
| `9/32` | Minimalwert | Service |
| `9/35` | Hysterese | Service |
| `9/37` | Sollwert-Offset | Betreiber |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Betreiber |
| `11/8` | Zuordnung zu WEZ | Betreiber |
| `11/9` | Führungskessel | Service |
| `20/14` | min. Drehzahl | Betreiber, Service |
| `20/15` | Betriebswahl | Info, Betreiber |
| `20/18` | Pumpensteuerung | Betreiber |
| `20/19` | Modulfunktionen | Service |
| `20/20` | Startleistung | Service |
| `20/21` | WW-Bedarf | Service |
| `20/22` | max. Drehzahl | Betreiber, Service |
| `20/23` | Digital-Sollwert WWK | Betreiber |
| `20/26` | Funktion | Service |
| `20/27` | B-Funktion | Service |
| `21/65` | Puffertemperatur TPE | Info |
| `21/66` | Puffertemperatur TPA | Info |
| `23/83` | Anzahl der Kessel in Betrieb | Info |
| `29/3` | Relaisfunktion | Betreiber |
| `29/21` | Eingang E1 | Betreiber |
| `29/30` | Summenstörmeldung Alarm | Betreiber |
| `29/31` | Summenstörmeldung Fehler | Betreiber |
| `29/32` | Summenstörmeldung Info | Betreiber |

### fctType 5 – Solar

| OID | Name | Ebene |
|---|---|---|
| `0/4` | WW-Temperatur Aktueller Wert | Info |
| `0/15` | Puffertemperatur oben | Info |
| `0/22` | Pumpensteuerung Drehzahl | Info |
| `2/70` | Datum | Info |
| `2/72` | Uhrzeit | Info |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `10/31` | Maximalwert | Service |
| `20/14` | min. Drehzahl | Service |
| `20/22` | max. Drehzahl | Service |
| `21/65` | Puffertemperatur TPE | Info |
| `39/112` | MAC-Adresse | Info |
| `43/99` | Wärmemengenzähler | Info |
| `43/101` | Volumenstrom | Info |
| `58/50` | Puffertemperatur TPS | Info |
| `58/56` | Kollektortemperatur | Info |
| `58/57` | Minimalwert | Service |
| `58/58` | Maximalwert | Service |
| `58/59` | Beginn | Betreiber |
| `58/60` | Ende | Betreiber |
| `58/61` | Laufzeit | Betreiber |
| `58/62` | Pausenzeit | Betreiber |
| `58/63` | Betriebswahl | Betreiber |
| `58/86` | Hydraulikschema Solar | Service |
| `58/97` | WW-Temperatur Solar | Info |
| `58/116` | Umschaltventil 1 | Service |
| `58/117` | Umschaltventil 2 | Service |
| `59/19` | Rücklauftemperatur | Info |
| `59/34` | WW-Temperatur Sollwert | Betreiber |

### fctType 6 – Kessel (Gas / Öl)

| OID | Name | Ebene |
|---|---|---|
| `0/4` | WW-Temperatur Aktueller Wert | Service |
| `0/7` | Kesseltemperatur | Info, Service |
| `0/9` | Kesselleistung | Info, Service |
| `0/11` | Abgastemperatur | Service |
| `1/7` | Kesseltemperatur Soll | Info, Service |
| `2/70` | Datum | Info |
| `2/72` | Uhrzeit | Info |
| `2/81` | Betriebsstunden | Service |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `52/16` | Rücklauftemperatur | Service |
| `59/17` | Betriebsphase | Info |
| `60/27` | Anlagendruck | Info, Service |
| `60/29` | Betriebsstunden seit letztem Service | Info, Service |
| `60/30` | Ionisationsstrom | Service |
| `60/32` | Pumpendrehzahl | Service |
| `60/33` | Netzbetriebsstunden | Service |
| `60/35` | Interner Fehlercode | Service |

### fctType 7 – Wärmepumpe

| OID | Name | Ebene |
|---|---|---|
| `2/70` | Datum | Betreiber |
| `2/72` | Uhrzeit | Betreiber |
| `2/81` | Betriebsstunden | Info |
| `3/78` | Urlaubsprogramm bis Datum | Betreiber |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `9/20` | Handbetrieb Solltemperatur | Werk |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Service, Werk |
| `12/39` | Maximalwert der Solltemperatur | Service, Werk |
| `20/106` | Analog-Sollwert | Werk |
| `37/1` | Grenze min. für Solltemperatur max | Werk |
| `37/2` | Grenze max. für Solltemperatur max | Werk |
| `37/5` | Soll-Temperatur Frostbetrieb | Werk |
| `37/10` | min. Wärmeanforderung | Werk |
| `37/11` | Soll-Temperatur min | Werk |
| `37/26` | Regler Kesseltemperatur P-Band | Werk |
| `37/27` | Regler Kesseltemperatur Nachstellzeit | Werk |
| `39/66` | Interner Fehler | Service |
| `39/115` | Seriennummer | Info |
| `40/73` | Grenze Min für Solltemperatur ext. Wärmeanforderung (09-057) | Werk |
| `40/74` | Grenze Max. für Solltemperatur ext. Wärmeanforderung (09-057) | Werk |
| `40/82` | Grenze Min für Solltemperatur Handbetrieb (09-020) | Werk |
| `40/83` | Grenze Max für Solltemperatur Handbetrieb (09-020) | Werk |
| `50/1` | Abtauen einleiten | Betreiber |
| `50/2` | Wärmepumpe-Typ Auswahl | Service, Werk |
| `50/3` | – | Service |
| `50/4` | Wärmepumpe-Typ | Werk |
| `50/5` | Betriebswahl | Betreiber |
| `50/6` | Betriebsphase | Service |
| `50/11` | Silentmode | Betreiber, Werk |
| `50/14` | Zeitprogramm Silentmode | Betreiber, Werk |
| `50/24` | Aktuelle Leistungsabgabe | Service |
| `50/26` | Aktuelle Leistung | Info |
| `50/32` | Silentmode Faktor | Betreiber, Werk |
| `50/40` | Lüftersolldrehzahl | Service |
| `50/41` | Verdichter Istdrehzahl | Service |
| `50/55` | Kesselpumpe min. Drehzahl | Service, Werk |
| `50/56` | Kesselpumpe max. Drehzahl | Service, Werk |
| `50/57` | Bypasspumpe min. Drehzahl | Service, Werk |
| `50/58` | Bypasspumpe max. Drehzahl | Service, Werk |
| `50/90` | Software Gateway | Service |
| `50/93` | Software Wärmepumpe | Service |
| `50/95` | Gateway Addresse | Werk |
| `50/100` | Status | Service |
| `51/30` | Aktuelle Leistungsaufnahme | Service |
| `51/32` | Offset für minimalen Volumenstrom Kühlen | Werk |
| `51/33` | Offset für minimalen Volumenstrom Abtauen | Werk |
| `51/34` | Maximale Rücklauftemperatur | Werk |
| `51/36` | Minimaler Volumenstrom Heizen min. | Werk |
| `51/37` | Minimaler Volumenstrom aktuell | Werk |
| `51/40` | Minimaler Volumenstrom Abtauen | Werk |
| `51/41` | Minimaler Volumenstrom | Werk |
| `51/42` | Maximale Vorlauftemperatur Heizen | Werk |
| `51/43` | Minimale Vorlauftemperatur Heizen | Werk |
| `51/44` | Maximale Vorlauftemperatur Kühlen | Werk |
| `51/45` | Minimale Vorlauftemperatur Kühlen | Werk |
| `51/46` | Maximale Außentemperatur Heizen | Werk |
| `51/47` | Minimale Außentemperatur Heizen | Werk |
| `51/50` | Minimale absolute thermische Senkenleistung Heizen | Werk |
| `51/51` | Minimale absolute thermische Senkenleistung Kühlen | Werk |
| `51/52` | Maximale absolute thermische Senkenleistung Heizen | Werk |
| `51/53` | Maximale absolute thermische Senkenleistung Kühlen | Werk |
| `51/54` | Verzögerung Überwachung Volumenstrom | Werk |
| `51/56` | Leistungsbeschränkung WW Sommerbetrieb | Betreiber, Werk |
| `51/61` | Positiver Sollwertsprung | Werk |
| `51/62` | Negativer Sollwertsprung | Werk |
| `51/64` | Hysterese Aus | Service, Werk |
| `51/65` | Hysterese Ein | Service, Werk |
| `51/69` | Minimale Stillstandszeit WP | Werk |
| `51/72` | Verzögerung Wärmeanforderung für WP | Werk |
| `51/77` | Bivalenzpunkt Hybrid-Betrieb | Werk |
| `51/78` | Hysterese Bivalenzpunkt Hybridbetrieb | Werk |
| `51/79` | Max. Leistung Hybrid-Betrieb 75% von A-7/W35 | Werk |
| `51/91` | Nachlaufzeit bei Stellgrad 0% | Werk |
| `51/92` | Minimale Laufzeit WP | Werk |
| `51/100` | Betriebswahl | Info, Betreiber |
| `51/101` | Status | Info |
| `51/113` | Wärmepumpentyp | Info |
| `51/114` | Fernzugriff aktivieren | Service |
| `51/125` | AEW Evo Total accumulated heating energy | Werk |
| `51/126` | AEW Evo Total accumulated electrical energy | Werk |
| `51/127` | AEW Evo Message ID of the flow temperature sensor | Werk |
| `52/0` | AEW Evo Actual power consumtion | Werk |
| `52/1` | AEW Evo Actual power consumtion electrical energy | Werk |
| `52/2` | AEW Evo Actual Source In temperature | Werk |
| `52/3` | AEW Evo Actual Source Out temperature | Werk |
| `52/4` | AEW Evo Source side actuator | Werk |
| `52/5` | AEW Evo Source side actuator | Werk |
| `52/11` | Fortlufttemperatur | Service |
| `52/12` | Aussentemperatur Wärmepumpe | Service |
| `52/13` | Temperatur Einspritzung | Service |
| `52/14` | Heißgastemperatur | Service |
| `52/15` | Vorlauftemperatur | Info, Service |
| `52/16` | Rücklauftemperatur | Info, Service |
| `52/17` | Sauggastemperatur | Service |
| `52/18` | Verdampferausstrittstemperatur | Service |
| `52/19` | Verdampfereintrittstemperatur | Service |
| `52/20` | Verflüssigeraustrittstemperatur | Service |
| `52/21` | Frostschutztemperatur | Service |
| `52/22` | Ölsumpftemperatur | Service |
| `52/30` | Niederdruck | Service |
| `52/31` | Mitteldruck | Service |
| `52/32` | Hochdruck | Service |
| `52/40` | COP aktuell | Info |
| `52/41` | Strombegrenzung Wärmepumpe | Service |
| `52/47` | Verdichtereintrittstemperatur | Service |
| `52/48` | Minimaler Volumenstrom Kühlen | Werk |
| `52/50` | Betriebsstunden Heizen | Info |
| `52/51` | Betriebsstunden Heizen heute | Info |
| `52/52` | Betriebsstunden Warmwasser | Info |
| `52/53` | Betriebsstunden Warmwasser heute | Info |
| `52/56` | Anzahl Starts | Info |
| `52/59` | Wärmemenge Heizen | Info |
| `52/60` | Wärmemenge Heizen heute | Info |
| `52/61` | Wärmemenge Warmwasser | Info |
| `52/62` | Wärmemenge Warmwasser heute | Info |
| `52/72` | Volumenstrom | Service |
| `52/74` | Silentmode Faktor Minimalwert | Werk |
| `52/87` | Ø COP Heizen heute | Info |
| `52/89` | Ø COP Warmwasser heute | Info |
| `52/100` | AP440 Alarm 1 | Service |
| `52/101` | AP440 Alarm 2 | Service |
| `52/102` | AP440 Alarm 3 | Service |
| `52/103` | AP440 Alarm 4 | Service |
| `52/104` | AP440 Alarm 5 | Service |
| `52/105` | AP440 Alarm 6 | Service |
| `52/106` | AP440 Alarm 7 | Service |
| `52/107` | AP440 Alarm 8 | Service |
| `52/108` | AP440 Alarm 9 | Service |
| `52/109` | AP440 Alarm 10 | Service |
| `52/117` | TerraWIN Heat pump operating mode | Werk |
| `52/118` | TerraWIN sDiagnosisData.heatpump[0].excessEnergy | Werk |
| `52/119` | TerraWIN Total accumulated heating energy | Werk |
| `52/120` | Total accumulated electrical energy | Werk |
| `52/121` | Vorlauftemperatur Soll | Info |
| `52/122` | TerraWIN Consuming Excess Energy | Werk |
| `52/123` | TerraWIN Set value compressor | Werk |
| `52/124` | TerraWIN Set temperature heat pump | Werk |
| `55/20` | Inverterbegrenzung | Service |
| `56/4` | Anzahl Stufen E-Heizung | Service, Werk |

### fctType 8 – E-Heizung / Zusatzheizung

| OID | Name | Ebene |
|---|---|---|
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `9/20` | Handbetrieb Solltemperatur | Werk |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Service, Werk |
| `12/39` | Maximalwert der Solltemperatur | Service, Werk |
| `20/106` | Analog-Sollwert | Werk |
| `37/1` | Grenze min. für Solltemperatur max | Werk |
| `37/2` | Grenze max. für Solltemperatur max | Werk |
| `37/5` | Soll-Temperatur Frostbetrieb | Werk |
| `37/10` | min. Wärmeanforderung | Werk |
| `37/11` | Soll-Temperatur min | Werk |
| `37/26` | Regler Kesseltemperatur P-Band | Werk |
| `37/27` | Regler Kesseltemperatur Nachstellzeit | Werk |
| `39/66` | Interner Fehler | Service |
| `40/73` | Grenze Min für Solltemperatur ext. Wärmeanforderung (09-057) | Werk |
| `40/74` | Grenze Max. für Solltemperatur ext. Wärmeanforderung (09-057) | Werk |
| `40/82` | Grenze Min für Solltemperatur Handbetrieb (09-020) | Werk |
| `40/83` | Grenze Max für Solltemperatur Handbetrieb (09-020) | Werk |
| `50/6` | Betriebsphase | Service |
| `51/30` | Aktuelle Leistungsaufnahme | Service |
| `51/64` | Hysterese Aus | Service, Werk |
| `51/65` | Hysterese Ein | Service, Werk |
| `52/50` | Betriebsstunden Heizen | Info |
| `52/51` | Betriebsstunden Heizen heute | Info |
| `52/52` | Betriebsstunden Warmwasser | Info |
| `52/53` | Betriebsstunden Warmwasser heute | Info |
| `52/56` | Anzahl Starts | Info |
| `52/121` | Vorlauftemperatur Soll | Info |
| `56/5` | Aktuelle Stufe E-Heizung | Info |
| `56/10` | Stellgrad E-Heizung Stufe 2 Ein | Werk |
| `56/11` | Stellgrad E-Heizung Stufe 3 Ein | Werk |
| `56/12` | Stellgrad E-Heizung Hysterese Leistung | Werk |
| `56/15` | Temperaturdifferenz für Error 4680 | Werk |
| `56/16` | Verzögerungszeit Error 4680 | Werk |
| `56/17` | Delta Rücklauf bei Error 1790 | Werk |
| `56/26` | Betriebsstunden Stufe 1 | Service |
| `56/27` | Betriebsstunden Stufe 2 | Service |
| `56/28` | Betriebsstunden Stufe 3 | Service |

### fctType 9 – Kessel (BioWIN)

| OID | Name | Ebene |
|---|---|---|
| `0/7` | Kesseltemperatur | Info, Service |
| `0/8` | Rücklauftemperatur Aktueller Wert | Service, Werk |
| `0/9` | Kesselleistung | Info |
| `0/11` | Abgastemperatur | Info |
| `0/15` | Puffertemperatur oben | Service |
| `0/16` | Puffertemperatur unten | Service |
| `0/17` | Puffertemperatur mitte | Service |
| `0/42` | O2 Signal | Service |
| `0/45` | Brennkammertemperatur | Service |
| `0/96` | Weichen-/Puffertemperatur | Info |
| `1/7` | Kesseltemperatur Soll | Info |
| `1/8` | Rücklauftemperatur Sollwert | Service |
| `2/1` | Betriebsphase | Service |
| `2/70` | Datum | Info, Betreiber |
| `2/72` | Uhrzeit | Info, Betreiber |
| `2/80` | Anzahl der Brennerstarts | Info |
| `2/81` | Betriebsstunden | Info |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `7/12` | Drehzahlregelung | Werk |
| `9/20` | Handbetrieb Solltemperatur | Werk |
| `9/21` | Hysterese Brenner EIN | Service, Werk |
| `9/31` | Mindestlaufzeit mit Pufferspeicher | Service |
| `9/32` | Minimalwert | Service |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Service, Werk |
| `11/27` | WEZ-Nummer | Info, Service, Werk |
| `12/38` | Gerätetyp | Info |
| `12/39` | Maximalwert der Solltemperatur | Service, Werk |
| `12/40` | Kesseltemperatur für Neustart | Service |
| `12/41` | Kesselsollwert Fremdregelung (BUML TTL) | Service |
| `12/42` | Startverzögerung Automatikkessel | Service |
| `12/98` | Minimalwert | Service |
| `12/99` | Maximalwert | Service |
| `12/100` | Bereich | Service, Werk |
| `12/101` | Istwert | Service, Werk |
| `12/102` | Förderzeit Zündphase | Service |
| `12/103` | Ausbrand | Service |
| `12/104` | Korrektur | Service, Werk |
| `12/105` | Elektrische Zündung | Service |
| `12/106` | Minimale Abgastemperatur | Service, Werk |
| `14/10` | Zuführung mit Freigabezeit Ende | Betreiber, Werk |
| `14/11` | Zuführung mit Freigabezeit Beginn | Betreiber, Werk |
| `14/19` | Betriebsart Zuführung | Betreiber, Werk |
| `14/20` | Zuführung mit Startzeit | Betreiber, Werk |
| `14/21` | Sondenumschaltung | Betreiber |
| `14/22` | Laufzeit der Saugturbine | Service |
| `14/23` | Art des Brennstoffzuführsystems | Service |
| `14/70` | Anzahl der Rostrüttelungen Ausbrand | Service |
| `14/71` | Anzahl der Rostrüttelungen Betrieb | Service |
| `14/72` | Startzeiten für Ascheverdichtung Startzeit 1 | Betreiber |
| `14/73` | Startzeiten für Ascheverdichtung Startzeit 2 | Betreiber |
| `14/74` | Reinigung bestätigen | Betreiber |
| `14/75` | Korrektur Reinigungsintervall | Betreiber, Service, Werk |
| `14/76` | Profil Entaschung | Service, Werk |
| `14/77` | Eingang X14/5 | Service |
| `14/78` | Zuluftklappe Laufzeit | Service |
| `14/79` | Beginn Sperrzeit | Betreiber, Werk |
| `14/80` | Dauer | Betreiber, Werk |
| `20/14` | min. Drehzahl | Service, Werk |
| `20/22` | max. Drehzahl | Service, Werk |
| `20/28` | Minimale Laufzeit | Service |
| `20/61` | Laufzeit bis Reinigung | Info |
| `20/62` | Laufzeit bis Hauptreinigung | Info |
| `20/63` | Laufzeit bis Wartung | Info |
| `20/64` | Betriebsart | Service |
| `20/87` | Verbrauch Spülwasser | Info |
| `20/97` | Hysterese TK-Soll Ausschalten (nach oben) | Werk |
| `20/98` | Soll-Leistung min. | Werk |
| `20/99` | Soll-Leistung max. | Werk |
| `20/106` | Analog-Sollwert | Werk |
| `23/87` | Puffer-Beladegrad | Service |
| `23/88` | Saugzuggebläse Soll-Drehzahl | Service |
| `23/89` | Saugzuggebläse Ist-Drehzahl | Service |
| `23/90` | Position Primär-LK | Service |
| `23/91` | Position Sekundär-LK | Service |
| `23/93` | EnergyHold Heizkreis (BUML TTL) | Service |
| `23/94` | Endschalter Primärluftklappe | Service |
| `23/95` | Endschalter Sekundärluftklappe | Service |
| `23/97` | Druckschalter | Service |
| `23/98` | O2 Heizstrom | Service |
| `23/100` | Brennstoffverbrauch seit Befüllung | Betreiber |
| `23/103` | Brennstoffverbrauch gesamt | Info |
| `29/30` | Summenstörmeldung Alarm | Service |
| `29/31` | Summenstörmeldung Fehler | Service |
| `29/32` | Summenstörmeldung Info | Service |
| `37/0` | Soll-Temperatur Kaminkehrer | Werk |
| `37/1` | Grenze min. für Solltemperatur max | Werk |
| `37/2` | Grenze max. für Solltemperatur max | Werk |
| `37/3` | Nachlaufzeit bei TK > Tksoll + Hyst | Werk |
| `37/4` | Handbetrieb max. Soll-Temperatur | Werk |
| `37/5` | Soll-Temperatur Frostbetrieb | Werk |
| `37/9` | Sollwertsprung | Werk |
| `37/10` | min. Wärmeanforderung | Werk |
| `37/11` | Soll-Temperatur min | Werk |
| `37/18` | Soll-Temperatur Min für Start Brenner | Werk |
| `37/19` | Minimale Kesselrücklauftemperatur für PW_Status | Werk |
| `37/20` | Kesselminimaltemperatur wird nicht erreicht | Werk |
| `37/22` | Max-Temperatur | Werk |
| `37/23` | Max-Temperatur MIN | Werk |
| `37/24` | Max-Temperatur MAX | Werk |
| `37/25` | Max-Temperatur Differenz | Werk |
| `37/26` | Regler Kesseltemperatur P-Band | Werk |
| `37/27` | Regler Kesseltemperatur Nachstellzeit | Werk |
| `37/29` | Minimale Kesselleistung | Service, Werk |
| `37/31` | Laufzeit Brenner gesperrt | Werk |
| `37/32` | Überhöhung Solltemperatur min. während Anfahrtsentlastung | Werk |
| `37/33` | Reduktion Solltemperatur min. in K/min nach Anfahrtsentlastung | Werk |
| `37/34` | EnergyHold Sollwert MES/REG | Werk |
| `37/35` | EnergyHold Sollwert bei Kaminkehrer | Werk |
| `37/36` | EnergyHold Hysterese bei Kaminkehrer | Werk |
| `37/37` | EnergyHold Hysterese für Sollwert EnergyHold MES/REG | Werk |
| `37/38` | Laufzeit ohne EnergyHold MES nach Start Brenner | Werk |
| `37/39` | Minmale Brennerlaufzeit für PW_Status | Werk |
| `37/40` | Offset TK-EnergyHold | Werk |
| `37/41` | EnergyHold Hysterese | Werk |
| `37/42` | Offset TK-EnergyHold bei Mindestlaufzeit Brenner | Werk |
| `37/43` | Saugzuggebläse maximale Änderung Istdrehzahl für Rückmeldung Solldrehzahl erreicht | Werk |
| `37/44` | Pufferladung | Service |
| `37/45` | EnergyHold Offset für TK_Soll | Werk |
| `37/46` | Sollwert für Error 3980 | Werk |
| `37/53` | Maximale Laufzeit Kaminkehrer | Werk |
| `37/57` | Soll-Temperatur Abgashochhaltung min | Werk |
| `37/58` | Soll-Temperatur Abgashochhaltung max | Werk |
| `37/59` | Regler Abgashochhaltung P-Band | Werk |
| `37/60` | Regler Abgashochhaltung Nachstellzeit | Werk |
| `37/108` | Ascheschieber Zeit Endschalter verlassen | Werk |
| `37/120` | Ascheaustragung Normalstrom Unteres Limit | Werk |
| `37/121` | Ascheaustragung Normalstrom Oberes Limit | Werk |
| `37/122` | Nachheizflächenreinigung Normalstrom Unteres Limit | Werk |
| `37/123` | Nachheizflächenreinigung Normalstrom Oberes Limit | Werk |
| `37/126` | Primärzündung Laufzeit bis Takt | Werk |
| `37/127` | Primärzündung Taktzeit Aus | Werk |
| `38/0` | Primärzündung Taktzeit Ein | Werk |
| `38/10` | Soll_Leistung Kaminkehrer Default | Werk |
| `38/31` | Ascheschieber Laufzeit Endlage - Endlage | Werk |
| `38/32` | Ascheschieber Nachlaufzeit Endlage geschlossen | Werk |
| `38/48` | Pause Ascheaustragung nach Entaschung | Werk |
| `38/63` | Minimale Laufzeit Vorspülen | Werk |
| `38/96` | Endposition Stirring | Werk |
| `38/99` | Laufzeit bis HFR im Modulationsbetrieb | Werk |
| `38/100` | Laufzeit HFR im Modulationsbetrieb und Primärausbrand | Werk |
| `38/101` | Laufzeit HFR Standschutz | Werk |
| `38/103` | Laufzeit Ascheaustragung | Werk |
| `38/104` | Laufzeit Ascheaustragung Standschutz | Werk |
| `39/18` | Restlaufzeit im Modulationsbetrieb bis HFR | Werk |
| `39/66` | Interner Fehler | Service |
| `39/90` | Brenner sperren | Service |
| `39/94` | Reinigung bestätigen | Betreiber |
| `39/95` | Brennstoffzuführung anfordern | Betreiber |
| `39/100` | Wartung | Service |
| `39/112` | MAC-Adresse | Info |
| `40/28` | Wartung Aus/Ein | Service, Werk |
| `40/44` | Blockade Stokerschnecke | Service |
| `40/53` | Blockade Entaschung | Service |
| `40/60` | Blockade Ascheaustragung | Service |
| `40/61` | Blockade Heizflächenreinigung | Service |
| `40/73` | Grenze Min für Solltemperatur ext. Wärmeanforderung (09-057) | Werk |
| `40/74` | Grenze Max. für Solltemperatur ext. Wärmeanforderung (09-057) | Werk |
| `40/75` | EnergyHold Anfahrtsentlastung für PW_Staus PID: Kp | Werk |
| `40/76` | EnergyHold Anfahrtsentlastung für PW_Staus PID: Tn | Werk |
| `40/82` | Grenze Min für Solltemperatur Handbetrieb (09-020) | Werk |
| `40/83` | Grenze Max für Solltemperatur Handbetrieb (09-020) | Werk |
| `40/88` | EnergyHold Mindestwaermeabnahme für PW_Staus PID: Kp | Werk |
| `40/89` | EnergyHold Mindestwaermeabnahme für PW_Staus PID: Tn | Werk |
| `40/90` | Differenz für Synchronisation Reinigung und Hauptreinigung | Werk |
| `40/92` | Korrektur Menge Förderschnecke Kaminkehrer | Werk |
| `40/93` | Korrekturfaktor Brennstoffmenge Kaminkehrer | Werk |
| `40/100` | Laufzeit Ventil Rezirkulation | Werk |
| `40/101` | Ventil Abgas-Rezirkulation | Werk |
| `40/103` | Ventil Rezirkulation Modulationsbetrieb | Werk |
| `40/105` | Abgas-Rezirkulation | Werk |
| `40/114` | Rezirkulation minimale Abgastemperatur | Werk |
| `40/115` | Rezirkulation minimale Abgastemperatur Hysterese | Werk |
| `40/116` | Rezirkulation minimale Leistung | Werk |
| `40/117` | Rezirkulation minimale Leistung Hysterese | Werk |
| `40/118` | Laufzeit im Modulationsbetrieb bis HFR | Werk |
| `40/119` | Laufzeit 1 HFR | Werk |
| `40/120` | Laufzeit 2 HFR | Werk |
| `40/121` | Zeitprogramm Heizflächenreinigung | Werk |
| `41/0` | Förderschnecke Normalstrom Unteres Limit | Werk |
| `41/1` | Förderschnecke Normalstrom Oberes Limit | Werk |
| `41/2` | Primärzündung 2 Normalstrom Unteres Limit | Werk |
| `41/3` | Primärzündung 2 Normalstrom Oberes Limit | Werk |
| `41/4` | Max. Zeit Selbsttest Sondenumschaltung mit 3 Sonden | Werk |
| `41/5` | Max. Zeit Selbsttest Sondenumschaltung mit 8 Sonden | Werk |
| `41/6` | Max. Zeit Position Sondenumschaltung mit 3 Sonden | Werk |
| `41/7` | Max. Zeit Position Sondenumschaltung mit 8 Sonden | Werk |
| `41/8` | Korrektur Ascheaustragung | Service, Werk |
| `41/9` | Brennstoffmenge Ascheaustragung | Werk |
| `41/10` | TK für Status BioWIN Hybrid | Werk |
| `41/11` | Zeit Kalt - / Warmstart | Werk |
| `41/12` | Soll-Brennstoffmenge min | Werk |
| `41/13` | Soll-Brennstoffmenge max | Werk |
| `41/14` | Zyklusdauer Förderschnecke | Werk |
| `41/15` | Minimale Laufzeit Förderschnecke | Werk |
| `41/16` | Nachlaufzeit Motor Förderschnecke | Werk |
| `41/17` | Drehrichtung Förderschnecke | Werk |
| `41/18` | Zündphase Ansteuerung Förderschnecke Start Rampe | Werk |
| `41/19` | Soll- Brennkammertemperatur kompensiert 100% | Werk |
| `41/20` | Soll- Brennkammertemperatur kompensiert 90% | Werk |
| `41/21` | Soll- Brennkammertemperatur kompensiert 80% | Werk |
| `41/22` | Soll- Brennkammertemperatur kompensiert 70% | Werk |
| `41/23` | Soll- Brennkammertemperatur kompensiert 60% | Werk |
| `41/24` | Soll- Brennkammertemperatur kompensiert 50% | Werk |
| `41/25` | Soll- Brennkammertemperatur kompensiert 40% | Werk |
| `41/26` | Soll- Brennkammertemperatur kompensiert 30% | Werk |
| `41/27` | Verzögerung Überwachung Brennraumtemperatur bei Anstieg | Werk |
| `41/28` | Zündphase Ansteuerung Förderschnecke Warmstart | Werk |
| `41/29` | Auswahl Primärzündung | Werk |
| `41/30` | Änderung Brennstoffmenge / K bei 100% Leistung | Werk |
| `41/31` | Änderung Brennstoffmenge / K bei 30% Leistung | Werk |
| `41/32` | Integrator Brennstoffmenge | Werk |
| `41/33` | Faktor Kesseltemperatur für Mittelwert | Werk |
| `41/34` | Divisor Korrektur Menge Förderschnecke | Werk |
| `41/35` | Maximale Ausbrandzeit | Werk |
| `41/36` | Menge Förderschnecke Default Min | Werk |
| `41/37` | Menge Förderschnecke Default Max | Werk |
| `41/38` | Menge Förderschnecke berechnet Regelbereich | Werk |
| `41/39` | Brennstoffmenge Reinigung Klassik Stufe 0 | Werk |
| `41/40` | Brennstoffmenge Reinigung Klassik Stufe 1 | Werk |
| `41/41` | Brennstoffmenge Reinigung Klassik Stufe 2 | Werk |
| `41/42` | Brennstoffmenge Reinigung Klassik Stufe 3 | Werk |
| `41/43` | Brennstoffmenge Reinigung Exklusiv Stufe 0 | Werk |
| `41/44` | Brennstoffmenge Reinigung Exklusiv Stufe 1 | Werk |
| `41/45` | Brennstoffmenge Reinigung Exklusiv Stufe 2 | Werk |
| `41/46` | Brennstoffmenge Reinigung Exklusiv Stufe 3 | Werk |
| `41/47` | Anzahl Reinigung bis Hauptreinigung Klassik | Werk |
| `41/48` | Anzahl Reinigung bis Hauptreinigung Exklusiv | Werk |
| `41/49` | Faktor Brennstoffmenge Reinigung bis Wartung Klassik | Werk |
| `41/50` | Faktor Brennstoffmenge Reinigung bis Wartung Exklusiv | Werk |
| `41/51` | Streikbetrieb | Service, Werk |
| `41/52` | Laufzeit Förderschnecke vorwärts bei Blockade | Werk |
| `41/53` | Laufzeit Förderschnecke rückwärts bei Blockade | Werk |
| `41/54` | Zuluftklappe | Service, Werk |
| `41/55` | Vorspülen maximale Laufzeit | Werk |
| `41/56` | Zuluftklappe Laufzeit | Service, Werk |
| `41/57` | Vorspülen Brennkammertemperatur | Werk |
| `41/58` | Vorspülen Gebläsedrehzahl bei TK 20°C | Werk |
| `41/59` | Vorspülen Gebläsedrehzahl bei TK 80°C | Werk |
| `41/60` | Förderzeit Zündphase | Service, Werk |
| `41/61` | Zündphase Laufzeit Förderschnecke Grenze min | Werk |
| `41/62` | Zündphase Laufzeit Förderschnecke Grenze max | Werk |
| `41/63` | Zündphase 2. Laufzeit Förderschnecke | Werk |
| `41/64` | Zündphase Ansteuerung Förderschnecke Kaltstart | Werk |
| `41/65` | Zündphase Anstieg Brennkammertemperatur | Werk |
| `41/66` | Zündphase Saugzuggebläse Drehzahl | Werk |
| `41/67` | Zündphase Maximale Änderungsgeschwindigkeit/sec Saugzuggebläse | Werk |
| `41/68` | Zündphase Zeit bis Flammenbildung | Werk |
| `41/69` | Flammenstabilisierung Maximale Änderungsgeschwindigkeit/sec Brennstoffdosierung | Werk |
| `41/70` | Flammenstabilisierung Brennkammertemperatur Austritt | Werk |
| `41/71` | Flammenstabilisierung maximale Laufzeit | Werk |
| `41/72` | Maximale Gebläsedrehzahl | Service, Werk |
| `41/73` | Modulation Saugzuggebläse Drehzahl 100% min | Werk |
| `41/74` | Modulation Saugzuggebläse Drehzahl 100% max | Werk |
| `41/75` | Minimale Gebläsedrehzahl | Service, Werk |
| `41/76` | Modulation Saugzuggebläse Drehzahl 30% min | Werk |
| `41/77` | Modulation Saugzuggebläse Drehzahl 30% max | Werk |
| `41/78` | Modulation Maximale Änderungsgeschwindigkeit/sec Saugzuggebläse negativ | Werk |
| `41/79` | Modulation Maximale Laufzeit Stufe 0 | Werk |
| `41/80` | Modulation Maximale Laufzeit Stufe 1 | Werk |
| `41/81` | Modulation Maximale Laufzeit Stufe 2 | Werk |
| `41/82` | Modulation Maximale Laufzeit Stufe 3 | Werk |
| `41/83` | Saugzuggebläse Drehzahl Brennraumtür offen | Werk |
| `41/84` | Modulation Minimale Brennkammertemperatur | Werk |
| `41/85` | Modulation Start Überwachung Brennkammertemperatur | Werk |
| `41/86` | Modulation Maximale Änderungsgeschwindigkeit/sec Saugzuggebläse positiv | Werk |
| `41/87` | Modulation Faktor für Grenztemperatur | Werk |
| `41/88` | Soll- Brennkammertemperatur K-Wert PT1 | Werk |
| `41/89` | Ausbrand Saugzuggebläse Drehzahl Stufe 0 | Werk |
| `41/90` | Ausbrand Saugzuggebläse Drehzahl Stufe 1 | Werk |
| `41/91` | Ausbrand Saugzuggebläse Drehzahl Stufe 2 | Werk |
| `41/92` | Ausbrand Saugzuggebläse Drehzahl Stufe 3 | Werk |
| `41/93` | Ausbrand Laufzeit in Modulation bis Entaschung Stufe 0 | Werk |
| `41/94` | Ausbrand Laufzeit in Modulation bis Entaschung Stufe 1 | Werk |
| `41/95` | Ausbrand Laufzeit in Modulation bis Entaschung Stufe 2 | Werk |
| `41/96` | Ausbrand Laufzeit in Modulation bis Entaschung Stufe 3 | Werk |
| `41/97` | Ausbrand Zeit bis Entaschung Stufe 0 | Werk |
| `41/98` | Ausbrand Zeit bis Entaschung Stufe 1 | Werk |
| `41/99` | Ausbrand Zeit bis Entaschung Stufe 2 | Werk |
| `41/100` | Ausbrand Zeit bis Entaschung Stufe 3 | Werk |
| `41/101` | Entaschung Anzahl Hübe Stufe 0 | Werk |
| `41/102` | Entaschung Anzahl Hübe Stufe 1 | Werk |
| `41/103` | Entaschung Anzahl Hübe Stufe 2 | Werk |
| `41/104` | Entaschung Anzahl Hübe Stufe 3 | Werk |
| `41/105` | Ausbrand Brennkammertemperatur Austritt | Werk |
| `41/106` | Ausbrand Nachlaufzeit Saugzuggebläse | Werk |
| `41/107` | Modulation Zeit Berechnung positiv und negativ | Werk |
| `41/108` | Modulation Zeit Berechnung nur positiv | Werk |
| `41/109` | Brennwert Saugzuggebläse Drehzahl Spülen | Werk |
| `41/110` | Spülung Wärmetauscher | Service, Werk |
| `41/111` | Brennwert Spülung Abfluss Grenze Ventil geschlossen | Werk |
| `41/112` | Brennwert Spülung Abfluss Grenze unterhalb Grenzwert | Werk |
| `41/113` | Brennwert Spülung Abfluss Grenze unterhalb Normalwert | Werk |
| `41/114` | Brennwert Spülung Abfluss Grenze oberhalb Normalwert | Werk |
| `41/115` | Brennwert Spülung WT Grenze Ventil geschlossen | Werk |
| `41/116` | Brennwert Spülung WT Grenze unterhalb Grenzwert | Werk |
| `41/117` | Brennwert Spülung WT Grenze unterhalb Normalwert | Werk |
| `41/118` | Brennwert Spülung WT Grenze oberhalb Normalwert | Werk |
| `41/119` | Brennwert Spülung Abfluss Menge Selbsttest | Werk |
| `41/120` | Brennwert Spülung WT Menge Selbsttest | Werk |
| `41/121` | Brennwert Spülung Abfluss Menge Modulation | Werk |
| `41/122` | Brennwert Spülung WT Menge Ausbrand | Werk |
| `41/124` | Brennwert Zeit Stillstand Spülen im Vorspülen | Werk |
| `41/125` | Brennwert Spülung Abfluss Menge Vorspülen | Werk |
| `41/127` | Brennwert Abgastemperatur Spülung WT | Werk |
| `42/0` | Brennwert Spülung Abfluss Menge Sperrwassernachladung | Werk |
| `42/1` | Brennwert Brennstoffmenge in Modulation bis Spülung WT | Werk |
| `42/2` | Brennwert Brennstoffmenge in Modulation bis Spülung Abfluss | Werk |
| `42/3` | Brennwert Zeit Sperrwassernachladung Modulation | Werk |
| `42/4` | Laufzeit Brenner gesperrt bei Service | Werk |
| `42/5` | Vorspülen Druck Venturidüse min | Werk |
| `42/6` | Vorspülen Druck Venturidüse max. | Werk |
| `42/7` | Korrektur Spülung Abfluss | Service, Werk |
| `42/8` | Korrektur Spülung Wärmetauscher | Service, Werk |
| `42/9` | Wiederholung Entaschung im Vorspülen | Werk |
| `42/10` | Zündphase Anstieg 2 Brennkammertemperatur | Werk |
| `42/11` | Korrektur Menge Förderschnecke RLU | Werk |
| `42/12` | Sondenumschaltung Parkposition verfügbar | Werk |
| `42/13` | Selbsttest Druck Venturidüse min | Werk |
| `42/14` | Selbsttest Druck Venturidüse max. | Werk |
| `42/15` | Bitmuster für "Art des Brennstoffzuführsystem" (42-018) | Werk |
| `42/16` | Modulation Saugzuggebläse für Überwachung Unterdruck Venturidüse | Werk |
| `42/17` | Modulation Minimaler Unterdruck Venturidüse Min | Werk |
| `42/18` | Art des Brennstoffzuführsystems | Service, Werk |
| `42/19` | Externe Verbrennungsluft | Service, Werk |
| `42/20` | Rührwerk Zeit Verzögerung Ein- und Ausschalten | Werk |
| `42/21` | Sensor Pelletförderung | Service, Werk |
| `42/22` | Pelletsmenge Wochenbehälter 1 | Werk |
| `42/23` | Pelletsmenge Wochenbehälter 2 | Werk |
| `42/24` | Pelletsmenge Behälter automatische Brennstoffzuführung | Werk |
| `42/25` | Pelletszuführung Drehzahl Saugzuggebläse | Werk |
| `42/26` | Pelletszuführung Zeit bis Klappe geschlossen | Werk |
| `42/27` | Pelletszuführung Anzahl Wiederholungen Klappe bis Behälter voll | Werk |
| `42/28` | Pelletszuführung Anzahl Wiederholungen Klappe bis Error | Werk |
| `42/29` | Laufzeit der Saugturbine | Service, Werk |
| `42/30` | Pelletszuführung Auswahl Behälter automatische Brennstoffzuführung | Werk |
| `42/31` | Brennstoffmenge nach IN 581 | Service, Werk |
| `42/32` | Brennstoffmenge nach IN 581 | Service, Werk |
| `42/33` | Befüllgrad Endschalter leer automatische Brennstoffzuführung | Werk |
| `42/34` | Befüllgrad Wochenbehälter 1 leer | Werk |
| `42/35` | Befüllgrad Wochenbehälter 2 leer | Werk |
| `42/36` | Befüllgrad automatische Brennstoffzuführung leer | Werk |
| `42/37` | Befüllgrad Zuführung freigeben | Werk |
| `42/38` | Befüllgrad Zuführung anfordern mit Freigabezeit | Werk |
| `42/39` | Befüllgrad Zuführung anfordern mit Startzeit | Werk |
| `42/40` | Wochenbehälter Deckel Brennstoffbehälter maximale Zeit offen | Werk |
| `42/41` | Wochenbehälter Faktor Brennstoffmenge bis Error 1410 | Werk |
| `42/42` | Laufzeit Maulwurf | Service, Werk |
| `42/45` | Verzögerung Überwachung Pelletsförderung | Werk |
| `42/46` | Ausgang X12 | Service |
| `42/47` | Überwachung Pelletsförderung Anzahl Sample für Überwachung | Werk |
| `42/48` | Laufzeit Absperreinheit | Werk |
| `42/49` | Pelletszuführung Zeit Endschalter Behälter voll | Werk |
| `42/50` | Sondenumschaltung Faktor | Werk |
| `42/51` | Erhöhung Anzahl Befüllung bei Erkennung Sonde fördert nicht | Werk |
| `42/52` | Anzahl Sonde fördert nicht bis Sonde leer | Werk |
| `42/53` | Sondenumschaltung Maximale Saugzyklen auf einer Sonde | Werk |
| `42/54` | Anzahl leerer Sonden bis Infomeldung | Werk |
| `42/55` | Erhöhung Anzahl Befüllung bei Erkennung Sonde leer | Werk |
| `42/56` | Maximale Saugzyklen Sonde Solo / Rührwerk | Werk |
| `42/57` | Schwelle Befüllgrad Lagerraum für Error | Werk |
| `42/58` | Pelletszuführung Laufzeit Saugzyklus Grenze min | Werk |
| `42/59` | Pelletszuführung Laufzeit Saugzyklus Grenze max. | Werk |
| `42/60` | Pelletszuführung Laufzeit Spülen | Werk |
| `42/61` | Bewertungszeit Verhältnis Brennwert aktuell | Werk |
| `42/62` | Schwelle Brennwertnutzen zu gering | Werk |
| `42/63` | Filterzeit Venturidüse | Werk |
| `42/64` | RLU Vorspülen Druck Venturidüse min | Werk |
| `42/65` | RLU Vorspülen Druck Venturidüse max. | Werk |
| `42/66` | Faktor Venturidruck Rezirkulation Offen | Werk |
| `42/68` | Inbetriebnahme-Kennung | Werk |
| `42/69` | Laufzeit Überwachung Venturi mit gesenktem Druck Beginn Modulation | Werk |
| `42/70` | Modulation Minimaler Unterdruck Venturidüse Max | Werk |
| `42/71` | Saugzuggebläse Maximale Laufzeit Gebläse blockiert | Werk |
| `42/73` | Freigabezeit Abgasmessung 100% | Werk |
| `42/74` | Freigabezeit Abgasmessung 30% | Werk |
| `42/75` | LogWIN-BioWIN Kamintrennung | Service, Werk |
| `42/76` | Modulation Minimaler Unterdruck Venturidüse Max Beginn Modulation | Werk |
| `42/77` | Menge Förderschnecke Default händische Beschickung | Werk |
| `42/78` | Menge Förderschnecke Default automatische Beschickung | Werk |
| `42/79` | Primärzündung Laufzeit bis Takt bei min. Strom | Werk |
| `42/80` | Primärzündung Laufzeit bis Takt bei max. Strom | Werk |
| `42/81` | Primärzündung Strom für max. Laufzeit bis Takten | Werk |
| `42/82` | Primärzündung Strom für min. Laufzeit bis Takten | Werk |
| `42/83` | Brennstoffmenge Reinigung Alpha Stufe 0 | Werk |
| `42/84` | Brennstoffmenge Reinigung Alpha Stufe 1 | Werk |
| `42/85` | Brennstoffmenge Reinigung Alpha Stufe 2 | Werk |
| `42/86` | Brennstoffmenge Reinigung Alpha Stufe 3 | Werk |
| `42/87` | Anzahl Reinigung bis Hauptreinigung Alpha | Werk |
| `42/88` | Faktor Brennstoffmenge Reinigung bis Wartung Alpha | Werk |
| `42/89` | Aschesystem | Service, Werk |
| `42/90` | Verzögerung Bewertung Zündstrom | Werk |
| `42/91` | Offset Venturidruck | Werk |
| `42/92` | Offset Venturidruck min. | Werk |
| `42/93` | Offset Venturidruck max. | Werk |
| `42/94` | Zeit bis Offseterkennung | Werk |
| `42/95` | Soll-Venturidruck DuoWIN | Werk |
| `42/96` | Saugzuggebläse Drehzahl DuoWIN min | Werk |
| `42/97` | Saugzuggebläse Drehzahl DuoWIN max | Werk |
| `42/98` | Regler DuoWIN-Drehzahl P-Band | Werk |
| `42/99` | Regler DuoWIN-Drehzahl Nachstellzeit | Werk |
| `42/100` | Offset Venturi Multiplikator | Werk |
| `42/101` | Nachlaufzeit Ladepumpe ohne Pufferspeicher | Werk |
| `42/102` | Nachlaufzeit Ladepumpe mit Pufferspeicher | Werk |
| `42/103` | Pumpensteuerung max. Drehzahl WW | Werk |
| `43/5` | Abgastemperatur vor Wärmetauscher | Service |
| `43/7` | Unterdruck Venturidüse | Service |
| `43/31` | Grenztemperatur in Modulation unterschritten | Service |
| `43/32` | Grenzdruck in Modulation unterschritten | Service |
| `43/34` | Sonde 1 | Betreiber |
| `43/35` | Sonde 2 | Betreiber |
| `43/36` | Sonde 3 | Betreiber |
| `43/37` | Sonde 4 | Betreiber |
| `43/38` | Sonde 5 | Betreiber |
| `43/39` | Sonde 6 | Betreiber |
| `43/40` | Sonde 7 | Betreiber |
| `43/41` | Sonde 8 | Betreiber |
| `43/42` | Befüllgrad Vorratsbehälter | Info |
| `43/45` | Vorratsbehälter befüllt? | Betreiber |
| `43/77` | Warnlevel Lagerraum | Betreiber |
| `43/78` | Befüllgrad Lagerraum | Info |
| `43/79` | Sonden zurücksetzen | Betreiber |
| `43/82` | Brennwert Zähler Spülung Abfluss schließt nicht | Werk |
| `43/83` | Brennwert Zähler Spülung Abfluss nicht erfolgreich | Werk |
| `43/84` | Brennwert Zähler Spülung WT schließt nicht | Werk |
| `43/85` | Brennwert Zähler Spülung WT nicht erfolgreich | Werk |
| `43/89` | Verhältnis Brennwert Aktuell | Werk |
| `43/90` | Brennwertnutzen | Service, Werk |
| `43/91` | Betriebsstunden Brennwert | Werk |
| `43/95` | Brennstoffmenge bis Ascheaustragung | Service |
| `43/99` | Wärmemengenzähler | Service, Werk |
| `43/100` | Wärmemengenzähler | Service, Werk |
| `43/101` | Volumenstrom | Service, Werk |
| `43/102` | Aktuelle Kesselleistung | Werk |
| `43/103` | Wärmemengenzähler | Service, Werk |
| `43/104` | Heizwert Pellets (kWh/kg) | Werk |
| `43/105` | Kesselwirkungsgrad direkt | Werk |
| `43/106` | Volumenstromsensor | Werk |
| `43/107` | Bitmuster für Auswahl Wärmemengenzähler (43-103) | Werk |
| `43/108` | Volumenstromsensor gültig | Werk |
| `43/109` | Bitmuster für Auswahl Volumenstromsensor (43-106) | Werk |
| `43/110` | Erzeugte Wärmemenge Leistungsmessung | Werk |
| `44/69` | Staubabscheider | Service, Werk |
| `44/70` | Staubabscheider Auswahl | Werk |
| `44/71` | Staubabscheider Status | Service, Werk |
| `44/72` | Staubabscheider aktuelle Spannung | Service, Werk |
| `44/73` | Staubabscheider aktueller Strom | Service, Werk |
| `44/74` | Staubabscheider Maximale Ausgangsspannung eingestellt | Werk |
| `44/75` | Staubabscheider Störungsnummer | Werk |
| `44/76` | Staubabscheider Temperatur Elektronik | Werk |
| `44/77` | Staubabscheider Modus Hochspannung | Werk |
| `44/78` | Staubabscheider Softwareversion | Werk |
| `44/79` | Staubabscheider Maximale Ausgangsspannung | Werk |
| `44/80` | Staubabscheider Maximale Ausgangsleistung | Werk |
| `44/81` | Staubabscheider Messmodus | Werk |
| `44/82` | Staubabscheider Kurzschlusszähler | Werk |
| `44/83` | Staubabscheider Betriebsstunden | Werk |
| `44/84` | Staubabscheider Betriebsstunden Filter Störung | Werk |
| `44/86` | Staubabscheider Kesselleistung Filter Ein | Werk |
| `50/22` | Externe Anforderung | Service |
| `51/35` | Sollwert Spreizung | Werk |
| `54/25` | Regler Spreizung P-Band | Werk |
| `54/26` | Regler Spreizung Nachstellzeit | Werk |
| `54/34` | Nachlaufzeit Pumpe | Werk |
| `58/5` | Pumpensteuerung | Service, Werk |
| `58/12` | Pumpe Wärmeerzeuger | Service |
| `58/15` | – | Service |
| `58/42` | Hysterese Transferdifferenz ein | Werk |
| `59/7` | Anlagenkonfiguration | Service |
| `59/23` | Rücklaufhochhaltung | Service |
| `63/1` | Steuersignal invertiert | Werk |
| `63/2` | Mischer | Service |

### fctType 10 – Kessel (Automatik-/Zusatzkessel)

| OID | Name | Ebene |
|---|---|---|
| `0/7` | Kesseltemperatur | Service |
| `0/8` | Rücklauftemperatur Aktueller Wert | Service |
| `0/11` | Abgastemperatur | Info, Service |
| `0/15` | Puffertemperatur oben | Info |
| `0/16` | Puffertemperatur unten | Info |
| `0/17` | Puffertemperatur mitte | Info |
| `0/42` | O2 Signal | Info, Service |
| `0/45` | Brennkammertemperatur | Info, Service |
| `1/7` | Kesseltemperatur Soll | Info |
| `1/8` | Rücklauftemperatur Sollwert | Service |
| `2/1` | Betriebsphase | Info |
| `2/70` | Datum | Info, Betreiber |
| `2/72` | Uhrzeit | Info, Betreiber |
| `2/81` | Betriebsstunden | Info |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Service |
| `12/38` | Gerätetyp | Info |
| `12/40` | Kesseltemperatur für Neustart | Service |
| `12/42` | Startverzögerung Automatikkessel | Betreiber |
| `12/103` | Ausbrand | Service |
| `12/105` | Elektrische Zündung | Service |
| `20/8` | Funktion aktivieren | Service |
| `20/14` | min. Drehzahl | Service |
| `20/17` | Sollwert | Service |
| `20/22` | max. Drehzahl | Service |
| `20/65` | Abbruch Startverzögerung | Betreiber |
| `20/111` | Sperrzeit Zündung | Betreiber |
| `20/112` | Anzahl der Anheizvorgänge | Info |
| `20/118` | Kombikessel | Service |
| `20/119` | LED Helligkeit | Service |
| `23/87` | Puffer-Beladegrad | Info |
| `23/88` | Saugzuggebläse Soll-Drehzahl | Service |
| `23/89` | Saugzuggebläse Ist-Drehzahl | Service |
| `23/90` | Position Primär-LK | Service |
| `23/91` | Position Sekundär-LK | Service |
| `23/98` | O2 Heizstrom | Service |
| `29/30` | Summenstörmeldung Alarm | Service |
| `29/31` | Summenstörmeldung Fehler | Service |
| `29/32` | Summenstörmeldung Info | Service |
| `39/66` | Interner Fehler | Service |
| `39/112` | MAC-Adresse | Info |
| `42/75` | LogWIN-BioWIN Kamintrennung | Service |
| `43/100` | Wärmemengenzähler | Service |
| `43/101` | Volumenstrom | Service |
| `43/103` | Wärmemengenzähler | Service |
| `44/69` | Staubabscheider | Service |
| `46/120` | Fehler 396 | Service |
| `46/121` | Fehler 375 | Service |
| `46/122` | Brenner AUS | Service |
| `50/22` | Externe Anforderung | Service |
| `58/5` | Pumpensteuerung | Service |
| `58/12` | Pumpe Wärmeerzeuger | Service |
| `58/115` | Mischer | Service |
| `59/7` | Anlagenkonfiguration | Service |
| `63/2` | Mischer | Service |

### fctType 14 – Heizkreis (UML / UMLZ)

| OID | Name | Ebene |
|---|---|---|
| `0/0` | Aussentemperatur | Info |
| `0/1` | Raumtemperatur Aktueller Wert | Info |
| `0/2` | Vorlauftemperatur Aktueller Wert | Info |
| `0/4` | WW-Temperatur Aktueller Wert | Info |
| `0/7` | Kesseltemperatur | Info |
| `0/118` | WW-Zirkulationstemperatur Aktueller Wert | Info |
| `1/1` | Raumtemperatur Sollwert Heizen | Info, Betreiber |
| `1/2` | Vorlauftemperatur Sollwert | Info |
| `1/4` | WW-Temperatur Sollwert | Info |
| `1/7` | Kesseltemperatur Soll | Info |
| `1/20` | Heizkreispumpe | Info |
| `1/65` | WW-Zirkulationspumpe | Info |
| `1/66` | WW-Ladepumpe | Info |
| `1/118` | WW-Zirkulationstemperatur Sollwert | Info |
| `2/2` | Aktive Aktoren | Service |
| `2/9` | Betriebsart | Info |
| `2/10` | Dauer | Betreiber |
| `2/16` | Freigabe starten | Betreiber |
| `2/70` | Datum | Betreiber |
| `2/72` | Uhrzeit | Betreiber |
| `3/0` | Raumtemperatur | Service |
| `3/1` | Fusspunkt | Service |
| `3/2` | TA Absenkbetrieb | Service |
| `3/4` | Temperatur | Betreiber |
| `3/6` | Startoptimierung Vorhaltezeit | Service |
| `3/7` | Kompensation | Service |
| `3/12` | Klimapunkt | Service |
| `3/13` | Vorlauf | Service |
| `3/21` | TA Heizbetrieb | Service |
| `3/23` | Aussentemperatur | Service |
| `3/29` | Rücklauf | Service |
| `3/30` | Nachstellzeit | Service |
| `3/50` | Betriebswahl | Info, Betreiber |
| `3/51` | Heizbetrieb | Betreiber |
| `3/53` | Absenkbetrieb | Betreiber |
| `3/58` | Behaglichkeit Korrekturwert | Betreiber |
| `3/61` | Programm 1 | Betreiber |
| `3/62` | Programm 2 | Betreiber |
| `3/63` | Programm 3 | Betreiber |
| `3/78` | Urlaubsprogramm bis Datum | Betreiber |
| `4/12` | Systemzeit | Service |
| `4/13` | Aussentemp. | Service |
| `4/14` | Betriebswahl | Service |
| `4/60` | Programm | Service |
| `4/63` | T-Beharrung | Service |
| `4/64` | Dauer Beharrung | Service |
| `4/65` | T-Aufheizphase | Service |
| `4/66` | T-Abkühlphase | Service |
| `4/67` | Dauer T-Änderung | Service |
| `4/77` | Anzahl Heizkreise | Service |
| `4/82` | Zeitprogramm | Betreiber |
| `4/92` | Softwareversion | Service |
| `4/93` | Hardwareversion | Service |
| `5/0` | Hysterese Ein | Service |
| `5/1` | WW-Überhöhung | Service |
| `5/3` | Nachlaufzeit 1 | Service |
| `5/6` | WW-Zirkulationspumpe | Service |
| `5/8` | WW-Ladung max. Ladevorrang | Service |
| `5/51` | Temperatur | Betreiber |
| `5/58` | WW-Speicher | Service |
| `5/61` | WW-Programm | Betreiber |
| `5/64` | WW-Zirkulationsprogramm | Betreiber |
| `5/65` | WW-Zirkulationsprogramm | Betreiber |
| `5/70` | Einschaltzeit | Service |
| `5/71` | Ausschaltzeit | Service |
| `5/76` | WW-Kreis | Service |
| `5/80` | Nachlaufzeit 2 | Service |
| `7/1` | Kesseltemp.-Überhöhung Heizkreis | Service |
| `7/2` | Vorlauf min. | Service |
| `7/3` | Nachlaufz. Pumpe | Service |
| `7/8` | Vorlauf max. | Service |
| `7/13` | Mischerlaufzeit | Service |
| `7/45` | Vorlauftemperatur | Service |
| `7/76` | Heizkreis | Service |
| `51/102` | Normaltemp. Kühlen | Betreiber |
| `51/103` | Absenktemp. Kühlen | Betreiber |
| `51/105` | Ende | Betreiber |
| `51/106` | Funktion aktivieren | Betreiber |
| `51/107` | Zeitprogramm Heizen | Betreiber |
| `51/108` | Zeitprogramm Kühlen | Betreiber |
| `51/110` | Normaltemp. Heizen | Betreiber |
| `51/111` | Absenktemp. Heizen | Betreiber |
| `51/112` | Betriebswahl | Betreiber |
| `51/114` | Fernzugriff aktivieren | Service, Werk |
| `51/115` | Konfiguration | Info |
| `51/116` | AEW Evo Message ID of the room temperature sensor | Werk |
| `51/117` | AEW Evo Message ID of the humidity sensor | Werk |
| `51/118` | AEW Evo Actual room humidity | Werk |
| `51/119` | AEW Evo Cool request set by external controller | Werk |
| `51/120` | AEW Evo Heat request set by external controller | Werk |
| `51/121` | AEW Evo Flow set temperature from external controller | Werk |
| `51/122` | AEW Evo Excess energy target temp | Werk |
| `52/110` | TerraWIN Actual heat circuit reflux temperature | Werk |
| `52/111` | TerraWIN Actual heat circuit mixer position | Werk |
| `52/112` | TerraWIN Actual value of the heat circuit pump | Werk |
| `52/113` | TerraWIN Heat Circuit Use Excess Energy | Werk |
| `52/114` | TerraWIN Excess energy target cool temp | Werk |
| `58/28` | Heizkurve Niveau | Service |
| `58/29` | Heizkurve Neigung | Service |
| `58/48` | Heizkreispumpe | Info |
| `58/49` | Mischer | Info |
| `58/70` | Solar | Service |
| `58/83` | Motor Mischventil | Service |
| `58/84` | Mischerlaufzeit | Service |
| `58/87` | T-Start | Service |
| `58/89` | WW-Temperatur Maximalwert | Service |

### fctType 15 – Umschaltung

| OID | Name | Ebene |
|---|---|---|
| `0/7` | Kesseltemperatur | Info |
| `0/15` | Puffertemperatur oben | Info |
| `0/16` | Puffertemperatur unten | Info |
| `0/17` | Puffertemperatur mitte | Info |
| `2/2` | Aktive Aktoren | Info |
| `2/9` | Betriebsart | Info |
| `3/50` | Betriebswahl | Info |
| `4/92` | Softwareversion | Service |
| `4/93` | Hardwareversion | Service |
| `7/12` | Drehzahlregelung | Service |
| `9/32` | Minimalwert | Service |
| `10/31` | Maximalwert | Service |
| `20/0` | Automatikkessel | Service |
| `20/1` | Festbrennstoff | Service |
| `20/2` | Pufferspeicher | Service |
| `20/3` | Modulfunktionen | Service |
| `20/5` | Fühleranschluss Y3 | Service |
| `20/6` | Antrieb | Service |
| `20/7` | Umschaltsperrzeit | Service |
| `20/8` | Funktion aktivieren | Service |
| `20/9` | Zeitverzögerung | Service |
| `20/10` | Minimalwert | Service |
| `20/11` | Offset WE-Sollwert | Service |
| `20/14` | min. Drehzahl | Service |
| `20/15` | Betriebswahl | Betreiber |
| `20/16` | Maximalwert | Service |
| `20/17` | Sollwert | Service |
| `20/22` | max. Drehzahl | Service |
| `23/87` | Puffer-Beladegrad | Info |

### fctType 16 – Puffer (B-PLMi)

| OID | Name | Ebene |
|---|---|---|
| `0/7` | Kesseltemperatur | Info |
| `0/8` | Rücklauftemperatur Aktueller Wert | Info |
| `1/7` | Kesseltemperatur Soll | Info |
| `1/8` | Rücklauftemperatur Sollwert | Info |
| `1/15` | Puffertemperatur Sollwert | Info |
| `1/22` | WE-Pumpe | Info |
| `1/100` | Brenner | Info |
| `1/102` | Rücklaufhochhaltung | Info |
| `2/2` | Aktive Aktoren | Info |
| `2/9` | Betriebsart | Info |
| `3/50` | Betriebswahl | Info |
| `4/82` | Zeitprogramm | Betreiber |
| `4/92` | Softwareversion | Service |
| `4/93` | Hardwareversion | Service |
| `5/1` | WW-Überhöhung | Service |
| `6/4` | Überhöhung | Service |
| `7/12` | Drehzahlregelung | Service |
| `9/0` | Nachlaufzeit | Service |
| `9/32` | Minimalwert | Service |
| `9/35` | Hysterese | Service |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Service |
| `10/31` | Maximalwert | Service |
| `20/4` | Modulfunktionen | Service |
| `20/14` | min. Drehzahl | Service |
| `20/15` | Betriebswahl | Betreiber |
| `20/22` | max. Drehzahl | Service |
| `20/28` | Minimale Laufzeit | Service |
| `20/29` | Sollwert für Laufzeitoptimierung | Service |
| `20/124` | Rücklaufhochhaltung | Service |
| `21/64` | Puffertemperatur TPT | Info |
| `21/65` | Puffertemperatur TPE | Info |
| `21/66` | Puffertemperatur TPA | Info |
| `22/75` | Puffertransferpumpe | Info |

### fctType 20 – ZSP Pumpen-/Relaismodul

| OID | Name | Ebene |
|---|---|---|
| `0/7` | Kesseltemperatur | Info |
| `0/22` | Pumpensteuerung Drehzahl | Info |
| `0/95` | Analog-Sollwert | Info, Betreiber |
| `1/7` | Kesseltemperatur Soll | Info |
| `4/92` | Softwareversion | Service |
| `4/93` | Hardwareversion | Service |
| `7/12` | Drehzahlregelung | Betreiber |
| `9/35` | Hysterese | Betreiber |
| `9/37` | Sollwert-Offset | Betreiber |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Betreiber |
| `11/8` | Zuordnung zu WEZ | Betreiber |
| `11/76` | Kaskadenfunktion | Service |
| `20/14` | min. Drehzahl | Betreiber |
| `20/18` | Pumpensteuerung | Betreiber |
| `20/22` | max. Drehzahl | Betreiber |
| `20/23` | Digital-Sollwert WWK | Betreiber |
| `22/31` | Aktorentest Relais | Info |
| `22/32` | Aktorentest Drehzahl | Info |
| `29/0` | Summenstörmeldung | Service |
| `29/1` | Pumpensteuerung | Service |
| `29/2` | Ext. Wärmeanforderung | Service |
| `29/3` | Relaisfunktion | Betreiber |
| `29/21` | Eingang E1 | Betreiber |
| `29/30` | Summenstörmeldung Alarm | Betreiber |
| `29/31` | Summenstörmeldung Fehler | Betreiber |
| `29/32` | Summenstörmeldung Info | Betreiber |
| `63/1` | Steuersignal invertiert | Betreiber |

### fctType 21 – Puffer

| OID | Name | Ebene |
|---|---|---|
| `0/15` | Puffertemperatur oben | Info |
| `0/16` | Puffertemperatur unten | Info |
| `0/17` | Puffertemperatur mitte | Info |
| `1/15` | Puffertemperatur Sollwert | Info |
| `2/70` | Datum | Info |
| `2/72` | Uhrzeit | Info |
| `4/82` | Zeitprogramm | Betreiber |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `9/35` | Hysterese | Service |
| `12/42` | Startverzögerung Automatikkessel | Betreiber |
| `20/3` | Modulfunktionen | Service |
| `20/7` | Umschaltsperrzeit | Service |
| `20/10` | Minimalwert | Service |
| `20/11` | Offset WE-Sollwert | Service |
| `20/15` | Betriebswahl | Betreiber |
| `20/16` | Maximalwert | Service |
| `21/64` | Puffertemperatur TPT | Info |
| `23/87` | Puffer-Beladegrad | Info |
| `39/112` | MAC-Adresse | Info |
| `51/81` | Hysterese Kühlen Ein | Service |
| `58/118` | Zustand Wärmepuffer | Service |
| `58/121` | Pufferfühler oben | Service |
| `58/122` | Pufferfühler mitte | Service |
| `58/123` | Pufferfühler unten | Service |
| `59/16` | Umschaltung Wärmeerzeuger | Service |
| `59/26` | Restlaufzeit | Betreiber |
| `59/28` | Abbrechen | Betreiber |
| `59/32` | Puffertransferpumpe | Service |
| `59/36` | Kälte-Puffertemperatur oben | Info |
| `59/37` | Kälte-Puffertemperatur unten | Info |
| `59/75` | Kühlventil vor Pufferspeicher | Service |
| `59/76` | Kühlventil nach Pufferspeicher | Service |
| `60/11` | Zustand Rücklauf Umschalter | Service |
| `60/13` | Dauer Rücklauf Umschalter | Service |
| `63/4` | Umschaltventil | Service |
| `63/5` | Kühlventil vor Pufferspeicher invertiert | Service |
| `63/6` | Kühlventil nach Pufferspeicher invertiert | Service |
| `63/9` | Rücklauf Umschalter invertiert | Service |

### fctType 24 – Pumpe Wärmeerzeuger / Schichtladung

| OID | Name | Ebene |
|---|---|---|
| `0/7` | Kesseltemperatur | Info |
| `0/8` | Rücklauftemperatur Aktueller Wert | Service |
| `1/7` | Kesseltemperatur Soll | Info |
| `1/8` | Rücklauftemperatur Sollwert | Service |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `9/32` | Minimalwert | Service |
| `20/8` | Funktion aktivieren | Service |
| `20/14` | min. Drehzahl | Service |
| `20/17` | Sollwert | Service |
| `20/22` | max. Drehzahl | Service |
| `46/1` | Maximalwert | Service |
| `46/90` | Rücklauftemperatur | Service |
| `58/12` | Pumpe Wärmeerzeuger | Service |
| `58/115` | Mischer | Service |
| `59/17` | Betriebsphase | Info |
| `59/21` | Ausbrand Dauer | Service |
| `59/23` | Rücklaufhochhaltung | Service |
| `59/58` | Maximalwert | Service |
| `60/20` | Minimale Laufzeit auto. Zusatzkessel | Service |
| `63/2` | Mischer | Service |

### fctType 25 – Kessel (PuroWIN)

| OID | Name | Ebene |
|---|---|---|
| `0/7` | Kesseltemperatur | Service |
| `0/9` | Kesselleistung | Info |
| `0/11` | Abgastemperatur | Info |
| `0/42` | O2 Signal | Service |
| `0/45` | Brennkammertemperatur | Info, Service |
| `2/1` | Betriebsphase | Info, Service |
| `2/80` | Anzahl der Brennerstarts | Info |
| `2/81` | Betriebsstunden | Info |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `9/20` | Handbetrieb Solltemperatur | Werk |
| `9/21` | Hysterese Brenner EIN | Service, Werk |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Service, Werk |
| `9/75` | Betriebswahl | Betreiber |
| `9/90` | Kaminkehrer | Betreiber |
| `10/110` | Kaminkehrer Leistung | Betreiber |
| `11/27` | WEZ-Nummer | Service |
| `12/38` | Gerätetyp | Info |
| `12/39` | Maximalwert der Solltemperatur | Service, Werk |
| `12/106` | Minimale Abgastemperatur | Service, Werk |
| `14/10` | Zuführung mit Freigabezeit Ende | Betreiber, Werk |
| `14/11` | Zuführung mit Freigabezeit Beginn | Betreiber, Werk |
| `14/19` | Betriebsart Zuführung | Betreiber, Werk |
| `14/20` | Zuführung mit Startzeit | Betreiber, Werk |
| `14/75` | Korrektur Reinigungsintervall | Betreiber |
| `20/96` | Handbetrieb Soll-Leistung | Service |
| `20/97` | Hysterese TK-Soll Ausschalten (nach oben) | Werk |
| `20/98` | Soll-Leistung min. | Werk |
| `20/99` | Soll-Leistung max. | Werk |
| `20/106` | Analog-Sollwert | Werk |
| `23/88` | Saugzuggebläse Soll-Drehzahl | Service |
| `23/89` | Saugzuggebläse Ist-Drehzahl | Service |
| `23/90` | Position Primär-LK | Service |
| `23/91` | Position Sekundär-LK | Service |
| `23/94` | Endschalter Primärluftklappe | Service |
| `23/95` | Endschalter Sekundärluftklappe | Service |
| `23/98` | O2 Heizstrom | Service |
| `37/0` | Soll-Temperatur Kaminkehrer | Werk |
| `37/4` | Handbetrieb max. Soll-Temperatur | Werk |
| `37/5` | Soll-Temperatur Frostbetrieb | Werk |
| `37/7` | Maximale Laufzeit Flammenstabilisierung | Werk |
| `37/8` | Flammenabriss im Modulationsbetrieb | Service |
| `37/9` | Sollwertsprung | Werk |
| `37/10` | min. Wärmeanforderung | Werk |
| `37/11` | Soll-Temperatur min | Werk |
| `37/13` | Thermocontroltemperatur Flammenabriss | Werk |
| `37/14` | Zeit Erkennung Flammenabriss in Flammenstabilisierung | Werk |
| `37/15` | Zeit Erkennung Wiederzünden in Flammenstabilisierung | Werk |
| `37/16` | Rampe Anstieg Dosiserung in %/1sec nach Flammenabriss in Flammenstabilisierung | Werk |
| `37/17` | Betriebsstunden bis Reinigungsausbrand | Service, Werk |
| `37/18` | Soll-Temperatur Min für Start Brenner | Werk |
| `37/19` | Minimale Kesselrücklauftemperatur für PW_Status | Werk |
| `37/20` | Kesselminimaltemperatur wird nicht erreicht | Werk |
| `37/21` | PLK Öffnen bei Flammeabriss | Werk |
| `37/22` | Max-Temperatur | Werk |
| `37/23` | Max-Temperatur MIN | Werk |
| `37/24` | Max-Temperatur MAX | Werk |
| `37/25` | Max-Temperatur Differenz | Werk |
| `37/26` | Regler Kesseltemperatur P-Band | Werk |
| `37/27` | Regler Kesseltemperatur Nachstellzeit | Werk |
| `37/28` | Entaschung nicht erfolgreich | Service |
| `37/29` | Minimale Kesselleistung | Service, Werk |
| `37/30` | Minimale Zeit ohne Flammenabriss bis Modulation | Werk |
| `37/31` | Laufzeit Brenner gesperrt | Werk |
| `37/32` | Überhöhung Solltemperatur min. während Anfahrtsentlastung | Werk |
| `37/33` | Reduktion Solltemperatur min. in K/min nach Anfahrtsentlastung | Werk |
| `37/34` | EnergyHold Sollwert MES/REG | Werk |
| `37/35` | EnergyHold Sollwert bei Kaminkehrer | Werk |
| `37/36` | EnergyHold Hysterese bei Kaminkehrer | Werk |
| `37/37` | EnergyHold Hysterese für Sollwert EnergyHold MES/REG | Werk |
| `37/38` | Laufzeit ohne EnergyHold MES nach Start Brenner | Werk |
| `37/39` | Minmale Brennerlaufzeit für PW_Status | Werk |
| `37/40` | Offset TK-EnergyHold | Werk |
| `37/41` | EnergyHold Hysterese | Werk |
| `37/42` | Offset TK-EnergyHold bei Mindestlaufzeit Brenner | Werk |
| `37/44` | Pufferladung | Service |
| `37/45` | EnergyHold Offset für TK_Soll | Werk |
| `37/46` | Sollwert für Error 3980 | Werk |
| `37/48` | Thermocontroltemperatur Primärzündung o.k. | Werk |
| `37/49` | Thermocontroltemperatur Sekundärzündung o.k. | Werk |
| `37/50` | Thermocontrol min. für Dosierung Flammenstabilisierung | Werk |
| `37/51` | Thermocontrol max. für Dosierung Flammenstabilisierung | Werk |
| `37/52` | Grenztemperatur Modulationsbetrieb und Primärausbrand | Werk |
| `37/53` | Maximale Laufzeit Kaminkehrer | Werk |
| `37/54` | Minimale Thermocontroltemperatur Sekundärausbrand | Werk |
| `37/55` | Minimale Thermocontroltemperatur Reinigungsausbrand | Werk |
| `37/56` | Sollwert O2 Sekundärzündung | Werk |
| `37/57` | Soll-Temperatur Abgashochhaltung min | Werk |
| `37/58` | Soll-Temperatur Abgashochhaltung max | Werk |
| `37/59` | Regler Abgashochhaltung P-Band | Werk |
| `37/60` | Regler Abgashochhaltung Nachstellzeit | Werk |
| `37/61` | Verzögerung Einschalten Strommessung O2 Sonde | Werk |
| `37/62` | O2 Sonde Normalstrom Unteres Limit | Werk |
| `37/63` | O2 Sonde Normalstrom Oberes Limit | Werk |
| `37/64` | Sollwert O2 Vorspülen | Werk |
| `37/66` | O2 Sollwert Stabilisierung | Werk |
| `37/67` | O2 Sollwert min. Leistung | Service, Werk |
| `37/68` | O2 Sollwert max. Leistung | Service, Werk |
| `37/69` | Sollwert O2 Primärausbrand | Werk |
| `37/70` | Sollwert O2 Sekundärausbrand | Werk |
| `37/71` | Sollwert O2 für Ende Sekundärausbrand | Werk |
| `37/72` | O2 Min für Überwachung Modulationsbetrieb | Werk |
| `37/73` | O2 Max für Überwachung Modulationsbetrieb | Werk |
| `37/74` | Sollwert O2 min Reinigungsausbrand Ende | Werk |
| `37/75` | O2 PID: Kp | Werk |
| `37/77` | O2 Divisor SLK | Werk |
| `37/78` | O2 Divisor PLK | Werk |
| `37/79` | Rampe Sollwert O2 | Werk |
| `37/80` | Faktor für Zeit Rampe O2 | Werk |
| `37/81` | Primärluftmengensensor Faktor "d" in mm | Werk |
| `37/82` | Primärluftmengensensor Faktor "F" | Werk |
| `37/83` | Grenzwert Primärluftmenge min. Diagnose | Werk |
| `37/84` | Grenzwert Primärluftmenge max. Diagnose | Werk |
| `37/85` | Zeit Grenze Primärluftmenge | Werk |
| `37/86` | Primärluftklappe PLK Primärzündung | Werk |
| `37/87` | Primärluftmenge min. Primärzündung | Werk |
| `37/88` | Primärluftmenge max. Primärzündung | Werk |
| `37/89` | Zeit Primärluftmenge und Strom Sekundärzündelement Primärzündung | Werk |
| `37/90` | Primärluftklappe PLK Sekundärzündung | Werk |
| `37/91` | Primärluftmenge min. Sekundärzündung | Werk |
| `37/92` | Primärluftmenge max. Sekundärzündung | Werk |
| `37/93` | Zeit Primärluftmenge Sekundärzündung | Werk |
| `37/94` | PLK Stellung min. Flammenstabilisierung | Werk |
| `37/95` | PLK Stellung max. Flammenstabilisierung | Werk |
| `37/98` | Min. Primär-LK min. Leistung | Werk |
| `37/99` | Min. Primär-LK max. Leistung | Werk |
| `37/100` | Max. Primär-LK min. Leistung | Werk |
| `37/101` | Max. Primär-LK max. Leistung | Werk |
| `37/102` | Endposition kleine Entaschung | Werk |
| `37/103` | Betriebsstunden bis kleine Entaschung in Primaerzuendung | Werk |
| `37/104` | Primaerzuendung Stillstandszeit | Werk |
| `37/105` | Filterzeit Primaerluftmenge | Werk |
| `37/106` | PLK Stellung min. Primärausbrand | Werk |
| `37/107` | Primärluftmenge max. im Vorspülen | Werk |
| `37/108` | Ascheschieber Zeit Endschalter verlassen | Werk |
| `37/109` | Glutbettschieber Zeit Endschalter verlassen | Werk |
| `37/110` | Reduzierte Leistung im Reinigungsausbrand | Werk |
| `37/111` | Vorratsbehälterschnecke Mindeststrom relativ | Werk |
| `37/112` | Vorratsbehälterschnecke Spitzenststrom relativ | Werk |
| `37/113` | Thermocontroltemperatur reduzierte Leistung Reinigungsausbrand | Werk |
| `37/114` | Vorratsbehälterschnecke  Maximale Frequenz | Werk |
| `37/115` | Vorratsbehälterschnecke Minimale Frequenz | Werk |
| `37/117` | Laufzeit Vorratsbehälterschnecke Rückwärts bei Blockade oder Unterbrechung | Werk |
| `37/118` | Anzahl Versuche Blockade oder Unterbrechung Vorratsbehälterschnecke | Werk |
| `37/120` | Ascheaustragung Normalstrom Unteres Limit | Werk |
| `37/121` | Ascheaustragung Normalstrom Oberes Limit | Werk |
| `37/122` | Nachheizflächenreinigung Normalstrom Unteres Limit | Werk |
| `37/123` | Nachheizflächenreinigung Normalstrom Oberes Limit | Werk |
| `37/124` | Sekundärzündung Normalstrom Unteres Limit | Werk |
| `37/125` | Sekundärzündung Normalstrom Oberes Limit | Werk |
| `37/126` | Primärzündung Laufzeit bis Takt | Werk |
| `37/127` | Primärzündung Taktzeit Aus | Werk |
| `38/0` | Primärzündung Taktzeit Ein | Werk |
| `38/1` | Nachlaufzeit Sekundärzündung Flammenstabilisierung | Werk |
| `38/2` | Saugzuggebläse Drehzahl Vorspülen | Werk |
| `38/3` | Saugzuggebläse Drehzahl Primärzündung | Werk |
| `38/4` | Saugzuggebläse Drehzahl Sekundärzündung | Werk |
| `38/5` | Saugzuggebläse Drehzahl 1 Flammenstabilisierung | Werk |
| `38/6` | Minimale Gebläsedrehzahl | Service, Werk |
| `38/7` | Maximale Gebläsedrehzahl | Service, Werk |
| `38/8` | Gebläsedrehzahl min. Primärausbrand | Werk |
| `38/9` | Gebläsedrehzahl Sekundärausbrand | Werk |
| `38/10` | Soll_Leistung Kaminkehrer Default | Werk |
| `38/11` | Saugzuggebläse Drehzahl 2 Flammenstabilisierung | Werk |
| `38/12` | Sekundärluftklappe SLK Standby | Werk |
| `38/13` | Sekundärluftklappe SLK Vorspülen | Werk |
| `38/14` | Sekundärluftklappe SLK Primärzündung | Werk |
| `38/15` | Sekundärluftklappe SLK Sekundärzündung | Werk |
| `38/16` | SLK Stellung min. Flammenstabilisierung | Werk |
| `38/17` | SLK Stellung max. Flammenstabilisierung | Werk |
| `38/18` | SLK Stellung Freigabe PLK Flammenstabilisierung | Werk |
| `38/19` | SLK Stellung min. Modulationsbetrieb | Werk |
| `38/20` | SLK Stellung max. Modulationsbetrieb | Werk |
| `38/21` | SLK Stellung Freigabe PLK Modulationsbetrieb | Werk |
| `38/22` | SLK Stellung min. Primärausbrand | Werk |
| `38/23` | SLK Stellung max. Primärausbrand | Werk |
| `38/24` | SLK Stellung min. Sekundärausbrand | Werk |
| `38/25` | SLK Stellung max. Sekundärausbrand | Werk |
| `38/28` | Maximale Änderungsgeschwindigkeit/sec Saugzuggebläse in Moduation | Werk |
| `38/29` | Glutbettschieber Laufzeit Endlage - Endlage | Werk |
| `38/30` | Glutbettschieber Nachlaufzeit Endlage geschlossen | Werk |
| `38/31` | Ascheschieber Laufzeit Endlage - Endlage | Werk |
| `38/32` | Ascheschieber Nachlaufzeit Endlage geschlossen | Werk |
| `38/33` | Stokerschnecke Mindeststrom relativ | Werk |
| `38/34` | Stokerschnecke Spitzenststrom relativ | Werk |
| `38/36` | Stokerschnecke  Maximale Frequenz | Werk |
| `38/37` | Stokerschnecke Minimale Frequenz | Werk |
| `38/39` | Laufzeit Stokerschnecke Rückwärts bei Blockade oder Unterbrechung | Werk |
| `38/40` | Anzahl Versuche Blockade oder Unterbrechung Stokerschnecke | Werk |
| `38/41` | Laufzeit Vorwärts bis Blockade oder Unterbrechung behoben Stokerschnecke, RAS-Direktschnecke, Vorratsbehälterschnecke und RAS-Steigschnecke | Werk |
| `38/42` | Laufzeit Stokerschnecke bei Zuführung | Werk |
| `38/43` | Mindestlaufzeit Flammenstabilisierung | Werk |
| `38/44` | RAS-Saugschnecke Mindeststrom relativ | Werk |
| `38/45` | RAS-Saugschnecke Spitzenststrom relativ | Werk |
| `38/46` | RAS-Saugschnecke Frequenz Max | Werk |
| `38/47` | RAS-Saugschnecke Frequenz Min | Werk |
| `38/48` | Pause Ascheaustragung nach Entaschung | Werk |
| `38/49` | Zeit Primärluftmenge im Vorspülen | Werk |
| `38/51` | Zeit O2 Istwert nicht im Bereich | Werk |
| `38/52` | Menge Förderschnecke Primärzündung | Werk |
| `38/53` | Laufzeit Zyklus | Werk |
| `38/54` | Unterbrechung in Modulation | Werk |
| `38/55` | Verzögerung Siebreinigung | Werk |
| `38/56` | Laufzeit Siebreinigung | Werk |
| `38/57` | Verzögerung RAS-Saugschnecke | Werk |
| `38/59` | RAS-Saugschnecke Laufzeit Rückwärts | Werk |
| `38/60` | RAS-Saugschnecke Laufzeit bis Störung behoben | Werk |
| `38/61` | RAS-Saugschnecke Anzahl Versuche bei Störung | Werk |
| `38/62` | Zeit leer/voll gleichzeitig | Werk |
| `38/63` | Minimale Laufzeit Vorspülen | Werk |
| `38/64` | Maximale Laufzeit Vorspülen | Werk |
| `38/65` | Laufzeit 1 Brennstoffdosierung Primärzündung Direktschnecke | Werk |
| `38/66` | Laufzeit 2 Brennstoffdosierung Primärzündung Direktschnecke | Werk |
| `38/67` | Ansteuerung Dosierung Primärzündung Direktschnecke | Werk |
| `38/68` | Maximale Laufzeit Primärzündung | Werk |
| `38/69` | Laufzeit 1 Brennstoffdosierung Primärzündung nach Primär- oder Reinigungsausbrand Direktschnecke | Werk |
| `38/70` | Wiederholung Primärzündung | Werk |
| `38/71` | Mindestlaufzeit Primärzündung | Werk |
| `38/72` | Laufzeit Sekundärzündung gesamt | Werk |
| `38/73` | Wiederholung Sekundärzündung | Werk |
| `38/74` | Ansteuerung Dosierung min. Flammenstabilisierung Direktschnecke | Werk |
| `38/75` | Ansteuerung Dosierung max. Flammenstabilisierung Direktschnecke | Werk |
| `38/76` | Unterbrechung Dosierung Flammenstabilisierung wenn TCC um diesen Wert fällt | Werk |
| `38/77` | Fortsetzung Dosierung Flammenstabilisierung wenn TCC um diesen Wert steigt | Werk |
| `38/78` | Maximale Unterbrechung Dosierung Flammenstabilisierung | Werk |
| `38/79` | Maximale Laufzeit Zuführung | Werk |
| `38/80` | Ansteuerung Dosierung Modulationsbetrieb Direktschnecke | Werk |
| `38/81` | Maximale Laufzeit im Modulationsbetrieb | Werk |
| `38/82` | Minimale Laufzeit Sekundärzündung | Werk |
| `38/83` | Wiederholungen nach Flammenabriss in Flammenstabilisierung | Werk |
| `38/84` | Anzahl Stiring bis Entaschung (Modulation) | Service, Werk |
| `38/85` | Glutbettschieber Nachlaufzeit Endlage offen | Werk |
| `38/86` | Maximale Laufzeit Primärausbrand Brenner voll | Werk |
| `38/87` | Ascheschieber Nachlaufzeit Endlage offen | Werk |
| `38/88` | Minimale Laufzeit Sekundärausbrand | Werk |
| `38/89` | Saugturbine ohne / mit Frequenzumrichter | Service, Werk |
| `38/90` | Gebläsedrehzahl Sekundärausbrand bei O2 zu gering | Werk |
| `38/91` | Zeit bis Stiring Reinigungsausbrand | Werk |
| `38/92` | Verzögerung Überfüllung RAS | Werk |
| `38/93` | Maximale Zeit Level-Control erreicht im Modulationsbetrieb | Werk |
| `38/94` | Anzahl Stiring bis Entaschung (Ausbrand) | Service |
| `38/95` | Maximale Zeit Level-Control nicht erreicht im Modulationsbetrieb | Werk |
| `38/96` | Endposition Stirring | Werk |
| `38/97` | Einschaltverzögerung Schnecken | Service, Werk |
| `38/98` | Endposition Verteilung | Werk |
| `38/99` | Laufzeit bis HFR im Modulationsbetrieb | Werk |
| `38/100` | Laufzeit HFR im Modulationsbetrieb und Primärausbrand | Werk |
| `38/101` | Laufzeit HFR Standschutz | Werk |
| `38/102` | Betriebsstunden bis Ascheaustragung | Werk |
| `38/103` | Laufzeit Ascheaustragung | Werk |
| `38/104` | Laufzeit Ascheaustragung Standschutz | Werk |
| `38/105` | Pause vor Laufzeit 2 Primärzündung | Werk |
| `38/106` | Temperaturanstieg Thermocontrol in Primärzündung | Werk |
| `38/107` | RAS-Direktschnecke Mindeststrom relativ | Werk |
| `38/108` | RAS-Direktschnecke Spitzenststrom relativ | Werk |
| `38/110` | RAS-Direktschnecke  Maximale Frequenz | Werk |
| `38/111` | RAS-Direktschnecke Minimale Frequenz | Werk |
| `38/113` | Laufzeit RAS-Direktschnecke Rückwärts bei Blockade oder Unterbrechung | Werk |
| `38/114` | Anzahl Versuche Blockade oder Unterbrechung RAS-Direktschnecke | Werk |
| `38/115` | Minimale Thermocontroltemperatur „Warten auf Lambda“ | Werk |
| `38/116` | Sollwert O2„Warten auf Lambda“ | Werk |
| `38/117` | Brennstoffdosierung Zeit Level-Control Ein | Werk |
| `38/118` | Saugturbine Mindeststrom | Werk |
| `38/119` | Saugturbine Spitzenststrom | Werk |
| `38/120` | Primärluftklappe Laufzeit Endlage - Endlage | Werk |
| `38/121` | Sekundärluftklappe Laufzeit Endlage - Endlage | Werk |
| `38/122` | Laufzeit in Modulation bis Pause Brennstoffdosierung | Werk |
| `38/123` | Pause Brennstoffdosierung | Werk |
| `38/124` | Laufzeit bis Pause Saugzuführung | Werk |
| `38/125` | Anzahl Saugzyklen | Service |
| `38/126` | Gewählter Brennstoff | Betreiber |
| `38/127` | Aktueller Brennstoff | Betreiber |
| `39/3` | Primärluftmenge | Service |
| `39/23` | Saugzuggebläse Soll-Drehzahl | Service |
| `39/57` | Aschetonne entleeren | Betreiber |
| `39/61` | Gerätetyp | Info |
| `39/66` | Interner Fehler | Service |
| `39/82` | Softwareversion EWM | Service |
| `39/90` | Brenner sperren | Service |
| `39/94` | Reinigung bestätigen | Betreiber |
| `39/95` | Brennstoffzuführung anfordern | Betreiber |
| `39/100` | Wartung | Service |
| `40/0` | RAS-Steigschnecke Mindeststrom relativ | Werk |
| `40/1` | RAS-Steigschnecke Spitzenststrom relativ | Werk |
| `40/2` | RAS-Steigschnecke Maximale Frequenz | Werk |
| `40/3` | RAS-Steigschnecke Minimale Frequenz | Werk |
| `40/4` | Anzahl der Steigschnecken | Service, Werk |
| `40/5` | Zeit bis Stiring bei 100% Leistung | Service, Werk |
| `40/6` | Zeit bis Stiring bei 30% Leistung | Service, Werk |
| `40/7` | Stokerschnecke Ansteuerung max. | Werk |
| `40/8` | Stokerschnecke Ansteuerung min. | Werk |
| `40/9` | RAS-Direktschnecke Ansteuerung max. | Werk |
| `40/10` | RAS-Direktschnecke Ansteuerung min. | Werk |
| `40/11` | RAS-Steigschnecke Ansteuerung max. | Werk |
| `40/12` | RAS-Steigschnecke Ansteuerung min. | Werk |
| `40/13` | Vorratsbehälterschnecke Ansteuerung max. | Werk |
| `40/14` | Vorratsbehälterschnecke Ansteuerung min. | Werk |
| `40/15` | Stokerschnecke Ansteuerung vorwärts bei Blockade oder Unterbrechung | Werk |
| `40/16` | Stokerschnecke Ansteuerung rückwärts bei Blockade oder Unterbrechung | Werk |
| `40/17` | RAS-Direktschnecke Ansteuerung vorwärts bei Blockade oder Unterbrechung | Werk |
| `40/18` | RAS-Direktschnecke Ansteuerung rückwärts bei Blockade oder Unterbrechung | Werk |
| `40/19` | RAS-Steigschnecke Ansteuerung vorwärts bei Blockade oder Unterbrechung | Werk |
| `40/20` | RAS-Steigschnecke Ansteuerung rückwärts bei Blockade oder Unterbrechung | Werk |
| `40/21` | Vorratsbehälterschnecke Ansteuerung vorwärts bei Blockade oder Unterbrechung | Werk |
| `40/22` | Vorratsbehälterschnecke Ansteuerung rückwärts bei Blockade oder Unterbrechung | Werk |
| `40/23` | Laufzeit RAS-Steigschnecke Rückwärts bei Blockade oder Unterbrechung | Werk |
| `40/24` | Anzahl Versuche Blockade oder Unterbrechung RAS-Steigschnecke | Werk |
| `40/25` | Betriebsstunden bis Reinigung Aschetonne 1 | Werk |
| `40/26` | Betriebsstunden bis Hauptreinigung | Werk |
| `40/27` | Betriebsstunden bis Wartung | Werk |
| `40/28` | Wartung Aus/Ein | Service, Werk |
| `40/29` | Korrekturfaktor Stokerschnecke | Service, Werk |
| `40/30` | Korrekturfaktor RAS-Direktschnecke | Service, Werk |
| `40/31` | Korrekturfaktor RAS-Steigschnecke | Service, Werk |
| `40/32` | Korrekturfaktor Vorratsbehälterschnecke | Service, Werk |
| `40/34` | Korrekturfaktor RAS-Steigschnecke 2 | Werk |
| `40/35` | Korrekturfaktor RAS-Steigschnecke 3 | Werk |
| `40/36` | Index für Anzeige Steigschnecke | Werk |
| `40/37` | RAS-Saugschnecke Ansteuerung Betrieb | Werk |
| `40/38` | RAS-Saugschnecke Ansteuerung vorwärts bei Blockade oder Unterbrechung | Werk |
| `40/39` | RAS-Saugschnecke Ansteuerung rückwärts bei Blockade oder Unterbrechung | Werk |
| `40/40` | Korrekturfaktor RAS-Saugschnecke | Service, Werk |
| `40/41` | Frequenz Saugturbine Max | Werk |
| `40/42` | Frequenz Saugturbine Min | Werk |
| `40/43` | Ansteuerung Saugturbine | Werk |
| `40/44` | Blockade Stokerschnecke | Service |
| `40/45` | Blockade Direktschnecke | Service |
| `40/46` | Blockade Saugzuführung | Service |
| `40/47` | Blockade Vorratsbehälterschnecke | Service |
| `40/48` | Blockade Steigschnecke | Service |
| `40/49` | Überfüllung Direktschnecke | Service |
| `40/50` | Überfüllung Saugzuführung | Service |
| `40/51` | Überfüllung Steigschnecke | Service |
| `40/52` | Blockade Glutbettschieber | Service |
| `40/53` | Blockade Entaschung | Service |
| `40/54` | Blockade Füllstandschalter | Service |
| `40/55` | Korrekturfaktor Saugturbine | Service, Werk |
| `40/56` | Brennstoffbewertung Normierungsfaktor | Werk |
| `40/57` | Brennstoffbewertung Bezugsfrequenz | Werk |
| `40/58` | Brennstoffbewertung Bezugsleistung | Werk |
| `40/60` | Blockade Ascheaustragung | Service |
| `40/61` | Blockade Heizflächenreinigung | Service |
| `40/66` | Blockade Ascheförderer | Service |
| `40/69` | Ascheaustragung mit Freigabezeit Beginn | Betreiber |
| `40/70` | Ascheaustragung mit Freigabezeit Ende | Betreiber |
| `40/101` | Ventil Abgas-Rezirkulation | Service |
| `40/105` | Abgas-Rezirkulation | Service |
| `42/21` | Sensor Pelletförderung | Service |
| `43/34` | Sonde 1 | Betreiber |
| `43/35` | Sonde 2 | Betreiber |
| `43/36` | Sonde 3 | Betreiber |
| `43/37` | Sonde 4 | Betreiber |
| `43/38` | Sonde 5 | Betreiber |
| `43/39` | Sonde 6 | Betreiber |
| `43/40` | Sonde 7 | Betreiber |
| `43/41` | Sonde 8 | Betreiber |
| `43/79` | Sonden zurücksetzen | Betreiber |
| `376` | – | Werk |

### fctType 26 – Wärmepumpe (Energiemanagement)

| OID | Name | Ebene |
|---|---|---|
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `39/66` | Interner Fehler | Service |
| `50/5` | Betriebswahl | Betreiber |
| `50/43` | Puffertemperatur | Info |
| `51/35` | Sollwert Spreizung | Service, Werk |
| `51/84` | Hysterese Umschaltventil bei EnergyHold | Werk |
| `51/85` | Rücklauftemperatur für EnergyHold Heizen | Werk |
| `51/86` | Hysterese für EnergyHold Heizen | Werk |
| `51/87` | EnergyHold Max für Heizen | Werk |
| `51/88` | Frostschutztemperatur 1 | Werk |
| `51/89` | Hysterese Frostschutztemperatur 1 | Werk |
| `51/90` | Frostschutztemperatur 2 | Werk |
| `51/93` | Frostschutztemperatur Aussentemperatur | Werk |
| `51/94` | Verzögerung Error bei Frostschutz | Werk |
| `52/10` | Aussentemperatur Regelung | Info |
| `54/0` | Kosten Pellets | Betreiber, Werk |
| `54/1` | Wärmemenge Pellets (kWh/kg) | Werk |
| `54/2` | Wirkungsgrad Pelletskessel | Werk |
| `54/5` | Verzögerung Bewertung COP Oekonomischer Betrieb | Werk |
| `54/6` | Verzögerung COP Mittelwert < COP Soll | Werk |
| `54/7` | Zeitprogramm Stromtarife | Betreiber, Werk |
| `54/8` | Tarif 1 | Betreiber, Werk |
| `54/9` | Tarif 2 | Betreiber, Werk |
| `54/10` | Tarif 3 | Betreiber, Werk |
| `54/11` | Tarif 4 | Betreiber, Werk |
| `54/12` | Tarif 5 | Betreiber, Werk |
| `54/13` | Maximale Laufzeit im Bivalenzzustand 1 bei PV Eingang | Werk |
| `54/15` | Zeitprogramm Pufferspeicher | Betreiber, Werk |
| `54/16` | Sollwert Pufferspeicher bei PV | Betreiber, Werk |
| `54/17` | Umschaltventil immer auf BioWIN | Werk |
| `54/18` | EnergyHold Max BioWIN im Zustand Bivalenz 3 | Werk |
| `54/19` | Maximale Laufzeit EnergyHold Max bei BioWIN | Werk |
| `54/20` | Mindestlaufzeit beide WEZ freigegeben BioWIN Hybrid | Werk |
| `54/22` | Mindestlaufzeit beide WEZ freigegeben AeroWIN | Werk |
| `54/23` | Verzögerung Error Volumenstrom | Werk |
| `54/24` | Abweichung Volumenstrom zu Soll für Error | Werk |
| `54/25` | Regler Spreizung P-Band | Werk |
| `54/26` | Regler Spreizung Nachstellzeit | Werk |
| `54/27` | Untere Einsatzgrenze Wärmepumpe | Betreiber, Werk |
| `54/28` | Bivalenztemperatur Heizung | Betreiber, Werk |
| `54/29` | Regler Volumenstrom P-Band | Werk |
| `54/30` | Regler Volumenstrom Nachstellzeit | Werk |
| `54/31` | Verzögerungszeit Bivalenz Heizung | Betreiber, Werk |
| `54/32` | Verzögerungszeit Bivalenz WW | Betreiber, Werk |
| `54/33` | Notbetrieb | Betreiber, Werk |
| `54/34` | Nachlaufzeit Pumpe | Werk |
| `54/35` | Verzögerungszeit WP nicht verfügbar für Heizung | Werk |
| `54/37` | Hysterese Bivalenz | Service, Werk |
| `54/38` | Minimale Kesseltemperatur Pelletskesssel | Werk |
| `54/39` | Hysterse Minimale Kesseltemperatur Pelletskesssel | Werk |
| `54/40` | Laufzeit Umschaltventil | Werk |
| `54/41` | Bivalenztemperatur WW | Betreiber, Werk |
| `54/43` | SG Ready | Betreiber, Werk |
| `54/45` | Hybrid-Assistent | Betreiber, Werk |
| `54/46` | Helligkeit Hybrid-Assistent | Betreiber, Werk |
| `54/49` | SG Ready Status | Info |
| `54/50` | Ladeventil | Service, Werk |
| `54/51` | Pufferspeicher | Service, Werk |
| `54/52` | EnergyHold WW mit Boilerladeventil | Werk |
| `54/53` | Offset Sollwert Warmwasser | Werk |
| `54/54` | Hysterse Offset Sollwert Warmwasser | Werk |
| `54/55` | Laufzeit Boilerladeventil | Werk |
| `54/56` | EnergyHold BioWIN Status bei Frostschutz 2. WEZ | Werk |

### fctType 27 – Wärmepumpe

| OID | Name | Ebene |
|---|---|---|
| `0/0` | Aussentemperatur | Info |
| `2/70` | Datum | Info |
| `2/72` | Uhrzeit | Info |
| `4/92` | Softwareversion | Info |
| `4/93` | Hardwareversion | Info |
| `9/57` | Solltemperatur ext. Wärmeanforderung | Service |
| `12/38` | Gerätetyp | Info |
| `20/14` | min. Drehzahl | Service |
| `20/22` | max. Drehzahl | Service |
| `29/30` | Summenstörmeldung Alarm | Service |
| `29/31` | Summenstörmeldung Fehler | Service |
| `29/32` | Summenstörmeldung Info | Service |
| `39/66` | Interner Fehler | Service |
| `39/112` | MAC-Adresse | Info |
| `50/11` | Silentmode | Betreiber |
| `50/14` | Zeitprogramm Silentmode | Betreiber |
| `50/22` | Externe Anforderung | Service |
| `50/28` | Solltemperatur ext. Kühlanforderung | Service |
| `50/31` | Silentmode Faktor | Betreiber |
| `50/39` | Lüftersolldrehzahl A | Service |
| `50/41` | Verdichter Istdrehzahl | Service |
| `50/42` | Lüftersolldrehzahl B | Service |
| `50/68` | Betriebswahl | Betreiber |
| `50/70` | Betriebsphase | Service |
| `50/71` | Heizgrenze aktiv | Service |
| `50/72` | Kühlgrenze aktiv | Service |
| `50/73` | Kondensationswächter | Service |
| `50/88` | Software Wärmepumpe | Service |
| `51/21` | Leistung Heizen | Service |
| `51/22` | Leistung Kühlen | Service |
| `51/64` | Hysterese Aus | Service |
| `51/65` | Hysterese Ein | Service |
| `51/70` | Pausenzeit Wärmepumpe | Service |
| `51/71` | Pausenzeit abbrechen | Service |
| `51/80` | Hysterese Kühlen Aus | Service |
| `51/81` | Hysterese Kühlen Ein | Service |
| `52/12` | Aussentemperatur Wärmepumpe | Service |
| `52/14` | Heißgastemperatur | Service |
| `52/15` | Vorlauftemperatur | Service |
| `52/16` | Rücklauftemperatur | Service |
| `52/17` | Sauggastemperatur | Service |
| `52/18` | Verdampferausstrittstemperatur | Service |
| `52/20` | Verflüssigeraustrittstemperatur | Service |
| `52/30` | Niederdruck | Service |
| `52/32` | Hochdruck | Service |
| `52/49` | Anzahl Starts Heizen | Info |
| `52/70` | Expansionsventil | Service |
| `52/72` | Volumenstrom | Service |
| `52/80` | Energiezähler Wärmepumpe Wirkleistung | Info |
| `52/81` | Energiezähler Wärmepumpe Gesamtenergie | Info |
| `52/82` | Energiezähler PV-Überschuss Wirkleistung | Info |
| `52/83` | Energiezähler PV-Überschuss Gesamtenergie | Info |
| `52/121` | Vorlauftemperatur Soll | Info |
| `54/21` | Zustand Bivalenz | Service |
| `54/27` | Untere Einsatzgrenze Wärmepumpe | Betreiber |
| `54/28` | Bivalenztemperatur Heizung | Betreiber |
| `54/31` | Verzögerungszeit Bivalenz Heizung | Betreiber |
| `54/32` | Verzögerungszeit Bivalenz WW | Betreiber |
| `54/37` | Hysterese Bivalenz | Service |
| `54/41` | Bivalenztemperatur WW | Betreiber |
| `54/43` | SG Ready | Betreiber |
| `56/5` | Aktuelle Stufe E-Heizung | Info |
| `56/6` | Betriebsphase | Info |
| `56/29` | Betriebsstunden | Info |
| `58/5` | Pumpensteuerung | Service |
| `58/12` | Pumpe Wärmeerzeuger | Service |
| `59/7` | Anlagenkonfiguration | Service |
| `59/45` | Temperatur Lastausgleich | Info |
| `59/71` | Anzahl Starts | Info |
| `59/72` | Anzahl Stufen E-Heizung | Service |
| `59/77` | Vorlauftemperatur Soll | Info |
| `59/92` | Verzögerungszeit PV-Überschuss Heizkreis | Betreiber |
| `59/93` | Verzögerungszeit PV-Überschuss Warmwasser | Betreiber |
| `59/95` | Zeitprogramm Freigabezeit Energy Pilot | Betreiber |
| `59/99` | Betriebswahl | Betreiber |
| `59/111` | PV-Überschuss für WW-Ladung | Betreiber |
| `60/5` | Energy Pilot aktivieren | Service |
| `60/8` | Pausenzeit nach Heizen / Kühlen | Service |
| `60/9` | Ventil Inneneinheit | Service |
| `60/18` | Wärmemenge Heizen | Info |
| `60/19` | Energiemenge Kühlen | Info |
| `63/7` | Ventil Deckenkühlung invertiert | Service |
| `63/8` | Ventil Inneneinheit invertiert | Service |
