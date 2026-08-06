# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Vorabversionen tragen ein Suffix (`0.1.0-beta.1`) und erscheinen in HACS nur,
wenn dort Vorabversionen zugelassen sind.

## [Unveröffentlicht]

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

- **Die Geräteseite sagt, was das Gerät ist.** Bisher stand dort nichts:
  kein Software-, kein Hardwarestand, keine Seriennummer – obwohl die Anlage
  alles davon liefert. Als Modell stand der von Hand vergebene Anlagenname;
  jetzt steht dort die Bauart.
- **Probleme melden sich, statt still zu bleiben.** Stimmt das Passwort nicht
  mehr, fragt Home Assistant von sich aus danach – aber erst nach drei
  abgewiesenen Anfragen hintereinander, denn eine einzelne ist Alltag.
  Antwortet die Anlage gar nicht mehr, steht das in den Reparaturen, mit Namen
  und Grund, und verschwindet von selbst, sobald wieder Werte kommen. Vorher
  wurden die Entitäten einfach grau.
- **`heatnexus.rediscover` schweigt nicht mehr.** Der Lauf dauert 30 bis 120
  Sekunden; hinterher stand nur „Dienst ausgeführt" da. Jetzt kommt je Anlage
  zurück, wie viele Entitäten, Datenpunkte und Zeitprogramme gefunden wurden.
- **Das Schaubild passt sich dem Erscheinungsbild an.** Auf hellem Grund waren
  Rahmen und Beschriftung blass bis unlesbar – die Zeichnung war für einen
  dunklen Hintergrund gerechnet. Sie kommt jetzt in beiden Farbsätzen mit und
  wechselt beim Umschalten mit, ohne neu zu laden. Gilt für die Oberfläche wie
  für das mitgelieferte Dashboard.

### Geändert

- **Bei Störungen wird langsamer gefragt.** Bisher lief der Abruf unbeirrt
  alle dreißig Sekunden weiter, auch wenn die Steuerung dreimal hintereinander
  nichts geliefert hatte – und hielt eine überlastete oder gerade neu
  startende Anlage genau darin fest. Jetzt verdoppelt sich der Abstand nach
  jedem Fehlschlag, höchstens bis fünf Minuten; die erste gelungene Antwort
  stellt sofort auf den gewählten Takt zurück.

### Behoben

- **Die Integration ließ sich unter Home Assistant 2026.7 nicht mehr laden.**
  Sie benutzte ein Paket, das Home Assistant inzwischen aus seinen
  Abhängigkeiten geworfen hat. Es lief nur weiter, solange irgendeine andere
  Integration es noch mitbrachte.
- **Das Pumpen-/Relaismodul zeigte eine Wärmeanforderung, wo es nie eine
  gibt.** Wo das Modul nur ein Relais schaltet, stand in der Heizungsübersicht
  eine Zeile mit einem Strich, die nie einen Wert bekam.

## [1.5.0-beta.3] - 2026-08-05

Vorabversion. Sie behebt, was an der Anlage aufgefallen ist, und schneidet die
Oberfläche in lesbare Teile.

### Behoben

- **„wird ausgeführt …" blieb für immer stehen.** Nach einem Eingriff räumte
  die Oberfläche ihre Rückmeldung nie wieder ab: Beim Schnitt in ES-Module
  blieben zwei Zeitkonstanten ohne Ausfuhr liegen, und der erste Aufräumversuch
  scheiterte still. Sichtbar wurde es bei Eco und Comfort — die Anlage stellte
  brav zurück, die Karte behauptete weiter, sie arbeite noch.
- **Ein zweiter Eingriff löst den ersten ab.** Wer den Sollwert verschiebt und
  danach Eco drückt, hat seine erste Vorgabe selbst überstimmt. Sie wartete
  trotzdem drei Minuten auf eine Bestätigung, die nicht mehr kommen konnte.
- **Ein geschriebenes Zeitprogramm steht sofort in der Karte.** Zeitprogramme
  werden im langsamen Takt gelesen; wer eines änderte und die Karte gleich
  wieder öffnete, sah bis zu einer Viertelstunde lang den Stand von vorher und
  musste glauben, das Schreiben sei fehlgeschlagen. Jetzt wird genau dieses
  eine Programm sofort nachgelesen.

### Geändert

- **Das Wochenraster zeigt Blöcke statt sieben gleicher Zeilen.** Ein Programm,
  das für die ganze Woche gilt, steht in einer Zeile „täglich"; getrennte
  Blöcke stehen als „Mo–Fr" und „Sa, So" untereinander — so, wie die Anlage sie
  auch führt. Unter jedem Balken stehen die Schaltzeiten als Text: Ob um 05:00
  oder um 05:30 geschaltet wird, liest niemand aus einem Balken ab. Tage ohne
  Programm bekommen eine eigene, leere Zeile.
- Entfernen im Zeitprogramm-Editor trägt einen Mülleimer statt eines „x".

## [1.5.0-beta.2] - 2026-08-05

Vorabversion. Sie bündelt alles seit `1.5.0-beta.1`: den Reiter für die
Zeitprogramme, die Meldungsliste, den sparsameren Abruf und die Färbung der
Speicher. Zwei Umbauten darin fassen die Oberfläche an – bitte an beiden
Anlagen prüfen, bevor daraus 1.5.0 wird.

### Neu

- **Zeitprogramme bedienen statt nur ablesen.** Ein eigener Reiter zeigt jedes
  Zeitprogramm als Wochenraster: sieben Zeilen, darin die Schaltzeiten als
  Balken, eingefärbt nach Solltemperatur – bei Zirkulation und Freigabezeiten
  nach Ein und Aus. Bearbeitet wird in **Blöcken**, so wie die Anlage es führt:
  Wochentage anhaken, bis zu sechs Schaltzeiten je Block setzen, speichern
  schreibt das ganze Programm.

  Der Editor lehnt vorher ab, was die Anlage nicht annimmt – mehr als sechs
  Schaltzeiten je Block, denselben Wochentag in zwei Blöcken, dieselbe Uhrzeit
  doppelt. Das Gerät würde sonst kommentarlos kürzen. Vor der ersten
  Schaltzeit des Tages gilt die letzte des Vortages weiter; genau so heizt die
  Anlage, und genau so steht es jetzt auch im Raster.

- **Meldungsliste je Anlage.** `FE01msg` nennt nur, was gerade anliegt – wer
  die Verkleidungstür öffnet und wieder schließt, sieht die Meldung kommen und
  gehen, und hinterher steht nirgends, dass sie da war. Ein neuer Sensor
  „Meldungsliste" sammelt jede Meldung ohne Dubletten, mit erstem und letztem
  Auftreten; der Dienst `heatnexus.meldungen_loeschen` leert sie.

  **Es ist unsere Liste, nicht die des Kessels.** Der Störspeicher des
  Bediengeräts ist über die Schnittstelle nicht zu bekommen: `2/96` – die
  Adresse, die die Weboberfläche der Steuerung selbst benutzt – antwortet an
  jeder Funktion mit `409`, und von 24 denkbaren Endpunktnamen kennt die
  Steuerung keinen. Löschen räumt deshalb nur in Home Assistant auf; am Gerät
  anstehende Meldungen bleiben unberührt.

### Verbessert

- **Der Abruf holt Menü-Fenster statt einzelner Datenpunkte.** Bisher wurde
  jeder fällige Wert einzeln geholt. Jetzt liest die Integration je Menü-Ebene
  ein Fenster von der ersten bis zur letzten gebrauchten Stelle
  (`?count=&offset=`) – dieselbe Form, die das Bediengerät selbst benutzt. An
  der Anlage gemessen, 78 abgerufene Werte über 28 Menü-Ebenen: **78 Anfragen
  → 28**, und die Zahl der Datenpunkte auf dem Anlagenbus bleibt bei 80. Das
  ganze Menü zu ziehen wäre mit 29 Anfragen kaum besser gewesen, hätte die
  Buslast aber verdreifacht.
- **Puffer und Warmwasserboiler bekommen ihre Farbe aus den echten Fühlern.**
  Die Farbe liegt unter der Zeichnung, nicht darüber – so bleiben Kontur,
  Dämmnähte, Stutzen und Register sichtbar; oben liegend deckte sie alles zu
  und der Speicher sah aus wie ein Klotz. Meldet ein Boiler nur einen Istwert,
  wird gleichmäßig eingefärbt, statt eine Schichtung zu erfinden.
