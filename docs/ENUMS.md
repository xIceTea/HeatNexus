# Auswahlwerte

**Erzeugt aus `device_db.json` – nicht von Hand ändern.**
Neu erzeugen mit `python tools/build_datenpunkte_doku.py`.

167 Auswahltabellen. Sie sind **keine Listen**: Die Zahlen haben
Lücken, weil nicht jede Anlage jeden Wert kennt. Zusätzlich meldet die Anlage
im Feld `enum` ihrer Metadaten, welche Werte sie tatsächlich zulässt – erst
das ergibt die Auswahl, die HeatNexus anbietet.

Weicht ein Text an der echten Anlage nachweislich ab, steht die
berichtigte Tabelle in `const.ENUMS` und geht der erzeugten vor.
Derzeit ist das bei keiner nötig.

### `2/1`

| Wert | Bedeutung |
|---|---|
| 0 | Brenner gesperrt |
| 1 | Selbsttest |
| 2 | WE ausschalten |
| 3 | Standby |
| 4 | Brenner AUS |
| 5 | Vorspülen |
| 6 | Zündphase |
| 7 | Stabilisierung |
| 8 | Modulation |
| 9 | Gerät gesperrt |
| 10 | Standby Sperrzeit |
| 11 | Gebläse AUS |
| 12 | Verkleidungstür offen |
| 13 | Zündung bereit |
| 14 | Abbruch Zündung |
| 15 | Anheizvorgang |
| 16 | Schichtladung |
| 17 | Ausbrand |

### `2/2`

| Wert | Bedeutung |
|---|---|
| 0 | Brenner |
| 1 | Pufferladepumpe |
| 2 | Umschaltventil |
| 3 | Umschaltventil |
| 4 | WW-Ladepumpe |
| 6 | Puffertransferpumpe |
| 7 | Kesselkreispumpe |
| 12 | Brenner ZSK |
| 13 | Pumpe ZSK |
| 14 | Kühlen |

### `2/9`

| Wert | Bedeutung |
|---|---|
| 0 | Standby |
| 1 | Heizbetrieb |
| 2 | Absenkbetrieb |
| 3 | WW-Ladung |
| 4 | Eco / Comfort |
| 5 | Urlaubsprogramm |
| 6 | Estrich |
| 7 | Frostschutz |
| 8 | Standby |
| 9 | Handbetrieb |
| 10 | Testbetrieb |
| 11 | Kaminkehrer |
| 12 | Brenner AUS |
| 13 | Brenner EIN |
| 14 | Automatikkessel |
| 15 | FB-Kessel |
| 16 | Pufferspeicher |
| 17 | Warmwasser Hygiene-Programm |
| 18 | Warmwasser Einmalladung |
| 19 | Automatikbetrieb |
| 20 | Kühlen |
| 21 | Standby |

### `2/16`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `2/59`

| Wert | Bedeutung |
|---|---|
| 0 | Ausgeschaltet |
| 1 | Abschaltvorgang |
| 2 | Festbrennstoff-/Pufferbetrieb |
| 3 | Brennstoffzuführung in Betrieb |
| 4 | Brennstoffzuführung |
| 5 | Kessel-Temperatur |
| 6 | Brennstoffzuführung in Betrieb |
| 7 | Brennstoffzuführung |
| 8 | Handbetrieb |
| 9 | Kaminkehrerfunktion |
| 10 | Aktorentest |
| 11 | Installationsvorgang aktiv |
| 12 | Brennstoffzuführung in Betrieb |
| 13 | Inbetriebnahme |
| 14 | Lagerraum befüllen |
| 15 | Lagerraum befüllen |
| 16 | Grundeinstellungen |

### `2/73`

| Wert | Bedeutung |
|---|---|
| 0 | Mo |
| 1 | Di |
| 2 | Mi |
| 3 | Do |
| 4 | Fr |
| 5 | Sa |
| 6 | So |

### `3/50`

| Wert | Bedeutung |
|---|---|
| 0 | Standby |
| 1 | Programm 1 |
| 2 | Programm 2 |
| 3 | Programm 3 |
| 4 | Heizbetrieb |
| 5 | Absenkbetrieb |
| 6 | WW-Betrieb |
| 7 | Handbetrieb |
| 8 | Kühlen |

