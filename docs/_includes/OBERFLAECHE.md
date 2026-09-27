# Die Oberfläche

HeatNexus bringt eine eigene Seite in der Seitenleiste von Home Assistant mit.
Hier steht, was darauf zu sehen ist — damit man es beurteilen kann, ohne die
Integration erst installieren zu müssen.

<p align="center">
  <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/panel_rundgang.gif" alt="Rundgang durch die Oberfläche: Übersicht, Störung, Steuerung, Wartung, Zeitprogramme" width="900">
</p>

<p align="center">
  <em>Alle Werte im Bild sind erfunden, der Aufbau ist echt: Aufgenommen wird
  die ausgelieferte Oberfläche selbst.</em>
</p>

## Was der Rundgang zeigt

**Übersicht.** Oben die Heizungsübersicht: je Anlagenteil ein Leitwert, so wie
das Bediengerät der Anlage ihn zeigt — am Kessel die Kesseltemperatur, am
Puffer die obere, am Heizkreis die Raumtemperatur. Darunter das
Anlagenschaubild, dann der Systemstatus mit Betriebszustand,
Außentemperatur, Kesselleistung, Brennstoff, Vorratsbehälter und den
Restlaufzeiten.

**Schaubild in Bewegung.** Die Pumpen drehen sich, solange sie fördern, und
die Bänder auf Vor- und Rücklauf zeigen die Richtung. Im Rundgang läuft neben
Kessel, Puffer und Heizkreis auch die Zirkulation — an den senkrechten
Stichleitungen sieht man, wohin die Wärme gerade geht.

<a id="stoerung"></a>

**Störung.** Liegt eine Meldung an, wechselt der Balken oben von „Anlage in
Ordnung" auf „Störung anliegend", und die Störungskarte nennt den Klartext des
Herstellers samt Abhilfe. Verschwindet die Meldung an der Anlage, verschwindet
auch die Anzeige — sie wird nicht quittiert, sondern gelesen.

**Steuerung.** Was man an der Anlage wirklich verstellt: Sollwert des
Heizkreises, Eco und Comfort als befristete Übersteuerung, die Betriebswahl,
Warmwasser mit Sollwert und Einmalladung, dazu die Tasten am Kessel. Wo ein
Fehlgriff Arbeit macht oder Brennstoff kostet, kommt vorher eine Rückfrage.

Im Bild läuft dabei beides mit: Am Heizkreis steht „Vorgabe noch bis 10:09"
samt „abbrechen" — ein von Hand verschobener Sollwert überstimmt das
Zeitprogramm nur auf Zeit. Und die Warmwasserkarte zeigt eine **laufende
Einmalladung**: Die Betriebsart meldet „Warmwasser Einmalladung", die Taste
heißt so lange „Warmwasser laden abbrechen". Erkannt wird das an der
Betriebsart, nicht am Auslöser — der fällt zurück, sobald die Anlage den
Auftrag angenommen hat.

**Wartung.** Restlaufzeiten bis Ascheentleerung, Hauptreinigung und Wartung,
der Brennstoff, die Zählerstände.

<a id="zeitprogramme"></a>

**Zeitprogramme.** Je Programm ein Wochenraster: Blöcke wie „Mo–Fr" und
„Sa, So", darin die Schaltzeiten als Balken, darunter als Text. Bearbeitet wird
in Blöcken und gespeichert als ganzes Programm — so, wie die Anlage es führt.
„Aktivieren“ stellt die zugehörige Auswahl nach einer Rückfrage auf dieses Programm.
Beim Bearbeiten lässt sich eine eigene Bezeichnung wie „Übergangszeit“ vergeben.
Sie steht hinter dem Namen des Programms. In der Leseansicht ist die Zeile
hervorgehoben, die gerade gilt.

<a id="automatik"></a>

## Automatik

Der Außenfühler der Anlage hängt meist auf der Nordseite. An einem sonnigen
Tag in der Übergangszeit misst er wenig, während die Räume nach Süden warm
werden – und der Heizkreis heizt weiter. Die Automatik nimmt dafür
Temperaturfühler aus Home Assistant, die Wetterprognose und auf Wunsch eine
PV-Prognose dazu. Sie regelt nicht selbst, sondern verschiebt, was die Anlage
ohnehin tut:

- **Sonnentag.** Zur Entscheidungszeit prüft sie die Sonnenquote des Tages. Ist
  sie hoch genug und der Raum warm genug, senkt sie den Sollwert befristet ab,
  auf demselben Weg wie Eco in der Steuerung. Die Absenkung endet an der Anlage
  von selbst, spätestens zwei Stunden vor Sonnenuntergang. Fällt der Raum unter
  die Rückkehrschwelle, beendet die Automatik sie vorher.
- **Übergangszeit.** Liegt die gedämpfte Außentemperatur über der Heizgrenze
  oder sagt die Prognose für heute und morgen mildes Wetter voraus, schaltet
  sie den Heizkreis auf nur Warmwasser. Zurück geht es, wenn es kühler wird
  und der Raum auskühlt. Eine Hysterese und eine Mindestdauer verhindern
  häufiges Umschalten.
- **Abwesenheit und Fenster** sind freiwillig. Sind alle Personen weg, senkt
  sie ab. Ein offenes Fenster setzt die Entscheidungen aus.

Eingerichtet wird im Reiter **Automatik** je Heizkreis: Heizflächen, Räume,
Wetter und optional PV-Prognose, Personen und Fenster. Die Art der Heizflächen
wählt eines von drei Profilen – Schnell für Heizkörper, Standard für gemischt,
Träge für Fußboden- und Wandheizung. Unter „Erweitert“ lässt sich jeder Wert
einzeln ändern.

