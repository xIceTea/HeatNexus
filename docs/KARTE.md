# Anlagenschaubild als Karte

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
| `liste` | `rechts` oder `unten` – wo die Werteliste steht | `rechts` |
| `zusatzwerte` | Entitäten für die Werteliste neben dem Bild | leer |
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
