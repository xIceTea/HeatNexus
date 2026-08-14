# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Vorabversionen tragen ein Suffix (`0.1.0-beta.1`) und erscheinen in HACS nur,
wenn dort Vorabversionen zugelassen sind.

## [1.8.1] - 2026-08-14

### Geändert

- Bezeichnungen bleiben deutsch, bis eine andere Sprache gewählt wird.
- Kürzere Erklärungen in den allgemeinen Einstellungen.

### Behoben

- Eine abgewählte Systemuhr ließ ihre Entitäten als abgeschaltete Zeilen zurück.

## [1.8.0] - 2026-08-14

Bezeichnungen in der Sprache von Home Assistant und eine Erkennung, die auch
Anlagenteile findet, die sich nicht selbst ankündigen. Die Abschnitte der fünf
Vorabversionen darunter führen jede Änderung einzeln auf; hier stehen die
Neuerungen gegenüber 1.7.0.

### Neu

- Bezeichnungen folgen der Sprache von Home Assistant: Deutsch, Englisch, Französisch, Italienisch.
- Die Sprache der Bezeichnungen lässt sich in den Einstellungen festlegen.
- Datenpunkte ohne Namen in der Datenbank heißen jetzt wie an der Anlage.
- Anlagenteile, die sich nicht selbst ankündigen, werden trotzdem erkannt.

### Geändert

- Ein Sprachwechsel ändert auch die Zustandstexte von Aufzählungen.
- Nach einem Sprachwechsel meldet HeatNexus den nötigen Neustart.

### Behoben