### `4/12`

| Wert | Bedeutung |
|---|---|
| 0 | senden |
| 1 | verwenden |
| 2 | lokale Zeit |

### `4/13`

| Wert | Bedeutung |
|---|---|
| 0 | senden |
| 1 | verwenden |
| 2 | lokale TA |

### `4/14`

| Wert | Bedeutung |
|---|---|
| 0 | senden |
| 1 | verwenden |
| 2 | lokale BW |

### `4/33`

| Wert | Bedeutung |
|---|---|
| 0 | Schaltkontakt |
| 1 | Interface ZSP 4601 |

### `4/60`

| Wert | Bedeutung |
|---|---|
| 0 | beenden |
| 1 | Belegreifheizen |
| 2 | Funktionsheizen |

### `4/77`

| Wert | Bedeutung |
|---|---|
| 0 | 1 |
| 1 | 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 5 |
| 5 | 6 |
| 6 | 7 |
| 7 | 8 |

### `5/2`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `5/6`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Mit Zeitsteuerung |
| 2 | Mit Temperatursteuerung |
| 3 | Mit Impulssteuerung |
| 4 | EIN |

### `5/76`

| Wert | Bedeutung |
|---|---|
| 0 | inaktiv |
| 1 | WW-Ladepumpe |
| 2 | Ladeventil |
| 3 | Umschaltventil |
| 4 | Ventil Inneneinheit |
| 5 | Ventil Inneneinheit und WW-Ladepumpe |

### `7/12`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | 0..10V |
| 2 | PWM |
| 3 | PWM |
| 4 | ohne |
| 5 | LIN |

### `7/76`

| Wert | Bedeutung |
|---|---|
| 0 | inaktiv |
| 1 | Radiatoren |
| 2 | Fussboden |
| 3 | Pumpenkreis |
| 4 | Vorlauf Regelung |
| 5 | Fan Coil |

### `9/75`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |
| 2 | Handbetrieb |
| 3 | Kaminkehrer |
| 4 | Aktorentest |
| 5 | Inbetriebnahme |
| 6 | Serviceausbrand |
| 7 | Lagerraum befüllen |

### `11/76`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `12/103`

| Wert | Bedeutung |
|---|---|
| 0 | Automatische Erkennung |
| 1 | Normal |
| 2 | Gluterhaltung |

### `12/105`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `14/19`

| Wert | Bedeutung |
|---|---|
| 0 | ausgeschaltet |
| 1 | ohne Zeitsteuerung |
| 2 | mit Freigabezeit |
| 3 | mit Startzeit |

### `14/21`

| Wert | Bedeutung |
|---|---|
| 0 | alle Sonden |
| 1 | nur Sonde 1 |
| 2 | nur Sonde 2 |
| 3 | nur Sonde 3 |
| 4 | nur Sonde 4 |
| 5 | nur Sonde 5 |
| 6 | nur Sonde 6 |
| 7 | nur Sonde 7 |
| 8 | nur Sonde 8 |
| 16 | nur Zone 1 |
| 17 | nur Zone 2 |

### `14/23`

| Wert | Bedeutung |
|---|---|
| 0 | ohne Zuführsystem |
| 1 | Saugturbine mit 3 Sonden |
| 2 | Saugturbine mit 2 Sonden |
| 3 | Saugturbine mit Rührwerk |
| 17 | Saugturbine mit Rührwerk |
| 18 | Saugturbine mit 2 Sonden |
| 19 | Saugturbine mit 3 Sonden |
| 20 | Saugturbine mit 4 Sonden |
| 22 | Saugturbine mit 6 Sonden |
| 24 | Saugturbine mit 8 Sonden |

### `14/74`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `14/76`

| Wert | Bedeutung |
|---|---|
| 0 | Stufe 0 |
| 1 | Stufe 1 |
| 2 | Stufe 2 |
| 3 | Stufe 3 |

### `14/77`

| Wert | Bedeutung |
|---|---|
| 0 | Rauchgasthermostat |
| 1 | Zuluftklappe |
| 2 | Ext. Verbrennungsluft |

