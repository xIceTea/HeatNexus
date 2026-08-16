# Architektur

![Aufbau: die Heizung liefert über HTTP an client.py, das die Descriptor-Liste erzeugt; __init__.py führt Coordinator, Cache und Dienste; die Plattformen filtern die Liste nach dem Feld type](assets/aufbau.svg)

## Descriptor-Liste als zentrale Schnittstelle

`client.py` kapselt das gesamte Gerätewissen und erzeugt flache Beschreibungen:

```python
{"id": "0702bb000002-0-0-7-0",            # unique_id: <neuronId>-<fctId>-<gn>-<mn>-<idx>
 "alt_id": "…",                           # frühere Kennung, nur für die Umstellung
 "oid": "/1/60/0/0/7/0",
 "name": "Kesseltemperatur Ist",
 "type": "temperature",                   # bestimmt die Plattform
 "unit": "°C", "device_class": None, "state_class": None,
 "category": None, "icon": None,
 "min": None, "max": None, "step": None,
 "write_prot": True,
 "device_id": "0702bb000002-0",           # HA-Gerät
 "device_name": "PuroWIN",
 "fct_type": 25}                          # Funktionstyp, ordnet das Dashboard
```

Die Kennung hängt an der **`neuronId`** – der Seriennummer des Bausteins, die
jeder Knoten in der Struktur meldet. Sie übersteht einen Adresswechsel der
Anlage; nur wenn ein Knoten keine meldet, tritt die Adresse als Notnagel ein.
Das `alt_id` jedes Deskriptors trägt die frühere, adressgebundene Kennung, mit
der `migration.py` bestehende Registrierungseinträge umschreibt.

Jede Plattform filtert `coordinator.data["devices"]` nach `type`. Eine neue
Plattform benötigt daher nur einen neuen `type` im Client, ein Modul, das darauf
filtert, und den Eintrag in `PLATFORMS`.

Die Felder und ihre Vorgaben stehen an **einer** Stelle
(`client.DESKRIPTOR_VORGABE`); die drei Quellen — kuratierte Tabelle,
Menü-Erkennung, LON-Adressraum — bauen ihre Beschreibung über
`client._deskriptor()`. Vorher standen sie dreimal nebeneinander und liefen
auseinander: Zwei führten `level` und `enabled_default`, die dritte nicht.

## Ablauf beim Start

1. **Cache** – RAM (Reload) → Platte (`Store`, Neustart) → vollständige Discovery.
   Verworfen wird der Stand bei geändertem Umfang (Bedienebenen, Zugang,
   Schalter), bei einem Alter über 30 Tagen oder durch den Dienst
   `heatnexus.rediscover`. Eine **neue Fassung der Integration verwirft ihn
   bewusst nicht**: Das kostete nach jeder Aktualisierung einen vollen Neuabzug
   von 30 bis 120 Sekunden. Der gespeicherte Stand wird sofort hergestellt, ein
   vollständiger Abzug läuft im Hintergrund nach und ergänzt, was neu ist.
   Deskriptoren laufen beim Wiederherstellen durch `helpers.messgroesse` –
   geänderte Einheiten und Geräteklassen wirken damit ohne Neuabzug, eine
   geänderte Plattformauflösung nicht.
2. **Discovery** – `/1` liefert Knoten und Funktionen. Je Funktion entstehen
   Entities aus den kuratierten Tabellen in `const.py` (`FCT_ENTITY_MAP`) und aus
   der Geräte-Datenbank (`device_db.json`, Ebenen `info`/`operate`/`service`).
   Heizkreise erhalten zusätzlich eine Climate-Entity, Knoten mit `FE01msg`
   je einen Meldungs- und Klartextsensor.
3. **Metadaten** – jeder Datenpunkt wird einmal gelesen: Typauflösung,
   Wertebereiche, Einheiten und Enum-Listen kommen vom Gerät. Nicht vorhandene
   Datenpunkte werden entfernt, schreibgeschützte als Nur-Lese-Entity angelegt.
4. **Poll-Set** – standardmäßig aktive Entities plus die Climate-Datenpunkte.
   Entities der Serviceebene sind deaktiviert und melden ihre OID erst beim
   Aktivieren zum Polling an.

Die Einrichtung wartet nur auf die Grunddaten (`async_init_basic()`, eigenes
Zeitlimit `INIT_TIMEOUT`, getrennt vom Zeitlimit des Pollings). Der Vollabzug
läuft danach als Hintergrundaufgabe und meldet die zusätzlich gefundenen
Entities nach.

