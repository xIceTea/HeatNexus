# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Vorabversionen tragen ein Suffix (`0.1.0-beta.1`) und erscheinen in HACS nur,
wenn dort Vorabversionen zugelassen sind.

## [Unveröffentlicht]

### Behoben

- **Das Dashboard erschien nur als Fehlermeldung.** Die Ansichten wurden bisher
  im Browser aus einer nachgeladenen Datei aufgebaut. War sie noch nicht
  geladen – nach einem Neustart der Regelfall – zeigte die Seite nur
  „Timeout waiting for strategy element". Die Ansichten entstehen jetzt in Home
  Assistant selbst und sind sofort da.
- **Umlaute in Gerätenamen.** Von Hand vergebene Namen wie „Hebebühne" kamen als
  „Hebeb?hne" an: Die Steuerung nutzt die DOS-Zeichentabelle, in der das „ü" auf
  einem Byte liegt, das die bisherige Rückfallkette gar nicht kannte.
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
  Jede Überschrift trägt nun „Heizhaus · B-PLMi PUFFER"; bei den Reitern
  geschieht das nur dort, wo der Name mehrfach vorkommt.
- Jeder Anlagenteil bekommt ein eigenes Symbol, und Werte ohne Inhalt
  („Nicht verfügbar") erscheinen nicht mehr in der Übersicht.
- Restlaufzeiten (Ascheentleerung, Hauptreinigung, Wartung) werden in die
  Langzeitstatistik aufgenommen; damit ist ihr Verlauf auswertbar.

### Neu

- **Eigene Oberfläche** (in Arbeit, standardmäßig aus): Unter *Konfigurieren →
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