### `20/0`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `20/1`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `20/2`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `20/3`

| Wert | Bedeutung |
|---|---|
| 0 | Auto mit Umschaltung |
| 1 | Auto mit Laufzeitverlängerung |
| 2 | Auto mit Parallelbetrieb |
| 3 | FB-/Pufferbetrieb |

### `20/4`

| Wert | Bedeutung |
|---|---|
| 0 | Brenner und Transferpumpe |
| 1 | Brenner und Kesselpumpe |
| 2 | Pufferladung mit TPE |
| 3 | Pufferladung mit TPE/TPA |
| 4 | Pufferladung bedarfsopt. |
| 5 | Pufferladung Kaskade |

### `20/5`

| Wert | Bedeutung |
|---|---|
| 0 | Pufferfühler mitte |
| 1 | Rauchgasfühler |
| 2 | Rauchgasthermostat |

### `20/6`

| Wert | Bedeutung |
|---|---|
| 0 | Motor |
| 1 | Th. Antrieb |

### `20/8`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `20/15`

| Wert | Bedeutung |
|---|---|
| 0 | Standby |
| 1 | Automatikbetrieb |
| 2 | Festbrennstoffbetrieb |
| 3 | Pufferbetrieb |
| 4 | Auto mit Zeitprogramm |
| 6 | Handbetrieb |
| 7 | Kaminkehrerfunktion |

### `20/18`

| Wert | Bedeutung |
|---|---|
| 0 | Transferpumpe |
| 1 | Pufferladepumpe |
| 2 | Kesselkreispumpe |
| 3 | Heizkreispumpe |

### `20/19`

| Wert | Bedeutung |
|---|---|
| 0 | Pufferladung mit TPE |
| 1 | Pufferladung mit TPE/TPA |
| 2 | Hydr. Weiche mit TWE |
| 3 | Hydr. Weiche mit TWE/TWA |

### `20/20`

| Wert | Bedeutung |
|---|---|
| 0 | Automatik |
| 1 | gering |
| 2 | mittel |
| 3 | hoch |
| 4 | maximal |

### `20/21`

| Wert | Bedeutung |
|---|---|
| 0 | Automatik |
| 1 | gering |
| 2 | mittel |
| 3 | hoch |
| 4 | maximal |

### `20/26`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | Notkessel |
| 2 | Spitzenlast |

### `20/27`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `20/81`

| Wert | Bedeutung |
|---|---|
| 0 | 19,2 kbit/s |
| 1 | 38,4 kbit/s |
| 2 | 76,8 kbit/s |
| 3 | 115,2 kbit/s |

### `20/105`

| Wert | Bedeutung |
|---|---|
| 0 | 0 |
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 4 |
| 5 | 5 |
| 6 | 6 |
| 7 | 7 |
| 8 | 8 |
| 9 | 9 |
| 10 | 10 |
| 11 | 11 |
| 12 | 12 |
| 13 | 13 |
| 14 | 14 |
| 15 | 15 |
| 16 | 16 |
| 17 | 17 |
| 18 | 18 |
| 19 | 19 |
| 20 | 20 |
| 21 | 21 |

### `20/106`

| Wert | Bedeutung |
|---|---|
| 0 | Stufe 0 |
| 1 | Stufe 1 |
| 2 | Stufe 2 |
| 3 | Stufe 3 |

### `20/107`

| Wert | Bedeutung |
|---|---|
| 0 | ¤ |
| 1 | EUR |
| 2 | CHF |
| 3 | GBP |
| 4 | DKK |
| 5 | SEK |
| 6 | NOK |
| 7 | PLN |
| 8 | CZK |
| 9 | HUF |
| 10 | HRK |
| 11 | RON |
| 12 | BGN |

### `20/118`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `20/124`

| Wert | Bedeutung |
|---|---|
| 0 | Thermisches Mischventil |
| 1 | Motor Mischventil |

### `22/31`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |

### `23/94`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `23/95`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `23/97`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `29/0`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `29/1`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `29/2`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `29/3`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `29/21`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `29/30`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `29/31`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `29/32`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `37/44`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `38/89`

