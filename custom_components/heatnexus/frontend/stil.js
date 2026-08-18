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
  /* Farbsätze der Oberfläche.

     Die Vorgabe folgt Home Assistant; wählt jemand einen festen Satz, setzt
     die Oberfläche dieselben Variablen am Wirtselement neu. */
  :host {
    --hn-grund: var(--primary-background-color, #0e1419);
    --hn-karte: var(--card-background-color, #151d26);
    --hn-text: var(--primary-text-color, #e6edf3);
    --hn-gedaempft: color-mix(in srgb, var(--hn-text) 65%, transparent);
    --hn-akzent: #6fb2f5;
    --hn-akzent-text: #0e1419;
    --hn-linie: rgba(255, 255, 255, 0.1);
    --hn-flaeche: rgba(255, 255, 255, 0.05);
  }

  :host {
    display: block;
    background: var(--hn-grund);
    color: var(--hn-text);
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
    background: var(--hn-grund);
    border-bottom: 1px solid var(--hn-flaeche);
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
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
    color: inherit;
  }
  .menue-taste:hover { background: var(--hn-linie); }
  /* Werkzeuge der Kopfzeile: ein Knopf, darunter die Liste. */
  .werkzeuge { position: relative; flex: none; }
  .werkzeugliste {
    position: absolute; right: 0; top: calc(100% + 6px); z-index: 20;
    min-width: 220px; padding: 6px; border-radius: 12px;
    background: var(--hn-karte);
    border: 1px solid var(--hn-linie);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
  }
  .werkzeugliste[hidden] { display: none; }
  .werkzeugliste button {
    display: flex; align-items: center; gap: 10px; width: 100%;
    padding: 9px 10px; border-radius: 9px; cursor: pointer;
    background: none; border: none; color: inherit; text-align: left;
    font: inherit; font-size: 14px; font-weight: 600;
  }
  .werkzeugliste button:hover { background: var(--hn-flaeche); }
  .werkzeugliste ha-icon { --mdc-icon-size: 20px; }
  .kopfleiste .marke { font-size: 20px; font-weight: 700; }
  .kopfleiste .abstand { flex: 1; }
  .aussen {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 12px; border-radius: 999px; font-size: 14px; font-weight: 600;
    background: var(--hn-flaeche);
  }
  .aussen ha-icon { --mdc-icon-size: 18px; }
  .waehler { display: flex; gap: 6px; flex-wrap: wrap; }
  .waehler button {
    padding: 8px 14px; border-radius: 999px; font: inherit; font-size: 13px;
    font-weight: 600; cursor: pointer; color: inherit;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .waehler button:hover { background: var(--hn-linie); }
  .waehler button[aria-selected="true"] {
    background: color-mix(in srgb, var(--hn-akzent) 18%, transparent);
    border-color: color-mix(in srgb, var(--hn-akzent) 50%, transparent);
    color: var(--hn-akzent);
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
    opacity: 1; color: var(--hn-akzent); border-bottom-color: var(--hn-akzent);
  }
  .anlagen-trenner {
    display: flex; align-items: center; gap: 12px;
    margin: 8px 16px 0; padding-top: 16px;
    font-size: 15px; font-weight: 700; letter-spacing: 0.3px;
    border-top: 1px solid var(--hn-linie);
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
    background: color-mix(in srgb, var(--hn-akzent) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--hn-akzent) 35%, transparent);
  }
  .anordnen-leiste .titel { font-weight: 700; font-size: 15px; color: var(--hn-akzent); }
  .anordnen-leiste .hinweis { font-size: 12px; opacity: 0.7; flex: 1; min-width: 180px; }
  .anordnen-leiste .abstand { flex: 1; }
  .anordnen-taste {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 14px; border-radius: 999px; cursor: pointer;
    font: inherit; font-size: 13px; font-weight: 600; color: inherit;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .anordnen-taste:hover { background: var(--hn-linie); }
  .anordnen-taste.fertig {
    background: color-mix(in srgb, var(--hn-akzent) 25%, transparent); border-color: color-mix(in srgb, var(--hn-akzent) 50%, transparent);
    color: #cfe6ff;
  }
  .anordnen-taste ha-icon { --mdc-icon-size: 18px; }
  /* Die Spaltenwahl sieht aus wie die Anlagenwahl oben – gleiche Geste. */
  .spaltenwahl { display: inline-flex; gap: 4px; }
  .spaltenwahl button {
    min-width: 34px; padding: 7px 10px; border-radius: 999px;
    font: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
    color: inherit; opacity: 0.6;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .spaltenwahl button[aria-pressed="true"] {
    opacity: 1; color: var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 15%, transparent);
    border-color: color-mix(in srgb, var(--hn-akzent) 45%, transparent);
  }

  /* Die Hülle, die im Anordnen-Modus um jede Karte liegt. Ohne sie müsste die
     Karte selbst die Griffleiste tragen – und jede Kartenart hätte sie neu
     bekommen müssen. */
  .anordner { display: flex; flex-direction: column; min-width: 0; }
  .anordner > .karte, .anordner > .klappkarte {
    flex: 1;
    border-color: color-mix(in srgb, var(--hn-akzent) 35%, transparent);
    border-top-left-radius: 0; border-top-right-radius: 0;
  }
  .anordner-griff {
    display: flex; align-items: center; gap: 4px;
    padding: 6px 8px; cursor: grab;
    border: 1px solid color-mix(in srgb, var(--hn-akzent) 35%, transparent); border-bottom: none;
    border-radius: 14px 14px 0 0;
    background: color-mix(in srgb, var(--hn-akzent) 16%, transparent);
  }
  .anordner-griff .name {
    flex: 1; min-width: 0; font-size: 12px; font-weight: 600;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .anordner-griff button {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; flex: none; border-radius: 8px;
    background: var(--hn-flaeche); border: 1px solid var(--hn-linie);
    color: inherit; font: inherit; cursor: pointer;
  }
  .anordner-griff button:hover { background: var(--hn-linie); }
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
  .anordner.ziel-vor { box-shadow: -3px 0 0 0 var(--hn-akzent); }
  .anordner.ziel-nach { box-shadow: 3px 0 0 0 var(--hn-akzent); }
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
    background: var(--hn-karte);
    border: 1px solid var(--hn-flaeche);
    border-radius: 16px;
    padding: 14px 16px;
  }
  .karte + .karte { margin-top: 16px; }
  .kartenkopf { display: flex; align-items: center; gap: 8px; }
  .kartenkopf h2 { flex: 1; }
  .fragezeichen {
    width: 22px; height: 22px; flex: none; border-radius: 50%;
    font: inherit; font-size: 13px; font-weight: 700; line-height: 1;
    cursor: pointer; color: var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--hn-akzent) 35%, transparent);
  }
  .fragezeichen:hover {
    background: color-mix(in srgb, var(--hn-akzent) 28%, transparent);
    border-color: color-mix(in srgb, var(--hn-akzent) 70%, transparent);
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
    background: var(--hn-flaeche);
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
  .betriebsart-klein.abgesenkt { color: var(--hn-akzent); }
  .kreis-symbole { display: flex; gap: 10px; margin-left: 12px; }
  .kreis-symbole ha-icon { --mdc-icon-size: 20px; opacity: 0.7; }
  .kreis-symbole ha-icon.heizt { color: #ffab6f; opacity: 1; }
  .kreis-symbole ha-icon.abgesenkt { color: var(--hn-akzent); opacity: 1; }
  .status-zeile {
    display: flex; align-items: center; gap: 12px; padding: 8px 0;
    border-bottom: 1px solid var(--hn-flaeche);
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
    font-weight: 600; font-size: 14px; color: var(--hn-akzent);
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
  /* Die Hülle ist der Bezug für Behälterbreiten. Die Oberfläche setzt darauf
     eine Einheit der Zeichnung, in Kartenbreite ausgedrückt; alles Aufgesetzte
     rechnet damit und wächst mit dem Bild statt in Bildpunkten zu verharren. */
  .schaubild {
    width: 100%; position: relative; isolation: isolate;
    container-type: inline-size;
    --hn-einheit: 0.1cqw;
    /* Pumpenmarke und Leitung teilen sich eine Begrenzung, damit ihr
       Größenverhältnis in jeder Breite dasselbe bleibt. Ohne sie steht die
       Marke auf schmalen Anzeigen als Klecks auf einem Haarstrich. */
    --hn-marke: clamp(16px, calc(var(--hn-einheit) * 28), 40px);
    --hn-strang: clamp(3.43px, calc(var(--hn-einheit) * 6), 8.57px);
    /* Farbe der Wärmeübergabe. Dieselbe, in der die Vorlaufbänder strömen.
       Ein Laufrad sind drei Schaufeln um eine Nabe; in Signalgelb liest sich
       diese Form als Warnzeichen für Strahlung. */
    --hn-uebergabe: #ffd9c2;
    /* Schriftmaß der Marken. Die Karte stellt es ein; die Zeichnung selbst
       bleibt davon unberührt. */
    --hn-schrift: 1;
  }
  .schaubild img { width: 100%; display: block; border-radius: 12px; }

  /* --- Bewegung im Schaubild ------------------------------------------- */
  /* Das Bild selbst ist eine Daten-URL in einem <img> und kennt keine
     Zustände aus Home Assistant. Bewegung entsteht deshalb als eigene Ebene
     darüber, genau wie schon bei den Pumpen.

     Bewegt wird ausschließlich die Hintergrundposition – das läuft im
     Compositor und kostet kein Neuzeichnen. */
  .schaubild .fluss {
    position: absolute;
    height: var(--hn-strang);
    transform: translateY(-50%);
    border-radius: 999px; pointer-events: none;
    opacity: 0; transition: opacity 0.4s ease;
    background-repeat: repeat-x;
    background-size: calc(var(--hn-einheit) * 26) 100%;
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
  /* Wird dem Speicher entnommen, dreht sich beides um: Oben verlässt die Wärme
     ihn, unten kommt sie zurück. */
  .schaubild .fluss.senkrecht.rueckwaerts.laeuft { animation-direction: reverse; }
  .schaubild .fluss.senkrecht.ruecklauf.rueckwaerts.laeuft { animation-direction: reverse; }
  @keyframes stroemen {
    from { background-position: 0 0; }
    to { background-position: calc(var(--hn-einheit) * 26) 0; }
  }

  /* Die Stichleitung hinunter zum Anlagenteil: dieselben Bänder, gekippt.
     Der Vorlauf läuft hinunter zum Verbraucher, der Rücklauf hinauf. */
  .schaubild .fluss.senkrecht {
    width: var(--hn-strang); height: auto;
    transform: translateX(-50%);
    background-repeat: repeat-y;
    background-size: 100% calc(var(--hn-einheit) * 26);
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
    to { background-position: 0 calc(var(--hn-einheit) * 26); }
  }

  .schaubild .glut {
    position: absolute;
    height: calc(var(--hn-einheit) * 26);
    transform: translate(-50%, -50%);
    border-radius: 999px; pointer-events: auto; cursor: pointer;
    opacity: 0; transition: opacity 0.6s ease;
    background: radial-gradient(
      ellipse at center, #ffb347 0%, #e2543a 45%, rgba(226, 84, 58, 0) 75%);
  }
  .schaubild .glut.brennt { animation: glimmen 2.6s ease-in-out infinite; }

  /* Mischer: Stellung, nicht Bewegung. Der Zeiger schwenkt beim Wechsel des
     Werts an seine neue Stelle und bleibt dort stehen. */
  .schaubild .mischer-stutzen {
    position: absolute;
    width: calc(var(--hn-einheit) * 4);
    transform: translateX(-50%);
    pointer-events: none; border-radius: 999px; opacity: 0.85;
    transition: background 0.8s ease;
  }
  .schaubild .mischer {
    position: absolute; transform: translate(-50%, -50%);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
  }
  .schaubild .mischer .zeiger {
    width: calc(var(--hn-einheit) * 3); height: 62%; border-radius: 999px;
    background: #f2f6fa;
    box-shadow: 0 0 4px rgba(0, 0, 0, 0.6);
    transform-origin: 50% 50%;
    transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .schaubild .mischer:hover .zeiger { background: var(--hn-akzent); }

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
  /* Karte: Schaubild und Werteliste nebeneinander, am Handy untereinander. */
  /* Die Karte richtet sich nach ihrer **eigenen** Breite, nicht nach dem
     Fenster: In der Editor-Vorschau steht sie schmal in einem breiten Fenster,
     und feste Schriftgrößen liefen dort ineinander. */
  .karte-zweispaltig { display: grid; gap: 12px; }
  /* **Jede Spalte ist ihr eigener Bezug.** Die Werteliste steht in einem
     Drittel der Kartenbreite; nach der ganzen Karte gemessen blieb sie groß
     und Titel und Wert liefen ineinander. */
  .karte-zweispaltig > * { container-type: inline-size; min-width: 0; }
  /* Gleich hohe Zeilen, auch wo Anlagenteil oder Wert fehlen. Die kompakte
     Ansicht ist durchgehend flacher, nicht einzelne Zeilen darin. */
  .karte-zweispaltig .zeile { min-height: 56px; }
  .karte-zweispaltig .zeile.knapp { min-height: 40px; }
  @container (max-width: 340px) {
    .karte-zweispaltig .zeile .wert { font-size: 16px; }
    .karte-zweispaltig .zeile .wert.lang { font-size: 12px; }
    .karte-zweispaltig .zeile .titel { font-size: 12px; }
    .karte-zweispaltig .zeile .bezeichnung { font-size: 10px; }
    .karte-zweispaltig .zeile { gap: 8px; padding: 8px 10px; min-height: 48px; }
    .karte-zweispaltig .zeile.knapp { min-height: 36px; }
    .karte-zweispaltig .kartenkopf h2 { font-size: 15px; }
  }
  /* Noch schmaler passen Titel und Wert nicht mehr nebeneinander. Dann
     untereinander statt in immer kleinerer Schrift. */
  @container (max-width: 230px) {
    .karte-zweispaltig .zeile {
      flex-direction: column; align-items: flex-start; gap: 2px; min-height: 0;
    }
    .karte-zweispaltig .zeile.knapp { min-height: 0; }
    .karte-zweispaltig .zeile .rechts { text-align: left; }
    .karte-zweispaltig .zeile .wert { font-size: 15px; }
    .karte-zweispaltig .zeile .wert.lang { font-size: 12px; }
  }
  .karte-zweispaltig.lage-rechts { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); }
  .karte-zweispaltig.lage-unten { grid-template-columns: minmax(0, 1fr); }
  @media (max-width: 700px) {
    .karte-zweispaltig.lage-rechts { grid-template-columns: minmax(0, 1fr); }
  }
  /* Die Karte kann die Bewegung abschalten; die Zustände bleiben sichtbar. */
  .schaubild.ruhig * { animation: none !important; }
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
    padding: 0.2em 0.7em; border-radius: 999px;
    font-size: clamp(
      calc(9px * var(--hn-schrift)),
      calc(var(--hn-einheit) * 12 * var(--hn-schrift)),
      calc(18px * var(--hn-schrift))
    );
    font-weight: 700; letter-spacing: 0.3px;
    background: rgba(10, 14, 19, 0.78);
    pointer-events: none; white-space: nowrap;
    opacity: 0; transition: opacity 0.4s ease;
  }
  .schaubild .speicher.laedt { opacity: 1; color: #ffab6f; }
  .schaubild .speicher.entlaedt { opacity: 1; color: var(--hn-akzent); }

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
  /* Der Wärmeübergabepunkt in Betrieb: Glut im Gehäuse, Abgabe nach außen,
     dazu das drehende Laufrad darunter. Ohne Anforderung ist alles
     unsichtbar, dann steht im Bild das gezeichnete Modul. */
  .schaubild .uebergabe {
    position: absolute; pointer-events: none; overflow: hidden;
    opacity: 0; transition: opacity 0.8s ease;
  }
  .schaubild .uebergabe.an { opacity: 1; }
  .schaubild .uebergabe .glut {
    position: absolute; left: 50%; top: 53%; width: 112%; aspect-ratio: 1.15;
    transform: translate(-50%, -50%); border-radius: 50%;
    background: radial-gradient(circle, var(--hn-uebergabe) 0%,
      color-mix(in srgb, var(--hn-uebergabe) 55%, transparent) 45%,
      transparent 72%);
    animation: uebergabe-glimmen 3.4s ease-in-out infinite;
  }
  .schaubild .uebergabe .glut.zwei {
    left: 32%; top: 40%; width: 74%;
    animation-duration: 2.1s; animation-direction: reverse;
  }
  @keyframes uebergabe-glimmen {
    0%, 100% { opacity: 0.12; }
    45% { opacity: 0.40; }
    70% { opacity: 0.22; }
  }
  /* Die Wellen liegen im Gehäuse und werden am Rand beschnitten: Sie sollen
     die Abgabe andeuten, nicht über die Nachbarn im Bild laufen. */
  .schaubild .uebergabe .welle {
    position: absolute; left: 50%; top: 53%; width: 90%; aspect-ratio: 1;
    transform: translate(-50%, -50%); border-radius: 50%;
    border: 2px solid var(--hn-uebergabe); opacity: 0;
    animation: uebergabe-abgabe 3s ease-out infinite;
  }
  .schaubild .uebergabe .welle:nth-child(4) { animation-delay: 1s; }
  .schaubild .uebergabe .welle:nth-child(5) { animation-delay: 2s; }
  @keyframes uebergabe-abgabe {
    0% { opacity: 0; transform: translate(-50%, -50%) scale(0.5); }
    25% { opacity: 0.5; }
    100% { opacity: 0; transform: translate(-50%, -50%) scale(1.45); }
  }
  /* Das eigene Laufrad über dem gezeichneten. Es dreht sich viel langsamer
     als eine Pumpe: Hier fließt keine Fördermenge, hier geht Wärme über. */
  .schaubild .uebergabe-rad {
    position: absolute; transform: translate(-50%, -50%);
    aspect-ratio: 1; border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    background: var(--hn-karte, #151d26);
    color: var(--hn-gedaempft);
    opacity: 0; transition: opacity 0.8s ease, color 0.6s ease;
  }
  .schaubild .uebergabe-rad.an { opacity: 1; color: var(--hn-uebergabe); }
  .schaubild .uebergabe-rad svg {
    display: block; width: 78%; height: 78%; transform-origin: 50% 50%;
  }
  .schaubild .uebergabe-rad.an svg { animation: dreht 16s linear infinite; }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .uebergabe .glut,
    .schaubild .uebergabe .welle,
    .schaubild .uebergabe-rad.an svg { animation: none; }
    .schaubild .uebergabe .glut { opacity: 0.3; }
    .schaubild .uebergabe .welle { opacity: 0; }
  }

  .schaubild .pumpe {
    position: absolute; transform: translate(-50%, -50%);
    width: var(--hn-marke);
    aspect-ratio: 1; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    /* Die stehende Pumpe soll als Pumpe lesbar bleiben. Auf der Leitung wirkte
       die fast schwarze Scheibe wie ein Loch, nicht wie ein Bauteil. */
    background: rgba(26, 32, 40, 0.92);
    border: 1px solid color-mix(in srgb, var(--hn-gedaempft) 45%, transparent);
    color: var(--hn-gedaempft);
    transition: transform 0.5s ease, color 0.4s ease, border-color 0.4s ease,
      box-shadow 0.4s ease;
  }
  /* Das Laufrad ist eine eigene Zeichnung mit dem Nullpunkt in der Mitte des
     Kastens. Ein Symbolzeichensatz gibt diese Mitte nicht her: Die Nabe lag
     neben dem Drehpunkt, und das Rad eierte beim Drehen. */
  .schaubild .pumpe svg {
    display: block; width: 62%; height: 62%;
    transform-origin: 50% 50%;
  }
  /* Die laufende Pumpe tritt hervor. Der Faktor bleibt klein: Eine Marke, die
     doppelt so groß wird, ragte in Kessel und Speicher hinein. */
  .schaubild .pumpe.laeuft {
    color: var(--hn-akzent); border-color: color-mix(in srgb, var(--hn-akzent) 60%, transparent);
    box-shadow: 0 0 10px color-mix(in srgb, var(--hn-akzent) 35%, transparent);
    transform: translate(-50%, -50%) scale(1.18);
  }
  .schaubild .pumpe.laeuft svg { animation: dreht 1.6s linear infinite; }
  @keyframes dreht { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .pumpe.laeuft svg { animation: none; }
  }
  .schaubild .marke-wert {
    position: absolute; transform: translate(-50%, -50%);
    background: rgba(10, 14, 19, 0.72); color: #fff;
    font-size: clamp(
      calc(10px * var(--hn-schrift)),
      calc(var(--hn-einheit) * 15 * var(--hn-schrift)),
      calc(22px * var(--hn-schrift))
    );
    font-weight: 600;
    padding: 0.22em 0.6em;
    border-radius: 0.55em; white-space: nowrap;
  }

  .linienwahl { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .linie {
    padding: 5px 10px; border-radius: 999px; font: inherit; font-size: 12px;
    font-weight: 600; cursor: pointer; color: inherit; opacity: 0.45;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .linie:hover { opacity: 0.8; }
  .linie[aria-pressed="true"] {
    opacity: 1; color: var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 15%, transparent);
    border-color: color-mix(in srgb, var(--hn-akzent) 45%, transparent);
  }
  .gitter { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }

  /* --- Tasten ---------------------------------------------------------- */
  .taste {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 16px 10px; border-radius: 14px; cursor: pointer;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-flaeche);
    color: inherit; font: inherit; text-align: center;
  }
  .taste:hover { background: var(--hn-linie); }
  .taste .beschriftung { font-size: 13px; font-weight: 600; }
  .taste.an { border-color: color-mix(in srgb, var(--hn-akzent) 50%, transparent); color: var(--hn-akzent); }
  .taste.an .beschriftung { text-shadow: 0 0 12px color-mix(in srgb, var(--hn-akzent) 60%, transparent); }
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
    background: var(--hn-flaeche); color: inherit;
    border: 1px solid var(--hn-linie); font: inherit;
  }
  .rueckmeldung { font-size: 11px; opacity: 0.5; min-height: 14px; }
  .rueckmeldung.laeuft { opacity: 0.9; color: var(--hn-akzent); }
  .rueckmeldung.erfolg { opacity: 1; color: #7bd88f; }
  .rueckmeldung.fehler { opacity: 1; color: #ff8a80; }
  .rueckmeldung.wartet { opacity: 0.9; color: #ffab6f; }

  /* --- Steuerung ------------------------------------------------------- */
  .regler { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
  .regler button {
    width: 42px; height: 42px; border-radius: 12px; font: inherit;
    font-size: 20px; font-weight: 600; cursor: pointer; color: inherit;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .regler button:hover { background: var(--hn-linie); }
  .regler .sollwert { flex: 1; text-align: center; }
  .regler .sollwert .zahl { font-size: 30px; font-weight: 700; line-height: 1.1; }
  .regler .sollwert .beschriftung { font-size: 11px; opacity: 0.5; }
  .betriebsart {
    font-size: 13px; font-weight: 600; color: var(--hn-akzent);
    margin-bottom: 4px; min-height: 16px;
  }
  .gross { display: flex; align-items: baseline; gap: 10px; }
  .gross .zahl { font-size: 32px; font-weight: 700; }
  .gross .beschriftung { font-size: 12px; opacity: 0.55; }
  .trenner { height: 1px; background: var(--hn-flaeche); margin: 14px 0; }
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
    background: var(--hn-karte);
    border: 1px solid var(--hn-linie);
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
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .dialog-taste:hover { background: var(--hn-linie); }
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
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie); border-radius: 8px;
    padding: 4px 8px;
    font: inherit; font-size: 14px; font-weight: 600;
    color: var(--hn-text);
  }
  .zahl-feld input:focus {
    outline: none; border-color: var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 12%, transparent);
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
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie); border-radius: 5px;
    color: var(--hn-text);
    font-size: 9px; cursor: pointer;
  }
  .zahl-pfeil:hover { background: color-mix(in srgb, var(--hn-akzent) 18%, transparent); border-color: var(--hn-akzent); }
  .zahl-pfeil:active { background: color-mix(in srgb, var(--hn-akzent) 30%, transparent); }
  .zeitraster { display: flex; flex-direction: column; gap: 4px; }
  .zeitraster-skala {
    display: flex; justify-content: space-between;
    margin-left: 92px; font-size: 10px; opacity: 0.45;
  }
  .zeitraster-block { padding: 6px 0; }
  .zeitraster-block + .zeitraster-block { border-top: 1px solid var(--hn-flaeche); }
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
    background: var(--hn-flaeche); overflow: hidden;
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
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .zp-taste ha-icon { --mdc-icon-size: 18px; }
  .zp-taste:hover { background: var(--hn-linie); }
  .zp-taste:disabled { opacity: 0.4; cursor: default; }
  .zp-taste.betont { background: color-mix(in srgb, var(--hn-akzent) 16%, transparent); border-color: color-mix(in srgb, var(--hn-akzent) 40%, transparent); }

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
    border: 1px solid var(--hn-linie); border-radius: 12px; padding: 12px;
  }
  .zp-blockkopf {
    font-size: 12px; font-weight: 600; opacity: 0.6; margin-bottom: 8px;
  }
  .zp-tage { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .zp-tag {
    width: 36px; padding: 6px 0; border-radius: 8px; font: inherit; font-size: 12px;
    font-weight: 600; cursor: pointer; color: inherit;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .zp-tag[aria-pressed="true"] {
    background: color-mix(in srgb, var(--hn-akzent) 20%, transparent); border-color: color-mix(in srgb, var(--hn-akzent) 50%, transparent);
  }
  .zp-punkte { display: flex; flex-direction: column; gap: 6px; }
  .zp-punkt { display: flex; align-items: center; gap: 8px; }
  .zp-punkt input, .zp-punkt select {
    padding: 6px 8px; border-radius: 8px; font: inherit; font-size: 13px;
    color: inherit; background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .zp-punkt .zp-wert { width: 92px; }
  .zp-weg {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; border-radius: 8px; font: inherit;
    cursor: pointer; color: inherit; background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .zp-weg ha-icon { --mdc-icon-size: 18px; }
  .zp-weg:hover { background: rgba(229, 57, 53, 0.25); color: #ff8a80; }
  .zp-blockleiste { display: flex; gap: 8px; margin-top: 10px; }
  .zp-meldung { font-size: 13px; margin-top: 10px; min-height: 18px; }
  .zp-meldung.fehler { color: #ff8a80; }

  .klickbar { cursor: pointer; }
  /* Nur die Farbe, nicht die ganze Kurzschreibweise: Sonst verlöre das
     Glutbett beim Überfahren seinen Verlauf. */
  .klickbar:hover { background-color: var(--hn-flaeche); }
  /* Die Marken des Schaubilds bringen ihre eigene Fläche mit; die helle
     Zeilenfarbe darüber ließ sie durchsichtig wirken. Die Sperre gilt für
     alle Marken, nicht je Bauteil – die Werteliste hängt daneben, nicht darin. */
  .schaubild .klickbar:hover { background-color: transparent; }
  /* Die Pumpe behält ihre Scheibe und tritt nur etwas hervor. Farbe und Rand
     bleiben dem Zustand überlassen, sonst sähe eine laufende Pumpe beim
     Überfahren wie eine stehende aus. */
  .schaubild .pumpe.klickbar:hover { background-color: rgba(34, 42, 52, 0.96); }
  .status-zeile.klickbar:hover { background: var(--hn-flaeche); border-radius: 8px; }
  .marke-wert.klickbar:hover { background: rgba(10, 14, 19, 0.92); }
  .klickbar:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }
  .hinweis { opacity: 0.6; font-size: 14px; padding: 6px 0; }
  .yaml-feld {
    width: 100%; min-height: 46vh; resize: vertical;
    margin: 10px 0; padding: 10px; border-radius: 10px;
    background: var(--hn-flaeche); color: inherit;
    border: 1px solid var(--hn-linie);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px; line-height: 1.45; white-space: pre;
  }
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
    border: 1px solid var(--hn-linie);
    background: var(--hn-flaeche);
    color: inherit;
    font: inherit;
  }
  .hilfe-suche:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }
  .hilfe-eintrag { padding: 6px 0; border-top: 1px solid var(--hn-flaeche); }
  .hilfe-eintrag:first-child { border-top: none; }
  .hilfe-eintrag summary { cursor: pointer; font-weight: 500; }
  .hilfe-eintrag summary:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }
  /* Die Texte tragen Absätze und Aufzählungen als Zeilenumbruch, kein Markup. */
  .hilfe-eintrag p { margin: 6px 0 0; opacity: 0.85; white-space: pre-line; }
  .hilfe-leer { opacity: 0.6; padding: 6px 0; }
`;
