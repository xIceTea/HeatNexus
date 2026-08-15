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
| `anlage` | Kennung oder Name der Anlage | die erste gefundene |
| `farbsatz` | `auto`, `dunkel`, `hell`, `terrakotta`, `petrol`, `pflaume` | `auto` |
| `animation` | Pumpen und Leitungen bewegen sich | `true` |

`auto` folgt dem Erscheinungsbild von Home Assistant.

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

Nach einer Aktualisierung von HeatNexus wird das Modul unter einem neuen Pfad
ausgeliefert; ein gewöhnliches Neuladen genügt, ein harter Neustart des
Browsers ist nicht nötig.
