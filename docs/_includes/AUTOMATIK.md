# Automatik

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
- **Übergangszeit.** Sagt die Prognose für heute und morgen im Mittel
  mindestens die Heizgrenze voraus, oder liegt die gedämpfte Außentemperatur
  um die Hysterese darüber, schaltet sie den Heizkreis auf nur Warmwasser.
  Voraussetzung ist eine milde Nacht: Weder die aktuelle Außentemperatur noch
  die Stundenprognose bis 9 Uhr am nächsten Morgen darf unter die
  Einschaltschwelle fallen. Sonst bräuchte der Heizkreis am Morgen wieder Wärme.
  Zurück geht es, wenn es kühler wird und die Räume auskühlen. Eine Hysterese
  und eine Mindestdauer verhindern häufiges Umschalten. Liegt die aktuelle
  Außentemperatur unter der Einschaltschwelle der Steuerung und fordern die
  Thermostate Wärme an, geht der Heizkreis sofort zurück ins Programm.
- **Heizpause.** An milden Tagen schreibt die Automatik einen befristeten
  Raumsollwert knapp unter die Außentemperatur der Steuerung. Die Steuerung
  schaltet den Heizkreis damit ab und nimmt ihn bei Kälte wieder in Betrieb.
  Auslöser sind eine gedämpfte Außentemperatur über der Heizgrenze, ein
  Tagesmittel ab der Heizgrenze, starke Sonne oder eine laufende
  Vorrangquelle. Die Vorgabe läuft ab. Die Automatik erneuert sie nur,
  solange die Pause passt.
- **Abwesenheit und Fenster** sind freiwillig. Sind alle Personen weg, senkt
  sie ab. Ein offenes Fenster setzt die Entscheidungen aus.

## Die Heizgrenze der Steuerung

Die Automatik führt keine eigene Heizgrenze. Sie liest `TA Heizbetrieb` der
Steuerung und richtet sich danach, an jedem Heizkreis und mit jedem Kessel.
Die Steuerung selbst schaltet nach der aktuellen Außentemperatur; die
Automatik schaltet nach Prognose und gedämpfter Außentemperatur und ist damit
vorausschauend. Liefert ein Heizkreis die Heizgrenze nicht, rechnet sie mit
17 °C und sagt das in der Außen-Kachel.

Unter den Kacheln stehen die **Heizgrenzen der Steuerung** für Heiz- und
Absenkbetrieb. Sie lassen sich dort ändern; das ist eine Einstellung von Hand,
kein Eingriff der Automatik, und zählt nicht zum Budget.

## Einrichten

Eingerichtet wird im Reiter **Automatik** je Heizkreis: Heizflächen, Räume,
Wetter und optional PV-Prognose, Personen und Fenster. Die Art der Heizflächen
wählt eines von drei Profilen – Schnell für Heizkörper, Standard für gemischt,
Träge für Fußboden- und Wandheizung. Die **Ausrichtung** verschiebt diese Werte
und legt fest, wie weit die Automatik von der Heizgrenze der Steuerung abweicht:

- **Eco** greift früher und kräftiger ein: 2 K unter der Heizgrenze der
  Steuerung, Sonnentag ab
  15 % weniger Sonnenquote, 0,5 K mehr Absenkung, „sehr sonnig“ schon ab 0,5 K
  über Ziel, Räume nach einer Stunde ohne Wärmeanforderung ruhig.
- **Ausgewogen** nimmt die Werte der Heizflächen unverändert.
- **Komfort** greift später und sanfter ein: 1 K über der Heizgrenze der
  Steuerung, Sonnentag
  erst ab 10 % mehr Sonnenquote, 0,5 K weniger Absenkung, kein „sehr sonnig“,
  Räume erst nach drei Stunden ruhig.

Unter „Erweitert“ lässt sich jeder Wert einzeln ändern; eigene Werte gehen der
Ausrichtung vor.

## Modus und Grenzen

Der Modus bestimmt, was die Automatik mit ihrer Entscheidung tut:

- **Beobachten** ist die Voreinstellung. Die Automatik schreibt nichts an die
  Steuerung, und das Protokoll zeigt, was sie getan hätte.
- Im Modus **Manuell mit Empfehlung** schreibt die Automatik nur, was nicht
  weniger heizt. Eingriffe, die weniger heizen, schlägt sie vor; das gilt auch
  für das Verlängern eines Sonnentags oder einer Heizpause. Die Empfehlung
  erscheint im Reiter Automatik und als Sensor, und erst „Übernehmen“ führt sie
  aus. „Verwerfen“ lehnt sie ab; derselbe Vorschlag kommt am Tag nicht wieder.
  Die Rückkehr ins Programm und Eingriffe zur Sicherheit schreibt die Automatik
  ohne Rückfrage. Der Blueprint „Empfehlung der Automatik melden“ schickt die
  Empfehlung an ein Mobilgerät, mit den Aktionen „Übernehmen“ und „Verwerfen“.
  Solange eine Empfehlung offen ist, trägt der Reiter Automatik einen Punkt,
  und in der Seitenleiste von Home Assistant steht eine Benachrichtigung. Die
  Benachrichtigung lässt sich in den Einstellungen unter „Manuell mit
  Empfehlung“ abschalten.
- **Automatisch** schreibt jede Entscheidung selbst.

Ein Wechsel weg von „Automatisch“ nimmt laufende Eingriffe der Automatik
zurück, und die Regel rechnet sofort neu. Im Modus „Manuell mit Empfehlung“
erscheint dann gleich die passende Empfehlung, im Beobachten der vorgemerkte
Eingriff.

Weitere Regeln:

- Eine Bedienung von Hand hat Vorrang und pausiert die Automatik bis 05:00 am
  nächsten Morgen.
- Fährt die Steuerung ein eigenes Programm – Urlaub, Estrich, Hand-, Test- oder
  Kaminkehrerbetrieb –, greift die Automatik nicht ein.
- Höchstens vier Eingriffe am Tag gehen an die Steuerung; die Zahl lässt sich
  einstellen.
- Unter 16 °C im Raum nimmt sie jeden eigenen Eingriff sofort zurück. Unter
  3 °C außen schaltet sie „nur Warmwasser“ sofort zurück. Den Frostschutz der
  Anlage ersetzt sie nicht.
- Wird die Automatik ausgeschaltet, nimmt sie ihre eigenen Eingriffe zurück.

## Prognose an den Standort anpassen

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

## Heute, morgen, übermorgen

Das Stundenraster zeigt je Stunde von 06 bis 22 Uhr das Wetter, die angepasste
Außentemperatur, was die Automatik in dieser Stunde tut, und den Raum gegen das
Soll. Darunter zeigt ein Diagramm die Sonne, die Außentemperatur gemessen und
laut Prognose, die gedämpfte Außentemperatur und die Heizgrenze. Die schon
vergangenen Stunden von heute liest die Automatik beim Start aus der
Aufzeichnung von Home Assistant nach.

Für morgen und übermorgen rechnet sie mit derselben Regel vor, was sie
voraussichtlich tun wird. Dabei nimmt sie an, dass die Räume ihr Ziel halten.

## Räume und ihr Ziel

Ohne Raumfühler am Heizkreis regelt die Steuerung nur nach der
Außentemperatur. Der Raumsollwert verschiebt dann nur die Heizkurve und sagt
nichts darüber, wie warm ein Raum sein soll. Die Automatik vergleicht deshalb
jeden Raum mit seinem eigenen Ziel:

- **Thermostate** wie tado lassen sich direkt als Raum wählen. Sie liefern Ist,
  Ziel und ob sie gerade heizen. Senkt ein Thermostat nachts ab, sinkt das Ziel
  mit.
- Ein ausgeschaltetes Thermostat, etwa beim Lüften oder im Sommer, zählt als
  Raum ohne Bedarf: Es fordert keine Wärme an und geht nicht in die Abweichung
  ein. Sein Ist-Wert zählt weiter für die Sicherheit unter 16 °C. Ein nicht
  erreichbares Thermostat zählt gar nicht.
