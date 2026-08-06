<p align="center">
  <img src="assets/banner_small.png" alt="HeatNexus" width="820">
</p>

<p align="center">
  <a href="https://github.com/xIceTea/HeatNexus/actions/workflows/validate.yml"><img src="https://github.com/xIceTea/HeatNexus/actions/workflows/validate.yml/badge.svg" alt="Validate"></a>
  <a href="https://github.com/xIceTea/HeatNexus/actions/workflows/tests.yml"><img src="https://github.com/xIceTea/HeatNexus/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <img src="https://img.shields.io/badge/HACS-Custom-41BDF5" alt="HACS Custom">
  <img src="https://img.shields.io/badge/Home%20Assistant-2025.6%2B-03a9f4" alt="Home Assistant 2025.6+">
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=xIceTea&amp;repository=HeatNexus&amp;category=integration"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="In HACS öffnen"></a>
  <a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=heatnexus"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Integration hinzufügen"></a>
</p>

<p align="center"><strong>Deutsch</strong> · <a href="README.en.md">English</a></p>

# HeatNexus

Heizungen in Home Assistant – lokal, vollständig, ohne Cloud.

Die Anlage wird direkt über ihre HTTP-API im Netzwerk gelesen und gesteuert.
Abgedeckt sind Kessel, Heizkreise, Puffer, Warmwasser und Zirkulation,
einschließlich Info-, Betreiber- und Serviceebene.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/anlagenschema_animation.gif">
    <img src="assets/anlagenschema_animation_hell.gif" alt="Anlagenschaubild in Bewegung: Kessel startet, Puffer lädt, Heizkreis und Warmwasser werden warm" width="820">
  </picture>
</p>

<p align="center">
  <em>Das Anlagenschaubild wird aus den erkannten Anlagenteilen zusammengesetzt –
  wer zwei Puffer hat, sieht zwei. Es steht nicht still: Die Pumpen drehen sich,
  die Bänder auf Vor- und Rücklauf zeigen die Förderrichtung, der Puffer meldet
  „lädt“ und „entlädt“, Speicher und Heizkörper färben sich nach ihren Fühlern.
  Beispielwerte.</em>
</p>

<p align="center">
  <a href="docs/OBERFLAECHE.md"><img src="assets/panel_rundgang.gif" alt="Rundgang durch die Oberfläche: Übersicht, Störung, Steuerung, Wartung, Zeitprogramme" width="820"></a>
</p>

<p align="center">
  <em>Die eigene Oberfläche in der Seitenleiste: Übersicht, anliegende Störung,
  Steuerung mit laufender Warmwasserladung, Wartung, Zeitprogramme. Ausführlich
  in <a href="docs/OBERFLAECHE.md">docs/OBERFLAECHE.md</a> – Beispielwerte,
  aufgenommen aus der ausgelieferten Oberfläche.</em>
</p>

## Unterstützte Geräte

| Anlagenteil | Stand |
|---|---|
| PuroWIN – Hackgut | an der Anlage geprüft |
| UML / UMLZ Heizkreismodul | an der Anlage geprüft |
| B-PLMi Pufferlademodul | an der Anlage geprüft |
| ZSP Pumpen- und Relaismodul | an der Anlage geprüft |
| BioWIN, BioWIN 2 – Pellets | eingebunden, ungeprüft |
| Wärmepumpe, E-Heizung | eingebunden, ungeprüft |
| Gas- und Ölkessel | eingebunden, ungeprüft |
| Solar, Kaskade, Umschaltung | eingebunden, ungeprüft |
| Infinity PLUS Heizkreis und Warmwasser | eingebunden, ungeprüft |

„Eingebunden" heißt: Die Funktion ist in der mitgelieferten Datenbank
beschrieben und wird mit Namen, Einheiten und Auswahlwerten erkannt – nur stand
noch keine solche Anlage zum Nachmessen bereit. Welcher Funktionstyp was ist und
welche Datenpunkte er führt, steht vollständig in
[`docs/DATAPOINTS.md`](docs/DATAPOINTS.md).

Alles Weitere wird über die allgemeine Erkennung eingebunden: Was die Steuerung
liefert, erscheint auch in Home Assistant. Rückmeldungen zu nicht gelisteten
Geräten sind willkommen – der Diagnose-Export der Integration reicht dafür.

