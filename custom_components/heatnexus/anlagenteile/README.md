# Bauteilzeichnungen für das Anlagenschaubild

Jede Datei zeichnet **ein** Anlagenteil. `schema.py` setzt sie zu einem Bild
zusammen, färbt sie ein und legt die Live-Werte darüber.

## Regeln

**Bruchstück, kein Bild.** Die Datei enthält *keine* `<svg>`-Wurzel und keinen
XML-Prolog – nur die Formen. `<defs>` ist erlaubt.

**Feste Maße.** Gezeichnet wird in ein Feld von **200 × 392**:

| Linie | y | Bedeutung |
|---|---|---|
| 92 | Vorlauf | die waagrechte rote Leitung |
| 318 | Rücklauf | die waagrechte blaue Leitung |
| 374 | Titel | die Beschriftung setzt `schema.py` selbst |

Die Mitte liegt bei **x = 100**. Der Körper eines Anlagenteils sollte zwischen
y = 118 und y = 294 bleiben und höchstens 130 breit sein, sonst stoßen zwei
Nachbarn aneinander. Die Anschlussstutzen an den Leitungen zeichnet `schema.py`.

**Farben nur als Platzhalter.** Kein `#rrggbb` in der Datei. Erlaubt sind:

`{{vorlauf}}` `{{ruecklauf}}` `{{rahmen}}` `{{text}}` `{{titel}}` `{{korpus}}`
`{{korpus_hell}}` `{{korpus_dunkel}}` `{{warm}}` `{{glut}}` `{{kalt}}`
`{{schrift}}`

Wer eine Farbe ändern will, ändert sie in `FARBEN` in `schema.py` – nicht in elf
Dateien. Neue Platzhalter dort eintragen, sonst bleiben sie als `{{name}}` im
Bild stehen.

Ausnahme sind `#ffffff` und `#000000` mit kleiner Deckkraft: Sie liegen als
Licht und Schatten über einer Form und sind deshalb unabhängig von der Farbe
darunter. Jede andere feste Farbe lässt den Test fehlschlagen.

**Kennungen dürfen doppelt sein.** `schema.py` stellt jeder `id` einen
Platzhalter je Anlagenteil voran, damit zwei Puffer im selben Bild nicht
denselben Verlauf benutzen. Bezüge müssen dafür in einer dieser drei
Schreibweisen stehen: `id="…"`, `url(#…)`, `href="#…"`.

**Keine Fremdverweise.** Kein `<image>`, keine externe Schrift, kein Script. Das
Bild wird als `data:`-URL ausgeliefert; alles Externe würde geblockt.

## Dateinamen

| Datei | Anlagenteil |
|---|---|
| `kessel.svg` | Wärmeerzeuger, neutral |
| `kessel-hackgut.svg` | Hackgutkessel |
| `kessel-pellets.svg` | Pelletskessel |
| `kessel-scheitholz.svg` | Scheitholzkessel |
| `kessel-waermepumpe.svg` | Wärmepumpe |
| `kessel-gas-oel.svg` | Gas- oder Ölkessel |
| `puffer.svg` | Pufferspeicher |
| `heizkreis.svg` | Heizkreis |
| `wasser.svg` | Warmwasserspeicher |
| `zirkulation.svg` | Warmwasser-Zirkulationskreis (hängt am Heizkreis) |
| `pumpenmodul.svg` | ZSP – Pumpen-/Relaismodul (fctType 20) |
| `solar.svg` | Solarkollektor (fctType 5) |
| `modul.svg` | unbekannter Funktionstyp |

Eine Wärmepumpe bekommt keine eigene Datei: Sie ist der Wärmeerzeuger und wird
über `kessel-waermepumpe.svg` gezeichnet.

`pumpenmodul` und `zirkulation` sind bewusst verschieden. Das ZSP ist ein
Schaltgerät in der Leitung – es kann eine Pumpe regeln, eine externe
Wärmeanforderung entgegennehmen oder einen Sammelalarm schalten. Die
Warmwasser-Zirkulation ist ein Kreis. Bis 1.2.0 sahen beide gleich aus.

Für den Kessel wird `kessel-<art>.svg` gesucht und auf `kessel.svg`
zurückgefallen. Eine weitere Art braucht nur die Datei und einen Eintrag in
`KESSELARTEN` in `const.py`.

**Fehlt eine Datei, zeichnet `schema.py` eine schlichte Ersatzform.** Das
Schaubild bleibt heil; es sieht nur langweiliger aus.

## Was hier nicht hingehört

Keine Produktfotos und keine Nachzeichnungen von Herstellerbildern. Die
Zeichnungen sind bewusst schematisch: Sie sollen die Hydraulik zeigen, kein
Gerät abbilden.