- **Unveränderte Werte lösen keinen Rundlauf mehr aus.** Der Koordinator
  meldet nur noch, was sich wirklich geändert hat. Die befristete Anzeige des
  Thermostats prüft ihren Ablauf dafür zeitbasiert und nicht mehr am Takt des
  Abrufs.

## [1.5.0-beta.1] - 2026-08-05

Vorabversion. Sie bündelt alles seit 1.4.1 – darunter den zweiten Anlauf beim
Heizkörper und die Schichtung des Puffers. Bitte an beiden Anlagen prüfen,
bevor daraus 1.5.0 wird.

### Neu

- **Der Puffer zeigt seine Schichtung.** Oben die Farbe der oberen Temperatur,
  unten die der unteren, dazwischen die Sprungschicht – beides echte Fühler
  (`21/65` TPE, `21/66` TPA). Durchgeladen heißt durchgehend eine Farbe.
  Gezeichnet wird nur, wenn beide melden: Einen zweiten Wert abzuleiten wäre
  schlimmer als keine Schichtung, der Speicher sähe immer halb geladen aus.

### Behoben

- **An den Ecken des Heizkörpers schimmerte Rot durch**, auf dem Handy
  deutlicher als am Rechner. Die gezeichneten Glieder sind an den Enden rund,
  die farbige Ebene darüber war eckig. Sie besteht jetzt aus einem Element je
  Glied mit derselben Rundung, und die Zeichnung darunter ist neutral: Sie
  füllte die Glieder mit einem Verlauf von Glut nach Warm und glühte damit
  auch bei 27 °C Vorlauf. Ohne gemessene Vorlauftemperatur bleibt der
  Heizkörper grau.

### Werkzeug

- Die Sonde kennt den Zugang der Anlage (`--user USER|Service`); er war fest
  verdrahtet.
- Sie kann die Endpunkte der Steuerung **aufzählen** statt sie zu raten und
  unterscheidet dabei „vorhanden", „kennt sie nicht" und „unklar". Ein `401`
  ist der verbrauchte Digest-Nonce und kein Fund – vorher zählte er als einer.
- Der Störspeicher-Suchlauf ist aus dem Quelltext der Weboberfläche abgeleitet
  statt geraten: zehn Einträge unter `/1/<node>/<fct>/2/96/<0…9>`, gelesen
  über `lookup`. Ergebnis an der geprüften Anlage: Diese Firmware führt ihn
  nicht über die Schnittstelle.

## [1.4.2] - 2026-08-04

### Behoben

- **An den Ecken des Heizkörpers schimmerte Rot durch.** Die gezeichneten
  Glieder sind an den Enden rund, die farbige Ebene darüber war eckig – an
  jeder der vier Ecken blieb ein Rest der Zeichnung stehen. Die Ebene besteht
  jetzt aus einem Element je Glied mit derselben Rundung. Dazu ist die
  Zeichnung selbst neutral geworden: Sie füllte die Glieder mit einem Verlauf
  von Glut nach Warm und glühte damit auch bei 27 °C Vorlauf. Ohne gemessene
  Vorlauftemperatur bleibt der Heizkörper jetzt grau – dann wissen wir es
  schlicht nicht.

### Werkzeug

- Die Sonde kann die Endpunkte der Steuerung **aufzählen** statt sie zu raten:
  Auf einen unbekannten Namen antwortet die Anlage mit
  `503 endpoint <name> does not exist`. Damit lässt sich prüfen, was es
  wirklich gibt (`probe endpunkte`).
- Neuer Suchlauf `stoerspeicher` über den SOAP-Dienst der Steuerung, rein
  lesend.

## [1.4.1] - 2026-08-04

### Behoben

- **Der Heizkörper im Schaubild war blau-rot gestreift.** Das Streifenmuster,
  das die fünf Glieder aus der Ebene ausschneidet, stand in festen
  Bildpunkten. Die Karte skaliert das Schaubild aber auf ihre eigene Breite –
  danach saßen die Streifen neben den gezeichneten Gliedern, und dazwischen
  blitzte die rote Füllung der Zeichnung durch. Das Raster kommt jetzt als
  Anteil der Ebenenbreite aus derselben Quelle wie die Zeichnung selbst; ein
  Test prüft es. Die Glanzkante in jedem Glied malt die Ebene mit, statt sie
  zu verdecken.

### Werkzeug

- **Die Suche nach den statischen Navigationseinträgen sah aus, als hinge
  sie.** Sie meldet jetzt jede geprüfte Adresse sofort. Dazu zwei Ursachen
  beseitigt: Ein `409 – invalid Identifier` ist die endgültige Auskunft der
  Anlage und wird nicht mehr über den zweiten Endpunkt nachgefragt, und ein
  verbrauchter Digest-Nonce kostet einen Anlauf ohne Wartezeit statt dreier
  mit.

## [1.4.0] - 2026-08-04

Bedienen, was man täglich anfasst: Warmwasser, Heizkreis und Lagerraum. Drei
der vier Fehler darunter waren keine Anzeigefehler, sondern Vergleiche mit dem
falschen Wert – belegt an zwei Anlagen und den Sonden-Läufen.

### Neu

- **Der Heizkörper im Schaubild färbt sich nach seiner Vorlauftemperatur.**
  Kalt in der Farbe des Rücklaufs, heiß in der des Vorlaufs – dieselben beiden
  Farben, die auch die Leitungen tragen. Ab etwa zwei Dritteln der Skala
  pulsiert er leicht, wie das Glutbett am Kessel. Wer Bewegung abbestellt hat,
  bekommt nur die Farbe.
- **Das Menüband bleibt beim Blättern stehen.** Marke, Anlagenwahl und die
  Reiter kleben oben; nur die Karten laufen durch. Vorher kam man aus der
  Wartung nur über den Weg nach oben zurück in die Übersicht.
- **Die Lagerraumbefüllung zeigt endlich Freigabe und Restlaufzeit.** Beide
  Datenpunkte führt die Anlage (`39/107`, `39/5`), abgefragt wurden sie auch –
  angelegt wurden sie nie, weil sie in keiner Bedienebene stehen und deshalb
  als Werksebene durchfielen. Ausdrücklich ergänzte Datenpunkte sind davon
  jetzt ausgenommen.
- **Neuer Dienst `heatnexus.set_vorgabe`**: befristete Raumtemperatur-Vorgabe
  eines Heizkreises mit eigener Dauer – derselbe Eingriff, den die Anlage
  „Eco / Comfort" nennt, jetzt auch für Automationen.
- **Englische Fassung des README** (`README.en.md`), verlinkt in beiden
  Richtungen.

### Behoben

- **Die Warmwasserladung verglich mit dem falschen Sollwert.** Geprüft wurde
  gegen die gewöhnliche Warmwassertemperatur (`1/4`, an der geprüften Anlage
  49,5 °C) statt gegen die Temperatur der *Einmalladung* (`5/51`, dort
  65 °C). Bei 61 °C im Speicher meldete die Taste „schon 61 °C – erst ab
  45 °C" und verweigerte eine Ladung, die die Anlage klaglos ausgeführt hätte.
  Der Abstand sah nach 16 K aus, war aber die Differenz der beiden Sollwerte.
  Der Abstand selbst bleibt bei den 5 K des Herstellers; meldet die Anlage
  ihren eigenen Parameter „Hysterese EIN" (`5/0`), gilt der.
- **Eco, Comfort und der Sollwert wirkten im WW-Betrieb und im Standby
  nicht.** Beide Tasten schrieben Temperatur und Dauer als Zahlenwerte an der
  Klimaentität vorbei. Dort ist der Heizkreis aber aus: Die Anlage übernahm
  nur den Timer, es lief eine Vorgabe ohne Wärmeanforderung, und die
  Rückmeldung wartete auf eine Bestätigung, die nicht kommen konnte. Jetzt
  gehen sie denselben Weg wie ein gesetzter Sollwert – kurz in ein
  Heizprogramm und danach zurück.
- **„Warmwasser laden" ist in Übersicht und Steuerung dieselbe Taste.** In der
  Steuerung fehlten Ladeschwelle, Betriebswahl und Abbruch; dieselbe Ladung
  ließ sich in der einen Ansicht beenden und in der anderen nicht.