- Anlagen mit vielen Datenpunkten hörten dauerhaft auf, Werte zu lesen ([#2](https://github.com/xIceTea/HeatNexus/issues/2)).
- Abgelehnte Datenpunkte standen nach einem Neustart wieder im Abruf ([#2](https://github.com/xIceTea/HeatNexus/issues/2)).
- Der Brennstoffverbrauch in Tonnen löste beim Start eine Warnung aus ([#3](https://github.com/xIceTea/HeatNexus/issues/3)).
- Werte in Litern je Stunde lösten dieselbe Warnung aus.
- Beim Automatik-/Zusatzkessel fehlten Betriebswahl und Alarmcode.
- Bei nur einer Anlage fehlte der Zugang zu den allgemeinen Einstellungen.
- Die Anordnung der Karten im Reiter „Hilfe" wurde nicht gespeichert.

## [1.8.0-beta.5] - 2026-08-13

### Behoben

- Der Brennstoffverbrauch in Tonnen löste beim Start eine Warnung aus ([#3](https://github.com/xIceTea/HeatNexus/issues/3)).
- Werte in Litern je Stunde lösten dieselbe Warnung aus.

### Geändert

- Die Protokollzeile zum Zeitfenster sagt jetzt, dass der Rest zuerst nachgeholt wird.

## [1.8.0-beta.4] - 2026-08-13

### Behoben

- Abgelehnte Datenpunkte standen nach einem Neustart wieder im Abruf ([#2](https://github.com/xIceTea/HeatNexus/issues/2)).

## [1.8.0-beta.3] - 2026-08-13

### Behoben

- Anlagen mit vielen Datenpunkten hörten dauerhaft auf, Werte zu lesen ([#2](https://github.com/xIceTea/HeatNexus/issues/2)).
- Datenpunkte, die die Anlage ablehnt, wurden in jedem Durchlauf erneut abgefragt ([#2](https://github.com/xIceTea/HeatNexus/issues/2)).

## [1.8.0-beta.2] - 2026-08-13

### Neu

- Datenpunkte ohne Namen in der Datenbank heißen jetzt wie an der Anlage.
- Bezeichnungen folgen der Sprache von Home Assistant: Deutsch, Englisch, Französisch, Italienisch.
- Die Sprache der Bezeichnungen lässt sich in den Einstellungen festlegen.

### Geändert

- Ein Sprachwechsel ändert auch die Zustandstexte von Aufzählungen.
- Nach einem Sprachwechsel meldet HeatNexus den nötigen Neustart.

### Behoben

- Beim Automatik-/Zusatzkessel fehlten Betriebswahl und Alarmcode.
- Bei nur einer Anlage fehlte der Zugang zu den allgemeinen Einstellungen.

## [1.8.0-beta.1] - 2026-08-13

### Neu

- Anlagenteile, die sich nicht selbst ankündigen, werden trotzdem erkannt.

### Behoben

- Die Anordnung der Karten im Reiter „Hilfe" wurde nicht gespeichert.

## [1.7.0] - 2026-08-13

Ein eigener Hilfe-Reiter, Geräteseiten, die sagen womit man es zu tun hat, und
eine Erkennung, die auch Datenpunkte außerhalb der Menü-Ebenen findet. Die
Abschnitte der beiden Vorabversionen darunter führen jede Änderung einzeln
auf; hier stehen die Neuerungen gegenüber 1.6.0.

### Neu

- Neuer Reiter „Hilfe" im Panel, durchsuchbar.
- Datenpunkte außerhalb der Menü-Ebenen werden erkannt.
- Systemuhr und Systemdatum lassen sich per Haken anlegen.
- Die Steuerung zeigt Modell und Firmwarestand.
- Unbekannte Anlagenteile zeigen die Bezeichnung ab Werk als Modell.
- Anlagenteile ohne bekanntes Muster bekommen ihren Leitwert in der Übersicht.
- Zählerstände ohne Einheit bekommen einen Langzeitverlauf.

### Geändert

- Zeitfelder außer Systemuhr und Systemdatum sind nicht mehr vorab deaktiviert.
- Systemuhr und Systemdatum entfallen ab Werk — weniger Abfragen und Verlaufsdaten.
- Eine nicht erreichbare Anlage wird nur noch einmal protokolliert.

### Behoben

- Zeitprogramme sind gleich nach der Einrichtung verfügbar.
- 29 fehlende Datenpunktnamen ergänzt.
- Seriennummer und Softwarestand standen nur an Heizkreisen.
- Der Dienst „Behaglichkeitskorrektur" war englisch beschriftet.

## [1.7.0-beta.2] - 2026-08-13

### Neu

- Neuer Reiter „Hilfe" im Panel, durchsuchbar.

### Behoben

- 29 fehlende Datenpunktnamen ergänzt.

## [1.7.0-beta.1] - 2026-08-12

### Neu

- Datenpunkte außerhalb der Menü-Ebenen werden erkannt.
- Systemuhr und Systemdatum lassen sich per Haken anlegen.

### Geändert

- Nur noch Systemuhr und Systemdatum sind vorab deaktiviert.

### Behoben

- Zeitprogramme sind gleich nach der Einrichtung verfügbar.

## [1.6.0] - 2026-08-06

Bedienen, das ankommt: Eco und Comfort wirken jetzt auch aus dem Warmwasser-
und Standby-Betrieb heraus, die Warmwasserladung lässt sich wieder abbrechen,
und das Schaubild zeigt, wohin die Wärme gerade fließt. Dazu der Wechsel auf
die GPL-3.0.

### Neu

- **Ein übergangener Abbruch wird nachgesetzt.** Ging der Befehl an der Anlage
  vorbei, lief die Warmwasserladung weiter und man musste ein zweites Mal
  drücken. Jetzt wird nachgesehen und, falls nötig, noch einmal geschickt —
  nur die Freigabe, höchstens zweimal.

### Behoben

- **Eco und Comfort aus dem Warmwasser- oder Standby-Betrieb heraus.** Die
  Vorgabe wurde übertragen, eine Sekunde später aber wieder zurückgenommen: Die
  Anzeige sprang auf den alten Wert, und an der Anlage änderte sich nichts.
- Die senkrechte Leitung am Puffer bewegt sich jetzt auch beim **Entladen**.
  Sie hing allein an der Ladepumpe, und die dreht nur beim Laden — der Strang
  stand still, während daneben „entlädt" stand und die Wärme nach oben abfloss.
- Der senkrechte Strang am Kessel bewegt sich mit, solange der Puffer geladen
  wird. Bisher stand er still, während daneben alles strömte.
- Die Beschriftung „Warmwasser laden abbrechen" war auf dunklem Grund kaum zu
  lesen. Sie hebt sich jetzt ab und zeigt in eigener Farbe, dass ein Druck den
  laufenden Auftrag beendet.
- **Warmwasserladung abbrechen wirkt wieder.** Hinter der zurückgenommenen
  Freigabe ging noch eine Betriebswahl an die Anlage, und die Ladung lief
  weiter. Zurückgestellt wird die Betriebswahl jetzt nur noch, wenn die Ladung
  aus dem Standby heraus gestartet wurde und dafür umgeschaltet werden musste.
- Nach einer Bedienung wurde nur einmal nachgelesen. Betriebsart und Pumpe
  ziehen aber nicht gleichzeitig nach — im Schaubild lief die Ladepumpe
  dadurch bis zum nächsten Durchlauf weiter. Jetzt wird mehrfach nachgefasst.
- Der Wartezeiger auf einer gedrückten Taste sah nach Hängen aus. Dass etwas
  läuft, sagt die Zeile darunter.
- Nach einem Druck blieb eine Taste bis zu dreiviertel Minuten gesperrt, wenn
  die Anlage den Auftrag nicht übernahm — der Mauszeiger stand auf
  „beschäftigt", weitere Drucke fielen wortlos weg. Die Sperre dauert jetzt nur
  noch, solange der Befehl unterwegs ist.

### Geändert

- **HeatNexus steht jetzt unter der GNU General Public License v3.0.** Wer die
  Integration abwandelt und weitergibt, gibt sie unter derselben Lizenz weiter —
  mit Quelltext. Bis einschließlich 1.5.0 galt die Apache License 2.0; ältere
  Fassungen bleiben unter den Bedingungen, unter denen sie erschienen sind. Für
  die Nutzung ändert sich nichts.

## [1.5.0] - 2026-08-06

Zeitprogramme lassen sich jetzt bedienen statt nur ablesen, die Anlage meldet
sich, wenn etwas nicht stimmt, und der Abruf holt ganze Menü-Fenster statt
einzelner Datenpunkte. Die Abschnitte der zehn Vorabversionen darunter führen
jede Änderung einzeln auf; hier stehen die Neuerungen gegenüber 1.4.2.

> **Diese Fassung setzt Home Assistant 2025.6 oder neuer voraus.** Die
> Anmeldung an der Anlage übernimmt Home Assistants eigene HTTP-Bibliothek;
> die dafür nötige Fassung liegt ab 2025.6 bei.

### Neu

- **Zeitprogramme bedienen.** Eigener Reiter, Wochenraster, Editor. Das
  Programm öffnet sich zum Lesen — die Zeiten stehen als *von – bis* wie im
  Bediengerät —, und *Bearbeiten* holt die Startpunkte.
- **Meldungsliste je Anlage** und eine Geräteseite, die sagt, was das Gerät ist.
- **Automations-Vorlage Legionellenschutz nachbilden** für Regler ohne eigene
  Legionellenschutzfunktion.
- Einschalthysterese und Ladetemperatur der Warmwasserladung sind in der
  Steuerung einstellbar.
- Der Puffer zeigt seine Schichtung, das Schaubild folgt dem Erscheinungsbild.
- Probleme melden sich in den Reparaturen, statt still zu bleiben.
- `heatnexus.rediscover` sagt, was dabei herausgekommen ist.

### Geändert

- Der Abruf holt Menü-Fenster statt einzelner Datenpunkte — deutlich weniger
  Anfragen an die Anlage.
- Uhrzeiten und Datumsfelder werden nicht mehr von selbst angelegt.
- Bei Störungen wird langsamer gefragt, statt die Anlage im gleichen Takt
  weiter zu belasten.

### Behoben

- Nach einem Neustart oder einem *Neu einlesen* standen alle Entitäten still
  und die Anlage zeigte keinen einzigen Wert mehr.
- *Warmwasser laden abbrechen* wirkte erst beim zweiten Druck, zeigte den
  Druck erst beim nächsten Abruf und hielt die nachlaufende Ladepumpe für eine
  laufende Ladung.
- Die Integration ließ sich unter Home Assistant 2026.7 nicht mehr laden.
- „wird ausgeführt …" blieb für immer stehen.
- Das Pumpen-/Relaismodul zeigte eine Wärmeanforderung, wo es nie eine gibt.

## [1.5.0-beta.10] - 2026-08-06

Vorabversion.

### Neu

- Automations-Vorlage **Legionellenschutz nachbilden**. Nicht jeder Regler
  führt die eingebaute Legionellenschutzfunktion; wo sie fehlt, fährt die
  Vorlage den Speicher in festem Turnus über die Einmalladung hoch und stellt
  hinterher alles zurück. Wochentage, Uhrzeit, Zieltemperatur und Haltezeit
  sind einstellbar. **Nur mit Verbrühschutz-Armatur einsetzen** — die Vorlage
  sagt im Einrichtungsdialog, warum.

### Behoben

- *Warmwasser laden abbrechen* wirkte erst beim zweiten Druck, wenn die Ladung
  am Gerät gestartet oder die Seite zwischendurch neu geladen wurde.
- Die Ladetaste zeigte den Druck erst beim nächsten Abruf — bis zu 30 Sekunden,
  in denen unverändert *läuft* dastand und es aussah, als sei nichts passiert.
  Sie zeigt den gedrückten Zustand jetzt sofort und bleibt so lange gesperrt,
  bis die Anlage ihn bestätigt.
- Das Estrich-Ausheizprogramm des Heizkreises heißt schlicht *Programm* und
  stand deshalb als Zeitprogramm in der Liste. Wer den Datenpunkt einschaltete,
  sah in der Steuerungsübersicht *beenden* statt seines Heizprogramms.
- Ein Zahlenfeld sprang nach der Eingabe erst auf den alten Wert zurück und
  Sekunden später auf den neuen. Der eingestellte Wert bleibt jetzt stehen, bis
  die Anlage ihn bestätigt.
- Die Taste am Zeitprogramm stand bei kurzen Programmen mitten in der Karte
  statt unten links.

### Geändert

- Das Zeitprogramm öffnet sich zuerst zum **Lesen**: Die Zeiten stehen als
  *von – bis*, so wie das Bediengerät sie zeigt. *Bearbeiten* holt den Editor,
  und der sagt jetzt über der Tabelle, dass dort der **Startpunkt** eingestellt
  wird — ein Punkt gilt, bis der nächste kommt. Übernommen oder verworfen wird
  unten.
- Uhrzeiten und Datumsfelder werden nicht mehr von selbst angelegt. Es sind
  Einstellwerte, die man einmal anfasst; sie kosteten in jedem Durchlauf eine
  Anfrage an die Anlage. Wer sie braucht, schaltet sie einzeln ein.
- Das Zahlenfeld der Ladeschwelle hat wieder Pfeile — eigene, die die
  Schrittweite der Anlage treffen und am Telefon zu bedienen sind.
- Die *Ladetemperatur* der Einmalladung lässt sich in der Steuerung direkt
  verstellen statt nur ablesen. Sie ist der Ausschaltpunkt der Ladung.
- Die Ladeschwelle heißt *Freigabe ab Abweichung* statt *Nachladen ab*: Gemeint
  ist der Abstand zum Sollwert, nicht eine Temperatur.

## [1.5.0-beta.9] - 2026-08-06

Vorabversion.

### Behoben

- Warmwasser- und Zirkulationsprogramm trugen im Reiter Zeitprogramme das
  Symbol des Heizkreises.
- Nach einem Neustart oder einem *Neu einlesen* standen alle Entitäten still
  und die Anlage zeigte keinen einzigen Wert mehr. Ein Abruf, der in die
  Zeitüberschreitung lief, galt als „Anlage meldet keine Datenpunkte mehr".
- Der erste Abruf nach dem Start liest jeden Wert auf einmal und passte auf
  größeren Anlagen nicht in sein Zeitfenster. Er bekommt jetzt mehr Zeit; der
  Takt danach bleibt unverändert.
- Ein Pumpen-/Relaismodul ohne Aufgabe stand mit einer Wärmeanforderung in der
  Heizungsübersicht, die es nie geben wird.
- Liegt keine Wärmeanforderung an, verschwand die Zeile ganz und mit ihr das
  Anlagenteil; jetzt steht dort ein Strich.
- Im Wochenraster standen Schaltzeit und Wert ohne Trennung nebeneinander
  („06:00 21,0 °C"); dazwischen steht jetzt ein Strich.
- Zahlenfelder übertrugen jede getippte Ziffer einzeln zur Anlage.
- Das Zahlenfeld trug eine fremde Schrift, die Pfeilchen lagen über der Einheit.
- Im Zeitprogramm-Editor fehlte „Uhr" hinter der Schaltzeit.


## [1.5.0-beta.8] - 2026-08-06

Vorabversion.

### Neu

- Einschalthysterese der Warmwasserladung unter *Steuerung* einstellbar
  (1–20 K, Werk 5 K). Sie entscheidet mit, ob ein Ladeauftrag angenommen wird.

### Geändert

- Ein neu eingeschalteter Wert steht sofort da statt erst nach bis zu 30 s.

## [1.5.0-beta.7] - 2026-08-06

Vorabversion.

### Behoben

- Im HACS-Fenster fehlten alle Bilder.

### Geändert

- Das Zeitprogramm des Puffers weist darauf hin, dass es nur in der
  Betriebswahl *Auto mit Zeitprogramm* wirkt.

## [1.5.0-beta.6] - 2026-08-06

Vorabversion.

### Behoben

- Ein zweiter Druck auf *Warmwasser laden abbrechen* stellte die Betriebswahl
  auf ein Programm, das nie jemand gewählt hatte.
- Der Modus der Zirkulationspumpe war standardmäßig abgeschaltet; ohne ihn
  standen beide Zirkulationsprogramme kommentarlos nebeneinander.

### Geändert

- Zeitprogramme tragen das Symbol ihres Anlagenteils.
- Im Zeitprogramm-Editor steht die Einheit hinter dem Wert.

## [1.5.0-beta.5] - 2026-08-06

Vorabversion.

### Behoben

- *Warmwasser laden abbrechen* startete die Ladung neu, statt sie zu beenden.
- Der Abbruch wartete auf die nachlaufende Ladepumpe und blieb auf
  „wird ausgeführt …" stehen.
- Anlagen, die ihre Zeitprogramme *Heizprogramm 1* nennen, wurden nicht erkannt.

### Geändert

- Von den beiden gleichnamigen Zirkulationsprogrammen steht nur noch das da,
  das zur eingestellten Steuerungsart passt.

## [1.5.0-beta.4] - 2026-08-06

Vorabversion.

> **Diese Fassung setzt Home Assistant 2025.6 oder neuer voraus.** Die
> Anmeldung an der Anlage übernimmt jetzt Home Assistants eigene
> HTTP-Bibliothek; die dafür nötige Fassung liegt ab 2025.6 bei. Auf älteren
> Installationen bitte bei 1.5.0-beta.3 bleiben.

### Neu

- Die Geräteseite sagt, was das Gerät ist.
- Probleme melden sich, statt still zu bleiben.
- `heatnexus.rediscover` schweigt nicht mehr.
- Das Schaubild passt sich dem Erscheinungsbild an.

### Geändert

- Bei Störungen wird langsamer gefragt.

### Behoben

- Die Integration ließ sich unter Home Assistant 2026.7 nicht mehr laden.
- Das Pumpen-/Relaismodul zeigte eine Wärmeanforderung, wo es nie eine gibt.

## [1.5.0-beta.3] - 2026-08-05

Vorabversion. Sie behebt, was an der Anlage aufgefallen ist, und schneidet die
Oberfläche in lesbare Teile.

### Behoben

- „wird ausgeführt …" blieb für immer stehen.
- Ein zweiter Eingriff löst den ersten ab.
- Ein geschriebenes Zeitprogramm steht sofort in der Karte.

### Geändert

- Das Wochenraster zeigt Blöcke statt sieben gleicher Zeilen.
- Entfernen im Zeitprogramm-Editor trägt einen Mülleimer statt eines „x".

## [1.5.0-beta.2] - 2026-08-05

Vorabversion. Sie bündelt alles seit `1.5.0-beta.1`: den Reiter für die
Zeitprogramme, die Meldungsliste, den sparsameren Abruf und die Färbung der
Speicher. Zwei Umbauten darin fassen die Oberfläche an – bitte an beiden
Anlagen prüfen, bevor daraus 1.5.0 wird.

### Neu

- Zeitprogramme bedienen statt nur ablesen.
- Meldungsliste je Anlage.

### Verbessert

- Der Abruf holt Menü-Fenster statt einzelner Datenpunkte.
- Puffer und Warmwasserboiler bekommen ihre Farbe aus den echten Fühlern.
- Unveränderte Werte lösen keinen Rundlauf mehr aus.

## [1.5.0-beta.1] - 2026-08-05

Vorabversion. Sie bündelt alles seit 1.4.1 – darunter den zweiten Anlauf beim
Heizkörper und die Schichtung des Puffers. Bitte an beiden Anlagen prüfen,
bevor daraus 1.5.0 wird.

### Neu

- Der Puffer zeigt seine Schichtung.

### Behoben

- An den Ecken des Heizkörpers schimmerte Rot durch.

### Werkzeug

- Die Sonde kennt den Zugang der Anlage (`--user USER|Service`); er war fest
  verdrahtet.
- Sie kann die Endpunkte der Steuerung **aufzählen** statt sie zu raten und
  unterscheidet dabei „vorhanden", „kennt sie nicht" und „unklar".
- Der Störspeicher-Suchlauf ist aus dem Quelltext der Weboberfläche abgeleitet
  statt geraten: zehn Einträge unter `/1/<node>/<fct>/2/96/<0…9>`, gelesen
  über `lookup`.

## [1.4.2] - 2026-08-04

### Behoben

- An den Ecken des Heizkörpers schimmerte Rot durch.

### Werkzeug

- Die Sonde kann die Endpunkte der Steuerung **aufzählen** statt sie zu raten:
  Auf einen unbekannten Namen antwortet die Anlage mit `503 endpoint <name>
  does not exist`.
- Neuer Suchlauf `stoerspeicher` über den SOAP-Dienst der Steuerung, rein
  lesend.

## [1.4.1] - 2026-08-04

### Behoben

- Der Heizkörper im Schaubild war blau-rot gestreift.

### Werkzeug

- Die Suche nach den statischen Navigationseinträgen sah aus, als hinge sie.

## [1.4.0] - 2026-08-04

Bedienen, was man täglich anfasst: Warmwasser, Heizkreis und Lagerraum. Drei
der vier Fehler darunter waren keine Anzeigefehler, sondern Vergleiche mit dem
falschen Wert – belegt an zwei Anlagen und den Sonden-Läufen.

### Neu

- Der Heizkörper im Schaubild färbt sich nach seiner Vorlauftemperatur.
- Das Menüband bleibt beim Blättern stehen.
- Die Lagerraumbefüllung zeigt endlich Freigabe und Restlaufzeit.
- Neuer Dienst `heatnexus.set_vorgabe`.
- Englische Fassung des README.

### Behoben

- Die Warmwasserladung verglich mit dem falschen Sollwert.
- Eco, Comfort und der Sollwert wirkten im WW-Betrieb und im Standby nicht.
- „Warmwasser laden" ist in Übersicht und Steuerung dieselbe Taste.
- Das Urlaubsprogramm zählt bei der Warmwasserladung wie Standby.
- Ein Pumpen-/Relaismodul ohne Aufgabe steht nicht mehr im Schaubild.
- Der Schriftzug der Integration hielt die Maße nicht ein.

### Werkzeug

- Die Sonde liest strukturierte Objekte einzeln (`objekt`), sucht die
  statischen Navigationseinträge der Steuerung (`statisch`) und legt ihre
  Ausgabe immer im Repository ab, egal aus welchem Ordner sie gestartet wird.
- Ein verbrauchter Digest-Nonce beantwortete jede folgende Anfrage mit 401 und
  ließ ganze Suchläufe wie „gibt es nicht" aussehen.

### Hinweis

Die neuen Datenpunkte der Lagerraumbefüllung erscheinen erst nach einem
Neueinlesen: Dienst `heatnexus.rediscover` aufrufen.

## [1.3.1] - 2026-08-04

### Neu

- Eine laufende Vorgabe lässt sich beenden.
- Die Warmwasserladung sagt, wenn die Anlage sie nicht annimmt.

### Behoben

- Am Pumpen-/Relaismodul steht im Schaubild keine Zahl mehr.
- In der Heizungsübersicht verschwindet die Wärmeanforderung ganz.
- Die Lampen des Moduls waren oval und zu blass.

## [1.3.0] - 2026-08-03

Die eigene Oberfläche lässt sich jetzt einrichten statt nur ablesen: Karten
selbst anordnen, das Schaubild zeigt Bewegung und Zustand, Eco und Comfort
sind einen Druck entfernt. Die Abschnitte der neun Vorabversionen darunter
führen jede Änderung einzeln auf; hier stehen die Neuerungen gegenüber 1.2.0
und alles, was seit 1.3.0-beta.9 dazugekommen ist.

### Neu

- Karten selbst anordnen.
- Das Schaubild bewegt sich und zeigt Zustand.
- Eco und Comfort je Heizkreis.
- Warmwasser und Zirkulation stehen in der Heizungsübersicht.
- Das Pumpen-/Relaismodul zeigt seine Wärmeanforderung im Bild.

### Behoben

- Der Rücklauf floss in der Stichleitung verkehrt herum.
- Eine laufende Warmwasserladung kehrt beim Abbrechen dorthin zurück, wo sie
  herkam.
- Am Pumpen-/Relaismodul steht keine fremde Temperatur mehr.

## [1.3.0-beta.9] - 2026-08-03

### Behoben

- In den Optionen stand „kesselwert" als roher Schlüssel.

## [1.3.0-beta.8] - 2026-08-03

### Behoben

- Der Analog-Sollwert ist wieder aus dem Schaubild verschwunden.
- Stattdessen steht die Anforderung in der Heizungsübersicht.
- Die Abbrechen-Taste ist rot.

## [1.3.0-beta.7] - 2026-08-03

### Neu

- Eco und Comfort je Heizkreis.
- Der zweite Wert am Kessel ist wählbar.
- Das Glutbett hat eine Ersatzskala.
- Das Pumpen-/Relaismodul zeigt seine Wärmeanforderung.

### Geändert

- Am Pumpen-/Relaismodul steht der Analog-Sollwert vorn.

## [1.3.0-beta.6] - 2026-08-03

### Neu

- Die Strömung zeigt, wohin die Wärme geht.

### Behoben

- Die Taste wechselte nicht auf „Warmwasser laden abbrechen".

## [1.3.0-beta.5] - 2026-08-03

### Behoben

- „übernommen ✓" blieb für immer stehen.
- Warmwasser laden schaltet vorher den Kreis ein.
- Eine laufende Warmwasserladung lässt sich abbrechen.
- Im Systemstatus heißt der Wert **Brennkammertemperatur** statt „Brennkammer".

### Neu

- Der Puffer sagt, was er tut.

### Geändert

- Die Übersicht kommt in einer aufgeräumten Standardanordnung.

## [1.3.0-beta.4] - 2026-08-03

Die Nummer 1.3.0-beta.3 wurde zurückgezogen: Sie enthielt denselben Stand wie
beta.2, gehörte inhaltlich aber dorthin. Eine bereits veröffentlichte Nummer
ein zweites Mal mit anderem Inhalt zu vergeben, verwirrt HACS und jeden, der
sie schon geholt hat.

### Neu

- Der Mischer zeigt seine Stellung.

### Geändert

- Der Temperaturwert des Pumpen-/Relaismoduls heißt wie beim Hersteller.
- Der Funktionstyp 20 heißt im Quelltext nicht mehr „Zirkulation", sondern
  **ZSP Pumpen-/Relaismodul**.

## [1.3.0-beta.2] - 2026-08-03

### Neu

- Das Schaubild bewegt sich.

### Behoben

- Der Kessel steht wieder mittig über seinem Anschluss.
- Keine Lücke mehr zwischen Leitung und Anlagenteil.
- Der Mischer sieht aus wie ein Ventil.
- Fehlende Messwerte erscheinen nicht mehr als Strich.
- Die Anordnung gilt je Anlage.
- Gleiche Breitenangabe heißt jetzt gleiche Breite.
- Die Breite lässt sich wieder verkleinern.
- Im Systemstatus heißt der Wert wieder **Abgastemperatur** statt „Abgas".
- HeatNexus hat wieder ein Symbol.

### Geändert

- Die Taste *Karten anordnen* steht in der Kopfzeile ganz außen.

## [1.3.0-beta.1] - 2026-08-03

### Neu

- Die Karten lassen sich selbst anordnen.
- Neue Anlagenteile bringen die Anordnung nicht durcheinander.
- Zurück zur Standardanordnung.

### Geändert

- Karten einer Zeile sind jetzt gleich hoch.
- Alle vier Reiter benutzen dasselbe Kartenraster.

## [1.2.0] - 2026-08-02

Erste ausgereifte Fassung der eigenen Oberfläche. Inhaltlich entspricht sie
`1.2.0-beta.5`; die Abschnitte der fünf Vorabversionen darunter führen jede
Änderung einzeln auf.

### Hinzugefügt

- Das Anlagenschaubild ist gezeichnet statt skizziert.
- Auswahl des Wärmeerzeugers je Anlage.
- 21 zusätzliche Datenpunkte.
- Alle Datenpunkte und Auswahlwerte stehen als Dokument bereit.

### Geändert

- Neue Anordnung der Übersicht.
- Die Oberfläche startet in der Ansicht „Alle".

### Behoben

- Die Oberfläche erschien nach einer Aktualisierung erst nach
  `Strg`+`Umschalt`+`R`.
- Die in den Optionen gewählte Außentemperatur überschrieb den Fühler jeder
  Anlage.
- Die Funktionsliste eines Knotens wurde als Zeitprogramm angelegt.
- Die Integration ließ sich zeitweise gar nicht mehr einrichten.
- Mehrere Funktionstypen waren falsch zugeordnet.

## [1.2.0-beta.5] - 2026-08-02

### Behoben

- Die Oberfläche erscheint nach einer Aktualisierung endlich von selbst.
- Keine Benachrichtigung mehr ohne Haken.
- Keine schwarze Lücke mehr in der Übersicht.

### Geändert

- Die Karte *Heizungsübersicht* zeigt Logo und Schriftzug nicht mehr ein
  zweites Mal – beides steht in der Kopfzeile darüber.

## [1.2.0-beta.4] - 2026-08-02

### Behoben

- Die gewählte Außentemperatur überschrieb jede Anlage.

### Geändert

- Die Oberfläche startet in der Ansicht „Alle".
- Neue Anordnung der Übersicht.
- Der Verlauf ist in der Übersicht zugeklappt.
- Der Störungshinweis steht nur noch zweimal statt dreimal.
- Die Namen der Anlagenteile im Schaubild sind größer.

### Hinzugefügt

- 21 Datenpunkte, die die Anlagen liefern, sind nicht mehr auf der Werksebene
  versteckt.

## [1.2.0-beta.3] - 2026-08-02

### Behoben

- Die Funktionsliste eines Knotens wurde als Zeitprogramm angelegt.

## [1.2.0-beta.2] - 2026-08-02

### Behoben

- Die Integration ließ sich nicht mehr einrichten.
- Die Bauteilzeichnungen des Schaubilds wurden beim ersten Aufbau von der
  Platte gelesen – mitten in der Ereignisschleife, was Home Assistant als
  „Detected blocking call to read_text" meldete.

## [1.2.0-beta.1] - 2026-08-02

### Hinzugefügt

- Das Anlagenschaubild ist gezeichnet statt skizziert.
- Auswahl des Wärmeerzeugers je Anlage.
- Ohne Auswahl **erkennt HeatNexus die Art selbst**: zuerst am Brennstoff, den
  die Anlage meldet, sonst am Namen der Funktion.
- Solaranlage und Pumpenmodul haben eigene Zeichnungen.
- Eine **Wärmepumpe** wird jetzt als Wärmeerzeuger gezeichnet und nicht mehr
  als namenloser Kasten.
- Alle Datenpunkte und Auswahlwerte stehen jetzt als Dokument bereit.

### Behoben

- Die Funktionstypen waren an mehreren Stellen falsch zugeordnet.
- Der Diagnose-Export listete unter *Geräte* zwanzigmal dasselbe Gerät statt
  der vorhandenen Anlagenteile.
- Die Gerätesonde (`tools/heatnexus_probe.py`) las Umlaute anders als die
  Integration und zerlegte damit von Hand vergebene Namen.

## [1.1.1] - 2026-08-02

### Behoben

- Die Oberfläche erscheint nach einem Update von selbst.
- Ohne das Neuladen fehlten auch die „?“ – die sind damit erledigt.
- Im Einstellungsmenü hieß der erste Punkt weiter *Allgemein
  (Abfrageintervall)*, obwohl dort längst mehr steht.
- Im Anlagenschaubild verdeckten die Pumpenkreise die Beschriftung darunter.

### Geändert

- Erklärungen nach dem Wortlaut der Anlagendokumentation.
- Das „?“ steht jetzt auch an den Auswahlfeldern – vor allem am Brennstoff,
  dem man die richtige Einstellung nicht ansieht.
- Die Tasten der Kesselkarte stehen nebeneinander.
- Gleichzeitige Anfragen an die Anlage wieder auf drei begrenzt.

## [1.1.0] - 2026-08-02

Die zehn Vorabversionen dieser Fassung sind hier zu einem Eintrag
zusammengefasst.

### Neu

- Die eigene Oberfläche hat Reiter.
- Reiter „Steuerung“.
- Kessel ein- und ausschalten.
- Reinigung, Hauptreinigung und Wartung als eigene Tasten.
- Lagerraum befüllen.
- Erklärungen per „?“.
- Pumpen im Anlagenschaubild.
- Verlauf mit wählbaren Linien.
- Außentemperatur frei wählbar.
- Rückfrage vor Eingriffen.
- Zugang wählbar.
- Abfragestatistik in der Diagnose.

### Geändert

- Messwerte tragen jetzt ihre Größe.
- Nach einem Neustart stehen die Werte sofort da.
- Eine Aktualisierung liest die Anlage nicht mehr komplett neu ein.
- Nicht mehr alles im selben Takt.
- Nach jeder Bedienung wird nachgefasst.
- Mehrere Anlagen werden gleichzeitig verbunden.
- Abgewählte Bedienebenen verschwinden wirklich.
- Der Diagnose-Export enthält keine Adresse und keine Seriennummer mehr.
- Die Benachrichtigung beim Einlesen ist abschaltbar und standardmäßig aus.
- Zeitprogramme: Mehr als sechs Schaltpunkte je Block werden abgelehnt, statt
  von der Anlage stillschweigend gekürzt zu werden.

### Behoben

- Warmwasser wurde angezeigt, wo es keines gibt.
- Der Warmwasserspeicher fehlte im Anlagenschaubild.
- Die Warmwasserladung meldete sich nicht zurück.
- Schreibgeschützte Temperaturen.
- Am Heizkreis stand die Kesseltemperatur.
- Die eigene Oberfläche zeigte nach einer Aktualisierung die alte Fassung.
- Die allgemeinen Einstellungen ließen sich nicht speichern.
- Lange Werte sprengten die Karten, Pumpen überdeckten die Beschriftungen, und
  der Heizkreis stand ohne Warmwasser verloren in der Mitte.
- Eine Warnung im Protokoll über eine abgekündigte Home-Assistant-Funktion.

---

## [1.0.0] - 2026-08-01

Erste öffentliche Fassung.

### Behoben

- Die eigene Oberfläche blieb halb leer.
- Warmwasser wurde nicht erkannt.
- Betriebsart des Heizkreises als Zahl.
- Das Dashboard erschien nur als Fehlermeldung.
- Umlaute in Gerätenamen.
- Abgewählte Bedienebenen löschten Entitäten.
- Ab der siebten Anlage.
- Der gespeicherte Erkennungsstand wird beim Entfernen einer Anlage
  mitgelöscht, statt dauerhaft liegenzubleiben.
- Beim Entladen einer Anlage lief das Einlesen im Hintergrund weiter und
  meldete „Connector is closed".
- Bedienebenen ohne Klartext.
- Eine unvollständige Aktualisierung legte die Integration lahm.
- „Betriebsart: Unbekannt".

### Geändert

- Kennungen hängen nicht mehr an der IP-Adresse.
- Adresse änderbar.
- Entitätsnamen nach Home-Assistant-Art.
- Reihenfolge im Dashboard.
- Das Dashboard baut sich bei jedem Öffnen neu auf und folgt damit einem
  geänderten Umfang ohne Zutun.
- Die Anlage steht jetzt überall dabei.
- Jeder Anlagenteil bekommt ein eigenes Symbol, und Werte ohne Inhalt („Nicht
  verfügbar") erscheinen nicht mehr in der Übersicht.
- Restlaufzeiten (Ascheentleerung, Hauptreinigung, Wartung) werden in die
  Langzeitstatistik aufgenommen; damit ist ihr Verlauf auswertbar.

### Neu

- Begleitung beim ersten Einlesen.
- Werte in der Oberfläche sind anklickbar.
- Eigene Oberfläche.
- Ansicht „Anlage".
- Ansicht „Wartung".
- Ansicht „Auswertung".
- Fünf Automations-Vorlagen.

## [0.1.0] – Erste Veröffentlichung

Erkennung, Anzeige und Bedienung von Windhager-Heizungen über die lokale
Geräte-API. Getestet an PuroWIN mit B-PLMi-Puffer, UML/UMLZ-Heizkreisen und
ZSP-Zirkulation.

### Enthalten

- Automatische Erkennung.
- Umfang wählbar.
- Thermostat je Heizkreis.
- Zeitprogramme.
- Störungen im Klartext.
- Mehrere Anlagen.
- Schneller Start.
- Werkzeug zum Auslesen einer Anlage.

### Bekannte Einschränkungen

- Ohne angeschlossenen Raumfühler regelt die Anlage über die Heizkurve; das
  Thermostat verschiebt dann den Raum-Sollwert befristet.
- In den Betriebsarten Standby und WW-Betrieb heizt der Heizkreis nicht; ein
  Sollwert wird dort mit einer Meldung abgelehnt.
- BioWIN-Anlagen werden über die allgemeine Erkennung eingebunden, sind aber
  noch nicht an echter Hardware geprüft.
