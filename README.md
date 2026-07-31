<p align="center">
  <img src="assets/banner_small.png" alt="HeatNexus" width="820">
</p>

<p align="center">
  <a href="https://github.com/xIceTea/HeatNexus/actions/workflows/validate.yml"><img src="https://github.com/xIceTea/HeatNexus/actions/workflows/validate.yml/badge.svg" alt="Validate"></a>
  <a href="https://github.com/xIceTea/HeatNexus/actions/workflows/tests.yml"><img src="https://github.com/xIceTea/HeatNexus/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <img src="https://img.shields.io/badge/HACS-Custom-41BDF5" alt="HACS Custom">
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.12%2B-03a9f4" alt="Home Assistant 2024.12+">
</p>

# HeatNexus

Heizungen in Home Assistant – lokal, vollständig, ohne Cloud.

Die Anlage wird direkt über ihre HTTP-API im Netzwerk gelesen und gesteuert.
Abgedeckt sind Kessel, Heizkreise, Puffer, Warmwasser und Zirkulation,
einschließlich Info-, Betreiber- und Serviceebene.

## Unterstützte Geräte

| Hersteller | Gerät | Stand |
|---|---|---|
| Windhager | PuroWIN (Hackgut) | getestet |
| Windhager | BioWIN, BioWIN 2 (Pellets) | eingebunden, noch nicht an Hardware geprüft |
| Windhager | UML / UMLZ Heizkreismodul | getestet |
| Windhager | B-PLMi Pufferlademodul | getestet |
| Windhager | ZSP Zirkulationssteuerung | getestet |
| Windhager | Solar, Kaskade, Wärmepumpe | werden erkannt, ungetestet |

Weitere Anlagen werden über die allgemeine Erkennung eingebunden: Was die
Steuerung liefert, erscheint auch in Home Assistant. Rückmeldungen zu nicht
gelisteten Geräten sind willkommen.

## Funktionsumfang

- **Automatische Erkennung** aller freigeschalteten Funktionen der Anlage.
  Nicht vorhandene Datenpunkte werden entfernt, schreibgeschützte nur lesend
  angelegt.
- **Wertebereiche vom Gerät**: Minimum, Maximum, Schrittweite, Einheit und
  erlaubte Auswahlwerte stammen aus den Metadaten der Anlage.
- **Thermostat je Heizkreis** mit Betriebswahl, Behaglichkeitskorrektur und
  befristetem Komfort-Sollwert.
- **Zeitprogramme** für Heizung, Warmwasser und Zirkulation lesen und schreiben.
- **Störungen im Klartext** mit Code, Art und Handlungsempfehlung.
- **Serviceebene** vollständig verfügbar, standardmäßig deaktiviert und pro
  Entity zuschaltbar.
- Mehrere Anlagen parallel.

## Installation

### HACS

1. HACS → Integrationen → ⋮ → **Benutzerdefinierte Repositories**
2. Repository-URL eintragen, Kategorie *Integration*
3. „HeatNexus" installieren, Home Assistant neu starten

### Manuell

Ordner `custom_components/heatnexus` nach `<config>/custom_components/heatnexus`
kopieren und Home Assistant neu starten.

### Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → **HeatNexus**.
Erforderlich sind die IP-Adresse der Anlage und das
Service-Passwort; der Benutzername ist `USER`.

Im zweiten Schritt wird der **Umfang** festgelegt:

| Bedienebene | Inhalt | Standard |
|---|---|---|
| Info | Messwerte und Zustände | immer aktiv |
| Betreiber | Betriebswahl, Sollwerte, Programme, Warmwasser | immer aktiv |
| Service | Heizkurve, Grenzwerte, Estrichprogramm | angelegt, deaktiviert |
| Werk | Verbrennungsregelung, Zündung, Antriebe | nicht angelegt |

Dazu zwei Schalter:

- **Service-/Werksebene sofort aktivieren** – ohne Haken werden die Entitäten
  angelegt, bleiben aber deaktiviert und erzeugen keine Abfragen.
- **Service-/Werksebene bedienbar machen** – ohne Haken werden diese Parameter
  nur angezeigt. Erst mit Haken lassen sie sich schreiben.

Beides ist jederzeit über *Konfigurieren* an der Integration änderbar, ebenso
das Abfrageintervall. Nach einer Änderung liest die Integration die Anlage neu
ein.

Beim ersten Start wird die Anlage einmal vollständig eingelesen. Das Ergebnis
wird gespeichert und übersteht Neustarts.

## Dienste

| Dienst | Wirkung |
|---|---|
| `heatnexus.set_time_program` | Zeitprogramm setzen (`switch_points` mit `weekdays`, oder `blocks` für getrennte Wochenpläne) |
| `heatnexus.set_current_temp_compensation` | Behaglichkeitskorrektur eines Heizkreises |
| `heatnexus.rediscover` | Anlage neu einlesen, z. B. nach Umbauten |

```yaml
service: heatnexus.set_time_program
target:
  entity_id: sensor.heizkreis_programm_1
data:
  weekdays: ["Mo", "Di", "Mi", "Do", "Fr"]
  switch_points:
    - {time: "06:00", value: 21}
    - {time: "22:00", value: 18}
```

## Dashboard

Vorlagen für Gesamtübersicht, Bedienkarten und ein Anlagenschaubild liegen unter
[`dashboards/`](dashboards/).

## Dokumentation

| Datei | Inhalt |
|---|---|
| [`docs/API.md`](docs/API.md) | Geräte-API und OID-Aufbau |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Aufbau der Integration |
| [`docs/DATAPOINTS.md`](docs/DATAPOINTS.md) | Datenpunkte je Funktionstyp |
| [`CHANGELOG.md`](CHANGELOG.md) | Versionshistorie |

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
ruff check custom_components tests tools
```

Anlage auslesen – unter Windows genügt ein Doppelklick auf `tools/probe.cmd`,
sonst:

```bash
python tools/heatnexus_probe.py                       # geführter Modus
python tools/heatnexus_probe.py all 192.0.2.10 192.0.2.11
```

Details in [`tools/README.md`](tools/README.md).

## Hinweis

Die Integration schreibt auf eine Heizungsanlage. Steuerbare Datenpunkte der
Betreiberebene sind geprüft, Serviceparameter sind bewusst deaktiviert.
Nutzung auf eigene Verantwortung.
