# Einrichtung

Was beim Hinzufügen abgefragt wird, was später unter *Konfigurieren* noch
umstellbar ist, und was die einzelnen Schalter bewirken.

## Zugang

Gebraucht werden die **IP der Steuerung** und das **Service-Passwort**. Der
Benutzername ist immer `USER` und wird nicht abgefragt. Ob der Weg frei ist,
zeigt ein Blick in den Browser: Unter `http://<IP der Anlage>` muss die
Weboberfläche des InfoWIN Touch erscheinen.

Ein Konfigurationseintrag kann **mehrere Anlagen** führen — bis zu sechs. Jede
bekommt eine eigene Bezeichnung, etwa `Heizhaus` und `Wohnhaus`. Diese
Bezeichnung erscheint überall dort, wo sonst zweimal dasselbe stünde: Zwei
Steuerungen melden beide ein `B-PLMi PUFFER`, und ohne Bezeichnung wäre nicht
zu erkennen, welcher gemeint ist.

## Bedienebenen

Die Steuerung ordnet jeden Datenpunkt einer Ebene zu — dieselben Ebenen, die
auch das InfoWIN Touch kennt. Die Auswahl entscheidet, was HeatNexus überhaupt
anlegt.

| Ebene | Was darin steckt | Vorgabe |
|---|---|---|
| Infoebene | Messwerte und Zustände | an |
| Betreiberebene | Betriebswahl, Sollwerte, Zeitprogramme | an |
| Serviceebene | Heizkurve, Grenzwerte, Estrichprogramm | an, Entitäten deaktiviert |
| Werksebene | Verbrennungsregelung, Zündung, Antriebe | aus |

Die Serviceebene ist ein Sonderfall: Sie wird mitgelesen, ihre Entitäten
entstehen aber **deaktiviert**. Sie tauchen in der Geräteübersicht auf, kosten
aber keinen einzigen Abruf, solange niemand sie einschaltet. Erst beim
Aktivieren meldet sich die Entität beim Abfragezyklus an.

Zwei Haken steuern diesen Sonderfall:

- **Fortgeschrittene Werte aktivieren** legt Service- und Werksebene sofort
  aktiv an, statt deaktiviert.
- **Fortgeschrittene Werte bedienbar machen** erlaubt das Schreiben auf diesen
  Ebenen. Ohne den Haken bleiben sie lesbar, aber unveränderlich.

**Eine abgewählte Ebene wird gelöscht, nicht deaktiviert.** Wer die Werksebene
wieder abwählt, hat sich entschieden — die Einträge verschwinden aus der
Registrierung, statt als deaktivierte Zeilen liegen zu bleiben. Anders liegt
der Fall, wenn die Anlage einen Datenpunkt nicht mehr liefert: Dann wird die
Entität nur deaktiviert, damit Name, Bereich und Verlauf erhalten bleiben.

## Abfrageintervall

Einstellbar zwischen **30 und 300 Sekunden**, Vorgabe 30. Der Wert ist die
Untergrenze, kein Multiplikator: Nicht jeder Datenpunkt wird in jedem Takt
gelesen.

| Klasse | Ziel | Was dazugehört |
|---|---|---|
| schnell | 30 s | Thermostate, Temperaturen, Pumpen, Betriebsphase, Meldungen |
| normal | 2 min | alles Übrige |
| langsam | 15 min | Zähler, Laufzeiten, träge Einheiten, deaktiviert angelegte Werte |

Die Klasse ergibt sich daraus, *was* der Wert ist — Plattform, Name,
Zustandsklasse, Einheit — nicht daraus, auf welcher Ebene er liegt.
Betriebsstunden ändern sich nicht in dreißig Sekunden.

Ein kürzeres Intervall bringt deshalb wenig und kostet: Die Steuerung
beantwortet Anfragen nacheinander, mehr Gleichzeitigkeit verkürzt einen
Durchlauf nicht.

## Was zusätzlich angelegt wird

| Schalter | Vorgabe | Wirkung |
|---|---|---|
| Dashboard | an | Legt das mitgelieferte Dashboard an. Es wird bei jedem Öffnen neu gebaut. |
| Eigene Oberfläche | an | Die HeatNexus-Seite in der Seitenleiste. |
| Erklärungen | an | Die „?"-Knöpfe in der eigenen Oberfläche. |
| Systemuhr und Systemdatum | aus | Uhrzeit und Datum der Steuerung als eigene Entitäten. |
| Meldung beim Einlesen | aus | Benachrichtigung, während die Anlage gelesen wird. |
| LON-Adressraum | je nach Gerät | Liest einen zweiten Adressraum mit. Bringt nur dort zusätzliche Werte, wo die Steuerung auf dem normalen Weg wenig meldet. |
| Zusatzwerte | Laufzeit, Zähler | Abgeleitete Werte, gruppenweise an- und abwählbar. |
| Automations-Vorlagen | alle | Welche Blueprints mitgeliefert werden. |

## Darstellung

- **Sprache** der Bezeichnungen, die die Steuerung selbst führt. `Automatisch`
  folgt Home Assistant; Deutsch, Englisch, Französisch und Italienisch lassen
  sich erzwingen.
- **Außentemperatur** — welche Entität in der Kopfzeile der eigenen Oberfläche
  gilt. Leer heißt: HeatNexus sucht sie sich in der Anlage. Nötig, weil der
  Außenfühler oft an einem anderen Gerät hängt als an dem, das ihn meldet.
- **Kesselart** wirkt nur auf die Zeichnung im Schaubild. `Automatisch` leitet
  sie aus Brennstoff und Funktionsnamen ab; die Auswahl ist dafür da, dass eine
  falsch erkannte Anlage trotzdem richtig aussieht.
- **Zweiter Kesselwert** im Schaubild: Kesselleistung oder
  Brennkammertemperatur.

## Eco und Comfort

Beides ist dieselbe befristete Übersteuerung, die auch das Bediengerät
schreibt. Die Anlage kennt nur **einen** Übersteuerungswert; ob er Eco oder
Comfort heißt, entscheidet sie daran, ob er unter oder über dem Sollwert des
Zeitprogramms liegt. Einstellbar sind je eine Temperatur und eine Dauer —
Vorgabe 10 °C und 22 °C, jeweils 180 Minuten.

## Wenn sich die Anlage ändert

Der Erkennungsstand wird gespeichert und in dieser Reihenfolge wiederverwendet:
Arbeitsspeicher, dann Platte, dann vollständige Neuerkennung. Verworfen wird er
bei geändertem Umfang, bei einem Alter über 30 Tagen oder durch den Dienst
`heatnexus.rediscover`.

**Nach einer Aktualisierung ist nichts zu tun.** Eine neue Fassung verwirft den
Stand bewusst nicht — das kostete jedes Mal einen vollen Neuabzug. Stattdessen
wird der gespeicherte Stand sofort hergestellt und im Hintergrund abgeglichen;
neue Entitäten melden sich, sobald sie da sind.

`heatnexus.rediscover` braucht es nur nach einem **Umbau an der Heizung** — ein
neuer Heizkreis, ein neues Modul. Der Dienst meldet danach je Anlage zurück,
was gefunden wurde.
