# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Vorabversionen tragen ein Suffix (`0.1.0-beta.1`) und erscheinen in HACS nur,
wenn dort Vorabversionen zugelassen sind.

## [Unveröffentlicht]

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