Wird der Umfang verkleinert, werden die betroffenen Entities **stillgelegt,
nicht gelöscht** – eigene Namen, Bereichszuordnung und Verlauf bleiben damit
erhalten und leben beim Wiederdazuwählen weiter.

## LON-Netzwerkvariablen

Jeder Knoten meldet neben seinen Funktionen einen Bereich `NV's` mit
`fctType -1`: den LON-Adressraum unter `/1/<knoten>/32`. Dort **deutet die
Steuerung die Adresse um** – der Member ist der `nvIndex`, die Gruppe fällt
weg, und die Einträge führen keine `OID`. Deshalb läuft er nicht durch die
gewöhnliche Erkennung, sondern über `client._lese_nv`.

Was ihn wertvoll macht: Die Namen kommen aus den Funktionsblöcken des Bus
(`WET` Wärmeerzeuger, `LX` Kreis, `M` Mischer, `GB` Gebläse, `PMX`
Verbrennungsregler, `OXY` Lambdasonde, `FS` Förderung, `FWN` Wartung) und
bedeuten an jeder Baureihe dasselbe. Eine Anlage, für die es keine kuratierte
Adresstabelle gibt, bekommt darüber trotzdem benannte Werte.

`lon.py` hält die Zuordnung Name → Klarname, Klassen und kanonischer
Schlüssel. Was dort nicht steht, wird trotzdem angelegt: mit dem Namen der
Anlage und ab Werk deaktiviert.

**Die Größe kommt vom Standard, der Begriff aus der Tabelle.** Jeder Eintrag
führt einen `snvtName` – den LonMark-Typ. Er sagt Einheit und Statistikklasse,
ohne dass der Name bekannt sein muss: `SNVT_temp_p` ist eine Temperatur,
`SNVT_count` ein Zählerstand. Damit bekommt auch ein unbenannter Wert eine
brauchbare Anzeige. `SNVT_address` und `SNVT_obj_request` sind Innenleben des
Bus und werden gar nicht erst angelegt; `SNVT_obj_status` bleibt als Diagnose,
weil er an manchen Knoten die einzige Auskunft ist.

Gemessen: eine fremde BioWIN führt 99 Namen, die eigene PuroWIN 133 – mit
teils anderen Blöcken (`BUF` Pufferladung, `RLH` Rücklaufanhebung, `WZP`
Zirkulation, `TVSTPT` Raumtemperatur). Ein Wert, dessen kanonischer Schlüssel schon
von einem Datenpunkt belegt ist, bleibt ebenfalls deaktiviert – entschieden
wird nach `_apply_metadata`, weil erst dann feststeht, welche Datenpunkte die
Anlage wirklich führt.

Geschrieben wird nichts: `nvi`-Variablen sind Eingänge der Regelung zwischen
den Knoten.

Ein Knoten ohne brauchbare Funktion besteht nur aus diesem Bereich – das
Bedienteil (`MB6611 LOP`) ist so einer. Er bekommt sein eigenes Gerät; Knoten
mit Funktion hängen ihre Netzwerkvariablen an deren Gerät.

## Zeichensatz

Die Steuerung antwortet nicht in UTF-8. Von Hand vergebene Namen kommen in der
DOS-Zeichentabelle der Anlage; das „ü" liegt dort auf einem Byte, das CP1252
nicht kennt. `client._decode` probiert deshalb der Reihe nach `utf-8`,
`cp1252`, `cp850` und zuletzt `latin-1`, das jedes Byte abbilden kann.

## Dashboard

`dashboard.py` baut die Lovelace-Konfiguration **in Home Assistant** aus der
Geräte- und Entitätsregistrierung und liefert sie fertig aus; bei jedem Öffnen
neu. Die Reihenfolge der Abschnitte kommt aus dem Funktionstyp (`FCT_RANG`:
Kessel, Puffer, Heizkreis, Warmwasser, Zirkulation), unbekannte Typen stehen
hinten. Ein Frontend-Modul gibt es bewusst nicht: Eine Strategie im Browser
steht erst zur Verfügung, wenn die Seite sie geladen hat – nach einem Neustart
ist das nicht der Fall.

## Anlagenschaubild

`schema.py` setzt das Schaubild aus **SVG-Dateien** in `anlagenteile/`
zusammen und übergibt es als `data:`-URL an eine `picture-elements`-Karte; die
Live-Werte liegen als eigene Marken darüber. Jede Datei zeichnet ein Bauteil in
ein Feld von 200 × 392 mit der Mitte bei x = 100, dem Vorlauf auf y = 92 und dem
Rücklauf auf y = 318. Farben stehen darin als Platzhalter (`{{korpus}}`,
`{{glut}}`, …) und werden beim Zusammensetzen eingesetzt; Kennungen bekommen je
Anlagenteil einen eigenen Präfix, damit zwei Puffer sich nicht denselben Verlauf
teilen. Fehlt eine Datei, greift eine schlichte gezeichnete Ersatzform.

