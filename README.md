![HeatNexus](https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/banner_small.png)

[![Validate](https://github.com/xIceTea/HeatNexus/actions/workflows/validate.yml/badge.svg)](https://github.com/xIceTea/HeatNexus/actions/workflows/validate.yml) [![Tests](https://github.com/xIceTea/HeatNexus/actions/workflows/tests.yml/badge.svg)](https://github.com/xIceTea/HeatNexus/actions/workflows/tests.yml) ![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5) ![Home Assistant 2025.6+](https://img.shields.io/badge/Home%20Assistant-2025.6%2B-03a9f4) [![Lizenz: GPL-3.0](https://img.shields.io/badge/Lizenz-GPL--3.0-blue)](LICENSE)

[![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=xIceTea&repository=HeatNexus&category=integration) [![Integration hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=heatnexus)

**Deutsch** · [English](README.en.md)

# HeatNexus

Heizungen in Home Assistant – lokal, vollständig, ohne Cloud.

## Erste Schritte

**[Loslegen mit HeatNexus](https://xicetea.github.io/HeatNexus/)**

Alle Anleitungen stehen auf der Projektseite: Einrichtung, Bedienung,
Fehlersuche und die vollständige Referenz auf einer Seite.

[Einrichtung](https://xicetea.github.io/HeatNexus/ANLEITUNG#einrichtung) ·
[Passt das zu meiner Anlage?](https://xicetea.github.io/HeatNexus/#anlagen) ·
[Fehlersuche](https://xicetea.github.io/HeatNexus/ANLEITUNG#fehlersuche) ·
[Datenpunkte](https://xicetea.github.io/HeatNexus/ANLEITUNG#datenpunkte)

![Anlagenschaubild in Bewegung: Kessel startet, Puffer lädt, Heizkreis und Warmwasser werden warm](https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_animation.gif)

*Das Anlagenschaubild wird aus den erkannten Anlagenteilen zusammengesetzt –
  wer zwei Puffer hat, sieht zwei. Es steht nicht still: Die Pumpen drehen sich,
  die Bänder auf Vor- und Rücklauf zeigen die Förderrichtung, der Puffer meldet
  „lädt“ und „entlädt“, Speicher und Heizkörper färben sich nach ihren Fühlern.
  Beispielwerte.*

[![Rundgang durch die Oberfläche: Übersicht, Störung, Steuerung, Wartung, Zeitprogramme](https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/panel_rundgang.gif)](https://xicetea.github.io/HeatNexus/ANLEITUNG#oberflaeche)

*Die eigene Oberfläche in der Seitenleiste: Übersicht, anliegende Störung,
  Steuerung mit laufender Warmwasserladung, Wartung, Zeitprogramme. Ausführlich
  in [Die Oberfläche](https://xicetea.github.io/HeatNexus/ANLEITUNG#oberflaeche) – Beispielwerte,
  aufgenommen aus der ausgelieferten Oberfläche.*

## Für welche Anlagen

> **HeatNexus spricht die Regelung von Windhager an** – nicht ein einzelnes
> Kesselmodell. Voraussetzung ist ein **InfoWIN Touch** mit Netzwerkanschluss,
> erreichbar im eigenen Netz. Gelesen und gesteuert wird direkt über dessen
> HTTP-Schnittstelle: Kessel, Heizkreise, Puffer, Warmwasser und Zirkulation,
> einschließlich Info-, Betreiber- und Serviceebene.
>
> **Der Test dauert eine halbe Minute:** `http://<IP der Anlage>` im Browser
> öffnen. Kommt die Weboberfläche des InfoWIN Touch, ist der Weg frei.

**Geprüft heißt geprüft.** Die Tabelle unterscheidet drei Stufen — was an
echter Hardware läuft, was ein fremder Abzug belegt, und was bisher nur in der
Datenbank steht:

| | Anlagenteil | Stand |
|---|---|---|
| 🟢 | PuroWIN – Hackgut | an der Anlage geprüft |
| 🟢 | UML / UMLZ Heizkreismodul | an der Anlage geprüft |
| 🟢 | B-PLMi Pufferlademodul | an der Anlage geprüft |
| 🟢 | ZSP Pumpen- und Relaismodul | an der Anlage geprüft |
| 🔵 | BioWIN, BioWIN 2 – Pellets | an einer fremden Anlage geprüft |
| ⚪ | Wärmepumpe, E-Heizung | eingebunden, ungeprüft |
| ⚪ | Gas- und Ölkessel | eingebunden, ungeprüft |
| ⚪ | Solar, Kaskade, Umschaltung | eingebunden, ungeprüft |
| ⚪ | Infinity PLUS Heizkreis und Warmwasser | eingebunden, ungeprüft |

„Eingebunden" heißt: Die Funktion ist in der mitgelieferten Datenbank
beschrieben und wird mit Namen, Einheiten und Auswahlwerten erkannt – nur stand
noch keine solche Anlage zum Nachmessen bereit.

„An einer fremden Anlage geprüft" heißt: Jemand hat einen Abzug seiner Anlage
beigesteuert, die Erkennung ist daran belegt und die Werte stehen in Home
Assistant. Nicht geprüft ist das Bedienen – Schalter, Sollwerte und
Zeitprogramme dieses Anlagenteils sind an echter Hardware noch nicht
ausprobiert.

Welcher Funktionstyp was ist und welche Datenpunkte er führt, steht vollständig
in [Datenpunkte](https://xicetea.github.io/HeatNexus/ANLEITUNG#datenpunkte).

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
- **Anlagenschaubild als Lovelace-Karte** für eigene Dashboards, mit Werteliste
  daneben, wählbaren Anlagenteilen und fünf Farbsätzen.
- **Dashboard und Automations-Vorlagen** kommen mit und bauen sich aus dem,
  was die Anlage liefert.
- **LON-Bus als zweite Quelle**: Netzwerkvariablen werden erkannt, benannt und
  je Anlage zugeschaltet.
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

| Zugang | Passwort ab Werk |
|---|---|
| `USER` | `123` |
| `Service` | `123` |

An der geprüften Anlage sehen **beide Zugänge über die Schnittstelle dasselbe**,
auch die Fachparameter. Die Trennung in Bedienebenen gilt am Bediengerät; was
in Home Assistant erscheint, entscheidet der Umfang im nächsten Schritt. Für
andere Baureihen ist das nicht belegt, deshalb bleibt der Zugang wählbar.

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
alles sofort da. Vollständig neu eingelesen wird nach einer Änderung des Umfangs
oder über den Dienst `heatnexus.rediscover`. Eine neue Fassung von HeatNexus
löst das **nicht** aus – sonst kostete jede Aktualisierung die volle Wartezeit
von vorn. Stattdessen ist der gespeicherte Stand sofort da, und was neu
dazugekommen ist, ergänzt HeatNexus im Hintergrund.

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
Reiter für Reiter in [Die Oberfläche](https://xicetea.github.io/HeatNexus/ANLEITUNG#oberflaeche):

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

Über das Werkzeugmenü (⋮) rechts in der Kopfzeile lassen sich die Karten
umsortieren und die Dashboard-Vorlage abrufen. Der Farbsatz – Dunkel, Hell,
Terrakotta, Petrol oder Pflaume – steht in den Einstellungen der Anordnung und
gilt für Oberfläche und Schaubild gemeinsam.

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

### Das Anlagenschaubild als eigene Karte

Für ein selbst gebautes Dashboard gibt es das Schaubild als Lovelace-Karte.
Sie steht nach der Einrichtung in der Kartenauswahl unter **HeatNexus
Anlagenschaubild** – kein Hinzufügen als Ressource nötig.

Einstellbar sind: welche Anlage (oder alle), der Farbsatz, die Schriftgröße der
Werte, ob sich Pumpen und Strömung bewegen, welche Anlagenteile gezeichnet
werden, welche Werte im Bild stehen und welche in einer Liste daneben oder
darunter.

### Ein eigenes Dashboard daraus machen

Das mitgelieferte Dashboard entsteht bei jedem Öffnen neu; eigene Änderungen
daran überleben das nicht, auch nicht über den YAML-Editor. Wer es als
Ausgangspunkt nehmen will, bekommt es als Text:

*Eigene Oberfläche → ⋮ → **Dashboard-Vorlage*** – oder, ohne die Oberfläche,
*Entwicklerwerkzeuge → Aktionen → **HeatNexus: Dashboard als YAML ausgeben***

Den zurückgegebenen Text in ein neues, leeres Dashboard einfügen
(*Einstellungen → Dashboards → Hinzufügen*, dann ⋮ → *Rohkonfigurations-Editor*).
Ab da gehört es dir und bleibt, wie du es einrichtest — es wächst allerdings
auch nicht mehr mit, wenn die Anlage sich ändert.

## Automations-Vorlagen

Sechs Blueprints werden mitgeliefert und liegen nach der Einrichtung unter
*Einstellungen → Automationen & Szenen → Blueprints* bereit – ohne Import aus
dem Netz:

| Vorlage | Zweck |
|---|---|
| Störung melden | Meldung bei Störung, Erinnerung in festem Abstand, Entwarnung |
| Wartungswarnung mit Erinnerung | Vorwarnung, Warnung und Erinnerung für eine Restlaufzeit (Asche, Reinigung, Wartung) |
| Brennstoffvorrat niedrig | Meldung, wenn der Vorratsbehälter leer meldet, mit Erinnerung |
| Betriebsdauer erfassen | Misst, wie lange ein Anlagenteil ununterbrochen läuft |
| Heizkreis bei Abwesenheit absenken | Absenken bei Abwesenheit, Rückstellen bei Rückkehr |
| Legionellenschutz nachbilden | Fährt den Speicher in festem Turnus über die Einmalladung hoch — für Regler ohne eigene Legionellenschutzfunktion |

Was bei einem Ereignis passieren soll, gibt die jeweilige Automation vor –
Benachrichtigung, Ansage, Anruf, beliebige Aktion. Die Störungsvorlage wertet
den Sensor „Störung gemeldet" aus, nicht den angezeigten Text; sie hängt damit
an keiner Formulierung.

## Dokumentation

| Seite | Inhalt |
|---|---|
| [Die Oberfläche](https://xicetea.github.io/HeatNexus/ANLEITUNG#oberflaeche) | die eigene Oberfläche, Reiter für Reiter |
| [Schaubild als Karte](https://xicetea.github.io/HeatNexus/ANLEITUNG#karte) | das Anlagenschaubild als Lovelace-Karte |
| [Geräteschnittstelle](https://xicetea.github.io/HeatNexus/ANLEITUNG#geraeteschnittstelle) | Geräte-API und OID-Aufbau |
| [Aufbau](https://xicetea.github.io/HeatNexus/ANLEITUNG#aufbau) | Aufbau der Integration |
| [Datenpunkte](https://xicetea.github.io/HeatNexus/ANLEITUNG#datenpunkte) | alle Datenpunkte je Funktionstyp, mit Bedienebene |
| [Auswahlwerte](https://xicetea.github.io/HeatNexus/ANLEITUNG#aufzaehlungen) | alle Auswahlwerte mit ihrer Bedeutung |
| [`CHANGELOG.md`](CHANGELOG.md) | Versionshistorie |

Datenpunkte und Auswahlwerte werden aus der mitgelieferten Geräte-Datenbank
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

## Unterstützen

HeatNexus entsteht in der Freizeit an einer echten Anlage. Wer die Arbeit
unterstützen möchte:

<p align="center">
  <a href="https://buymeacoffee.com/xicetea">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png"
         alt="Buy Me A Coffee" height="60">
  </a>
</p>

Genauso hilfreich und kostenlos: ein Fehlerbericht mit Diagnose-Export,
besonders von Anlagentypen, die hier als *unterstützt, ungeprüft* stehen.

## Lizenz

HeatNexus steht unter der [GNU General Public License v3.0](LICENSE). Wer die
Integration abwandelt und weitergibt, gibt sie unter derselben Lizenz weiter —
mit Quelltext. Name und Logo sind davon ausgenommen, siehe [`NOTICE`](NOTICE).

