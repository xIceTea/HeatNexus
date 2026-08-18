# Fehlersuche

Die Fälle, die in den Diskussionen immer wieder auftauchen — nach Symptom
sortiert.

## Die Einrichtung schlägt fehl

**„Anmeldung abgelehnt"** — gefragt ist der Zugang der Weboberfläche der
Anlage, nicht der eines Portals. Ab Werk sind das `USER` und `Service`, beide
mit dem Passwort `123`. Wurde es einmal geändert, gilt das neue sofort auch
hier — dann in Home Assistant über *Neu anmelden* nachziehen.

Wie man ein unbekanntes Passwort wiederfindet — am Gerät, in der
Weboberfläche oder über Windhager Connect — steht mit allen Schritten unter
[Passwort herausfinden](#passwort-herausfinden).

**„Verbindung nicht möglich"** — vorher im Browser prüfen: Unter
`http://192.0.2.10` (die IP der eigenen Anlage) muss die Weboberfläche des
InfoWIN Touch erscheinen. Kommt dort nichts, liegt es nicht an HeatNexus.
Häufigste Ursachen: Die Steuerung hängt in einem anderen Netzsegment, oder das
Netzwerkmodul ist nicht freigeschaltet.

**„Einrichtung noch nicht bereit"** — der erste Durchlauf liest Struktur und
Kernwerte und darf dafür bis zu zwei Minuten brauchen. Bricht er ab, versucht
Home Assistant es von selbst erneut. Bleibt es dabei, antwortet die Steuerung
zu langsam — meist, weil parallel noch etwas anderes auf sie zugreift.

## Es fehlen Entitäten

**Erst die deaktivierten einblenden.** Die Serviceebene wird gelesen, ihre
Entitäten entstehen aber deaktiviert. In der Geräteansicht steht dafür ein
Filter *Deaktivierte Entitäten anzeigen*. Wer sie dauerhaft aktiv haben will,
setzt in den Optionen den Haken *Fortgeschrittene Werte aktivieren*.

**Dann die Bedienebenen prüfen.** Die Werksebene ist ab Werk aus. Was in keiner
Ebene der mitgelieferten Datenbank steht, gilt als Werksebene und erscheint nur
mit dieser Auswahl.

**Nach einem Umbau an der Heizung** — neuer Heizkreis, neues Modul — den Dienst
`heatnexus.rediscover` aufrufen. Er verwirft den gespeicherten Stand und liest
alles neu.

**Nach einer Aktualisierung ist nichts zu tun.** Der gespeicherte Stand wird
sofort hergestellt und im Hintergrund abgeglichen. Neue Entitäten melden sich
von selbst.

## Entitäten ohne Datenpunkt

Liefert die Anlage einen Wert nicht mehr, wird die Entität abgeschaltet und
bleibt stehen. Name, Symbol, Bereich und Verlauf bleiben damit erhalten. Kommt
der Wert zurück, ist die Entität sofort wieder da.

Sollen sie ganz verschwinden, steht unter *Einstellungen → System →
Reparaturen* ein Eintrag mit ihrer Anzahl. Auf Bestätigung löscht er sie samt
Verlauf.

Eine **abgewählte Bedienebene** ist etwas anderes: Das ist eine Entscheidung,
ihre Entitäten werden gleich entfernt und beim Wiederdazuwählen neu angelegt.

## Ein Wert bleibt leer

Antwortet die Steuerung auf einen Datenpunkt mit `404` oder mit `409` und
„invalid Identifier", gibt es ihn auf dieser Anlage nicht — die Entität wird
gar nicht erst angelegt. Das ist kein Fehler, sondern die Antwort der Anlage.

Bleibt eine vorhandene Entität leer, steht dort `None` und nicht `0`. Das ist
Absicht: Eine fehlende Messung ist keine Null. Wer in einer Automation darauf
prüft, prüft auf `unavailable` oder `unknown`, nicht auf den Zahlenwert.

Schreibbare Datenpunkte, die sich **nicht** lesen lassen, bleiben trotzdem
bedienbar. Sie zeigen keinen Zustand an, nehmen aber Befehle an.

## Etwas lässt sich nicht verstellen

**Der Datenpunkt ist schreibgeschützt.** Meldet die Steuerung `writeProt`, legt
HeatNexus statt des Bedienelements den lesenden Zwilling an. Das ist eine
Auskunft der Anlage, keine Entscheidung der Integration.

**Die Ebene ist nicht freigegeben.** Service- und Werksebene sind ohne den
Haken *Fortgeschrittene Werte bedienbar machen* nur lesbar.

**Der Heizkreis ist aus.** Eine Solltemperatur lässt sich in den Betriebsarten
*Standby* und *WW-Betrieb* nicht setzen. Die Anlage würde dabei nur einen Timer
stellen, ohne zu heizen — deshalb wird der Schreibversuch abgelehnt statt still
verschluckt.

**Die Änderung springt zurück.** Geschriebene Werte werden sofort angezeigt und
erst durch den nächsten Abruf bestätigt. Nimmt die Anlage den Wert nicht an,
fällt die Anzeige nach kurzer Zeit auf den echten Stand zurück.

## Dashboard oder Oberfläche fehlen

Beide sind Schalter in den Optionen. Das mitgelieferte Dashboard wird bei jedem
Öffnen neu gebaut und lässt sich deshalb nicht bearbeiten. Wer ein eigenes will,
ruft den Dienst `heatnexus.dashboard_ausgeben` auf, legt ein neues Dashboard an
und fügt den Text im Rohkonfigurations-Editor ein.

## Meldungen stehen noch da

Die Störungsanzeige wird **gelesen, nicht quittiert**. Verschwindet die Meldung
an der Anlage, verschwindet auch die Anzeige. Der Dienst
`heatnexus.meldungen_loeschen` leert nur die von HeatNexus geführte Liste in
Home Assistant — der Störspeicher am Bediengerät bleibt unberührt und wird wie
gewohnt dort zurückgesetzt.

## Etwas melden

Zum Melden gehören zwei Dinge:

1. **Der Diagnose-Export.** In der Geräteansicht der Integration unter den drei
   Punkten → *Diagnose herunterladen*. Darin steht, was HeatNexus gefunden hat,
   ohne Passwort.
2. **Was die Anlage ist** — Baureihe des Kessels und welche Module dranhängen.

Beides in ein [Issue](https://github.com/xIceTea/HeatNexus/issues) oder in die
[Diskussionen](https://github.com/xIceTea/HeatNexus/discussions).

Für Anlagen, die noch nicht abgedeckt sind, gibt es ein Sondenwerkzeug. Es ist
eine einzelne Python-Datei, braucht nichts außer der Standardbibliothek,
verändert nichts an der Anlage und läuft im Betrieb nicht mit:

```bash
python tools/heatnexus_probe.py all 192.0.2.10
```

Ohne Argument startet es geführt. Die Ergebnisse landen als JSON, CSV und
Bericht im Ordner `probe/`.