## Funktionsumfang

- **Automatische Erkennung** aller freigeschalteten Funktionen der Anlage.
  Nicht vorhandene Datenpunkte werden entfernt, schreibgeschützte nur lesend
  angelegt.
- **Wertebereiche vom Gerät**: Minimum, Maximum, Schrittweite, Einheit und
  erlaubte Auswahlwerte stammen aus den Metadaten der Anlage.
- **Thermostat je Heizkreis** mit Betriebswahl, Behaglichkeitskorrektur und
  befristetem Komfort-Sollwert.
- **Zeitprogramme** für Heizung, Warmwasser und Zirkulation lesen und schreiben –
  in der eigenen Oberfläche als Wochenraster, mit Editor für Wochentage und
  Schaltzeiten.
- **Störungen im Klartext** mit Code, Art und Handlungsempfehlung.
- **Serviceebene** vollständig verfügbar, standardmäßig deaktiviert und pro
  Entity zuschaltbar.
- **Eigene Oberfläche** in der Seitenleiste: Anlagenschaubild, Kennwerte,
  Systemstatus, Heizkreise, Warmwasser, Störungen, Verlauf und Schnellzugriff
  auf einer Seite; dazu eigene Reiter für Steuerung, Wartung, Verlauf und
  Zeitprogramme.
- **Anlagenschaubild** aus den erkannten Anlagenteilen gezeichnet, mit
  laufenden Pumpen und den Live-Werten darauf. Die Art des Wärmeerzeugers –
  Hackgut, Pellets, Scheitholz, Wärmepumpe, Gas/Öl – wird erkannt und lässt
  sich je Anlage übersteuern.
- **Dashboard und Automations-Vorlagen** kommen mit und bauen sich aus dem,
  was die Anlage liefert.
- Mehrere Anlagen parallel.

## Installation

### Über HACS

