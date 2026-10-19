# Die Oberfläche

HeatNexus bringt eine eigene Seite in der Seitenleiste von Home Assistant mit.
Hier steht, was darauf zu sehen ist — damit man es beurteilen kann, ohne die
Integration erst installieren zu müssen.

<p align="center">
  <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/panel_rundgang.gif" alt="Rundgang durch die Oberfläche: Übersicht, Störung, Steuerung, Automatik, Wartung, Zeitprogramme" width="900">
</p>

<p align="center">
  <em>Alle Werte im Bild sind erfunden, der Aufbau ist echt: Aufgenommen wird
  die ausgelieferte Oberfläche selbst.</em>
</p>

## Was der Rundgang zeigt

**Übersicht.** Oben die Heizungsübersicht: je Anlagenteil ein Leitwert, so wie
das Bediengerät der Anlage ihn zeigt — am Kessel die Kesseltemperatur, am
Puffer die obere, am Heizkreis die Raumtemperatur. Darunter das
Anlagenschaubild, dann der Systemstatus mit Betriebszustand,
Außentemperatur, Kesselleistung, Brennstoff, Vorratsbehälter und den
Restlaufzeiten.

**Schaubild in Bewegung.** Die Pumpen drehen sich, solange sie fördern, und
die Bänder auf Vor- und Rücklauf zeigen die Richtung. Im Rundgang läuft neben
Kessel, Puffer und Heizkreis auch die Zirkulation — an den senkrechten
Stichleitungen sieht man, wohin die Wärme gerade geht.

<a id="stoerung"></a>

**Meldungen.** Liegt eine Meldung an, wechselt der Balken oben von „Anlage in
Ordnung" auf die Art der Meldung, wie Windhager sie nennt: „Info-Meldung
anliegend" in Blau, „Fehler-Meldung anliegend" in Gelb, „Alarm-Meldung
anliegend" in Rot. Die Karte „Meldungen" nennt den Klartext des Herstellers
samt Abhilfe. Verschwindet die Meldung an der Anlage, verschwindet auch die
Anzeige.

<a id="stoerspeicher"></a>

**Meldungsliste.** Führt das Bediengerät eine Meldungsliste, steht sie in der
Karte „Meldungen“. Es ist dieselbe Liste wie am Bediengerät: Jede Zeile nennt den
Klartext, darunter Gerät, Art und Code, rechts die Zeit. Ein Tippen öffnet das
Detail mit den Tasten, die für den Eintrag gelten.

| Taste | Wann | Wirkung |
|---|---|---|
| Zurücksetzen | Der Eintrag ist neu. | Die Meldung gilt als erledigt und schließt sich am Bediengerät. Eine Störung am Kessel bleibt bestehen, solange ihre Ursache anliegt. |
| Löschen | Die Störung liegt nicht mehr an. | Der Eintrag verschwindet aus der Liste des Bediengeräts. |
| Störung am Kessel zurücksetzen | Die Störung liegt an, und die Option ist eingeschaltet. | Steuerungen ab Fassung 2 heben damit die Störung am Kessel auf, wie mit der Taste „Zurücksetzen“ an ihrem Bediengerät. |

Das Zurücksetzen am Kessel ist ab Werk ausgeschaltet. Die Option „Störungen am Kessel
zurücksetzen erlauben“ steht unter Einstellungen → Geräte & Dienste → HeatNexus
→ Optionen → Allgemein. Sie gilt für die ganze Anlage und bleibt über Updates
erhalten. Zurücksetzen sollte nur, wer die Ursache kennt und behoben hat. Jede
Aktion steht mit dem auslösenden Benutzer im Logbuch.

**Steuerung.** Was man an der Anlage wirklich verstellt: Sollwert des
Heizkreises, Eco und Comfort als befristete Übersteuerung, die Betriebswahl,
Warmwasser mit Sollwert und Einmalladung, dazu die Tasten am Kessel. Wo ein
Fehlgriff Arbeit macht oder Brennstoff kostet, kommt vorher eine Rückfrage.

Im Bild läuft dabei beides mit: Am Heizkreis steht „Vorgabe noch bis 10:09"
samt „abbrechen" — ein von Hand verschobener Sollwert überstimmt das
Zeitprogramm nur auf Zeit. Und die Warmwasserkarte zeigt eine **laufende
Einmalladung**: Die Betriebsart meldet „Warmwasser Einmalladung", die Taste
heißt so lange „Warmwasser laden abbrechen". Erkannt wird das an der
Betriebsart oder an der Freigabe der Einmalladung. Die Freigabe steht bis zum
Ende der Ladung auf Ja, auch wenn eine Vorgabe auf Zeit die Betriebsart belegt.