| Wert | Bedeutung |
|---|---|
| 0 | ohne |
| 1 | mit |

### `38/126`

| Wert | Bedeutung |
|---|---|
| 0 | Hackgut normal |
| 1 | Hackgut feucht |
| 2 | Pellets |
| 3 | Hackgut normal schlackend |
| 4 | Hackgut feucht schlackend |

### `38/127`

| Wert | Bedeutung |
|---|---|
| 0 | Hackgut normal |
| 1 | Hackgut feucht |
| 2 | Pellets |
| 3 | Hackgut normal schlackend |
| 4 | Hackgut feucht schlackend |

### `39/57`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `39/76`

| Wert | Bedeutung |
|---|---|
| 0 | Fehler Vorratsbehälter |
| 1 | Vorratsbehälter leer |
| 2 | Vorratsbehälter teilgefüllt |
| 3 | Vorratsbehälter voll |

### `39/90`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `39/94`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Reinigung |
| 2 | Hauptreinigung |
| 3 | Wartung |
| 4 | Hauptreinigung und Aschetonnen entleeren |

### `39/95`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `39/100`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Reinigung |
| 2 | Hauptreinigung |
| 3 | Wartung |
| 4 | Hauptreinigung und Aschetonnen entleeren |

### `39/107`

| Wert | Bedeutung |
|---|---|
| 0 | Gesperrt |
| 1 | Freigegeben |

### `39/108`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `40/28`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |

### `40/105`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `41/51`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |

### `41/54`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `41/110`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `42/18`

| Wert | Bedeutung |
|---|---|
| 1 | Tagesbehälter |
| 2 | Wochenbehälter |
| 10 | Saugturbine mit Rührwerk |
| 11 | Saugturbine mit 3 Sonden |
| 12 | Saugturbine mit 8 Sonden |
| 13 | Saugturbine mit SBT 400 |

### `42/19`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `42/21`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `42/46`

| Wert | Bedeutung |
|---|---|
| 0 | Pumpe Wärmeerzeuger |
| 1 | Absperreinheit |
| 2 | Summenstörmeldung |

### `42/75`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `42/89`

| Wert | Bedeutung |
|---|---|
| 0 | Klassik |
| 1 | Exklusiv |
| 2 | Alpha |

### `43/34`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |
| 2 | Leer |

### `43/35`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |
| 2 | Leer |

### `43/36`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |
| 2 | Leer |

### `43/37`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |
| 2 | Leer |

### `43/38`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |
| 2 | Leer |

### `43/39`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |
| 2 | Leer |

### `43/40`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |
| 2 | Leer |

### `43/41`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Ein |
| 2 | Leer |

### `43/49`

| Wert | Bedeutung |
|---|---|
| 0 | Sonde |
| 1 | Sonde 1 saugen |
| 2 | Sonde 1 spülen |
| 3 | Sonde 2 saugen |
| 4 | Sonde 2 spülen |
| 5 | Sonde 3 saugen |
| 6 | Sonde 3 spülen |
| 7 | Sonde 4 saugen |
| 8 | Sonde 4 spülen |
| 9 | Sonde 5 saugen |
| 10 | Sonde 5 spülen |
| 11 | Sonde 6 saugen |
| 12 | Sonde 6 spülen |
| 13 | Sonde 7 saugen |
| 14 | Sonde 7 spülen |
| 15 | Sonde 8 saugen |
| 16 | Sonde 8 spülen |

### `43/103`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Intern |
| 2 | Volumenstromsensor |
| 3 | Externer Wärmemengenzähler |

### `43/106`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | DN 20 PWM |
| 2 | DN 25 PWM |
| 3 | DN 20 NPN |
| 4 | DN 25 NPN |

### `44/69`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `44/70`

| Wert | Bedeutung |
|---|---|
| 0 | 1 |
| 1 | 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 5 |
| 5 | 6 |
| 6 | 7 |
| 7 | 8 |

### `50/1`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `50/2`

| Wert | Bedeutung |
|---|---|
| 0 | Typ undefiniert |
| 1 | AEK 4.5 |
| 2 | AEK 8.6 |
| 3 | AEP 7.6 |
| 4 | AEP 13.9 |

