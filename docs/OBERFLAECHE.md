# Die Oberfläche

HeatNexus bringt eine eigene Seite in der Seitenleiste von Home Assistant mit.
Diese Seite zeigt, was darin steht — bevor man die Integration installiert.

<p align="center">
  <img src="../assets/panel_rundgang.gif" alt="Rundgang durch die Oberfläche: Übersicht, Störung, Steuerung, Wartung, Zeitprogramme" width="900">
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

**Störung.** Liegt eine Meldung an, wechselt der Balken oben von „Anlage in
Ordnung" auf „Störung anliegend", und die Störungskarte nennt den Klartext des
Herstellers samt Abhilfe. Verschwindet die Meldung an der Anlage, verschwindet
auch die Anzeige — sie wird nicht quittiert, sondern gelesen.

**Steuerung.** Was man an der Anlage wirklich verstellt: Sollwert des
Heizkreises, Eco und Comfort als befristete Übersteuerung, die Betriebswahl,
Warmwasser mit Sollwert und Einmalladung, dazu die Tasten am Kessel. Wo ein
Fehlgriff Arbeit macht oder Brennstoff kostet, kommt vorher eine Rückfrage.

**Wartung.** Restlaufzeiten bis Ascheentleerung, Hauptreinigung und Wartung,
der Brennstoff, die Zählerstände.

**Zeitprogramme.** Je Programm ein Wochenraster: Blöcke wie „Mo–Fr" und
„Sa, So", darin die Schaltzeiten als Balken, darunter als Text. Bearbeitet wird
in Blöcken und gespeichert als ganzes Programm — so, wie die Anlage es führt.

Der Reiter **Verlauf** fehlt im Rundgang. Er zeichnet mit der Verlaufskarte von
Home Assistant, und die gibt es nur in einer laufenden Instanz; eine leere
Karte im Bild wäre eine Falschaussage.

## Wie das Bild entsteht

Es ist **kein Nachbau**. Aufgenommen wird `frontend/heatnexus-panel.js` selbst,
mit `frontend/stil.js`, in einem kopflosen Browser:

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
