# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Vorabversionen tragen ein Suffix (`0.1.0-beta.1`) und erscheinen in HACS nur,
wenn dort Vorabversionen zugelassen sind.

## [1.1.0-beta.7] - 2026-08-02

Diese Fassung gleicht die Bedienung an das an, was das Bediengerät der Anlage
selbst tut.

### Neu

- **Kessel ein- und ausschalten.** Am Bediengerät ist das der oberste
  Menüpunkt überhaupt – bei HeatNexus fehlte er. Mit Rückfrage, denn
  ausgeschaltet heizt der Kessel weder Heizkreise noch Warmwasser.
- **Karte „Lagerraum befüllen"** im Reiter *Steuerung*, aufgebaut wie die
  Seite am Bediengerät: Kesseltemperatur bzw. Vorratsbehälter, Restlaufzeit,
  ob das Befüllen **freigegeben oder gesperrt** ist, und die Betriebsphase –
  darunter die Anforderung mit Rückfrage.

### Geändert

- **Ein Abbrechen der Lagerraumbefüllung gibt es nicht** – und HeatNexus tut
  jetzt auch nicht mehr so. Am Bediengerät ist „Abbruch" die Taste des
  Nachfragedialogs, kein Stopp einer laufenden Freigabe. Die Freigabe läuft
  über ihre Restlaufzeit aus.
- Die Rückfrage beim **Brennstoffwechsel** nennt jetzt, was die Anleitung
  dazu sagt: Die Änderung wirkt erst nach Aus- und Einschalten am
  Hauptschalter.

---

## [1.1.0-beta.6] - 2026-08-02

### Neu

- **Lagerraum-Freigabe ist sichtbar.** Die Anlage führt zwei getrennte Werte:
  die Anforderung über die Betriebswahl des Kessels und die eigentliche
  Freigabe („Gesperrt" / „Freigegeben") samt Restlaufzeit. Beide standen in
  keiner Bedienebene und fehlten deshalb, obwohl das Bediengerät sie anzeigt.
  Sie werden jetzt immer mitgelesen.
- **Außentemperatur frei wählbar.** Unter *Konfigurieren → Allgemein* lässt
  sich festlegen, welcher Sensor in der Kopfzeile gilt – auch einer aus einer
  anderen Integration. Leer gelassen sucht HeatNexus sie wie bisher selbst.
  Nötig, weil der Außenfühler oft an einer anderen Anlage hängt als der, deren
  Werte man gerade ansieht.

### Geändert

- **Die Heizkreiszeile folgt jetzt der Vorlage**: Name mit farbiger
  Betriebsart darunter, rechts die Raumtemperatur groß und der Sollwert klein,
  dahinter Symbole für Betriebsart und Zeitprogramm. Heizen erscheint warm,
  Absenken kühl.

---

## [1.1.0-beta.5] - 2026-08-02

### Neu