[![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=xIceTea&repository=HeatNexus&category=integration)

Der Knopf trägt das Repository in HACS ein und öffnet die Installation direkt.
Danach Home Assistant neu starten.

Von Hand geht es genauso: HACS → Integrationen → ⋮ → **Benutzerdefinierte
Repositories** → Repository-URL eintragen, Kategorie *Integration* →
„HeatNexus" installieren → Home Assistant neu starten.

### Ohne HACS

Ordner `custom_components/heatnexus` nach `<config>/custom_components/heatnexus`
kopieren und Home Assistant neu starten.

### Einrichtung

[![Integration hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=heatnexus)

Oder von Hand: Einstellungen → Geräte & Dienste → Integration hinzufügen →
**HeatNexus**. Erforderlich sind die IP-Adresse der Anlage, der Zugang und das
zugehörige Passwort.

#### Zugang und Passwort

Die Schnittstelle ist dieselbe, die auch die Weboberfläche der Anlage benutzt.
Ab Werk kennt die Steuerung zwei Zugänge:

| Zugang | Passwort ab Werk | Umfang |
|---|---|---|
| `USER` | `123` | Info- und Betreiberebene |
| `Service` | `123` | zusätzlich die Fachparameter |

Ob der Zugang stimmt, lässt sich ohne Home Assistant prüfen: `http://<IP der
Anlage>` im Browser öffnen. Kommt die Weboberfläche des InfoWIN Touch, passt die
Kombination.

Wer Fachparameter auslesen oder schreiben will, wählt bei der Einrichtung
`Service`. Ein abweichender Benutzername lässt sich im selben Feld eintippen.

**Passwort ändern** lässt sich an zwei Stellen, beide führen zum selben
Parameter: direkt am InfoWIN Touch oder in dessen Weboberfläche unter
*Passwort*. Ein dort gesetztes Passwort gilt sofort auch für die Schnittstelle
– danach muss es in Home Assistant über *Neu anmelden* nachgezogen werden.

**Passwort unbekannt oder plötzlich falsch?** Ist die Anlage bei Windhager
Connect registriert, lässt sich das aktuelle Webserver-Passwort dort ablesen.
Nach der Anmeldung die Anlage auswählen – die Adresse endet dann auf
`/management`. Dieses Wort durch `settings` ersetzen:

```text
https://connect.windhager.com/systems/<Kennung der Anlage>/management
https://connect.windhager.com/systems/<Kennung der Anlage>/settings
```

Auf der Einstellungsseite steht das Passwort im Klartext und lässt sich dort
auch ändern.

> **Windhager-App:** Wird die Anlage mit myComfort / myConnect verbunden,
> vergibt Windhager ein eigenes Passwort; die Werksangaben oben gelten dann
> nicht mehr. Das ist kein dauerhafter Ausschluss – das Passwort lässt sich wie
> oben beschrieben ablesen oder neu setzen, und danach laufen App und HeatNexus
> wieder.

> **Nur HTTP:** Die Steuerung antwortet ausschließlich unverschlüsselt auf
> Port 80; einen HTTPS-Zugang gibt es lokal nicht (geprüft am PuroWIN mit
> InfoWIN Touch). Das Passwort selbst geht dank Digest-Authentifizierung nicht
> im Klartext über die Leitung, die Messwerte schon. HeatNexus gehört deshalb
> ins eigene Netz, nicht ins Internet.

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

Dort steht je Anlage auch der **Wärmeerzeuger**. Er wirkt nur auf die Zeichnung
im Anlagenschaubild und ändert weder Entitäten noch Werte. Ab Werk steht er auf
*automatisch erkennen*: HeatNexus nimmt zuerst den Brennstoff, den die Anlage
meldet, sonst den Funktionstyp, sonst den Namen der Funktion. Passt das Ergebnis
nicht, lässt es sich hier fest setzen.

#### Die erste Minute

Nach dem Einrichten steht die Integration sofort da, aber noch **nicht
vollständig**: Zuerst entsteht der Grundstock an Entitäten, dann liest
HeatNexus die Anlage im Hintergrund komplett ein. Je nach Anlage dauert das
30 bis 120 Sekunden, und in dieser Zeit kommen laufend weitere Entitäten
dazu – aus einer Handvoll werden je nach Umfang schnell mehrere hundert.

Eine Benachrichtigung begleitet den Vorgang und nennt am Ende die gefundene
Anzahl. Es ist also kein Grund zur Sorge, wenn direkt nach dem Einrichten erst
wenige Werte zu sehen sind.

Das Ergebnis wird gespeichert und übersteht Neustarts; beim nächsten Start ist
alles sofort da. Neu eingelesen wird nur nach einer Änderung des Umfangs, nach
einer neuen Version oder über den Dienst `heatnexus.rediscover`.

## Dienste

| Dienst | Wirkung |
|---|---|
| `heatnexus.set_time_program` | Zeitprogramm setzen (`switch_points` mit `weekdays`, oder `blocks` für getrennte Wochenpläne) |
| `heatnexus.set_vorgabe` | befristete Raumtemperatur-Vorgabe eines Heizkreises („Eco / Comfort") |
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

## Eigene Oberfläche

Neben dem Dashboard bringt HeatNexus eine eigene Seite in der Seitenleiste mit.
Sie zeigt die Anlage als Ganzes statt als Kachelsammlung – im Bild ganz oben,
Reiter für Reiter in [docs/OBERFLAECHE.md](docs/OBERFLAECHE.md):

- **Anlagenschaubild** mit Vor- und Rücklauf, den Live-Werten und Pumpen, die
  sich drehen, solange sie laufen.
- **Kennwerte** je Anlagenteil – ein Leitwert je Funktion, wie am Bediengerät
  der Anlage.
- **Systemstatus**: Betriebszustand, Außentemperatur, Kesselleistung,
  Brennstoff, Vorratsbehälter, Restlaufzeiten.
- **Heizkreise und Warmwasser** mit Betriebswahl und Sollwert direkt bedienbar.
- **Störungen im Klartext**, **Verlauf** und **Schnellzugriff** auf die
  häufigen Eingriffe, jeweils mit Rückfrage, wo ein Fehlgriff Arbeit macht.
- **Zeitprogramme** als Wochenraster: je Programm sieben Zeilen, darin die
  Schaltzeiten als Balken. Bearbeitet wird in Blöcken – Wochentage anhaken,
  Schaltzeiten setzen –, gespeichert wird das ganze Programm auf einmal, so wie
  die Anlage es führt.

Ein „?" neben Karten und Bedienelementen erklärt, was ein Wert bedeutet und was
eine Aktion auslöst. Beides – Oberfläche und Erklärungen – lässt sich unter
*Konfigurieren → Allgemein* abschalten.

Die Aufteilung entsteht in Home Assistant, nicht im Browser: Was die Anlage
liefert, erscheint; was fehlt, entfällt.

## Dashboard

Ein Dashboard **Heizung** erscheint nach der Einrichtung von selbst in der
Seitenleiste. Es wird aus den tatsächlich gefundenen Geräten gebaut – keine
Entitäts-IDs eintragen, kein YAML kopieren:

- **Übersicht** – je Anlagenteil die wichtigsten Werte, in fachlicher
  Reihenfolge (Kessel, Puffer, Heizkreis, Warmwasser, Zirkulation), dazu die
  Störungsmeldungen. Bei mehreren Anlagen steht die Anlage in der Überschrift,
  damit zwei gleich benannte Anlagenteile unterscheidbar bleiben.
- **Anlage** – ein Schaubild je Anlage: Kessel, Puffer, Heizkreise, Warmwasser
  und Zirkulation, verbunden durch Vor- und Rücklauf, mit den Live-Werten
  darauf. Gezeichnet wird, was gefunden wurde – bei zwei Puffern erscheinen
  zwei.
- **Wartung** – Restlaufzeiten bis Ascheentleerung, Hauptreinigung und Wartung
  als Rundinstrument, dazu Brennstoff, Vorratsbehälter und Zählerstände.
- **Auswertung** – Zuwachs der Zähler *heute* und *diesen Monat*
  (Brennerstarts, Betriebsstunden) sowie Temperaturverläufe der letzten
  48 Stunden je Anlagenteil.
- **Je Anlagenteil eine Ansicht**, gegliedert in Bedienung, Messwerte,
  Einstellungen und Diagnose.

Fehlt ein Anlagenteil, entfällt der Block. Wird der Umfang später geändert,
passt sich das Dashboard beim nächsten Öffnen an. Abschalten lässt es sich
unter *Konfigurieren → Allgemein*.

Wer lieber selbst baut: Vorlagen für Gesamtübersicht, Bedienkarten und ein
Anlagenschaubild liegen unter [`dashboards/`](dashboards/).

## Automations-Vorlagen

Fünf Blueprints werden mitgeliefert und liegen nach der Einrichtung unter
*Einstellungen → Automationen & Szenen → Blueprints* bereit – ohne Import aus
dem Netz:

| Vorlage | Zweck |
|---|---|
| Störung melden | Meldung bei Störung, Erinnerung in festem Abstand, Entwarnung |
| Wartungswarnung mit Erinnerung | Vorwarnung, Warnung und Erinnerung für eine Restlaufzeit (Asche, Reinigung, Wartung) |
| Brennstoffvorrat niedrig | Meldung, wenn der Vorratsbehälter leer meldet, mit Erinnerung |
| Betriebsdauer erfassen | Misst, wie lange ein Anlagenteil ununterbrochen läuft |
| Heizkreis bei Abwesenheit absenken | Absenken bei Abwesenheit, Rückstellen bei Rückkehr |

Was bei einem Ereignis passieren soll, gibt die jeweilige Automation vor –
Benachrichtigung, Ansage, Anruf, beliebige Aktion. Die Störungsvorlage wertet
das Attribut `stoerung_aktiv` aus, nicht den angezeigten Text; sie hängt damit
an keiner Formulierung.

## Dokumentation

| Datei | Inhalt |
|---|---|
| [`docs/OBERFLAECHE.md`](docs/OBERFLAECHE.md) | die eigene Oberfläche, Reiter für Reiter |
| [`docs/API.md`](docs/API.md) | Geräte-API und OID-Aufbau |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Aufbau der Integration |
| [`docs/DATAPOINTS.md`](docs/DATAPOINTS.md) | alle Datenpunkte je Funktionstyp, mit Bedienebene |
| [`docs/ENUMS.md`](docs/ENUMS.md) | alle Auswahlwerte mit ihrer Bedeutung |
| [`CHANGELOG.md`](CHANGELOG.md) | Versionshistorie |

`DATAPOINTS.md` und `ENUMS.md` werden aus der mitgelieferten Geräte-Datenbank
erzeugt (`python tools/build_datenpunkte_doku.py`) und von einem Test gegen sie
geprüft – sie können also nicht veralten.

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
