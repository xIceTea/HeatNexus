# Geräte-API

Basis: `http://<host>/api/1.0/…`, HTTP-Digest-Authentifizierung, Benutzer `USER`,
Passwort = Service-Passwort der Anlage.

## Endpunkte

| Zweck | Aufruf |
|---|---|
| Anlagenstruktur | `GET /api/1.0/lookup/1` |
| Funktions-Root (Menü-IDs) | `GET /api/1.0/lookup/1/<node>/<fct>` |
| Menü-Ebene (Sammelabruf) | `GET /api/1.0/lookup/1/<node>/<fct>/<menuId>` |
| Einzelner Datenpunkt | `GET /api/1.0/lookup/<OID>` |
| Datenpunkt schreiben | `PUT /api/1.0/datapoint`, Body `{"OID":"…","value":"…"}` |
| Strukturiertes Objekt | `GET`/`PUT` `/api/1.0/object?OID=<OID>` |

## OID-Aufbau

```
/1/<nodeId>/<fctId>/<gn>/<mn>/0
   └ Knoten  └ Funktion  └ Gruppe/Member
```

`gn/mn` ist die Adresse des Datenpunkts, der Präfix `/1/<nodeId>/<fctId>` gehört
zur Funktion. `fctId` ist nicht immer `0` – ein Modul kann mehrere Funktionen
desselben Typs führen (z. B. zwei Heizkreise).

## Anlagenstruktur

```json
[{"name": "UMUMLZ", "group": "4", "device": {"id": 49}, "nodeId": 15,
  "subnet": 1, "FE01msg": "PCM 00  OK", "neuronId": "0702dd000004",
  "programId": "9001001d010a0506",
  "functions": [{"lock": false, "name": "UMLZ HEIZKREIS", "fctId": 0, "fctType": 14},
                {"lock": true,  "name": "UM (2)",         "fctId": 1, "fctType": 14},
                {"lock": false, "name": "NV's",           "fctId": 32, "fctType": -1}]}]
```

- `lock: true` – Funktion nicht freigeschaltet.
- `fctType: -1` – Netzwerkvariablen, kein Gerät.
- `FE01msg` (und weitere `FExxmsg`) – Gerätemeldung: `"PUR 09  OK"` störungsfrei,
  `"PUR 09E346"` = Fehler 346.

## Sammelabruf über Menü-Ebenen

Der Funktions-Root liefert die Menü-IDs mit der Anzahl enthaltener Datenpunkte:

```json
GET /api/1.0/lookup/1/60/0
[{"count": 10, "id": 97}, {"count": 14, "id": 98}, {"count": 50, "id": 100}]
```

Eine Menü-ID liefert alle enthaltenen Datenpunkte vollständig – Wert und
Metadaten – in einem Request:

```json
GET /api/1.0/lookup/1/15/0/113
[{"OID": "/1/15/0/1/1/0", "groupNr": 1, "memberNr": 1, "name": "01-001",
  "minValue": "0.0", "maxValue": "0.0", "step": "0.1", "typeId": 13,
  "subtypeId": -1, "unit": "°C", "unitId": 1, "value": "5.0",
  "writeProt": true, "timestamp": "2026-06-12 21:07:01"}]
```

**Grenze:** Ein Menü-Abruf liefert höchstens **zehn** Datenpunkte, auch wenn der
Funktions-Root für die Ebene mehr meldet. Ebenen mit mehr Einträgen müssen
seitenweise nachgeladen werden; welche Form das Gerät dafür versteht, ermittelt
`tools/heatnexus_probe.py` mit der Aktion „Seitenmodus testen".

Große Ebenen brauchen zudem spürbar Zeit: mehr als drei gleichzeitige Anfragen
oder ein Zeitlimit unter 30 s führen zu abgebrochenen Antworten.

## Datenpunkt-Metadaten

| Feld | Bedeutung |
|---|---|
| `value` | Rohwert als String; `"-.-"`, `"-"`, `""` bedeuten „kein Wert" |
| `unit`, `unitId` | Einheit |
| `minValue`, `maxValue`, `step` | Wertebereich schreibbarer Datenpunkte |
| `writeProt` | `true` = nur lesbar |
| `enum` | erlaubte Werte, z. B. `"[1,2]"` |
| `typeId` | `30` = strukturiertes Objekt (Zeitprogramm), sonst Skalar |

Fehlerantworten:

- `404` – Datenpunkt existiert nicht.
- `409` mit `"Target returns invalid Identifier"` – auf dieser Anlage nicht
  vorhanden.
- `409` beim Schreiben – Gerät verweigert den Zugriff.

## Schreiben

```http
PUT /api/1.0/datapoint
{"OID":"/1/15/0/3/50/0","value":"1"}
```

Werte immer als String, Kommazahlen mit Punkt.

## Strukturierte Objekte

```http
GET /api/1.0/object?OID=/1/15/0/3/61/0
```

Parameter `OID` groß geschrieben, vollständige OID, Schrägstriche unkodiert.

```json
{"OID": "/1/15/0/3/61/0", "typeId": 30, "subtypeId": 14, "writeProt": false,
 "value": [{"weekdays": ["Mo","Tu","We","Th","Fr","Sa","Su"],
            "switchPoints": [{"time": "06:00", "value": 21},
                             {"time": "22:00", "value": 18}]}]}
```

Beim Schreiben wird das gelesene Objekt als Rahmen übernommen, `timestamp`
entfernt und nur `value` ersetzt.

## Grenzen

- Digest-Authentifizierung erfordert zwei Roundtrips pro neuer Verbindung; die
  Challenge wird wiederverwendet.
- Höchstens drei parallele Anfragen, Zeitlimit 30 s; darüber brechen große
  Antworten ab.
- Ein Menü-Abruf liefert maximal zehn Datenpunkte (siehe oben).
- **Zeichensatz:** Antworten sind nicht durchgängig UTF-8. Gerätenamen kommen
  als Latin-1/CP1252 (`Hebebühne`), deshalb beim Dekodieren einen Rückfall auf
  CP1252 vorsehen – sonst stehen Fragezeichen in Geräte- und Entitätsnamen.