- **Reinigung, Hauptreinigung und Wartung als eigene Tasten.** Bisher war das
  eine Auswahlliste, in der man erst lesen musste, was man wählt – und im
  Zweifel falsch wählte. Jede Taste fragt einzeln nach („Wurde die
  Hauptreinigung durchgeführt?") und setzt nur den Zähler zurück, um den es
  geht.
- **Lagerraum befüllen** als eigene Taste. Die Anlage kennt das als
  Betriebswahl des Kessels; dafür ist keine Werksebene nötig.

### Behoben

- **„wird ausgeführt …" blieb stehen**, wenn der Vorgang an der Anlage selbst
  abgebrochen wurde. Die Anzeige gibt jetzt nach drei Minuten auf, und ein
  zweiter Druck auf die Taste löst den alten Auftrag ab.
- **Der Heizkreis stand verloren in der Mitte**, wenn es kein Warmwasser gibt:
  Die Karte nahm nur zwei Drittel der Breite, die dritte Spalte blieb leer.
- **„Der Benutzername ist immer USER"** stand noch im Einrichtungsdialog,
  obwohl der Zugang direkt darunter wählbar ist.
- Eine Warnung im Protokoll über eine abgekündigte Home-Assistant-Funktion
  beim Umbenennen von Entitäten.

---

## [1.1.0-beta.4] - 2026-08-02

Vorabversion. **Wichtig für alle, die beta.3 installiert hatten:** Dort blieb
die Oberfläche auf dem alten Stand, weil der Browser die Datei aus seinem
Zwischenspeicher nahm. Das ist jetzt behoben.

### Behoben

- **Die eigene Oberfläche zeigte nach einer Aktualisierung weiter die alte
  Fassung.** Reiter, Anlagenwahl, Pumpen und die Seitenleisten-Taste fehlten,
  obwohl sie installiert waren: Die Adresse der Oberflächendatei ändert sich
  nicht, also lud der Browser die zwischengespeicherte. Sie trägt jetzt die
  Fassungsnummer und wird bei jeder Aktualisierung neu geholt.
- **Keine Rückmeldung beim Warmwasserladen** im Schnellzugriff. Die Taste sah
  auf den Auslöser, der sofort zurückfällt; sie sieht jetzt wie die Karte im
  Reiter *Steuerung* auf die Betriebsart der Anlage.
- **Leere Karten.** „Kein Heizkreis gefunden" und „Kein Warmwasserkreis
  gefunden" erschienen auch dort, wo es beides zu Recht nicht gibt. Was die
  Anlage nicht liefert, bekommt gar keine Karte mehr – so hält es die Anlage
  selbst.
- **Der Zugang stand nur unter *Neu konfigurieren*.** Er steht jetzt auch bei
  den Einstellungen der Anlage, wo man ihn neben den Bedienebenen sucht.
- **Die Abfragestatistik maß falsch.** Sie zählte die Wartezeit in der eigenen
  Warteschlange zur Antwortzeit der Anlage – bei 200 Anfragen und drei
  gleichzeitigen kam so eine „Antwortzeit" von zehn Sekunden heraus. Beides
  wird jetzt getrennt ausgewiesen.

### Geändert

- **Ruhigeres Layout.** Karten wachsen nur noch so hoch wie ihr Inhalt; bisher
  zog die längste Karte einer Zeile alle anderen mit.

---

## [1.1.0-beta.3] - 2026-08-02

Vorabversion zum Ausprobieren.

### Behoben

- **„Warmwasser laden" ohne Warmwasser.** Die Karte war schon weg, die Taste im
  Schnellzugriff nicht: Sie hing am Datenpunkt des Heizkreises, den die Anlage
  auch dort führt, wo gar kein Speicher hängt.
- **Die Warmwasserladung sprang zu früh auf „aus".** Der Auslöser der Anlage
  („Freigabe starten") ist eine Taste, kein Zustand – er fällt zurück, sobald
  der Auftrag angenommen ist. Angezeigt wird jetzt die **Betriebsart**, in der
  die Anlage „Warmwasser Einmalladung" bzw. „WW-Ladung" meldet, solange
  wirklich geladen wird. Solange das läuft, bietet die Taste **Abbrechen** an:
  Sie setzt die Betriebswahl neu und stellt damit den Grundzustand wieder her
  – denselben Weg geht die Anlagen-App über „Programm".
- **Am Heizkreis stand die Kesseltemperatur** als Leitwert statt der
  Raumtemperatur. Jeder Anlagenteil zeigt jetzt den Wert, den auch die Anlage
  für ihn zeigt.
- **Lange Werte sprengten die Karten.** Ein ganzes Warmwasserprogramm lief über
  zwanzig Zeilen; es wird gekürzt, der volle Text steht im Tooltip und in der
  Detailansicht.

### Geändert

- **Mehrere Anlagen werden gleichzeitig verbunden.** Bisher wartete die zweite
  Anlage, bis die erste ihren vollständigen Erstabruf hinter sich hatte.
- **Der Zugang lässt sich nachträglich wechseln** – über *Neu konfigurieren*,
  zusammen mit der Adresse. Bisher kam man an die Umstellung von „USER" auf
  „Service" nur über eine fehlgeschlagene Anmeldung heran.
- **Systemstatus** zeigt zusätzlich Brennkammer, Abgas, Brennerstarts und
  Betriebsstunden.

### Neu

- **Pumpen im Anlagenschaubild**, und sie drehen sich, solange sie laufen. Am
  Standbild war nicht zu erkennen, ob gerade etwas fließt.
- **Warmwasser als eigener Anlagenteil im Schaubild** – am Gerät hängen seine
  Datenpunkte am Heizkreis, auf dem Display steht es trotzdem für sich.
- **Verlauf mit wählbaren Linien**: Kesseltemperatur, Abgas, Brennkammer,
  Puffer, Vorlauf, Raum, Rücklauf, Außentemperatur und Kesselleistung sind
  vorausgewählt, jede Linie lässt sich an- und abschalten.
- **Reiter „Alle"** stellt bei mehreren Anlagen alle untereinander, mit
  Überschrift je Anlage.
- **Das HeatNexus-Symbol oben links** öffnet die Seitenleiste – auf dem Handy
  kam man sonst nur mit einer Wischgeste wieder heraus.
- **Abfragestatistik in der Diagnose**: Anfragen je Stunde, Dauer je Anfrage
  und je Abruf, Fehlschläge. Ohne diese Zahlen war jede Aussage über das
  Abrufverhalten geschätzt.

---

## [1.1.0-beta.2] - 2026-08-01

Vorabversion zum Ausprobieren.

### Behoben

- **Warmwasser wurde angezeigt, wo es keines gibt.** Ein Heizkreis führt die
  Warmwasser-Einstellungen auch dann, wenn kein Speicher daran hängt – erkannt
  wurde Warmwasser aber genau daran. Jetzt zählt, was die Anlage misst: eine
  Warmwassertemperatur oder ein gemeldeter Warmwasserkreis. Nebenbei zählte
  die Abgas-*Re*zirkulation des Kessels als Zirkulation mit.
- **Messwerte ohne Einheit und ohne Verlauf.** Außer Temperaturen bekam kein
  Wert eine Zuordnung: Drehzahlen, Ströme, Leistungen, Volumenströme und
  Zählerstände liefen als namenlose Zahlen ohne Langzeitstatistik. Sie tragen
  jetzt ihre Größe, ihre Einheit in der von Home Assistant erwarteten
  Schreibweise und eine sinnvolle Anzahl Nachkommastellen. Zählerstände
  (Betriebsstunden, Brennerstarts, Verbrauch) werden als Summe geführt und
  sind damit auswertbar.
- **Schreibgeschützte Temperaturen verloren ihre Eigenschaft** und standen als
  nackte Zahl da. Sie bleiben jetzt Temperaturen.
- Der Diagnose-Export enthält keine Adresse und keine Seriennummer mehr – er
  landet oft ungelesen in Fehlerberichten.

### Geändert

- **Nach einem Neustart stehen die Werte sofort da.** Bisher war bis zum ersten
  Abruf alles „nicht verfügbar". Angezeigt wird nun der zuletzt bekannte Wert,
  bis die Anlage antwortet. Bedienbare Werte machen das bewusst nicht: Ein
  Sollwert, der nicht der Anlage entspricht, wäre schlimmer als ein leeres Feld.
- **Eine Aktualisierung liest die Anlage nicht mehr komplett neu ein.** Bisher
  kostete jedes Update 30 bis 120 Sekunden, in denen kaum etwas dastand. Der
  bekannte Stand gilt sofort weiter, der Abgleich läuft im Hintergrund, und
  Neues wird nachgereicht.
- **Abgewählte Bedienebenen verschwinden wirklich.** Bisher blieben ihre
  Einträge abgeschaltet stehen. Wer eine Ebene abwählt, meint das auch – ihre
  Entitäten werden entfernt. Fällt dagegen ein Datenpunkt weg, weil die Anlage
  ihn nicht mehr liefert, wird er wie bisher nur stillgelegt.
- **Die Abfragetakte stimmen jetzt bei jedem Intervall.** „Alle 15 Minuten"
  hieß bei einem Intervall von 300 Sekunden in Wahrheit zweieinhalb Stunden.
- Die Benachrichtigung beim Einlesen ist jetzt **abschaltbar und
  standardmäßig aus** (*Konfigurieren → Allgemein*).
- Zeitprogramme: Mehr als sechs Schaltpunkte je Block werden mit einer
  Meldung abgelehnt, statt von der Anlage stillschweigend gekürzt zu werden.

### Neu

- **Die eigene Oberfläche hat Reiter**: Übersicht, Steuerung, Wartung, Verlauf.
  Bei mehreren Anlagen steht die Anlagenwahl darüber – bisher liefen sie
  ineinander.
- **Steuerung** nach dem Vorbild der Anlage selbst: je Heizkreis Betriebsart,
  Raumtemperatur, Sollwertregler, Betriebswahl und Zeitprogramm; Warmwasser
  mit Ist, Soll, Ladetemperatur und Einmalladung; die Eingriffe am Kessel.
- **Rückmeldung, die bis zum Ende trägt.** Nach „wird übertragen" steht jetzt
  „wird ausgeführt …", solange die Anlage den neuen Zustand nicht bestätigt
  hat, und erst dann „übernommen ✓". Ein laufender Sollwert am Heizkreis zeigt,
  wie lange er noch gilt.
- **Taste für die Seitenleiste** oben links, wenn der Platz knapp ist – auf dem
  Handy war die Seitenleiste sonst verdeckt.
- Die Außentemperatur steht in der Kopfzeile, wo sie hingehört: Sie gilt für
  die ganze Anlage, nicht für einen Anlagenteil.

---

## [1.1.0-beta.1] - 2026-08-01

Vorabversion zum Ausprobieren. In HACS nur sichtbar, wenn dort
„Vorabversionen einbeziehen“ eingeschaltet ist.


### Neu

- **Rückfrage vor Eingriffen.** Serviceausbrand, Reinigung bestätigen,
  Brennstoffwahl, Estrichprogramm, Legionellenschaltung und Lagerraumbefüllung
  fragen nach, bevor sie ausgelöst werden – in der eigenen Oberfläche als
  Dialog, im Dashboard über das Kachelsymbol. Harmlose Bedienungen wie die
  Warmwasser-Einmalladung bleiben ohne Nachfrage: Ein Hinweis, der immer kommt,
  wird irgendwann blind weggeklickt.
- **Sichtbare Rückmeldung beim Bedienen.** Die Anlage wird nur alle 30 Sekunden
  abgefragt; bisher drückte man eine Taste und nichts geschah. Jetzt steht
  „wird übertragen …", danach „übertragen ✓" oder der Fehlertext, und unter der
  Taste bleibt der Zustand stehen – bei Tasten der Zeitpunkt der letzten
  Auslösung, bei Schaltern „läuft" oder „aus".
- **Zugang wählbar.** Bei der Einrichtung lässt sich zwischen `USER` und
  `Service` wählen oder ein eigener Benutzername eintragen. Bisher war `USER`
  fest eingebaut, womit die Fachparameter je nach Anlage gar nicht erreichbar
  waren. Der Zugang gehört zum Erkennungsstand: Ein Wechsel liest die Anlage
  neu ein.
- Die README erklärt jetzt, welche Zugänge es ab Werk gibt, wie sich der Zugang
  prüfen lässt und warum die Windhager-App das Passwort ändert.

### Geändert

- **Nicht mehr alles im selben Takt.** Jeder Datenpunkt bekommt eine
  Poll-Klasse: Temperaturen, Betriebszustände und das Thermostat weiter alle
  30 Sekunden, Leistungen und Mischer alle zwei Minuten, Zählerstände,
  Betriebsstunden, Restlaufzeiten und Fachparameter alle 15 Minuten.
  Zeitprogramme laufen im langsamen Takt mit. Die Anzeige ändert sich dadurch
  nicht – zuletzt gelesene Werte bleiben stehen –, die Last auf der Steuerung
  sinkt aber deutlich.

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
