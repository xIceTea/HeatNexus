# Geräte-API

Basis: `http://<host>/api/1.0/…`, HTTP-Digest-Authentifizierung, Benutzer `USER`,
Passwort = Service-Passwort der Anlage.

## Zugänge

Die Steuerung kennt zwei Benutzer, `USER` und `Service`. Der Name wird geprüft —
ein erfundener Benutzer wird mit `401` abgewiesen —, aber **beide sehen über die
Schnittstelle dasselbe**: dieselben Datenpunkte, dieselben Werte, dasselbe
`writeProt`. Auch Parameter der Serviceebene beantwortet die Anlage einem
`USER`, und sie meldet sie als schreibbar.

Die Trennung in Bedienebenen ist damit eine Eigenschaft des **Bediengeräts**,
nicht der Schnittstelle. Was HeatNexus davon anlegt und bedienbar macht,
entscheidet die Integration selbst über die gewählten Bedienebenen — nicht der
Zugang.

Nachgemessen an einer PuroWIN-Installation mit InfoWIN Touch. Für andere
Baureihen ist es nicht belegt, deshalb bleibt der Zugang in der Einrichtung
wählbar.

## Endpunkte

| Zweck | Aufruf |
|---|---|
| Anlagenstruktur | `GET /api/1.0/lookup/1` |
| Funktions-Root (Menü-IDs) | `GET /api/1.0/lookup/1/<node>/<fct>` |
| Menü-Ebene (Sammelabruf) | `GET /api/1.0/lookup/1/<node>/<fct>/<menuId>` |
| Einzelner Datenpunkt | `GET /api/1.0/lookup/<OID>` |
| Datenpunkt schreiben | `PUT /api/1.0/datapoint`, Body `{"OID":"…","value":"…"}` |
| Strukturiertes Objekt | `GET`/`PUT` `/api/1.0/object?OID=<OID>` |
| Gerätekennung der Steuerung | `GET /api/1.0/info/deviceinfo` |
| Knotenliste mit Werksbezeichnung | `GET /api/1.0/nodes` |
| Statische Positionen | `GET /res/xml/StaticNav.xml`, `GET /res/xml/StaticNavAssignment.xml` |

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
  "subnet": 1, "FE01msg": "PCM 00  OK", "neuronId": "0702aa000001",
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

**Grenze:** Ein Menü-Abruf liefert von sich aus höchstens **zehn** Datenpunkte,
auch wenn der Funktions-Root für die Ebene mehr meldet. Zwei Wege führen an der
Grenze vorbei:

```http
GET /api/1.0/lookup/1/60/0/100?count=-1&offset=0   ganze Ebene auf einmal
GET /api/1.0/lookup/1/60/0/100?offset=10           seitenweise nachladen
```

`count=-1` ist der Weg, den das Bediengerät der Anlage selbst geht, und spart
den Großteil der Anfragen; er wird zuerst versucht. Antwortet die Steuerung
darauf nicht mit mehr als zehn Einträgen, wird über `offset` geblättert.

Große Ebenen brauchen spürbar Zeit. Die Steuerung beantwortet Anfragen der
Reihe nach, deshalb verkürzt höhere Parallelität einen Abzug nicht — der Hebel
liegt darin, **weniger** zu fragen, nicht gleichzeitiger.

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

## Weitere Endpunkte

### Gerätekennung

```json
GET /api/1.0/info/deviceinfo
{"device": "MB66xx", "version": "…", "checknumber": "…", "serialnumber": "…"}
```

Die einzige maschinenlesbare Kennung der Steuerung samt Firmwarestand, eine
Anfrage. „RC7030" ist die Bezeichnung aus der Herstellerdokumentation,
`MES_RC7030` die des Konfigurationsmenüs; die Hardware selbst meldet MB66xx.

### Knotenliste

```json
GET /api/1.0/nodes
[{"nodeId": 15, "neuronId": "0702aa000001", "subnet": 1, "name": "UMUMLZ",
  "programId": "9001001d010a0506",
  "device": {"id": 38, "name": "UMUMLZ", "DeviceClass": "29.01", "protocol": "eBUS"}}]
```

Ergänzt `lookup/1` um die **Werksbezeichnung** des Moduls, seine Geräteklasse
und das Busprotokoll; `lookup/1` liefert unter `device` nur eine Zahl. Unter
`name` steht dort der vergebene Name, hier die Bezeichnung ab Werk. Die Liste
kann Knoten enthalten, die `lookup/1` nicht führt – ein Bedienteil meldet sich
mit `protocol: "none"`.

### Statische Positionen

`GET /res/xml/StaticNav.xml` und `StaticNavAssignment.xml` nennen Datenpunkte,
die in **keiner** Menü-Ebene stehen (Zeitprogramme, Störspeicher). Beide sind
ohne Anmeldung ladbar. Sie gehören zur Firmware, nicht zur einzelnen Anlage:
Eine dort deklarierte Position kann an dieser Installation trotzdem mit `404`
oder `409` antworten. Ob es sie gibt, klärt erst die Abfrage.

### Endpunkte, die nichts einbringen

| Aufruf | Warum nicht |
|---|---|
| `GET /api/1.0/datapoints` | Cache der zuletzt gelesenen Datenpunkte, kein Inventar – enthält nur, was vorher schon abgefragt wurde, und ist damit als Erkennungsquelle wie als Abkürzung zirkulär |
| `GET /api/1.0/recorder/oids`, `…/datalogs` | `501`, solange die Datenaufzeichnung nicht läuft; `recorder/settings` antwortet mit `enabled: false` |
| LON-Netzwerkvariablen unter `/1/<node>/32` | Die Steuerung deutet die Adresse dort um: der Member gilt als `nvIndex`, die Gruppe wird ignoriert. Jeder Wert kostet eine eigene Anfrage |

## Grenzen

- Digest-Authentifizierung erfordert zwei Roundtrips pro neuer Verbindung; die
  Challenge wird wiederverwendet.
- Die Steuerung beantwortet Anfragen der Reihe nach; höhere Parallelität
  verkürzt einen Abzug nicht (siehe oben). Zeitlimit 30 s, weil große
  Menü-Ebenen länger brauchen als eine Einzelabfrage.
- Ein Menü-Abruf liefert ohne `count=-1` maximal zehn Datenpunkte.
- **Zeichensatz:** Antworten sind nicht durchgängig UTF-8. Von Hand vergebene
  Namen kommen in der DOS-Codepage der Steuerung – dort liegt „ü" auf `0x81`,
  einem Byte, das CP1252 gar nicht belegt. Beim Dekodieren deshalb der Reihe
  nach `utf-8`, `cp1252`, `cp850` versuchen, sonst stehen Fragezeichen in
  Geräte- und Entitätsnamen.