### `50/4`

| Wert | Bedeutung |
|---|---|
| 0 | Typ undefiniert |
| 1 | AEK 4.5 |
| 2 | AEK 8.6 |
| 3 | AEP 7.6 |
| 4 | AEP 13.9 |

### `50/5`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | Frostschutz |
| 2 | Automatik |
| 3 | Singlebetrieb Pellets |
| 4 | Singlebetrieb Wärmepumpe |
| 5 | Handbetrieb Heizen |
| 6 | Handbetrieb Kühlen |
| 7 | Eco-Betrieb |
| 10 | Aktorentest |
| 11 | Inbetriebnahme |
| 12 | Einstellungen |
| 13 | Automatik Heizen |
| 14 | Automatik Kühlen |

### `50/6`

| Wert | Bedeutung |
|---|---|
| 0 | Gesperrt |
| 1 | Selbsttest |
| 2 | Frostschutz |
| 3 | Standby |
| 4 | Heizen |
| 5 | Kühlen |
| 6 | Abtauen |
| 7 | Silentmode 1 Heizen |
| 8 | Silentmode 1 Kühlen |
| 9 | Silentmode 2 |
| 10 | EVU Sperre aktiv |
| 11 | Heizgrenze aktiv |
| 12 | Aktorentest |

### `50/7`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | Frostschutz |
| 2 | Automatik |
| 3 | Singlebetrieb Pellets |
| 4 | Singlebetrieb Wärmepumpe |
| 5 | Handbetrieb Heizen |
| 6 | Handbetrieb Kühlen |
| 7 | Eco-Betrieb |
| 10 | Aktorentest |
| 11 | Inbetriebnahme |
| 12 | Einstellungen |
| 13 | Automatik Heizen |
| 14 | Automatik Kühlen |

### `50/11`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Mode 1 |
| 2 | Mode 2 |

### `50/22`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Mode 1 |
| 2 | Mode 2 |

### `50/68`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | Frostschutz |
| 2 | Automatik |
| 3 | Vorrang Wärmepumpe |
| 4 | Wärmepumpe |
| 5 | E-Heizung |

### `50/70`

| Wert | Bedeutung |
|---|---|
| 0 | Gesperrt |
| 1 | Standby |
| 2 | Pausenzeit aktiv |
| 3 | Vorwärmen |
| 4 | Heizen |
| 5 | Kühlen |
| 6 | Abtauen |
| 7 | Aktorentest vorbereiten |
| 8 | Aktorentest |

### `50/73`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `50/96`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `50/97`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `51/71`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `51/100`

| Wert | Bedeutung |
|---|---|
| 0 | Standby |
| 1 | Warmwasser |
| 2 | Automatik |
| 3 | Automatik Heizen |
| 4 | Automatik Kühlen |
| 5 | Urlaubsprogramm |

### `51/101`

| Wert | Bedeutung |
|---|---|
| 0 | Standby |
| 1 | Vorlauf |
| 2 | Automatik |
| 3 | Abtauen |
| 4 | Kühlen |
| 5 | Nachlauf |
| 6 | PumpDown |
| 7 | Abschaltung |
| 8 | Fehler |
| 9 | Quellenspülung |

### `51/106`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `51/112`

| Wert | Bedeutung |
|---|---|
| 0 | Standby |
| 1 | Automatik |
| 2 | Normalbetrieb |
| 3 | Absenkbetrieb |

### `51/113`

| Wert | Bedeutung |
|---|---|
| 0 | Typ undefiniert |
| 1 | Sole |
| 2 | Wasser |
| 3 | Luft |
| 4 | DX |
| 5 | Luft-Sole |
| 6 | Quellen Man. |
| 7 | DX Quelle |

### `51/115`

| Wert | Bedeutung |
|---|---|
| 0 | Typ undefiniert |
| 1 | Heizen |
| 2 | Kühlen |
| 3 | Heizen/Passiv Kühlen |
| 4 | Heizen/Kühlen |

### `52/113`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | Heizen |
| 2 | Kühlen |

### `52/115`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | Heizen |
| 2 | Kühlen |

### `52/117`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |
| 2 | Notbetrieb |