Die Automatik beginnt im **Beobachtungsmodus**. Dann schreibt sie nichts an
die Steuerung, und das Protokoll zeigt, was sie getan hätte. Erst „Schalten“
macht sie wirksam. Weitere Regeln:

- Eine Bedienung von Hand hat Vorrang und pausiert die Automatik bis 05:00 am
  nächsten Morgen.
- Höchstens vier Eingriffe am Tag gehen an die Steuerung; die Zahl lässt sich
  einstellen.
- Unter 16 °C im Raum nimmt sie jeden eigenen Eingriff sofort zurück. Unter
  3 °C außen schaltet sie „nur Warmwasser“ sofort zurück. Den Frostschutz der
  Anlage ersetzt sie nicht.
- Wird die Automatik ausgeschaltet, nimmt sie ihre eigenen Eingriffe zurück.

### Prognose an den Standort anpassen

Die Wetterprognose gilt für den Ort, nicht für den Fühler an der Nordwand. Die
Automatik vergleicht deshalb jede Stunde, was die Prognose vorhergesagt hat,
mit dem Messwert des Außenfühlers. Aus der Abweichung je Tageszeit wird ein
Versatz, zum Beispiel „Außen angepasst −1,4 K“. Mit einem Zähler für den
tatsächlichen PV-Ertrag vergleicht sie ebenso die PV-Prognose mit dem Ertrag
und bildet einen Faktor, etwa „Sonne angepasst −12 %“. Das Verfahren entspricht
der Prognoseanpassung von evcc.

- Die Korrektur wirkt nach sieben Tagen mit Daten. Unter „Erweitert“ lässt sich
  das Lernfenster auf 3, 7 oder 14 Tage stellen; bei 3 Tagen wirkt sie nach
  drei Tagen.
- Der Schalter **Prognose anpassen** schaltet die Korrektur für Anzeige und
  Entscheidung ab. Gelernt wird weiter.
- Als PV-Prognose dient immer der Ertrag des ganzen Tages. Ein Wert für den
  Rest des Tages schrumpft im Lauf des Tages und wird nicht angeboten.

### Heute, morgen, übermorgen

Das Stundenraster zeigt je Stunde von 06 bis 22 Uhr das Wetter, die angepasste
Außentemperatur, was die Automatik in dieser Stunde tut, und den Raum gegen das
Soll. Darunter zeigt ein Diagramm die Sonne, die Außentemperatur gemessen und
laut Prognose, die gedämpfte Außentemperatur und die Heizgrenze. Die schon
vergangenen Stunden von heute liest die Automatik beim Start aus der
Aufzeichnung von Home Assistant nach.

Für morgen und übermorgen rechnet sie mit derselben Regel vor, was sie
voraussichtlich tun wird. Dabei nimmt sie an, dass der Raum am Sollwert liegt.

### Raumfühler

Die Auswahl zeigt zu jedem Fühler den aktuellen Wert. Ein ausgefallener Fühler
meldet in Home Assistant oft weiter seinen letzten Wert. Zeigt ein Raumfühler
über Stunden denselben Wert, gilt er als veraltet und zählt nicht zum Raumwert;
die Raum-Kachel nennt ihn dann ausdrücklich.

Je Heizkreis entstehen drei Entitäten: der Schalter **Automatik**, die Auswahl
**Automatik-Modus** und der Sensor **Automatik-Zustand** mit der Begründung als
Attribut. Damit lässt sie sich auch in Automationen und Dashboards verwenden.

## Eigene Werte über Labels

Auch Werte, die nicht von der Heizung stammen, lassen sich anzeigen. Vergib der
Entität in Home Assistant ein Label (Einstellungen → Bereiche, Labels & Zonen)
und wähle dieses Label in den Einstellungen der Integration unter „Labels in
der Oberfläche zeigen". Jedes gewählte Label wird zu einer eigenen Karte in der
Übersicht. Sie lässt sich verschieben, verbreitern und ausblenden wie jede
andere Karte.

Was jemand in einer Karte sieht, hängt an seinen Rechten in Home Assistant:
Werte, die er nicht lesen darf, stehen nicht darin.

Der Reiter **Verlauf** fehlt im Rundgang. Er benutzt die Verlaufskarte von
Home Assistant, und die zeichnet nur mit einer laufenden Anlage dahinter. Eine
leere Karte im Bild würde also etwas Falsches zeigen.

## Wie das Bild entsteht

Es ist **kein Nachbau**. Aufgenommen wird `frontend/heatnexus-panel.js` selbst,
mit `frontend/stil.js`, in einem kopflosen Browser:

- Die Aufteilung rechnet `panel.panel_daten` über eine Beispielanlage
  (`tools/beispielanlage.py`) — dieselbe, aus der auch das Anlagenschaubild im
  README entsteht.
- Die Zustandstabelle von Home Assistant wird nachgebildet. Je Auftritt lassen
  sich einzelne Zustände überschreiben; so entsteht die Störung.
- Die Oberfläche hängt an genau einem fremden Element, `ha-icon`. Es wird mit
  den Symbolpfaden bedient, die das installierte Home-Assistant-Frontend
  mitbringt — die Symbole sind also die echten, nicht nachgezeichnet.

```bash
python tools/build_panel_rundgang.py
```

Damit kann das Bild nicht veralten wie ein von Hand gemachter Bildschirmabzug:
Ändert sich die Oberfläche, ändert sie sich beim nächsten Lauf mit.

**Erfundene Werte, echte Struktur.** Kein Datenpunkt im Bild stammt von einer
Anlage; Namen und Adressen sind die der Geräte-Datenbank, die Zahlen sind
gewählt.
