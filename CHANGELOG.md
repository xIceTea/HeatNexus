# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Vorabversionen tragen ein Suffix (`0.1.0-beta.1`) und erscheinen in HACS nur,
wenn dort Vorabversionen zugelassen sind.

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