- **Das Urlaubsprogramm zählt bei der Warmwasserladung wie Standby.** Es steht
  nicht in der Betriebswahl – `3/50` kennt es gar nicht – sondern nur in der
  Betriebsart (`2/9`). Dort wird es jetzt gelesen.
- **Ein Pumpen-/Relaismodul ohne Aufgabe steht nicht mehr im Schaubild.** An
  der zweiten geprüften Anlage beantwortet das Modul weder Kesseltemperatur
  noch Pumpendrehzahl noch die Gruppe 29 – es ist ein Klemmenkasten. Es stand
  trotzdem als Kasten in der Leitung, durch den nichts fließt.
- **Der Schriftzug der Integration hielt die Maße nicht ein.** `logo.png` war
  512×127 statt mindestens 128 hoch, `logo@2x.png` 1024×254 statt 256. Ein
  Test prüft die vier Bilder jetzt.

### Werkzeug

- Die Sonde liest strukturierte Objekte einzeln (`objekt`), sucht die
  statischen Navigationseinträge der Steuerung (`statisch`) und legt ihre
  Ausgabe immer im Repository ab, egal aus welchem Ordner sie gestartet wird.
- Ein verbrauchter Digest-Nonce beantwortete jede folgende Anfrage mit 401 und
  ließ ganze Suchläufe wie „gibt es nicht" aussehen. Die Sonde meldet sich in
  diesem Fall neu an.

### Hinweis

Die neuen Datenpunkte der Lagerraumbefüllung erscheinen erst nach einem
Neueinlesen: Dienst `heatnexus.rediscover` aufrufen.

## [1.3.1] - 2026-08-04

### Neu

- **Eine laufende Vorgabe lässt sich beenden.** Neben *Vorgabe noch bis …*
  steht jetzt dauerhaft *abbrechen*. Ein Druck setzt die Dauer auf null –
  derselbe Weg, den die Anlage beim Wechsel der Betriebswahl selbst geht –,
  und es gilt wieder das Zeitprogramm. Ohne laufende Vorgabe ist die Zeile
  ausgeblendet.
- **Die Warmwasserladung sagt, wenn die Anlage sie nicht annimmt.** Sie
  startet erst, wenn das Wasser mindestens 5 K unter dem eingestellten Wert
  liegt; der eingestellte Wert ist der Ausschaltpunkt. Ist es dafür zu warm,
  blitzt die Taste zweimal rot und nennt den Grund, statt minutenlang auf
  *wird ausgeführt …* zu stehen.

### Behoben

- **Am Pumpen-/Relaismodul steht im Schaubild keine Zahl mehr.** Sein Fühler
  misst bei einer Fernwärmeübergabe den Speicher auf der *anderen* Seite – im
  Bild sah es aus, als stünde diese Temperatur im Heizhaus. Gezeichnet wird das
  Modul weiter; seinen Zustand zeigen die Lampen.
- **In der Heizungsübersicht verschwindet die Wärmeanforderung ganz**, solange
  keine anliegt. Ein „–" sah aus wie ein fehlender Messwert.
- **Die Lampen des Moduls waren oval und zu blass.** Sie sind rund, größer und
  leuchten von innen heraus; die Betriebslampe verdeckt die gezeichnete rote
  jetzt vollständig.

## [1.3.0] - 2026-08-03

Die eigene Oberfläche lässt sich jetzt einrichten statt nur ablesen: Karten
selbst anordnen, das Schaubild zeigt Bewegung und Zustand, Eco und Comfort
sind einen Druck entfernt. Die Abschnitte der neun Vorabversionen darunter
führen jede Änderung einzeln auf; hier stehen die Neuerungen gegenüber 1.2.0
und alles, was seit 1.3.0-beta.9 dazugekommen ist.

### Neu

- **Karten selbst anordnen.** In allen vier Reitern: ziehen, verschieben,
  aus- und einblenden, über ein bis vier Spalten breit machen. Je Benutzer und
  je Reiter gespeichert; neue Anlagenteile bringen die Anordnung nicht
  durcheinander.
- **Das Schaubild bewegt sich und zeigt Zustand.** Vor- und Rücklauf strömen,
  die Stichleitung zu jedem Verbraucher strömt mit, wenn dessen Pumpe läuft.
  Das Glutbett des Kessels glimmt nach seiner Leistung, der Mischer zeigt seine
  Stellung, der Puffer sagt *lädt* oder *entlädt*.
- **Eco und Comfort je Heizkreis** – zwei Tasten, die Temperatur und Dauer in
  einem Zug schreiben. Werte in den Optionen einstellbar.
- **Warmwasser und Zirkulation stehen in der Heizungsübersicht.** Beide hängen
  als Datenpunkte am Heizkreis, liest man aber täglich.
- **Das Pumpen-/Relaismodul zeigt seine Wärmeanforderung im Bild.** Liegt eine
  an, blinken die Klemmen des Moduls grün und die Betriebslampe wechselt von
  Rot auf Grün; in der Übersicht steht der angeforderte Sollwert.

### Behoben

- **Der Rücklauf floss in der Stichleitung verkehrt herum** – ins Bauteil
  hinein statt in die Leitung.
- **Eine laufende Warmwasserladung kehrt beim Abbrechen dorthin zurück, wo sie
  herkam.** Bisher stellte der Abbruch immer auf das Zeitprogramm und beendete
  damit stillschweigend einen laufenden Heiz- oder Absenkbetrieb. Nach jedem
  Eingriff werden die beteiligten Werte sofort neu abgefragt, statt bis zum
  nächsten Abruf zu warten.
- **Am Pumpen-/Relaismodul steht keine fremde Temperatur mehr.** Sein Fühler
  misst bei einer Fernwärmeübergabe den Speicher auf der anderen Seite; in der
  Übersicht sagte diese Zahl nichts. Dort steht jetzt die Anforderung – und
  nur, wenn eine anliegt.

## [1.3.0-beta.9] - 2026-08-03

### Behoben

- **In den Optionen stand „kesselwert" als roher Schlüssel.** Die Einstellung
  heißt jetzt *Kesselwert (Schaubild)*, ihre beiden Auswahlmöglichkeiten
  *Kesselleistung* und *Brennkammertemperatur* – in allen drei Sprachen.

## [1.3.0-beta.8] - 2026-08-03

### Behoben

- **Der Analog-Sollwert ist wieder aus dem Schaubild verschwunden.** In
  1.3.0-beta.7 stand er dort vorn; im Schaubild sagt eine Zahl an dieser Stelle
  aber nichts aus. Das Pumpen-/Relaismodul zeigt dort wieder seine gemessene
  Temperatur.
- **Stattdessen steht die Anforderung in der Heizungsübersicht.** Fordert das
  Modul gerade Wärme an – Analog-Sollwert über null –, steht dort
  *Soll … | Ist …* statt nur der gemessenen Temperatur. Ohne Anforderung
  bleibt der Sollwert weg; er sagt dann nichts.
- **Die Abbrechen-Taste ist rot.** *Warmwasser laden abbrechen* sah aus wie
  jede andere Taste.

## [1.3.0-beta.7] - 2026-08-03

### Neu

- **Eco und Comfort je Heizkreis.** Zwei Tasten schreiben die befristete
  Übersteuerung, die auch das Bediengerät setzt – Temperatur und Dauer in einem
  Zug. Beide Wertepaare stehen in den Optionen (Vorgabe: Eco 10 °C, Comfort
  22 °C, je 180 Minuten) und gelten für alle Kreise: Die Anlage kennt je Kreis
  nur *einen* Übersteuerungswert. Ob er Eco oder Comfort heißt, entscheidet sie
  daran, ob er unter oder über dem Programmsollwert liegt – deshalb landet man
  in der App bei „Comfort" auf „Eco", solange die Temperatur nicht passt.
- **Der zweite Wert am Kessel ist wählbar**: Kesselleistung (Vorgabe) oder
  Brennkammertemperatur, einstellbar je Anlage.
- **Das Glutbett hat eine Ersatzskala.** Es folgt weiterhin der Leistung.
  Meldet die Anlage keine, richtet es sich nach der Brennkammertemperatur:
  unter 100 °C dunkel, ab 500 °C voll, darüber bleibt es voll.
- **Das Pumpen-/Relaismodul zeigt seine Wärmeanforderung.** Steht der
  Analog-Sollwert über null, erscheint *fordert xx °C* unter dem Modul.

### Geändert

