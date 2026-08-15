---
start: true
titel: Windhager-Heizungen in Home Assistant
beschreibung: HeatNexus liest die Anlage lokal aus, ohne Cloud und ohne Konto — mit Oberfläche, Dashboard, Anlagenschaubild und Zeitprogrammen.
---

<div class="held" markdown="0">
  <h1>Deine Windhager-Heizung in Home Assistant</h1>
  <p class="unter">
    HeatNexus spricht direkt mit der Steuerung im Heizraum. Kein Konto,
    keine Cloud, keine Entitäts-IDs von Hand — was die Anlage meldet,
    erscheint; was fehlt, entfällt.
  </p>
  <div class="tasten">
    <a class="taste" href="https://my.home-assistant.io/redirect/hacs_repository/?owner=xIceTea&amp;repository=HeatNexus&amp;category=integration">In HACS öffnen</a>
    <a class="taste leer" href="#installation">Installation</a>
    <a class="taste leer" href="https://github.com/xIceTea/HeatNexus">Quelltext</a>
  </div>
</div>

<figure class="bild" markdown="0">
  <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_animation.gif"
       alt="Anlagenschaubild in Bewegung: der Kessel startet, der Puffer lädt, Heizkreis und Warmwasser werden warm">
  <figcaption>
    Das Anlagenschaubild wird aus den erkannten Anlagenteilen gezeichnet.
    Pumpen drehen sich, solange sie fördern, der Puffer färbt sich nach seinen
    beiden Fühlern, das Glutbett folgt der Kesselleistung.
  </figcaption>
</figure>

## Was HeatNexus mitbringt

<div class="gitter" markdown="0">
  <div class="feld">
    <h3>Alles wird erkannt</h3>
    <p>Kessel, Puffer, Heizkreise, Warmwasser, Zirkulation, Solar und Module — samt Wertebereichen, Einheiten und Auswahllisten aus der Steuerung selbst.</p>
  </div>
  <div class="feld">
    <h3>Eigene Oberfläche</h3>
    <p>Eine Seite in der Seitenleiste: Schaubild, Kennwerte, Heizkreise, Warmwasser, Wartung, Verlauf und Zeitprogramme.</p>
  </div>
  <div class="feld">
    <h3>Dashboard inklusive</h3>
    <p>Baut sich aus dem, was gefunden wurde, und passt sich an, wenn die Anlage sich ändert. Nichts einzutragen.</p>
  </div>
  <div class="feld">
    <h3>Schaubild als Karte</h3>
    <p>Das Anlagenschaubild gibt es als Lovelace-Karte für selbst gebaute Dashboards — mit Werteliste, Farbsätzen und wählbaren Anlagenteilen.</p>
  </div>
  <div class="feld">
    <h3>Zeitprogramme</h3>
    <p>Heizung, Warmwasser und Zirkulation als Wochenraster — lesen und schreiben, so wie die Anlage sie führt.</p>
  </div>
  <div class="feld">
    <h3>Störungen im Klartext</h3>
    <p>Code, Art und Handlungsempfehlung statt einer Zahl. Über 200 Meldungen hinterlegt.</p>
  </div>
  <div class="feld">
    <h3>Automations-Vorlagen</h3>
    <p>Fertige Blueprints für Störungsmeldung, Wartungserinnerung und Vorratswarnung — einzeln abwählbar.</p>
  </div>
  <div class="feld">
    <h3>Lokal, ohne Abhängigkeiten</h3>
    <p>Nur HTTP zur Steuerung im eigenen Netz. Keine Fremdbibliothek, keine Verbindung nach draußen.</p>
  </div>
</div>

<figure class="bild" markdown="0">
  <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_farbsaetze.gif"
       alt="Dieselbe Anlage in fünf Farbsätzen: Dunkel, Hell, Terrakotta, Petrol, Pflaume">
  <figcaption>
    Fünf Farbsätze für Oberfläche und Karte. Sie färben Gehäuse, Rahmen und
    Schrift — Vor- und Rücklauf bleiben überall rot und blau, denn das ist
    eine Auskunft und keine Gestaltung.
  </figcaption>
</figure>

<figure class="bild" markdown="0">
  <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/panel_rundgang.gif"
       alt="Rundgang durch die Oberfläche: Übersicht, Störung, Steuerung, Wartung, Zeitprogramme">
  <figcaption>
    Die eigene Oberfläche, Reiter für Reiter. Ausführlich in der
    <a href="OBERFLAECHE">Anleitung zur Oberfläche</a>.
  </figcaption>
</figure>

## Passt das zu meiner Anlage?

HeatNexus spricht die Netzwerkschnittstelle der **Windhager**-Regelung an, nicht
ein einzelnes Kesselmodell. Erkannt wird, was die Steuerung meldet — die
Baureihe entscheidet nur darüber, welche Zeichnung im Schaubild erscheint.

