# Vorlagen und Dienste

HeatNexus liefert sechs Automations-Vorlagen und sechs Dienste mit. Die
Vorlagen landen bei der Einrichtung unter
`blueprints/automation/heatnexus/` und werden mit jeder neuen Fassung
aufgefrischt; welche mitkommen, steht in den Optionen.

## Automations-Vorlagen

### Störung melden

Meldet sich, sobald die Anlage eine Störung anzeigt, wiederholt die Meldung auf
Wunsch und meldet die Entwarnung.

Ausgewertet wird der Sensor **Störung gemeldet**, nicht der angezeigte Text.
Damit hängt die Automation nicht an einer Formulierung und läuft auch bei
mehreren gleichzeitigen Meldungen richtig. Jeder Anlagenteil hat einen eigenen
Sensor dieser Art; für den Kessel genügt meist einer.

In der Aktion stehen `stoerungstext`, `anzahl` und `anlagenteil` bereit.

### Wartungswarnung mit Erinnerung

Dreistufige Warnung für eine Restlaufzeit: Vorwarnung bei der ersten Schwelle,
Warnung bei der zweiten, danach Erinnerung in festem Abstand. Erledigt ist die
Sache, sobald die Restlaufzeit wieder über der Rückstellschwelle liegt — den
Zähler setzt die Anlage nach der Arbeit selbst zurück.

Je Zähler eine Automation. Am PuroWIN sind das *Laufzeit bis Ascheentleerung*,
*Laufzeit bis Hauptreinigung* und *Laufzeit bis Wartung*. Helfer werden keine
gebraucht, den Zustand hält die Automation selbst.

### Brennstoffvorrat niedrig

Meldet sich, wenn der Vorratsbehälter leer ist, und erinnert daran, solange
sich nichts ändert.

Ausgewertet wird der Sensor **Vorratsbehälter Status**. Er ist keine
Füllstandszahl, sondern eine Zustandsmeldung — am PuroWIN *voll*,
*teilgefüllt*, *leer* und *Fehler Vorratsbehälter*. Welche davon eine Meldung
wert sind, wird als Text eingetragen, genau so, wie der Sensor sie anzeigt.

### Heizkreis bei Abwesenheit absenken

Senkt einen Heizkreis ab, sobald niemand mehr zu Hause ist, und stellt bei der
Rückkehr den vorherigen Betrieb wieder her. Die Betriebsart wird vor dem
Absenken gemerkt. Zur Auswahl stehen Absenkbetrieb, Standby und Heizbetrieb.

### Betriebsdauer erfassen

Zählt, wie lange die Anlage tatsächlich gelaufen ist — anhand der Betriebsart
und der Zustände, die als Ruhe gelten.

### Legionellenschutz nachbilden

Führt den Warmwasserspeicher in festem Turnus auf eine erhöhte Temperatur,
indem die Einmalladung dafür benutzt wird. Gedacht für Anlagen, deren Regler
die eingebaute Funktion nicht führt — dort gibt es keinen Datenpunkt, den man
einschalten könnte. Nach dem Lauf wird alles zurückgestellt: Ladung aus,
Ladetemperatur zurück, Betriebswahl zurück.

> **Verbrühungsgefahr.** Wasser mit 60 °C verbrüht die Haut in wenigen
> Sekunden. Diese Vorlage nur einsetzen, wenn hinter dem Speicher eine
> thermostatische Verbrühschutz-Armatur sitzt und die Zapftemperatur begrenzt.
> Nachtstunden als Vorgabe sind kein Ersatz dafür.

> **Kein zertifizierter Legionellenschutz.** Die Vorlage ahmt nach, was der
> Regler sonst selbst täte. Sie prüft nicht, ob jede Leitung die Temperatur
> erreicht, und ersetzt keine Anlage nach DVGW W 551.

## Dienste

| Dienst | Ziel | Wofür |
|---|---|---|
| `rediscover` | — | Verwirft den Erkennungsstand und liest die Anlage neu ein. Nach Umbauten. |
| `set_vorgabe` | Thermostat | Befristete Raumtemperatur, dieselbe, die die Anlage „Eco / Comfort" nennt. |
| `set_current_temp_compensation` | Thermostat | Verschiebt die gemessene Raumtemperatur um einen festen Betrag. |
| `set_time_program` | Zeitprogramm-Sensor | Schreibt ein Wochenprogramm. |
| `meldungen_loeschen` | Sensor | Leert die Meldungsliste in Home Assistant. |
| `dashboard_ausgeben` | — | Gibt das mitgelieferte Dashboard als YAML zurück. |

### Befristete Vorgabe

Temperatur zwischen 10 und 30 °C, Dauer bis 400 Minuten. `0` beendet eine
laufende Vorgabe sofort. Danach stellt die Anlage von selbst auf die
Betriebswahl zurück, die Zeitprogramme bleiben unverändert. Steht der Kreis auf
Standby oder WW-Betrieb, wird für die Dauer in ein Heizprogramm geschaltet und
anschließend zurückgesprungen.

```yaml
action: heatnexus.set_vorgabe
target:
  entity_id: climate.heizkreis_erdgeschoss
data:
  temperature: 21.5
  duration: 180
```

### Behaglichkeitskorrektur

Für Fühler, die dauerhaft zu warm oder zu kalt messen, weil sie ungünstig
hängen. Der Betrag liegt zwischen −3 und +3 K und wird auf die gemessene
Raumtemperatur aufgeschlagen.

### Zeitprogramm setzen

Zwei Wege. Vereinfacht über `switch_points` — mit `weekdays`, sonst gilt es
täglich:

```yaml
action: heatnexus.set_time_program
target:
  entity_id: sensor.heizkreis_erdgeschoss_zeitprogramm
data:
  weekdays: ["Mo", "Di", "Mi", "Do", "Fr"]
  switch_points:
    - { time: "06:00", value: 21 }
    - { time: "22:00", value: 18 }
```

Oder über `blocks` mit voller Kontrolle über mehrere Wochentag-Gruppen:

```yaml
action: heatnexus.set_time_program
target:
  entity_id: sensor.heizkreis_erdgeschoss_zeitprogramm
data:
  blocks:
    - weekdays: ["Mo", "Di", "Mi", "Do", "Fr"]
      switch_points:
        - { time: "06:00", value: 21 }
        - { time: "22:00", value: 18 }
    - weekdays: ["Sa", "So"]
      switch_points:
        - { time: "07:00", value: 21 }
        - { time: "23:00", value: 18 }
```

`blocks` überschreibt `switch_points` und `weekdays`, wenn beides angegeben ist.
Geschrieben wird nur der Inhalt: HeatNexus liest das Objekt vorher, tauscht den
Wert aus und lässt die Hülle der Anlage unangetastet.

### Dashboard ausgeben

Das mitgelieferte Dashboard wird bei jedem Öffnen neu gebaut und ist deshalb
nicht bearbeitbar. Der Dienst gibt es als YAML zurück — damit lässt sich ein
eigenes Dashboard anlegen: neues Dashboard erstellen, Rohkonfigurations-Editor
öffnen, Text einfügen. Ab da gehört es dir und ändert sich nicht mehr mit.