- **Am Pumpen-/Relaismodul steht der Analog-Sollwert vorn**, nicht mehr die
  Kesseltemperatur. Die misst den Fühler des Moduls – bei einer
  Fernwärmeübergabe also den Speicher auf der *anderen* Seite. Im Schaubild sah
  es damit so aus, als stünde diese Temperatur im Heizhaus.

## [1.3.0-beta.6] - 2026-08-03

### Neu

- **Die Strömung zeigt, wohin die Wärme geht.** Die waagrechten Leitungen
  strömen wie bisher, sobald irgendeine Pumpe fördert. Zusätzlich strömt jetzt
  die senkrechte Stichleitung zu jedem Anlagenteil, dessen eigene Pumpe läuft –
  bei mehreren gleichzeitig eben mehrere. Vorher blieben die Abzweige still,
  auch wenn dort tatsächlich Wasser lief.

### Behoben

- **Die Taste wechselte nicht auf „Warmwasser laden abbrechen".** Ob geladen
  wird, hing allein an der Betriebsart – die meldet je nach Baureihe andere
  Worte und an manchen Kreisen gar nichts. Jetzt zählt zusätzlich die
  Ladepumpe, und die läuft, solange geladen wird. Damit greift auch das
  Zurückstellen der Betriebswahl wieder.

## [1.3.0-beta.5] - 2026-08-03

### Behoben

- **„übernommen ✓" blieb für immer stehen.** Nach dem Umstellen einer
  Betriebswahl im Schnellzugriff verschwand die Rückmeldung nicht mehr. Die
  Sperre wurde zwar aufgehoben, den Text löschte aber niemand.
- **Warmwasser laden schaltet vorher den Kreis ein.** Steht die Betriebswahl
  auf *Standby*, ist der Kreis abgeschaltet und nimmt den Ladeauftrag gar
  nicht erst an. Er wird jetzt zuerst auf *WW-Betrieb* gestellt – aber nur
  aus dem Standby heraus, damit ein laufender Heiz- oder Absenkbetrieb
  erhalten bleibt.
- **Eine laufende Warmwasserladung lässt sich abbrechen.** Solange sie läuft,
  heißt die Taste *Warmwasser laden abbrechen*; ein Druck stellt die
  Betriebswahl zurück auf das Zeitprogramm. Über den Auslöser allein ging das
  nicht: Er fällt zurück, sobald die Anlage den Auftrag angenommen hat.
- Im Systemstatus heißt der Wert **Brennkammertemperatur** statt „Brennkammer".

### Neu

- **Der Puffer sagt, was er tut.** Zwischen seinen beiden Temperaturen steht
  *lädt* oder *entlädt* – je nachdem, ob seine Ladepumpe fördert oder ein
  Verbraucher zieht. Zwei Temperaturen allein ergeben keine Richtung.

### Geändert

- **Die Übersicht kommt in einer aufgeräumten Standardanordnung.** Oben
  Heizungsübersicht, Anlagenübersicht über zwei Spalten und Systemstatus,
  darunter Heizkreise, Schnellzugriff, Warmwasser und Störungen, unten der
  Verlauf. Gibt es keinen Warmwasserkreis, nimmt der Schnellzugriff dessen
  Platz ein, statt ein Loch stehen zu lassen.

## [1.3.0-beta.4] - 2026-08-03

Die Nummer 1.3.0-beta.3 wurde zurückgezogen: Sie enthielt denselben Stand wie
beta.2, gehörte inhaltlich aber dorthin. Eine bereits veröffentlichte Nummer
ein zweites Mal mit anderem Inhalt zu vergeben, verwirrt HACS und jeden, der
sie schon geholt hat.

### Neu

- **Der Mischer zeigt seine Stellung.** Im Schaubild schwenkt der Zeiger im
  Ventil zwischen Rücklauf (0 %) und Vorlauf (100 %), und das Stück Leitung
  darüber färbt sich von Blau nach Rot – genau das, was ein Mischer tut.

### Geändert

- **Der Temperaturwert des Pumpen-/Relaismoduls heißt wie beim Hersteller.**
  Bisher stand dort „Temperatur Ist" – kurz, aber in keiner Unterlage
  nachschlagbar. Windhager nennt den Datenpunkt `0/7` bei diesem Funktionstyp
  **Kesseltemperatur**; gemeint ist der eigene Fühlereingang des Moduls, nicht
  der Kessel. Ein „?"-Text erklärt das jetzt an Ort und Stelle. Die alte
  Schreibweise wird weiter erkannt, ein gespeicherter Erkennungsstand bleibt
  also gültig.
- Der Funktionstyp 20 heißt im Quelltext nicht mehr „Zirkulation", sondern
  **ZSP Pumpen-/Relaismodul**. Er kann eine Pumpe regeln, eine externe
  Wärmeanforderung entgegennehmen oder eine Sammelstörung melden – eine
  Zirkulationspumpe ist etwas anderes.

## [1.3.0-beta.2] - 2026-08-03

### Neu

- **Das Schaubild bewegt sich.** Vor- und Rücklauf strömen, solange eine Pumpe
  der Anlage fördert, und das Glutbett des Kessels glimmt, solange er Leistung
  bringt – heller bei Volllast, dunkler beim Modulieren. Wer in Home Assistant
  „Bewegung reduzieren" eingestellt hat, bekommt den Zustand als ruhige Farbe.

### Behoben

- **Der Kessel steht wieder mittig über seinem Anschluss.** Beim Hackgutkessel
  saß der Korpus acht, beim Pelletskessel zwanzig Bildpunkte neben dem Rohr –
  die Einschubschnecke bzw. der Vorratsbehälter hatte die Zeichnung
  verschoben. Ein Test misst das jetzt nach.
- **Keine Lücke mehr zwischen Leitung und Anlagenteil.** Die Anschlussstutzen
  waren fest dreißig Bildpunkte lang, die Bauteile fangen aber verschieden
  hoch an. Bei Pumpenmodul und Zirkulation klaffte deshalb sichtbar nichts.
- **Der Mischer sieht aus wie ein Ventil.** Bisher stand im Vorlauf des
  Heizkreises ein Kreis mit einem Kreuz darin, den man für eine Plus-Taste
  hielt. Jetzt steht dort das übliche Schaltzeichen aus drei Dreiecken.
- **Fehlende Messwerte erscheinen nicht mehr als Strich.** Ein Heizkreis ohne
  Raumfühler zeigte mitten im Heizkörper ein „–", das wie ein Symbol aussah.
- **Die Anordnung gilt je Anlage.** Wer im Heizhaus eine Karte verschob oder
  breiter machte, verschob sie im Wohnhaus mit.
- **Gleiche Breitenangabe heißt jetzt gleiche Breite.** Eine Anlage mit zwei
  Karten bekam zwei breite Spalten, die daneben mit drei Karten drei schmale –
  „1×" sah dadurch verschieden groß aus.
- **Die Breite lässt sich wieder verkleinern.** Bisher lief eine einzige Taste
  im Kreis: Wer einmal zu weit klickte, musste bis `4×` durch und von vorn
  beginnen. Jetzt gibt es `−`, die Anzeige und `+`.
- Im Systemstatus heißt der Wert wieder **Abgastemperatur** statt „Abgas".

- **HeatNexus hat wieder ein Symbol.** In HACS und auf der Integrationsseite
  blieb das Feld leer, weil die Bilder fehlten: Home Assistant holt sie
  entweder aus dem Repository *home-assistant/brands* oder aus einem
  `brand/`-Verzeichnis der Integration selbst. Das Verzeichnis gab es zwar,
  der Schriftzug darin hatte aber das falsche Maß (1294×320 statt höchstens
  512×256) und `logo@2x.png` fehlte – gemeldet hätte das die HACS-Prüfung
  *brands*, nur war die abgeschaltet. Beides ist behoben, die Prüfung läuft
  wieder mit. Eigene Bilder haben Vorrang vor dem Brands-Repository, dafür
  braucht Home Assistant Fassung 2026.3 oder neuer.

### Geändert

- Die Taste *Karten anordnen* steht in der Kopfzeile ganz außen. Zwischen
  Außentemperatur und Anlagenwahl stand sie mitten in den Angaben, die man
  ständig abliest.

## [1.3.0-beta.1] - 2026-08-03

### Neu

