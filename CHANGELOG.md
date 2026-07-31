# Changelog

Alle nennenswerten Änderungen dieses Projekts. Format nach
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

## [0.9.0]

### Geändert

- Das Projekt heißt **HeatNexus**; die Integration erscheint als
  „HeatNexus Windhager". Bestehende Entitäten, Verlaufsdaten und Automationen
  bleiben unverändert – Entitäts-IDs werden nicht angefasst.
- Projektstruktur als reguläre HACS-Integration: HACS-Metadaten, bereinigtes
  Manifest (`integration_type: hub`), Testsuite, Linting und automatische
  Validierung (hassfest, HACS).

### Hinzugefügt

- **Umfang bei der Einrichtung wählbar**: Bedienebenen (Info, Betreiber,
  Service, Werk), ob deren Entitäten sofort aktiv sind, ob sie bedienbar sein
  sollen, und das Abfrageintervall. Alles nachträglich über *Konfigurieren*
  änderbar. Service- und Werksparameter sind ohne ausdrückliche Freigabe nur
  lesbar.
- Erneute Passwortabfrage, wenn die Anlage die Anmeldung ablehnt, statt eines
  dauerhaft fehlerhaften Eintrags.
- Jede Anlage kann nur einmal eingerichtet werden; ein zweiter Versuch mit
  derselben Adresse wird abgewiesen.
- Werkzeug zum Auslesen einer Anlage (`tools/probe.cmd` bzw.
  `tools/heatnexus_probe.py`): Struktur, Menü-Ebenen, alle Datenpunkte als CSV,
  Zeitprogramme und ein Bericht mit Abgleich gegen die Geräte-Datenbank.
  Mehrere Anlagen in einem Lauf, IP-Adressen und Passwort werden abgefragt.
- Logo und Banner.
- Dokumentation zu Geräte-API, Architektur und Datenpunkten unter `docs/`.

## [0.8.0]

### Hinzugefügt

- Sensor „Meldung Klartext" je Gerät: aktive Störungen mit Klartext, Art
  (Fehler/Alarm/Info) und Handlungsempfehlung; vollständige Liste im Attribut
  `meldungen`.
- Störungstexttabelle mit 217 Einträgen.

### Geändert

- Mehrere gleichzeitig anstehende Störungen werden gesammelt und einzeln
  aufgeschlüsselt.
- Der Zustand des Klartextsensors enthält nur den Störungstext; Code und
  Handlungsempfehlung stehen im Attribut.

### Performance

- Discovery-Ergebnis wird persistent gespeichert und übersteht einen Neustart;
  Neuerkennung nur bei Versionswechsel, nach 30 Tagen oder auf Anforderung.
- Neuer Dienst `windhager.rediscover`.

## [0.7.0]

### Hinzugefügt

- Zeitprogramme (Heizprogramm 1–3, Warmwasser, Zirkulation) lesen und über den
  Dienst `windhager.set_time_program` schreiben, wahlweise mit mehreren
  Wochentag-Blöcken.
- Sensor „Meldung" je Gerät mit dem aktuellen Gerätestatus.

### Behoben

- Sollwert der Thermostate wird als befristeter Komfort-Override gesetzt und
  aus dem aktiven Raum-Sollwert zurückgelesen; der eingestellte Wert bleibt bis
  zur Bestätigung durch die Anlage sichtbar.
- Betriebsarten ohne Heizbetrieb (Standby, WW-Betrieb) lehnen das Setzen eines
  Sollwerts mit klarer Meldung ab, statt ihn stillschweigend zu verwerfen.
- Bedienungen am Thermostat werden innerhalb weniger Sekunden aktualisiert.

## [0.6.0]

### Behoben

- Erstinitialisierung ist vom zyklischen Abruf getrennt; schlägt sie fehl,
  meldet die Integration dies sauber zurück und wiederholt sie.
- Es werden nur aktive Datenpunkte zyklisch abgefragt; deaktivierte Entities
  erzeugen keine Last.
- Je Heizkreis existiert genau eine Thermostat-Entity.

### Geändert

- Abrufintervall 30 s, höhere Parallelität beim Lesen.

## [0.5.0]

### Hinzugefügt

- Serviceebene aller Funktionstypen (Heizkurve, Heizgrenzen, Vorlaufgrenzen,
  Estrichprogramm, Zirkulationseinstellungen, Pufferparameter) – standardmäßig
  deaktiviert.
- Urlaubsprogramm als Datums-Entity.

## [0.4.0]

### Hinzugefügt

- Automatische Erkennung aller freigeschalteten Funktionen über eine
  mitgelieferte Geräte-Datenbank; neue Heizkreise und Datenpunkte erscheinen
  ohne Codeänderung.

## [0.3.0]

### Geändert

- Wertebereiche, Schrittweiten, Einheiten, Schreibschutz und erlaubte
  Enum-Werte stammen aus den Metadaten der Anlage.
- Nicht vorhandene Datenpunkte werden entfernt.
- Übersetzungen für die Betriebsarten der Thermostate.

## [0.2.0]

### Hinzugefügt

- Bedienbare Datenpunkte der Betreiberebene: Betriebswahl, Behaglichkeit,
  Raumtemperatur-Sollwerte, Warmwasser-Einmalladung, Reinigung bestätigen,
  Brennstoffwahl, Kaminkehrerleistung.

## [0.1.0]

### Hinzugefügt

- Erste Fassung: Kessel, Heizkreise, Puffer und Zirkulation als Sensoren,
  Thermostat je Heizkreis, Einrichtung über die Oberfläche.