Für den Kessel entscheidet die **Kesselart** über die Datei
(`kessel-<art>.svg`, Rückfall `kessel.svg`). Sie kommt aus der Option
`kesselart` je Anlage; steht die auf „automatisch", wird sie aus dem gemeldeten
Brennstoff (`38/126`, `38/127`) und sonst aus dem Funktionsnamen abgeleitet. Die
Kesselart wirkt **nur auf die Zeichnung** – sie steht bewusst nicht im
Umfangs-Fingerabdruck, ein Wechsel liest die Anlage also nicht neu ein.

`schema.py` importiert nichts aus Home Assistant und ist ohne HA testbar.

Die Bewegung steckt **nicht** in der Zeichnung: Sie liegt als eigene Ebene
darüber (`frontend/teile/schaubild.js` mit den Regeln aus `frontend/stil.js`) –
strömende Bänder auf den Leitungen, drehende Pumpen, das Glutbett nach
Kesselleistung, die Schichtung des Puffers zwischen seinen beiden Fühlern.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_beispiel.svg">
    <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_beispiel_hell.svg" alt="Anlagenschaubild als Standbild" width="760">
  </picture>
</p>

Die Bilder für README und Dokumentation entstehen aus derselben Quelle wie das
Schaubild der Anlage, nicht von Hand:

| Werkzeug | Ergebnis |
|---|---|
| `tools/build_schaubild_beispiel.py` | Standbild je Farbsatz (`assets/anlagenschema_beispiel*.svg`) |
| `tools/build_schaubild_animation.py` | Bewegtbild je Farbsatz (`assets/anlagenschema_animation*.gif`) |

Beide beschreiben dieselbe Beispielanlage (`tools/beispielanlage.py`). Das
Bewegtbild hält die Bewegung der Oberfläche an und stellt sie Bild für Bild
weiter (`animation-delay` plus `animation-play-state: paused`); aufgenommen
wird mit einem kopflosen Browser, zusammengelegt mit Pillow. Es benutzt dabei
**dasselbe Stylesheet** wie die Oberfläche – ändert sich dort die Bewegung,
ändert sie sich beim nächsten Lauf im Bild mit.

## Automations-Vorlagen

`blueprints.py` legt die mitgelieferten Vorlagen aus
`blueprints/automation/heatnexus/` unter `<config>/blueprints/automation/heatnexus/`
ab und frischt sie beim Versionswechsel auf.

## Zyklisches Polling

`fetch_all()` liefert:

```python
{"devices": [...],                    # Descriptor-Liste
 "oids": {"/1/60/0/0/7/0": "59.4"},   # Rohwerte als String, None = kein Wert
 "objects": {oid: [blöcke]},          # Zeitprogramme
 "status": {"15": "PCM 00  OK"}}      # Gerätemeldungen je Knoten
```

Werte bleiben Strings und werden von den Entities selbst geparst. Fehlende Werte
sind `None`, nie `0`.

### Gestaffelter Takt

Nicht jeder Wert bewegt sich gleich schnell. Jeder Datenpunkt bekommt eine
Poll-Klasse, der Coordinator zählt seine Durchläufe und nimmt die trägen
Klassen nur jeden *n*-ten mit:

| Klasse | Ziel | Inhalt |
|---|---|---|
| `fast` | 30 s | Climate, Ist- und Solltemperaturen, Pumpen, Betriebsphase, Meldungen |
| `normal` | 2 min | alles ohne besonderes Merkmal |
| `slow` | 15 min | Zähler und Restlaufzeiten, `total`/`total_increasing`, träge Einheiten, deaktiviert angelegte Fachparameter |

Eingestuft wird nach dem, was der Wert **ist** – Plattform, Name, `state_class`
und Einheit –, nicht danach, in welcher Bedienebene er steht. Im Zweifel bleibt
es beim mittleren Takt: eine Anfrage zu viel ist harmloser als eine Anzeige,
die nachhinkt. Die Ziele sind Sollwerte; der tatsächliche Takt ergibt sich aus
dem eingestellten Abfrageintervall.

## Enums

