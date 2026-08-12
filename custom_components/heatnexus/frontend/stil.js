/**
 * Das Aussehen der Oberfläche.
 *
 * Steht als eigene Datei, weil es der größte zusammenhängende Block ist und
 * mit der Logik nichts zu tun hat. Der Stil liegt in einem Template-Literal:
 * Ein Backtick im Kommentar beendet es, und die ganze Datei ist kein gültiges
 * JavaScript mehr. In einer Datei, die nur Stil enthält, fällt das auf.
 *
 * **Keine Backticks in Kommentaren.** Der Test `test_browser_rechnet_genauso`
 * lädt die Module in Node und fängt es ab.
 */

export const STIL = `
  :host {
    display: block;
    background: var(--primary-background-color, #0e1419);
    color: var(--primary-text-color, #e6edf3);
    min-height: 100%;
    box-sizing: border-box;
  }
  * { box-sizing: border-box; }

  /* --- Kopfleiste: Menütaste, Marke, Anlagenwahl, Reiter --------------- */
  /* Kopfleiste und Reiter bleiben beim Blättern stehen; nur die Karten
     darunter laufen durch. Beide stecken dafür in einem gemeinsamen Kasten:
     Zwei getrennt klebende Elemente würden übereinander rutschen, weil jedes
     für sich am oberen Rand hängen bliebe.

     Der Hintergrund ist Pflicht – ohne ihn scheinen die Karten durch die
     Leiste hindurch. Der Farbwert ist derselbe wie am Wirtselement, damit die
     Leiste im hellen wie im dunklen Erscheinungsbild nicht auffällt. */
  .leiste {
    position: sticky; top: 0; z-index: 5;
    background: var(--primary-background-color, #0e1419);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }
  .kopfleiste {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px 0;
    flex-wrap: wrap;
  }
  .menue-taste {
    display: inline-flex;
    align-items: center; justify-content: center;
    width: 40px; height: 40px; flex: none;
    border-radius: 12px; cursor: pointer;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: inherit;
  }
  .menue-taste:hover { background: rgba(255, 255, 255, 0.1); }
  .kopfleiste .marke { font-size: 20px; font-weight: 700; }
  .kopfleiste .abstand { flex: 1; }
  .aussen {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 12px; border-radius: 999px; font-size: 14px; font-weight: 600;
    background: rgba(255, 255, 255, 0.05);
  }
  .aussen ha-icon { --mdc-icon-size: 18px; }
  .waehler { display: flex; gap: 6px; flex-wrap: wrap; }
  .waehler button {
    padding: 8px 14px; border-radius: 999px; font: inherit; font-size: 13px;
    font-weight: 600; cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .waehler button:hover { background: rgba(255, 255, 255, 0.1); }
  .waehler button[aria-selected="true"] {
    background: rgba(111, 178, 245, 0.18);
    border-color: rgba(111, 178, 245, 0.5);
    color: #6fb2f5;
  }
  .reiter { display: flex; gap: 4px; padding: 12px 16px 0; overflow-x: auto; }
  .reiter button {
    display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
    padding: 10px 16px; border: none; border-bottom: 2px solid transparent;
    background: none; color: inherit; font: inherit; font-size: 14px;
    font-weight: 600; cursor: pointer; opacity: 0.55;
  }
  .reiter button:hover { opacity: 0.85; }
  .reiter button[aria-selected="true"] {
    opacity: 1; color: #6fb2f5; border-bottom-color: #6fb2f5;
  }
  .anlagen-trenner {
    display: flex; align-items: center; gap: 12px;
    margin: 8px 16px 0; padding-top: 16px;
    font-size: 15px; font-weight: 700; letter-spacing: 0.3px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }
  .anlagen-trenner:first-of-type { border-top: none; padding-top: 4px; }

  /* --- Kartenraster ---------------------------------------------------- */
  /* Ein Raster für alle vier Reiter. Jede Karte liegt einzeln darin, nicht
     in einem Spaltenstapel: Sonst steckte die Reihenfolge im Stapel statt in
     einer Liste, und umsortieren ginge nicht.

     "align-items: stretch" ist Absicht. Vorher richtete sich jede Karte nach
     ihrem eigenen Inhalt, und in der Steuerung stand die Heizkreiskarte
     deutlich höher als Kessel und Lagerraum daneben – die Zeile sah aus, als
     fehlte etwas. Gleich hohe Karten je Zeile lesen sich ruhiger.

     Spaltenzahl und Kartenbreite kommen als Variablen von der Anordnung; sie
     stehen bewusst nicht als Inline-Stil da, sonst schlüge die eigene
     Einstellung den Umbruch auf schmalen Bildschirmen.

     "auto-fill" statt "auto-fit": Unter „Alle" bekommt jede Anlage ihr eigenes
     Raster. Mit "auto-fit" fallen leere Spalten in sich zusammen, und eine
     Anlage mit zwei Karten machte daraus zwei breite – daneben stand die
     Anlage mit drei Karten in drei schmalen. Gleiches „1×" sah dann
     verschieden groß aus. "auto-fill" lässt die leeren Spalten stehen, also
     ist eine Spalte überall gleich breit. */
  .raster {
    display: grid;
    gap: 16px;
    padding: 16px;
    grid-template-columns: var(--raster-spalten, repeat(auto-fill, minmax(320px, 1fr)));
    align-items: stretch;
  }
  .raster > * { grid-column: span var(--breite, 1); min-width: 0; }
  /* Der Inhalt bleibt oben, auch wenn die Karte für die Zeile mitwächst. */
  .karte { display: flex; flex-direction: column; }
  .raster > .karte + .karte { margin-top: 0; }
  @media (max-width: 1180px) {
    .raster { grid-template-columns: minmax(0, 1fr); }
    .raster > * { grid-column: auto; }
  }

  /* --- Anordnen -------------------------------------------------------- */
  .anordnen-leiste {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    margin: 12px 16px 0; padding: 10px 14px; border-radius: 14px;
    background: rgba(111, 178, 245, 0.12);
    border: 1px solid rgba(111, 178, 245, 0.35);
  }
  .anordnen-leiste .titel { font-weight: 700; font-size: 15px; color: #6fb2f5; }
  .anordnen-leiste .hinweis { font-size: 12px; opacity: 0.7; flex: 1; min-width: 180px; }
  .anordnen-leiste .abstand { flex: 1; }
  .anordnen-taste {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 14px; border-radius: 999px; cursor: pointer;
    font: inherit; font-size: 13px; font-weight: 600; color: inherit;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .anordnen-taste:hover { background: rgba(255, 255, 255, 0.12); }
  .anordnen-taste.fertig {
    background: rgba(111, 178, 245, 0.25); border-color: rgba(111, 178, 245, 0.5);
    color: #cfe6ff;
  }
  .anordnen-taste ha-icon { --mdc-icon-size: 18px; }
  /* Die Spaltenwahl sieht aus wie die Anlagenwahl oben – gleiche Geste. */
  .spaltenwahl { display: inline-flex; gap: 4px; }
  .spaltenwahl button {
    min-width: 34px; padding: 7px 10px; border-radius: 999px;
    font: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
    color: inherit; opacity: 0.6;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .spaltenwahl button[aria-pressed="true"] {
    opacity: 1; color: #6fb2f5;
    background: rgba(111, 178, 245, 0.15);
    border-color: rgba(111, 178, 245, 0.45);
  }

  /* Die Hülle, die im Anordnen-Modus um jede Karte liegt. Ohne sie müsste die
     Karte selbst die Griffleiste tragen – und jede Kartenart hätte sie neu
     bekommen müssen. */
  .anordner { display: flex; flex-direction: column; min-width: 0; }
  .anordner > .karte, .anordner > .klappkarte {
    flex: 1;
    border-color: rgba(111, 178, 245, 0.35);
    border-top-left-radius: 0; border-top-right-radius: 0;
  }
  .anordner-griff {
    display: flex; align-items: center; gap: 4px;
    padding: 6px 8px; cursor: grab;
    border: 1px solid rgba(111, 178, 245, 0.35); border-bottom: none;
    border-radius: 14px 14px 0 0;
    background: rgba(111, 178, 245, 0.16);
  }
  .anordner-griff .name {
    flex: 1; min-width: 0; font-size: 12px; font-weight: 600;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .anordner-griff button {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; flex: none; border-radius: 8px;
    background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.1);
    color: inherit; font: inherit; cursor: pointer;
  }
  .anordner-griff button:hover { background: rgba(255, 255, 255, 0.14); }
  .anordner-griff button:disabled { opacity: 0.3; cursor: default; }
  .anordner-griff button ha-icon { --mdc-icon-size: 16px; }
  /* Die Breite ist eine Anzeige, keine Taste – geklickt wird links und rechts
     davon. */
  .anordner-griff .breite {
    flex: none; min-width: 26px; padding: 0 2px;
    font-size: 12px; font-weight: 700; text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .anordner.gezogen { opacity: 0.4; }
  .anordner.ziel-vor { box-shadow: -3px 0 0 0 #6fb2f5; }
  .anordner.ziel-nach { box-shadow: 3px 0 0 0 #6fb2f5; }
  /* Versteckte Karten verschwinden nur außerhalb des Anordnen-Modus. Drin
     bleiben sie blass stehen – sonst wüsste niemand mehr, wo sie hinkommen. */
  .anordner.versteckt > .karte, .anordner.versteckt > .klappkarte {
    opacity: 0.35; filter: grayscale(1);
  }

  /* --- Karte zum Aufklappen -------------------------------------------- */
  /* Der Verlauf ist in der Übersicht zugeklappt: Er ist das größte Element
     der Seite, und wer ihn wirklich lesen will, geht in den eigenen Reiter. */
  .klappkarte > summary {
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .klappkarte > summary::-webkit-details-marker { display: none; }
  .klappkarte > summary h2 { flex: 1; margin: 0; }
  .klappkarte > summary .pfeil {
    flex: none; opacity: 0.5; transition: transform 0.15s ease;
    --mdc-icon-size: 20px;
  }
  .klappkarte[open] > summary { margin-bottom: 12px; }
  .klappkarte[open] > summary .pfeil { transform: rotate(180deg); }
  .karte {
    background: var(--card-background-color, #151d26);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 14px 16px;
  }
  .karte + .karte { margin-top: 16px; }
  .kartenkopf { display: flex; align-items: center; gap: 8px; }
  .kartenkopf h2 { flex: 1; }
  .fragezeichen {
    width: 22px; height: 22px; flex: none; border-radius: 50%;
    font: inherit; font-size: 13px; font-weight: 700; line-height: 1;
    cursor: pointer; color: #6fb2f5;
    background: rgba(111, 178, 245, 0.12);
    border: 1px solid rgba(111, 178, 245, 0.35);
  }
  .fragezeichen:hover {
    background: rgba(111, 178, 245, 0.28);
    border-color: rgba(111, 178, 245, 0.7);
  }
  .fragezeichen.auf-taste { position: absolute; top: 6px; right: 6px; }
  .taste { position: relative; }
  h2 {
    margin: 0 0 12px;
    font-size: 17px;
    font-weight: 600;
    letter-spacing: 0.2px;
  }
  h3 {
    margin: 18px 0 10px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    opacity: 0.55;
  }
  .abzeichen {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 14px; border-radius: 999px; font-weight: 600; font-size: 14px;
    background: rgba(67, 160, 71, 0.15); color: #7bd88f;
  }
  .abzeichen.stoerung { background: rgba(229, 57, 53, 0.15); color: #ff8a80; }

  /* --- Zeilen ---------------------------------------------------------- */
  .zeile {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 12px; border-radius: 12px;
    background: rgba(255, 255, 255, 0.03);
  }
  .zeile + .zeile { margin-top: 6px; }
  .zeile .text { flex: 1; min-width: 0; }
  .zeile .titel { font-size: 14px; font-weight: 600; }
  .zeile .unter { font-size: 12px; opacity: 0.55; }
  /* Rechte Spalte einer Zeile: großer Wert, darunter die Bezeichnung. */
  .zeile .rechts { text-align: right; min-width: 0; }
  .zeile .wert {
    font-size: 20px; font-weight: 600; line-height: 1.2;
    overflow-wrap: anywhere;
  }
  .zeile .wert.lang { font-size: 15px; }
  .zeile .bezeichnung { font-size: 11px; opacity: 0.5; margin-top: 2px; }
  .betriebsart-klein { font-size: 12px; font-weight: 600; margin-top: 2px; }
  .betriebsart-klein.heizt { color: #ffab6f; }
  .betriebsart-klein.abgesenkt { color: #6fb2f5; }
  .kreis-symbole { display: flex; gap: 10px; margin-left: 12px; }
  .kreis-symbole ha-icon { --mdc-icon-size: 20px; opacity: 0.7; }
  .kreis-symbole ha-icon.heizt { color: #ffab6f; opacity: 1; }
  .kreis-symbole ha-icon.abgesenkt { color: #6fb2f5; opacity: 1; }
  .status-zeile {
    display: flex; align-items: center; gap: 12px; padding: 8px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }
  .status-zeile:last-child { border-bottom: none; }
  .status-zeile .titel {
    flex: 1; font-size: 14px; min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  /* Lange Werte (z.B. ein ganzes Zeitprogramm) sprengten die Karte über
     zwanzig Zeilen. Sie werden gekürzt; der volle Text steht im Tooltip und
     in der Detailansicht. */
  .status-zeile .wert {
    font-weight: 600; font-size: 14px; color: #6fb2f5;
    max-width: 60%; text-align: right;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .status-zeile .wert.zustand { color: #7bd88f; }
  .status-zeile .wert.warm { color: #ffab6f; }
  ha-icon { --mdc-icon-size: 22px; opacity: 0.85; flex: none; }

  /* --- Schaubild ------------------------------------------------------- */
  /* Die Isolation macht die Huelle zum Stapelkontext. Ohne sie wuerde
     die Farbflaeche des Speichers mit ihrem negativen z-index nicht nur
     hinter das Bild rutschen, sondern hinter die ganze Karte - und waere
     verschwunden. */
  .schaubild { width: 100%; position: relative; isolation: isolate; }
  .schaubild img { width: 100%; display: block; border-radius: 12px; }

  /* --- Bewegung im Schaubild ------------------------------------------- */
  /* Das Bild selbst ist eine Daten-URL in einem <img> und kennt keine
     Zustände aus Home Assistant. Bewegung entsteht deshalb als eigene Ebene
     darüber, genau wie schon bei den Pumpen.

     Bewegt wird ausschließlich die Hintergrundposition – das läuft im
     Compositor und kostet kein Neuzeichnen. */
  .schaubild .fluss {
    position: absolute; height: 6px; transform: translateY(-50%);
    border-radius: 3px; pointer-events: none;
    opacity: 0; transition: opacity 0.4s ease;
    background-repeat: repeat-x;
    background-size: 26px 6px;
  }
  .schaubild .fluss.laeuft { opacity: 1; animation: stroemen 1.1s linear infinite; }
  .schaubild .fluss.vorlauf {
    background-image: linear-gradient(
      90deg, rgba(255, 214, 194, 0) 0%, rgba(255, 214, 194, 0.85) 45%,
      rgba(255, 214, 194, 0) 70%);
  }
  .schaubild .fluss.ruecklauf {
    background-image: linear-gradient(
      90deg, rgba(198, 224, 255, 0) 0%, rgba(198, 224, 255, 0.85) 45%,
      rgba(198, 224, 255, 0) 70%);
  }
  /* Der Rücklauf fließt zum Kessel zurück, also andersherum. Das gilt für die
     **waagrechte** Leitung. Die senkrechte Stichleitung führt vom Anlagenteil
     hinunter *in* den Rücklauf – dort ist die Grundrichtung schon richtig, und
     ein zweites Umdrehen ließ sie in das Bauteil hineinfließen. */
  .schaubild .fluss.ruecklauf.laeuft { animation-direction: reverse; }
  .schaubild .fluss.senkrecht.ruecklauf.laeuft { animation-direction: normal; }
  @keyframes stroemen {
    from { background-position: 0 0; }
    to { background-position: 26px 0; }
  }

  /* Die Stichleitung hinunter zum Anlagenteil: dieselben Bänder, gekippt.
     Der Vorlauf läuft hinunter zum Verbraucher, der Rücklauf hinauf. */
  .schaubild .fluss.senkrecht {
    width: 6px; height: auto;
    transform: translateX(-50%);
    background-repeat: repeat-y;
    background-size: 6px 26px;
  }
  .schaubild .fluss.senkrecht.vorlauf {
    background-image: linear-gradient(
      180deg, rgba(255, 214, 194, 0) 0%, rgba(255, 214, 194, 0.85) 45%,
      rgba(255, 214, 194, 0) 70%);
  }
  .schaubild .fluss.senkrecht.ruecklauf {
    background-image: linear-gradient(
      180deg, rgba(198, 224, 255, 0) 0%, rgba(198, 224, 255, 0.85) 45%,
      rgba(198, 224, 255, 0) 70%);
  }
  .schaubild .fluss.senkrecht.laeuft { animation-name: stroemen-senkrecht; }
  @keyframes stroemen-senkrecht {
    from { background-position: 0 0; }
    to { background-position: 0 26px; }
  }

  .schaubild .glut {
    position: absolute; height: 26px; transform: translate(-50%, -50%);
    border-radius: 13px; pointer-events: auto; cursor: pointer;
    opacity: 0; transition: opacity 0.6s ease;
    background: radial-gradient(
      ellipse at center, #ffb347 0%, #e2543a 45%, rgba(226, 84, 58, 0) 75%);
  }
  .schaubild .glut.brennt { animation: glimmen 2.6s ease-in-out infinite; }

  /* Mischer: Stellung, nicht Bewegung. Der Zeiger schwenkt beim Wechsel des
     Werts an seine neue Stelle und bleibt dort stehen. */
  .schaubild .mischer-stutzen {
    position: absolute; width: 4px; transform: translateX(-50%);
    pointer-events: none; border-radius: 2px; opacity: 0.85;
    transition: background 0.8s ease;
  }
  .schaubild .mischer {
    position: absolute; transform: translate(-50%, -50%);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
  }
  .schaubild .mischer .zeiger {
    width: 3px; height: 62%; border-radius: 2px;
    background: #f2f6fa;
    box-shadow: 0 0 4px rgba(0, 0, 0, 0.6);
    transform-origin: 50% 50%;
    transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .schaubild .mischer:hover .zeiger { background: #6fb2f5; }

  /* Der Heizkörper, eingefärbt nach seiner Vorlauftemperatur.

     Die Zeichnung füllt die fünf Glieder mit einem festen Verlauf – ein
     Heizkörper, der auch bei 27 Grad glüht. Darüber liegt deshalb diese Ebene
     und malt sie neu: unten die Farbe des Rücklaufs, oben die des Vorlaufs.

     Die Glieder entstehen als wiederholter Verlauf, nicht als fünf Kästen:
     "repeating-linear-gradient" trifft dieselben Abstände wie die Zeichnung
     (Glied 14 breit, Lücke 8, Raster 22), und die Ebene bleibt ein Element.
     Die weiße Kante links in jedem Glied ist der Glanz aus der Zeichnung. */
  .schaubild .heizkoerper {
    position: absolute; pointer-events: none;
    opacity: 0; transition: opacity 0.6s ease;
  }
  /* Ein Element je Glied statt einer Maske über der ganzen Fläche.
     Eine Maske aus einem Streifenverlauf hat harte Ecken; die gezeichneten
     Glieder sind an den Enden rund – Radius 7 bei Breite 14, also genau ein
     Halbkreis. An den vier Ecken jedes Glieds blieb deshalb ein Rest der
     Zeichnung sichtbar. Ein voller Eckradius ergibt dieselbe Rundung, und
     zwar mitskalierend. */
  .schaubild .heizkoerper .glied {
    position: absolute; top: 0; bottom: 0;
    border-radius: 999px;
    transition: background 1.2s ease;
  }
  .schaubild .heizkoerper.da { opacity: 1; }
  /* Heiß genug, um zu arbeiten: ein ruhiges Pulsieren, dieselbe Geste wie am
     Glutbett des Kessels. Nichts blinkt – es soll auffallen, nicht nerven. */
  .schaubild .heizkoerper.heiss { animation: glimmen 3.2s ease-in-out infinite; }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .heizkoerper.heiss { animation: none; }
  }

  /* Die Schichtung des Puffers: oben die Farbe der oberen Temperatur, unten
     die der unteren. Beide sind gemessen, hier wird nichts angedeutet. Ist
     der Speicher durchgeladen, steht er durchgehend in einer Farbe. */
  .schaubild .schichtung {
    position: absolute; pointer-events: none;
    /* Unter das Bild. Das muss ein *negativer* Wert sein: Ein absolut
       gesetztes Element malt sonst ueber jeden in-flow-Inhalt, auch wenn es
       im DOM davor steht. Mit z-index 0 lag die Farbe wieder ueber der
       Zeichnung und verdeckte Naehte, Deckel, Glanz und beim Boiler das
       Register - genau der Zustand, der behoben werden sollte. */
    z-index: -1;
    /* Nicht ausblendbar: Die Zeichnung laesst den Speicherkoerper frei,
       sobald ein Fuehlerwert bekannt ist. Stuende diese Flaeche auf
       Deckkraft null, sae man beim Laden durch den Speicher hindurch. Fehlen
       die Messwerte, setzt die Oberflaeche den neutralen Verlauf des
       Bauteils - er kommt mit den Daten vom Server, damit die Farben nicht
       hier und in schema.py getrennt gepflegt werden muessen. */
    transition: background 1.5s ease;
  }

  /* Ladezustand des Puffers, zwischen seinen beiden Temperaturen. */
  .schaubild .speicher {
    position: absolute; transform: translate(-50%, -50%);
    padding: 2px 8px; border-radius: 999px;
    font-size: 12px; font-weight: 700; letter-spacing: 0.3px;
    background: rgba(10, 14, 19, 0.78);
    pointer-events: none; white-space: nowrap;
    opacity: 0; transition: opacity 0.4s ease;
  }
  .schaubild .speicher.laedt { opacity: 1; color: #ffab6f; }
  .schaubild .speicher.entlaedt { opacity: 1; color: #6fb2f5; }

  /* Lampen des Pumpen-/Relaismoduls. Ohne Anforderung unsichtbar – dann steht
     im Bild die gezeichnete Lampe. Mit Anforderung liegt Grün darüber; die
     Betriebslampe deckt das gezeichnete Rot vollständig ab. */
  .schaubild .lampe {
    position: absolute; transform: translate(-50%, -50%);
    aspect-ratio: 1; border-radius: 50%; pointer-events: none;
    opacity: 0; transition: opacity 0.4s ease;
    /* Innen fast weiß, außen grün: So leuchtet die Lampe, statt nur grün zu
       sein – auf dem dunklen Gehäuse sonst kaum zu sehen. */
    background: radial-gradient(circle at 50% 40%, #d6ffe2 0%, #4ade6a 55%, #2f9e46 100%);
  }
  /* Die Betriebslampe muss die gezeichnete rote vollständig verdecken. */
  .schaubild .lampe.betrieb { box-shadow: 0 0 10px 3px rgba(74, 222, 106, 0.75); }
  .schaubild .lampe.klemme { box-shadow: 0 0 7px 2px rgba(74, 222, 106, 0.7); }
  .schaubild .lampe.an { opacity: 1; }
  .schaubild .lampe.klemme.an { animation: lampe-blinken 1.8s ease-in-out infinite; }
  @keyframes lampe-blinken {
    0%, 100% { opacity: 0.45; }
    50% { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .lampe.klemme.an { animation: none; opacity: 1; }
  }
  @keyframes glimmen {
    0%, 100% { filter: brightness(0.85); }
    50% { filter: brightness(1.25); }
  }

  /* Wer Bewegung abbestellt hat, bekommt den Zustand als ruhige Farbe. */
  @media (prefers-reduced-motion: reduce) {
    .schaubild .fluss.laeuft, .schaubild .glut.brennt { animation: none; }
  }
  .schaubild .pumpe {
    position: absolute; transform: translate(-50%, -50%);
    width: 30px; height: 30px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: rgba(10, 14, 19, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: rgba(255, 255, 255, 0.35);
  }
  .schaubild .pumpe ha-icon { --mdc-icon-size: 18px; opacity: 1; }
  .schaubild .pumpe.laeuft {
    color: #6fb2f5; border-color: rgba(111, 178, 245, 0.6);
    box-shadow: 0 0 10px rgba(111, 178, 245, 0.35);
  }
  .schaubild .pumpe.laeuft ha-icon { animation: dreht 1.6s linear infinite; }
  @keyframes dreht { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .pumpe.laeuft ha-icon { animation: none; }
  }
  .schaubild .marke-wert {
    position: absolute; transform: translate(-50%, -50%);
    background: rgba(10, 14, 19, 0.72); color: #fff;
    font-size: 15px; font-weight: 600; padding: 3px 9px;
    border-radius: 8px; white-space: nowrap;
  }

  .linienwahl { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .linie {
    padding: 5px 10px; border-radius: 999px; font: inherit; font-size: 12px;
    font-weight: 600; cursor: pointer; color: inherit; opacity: 0.45;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .linie:hover { opacity: 0.8; }
  .linie[aria-pressed="true"] {
    opacity: 1; color: #6fb2f5;
    background: rgba(111, 178, 245, 0.15);
    border-color: rgba(111, 178, 245, 0.45);
  }
  .gitter { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }

  /* --- Tasten ---------------------------------------------------------- */
  .taste {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 16px 10px; border-radius: 14px; cursor: pointer;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: inherit; font: inherit; text-align: center;
  }
  .taste:hover { background: rgba(255, 255, 255, 0.08); }
  .taste .beschriftung { font-size: 13px; font-weight: 600; }
  .taste.an { border-color: rgba(111, 178, 245, 0.5); color: #6fb2f5; }
  .taste.an .beschriftung { text-shadow: 0 0 12px rgba(111, 178, 245, 0.6); }
  /* Läuft die Ladung, bricht dieselbe Taste sie ab. Eigene Farbe statt der
     von „an": Blau mit gleichfarbigem Schein sackt auf dunklem Grund ab, und
     warm sagt, dass ein Druck hier einen Gegenbefehl auslöst. */
  .taste.abbrechen { border-color: rgba(255, 176, 122, 0.55); color: #ffc9a3; }
  .taste.abbrechen .beschriftung { text-shadow: none; }
  /* Zweimal rot aufblitzen, wenn die Anlage einen Eingriff nicht annimmt.
     Der Grund steht klein darunter und wird sonst überlesen. */
  @keyframes taste-abgewiesen {
    0%, 100% { border-color: rgba(255, 138, 128, 0.15); }
    50% { border-color: #ff8a80; background: rgba(255, 138, 128, 0.12); }
  }
  .taste.blinkt { animation: taste-abgewiesen 0.6s ease-in-out 2; }
  /* Gesperrt, aber ohne Wartezeiger: Die Anlage braucht für eine Antwort gut
     zwei Sekunden, und dass etwas läuft, sagt die Zeile darunter. */
  .taste[disabled] { opacity: 0.6; cursor: default; }
  select {
    width: 100%; padding: 9px 10px; border-radius: 10px;
    background: rgba(255, 255, 255, 0.05); color: inherit;
    border: 1px solid rgba(255, 255, 255, 0.1); font: inherit;
  }
  .rueckmeldung { font-size: 11px; opacity: 0.5; min-height: 14px; }
  .rueckmeldung.laeuft { opacity: 0.9; color: #6fb2f5; }
  .rueckmeldung.erfolg { opacity: 1; color: #7bd88f; }
  .rueckmeldung.fehler { opacity: 1; color: #ff8a80; }
  .rueckmeldung.wartet { opacity: 0.9; color: #ffab6f; }

  /* --- Steuerung ------------------------------------------------------- */
  .regler { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
  .regler button {
    width: 42px; height: 42px; border-radius: 12px; font: inherit;
    font-size: 20px; font-weight: 600; cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .regler button:hover { background: rgba(255, 255, 255, 0.1); }
  .regler .sollwert { flex: 1; text-align: center; }
  .regler .sollwert .zahl { font-size: 30px; font-weight: 700; line-height: 1.1; }
  .regler .sollwert .beschriftung { font-size: 11px; opacity: 0.5; }
  .betriebsart {
    font-size: 13px; font-weight: 600; color: #6fb2f5;
    margin-bottom: 4px; min-height: 16px;
  }
  .gross { display: flex; align-items: baseline; gap: 10px; }
  .gross .zahl { font-size: 32px; font-weight: 700; }
  .gross .beschriftung { font-size: 12px; opacity: 0.55; }
  .trenner { height: 1px; background: rgba(255, 255, 255, 0.07); margin: 14px 0; }
  .laufzeit-abbruch {
    margin-left: 4px; padding: 2px 8px; border-radius: 999px;
    font: inherit; font-size: 11px; font-weight: 700; cursor: pointer;
    color: #ff8a80;
    background: rgba(229, 57, 53, 0.18);
    border: 1px solid rgba(229, 57, 53, 0.45);
  }
  .laufzeit-abbruch:hover { background: rgba(229, 57, 53, 0.3); }
  .laufzeit-abbruch:disabled { opacity: 0.5; cursor: default; }
  .laufzeit {
    display: inline-flex; align-items: center; gap: 6px; margin-top: 10px;
    padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
    background: rgba(255, 171, 111, 0.15); color: #ffab6f;
  }
  .feld { margin-top: 12px; }
  /* Die Blässe sitzt auf dem Wort, nicht auf der Zeile: Ein durchsichtiger
     Kasten färbt auch das „?" darin blass, und das soll auffallen. */
  .feld > .beschriftung {
    display: flex; align-items: center; gap: 6px;
    font-size: 11px; margin-bottom: 6px;
  }
  .feld > .beschriftung > span { opacity: 0.5; }
  .feld > .beschriftung .fragezeichen { width: 18px; height: 18px; font-size: 11px; }

  /* --- Dialog ---------------------------------------------------------- */
  .schleier {
    position: fixed; inset: 0; z-index: 20;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, 0.55); padding: 16px;
  }
  .dialog {
    background: var(--card-background-color, #151d26);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px; padding: 22px 24px; max-width: 420px; width: 100%;
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
  }
  .dialog-titel { margin: 0 0 10px; font-size: 17px; font-weight: 600;
    text-transform: none; letter-spacing: 0; opacity: 1; }
  /* pre-line: Die Erklärungen bringen Absätze und Aufzählungen mit; ohne das
     liefen sie zu einem einzigen Block zusammen. */
  .dialog-text { font-size: 14px; line-height: 1.5; opacity: 0.8; white-space: pre-line; }
  .dialog.erklaerung { max-width: 520px; }
  .dialog.erklaerung .dialog-text { max-height: 62vh; overflow-y: auto; }
  .dialog-leiste { display: flex; gap: 10px; justify-content: flex-end; margin-top: 22px; }
  .dialog-taste {
    padding: 9px 16px; border-radius: 10px; font: inherit; font-weight: 600;
    cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }
  .dialog-taste:hover { background: rgba(255, 255, 255, 0.12); }
  .dialog-taste.betont { background: rgba(229, 57, 53, 0.2); border-color: rgba(229, 57, 53, 0.5);
    color: #ff8a80; }

  /* --- Zeitprogramme: Wochenraster und Editor -------------------------- */
  /* Die Balken sitzen in Prozent der Spur, nicht in Bildpunkten: Die Karte
     ist mal eine Spalte breit und mal vier. In Bildpunkten säßen die Zeiten
     schon bei der zweiten Breite daneben. */
  .zp-anlagenteil {
    font-size: 12px; opacity: 0.55; margin: -4px 0 12px;
    display: flex; align-items: center; gap: 5px;
  }
  .zp-anlagenteil ha-icon { --mdc-icon-size: 15px; }
  /* Die Einheit hinter dem Eingabefeld: leise, aber da. */
  .zp-einheit { font-size: 12px; opacity: 0.6; min-width: 20px; }

  /* Zahlenfeld in einer Statuszeile - es soll aussehen wie der Wert daneben,
     nicht wie ein Formularfeld. Die Pfeilchen des Browsers sind abgeschaltet:
     Sie sassen ueber der Einheit und trafen die Schrittweite der Anlage
     ohnehin nicht. */
  .zahl-feld { display: flex; align-items: baseline; gap: 5px; }
  .zahl-feld input {
    width: 74px; text-align: right;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px;
    padding: 4px 8px;
    font: inherit; font-size: 14px; font-weight: 600;
    color: var(--primary-text-color, #e6edf3);
  }
  .zahl-feld input:focus {
    outline: none; border-color: #6fb2f5;
    background: rgba(111, 178, 245, 0.12);
  }
  .zahl-feld input::-webkit-outer-spin-button,
  .zahl-feld input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
  .zahl-feld input[type="number"] { -moz-appearance: textfield; appearance: textfield; }
  .zahl-einheit { font-size: 13px; opacity: 0.6; }
  /* Eigene Pfeile links vom Feld. Am Telefon sind die des Browsers kaum zu
     treffen; diese sind so hoch wie das Feld und je 20 px breit. */
  .zahl-stufen { display: flex; flex-direction: column; gap: 2px; align-self: center; }
  .zahl-pfeil {
    width: 22px; height: 15px; padding: 0; line-height: 1;
    display: flex; align-items: center; justify-content: center;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 5px;
    color: var(--primary-text-color, #e6edf3);
    font-size: 9px; cursor: pointer;
  }
  .zahl-pfeil:hover { background: rgba(111, 178, 245, 0.18); border-color: #6fb2f5; }
  .zahl-pfeil:active { background: rgba(111, 178, 245, 0.3); }
  .zeitraster { display: flex; flex-direction: column; gap: 4px; }
  .zeitraster-skala {
    display: flex; justify-content: space-between;
    margin-left: 92px; font-size: 10px; opacity: 0.45;
  }
  .zeitraster-block { padding: 6px 0; }
  .zeitraster-block + .zeitraster-block { border-top: 1px solid rgba(255, 255, 255, 0.06); }
  .zeitraster-zeile { display: flex; align-items: center; gap: 8px; }
  .zeitraster-zeile .tag {
    width: 84px; flex: none; font-size: 12px; font-weight: 600; opacity: 0.75;
  }
  /* Die Schaltzeiten als Text unter dem Balken: Aus dem Balken allein liest
     niemand ab, ob um 05:00 oder um 05:30 geschaltet wird. */
  .zeitraster-zeiten {
    display: flex; flex-wrap: wrap; gap: 6px 14px;
    margin: 6px 0 2px 92px; font-size: 12px; opacity: 0.75;
  }
  .zeitraster-zeiten .schaltzeit { display: inline-flex; align-items: center; gap: 5px; }
  .zeitraster-zeiten .schaltzeit i {
    width: 8px; height: 8px; border-radius: 2px; display: inline-block;
  }
  .zeitraster .spur {
    position: relative; flex: 1; height: 16px; border-radius: 5px;
    background: rgba(255, 255, 255, 0.05); overflow: hidden;
  }
  .zeitraster .spur.leer { opacity: 0.5; }
  .zeitraster .balken { position: absolute; top: 0; bottom: 0; }

  .zp-wirkung {
    margin-top: 12px; padding: 7px 10px; border-radius: 8px; font-size: 12px;
    background: rgba(255, 171, 111, 0.12); color: #ffab6f;
  }
  /* margin-top:auto haelt die Leiste am unteren Rand. Die Karten einer Zeile
     sind gleich hoch (.raster steht auf align-items:stretch), und ohne das
     stand die Taste bei einem kurzen Programm irgendwo in der Mitte, weil
     darunter nur Leerraum kam. Links bleibt sie durch flex-start. */
  .zp-karteleiste {
    display: flex; align-items: center; justify-content: flex-start;
    gap: 12px; margin-top: auto; padding-top: 14px;
  }
  .zp-taste {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 12px; border-radius: 10px; font: inherit; font-size: 13px;
    font-weight: 600; cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }
  .zp-taste ha-icon { --mdc-icon-size: 18px; }
  .zp-taste:hover { background: rgba(255, 255, 255, 0.12); }
  .zp-taste:disabled { opacity: 0.4; cursor: default; }
  .zp-taste.betont { background: rgba(111, 178, 245, 0.16); border-color: rgba(111, 178, 245, 0.4); }

  .dialog.zp-dialog { max-width: 560px; }
  .zp-editor { max-height: 58vh; overflow-y: auto; display: flex;
    flex-direction: column; gap: 12px; }
  /* Leseansicht: dieselben Blockkaesten wie im Editor, aber statt der
     Startpunkte die fertigen Spannen - so steht es auch im Bediengeraet. */
  .zp-uebersicht { max-height: 58vh; overflow-y: auto; display: flex;
    flex-direction: column; gap: 12px; }
  .zp-spannen { display: flex; flex-direction: column; gap: 7px; }
  .zp-spanne { display: flex; align-items: center; gap: 9px; font-size: 14px; }
  .zp-spanne i { width: 9px; height: 9px; border-radius: 3px; flex: none; }
  .zp-spannezeit { font-variant-numeric: tabular-nums; }
  .zp-spannewert { margin-left: auto; font-weight: 600; }
  /* Ueber der Punktetabelle: was hier eingestellt wird, ist der Start einer
     Spanne, nicht die Spanne selbst. */
  .zp-punktekopf {
    font-size: 11px; font-weight: 600; opacity: 0.5; margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .zp-block {
    border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 12px;
  }
  .zp-blockkopf {
    font-size: 12px; font-weight: 600; opacity: 0.6; margin-bottom: 8px;
  }
  .zp-tage { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .zp-tag {
    width: 36px; padding: 6px 0; border-radius: 8px; font: inherit; font-size: 12px;
    font-weight: 600; cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .zp-tag[aria-pressed="true"] {
    background: rgba(111, 178, 245, 0.2); border-color: rgba(111, 178, 245, 0.5);
  }
  .zp-punkte { display: flex; flex-direction: column; gap: 6px; }
  .zp-punkt { display: flex; align-items: center; gap: 8px; }
  .zp-punkt input, .zp-punkt select {
    padding: 6px 8px; border-radius: 8px; font: inherit; font-size: 13px;
    color: inherit; background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }
  .zp-punkt .zp-wert { width: 92px; }
  .zp-weg {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; border-radius: 8px; font: inherit;
    cursor: pointer; color: inherit; background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .zp-weg ha-icon { --mdc-icon-size: 18px; }
  .zp-weg:hover { background: rgba(229, 57, 53, 0.25); color: #ff8a80; }
  .zp-blockleiste { display: flex; gap: 8px; margin-top: 10px; }
  .zp-meldung { font-size: 13px; margin-top: 10px; min-height: 18px; }
  .zp-meldung.fehler { color: #ff8a80; }

  .klickbar { cursor: pointer; }
  .klickbar:hover { background: rgba(255, 255, 255, 0.07); }
  .status-zeile.klickbar:hover { background: rgba(255, 255, 255, 0.05); border-radius: 8px; }
  .marke-wert.klickbar:hover { background: rgba(10, 14, 19, 0.92); }
  .klickbar:focus-visible { outline: 2px solid #6fb2f5; outline-offset: 2px; }
  .hinweis { opacity: 0.6; font-size: 14px; padding: 6px 0; }
  .gut { color: #7bd88f; }
  .schlecht { color: #ff8a80; }
  .mitte { text-align: center; padding: 18px 0; }
  .mitte ha-icon { --mdc-icon-size: 46px; opacity: 0.8; }
  .mitte .haupt { font-size: 16px; font-weight: 600; margin-top: 10px; }
  .mitte .neben { font-size: 13px; opacity: 0.6; margin-top: 4px; }

  .hilfe-suche {
    width: 100%;
    box-sizing: border-box;
    margin-bottom: 12px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.05);
    color: inherit;
    font: inherit;
  }
  .hilfe-suche:focus-visible { outline: 2px solid #6fb2f5; outline-offset: 2px; }
  .hilfe-eintrag { padding: 6px 0; border-top: 1px solid rgba(255, 255, 255, 0.07); }
  .hilfe-eintrag:first-child { border-top: none; }
  .hilfe-eintrag summary { cursor: pointer; font-weight: 500; }
  .hilfe-eintrag summary:focus-visible { outline: 2px solid #6fb2f5; outline-offset: 2px; }
  /* Die Texte tragen Absätze und Aufzählungen als Zeilenumbruch, kein Markup. */
  .hilfe-eintrag p { margin: 6px 0 0; opacity: 0.85; white-space: pre-line; }
  .hilfe-leer { opacity: 0.6; padding: 6px 0; }
`;
