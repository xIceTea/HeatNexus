# Werkzeuge

## Anlagen-Probe

Liest Struktur, Menü-Ebenen, alle Datenpunkte und Zeitprogramme einer oder
mehrerer Anlagen aus. Nur Python-Standardbibliothek, kein zusätzliches Paket.

**Windows:** `probe.cmd` doppelklicken. Es fragt nacheinander ab:

1. IP-Adressen (mehrere durch Komma oder Leerzeichen getrennt, werden für den
   nächsten Lauf gemerkt)
2. Service-Passwort – die Eingabe bleibt verdeckt, gespeichert wird sie nie.
   Bei mehreren Anlagen wahlweise ein Passwort für alle oder je Anlage eines
3. was gemacht werden soll (Mehrfachauswahl, z. B. `2,4,5`, oder `a` für alles)
4. Zielordner (Standard `probe`)

Vorab wird jede Anlage angepingt, nicht erreichbare werden übersprungen.

**Kommandozeile:**

```bash
python tools/heatnexus_probe.py                                   # geführter Modus
python tools/heatnexus_probe.py all 192.0.2.10 192.0.2.11
python tools/heatnexus_probe.py menus 192.0.2.10 -o probe
python tools/heatnexus_probe.py oid 192.0.2.10 /1/15/0/3/50/0
```

Passwort über `--password`, über die Umgebungsvariable `HEATNEXUS_PW` oder per
Abfrage. Eine Anlage darf auch als `192.0.2.10:8080` angegeben werden.

### Aktionen

| Aktion | Ergebnis |
|---|---|
| `structure` | Knoten, Funktionen, Gerätemeldungen → `<host>_structure.json` |
| `menus` | alle Menü-Ebenen mit Werten und Metadaten → `<host>_menus.json`, `<host>_datenpunkte.csv` |
| `objects` | Zeitprogramme und andere strukturierte Objekte → `<host>_objekte.json` |
| `compare` | Abgleich mit der mitgelieferten Geräte-Datenbank |
| `report` | Markdown-Bericht mit Kennzahlen und Abgleich → `<host>_bericht.md` |
| `diag` | testet, wie sich Menüs mit mehr als zehn Datenpunkten nachladen lassen |
| `texte` | prüft, ob die Anlage ihre Datenpunktnamen als Datei ausliefert |
| `statisch` | sucht die statischen Positionen (Störspeicher, Sonderzeitprogramm) |
| `stoerspeicher` | fragt den Störspeicher über den SOAP-Dienst der Steuerung |
| `endpunkte` | zählt auf, welche Endpunkte die Steuerung kennt |
| `nv` | liest LON-Netzwerkvariablen einzeln aus |
| `vollabzug` | holt `/api/1.0/datapoints`, den Cache der zuletzt gelesenen Werte |
| `vergleich` | stellt die LON-Werte den Datenpunkten gegenüber: liefert LON etwas, das es als OID nicht gibt |
| `oid`, `objekt` | einzelnen Datenpunkt bzw. ein strukturiertes Objekt lesen |
| `all` | alles nacheinander |

Der Zugang wählt sich über `--user`. An der geprüften Baureihe liefern `USER`
und `Service` denselben Umfang; der Schalter ist da, weil das für andere
Baureihen nicht belegt ist.

Die CSV ist mit Semikolon getrennt und öffnet sich direkt in Excel: OID, gn/mn,
Name aus der Datenbank, Wert, Einheit, Wertebereich, schreibbar, Enum, Typ.

### Hinweise

- Datenpunkte werden **menüweise** gelesen; ein Request liefert bis zu zehn
  Werte samt Metadaten. Meldet eine Ebene mehr, wird seitenweise nachgeladen –
  die dafür nötige Form ermittelt das Werkzeug selbst.
- Der Bericht stellt „erwartet" und „gelesen" gegenüber. Bleibt eine Lücke,
  zeigt die Aktion `diag`, woran es liegt.
- Standard sind drei parallele Anfragen mit 30 s Zeitlimit und zwei
  Wiederholungen. Mehr Parallelität bringt nichts: Die Steuerung beantwortet
  Anfragen der Reihe nach, zusätzliche Anfragen warten nur woanders.
- Der Zielordner enthält Anlagendaten (IP-Adressen, Messwerte) und ist über die
  `.gitignore` vom Repository ausgeschlossen.