**Voraussetzung** ist ein **InfoWIN Touch** mit Netzwerkanschluss (oder eine
gleichwertig angebundene Regelung), erreichbar im eigenen Netz, plus das
Service-Passwort. Ob es passt, siehst du in einer halben Minute: `http://<IP der
Anlage>` im Browser öffnen — kommt die Weboberfläche des InfoWIN Touch, ist der
Weg frei.

### Wärmeerzeuger

Diese Baureihen erkennt HeatNexus namentlich und zeichnet sie passend:

| Baureihe | Brennstoff | Stand |
|---|---|---|
| **PuroWIN** | Hackgut, wahlweise Pellets | an der Anlage geprüft |
| **BioWIN**, **BioWIN 2**, **PelletsWIN** | Pellets | an einer fremden Anlage geprüft |
| **LogWIN**, **VarioWIN** | Scheitholz | eingebunden, ungeprüft |
| **AeroWIN** und andere Wärmepumpen | Strom | eingebunden, ungeprüft |
| **DuoWIN**, Gas- und Ölkessel, Brennwerttherme | Gas, Öl | eingebunden, ungeprüft |
| E-Heizung, Automatik- und Zusatzkessel | — | eingebunden, ungeprüft |

### Module und Kreise

| Anlagenteil | Stand |
|---|---|
| **UML** / **UMLZ** Heizkreismodul | an der Anlage geprüft |
| **B-PLMi** Pufferlademodul | an der Anlage geprüft |
| **ZSP** Pumpen- und Relaismodul | an der Anlage geprüft |
| **Infinity PLUS** Heizkreis und Warmwasser | eingebunden, ungeprüft |
| Solar, Kaskade, Umschaltung, weitere Puffer | eingebunden, ungeprüft |

„Eingebunden" heißt: Die Funktion steht mit Namen, Einheiten und Auswahlwerten
in der mitgelieferten Datenbank und wird erkannt — es stand nur noch keine
solche Anlage zum Nachmessen bereit. „An einer fremden Anlage geprüft" heißt:
Jemand hat einen Abzug beigesteuert, das Auslesen ist daran belegt, das
Bedienen noch nicht.

Was hier nicht steht, fällt trotzdem nicht durch: Die allgemeine Erkennung
nimmt jeden Datenpunkt mit, den die Steuerung führt. Welcher Funktionstyp was
ist, steht vollständig unter [Datenpunkte](DATAPOINTS).

<div class="hinweis" markdown="1">
Unsicher, ob deine Anlage mitspielt? Leg in den
[Diskussionen](https://github.com/xIceTea/HeatNexus/discussions) einen Beitrag
an und schreib dazu, welches Gerät du hast. Es gibt ein Sondenwerkzeug, das
deine Anlage ausliest, ohne etwas zu verändern — eine einzelne Python-Datei,
die nichts an der Anlage verändert und im Betrieb nicht mitläuft.
</div>

## Installation

<ol class="schritte" markdown="0">
  <li>
    <strong>HACS öffnen</strong> und HeatNexus als eigenes Repository hinzufügen
    (Kategorie <em>Integration</em>), oder gleich über den Knopf oben.
  </li>
  <li>
    <strong>Herunterladen</strong> und Home Assistant neu starten.
  </li>
  <li>
    <strong>Einrichten</strong> unter <em>Einstellungen → Geräte &amp; Dienste →
    Integration hinzufügen → HeatNexus</em>. Gebraucht werden die IP der
    Steuerung und das Service-Passwort; der Benutzer heißt immer <code>USER</code>.
  </li>
  <li>
    <strong>Warten</strong>: Der erste Durchlauf liest die ganze Anlage ein.
    Danach stehen Geräte, Entitäten, Oberfläche und Dashboard bereit.
  </li>
</ol>

Ohne HACS geht es auch: Ordner `custom_components/heatnexus/` aus dem
[Release](https://github.com/xIceTea/HeatNexus/releases/latest) in den
Konfigurationsordner von Home Assistant kopieren und neu starten.

## Weiterlesen

- [Die eigene Oberfläche](OBERFLAECHE) — jeder Reiter, was er zeigt und was sich bedienen lässt
- [Das Anlagenschaubild als Karte](KARTE) — Einrichtung und alle Einstellungen
- [Datenpunkte](DATAPOINTS) — welche Werte es je Anlagenteil gibt
- [Aufzählungen](ENUMS) — was hinter den Zustandstexten steckt
- [Aufbau](ARCHITECTURE) — wie die Integration innen arbeitet
- [Geräteschnittstelle](API) — die HTTP-Schnittstelle der Steuerung

Fragen, Wünsche und Fehlermeldungen gehören in die
[Diskussionen](https://github.com/xIceTea/HeatNexus/discussions) oder die
[Issues](https://github.com/xIceTea/HeatNexus/issues).