- **Die Karten lassen sich selbst anordnen.** Oben in der Kopfzeile gibt es
  eine Taste *Karten anordnen*. Darin trägt jede Karte eine Griffleiste: mit
  der Maus ziehen, mit den Pfeilen verschieben, über das Auge ausblenden und
  über `1×` breiter oder schmaler machen. Die Spaltenzahl (automatisch bis
  vier) wird in der Leiste darüber gewählt. Jeder Reiter hat seine eigene
  Anordnung, und jeder Benutzer seine eigene – wer am Tablet in der Küche
  umsortiert, ändert nichts für die anderen.
- **Neue Anlagenteile bringen die Anordnung nicht durcheinander.** Gespeichert
  wird nicht die Reihenfolge als solche, sondern die Reihenfolge der Karten,
  die man kennt. Kommt ein Heizkreis dazu, rutscht er neben die anderen
  Heizkreise – nicht ans Ende. Was die Anlage zeitweise nicht meldet, behält
  seinen Platz und steht nach der Rückkehr wieder dort.
- **Zurück zur Standardanordnung** geht über das Menü `⋮` in der
  Anordnen-Leiste, wahlweise für den aktuellen Reiter oder für alle vier.
  Bewusst hinter dem Menü und hinter einer Rückfrage: Als Taste neben
  *Fertig* wäre eine ganze Anordnung schnell versehentlich weggeworfen.

### Geändert

- **Karten einer Zeile sind jetzt gleich hoch.** In der Steuerung stand die
  Heizkreiskarte deutlich höher als *Kessel* und *Lagerraum befüllen* daneben;
  die Zeile sah aus, als fehle etwas.
- Alle vier Reiter benutzen dasselbe Kartenraster. Die Übersicht hatte bisher
  drei feste Spalten mit je einem Stapel Karten darin – darin ließ sich nichts
  umsortieren.

## [1.2.0] - 2026-08-02

Erste ausgereifte Fassung der eigenen Oberfläche. Inhaltlich entspricht sie
`1.2.0-beta.5`; die Abschnitte der fünf Vorabversionen darunter führen jede
Änderung einzeln auf.

### Hinzugefügt

- **Das Anlagenschaubild ist gezeichnet statt skizziert.** Kessel, Puffer,
  Heizkreis, Solaranlage und Pumpenmodul haben eigene Zeichnungen; das Bild
  entsteht aus dem, was die Anlage meldet.
- **Auswahl des Wärmeerzeugers je Anlage**, falls die Erkennung danebenliegt.
- **21 zusätzliche Datenpunkte**, die die Anlagen liefern, sind nicht mehr auf
  der Werksebene versteckt.
- **Alle Datenpunkte und Auswahlwerte stehen als Dokument bereit.**

### Geändert

- **Neue Anordnung der Übersicht**, der Verlauf darin zugeklappt.
- **Die Oberfläche startet in der Ansicht „Alle"**, wenn es mehrere Anlagen gibt.

### Behoben

- Die Oberfläche erschien nach einer Aktualisierung erst nach `Strg`+`Umschalt`+`R`.
- Die in den Optionen gewählte Außentemperatur überschrieb den Fühler jeder Anlage.
- Die Funktionsliste eines Knotens wurde als Zeitprogramm angelegt.
- Die Integration ließ sich zeitweise gar nicht mehr einrichten.
- Mehrere Funktionstypen waren falsch zugeordnet.

## [1.2.0-beta.5] - 2026-08-02

### Behoben

- **Die Oberfläche erscheint nach einer Aktualisierung endlich von selbst.**
  Bisher blieb die alte Ansicht stehen, bis jemand Strg+Umschalt+R drückte.
  Seit 1.1.1 trägt der Dateipfad die Fassungsnummer, die Datei wurde also neu
  geladen – aber der Name des Anzeigeelements war fest, und ein Element lässt
  sich im Browser nur einmal je Seitensitzung anmelden. Die neue Datei
  übersprang die Anmeldung, und die alte Fassung zeichnete weiter. Jetzt trägt
  auch der Name die Fassung.
- **Keine Benachrichtigung mehr ohne Haken.** „HeatNexus ist bereit" erschien
  auch dann, wenn *Benachrichtigung beim Einlesen* abgewählt war: Nur die
  Fortschrittsmeldung prüfte die Option. Beide teilen sich eine Kennung – die
  zweite ersetzt die erste –, also erschien sie ohne die erste aus dem Nichts.
- **Keine schwarze Lücke mehr in der Übersicht.** Bereitet eine Anlage kein
  Warmwasser, klaffte in der Mitte ein Loch, weil das Raster feste Zeilen
  hatte. Jetzt stapeln die Karten in ihrer Spalte und rücken nach oben.

### Geändert

- Die Karte *Heizungsübersicht* zeigt Logo und Schriftzug nicht mehr ein
  zweites Mal – beides steht in der Kopfzeile darüber. Sie hat jetzt eine
  Überschrift wie jede andere Karte.

## [1.2.0-beta.4] - 2026-08-02

### Behoben

- **Die gewählte Außentemperatur überschrieb jede Anlage.** Wer in den
  Optionen einen Sensor festlegte, sah ihn danach auch beim Heizhaus, obwohl
  das seinen eigenen Fühler hat. Jetzt behält jede Anlage ihren Messwert; die
  Auswahl gilt nur für die Ansicht **Alle**, wo es keine einzelne Anlage gibt.

### Geändert

- **Die Oberfläche startet in der Ansicht „Alle".** Wer zwei Anlagen hat, will
  beide sehen, nicht die erste.
- **Neue Anordnung der Übersicht.** Je Spalte eine Sache: links die Anlage mit
  ihren Heizkreisen darunter, in der Mitte das Schaubild mit dem Warmwasser
  darunter, rechts Systemstatus, Störungen und **Schnellzugriff**. Damit wächst
  jede Spalte nach unten, wenn eine Anlage mehr Heizkreise oder mehr
  Warmwasserwerte hat, ohne die anderen zu verschieben.
- **Der Verlauf ist in der Übersicht zugeklappt** und lässt sich aufklappen.
  Er ist das größte Element der Seite; wer ihn wirklich lesen will, hat dafür
  den eigenen Reiter.
- **Der Störungshinweis steht nur noch zweimal statt dreimal.** „Keine
  Störung" im Systemstatus ist weg – derselbe Zustand steht in der
  Anlagenübersicht und in der Störungskarte.
- Die Namen der Anlagenteile im Schaubild sind größer.

### Hinzugefügt

