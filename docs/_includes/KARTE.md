# Anlagenschaubild als Karte

<p align="center">
  <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_animation.gif"
       alt="Anlagenschaubild in Bewegung: der Kessel startet, der Puffer lädt, Heizkreis und Warmwasser werden warm"
       width="900">
</p>

Das Anlagenschaubild gibt es nicht nur in der mitgelieferten Oberfläche,
sondern auch als Lovelace-Karte. Damit lässt es sich in ein selbst gebautes
Dashboard hängen – mit Werten, laufenden Pumpen und Glutbett wie in der
Oberfläche.

## Einrichten

Die Karte steht ohne Zutun bereit, sobald HeatNexus eingerichtet ist. Kein
Eintrag unter *Einstellungen → Dashboards → Ressourcen* nötig.

Dashboard bearbeiten → **Karte hinzufügen** → nach „HeatNexus" suchen.

Oder in YAML:

```yaml
type: custom:heatnexus-schaubild
```

## Einstellungen

| Feld | Bedeutung | Vorgabe |
|---|---|---|
| `anlage` | Kennung oder Name der Anlage, `alle` für sämtliche | die erste gefundene |
| `farbsatz` | `auto`, `dunkel`, `hell`, `terrakotta`, `petrol`, `pflaume` | `auto` |
| `schrift` | `klein`, `normal`, `gross`, `sehr_gross` | `normal` |
| `animation` | Pumpen und Leitungen bewegen sich | `true` |
| `pumpen` | Pumpen stehen als Marke im Bild | `true` |
| `mischer` | Mischerstellung steht im Bild | `true` |
| `zeichnungen` | je Anlagenteil eine andere Bauteilzeichnung | wie erkannt |
| `liste` | `rechts` oder `unten` – wo die Werteliste steht | `rechts` |
| `zusatzwerte` | Entitäten für die Werteliste neben dem Bild | leer |
| `zeilen` | Aufbau der Zeilen in der Liste | siehe unten |
| `titel_bild` | Überschrift über dem Bild, leer blendet sie aus | `Anlagenübersicht` |
| `titel_liste` | Überschrift über der Liste, leer blendet sie aus | `Werte` |
| `teile_aus` | Anlagenteile, die nicht gezeichnet werden | leer |
| `werte` | je Anlagenteil die Werte, die im Bild stehen | Vorgabe der Anlage |

`auto` folgt dem Erscheinungsbild von Home Assistant. Die Schrift der Marken
wächst mit der Kartenbreite; `schrift` verschiebt das Maß nach oben oder unten.

![Dieselbe Anlage in allen fünf Farbsätzen: Dunkel, Hell, Terrakotta, Petrol, Pflaume](https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_farbsaetze.gif)

Ein Farbsatz färbt Gehäuse, Rahmen und Schrift. Vor- und Rücklauf bleiben in
jedem Satz rot und blau — das ist eine Auskunft, keine Gestaltung.

Alles davon lässt sich im Karteneditor einstellen, YAML ist nicht nötig.

Beispiel mit zwei Anlagen nebeneinander:

```yaml
type: horizontal-stack
cards:
  - type: custom:heatnexus-schaubild
    anlage: Heizhaus
    farbsatz: petrol
  - type: custom:heatnexus-schaubild
    anlage: Wohnhaus
    farbsatz: petrol
```

## Eigene Zeichnungen

Welche Zeichnung ein Anlagenteil bekommt, entscheidet die Erkennung — Hackgut,
Pellets, Scheitholz, Gas/Öl, Wärmepumpe. Wer eine andere will, wählt sie im
Editor unter *Werte im Schaubild → Zeichnungen*; Warmwasser und Zirkulation
stehen dort ebenfalls.

```yaml
zeichnungen:
  PuroWIN: kessel-pellets
  UML Heizkreis-zirkulation: modul
```

## Die Werteliste

Neben dem Bild steht eine Liste, die frei zusammengestellt wird — Werte der
Anlage und beliebige andere Entitäten nebeneinander. Im Karteneditor führt ein
Klick auf eine Zeile zu ihren Einzelheiten: Name, Symbol, Aufbau und wo das
Anlagenteil steht.

| Feld unter `zeilen` | Bedeutung | Vorgabe |
|---|---|---|
| `aufbau` | `name_links`, `wert_rechts` oder `kompakt` | `name_links` |
| `teil` | `unter_wert`, `unter_name` oder `aus` | `unter_wert` |
| `symbol` | `an` oder `aus` | `an` |

Je Eintrag lässt sich das überschreiben, dazu kommen `name`, `beschriftung`
(das Anlagenteil), `symbol`, `farbe`, `einheit` und `klick`. Ein Eintrag ist
entweder die Entität allein oder ein Satz eigener Angaben:

```yaml
type: custom:heatnexus-schaubild
zeilen:
  aufbau: name_links
  teil: unter_wert
zusatzwerte:
  - sensor.purowin_kesseltemperatur
  - entity: sensor.heizkreis_vorlauftemperatur
    name: Vorlauf oben
    symbol: mdi:radiator
    teil: aus
  - entity: sensor.pv_ertrag_heute
    name: PV heute
    beschriftung: Heizhaus
    symbol: mdi:solar-power
    einheit: false
```

Das Symbol kommt ohne Angabe von HeatNexus: Flamme am Kessel, Heizkörper am
Vorlauf, Tank am Puffer. Fremde Entitäten behalten ihr eigenes.

## Was die Karte zeigt

Dieselbe Zeichnung wie die Oberfläche: Kessel, Puffer, Heizkreise, Warmwasser
und Zirkulation in der Reihenfolge des Wärmeflusses, dazu die Messwerte an
ihren Kästen. Ein Klick auf einen Wert öffnet die Detailansicht der Entität.

Die Zeichnung entsteht aus dem, was die Anlage meldet – es gibt kein festes
Bild und keine Rollenliste, in die eine Anlage passen müsste. Was fehlt,
erscheint nicht.

## Farben

Der Server schickt die Zeichnung **einmal** und dazu je Farbsatz eine Tabelle;
umgefärbt wird im Browser. Ein weiterer Farbsatz kostet dadurch nichts – und
das Umschalten des Erscheinungsbildes wirkt sofort, ohne dass etwas
nachgeladen wird.

## Wenn nichts erscheint

- **„Custom element doesn't exist: heatnexus-schaubild"** – Home Assistant hat
  das Modul noch nicht geladen. Einmal die Seite neu laden. Bleibt es dabei,
  hilft ein Neustart von Home Assistant.
- **„Noch keine Anlage eingelesen."** – Die Erkennung läuft noch. Nach dem
  ersten Einlesen steht das Bild von selbst da.
- **„Diese Anlage gibt es nicht mehr."** – Der Wert unter `anlage` passt zu
  keiner vorhandenen Anlage. Ohne Angabe nimmt die Karte die erste.

Nach einer Aktualisierung von HeatNexus zeigt eine bereits offene Seite
weiterhin die alte Fassung der Karte: Ein Browser nimmt einen Kartentyp je
Seitensitzung nur einmal an, und der Typ heißt in jeder Fassung gleich – er
steht so in den Dashboards der Nutzer. Ein Neuladen mit Strg+Umschalt+R
(macOS: Cmd+Umschalt+R) holt die neue.
