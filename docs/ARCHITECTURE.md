# Architektur

```
                    ┌────────────────────────────────────────────┐
   Heizung (LAN) ──►│ client.py   Discovery · Metadaten · Polling │
                    │             erzeugt Descriptor-Liste        │
                    └───────────────┬────────────────────────────┘
                                    │ coordinator.data
                    ┌───────────────▼────────────────────────────┐
                    │ __init__.py  DataUpdateCoordinator, Cache,  │
                    │              Dienste                        │
                    └───────────────┬────────────────────────────┘
                                    │ filtert nach descriptor["type"]
   climate · sensor · binary_sensor · select · number · switch · button · time · date
                    (alle über entity.py / WindhagerEntity)
```

## Descriptor-Liste als zentrale Schnittstelle

`client.py` kapselt das gesamte Gerätewissen und erzeugt flache Beschreibungen:

```python
{"id": "192-168-178-100-1-60-0-0-7-0",   # unique_id
 "oid": "/1/60/0/0/7/0",
 "name": "Kesseltemperatur Ist",
 "type": "temperature",                   # bestimmt die Plattform
 "unit": "°C", "device_class": None, "state_class": None,
 "category": None, "icon": None,
 "min": None, "max": None, "step": None,
 "write_prot": True,
 "device_id": "192-168-178-100-1-60-0",   # HA-Gerät
 "device_name": "PuroWIN",
 "fct_type": 25}                          # Funktionstyp, ordnet das Dashboard
```

Jede Plattform filtert `coordinator.data["devices"]` nach `type`. Eine neue
Plattform benötigt daher nur einen neuen `type` im Client, ein Modul, das darauf
filtert, und den Eintrag in `PLATFORMS`.

## Ablauf beim Start

1. **Cache** – RAM (Reload) → Platte (`Store`, Neustart) → vollständige Discovery.
   Der Cache wird verworfen bei Versionswechsel, Alter über 30 Tage oder durch
   den Dienst `heatnexus.rediscover`.
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
| `aiohelper.py` | nebenläufigkeitssichere Digest-Authentifizierung |
| `__init__.py` | Coordinator, Cache, Setup/Unload, Dienste |
| `dashboard.py` | mitgeliefertes Dashboard, serverseitig gebaut |
| `panel.py` | eigener Eintrag in der Seitenleiste, Aufteilung serverseitig |
| `schema.py` | Anlagenschaubild aus den Bauteildateien in `anlagenteile/` |
| `blueprints.py` | Automations-Vorlagen bereitstellen |
| `diagnostics.py` | Diagnosedaten für Fehlerberichte |
| `entity.py` | Basisklasse: unique_id, Gerätezuordnung, Poll-Registrierung |
| `const.py` | kuratierte Entity-Tabellen, Enums, Zeitkonstanten |
| `device_db.py` | Zugriff auf die Geräte-Datenbank |
| `error_texts.py` | Dekodierung der Gerätemeldungen |
| `helpers.py` | Wertparsing |
| `config_flow.py` | Einrichtung (Host, Passwort) |
| `climate.py` … `date.py` | Plattformen |