- **21 Datenpunkte, die die Anlagen liefern, sind nicht mehr auf der
  Werksebene versteckt.** Sie stehen in keiner Ebenenliste des Herstellers und
  waren damit unsichtbar, obwohl es gewöhnliche Messwerte und Fachparameter
  sind. Neu erreichbar unter anderem: **Kesseltype** („PW 400"),
  Puffer-Sollwert, Drehzahl der Wärmeerzeugerpumpe, Brenner, Puffertransfer-
  pumpe, die vier Frostschutzgrenzen des Heizkreises, Hysterese EIN,
  WW-Überhöhung, Mischerlaufzeit, Pumpennachlaufzeiten sowie Soll-Drehzahl des
  Saugzuggebläses. Jede Zeile ist an der Anlage gemessen; wo die
  Bedienungsanleitung denselben Parameter nennt, stimmen die Wertebereiche
  überein.

## [1.2.0-beta.3] - 2026-08-02

### Behoben

- **Die Funktionsliste eines Knotens wurde als Zeitprogramm angelegt.** Der
  `object`-Endpunkt liefert unter derselben Kennung ganz Verschiedenes: ein
  Zeitprogramm, einen Text (Gerätetyp, Softwarestand) oder die Liste der
  Funktionen eines Knotens. Weil die Funktionsliste ebenfalls eine Liste von
  Objekten ist, ging sie als Zeitprogramm durch – und ergab einen Sensor, der
  nichts anzeigt. Sichtbar wurde das nur mit eingeschalteter Werksebene.
  Erkannt an einem vollständigen Abzug der Anlage (518 Datenpunkte).

## [1.2.0-beta.2] - 2026-08-02

### Behoben

- **Die Integration ließ sich nicht mehr einrichten**: „module
  'custom_components.heatnexus.time' has no attribute 'monotonic'". Die
  Startdatei der Integration ist zugleich der Namensraum des Pakets – sobald
  Home Assistant die Plattform `time` lädt, überschreibt Python damit das dort
  stehende `import time`. Ob es dazu kam, war ein Wettlauf zwischen beidem;
  deshalb fiel es lange nicht auf, und deshalb war danach keine Anlage mehr da,
  weder im Panel noch als Entität. Ein Test hält den Fall jetzt fest.
- Die Bauteilzeichnungen des Schaubilds wurden beim ersten Aufbau von der
  Platte gelesen – mitten in der Ereignisschleife, was Home Assistant als
  „Detected blocking call to read_text" meldete. Sie werden jetzt einmal beim
  Laden der Integration eingelesen.

## [1.2.0-beta.1] - 2026-08-02

### Hinzugefügt

- **Das Anlagenschaubild ist gezeichnet statt skizziert.** Kessel, Puffer,
  Heizkörper, Warmwasserspeicher und Zirkulationskreis haben jetzt eine eigene
  Zeichnung mit Wärmetauscher, Schichtung, Registerheizschlange und
  Umlaufpumpe – statt der bunten Rechtecke von bisher.
- **Auswahl des Wärmeerzeugers je Anlage** unter *Einstellungen → Anlage*:
  Hackgut, Pellets, Scheitholz, Wärmepumpe, Gas/Öl oder neutral. Jede Art hat
  ihre eigene Zeichnung – der Hackgutkessel bekommt die Einschubschnecke, der
  Pelletskessel den Vorratsbehälter, die Wärmepumpe den Ventilator.
- Ohne Auswahl **erkennt HeatNexus die Art selbst**: zuerst am Brennstoff, den
  die Anlage meldet, sonst am Namen der Funktion. Lässt sich nichts sagen, wird
  neutral gezeichnet – geraten wird nicht.
- **Solaranlage und Pumpenmodul haben eigene Zeichnungen.** Der Kollektor
  erscheint als geneigtes Feld mit Sonne, das ZSP als Schaltgerät mit Pumpe und
  Anlegefühler. Bisher sah das ZSP genauso aus wie die
  Warmwasser-Zirkulation – im Schaubild standen zwei gleiche Kreise
  nebeneinander, die verschiedene Dinge meinten.
- Eine **Wärmepumpe** wird jetzt als Wärmeerzeuger gezeichnet und nicht mehr
  als namenloser Kasten. Sie braucht dafür weder eine Auswahl noch einen
  sprechenden Namen.
- **Alle Datenpunkte und Auswahlwerte stehen jetzt als Dokument bereit.**
  [`docs/DATAPOINTS.md`](docs/DATAPOINTS.md) führt je Funktionstyp jeden
  Datenpunkt mit Adresse, Name und Bedienebene, [`docs/ENUMS.md`](docs/ENUMS.md)
  alle Auswahltabellen. Beide werden aus der Geräte-Datenbank erzeugt, und ein
  Test schlägt fehl, wenn sie veralten. Bisher war das nur als JSON vorhanden.

### Behoben

- **Die Funktionstypen waren an mehreren Stellen falsch zugeordnet.** Sie waren
  aus Namen abgeleitet statt aus der Parameterliste des Herstellers. Richtig ist
  jetzt: 1 und 14 Heizkreis, 2 Warmwasser, 4 Kaskade, 5 und 13 Solar,
  6 Gas-/Ölkessel, 7 Wärmepumpe, 8 E-Heizung, 15 Umschaltung, 16 und 21 Puffer,
  20 und 24 Pumpenmodul, 26 und 27 Wärmepumpe. Betroffen waren Reihenfolge und
  Symbol der Abschnitte im Dashboard sowie die Zeichnung im Schaubild – eine
  Anlage mit Solarmodul sah dort bisher einen Warmwasserspeicher, eine
  Wärmepumpe einen namenlosen Kasten.
- Der Diagnose-Export listete unter *Geräte* zwanzigmal dasselbe Gerät statt
  der vorhandenen Anlagenteile. Jetzt eine Zeile je Anlagenteil, mit
  Funktionstyp und Zahl der Datenpunkte.
- Die Gerätesonde (`tools/heatnexus_probe.py`) las Umlaute anders als die
  Integration und machte aus „Hebebühne" ein „Hebeb�hne". Beide benutzen jetzt
  dieselbe Zeichensatzkette.

## [1.1.1] - 2026-08-02

### Behoben

- **Die Oberfläche erscheint nach einem Update von selbst** – ohne
  Strg+Umschalt+R. Bisher hielt der Browser die alte Datei fest: Home
  Assistant legt seine Oberfläche über einen Service-Worker ab, und der
  vergleicht Adressen ohne den Teil hinter dem Fragezeichen. Die
  Fassungsnummer steht deshalb jetzt im Pfad und nicht mehr dahinter.
- Ohne das Neuladen fehlten auch die „?“ – die sind damit erledigt.
- Im Einstellungsmenü hieß der erste Punkt weiter *Allgemein
  (Abfrageintervall)*, obwohl dort längst mehr steht. Jetzt: *Allgemein
  (Oberfläche, Erklärungen, Abfrage)*.
- Im Anlagenschaubild verdeckten die Pumpenkreise die Beschriftung darunter.

### Geändert

- **Erklärungen nach dem Wortlaut der Anlagendokumentation.** Der Brennstoff
  nennt jetzt die Werte, nach denen ausgewählt wird: *normal* 15 bis 30 %
  Wassergehalt bei bis zu 1,5 % Asche, *feucht* darüber bis höchstens 35 %,
  *schlackend* ab etwa 1,5 % Asche – samt Hinweis, dass die Umstellung erst
  nach Aus- und Einschalten am Hauptschalter wirkt. Ebenso überarbeitet:
  Serviceausbrand, Lagerraumbefüllung, Reinigungsbestätigungen,
  Einmalladung, Betriebswahl, Behaglichkeit und Sollwert.
- Das „?“ steht jetzt auch an den Auswahlfeldern – vor allem am Brennstoff,
  dem man die richtige Einstellung nicht ansieht.
- **Die Tasten der Kesselkarte stehen nebeneinander** statt untereinander; die
  Karte wuchs mit jeder Reinigungstaste weiter in die Länge.
- Gleichzeitige Anfragen an die Anlage wieder auf drei begrenzt. Sechs waren
  ausprobiert und gemessen: Die Antwortzeit stieg um zwei Drittel, der ganze
  Abruf wurde dabei kaum schneller. Die Anlage arbeitet Anfragen praktisch
  nacheinander ab.

## [1.1.0] - 2026-08-02

Die zehn Vorabversionen dieser Fassung sind hier zu einem Eintrag
zusammengefasst.

### Neu

- **Die eigene Oberfläche hat Reiter**: Übersicht, Steuerung, Wartung,
  Verlauf. Bei mehreren Anlagen steht darüber die Anlagenwahl, samt „Alle“ –
  dort erscheinen sie untereinander, jede mit eigener Überschrift.
- **Reiter „Steuerung“** nach dem Vorbild des Bediengeräts: je Heizkreis
  Betriebsart, Raumtemperatur, Sollwertregler, Betriebswahl und Zeitprogramm;
  Warmwasser mit Ist, Soll, Ladetemperatur und Einmalladung; die Eingriffe am
  Kessel; die Lagerraumbefüllung mit Freigabe und Restlaufzeit.
- **Kessel ein- und ausschalten.** Am Bediengerät der oberste Menüpunkt
  überhaupt – hier fehlte er bisher.
- **Reinigung, Hauptreinigung und Wartung als eigene Tasten** statt einer
  Auswahlliste. Jede fragt für sich nach und setzt nur den Zähler zurück, um
  den es geht.
- **Lagerraum befüllen**: anfordern und dann ablesen, ob die Anlage freigegeben
  hat. Erst dann darf weiterbefüllt werden – sonst nimmt das Rührwerk Schaden.
- **Erklärungen per „?“** an Karten und Bedienungen: was ein Wert bedeutet und
  worauf zu achten ist. Abschaltbar unter *Konfigurieren → Allgemein*.
- **Pumpen im Anlagenschaubild**, und sie drehen sich, solange sie laufen.
  Warmwasser und Zirkulation bekommen eigene Kreise, obwohl ihre Datenpunkte
  am Heizkreis hängen.
- **Verlauf mit wählbaren Linien** – Temperaturen, Außentemperatur und
  Kesselleistung vorausgewählt, jede einzeln an- und abschaltbar.
- **Außentemperatur frei wählbar**: welcher Sensor in der Kopfzeile gilt, auch
  einer aus einer anderen Integration.
- **Rückfrage vor Eingriffen** und **sichtbare Rückmeldung beim Bedienen** –
  „wird übertragen“, „wird ausgeführt …“, „übernommen ✓“.
- **Zugang wählbar** (`USER` oder `Service`), auch nachträglich änderbar.
- **Abfragestatistik in der Diagnose**: Anfragen je Stunde, Antwortzeit,
  Wartezeit, Fehlschläge.

### Geändert

- **Messwerte tragen jetzt ihre Größe.** Drehzahlen, Ströme, Leistungen,
  Volumenströme und Zählerstände liefen zuvor als namenlose Zahlen ohne
  Langzeitstatistik. Einheiten stehen in der von Home Assistant erwarteten
  Schreibweise, Zählerstände werden als Summe geführt und sind auswertbar.
- **Nach einem Neustart stehen die Werte sofort da** statt „nicht verfügbar“
  bis zum ersten Abruf.
- **Eine Aktualisierung liest die Anlage nicht mehr komplett neu ein.** Der
  bekannte Stand gilt sofort weiter, der Abgleich läuft im Hintergrund.
- **Nicht mehr alles im selben Takt**: Temperaturen und Zustände alle 30 s,
  Leistungen alle zwei Minuten, Zähler und Fachparameter alle 15 Minuten –
  und die Takte stimmen jetzt bei jedem eingestellten Intervall.
- **Nach jeder Bedienung wird nachgefasst**: Der geschriebene Wert wird sechsmal
  im Abstand von drei Sekunden nachgelesen, statt bis zu 30 Sekunden zu warten.
- **Mehrere Anlagen werden gleichzeitig verbunden**, und einzelne Werte werden
  mit höherem Durchsatz abgerufen. Die Einrichtung dauert damit etwa halb so
  lang wie zuvor.
- **Abgewählte Bedienebenen verschwinden wirklich**, statt abgeschaltet stehen
  zu bleiben. Fällt dagegen ein Datenpunkt weg, weil die Anlage ihn nicht mehr
  liefert, wird er nur stillgelegt.
- Der Diagnose-Export enthält keine Adresse und keine Seriennummer mehr.
- Die Benachrichtigung beim Einlesen ist abschaltbar und standardmäßig aus.
- Zeitprogramme: Mehr als sechs Schaltpunkte je Block werden abgelehnt, statt
  von der Anlage stillschweigend gekürzt zu werden.

### Behoben

- **Warmwasser wurde angezeigt, wo es keines gibt.** Ein Heizkreis führt die
  Warmwasser-Einstellungen auch dann, wenn kein Speicher daran hängt.
- **Der Warmwasserspeicher fehlte im Anlagenschaubild**, ebenso die
  Zirkulation und die Pumpen.
- **Die Warmwasserladung meldete sich nicht zurück.** Der Auslöser der Anlage
  ist eine Taste, kein Zustand – angezeigt wird jetzt die Betriebsart.
- **Schreibgeschützte Temperaturen** verloren ihre Eigenschaft und standen als
  nackte Zahl da.
- **Am Heizkreis stand die Kesseltemperatur** als Leitwert statt der
  Raumtemperatur.
- **Die eigene Oberfläche zeigte nach einer Aktualisierung die alte Fassung**,
  weil der Browser die Datei aus seinem Zwischenspeicher nahm.
- **Die allgemeinen Einstellungen ließen sich nicht speichern**, und zwei
  Schalter fehlten im Dialog.
- Lange Werte sprengten die Karten, Pumpen überdeckten die Beschriftungen, und
  der Heizkreis stand ohne Warmwasser verloren in der Mitte.
- Eine Warnung im Protokoll über eine abgekündigte Home-Assistant-Funktion.

---

## [1.0.0] - 2026-08-01

Erste öffentliche Fassung.

### Behoben

- **Die eigene Oberfläche blieb halb leer.** Kennwerte, Systemstatus,
  Warmwasser, Anlagenschaubild, Verlauf und Schnellzugriff fehlten. Die
  Aufteilung wurde beim Einrichten einmalig berechnet – zu einem Zeitpunkt, zu
  dem die Anlage noch eingelesen wurde und die meisten Werte schlicht noch
  nicht da waren. Sie wird jetzt bei jedem Öffnen frisch bestimmt, und ein noch
  fehlender Wert schließt eine Zeile nicht mehr aus.
- **Warmwasser wurde nicht erkannt.** Die Warmwasser-Datenpunkte gehören am
  Gerät zum Heizkreis und nicht zu einem eigenen Anlagenteil; gesucht wurde
  aber nach einem eigenen. Anlagen ohne Warmwasserbereitung zeigen die Karte
  weiterhin nicht – dort gibt es sie wirklich nicht.
- **Betriebsart des Heizkreises als Zahl.** In der Oberfläche stand „0" statt
  „Standby": Der Schlüssel der Übersetzungstabelle trug noch den alten
  Domänennamen.

- **Das Dashboard erschien nur als Fehlermeldung.** Die Ansichten wurden bisher
  im Browser aus einer nachgeladenen Datei aufgebaut. War sie noch nicht
  geladen – nach einem Neustart der Regelfall – zeigte die Seite nur
  „Timeout waiting for strategy element". Die Ansichten entstehen jetzt in Home
  Assistant selbst und sind sofort da.
- **Umlaute in Gerätenamen.** Von Hand vergebene Namen wie „Hebebühne" kamen als
  „Hebeb?hne" an: Die Steuerung nutzt die DOS-Zeichentabelle, in der das „ü" auf
  einem Byte liegt, das die bisherige Rückfallkette gar nicht kannte.
  Manche Steuerungen haben den Umlaut allerdings schon selbst verloren und
  liefern ihn als Ersatzzeichen aus – dann hilft nur, den Anlagenteil in Home
  Assistant oder an der Anlage umzubenennen.
- **Abgewählte Bedienebenen löschten Entitäten.** Wurde der Umfang verkleinert,
  waren eigene Namen, Symbole, Bereichszuordnung und Verlauf verloren. Die
  betroffenen Entitäten werden jetzt nur stillgelegt und beim Wiederdazuwählen
  reaktiviert. Wirklich aufräumen lässt sich weiterhin mit
  `heatnexus.rediscover`.
- **Ab der siebten Anlage** fehlte im Optionsdialog der Menüpunkt zur
  Bedienebenen-Auswahl.
- Der gespeicherte Erkennungsstand wird beim Entfernen einer Anlage
  mitgelöscht, statt dauerhaft liegenzubleiben.
- Beim Entladen einer Anlage lief das Einlesen im Hintergrund weiter und
  meldete „Connector is closed". Es wird jetzt zuerst beendet, danach wird die
  Verbindung geschlossen.
- **Bedienebenen ohne Klartext.** Im Dialog *Umfang festlegen* standen die
  internen Schlüssel „info", „operate", „service" und „oem" statt der
  deutschen Bezeichnungen: Home Assistant lädt die Übersetzung von
  Auswahlfeldern im Einrichtungsdialog einer eigenen Integration nicht
  zuverlässig mit. Die Bezeichnungen stehen jetzt zusätzlich fest hinterlegt.
- **Eine unvollständige Aktualisierung legte die Integration lahm.** Fehlte
  eine Datei der optionalen Oberfläche, meldete Home Assistant nur „No setup or
  config entry setup function defined" und richtete gar nichts mehr ein. Die
  Oberfläche wird jetzt erst geladen, wenn sie gebraucht wird; fehlt sie,
  laufen Entitäten und Dashboard weiter.
- **„Betriebsart: Unbekannt"** bei Puffer und Heizkreis. Die Anlage nennt in
  ihren Metadaten die Werte, die sie zur *Auswahl* stellt – beim Puffer nur
  „Standby". Angezeigt wurde daraufhin nur noch das, gemeldet hat die Anlage
  aber etwas anderes. Ein Anzeigesensor nutzt jetzt wieder die vollständige
  Tabelle.

### Geändert

- **Kennungen hängen nicht mehr an der IP-Adresse.** Geräte und Entitäten
  tragen jetzt die Seriennummer des jeweiligen Bausteins, die die Anlage in
  ihrer Struktur mitliefert. Zieht die Anlage im Netz um, bleibt alles
  bestehen – Namen, Bereiche, Verlauf, Automationen. Vorhandene Einträge
  werden beim ersten Start nach der Aktualisierung umgeschrieben; gelöscht
  oder neu angelegt wird nichts.
- **Adresse änderbar**: Über *Neu konfigurieren* an der Integration lässt sich
  die Adresse einer Anlage austauschen, ohne sie neu einzurichten.
- **Entitätsnamen nach Home-Assistant-Art**: Eine Entität heißt jetzt nach dem
  Muster „Anlage · Anlagenteil – Datenpunkt", ihre Kennung entsprechend
  `sensor.heizhaus_purowin_kesseltemperatur_ist`. Bisher entstanden Namen wie
  `sensor.b_plmi_puffer_meldung_4`, bei denen nicht erkennbar war, zu welcher
  Anlage sie gehören. Bestehende Entitäten werden einmalig umbenannt, soweit
  der neue Name frei ist und der Nutzer sie nicht selbst benannt hat.
  Das Thermostat eines Heizkreises trägt keinen Zusatz mehr und heißt wie der
  Heizkreis selbst.

- **Reihenfolge im Dashboard** folgt der Anlage statt dem Alphabet: Kessel,
  Puffer, Heizkreis, Warmwasser, Zirkulation. Anlagenteile ohne bekannten Typ
  stehen hinten.
- Das Dashboard baut sich bei jedem Öffnen neu auf und folgt damit einem
  geänderten Umfang ohne Zutun.
- **Die Anlage steht jetzt überall dabei.** Zwei gleich benannte Anlagenteile
  – etwa zwei Pufferlademodule – waren im Dashboard nicht auseinanderzuhalten.
  Jede Überschrift trägt nun die Anlage vor dem Anlagenteil; bei den Reitern
  geschieht das nur dort, wo der Name mehrfach vorkommt.
- Jeder Anlagenteil bekommt ein eigenes Symbol, und Werte ohne Inhalt
  („Nicht verfügbar") erscheinen nicht mehr in der Übersicht.
- Restlaufzeiten (Ascheentleerung, Hauptreinigung, Wartung) werden in die
  Langzeitstatistik aufgenommen; damit ist ihr Verlauf auswertbar.

### Neu

- **Begleitung beim ersten Einlesen.** Nach dem Einrichten liest HeatNexus die
  Anlage im Hintergrund vollständig ein; das dauert 30 bis 120 Sekunden, und
  solange erscheinen nach und nach weitere Entitäten. Eine Benachrichtigung
  sagt das an und nennt am Ende die gefundene Anzahl. Bisher standen zunächst
  nur wenige Werte da, ohne dass erkennbar war, dass noch etwas nachkommt.
- **Werte in der Oberfläche sind anklickbar.** Kennwerte, Systemstatus,
  Warmwasser, Heizkreise, Störungen und die Beschriftungen im Anlagenschaubild
  öffnen die Detailansicht der Entität – mit Verlauf, Einstellungen und
  Bedienung. Auch über die Tastatur erreichbar.
- **Eigene Oberfläche** (standardmäßig aus): Unter *Konfigurieren →
  Allgemein* lässt sich ein eigener Eintrag „HeatNexus" in der Seitenleiste
  einschalten – Kennwerte, Anlagenschaubild, Systemzustand, Heizkreise,
  Warmwasser, Störungen, 24-Stunden-Verlauf und Schnellzugriff in einer
  Anordnung, die sich mit Lovelace-Karten nicht bauen lässt. Welche Werte wo
  stehen, ermittelt die Integration; die Datei im Browser stellt nur dar.
- **Ansicht „Anlage"**: Ein Schaubild je Anlage – Kessel, Puffer, Heizkreise,
  Warmwasser und Zirkulation, verbunden durch Vor- und Rücklauf, mit den
  Live-Werten darauf. Das Bild wird aus den erkannten Anlagenteilen gezeichnet
  und passt sich damit jeder Anlage an: Wer zwei Puffer hat, sieht zwei.
- **Ansicht „Wartung"**: Restlaufzeiten bis Ascheentleerung, Hauptreinigung und
  Wartung als Rundinstrument mit mitwachsender Skala, dazu Brennstoff,
  Vorratsbehälter, Betriebsstunden und Brennerstarts.
- **Ansicht „Auswertung"**: Zählerstände als Zuwachs *heute* und *dieser Monat*
  – Brennerstarts und Betriebsstunden also ohne Hilfsentität und ohne eigene
  Automation – sowie Temperaturverläufe der letzten 48 Stunden je Anlagenteil.

- **Fünf Automations-Vorlagen** werden mitgeliefert: Störung melden,
  Wartungswarnung mit Erinnerung, Brennstoffvorrat niedrig, Betriebsdauer
  erfassen, Heizkreis bei Abwesenheit absenken. Sie stehen nach der Einrichtung
  unter Blueprints bereit, ein Import aus dem Netz entfällt.
  - Die Wartungswarnung kennt Vorwarnung, Warnung und Erinnerung in festem
    Abstand und kommt dabei ohne Hilfsschalter aus – zurückgesetzt wird sie,
    sobald die Anlage den Zähler wieder hochsetzt.
  - Die Störungsvorlage wertet das Attribut `stoerung_aktiv` aus statt den
    angezeigten Text; sie bleibt damit von Formulierungen unabhängig.
  - Die Betriebsdauer wird aus dem gemerkten Startzeitpunkt berechnet, nicht
    hochgezählt: Ein Neustart von Home Assistant verfälscht sie nicht mehr.
  - Alle Vorlagen sind auf die Werte abgestimmt, die die Anlage tatsächlich
    liefert: Der Vorratsbehälter meldet einen Zustand („Vorratsbehälter leer")
    und keine Füllstandszahl, und der Stillstand des Kessels umfasst mehrere
    Betriebsphasen, nicht nur „Standby".

## [0.1.0] – Erste Veröffentlichung

Erkennung, Anzeige und Bedienung von Windhager-Heizungen über die lokale
Geräte-API. Getestet an PuroWIN mit B-PLMi-Puffer, UML/UMLZ-Heizkreisen und
ZSP-Zirkulation.

### Enthalten

- **Automatische Erkennung** aller freigeschalteten Funktionen. Wertebereiche,
  Einheiten, Auswahlmöglichkeiten und Schreibschutz kommen aus den Metadaten der
  Anlage; nicht vorhandene Datenpunkte werden verworfen.
- **Umfang wählbar**: Bedienebenen (Info, Betreiber, Service, Werk), ob deren
  Entitäten sofort aktiv sind, ob sie bedienbar sein sollen, und das
  Abfrageintervall – bei der Einrichtung und jederzeit über *Konfigurieren*.
  Service- und Werksparameter sind ohne ausdrückliche Freigabe nur lesbar.
- **Thermostat je Heizkreis** mit Betriebswahl, Behaglichkeitskorrektur und
  befristetem Komfort-Sollwert; Bedienungen werden sofort angezeigt und beim
  nächsten Abruf bestätigt.
- **Zeitprogramme** für Heizung, Warmwasser und Zirkulation lesen und über den
  Dienst `heatnexus.set_time_program` schreiben.
- **Störungen im Klartext** mit Code, Art und Handlungsempfehlung; die
  vollständige Liste steht als Attribut bereit.
- **Mehrere Anlagen** parallel, jede nur einmal einrichtbar; erneute
  Passwortabfrage, wenn die Anlage die Anmeldung ablehnt.
- **Schneller Start**: Der Erkennungsstand wird gespeichert und übersteht
  Neustarts; neu eingelesen wird nur bei Bedarf oder über den Dienst
  `heatnexus.rediscover`.
- **Werkzeug zum Auslesen einer Anlage** (`tools/probe.cmd`): Struktur,
  Menü-Ebenen, alle Datenpunkte als CSV, Zeitprogramme und ein Bericht mit
  Abgleich gegen die mitgelieferte Geräte-Datenbank.

### Bekannte Einschränkungen

- Ohne angeschlossenen Raumfühler regelt die Anlage über die Heizkurve; das
  Thermostat verschiebt dann den Raum-Sollwert befristet.
- In den Betriebsarten Standby und WW-Betrieb heizt der Heizkreis nicht; ein
  Sollwert wird dort mit einer Meldung abgelehnt.
- BioWIN-Anlagen werden über die allgemeine Erkennung eingebunden, sind aber
  noch nicht an echter Hardware geprüft.