- Für reine **Temperaturfühler** gilt die Wunschtemperatur aus der Einrichtung.
  Bleibt das Feld leer, gilt der Raumsollwert des Heizkreises. Das passt nur,
  wenn der Heizkreis selbst einen Raumfühler hat.
- **Nur Warmwasser** setzt mit Thermostaten zusätzlich voraus, dass seit zwei
  Stunden kein Raum Wärme angefordert hat.
- Mit Thermostaten ist der **Sonnentag** ab Werk aus. Die Thermostate öffnen bei
  abgesenktem Sollwert nur weiter. Unter „Erweitert“ lässt er sich einschalten.

Die Raum-Kachel zeigt dann die Abweichung der Räume von ihrem Ziel, im Mittel
oder für den kältesten Raum.

## Wärmequellen mit Vorrang

In der Einrichtung lassen sich Wärmequellen von HeatNexus wählen, deren Wärme
Vorrang vor dem Kessel hat, etwa eine Solaranlage oder ein Heizstab am
PV-Überschuss. Ob eine Quelle Vorrang bekommt, entscheidet jede Anlage selbst;
ab Werk ist keine gewählt.

- Liefert eine gewählte Quelle zur Entscheidungszeit, gilt der Tag als
  Sonnentag, auch wenn die Prognose vorsichtiger ist.
- Beginnt eine gewählte Quelle zu liefern, entscheidet die Automatik sofort
  neu, einmal am Tag, statt bis zur nächsten Entscheidungszeit zu warten.
- Hat vier Stunden nach Beginn einer Absenkung keine gewählte Quelle Wärme
  geliefert, beendet die Automatik die Absenkung.
- Die Sonnen-Kachel nennt, ob eine Quelle liefert oder wie lange heute schon.
  Im Stundenraster tragen diese Stunden oben einen Strich.

Die Auswahl zeigt zu jedem Fühler den aktuellen Wert. Ein ausgefallener Fühler
meldet in Home Assistant oft weiter seinen letzten Wert. Zeigt ein Raumfühler
über Stunden denselben Wert, gilt er als veraltet und zählt nicht zum Raumwert;
die Raum-Kachel nennt ihn dann ausdrücklich.

## Geräte und Sensoren

Mit der ersten Automatik entsteht das Gerät **HeatNexus Automatik**. Es
bündelt alle Automatiken des Eintrags:

- **Status**: aus, beobachten, aktiv, Eingriff aktiv, pausiert oder Störung,
  der schwerste Zustand aller Heizkreise; je Heizkreis als Attribut,
- **Automatiken**, **Eingriffe heute**, **Letzter Eingriff** mit Grund und
  Heizkreis, **Nächste Entscheidung**,
- **Störung** und **Wetterprognose** (an, solange jede Automatik eine
  Prognose hat, die jünger als sechs Stunden ist).

Darunter steht je Heizkreis das Gerät **Automatik <Heizkreis>**. Es führt:

- den Schalter **Automatik** und die Auswahlen **Automatik-Modus** und
  **Automatik-Ausrichtung**,
- den Sensor **Automatik-Zustand** mit der Begründung als Attribut,
- den Sensor **Empfehlung** und die Tasten **Empfehlung übernehmen** und
  **Empfehlung verwerfen**,
- die Werte, mit denen sie rechnet: **Gedämpfte Außentemperatur**,
  **Heizgrenze** (die der Steuerung samt Ausrichtung), **Räume zum Ziel**,
  **Sonnenquote heute**,
- **Eingriffe heute** mit dem Budget als Attribut, **Letzter Eingriff** mit
  dem Grund, **Nächste Entscheidung**,
- **Störung**: an, solange die Steuerung Eingriffe ablehnt oder die
  Sicherheitsregel greift.

Damit lässt sich die Automatik auch in Automationen und Dashboards verwenden.
Der Diagnose-Export der Integration enthält je Automatik Einstellungen,
wirksame Werte, die letzte Lage, das Protokoll und den Verlauf des Tages.