### `54/33`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `54/43`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `54/45`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `54/49`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Zustand 1 |
| 2 | Zustand 2 |
| 3 | Zustand 3 |
| 4 | Zustand 4 |

### `54/50`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `54/51`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `55/20`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `56/6`

| Wert | Bedeutung |
|---|---|
| 0 | Gesperrt |
| 1 | Selbsttest |
| 2 | Frostschutz |
| 3 | Standby |
| 4 | Heizen |
| 5 | Kühlen |
| 6 | Abtauen |
| 7 | Silentmode 1 Heizen |
| 8 | Silentmode 1 Kühlen |
| 9 | Silentmode 2 |
| 10 | EVU Sperre aktiv |
| 11 | Heizgrenze aktiv |
| 12 | Aktorentest |

### `58/5`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | 0..10V |
| 2 | PWM |
| 3 | PWM |
| 4 | ohne |
| 5 | LIN |

### `58/38`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Standby |
| 2 | Automatik |
| 3 | Absenkbetrieb |
| 4 | Heizbetrieb |
| 5 | Handbetrieb |

### `58/63`

| Wert | Bedeutung |
|---|---|
| 0 | Aus |
| 1 | Standby |
| 2 | Automatik |
| 3 | Absenkbetrieb |
| 4 | Heizbetrieb |
| 5 | Handbetrieb |

### `58/70`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | EIN |

### `58/83`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | 3-Punkt (230VAC) |
| 2 | 0 - 10V |

### `58/86`

| Wert | Bedeutung |
|---|---|
| 0 | 0 |
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 4 |
| 5 | 5 |
| 6 | 6 |
| 7 | 7 |
| 8 | 8 |
| 9 | 9 |
| 10 | 10 |
| 11 | 11 |
| 12 | 12 |
| 13 | 13 |
| 14 | 14 |
| 15 | 15 |
| 16 | 16 |
| 17 | 17 |
| 18 | 18 |
| 19 | 19 |
| 20 | 20 |
| 21 | 21 |

### `58/101`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `58/102`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `58/107`

| Wert | Bedeutung |
|---|---|
| 0 | Mo |
| 1 | Di |
| 2 | Mi |
| 3 | Do |
| 4 | Fr |
| 5 | Sa |
| 6 | So |

### `58/111`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `58/113`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `58/116`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `58/117`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `58/121`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `58/122`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `58/123`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `59/7`

| Wert | Bedeutung |
|---|---|
| 0 | 0 |
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 4 |
| 5 | 5 |
| 6 | 6 |
| 7 | 7 |
| 8 | 8 |
| 9 | 9 |
| 10 | 10 |
| 11 | 11 |
| 12 | 12 |
| 13 | 13 |
| 14 | 14 |
| 15 | 15 |
| 16 | 16 |
| 17 | 17 |
| 18 | 18 |
| 19 | 19 |
| 20 | 20 |
| 21 | 21 |

### `59/17`

| Wert | Bedeutung |
|---|---|
| 0 | Standby |
| 1 | In Betrieb |
| 2 | Brenner gesperrt |

### `59/23`

| Wert | Bedeutung |
|---|---|
| 0 | ohne |
| 1 | Thermisches Mischventil |
| 2 | Motor Mischventil |

### `59/28`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `59/32`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `59/47`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `59/96`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 |  |
| 2 |  |

### `59/98`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 |  |
| 2 |  |
| 3 |  |

### `59/99`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | PV-Überschuss |
| 2 | Variable Stromtarife |
| 3 | PV-Überschuss und variable Stromtarife |

### `60/5`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `60/6`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `60/10`

| Wert | Bedeutung |
|---|---|
| 0 | AUS |
| 1 | Umschaltventil |
| 2 | Motor |

### `60/14`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `60/26`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `63/0`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `63/1`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `63/2`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `63/4`

| Wert | Bedeutung |
|---|---|
| 0 | Linkslauf |
| 1 | Rechtslauf |

### `63/5`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `63/6`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `63/7`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `63/8`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |

### `63/9`

| Wert | Bedeutung |
|---|---|
| 0 | Nein |
| 1 | Ja |