**Automatik.** Ein Sonnentag im Winter: Die Automatik hat am Morgen die
Sonnenquote geprüft und den Sollwert bis zum Nachmittag abgesenkt. Die Kacheln
zeigen Außentemperatur, Sonne und die Räume gegen ihr Ziel. Darunter steht der
Tagesverlauf mit Stundenraster und Vorschau auf morgen und übermorgen.

**Wartung.** Restlaufzeiten bis Ascheentleerung, Hauptreinigung und Wartung,
der Brennstoff, die Zählerstände.

<a id="zeitprogramme"></a>

**Zeitprogramme.** Oben zeigt der Streifen „Heute“ je Heizkreis, Warmwasser und
Puffer den heutigen Tag des geltenden Programms. Rechts stehen der Wert von jetzt
und der nächste Wechsel. Darunter steht je Anlagenteil eine Karte. Das geltende
Programm erscheint groß als Wochenraster mit Blöcken wie „Mo–Fr“ und „Sa, So“, die
Werte stehen im Balken. Die übrigen Programme zeigen ihren heutigen Tag als
schmalen Balken. Gleiche Temperaturen haben überall dieselbe Farbe; die Legende
steht unter dem Streifen. Bearbeitet wird in Blöcken und gespeichert als ganzes
Programm — so, wie die Anlage es führt.
„Aktivieren“ stellt die zugehörige Auswahl nach einer Rückfrage auf dieses Programm.
Beim Bearbeiten lässt sich eine eigene Bezeichnung wie „Übergangszeit“ vergeben.
Sie steht hinter dem Namen des Programms. In der Leseansicht ist die Zeile
hervorgehoben, die gerade gilt.

<a id="automatik"></a>

## Automatik

Der Reiter **Automatik** zeigt je Heizkreis Zustand, Begründung, Tagesverlauf,
Protokoll und Einstellungen. Wie sie entscheidet und was sie an die Steuerung
schreibt, steht unter [Automatik](#automatik).

## Auswertung

Der Reiter **Auswertung** zeigt, wie Heizkreise und Kessel über die Tage
arbeiten. Jeder Kennwert nennt sein Ergebnis und wie verlässlich es ist. Solange
zu wenige Tage vorliegen, steht dort „Sammelt noch Tage.“ Beim ersten Start
rechnet HeatNexus die vergangenen Tage aus der Langzeitstatistik nach.

| Teil | Kennwerte |
|---|---|
| Heizkreis | Wärmespeicher, gemessene Heizgrenze, Räume am Ziel, Nachtabsenkung, Vorlauf unter Soll |
| Kessel | Laufzeit je Start, Starts mit Automatik, Energie je Heizgradtag |

Jeder Kennwert steht auch als Sensor bereit. Auffällige Ergebnisse lassen sich
auf Wunsch als Hinweis in der Seitenleiste melden.

## Eigene Werte über Labels

Auch Werte, die nicht von der Heizung stammen, lassen sich anzeigen. Vergib der
Entität in Home Assistant ein Label (Einstellungen → Bereiche, Labels & Zonen)
und wähle dieses Label in den Einstellungen der Integration unter „Labels in
der Oberfläche zeigen". Jedes gewählte Label wird zu einer eigenen Karte in der
Übersicht. Sie lässt sich verschieben, verbreitern und ausblenden wie jede
andere Karte.

Jede Person sieht in einer Karte nur, was ihre Rechte in Home Assistant
erlauben: Werte ohne Leserecht fehlen darin.

Der Reiter **Verlauf** fehlt im Rundgang. Er benutzt die Verlaufskarte von
Home Assistant, und die zeichnet nur mit einer laufenden Anlage dahinter. Eine
leere Karte im Bild würde also etwas Falsches zeigen.

## Wie das Bild entsteht

Es ist **kein Nachbau**. Aufgenommen wird `frontend/heatnexus-panel.js` selbst,
mit `frontend/stil.js` und seinen Teilen unter `frontend/stil/`, in einem kopflosen Browser:

- Die Aufteilung rechnet `panel.panel_daten` über eine Beispielanlage
  (`tools/beispielanlage.py`) — dieselbe, aus der auch das Anlagenschaubild im
  README entsteht.
- Die Zustandstabelle von Home Assistant wird nachgebildet. Je Auftritt lassen
  sich einzelne Zustände überschreiben; so entsteht die Störung.
- Die Oberfläche hängt an genau einem fremden Element, `ha-icon`. Es wird mit
  den Symbolpfaden bedient, die das installierte Home-Assistant-Frontend
  mitbringt — die Symbole sind also die echten, nicht nachgezeichnet.

```bash
python tools/build_panel_rundgang.py
```

Damit kann das Bild nicht veralten wie ein von Hand gemachter Bildschirmabzug:
Ändert sich die Oberfläche, ändert sie sich beim nächsten Lauf mit.

**Erfundene Werte, echte Struktur.** Kein Datenpunkt im Bild stammt von einer
Anlage; Namen und Adressen sind die der Geräte-Datenbank, die Zahlen sind
gewählt.