Enum-Tabellen sind `dict[int, str]`, da die Wertebereiche Lücken enthalten
können. Quellenreihenfolge: kuratierte Tabelle in `const.py`, danach
`device_db.get_enum()`; die vom Gerät gemeldete `enum`-Liste schränkt die
auswählbaren Werte zusätzlich ein.

## Climate

- Der Sollwert wird als befristeter Komfort-Override geschrieben:
  `3/4` (Temperatur) und `2/10` (Dauer in Minuten).
- Angezeigt wird der aktive Raum-Sollwert `1/1`.
- In den Betriebsarten Standby (0) und WW-Betrieb (6) heizt der Heizkreis nicht;
  ein Sollwert wird dort mit einer Meldung abgelehnt.
- Nach einer Bedienung wird der eingestellte Wert sofort angezeigt und beim
  nächsten Poll bestätigt; zusätzlich lädt ein kurzer Burst gezielt die
  Climate-Datenpunkte nach.

## Datendateien

| Datei | Inhalt |
|---|---|
| `device_db.json` | Datenpunktnamen, Enum-Tabellen und Ebenenlisten je Funktionstyp |
| `error_texts_de.json` | Störungstexte und Handlungsempfehlungen je Code |

Beide werden aus den offiziellen Windhager-Parameterdateien erzeugt und nicht
von Hand gepflegt.

## Module

| Datei | Aufgabe |
|---|---|
| `client.py` | HTTP, Discovery, Metadaten, Polling, strukturierte Objekte |
| `__init__.py` | Coordinator, Cache, Setup/Unload, Dienste |
| `dashboard.py` | mitgeliefertes Dashboard, serverseitig gebaut |
| `panel/` | eigener Eintrag in der Seitenleiste: Anmeldung, Aufteilung, Suchmuster, Erklärtexte |
| `frontend/` | die Oberfläche selbst (siehe unten) |
| `schema.py` | Anlagenschaubild aus den Bauteildateien in `anlagenteile/` |
| `blueprints.py` | Automations-Vorlagen bereitstellen |
| `diagnostics.py` | Diagnosedaten für Fehlerberichte |
| `entity.py` | Basisklasse: unique_id, Gerätezuordnung, Poll-Registrierung |
| `const.py` | kuratierte Entity-Tabellen, Enums, Zeitkonstanten |
| `device_db.py` | Zugriff auf die Geräte-Datenbank |
| `error_texts.py` | Dekodierung der Gerätemeldungen |
| `helpers.py` | Wertparsing, Messgrößen (Einheit, Geräteklasse, Zustandsklasse) |
| `kanonisch.py` | herstellerunabhängige Schlüssel je Datenpunkt (`boiler_temperature`, …) |
| `migration.py` | schreibt Registrierungseinträge auf das aktuelle Kennungsschema um |
| `anordnung.py` | Anordnung der Karten je Nutzer, über WebSocket gespeichert |
| `config_flow.py` | Einrichtung (Host, Zugang, Passwort), Umfang, Optionen |
| `climate.py` … `date.py` | Plattformen |

## Die Oberfläche

Ausgeliefert wird der Ordner `frontend/`, ohne Bauschritt und ohne Framework —
was dort steht, lädt der Browser genau so.

| Datei | Aufgabe |
|---|---|
| `heatnexus-panel.js` | das Element selbst: Lebenszyklus, Werte-Zugriff, Aufbau, Kopf- und Reiterleiste |
| `stil.js` | das gesamte CSS |
| `ordnung.js` | Reihenfolge der Karten und Zeitkonstanten – dieselbe Rechnung wie `anordnung.py` auf dem Server |
| `zeitprogramm.js` | Zeitprogramme: Abschnitte, Prüfung, Nutzlast, Wochenraster, Editor |
| `teile/*.js` | die Abschnitte der Oberfläche, je einer als Mixin |

Ein Web-Component ist **eine** Klasse. Um sie trotzdem auf mehrere Dateien zu
verteilen, bringt jede Datei unter `teile/` ihren Abschnitt als Mixin mit
(`(Basis) => class extends Basis { … }`), und `heatnexus-panel.js` setzt sie
zusammen. Die Methoden bleiben dadurch Methoden derselben Klasse; es gibt kein
durchgereichtes `this` und keine geänderten Aufrufstellen.

`tests/test_oberflaeche.py` baut die Oberfläche in Node gegen eine schmale
DOM-Attrappe einmal komplett auf – mit der Aufteilung, die die echte
Serverseite liefert. Ein reiner Ladetest hätte den Fehler nicht gefunden, der
diesen Test veranlasst hat: eine Konstante ohne `export`, die erst beim
Aufräumen einer Rückmeldung auffiel.
