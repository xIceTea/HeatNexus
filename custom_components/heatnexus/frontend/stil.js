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
  /* Klassen mit eigenem display schlagen sonst die Browserregel für hidden. */
  [hidden] { display: none !important; }

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
    --hn-sonne: #f5c451;
    --hn-ww: #5aa9e6;
    --hn-gut: #7bd88f;
    --hn-at: #4fd1b5;
  }

  :host {
    display: block;
    /* iOS-Safari hebt die Schrift langer Zeilen sonst eigenmächtig an. */
    -webkit-text-size-adjust: 100%;
    text-size-adjust: 100%;
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
  /* Ganz nach rechts, auch wenn die Kopfzeile umbricht: Sonst klebt der
     Knopf an der letzten Anlagentaste statt am Rand. */
  .werkzeuge { position: relative; flex: none; margin-left: auto; }
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
  .reiter button.punkt { position: relative; }
  .reiter button.punkt::after {
    content: ""; position: absolute; top: 6px; right: 6px; width: 8px; height: 8px; border-radius: 50%;
    background: var(--hn-akzent); box-shadow: 0 0 0 2px var(--hn-grund);
  }
  .reiter button.versteckt { text-decoration: line-through; opacity: 0.35; }
  .reiter .reiter-griffe { display: inline-flex; align-items: center; margin-right: 8px; }
  .reiter .reiter-griffe button { padding: 4px; border-bottom: none; opacity: 0.6; }
  .reiter .reiter-griffe button:hover { opacity: 1; }
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
    margin: 10px 16px 12px; padding: 10px 14px; border-radius: 14px;
    max-height: 45vh; overflow-y: auto;
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
  /* Umbrechend statt überlaufend: Auf einem Telefon stehen sechs Farbsätze
     nicht nebeneinander, und was rechts hinausläuft, ist nicht erreichbar. */
  .spaltenwahl { display: flex; flex-wrap: wrap; gap: 4px; max-width: 100%; }
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
  /* Das Programm, nach dem die Anlage gerade faehrt. Voller Akzentrahmen und
     ein Balken an der Kante; der Ring liegt als Schatten aussen an, damit die
     Karte nicht um einen Punkt springt. Nicht Rot: Das heisst hier Stoerung. */
  .karte.aktiv {
    background: color-mix(in srgb, var(--hn-akzent) 12%, var(--hn-karte));
    border-color: var(--hn-akzent);
    box-shadow: inset 5px 0 0 0 var(--hn-akzent), 0 0 0 1px var(--hn-akzent);
  }
  .kartenkopf { display: flex; align-items: center; gap: 8px; }
  .zp-aktiv { margin-left: 6px; color: var(--hn-akzent); font-weight: 600; }
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
  .abhilfe {
    font-size: 13px; color: var(--hn-gedaempft);
    padding: 0 0 8px; white-space: pre-line;
  }
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
  /* Am Wärmeerzeuger pulst die Lampe langsamer: Sie steht für den laufenden
     Betrieb, nicht für eine anliegende Anforderung. */
  .schaubild .lampe.erzeuger.an { animation: lampe-blinken 2.6s ease-in-out infinite; }
  /* Eine Wärmequelle pulst wie ein Erzeuger: Sie liefert, sie fordert nicht an. */
  .schaubild .lampe.quelle.an { animation: lampe-blinken 2.6s ease-in-out infinite; }
  @keyframes lampe-blinken {
    0%, 100% { opacity: 0.45; }
    50% { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .lampe.klemme.an,
    .schaubild .lampe.quelle.an,
    .schaubild .lampe.erzeuger.an { animation: none; opacity: 1; }
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
    /* Gedreht reicht der Kasten des Rads über die Scheibe; ohne Beschnitt
       bleiben dort Reste früherer Bilder stehen. */
    overflow: hidden; contain: paint;
  }
  .schaubild .uebergabe-rad.an { opacity: 1; color: var(--hn-uebergabe); }
  .schaubild .uebergabe-rad .rad {
    display: block; width: 78%; aspect-ratio: 1; transform-origin: 50% 50%;
  }
  .schaubild .uebergabe-rad .rad svg { display: block; width: 100%; height: 100%; }
  .schaubild .uebergabe-rad.an .rad { animation: dreht 16s linear infinite; will-change: transform; }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .uebergabe .glut,
    .schaubild .uebergabe .welle,
    .schaubild .uebergabe-rad.an .rad { animation: none; }
    .schaubild .uebergabe .glut { opacity: 0.3; }
    .schaubild .uebergabe .welle { opacity: 0; }
  }

  .schaubild .pumpe {
    position: absolute; transform: translate(-50%, -50%);
    width: var(--hn-marke);
    aspect-ratio: 1; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    /* Die stehende Pumpe nimmt den Grund der Karte an. Eine feste dunkle
       Scheibe wirkt im hellen Farbsatz wie ein Loch in der Leitung. */
    background: var(--hn-karte, #151d26);
    overflow: hidden; contain: paint;
    border: 1px solid color-mix(in srgb, var(--hn-gedaempft) 45%, transparent);
    color: var(--hn-gedaempft);
    transition: transform 0.5s ease, color 0.4s ease, border-color 0.4s ease,
      box-shadow 0.4s ease;
  }
  /* Das Laufrad ist eine eigene Zeichnung mit dem Nullpunkt in der Mitte des
     Kastens. Ein Symbolzeichensatz gibt diese Mitte nicht her: Die Nabe lag
     neben dem Drehpunkt, und das Rad eierte beim Drehen. */
  /* Gedreht wird der Kasten aus HTML, nicht das SVG selbst: WebKit legt den
     Drehpunkt eines SVG sonst an die Ecke seiner viewBox, und das Rad eiert. */
  .schaubild .pumpe .rad {
    display: block; width: 62%; aspect-ratio: 1;
    transform-origin: 50% 50%;
  }
  .schaubild .pumpe .rad svg { display: block; width: 100%; height: 100%; }
  /* Die laufende Pumpe tritt hervor. Der Faktor bleibt klein: Eine Marke, die
     doppelt so groß wird, ragte in Kessel und Speicher hinein. */
  .schaubild .pumpe.laeuft {
    color: var(--hn-akzent); border-color: color-mix(in srgb, var(--hn-akzent) 60%, transparent);
    box-shadow: 0 0 10px color-mix(in srgb, var(--hn-akzent) 35%, transparent);
    transform: translate(-50%, -50%) scale(1.18);
  }
  /* Das drehende Rad bekommt eine eigene Ebene. Ohne sie rastert WebKit es in
     den mit 1.18 skalierten Elternkasten hinein und rundet dabei je Bild auf
     ganze Pixel – das Rad eiert dann, je nach Position der Pumpe. */
  .schaubild .pumpe.laeuft .rad {
    animation: dreht 1.6s linear infinite;
    will-change: transform;
  }
  @keyframes dreht { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .pumpe.laeuft .rad { animation: none; }
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
  .dialog-zahl-zeile { display: flex; align-items: center; gap: 10px; margin-top: 18px; font-size: 14px; }
  .dialog-zahl { width: 96px; padding: 8px 10px; border-radius: 8px;
    border: 1px solid var(--divider-color); background: var(--card-background-color);
    color: var(--primary-text-color); font-size: 15px; }
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
  .zp-bezeichnung-zeile { display: flex; flex-direction: column; gap: 6px;
    margin-bottom: 12px; font-size: 13px; }
  .zp-bezeichnung { font: inherit; padding: 7px 10px; border-radius: 8px;
    border: 1px solid var(--hn-linie); background: var(--hn-flaeche); color: inherit; }
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
  .zp-spanne.jetzt { margin: 0 -6px; padding: 3px 6px; border-radius: 6px;
    background: color-mix(in srgb, var(--hn-akzent) 16%, transparent); }
  .zp-spanne.jetzt .zp-spannezeit { font-weight: 600; }
  .zp-jetzt { font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
    text-transform: uppercase; color: var(--hn-akzent); }
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

  /* --- Automatik ------------------------------------------------------- */
  /* Gelb steht für Sonne, Blau für nur Warmwasser; Rot bleibt der Störung vorbehalten. */
  .automatik-bereich { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .raster:has(> .automatik-bereich) > * { align-self: start; }
  /* Die Hauptspalte reicht über viele Zeilen; Protokoll und Einladungen stapeln sich rechts daneben. */
  @media (min-width: 1181px) { .raster > .automatik-bereich { grid-row: span 24; } }
  .automatik-bereich > .karte + .karte { margin-top: 0; }
  .automatik-bereich h3 { margin: 0; font-size: 16px; font-weight: 700; text-transform: none; letter-spacing: normal; opacity: 1; }

  /* Kopfkarte */
  .karte.automatik { padding: 18px 20px; }
  .karte.automatik > .kartenkopf { flex-wrap: wrap; gap: 8px 12px; align-items: center; }
  .karte.automatik > .kartenkopf h2 { flex: 0 1 auto; min-width: 0; margin: 0; overflow-wrap: anywhere; line-height: 1.25; }
  .karte.automatik > .kartenkopf .automatik-knopf { margin-left: auto; }
  .automatik-marke {
    display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
    font-size: 12px; font-weight: 600; white-space: nowrap; line-height: 1.2;
    background: var(--hn-flaeche); color: var(--hn-gedaempft);
  }
  .automatik-marke::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
  .automatik-marke.z-sonnentag { background: color-mix(in srgb, var(--hn-sonne) 16%, transparent); color: var(--hn-sonne); }
  .automatik-marke.z-heizpause { background: color-mix(in srgb, var(--hn-at) 16%, transparent); color: var(--hn-at); }
  .automatik-marke.z-nur_ww { background: color-mix(in srgb, var(--hn-ww) 16%, transparent); color: var(--hn-ww); }
  .automatik-marke.z-programm { background: color-mix(in srgb, var(--hn-gut) 16%, transparent); color: var(--hn-gut); }
  .automatik-marke.z-pausiert, .automatik-marke.z-fenster, .automatik-marke.z-abwesend {
    background: color-mix(in srgb, var(--hn-akzent) 14%, transparent); color: var(--hn-akzent);
  }
  .automatik-marke.z-sicherheit, .automatik-marke.z-keine_daten {
    background: rgba(255, 171, 111, 0.15); color: #ffab6f;
  }
  .automatik-meta {
    display: flex; flex-wrap: wrap; gap: 4px 20px; margin: 6px 0 0;
    font-size: 13px; color: var(--hn-gedaempft);
  }
  .automatik-warum { margin: 16px 0 0; font-size: 17px; line-height: 1.5; }
  .automatik-zeile {
    display: flex; align-items: center; gap: 12px 24px; flex-wrap: wrap;
    margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--hn-linie);
  }
  .automatik-gruppe { display: inline-flex; align-items: center; gap: 10px; }
  .automatik-gruppe + .automatik-gruppe, .automatik-schalter + .automatik-gruppe {
    padding-left: 24px; border-left: 1px solid var(--hn-linie);
  }
  .automatik-gruppentitel { font-size: 13px; color: var(--hn-gedaempft); }
  .automatik-gruppentitel .fragezeichen {
    width: 18px; height: 18px; font-size: 11px; margin-left: 6px; vertical-align: middle;
  }
  .automatik-schalter {
    display: inline-flex; align-items: center; gap: 10px; padding: 0; cursor: pointer;
    background: none; border: none; color: inherit; font: inherit; font-size: 14px; font-weight: 600;
  }
  .automatik-schalter i {
    width: 40px; height: 22px; border-radius: 999px; background: var(--hn-linie);
    position: relative; transition: background 0.2s;
  }
  .automatik-schalter i::after {
    content: ""; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px;
    border-radius: 50%; background: var(--hn-text); transition: transform 0.2s;
  }
  .automatik-schalter.an i { background: var(--hn-akzent); }
  .automatik-schalter.an i::after { transform: translateX(18px); background: #fff; }
  .automatik-schalter:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 3px; border-radius: 6px; }
  .automatik-segment {
    display: inline-flex; padding: 3px; border-radius: 10px;
    background: var(--hn-flaeche); border: 1px solid var(--hn-linie);
  }
  .automatik-segment button {
    padding: 6px 12px; border-radius: 7px; border: none; background: none; cursor: pointer;
    color: var(--hn-gedaempft); font: inherit; font-size: 13px; font-weight: 500;
  }
  .automatik-segment button:hover:not([disabled]) { color: var(--hn-text); }
  .automatik-segment button[aria-pressed="true"] {
    background: color-mix(in srgb, var(--hn-akzent) 20%, transparent); color: var(--hn-akzent); font-weight: 600;
  }
  .automatik-segment button:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .automatik-hinweis {
    display: flex; gap: 12px; align-items: center; margin-top: 14px; padding: 10px 14px;
    border-radius: 12px; font-size: 13px;
    background: color-mix(in srgb, var(--hn-akzent) 10%, transparent);
    border: 1px dashed color-mix(in srgb, var(--hn-akzent) 45%, transparent);
  }
  .automatik-hinweis .text { flex: 1; }
  .automatik-hinweis.empfehlung {
    padding: 12px 16px; border: 1px solid var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 16%, transparent);
    box-shadow: inset 4px 0 0 var(--hn-akzent);
  }
  .empfehlung-titel {
    display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
    font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: var(--hn-akzent);
  }
  .empfehlung-titel ha-icon { --mdc-icon-size: 16px; }
  .empfehlung-grund { font-size: 14px; line-height: 1.45; }

  /* Tasten */
  .automatik-knopf {
    padding: 8px 16px; border-radius: 10px; border: 1px solid transparent; cursor: pointer; white-space: nowrap;
    font: inherit; font-size: 13px; font-weight: 600;
    background: var(--hn-akzent); color: var(--hn-akzent-text);
    transition: background 0.15s, color 0.15s, border-color 0.15s;
  }
  .automatik-knopf:hover:not([disabled]) { filter: brightness(1.08); }
  .automatik-knopf:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }
  .automatik-knopf.leise { background: transparent; color: inherit; border-color: var(--hn-linie); }
  .automatik-knopf.leise:hover:not([disabled]) { background: var(--hn-flaeche); filter: none; }
  .automatik-knopf.umriss {
    background: color-mix(in srgb, var(--hn-akzent) 10%, transparent); color: var(--hn-akzent);
    border-color: color-mix(in srgb, var(--hn-akzent) 45%, transparent);
  }
  .automatik-knopf.klein { padding: 6px 12px; font-size: 13px; }
  .automatik-knopf.warnung { color: #ffab6f; border-color: rgba(255, 171, 111, 0.45); }
  .automatik-knopf[disabled], .automatik-segment button[disabled], .automatik-schalter[disabled] {
    opacity: 0.5; cursor: default;
  }
  /* Speichern bleibt grau, bis ein Feld vom gespeicherten Wert abweicht. */
  .automatik-knopf.speichern[disabled] {
    opacity: 1; background: var(--hn-flaeche); color: var(--hn-gedaempft); border-color: var(--hn-linie);
  }
  .automatik-gespeichert { align-self: center; font-size: 12px; color: var(--hn-gut); }
  .automatik-bereich .klickbar { border-radius: 6px; }
  .automatik-bereich .klickbar:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }

  /* Kennwerte */
  .automatik-werte { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
  .automatik-wert {
    padding: 16px 18px; border-radius: 16px; min-width: 0;
    background: var(--hn-karte); border: 1px solid var(--hn-flaeche);
  }
  .automatik-wert .titel { font-size: 13px; color: var(--hn-gedaempft); margin-bottom: 8px; }
  .automatik-wert .werte { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
  .automatik-wert .zahl { font-size: 30px; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
  .automatik-wert.sonne .zahl { color: var(--hn-sonne); }
  .automatik-wert .neben { font-size: 13px; color: var(--hn-gedaempft); }
  .automatik-wert .fuss { font-size: 11px; margin-top: 8px; color: var(--hn-gedaempft); line-height: 1.4; }
  .automatik-wert .automatik-knopf { margin-top: 10px; }
  .automatik-wert .raeume { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
  .automatik-wert .raeume .raum { display: flex; justify-content: space-between; gap: 10px; }
  .automatik-wert .raeume .name { color: var(--hn-gedaempft); }
  .automatik-wert .raeume .wert { font-variant-numeric: tabular-nums; text-align: right; }
  .automatik-wert .raeume .heizt { color: #ffab6f; }
  .automatik-wert .raeume .veraltet { color: #ffab6f; }
  .automatik-wert .vorschlaege { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; font-size: 13px; }
  .automatik-wert .vorschlag { border-top: 1px solid var(--hn-linie); padding-top: 8px; }
  .automatik-wert .vorschlag .kopf { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  .automatik-wert .vorschlag .name { font-weight: 500; }
  .automatik-wert .vorschlag .empfehlung { font-size: 12px; padding: 2px 8px; border-radius: 10px; text-align: right;
    background: color-mix(in srgb, var(--hn-akzent) 18%, transparent); }
  .automatik-wert .vorschlag .angabe { color: var(--hn-gedaempft); font-size: 12px; margin-top: 2px; font-variant-numeric: tabular-nums; }
  .automatik-skala { margin-top: 14px; }
  .automatik-skala .bahn { position: relative; height: 18px; }
  .automatik-skala .bahn::before {
    content: ""; position: absolute; left: 0; right: 0; top: 7px; height: 4px;
    border-radius: 2px; background: var(--hn-linie);
  }
  .automatik-skala .zone { position: absolute; top: 7px; height: 4px; }
  .automatik-skala .zone:first-child { border-radius: 2px 0 0 2px; }
  .automatik-skala .zone.heizt, .automatik-skala .zone.kalt { background: color-mix(in srgb, #ff8a80 55%, transparent); }
  .automatik-skala .zone.hysterese { background: color-mix(in srgb, var(--hn-text) 25%, transparent); }
  .automatik-skala .zone.aus { background: color-mix(in srgb, var(--hn-gut) 55%, transparent); }
  .automatik-skala .zone.sonne { background: var(--hn-sonne); border-radius: 2px; }
  .automatik-skala .zone.neutral { background: color-mix(in srgb, var(--hn-text) 18%, transparent); }
  .automatik-skala .zone.moeglich { background: color-mix(in srgb, var(--hn-sonne) 45%, transparent); }
  .automatik-skala .zone.ueber { background: color-mix(in srgb, var(--hn-gut) 45%, transparent); }
  .automatik-skala .punkt-wert {
    position: absolute; top: -14px; transform: translateX(-50%);
    font-size: 11px; font-weight: 700; color: var(--hn-text); white-space: nowrap;
  }
  .automatik-skala .bahn:has(.punkt-wert) { margin-top: 14px; }
  .automatik-skala .marke { position: absolute; top: 2px; height: 14px; width: 0; border-left: 2px solid var(--hn-text); }
  .automatik-skala .marke.automatik { border-left-style: dashed; border-left-color: var(--hn-akzent); }
  .automatik-skala .marke.stark, .automatik-skala .marke.schwelle { opacity: 0.6; }
  .automatik-skala .marke.ziel { opacity: 0.35; }
  .automatik-skala .punkt {
    position: absolute; top: 3px; width: 12px; height: 12px; margin-left: -6px; border-radius: 50%;
    background: var(--hn-karte); border: 2px solid var(--hn-text);
  }
  .automatik-skala .punkt.gedaempft { border-color: var(--hn-gedaempft); }
  .automatik-skala .punkt.jetzt { width: 3px; height: 16px; top: 1px; margin-left: -1px; border: none; border-radius: 1px; background: var(--hn-text); }
  .automatik-skala .achse {
    display: flex; justify-content: space-between; gap: 6px; margin-top: 8px;
    font-size: 12px; color: var(--hn-gedaempft);
  }
  .automatik-skala .achse > span { white-space: nowrap; }
  .automatik-skala .achse .vorrang-zeile { color: var(--hn-gedaempft); }

  /* Tagesverlauf */
  .karte.automatik-verlauf { padding: 18px 20px; }
  .automatik-verlaufkopf { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 16px; margin-bottom: 14px; }
  .automatik-verlaufkopf .automatik-tagwahl { margin: 0; }
  .automatik-tagwahl {
    display: inline-flex; gap: 2px; padding: 3px; border-radius: 10px;
    background: var(--hn-flaeche); border: 1px solid var(--hn-linie);
  }
  .automatik-tagwahl button {
    padding: 5px 12px; border-radius: 7px; border: none; background: none; cursor: pointer;
    color: var(--hn-gedaempft); font: inherit; font-size: 13px; font-weight: 500;
  }
  .automatik-tagwahl button[aria-pressed="true"] {
    background: color-mix(in srgb, var(--hn-akzent) 20%, transparent); color: var(--hn-akzent); font-weight: 600;
  }
  .automatik-stundenlegende {
    display: flex; flex-wrap: wrap; gap: 4px 16px; margin-left: auto;
    font-size: 12px; color: var(--hn-gedaempft); cursor: help;
  }
  .automatik-stundenlegende i { display: inline-block; width: 12px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
  .automatik-stundenlegende i.m-absenkung { background: var(--hn-sonne); }
  .automatik-stundenlegende i.m-heizpause { background: var(--hn-at); }
  .automatik-stundenlegende i.m-nur_ww { background: var(--hn-ww); }
  .automatik-stundenlegende i.m-programm { background: color-mix(in srgb, var(--hn-text) 35%, transparent); }
  .automatik-vorschau {
    margin: 0 0 12px; padding: 8px 12px; border-radius: 10px; font-size: 13px;
    background: var(--hn-flaeche); border: 1px dashed var(--hn-linie);
  }
  .automatik-stunden {
    display: grid; grid-template-columns: repeat(17, minmax(0, 1fr)); gap: 2px; margin-bottom: 12px;
    user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent;
  }
  .automatik-stunde {
    text-align: center; font: inherit; font-size: 11px; color: var(--hn-gedaempft); cursor: pointer;
    border-radius: 10px; padding: 6px 0 5px; background: none; border: 1px solid transparent;
  }
  .automatik-stunde:hover { background: var(--hn-flaeche); }
  .automatik-stunde:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .automatik-stunde.gezeigt { background: var(--hn-flaeche); border-color: var(--hn-linie); }
  .automatik-stunde.plan .sym, .automatik-stunde.plan .t, .automatik-stunde.plan .raum { opacity: 0.55; }
  .automatik-stunde.plan .streifen { opacity: 0.45; }
  .automatik-stunde .sym { font-size: 15px; line-height: 1.4; color: var(--hn-gedaempft); }
  .automatik-stunde .sym.sonne { color: var(--hn-sonne); }
  .automatik-stunde .sym.mond { color: color-mix(in srgb, var(--hn-sonne) 70%, var(--hn-text)); }
  .automatik-stunde .sym.wolke { color: #9fb3c8; }
  .automatik-stunde .uhr { white-space: nowrap; }
  .automatik-stunde .t { font-size: 14px; font-weight: 700; color: var(--hn-text); }
  .automatik-stunde .t.kalt { color: var(--hn-text); }
  .automatik-stunde .t.warm { color: var(--hn-text); }
  .automatik-stunde .streifen {
    height: 3px; border-radius: 2px; margin: 6px 6px 5px;
    background: color-mix(in srgb, var(--hn-text) 30%, transparent);
  }
  .automatik-stunde .streifen.absenkung { background: var(--hn-sonne); }
  .automatik-stunde .streifen.heizpause { background: var(--hn-at); }
  .automatik-stunde .streifen.nur_ww { background: var(--hn-ww); }
  .automatik-stunde .raum { font-size: 11px; color: var(--hn-gedaempft); font-variant-numeric: tabular-nums; }
  .automatik-stundenkasten {
    margin: 0 0 14px; padding: 10px 14px; border-radius: 10px;
    background: var(--hn-flaeche); font-size: 13px; line-height: 1.5;
  }
  .automatik-stundenwerte { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 20px; }
  .automatik-stundenwerte .kopf { font-weight: 700; }
  .automatik-stundenwerte .modus { font-weight: 600; }
  .automatik-stundenwerte .modus.m-absenkung { color: var(--hn-sonne); }
  .automatik-stundenwerte .modus.m-heizpause { color: var(--hn-at); }
  .automatik-stundenwerte .modus.m-nur_ww { color: var(--hn-ww); }
  .automatik-stundenwerte .vorrang { color: var(--hn-sonne); }
  .automatik-verlaufkopf .korrektur {
    display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px 8px;
    font-size: 12px; color: var(--hn-gedaempft);
  }
  .automatik-schalter.klein { font-size: 12px; font-weight: 500; gap: 8px; }
  .automatik-schalter.klein i { width: 30px; height: 18px; }
  .automatik-schalter.klein i::after { width: 12px; height: 12px; }
  .automatik-schalter.klein.an i::after { transform: translateX(12px); }
  .automatik-korrekturmarke {
    padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap;
    background: var(--hn-flaeche); color: var(--hn-gedaempft); opacity: 0.75;
  }
  .automatik-korrekturmarke.wirkt {
    opacity: 1; background: color-mix(in srgb, var(--hn-akzent) 16%, transparent); color: var(--hn-akzent);
  }
  .automatik-stundenkasten .protokoll { font-size: 12px; color: var(--hn-gedaempft); margin-top: 2px; }
  .automatik-tag-bild {
    position: relative; touch-action: pan-y; cursor: crosshair;
    user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent;
  }
  .automatik-tag-bild svg { display: block; width: 100%; height: 190px; }
  .automatik-bildmarke {
    position: absolute; transform: translateY(-110%); font-size: 11px; line-height: 1;
    color: var(--hn-gedaempft); pointer-events: none;
  }
  .automatik-bildmarke.achse { left: 4px; }
  .automatik-bildmarke.grenze { right: 4px; }
  .automatik-zeiger {
    position: absolute; top: 0; bottom: 0; width: 0; pointer-events: none;
    border-left: 1px solid var(--hn-text); opacity: 0.6;
  }
  .automatik-tipp {
    position: absolute; top: 4px; pointer-events: none; z-index: 2;
    background: var(--hn-karte); border: 1px solid var(--hn-linie); border-radius: 8px;
    padding: 6px 9px; font-size: 12px; line-height: 1.45; white-space: nowrap;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
  }
  .automatik-tipp > div:first-child { font-weight: 700; }
  .automatik-tag .al-sonne {
    fill: color-mix(in srgb, var(--hn-sonne) 22%, transparent);
    stroke: color-mix(in srgb, var(--hn-sonne) 55%, transparent); stroke-width: 1; vector-effect: non-scaling-stroke;
  }
  .automatik-tag .al-grund { fill: var(--hn-flaeche); }
  .automatik-tag .al-m-programm { fill: color-mix(in srgb, var(--hn-text) 28%, transparent); }
  .automatik-tag .al-m-absenkung, .automatik-tag .al-absenkung { fill: var(--hn-sonne); }
  .automatik-tag .al-m-heizpause { fill: var(--hn-at); }
  .automatik-tag .al-m-nur_ww { fill: var(--hn-ww); }
  .automatik-tag .al-plan, .automatik-tag .al-verlaengerung { opacity: 0.45; }
  .automatik-tag .al-verlaengerung { fill: var(--hn-sonne); }
  .automatik-tag .al-jetzt {
    stroke: var(--hn-text); stroke-width: 1; stroke-dasharray: 3 3; vector-effect: non-scaling-stroke; opacity: 0.7;
  }
  .automatik-tag .al-aussen { fill: none; stroke: #ffab6f; stroke-width: 2; vector-effect: non-scaling-stroke; }
  .automatik-tag .al-prognose {
    fill: none; stroke: #ffab6f; stroke-width: 2; stroke-dasharray: 3 4; vector-effect: non-scaling-stroke;
  }
  .automatik-tag .al-gedaempft { fill: none; stroke: var(--hn-at); stroke-width: 2; vector-effect: non-scaling-stroke; }
  .automatik-tag .al-vorhersage {
    fill: none; stroke: var(--hn-akzent); stroke-width: 2; stroke-dasharray: 4 3; vector-effect: non-scaling-stroke;
  }
  .automatik-tag .al-grenze { stroke: var(--hn-gedaempft); stroke-dasharray: 6 5; vector-effect: non-scaling-stroke; }
  .automatik-achse { display: flex; justify-content: space-between; font-size: 11px; color: var(--hn-gedaempft); margin-top: 6px; }
  .automatik-legende { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12px; color: var(--hn-gedaempft); margin-top: 12px; }
  /* Farbmarke und Text je Eintrag auf einer Mittellinie, auch für die dünnen Linien. */
  .automatik-legende > span { display: inline-flex; align-items: center; }
  .automatik-legende i { display: inline-block; width: 14px; height: 10px; border-radius: 3px; margin-right: 6px; flex-shrink: 0; }
  .automatik-legende i.al-aussen { background: #ffab6f; height: 2px; }
  .automatik-legende i.al-prognose { height: 2px; background: repeating-linear-gradient(90deg, #ffab6f 0 3px, transparent 3px 6px); }
  .automatik-legende i.al-gedaempft { background: var(--hn-at); height: 2px; }
  .automatik-legende i.al-vorhersage { height: 2px; background: repeating-linear-gradient(90deg, var(--hn-akzent) 0 4px, transparent 4px 7px); }
  .automatik-legende i.al-grenze { height: 2px; background: repeating-linear-gradient(90deg, var(--hn-gedaempft) 0 4px, transparent 4px 7px); }
  .automatik-legende i.al-sonne { background: color-mix(in srgb, var(--hn-sonne) 45%, transparent); }

  /* Einstellungen */
  .karte.automatik-erweitert { padding: 0; }
  .automatik-einstellungskopf {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 16px 20px;
    cursor: pointer; list-style: none;
  }
  .automatik-einstellungskopf::-webkit-details-marker { display: none; }
  .automatik-einstellungskopf .pfeil { --mdc-icon-size: 20px; opacity: 0.6; transform: rotate(-90deg); transition: transform 0.15s; }
  .automatik-erweitert[open] .automatik-einstellungskopf .pfeil { transform: none; }
  .automatik-einstellungskopf .titelblock { flex: 1; min-width: 180px; }
  .automatik-einstellungskopf .unter { font-size: 12px; color: var(--hn-gedaempft); margin-top: 2px; }
  .karte.automatik-erweitert { position: relative; }
  /* Die Tasten stehen nach dem summary und sitzen optisch in dessen Zeile; zugeklappt sind sie verborgen. */
  .automatik-einstellungstasten {
    display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
    position: absolute; top: 14px; right: 20px;
  }
  .automatik-erweitert[open] > .automatik-einstellungskopf { padding-right: 380px; }
  .automatik-erweitert:not([open]) .automatik-einstellungstasten { display: none; }
  .automatik-gruppen {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding: 0 20px 4px;
  }
  .automatik-einstellungsgruppe {
    border: 1px solid var(--hn-linie); border-radius: 12px; padding: 4px 16px 6px; min-width: 0;
  }
  .automatik-einstellungsgruppe h4 {
    margin: 10px 0 4px; font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--hn-gedaempft);
  }
  .automatik-feld {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 9px 0; border-top: 1px solid var(--hn-flaeche); min-height: 48px;
  }
  .automatik-einstellungsgruppe h4 + .automatik-feld { border-top: none; }
  .automatik-feldtext { min-width: 0; }
  .automatik-feldtitel {
    padding: 0; border: none; background: none; color: inherit; font: inherit; font-size: 14px; text-align: left;
  }
  button.automatik-feldtitel { cursor: help; }
  button.automatik-feldtitel:hover { text-decoration: underline dotted; text-underline-offset: 3px; }
  button.automatik-feldtitel:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; border-radius: 4px; }
  .automatik-feld.geaendert .automatik-feldtitel::after {
    content: ""; display: inline-block; width: 6px; height: 6px; margin-left: 8px; border-radius: 50%;
    background: var(--hn-akzent); vertical-align: middle;
  }
  .automatik-feld .profilwert { font-size: 11px; color: var(--hn-gedaempft); margin-top: 2px; }
  .automatik-feld .eingabe { display: flex; align-items: center; gap: 8px; flex: none; }
  .automatik-feld input, .automatik-feld select {
    padding: 6px 10px; border-radius: 8px; font: inherit; font-size: 14px;
    background: var(--hn-grund); color: inherit; border: 1px solid var(--hn-linie);
  }
  .automatik-feld input { width: 72px; text-align: right; font-variant-numeric: tabular-nums; }
  .automatik-feld input[type="time"] { width: 96px; }
  .automatik-feld select { min-width: 100px; }
  .automatik-feld.breit select { min-width: 200px; }
  .automatik-feld.geaendert input, .automatik-feld.geaendert select { border-color: color-mix(in srgb, var(--hn-akzent) 55%, transparent); }
  .automatik-feld input:focus-visible, .automatik-feld select:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .automatik-feld .einheit { width: 28px; font-size: 12px; color: var(--hn-gedaempft); }
  .automatik-leiste { display: flex; gap: 8px; margin: 0; padding: 16px 20px; flex-wrap: wrap; }

  /* Protokoll */
  .automatik-protokollkarte { padding: 18px 20px; }
  .automatik-protokollkarte > .kartenkopf h2 { margin: 0; }
  .automatik-verweis {
    padding: 0; border: none; background: none; cursor: pointer;
    font: inherit; font-size: 13px; color: var(--hn-akzent);
  }
  .automatik-verweis:hover { text-decoration: underline; }
  .automatik-protokolltag {
    margin: 16px 0 2px; padding-bottom: 6px; border-bottom: 1px solid var(--hn-linie);
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--hn-gedaempft);
  }
  .automatik-protokoll { list-style: none; margin: 0; padding: 0; }
  .automatik-protokoll li {
    display: grid; grid-template-columns: 48px 1fr; gap: 12px; align-items: baseline;
    padding: 10px 0; border-bottom: 1px solid var(--hn-flaeche); font-size: 13px; line-height: 1.45;
  }
  .automatik-protokoll li:last-child { border-bottom: none; }
  .automatik-protokoll .zeit {
    color: var(--hn-gedaempft); font-variant-numeric: tabular-nums;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px;
  }
  .automatik-protokoll .inhalt { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
  .automatik-protokoll .art { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
  .automatik-protokoll .art.geschrieben { background: color-mix(in srgb, var(--hn-gut) 16%, transparent); color: var(--hn-gut); }
  .automatik-protokoll .art.haette, .automatik-protokoll .art.empfohlen, .automatik-protokoll .art.verworfen { border: 1px dashed rgba(245, 196, 81, 0.6); color: var(--hn-sonne); }
  .automatik-protokoll .art.abgelehnt { background: rgba(229, 57, 53, 0.15); color: #ff8a80; }
  .automatik-protokoll .art.budget, .automatik-protokoll .art.eingriff { background: rgba(255, 171, 111, 0.15); color: #ffab6f; }
  .automatik-protokoll .art.geprueft, .automatik-protokoll .art.einstellung { background: var(--hn-flaeche); color: var(--hn-gedaempft); }

  /* Einladung */
  .automatik-einladungskarte { border-style: dashed; padding: 18px 20px; }
  .automatik-einladungskarte > .kartenkopf h2 { margin: 0; }
  .automatik-stand { margin-left: auto; font-size: 12px; color: var(--hn-gedaempft); white-space: nowrap; }
  .automatik-einladung { font-size: 13px; line-height: 1.55; color: var(--hn-gedaempft); margin: 10px 0 14px; }
  .karte > .automatik-knopf { align-self: flex-start; }

  /* Einrichtungsdialog */
  .automatik-beschriftet { margin-top: 8px; }
  .automatik-unter { font-size: 12px; color: var(--hn-gedaempft); margin-bottom: 4px; }
  .automatik-haken-zeile.veraltet { color: #ffab6f; }
  .automatik-dialog {
    max-width: 560px; max-height: 86vh; padding: 0; overflow: hidden;
    display: flex; flex-direction: column;
  }
  .automatik-dialog .dialog-kopf {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 14px 14px 12px 24px; border-bottom: 1px solid var(--hn-linie);
  }
  .automatik-dialog .dialog-titel { margin: 0; }
  .automatik-dialog-inhalt { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 4px 24px 18px; }
  .automatik-dialog .dialog-leiste {
    margin-top: 0; padding: 14px 24px 18px; border-top: 1px solid var(--hn-linie);
  }
  .dialog-schliessen {
    flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%;
    border: none; background: transparent; color: inherit; opacity: 0.7;
    font-size: 24px; line-height: 1; cursor: pointer;
  }
  .dialog-schliessen:hover { background: var(--hn-flaeche); opacity: 1; }
  .dialog-schliessen:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
  .automatik-dialog section { margin-top: 14px; }
  .automatik-dialog h4 { margin: 0 0 6px; font-size: 13px; font-weight: 600; opacity: 0.7; }
  .automatik-dialog select { margin-top: 6px; }
  .automatik-haken {
    max-height: 160px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px;
  }
  .automatik-haken-zeile {
    display: flex; align-items: center; gap: 8px; font-size: 13px; flex-shrink: 0;
  }
  .automatik-beschriftet > .automatik-haken-zeile { margin-bottom: 6px; }
  @media (max-width: 900px) {
    .automatik-gruppen { grid-template-columns: minmax(0, 1fr); }
  }
  @media (max-width: 700px) {
    .automatik-stunden {
      grid-template-columns: repeat(17, minmax(52px, 1fr)); overflow-x: auto;
      scroll-snap-type: x proximity; scrollbar-width: thin; padding-bottom: 4px;
    }
    .automatik-stunde { scroll-snap-align: start; }
    .automatik-werte { grid-template-columns: minmax(0, 1fr); }
    .automatik-feld.breit select { min-width: 0; max-width: 55vw; }
    .automatik-gruppe + .automatik-gruppe, .automatik-schalter + .automatik-gruppe { padding-left: 0; border-left: none; }
    /* Das Segment nimmt die ganze Zeile unter dem Titel ein; lange Tasten brechen um, statt überzustehen. */
    .automatik-gruppe { flex: 1 1 100%; min-width: 0; flex-wrap: wrap; gap: 6px 10px; }
    .automatik-segment { flex: 1 1 100%; min-width: 0; }
    .automatik-segment button { flex: 1 1 0; min-width: 0; padding: 6px 8px; hyphens: auto; overflow-wrap: break-word; }
    .automatik-hinweis { flex-wrap: wrap; }
    .automatik-hinweis .text { flex: 1 1 100%; }
    .automatik-stundenlegende { margin-left: 0; }
    .automatik-einstellungstasten { position: static; padding: 0 20px 12px; }
    .automatik-erweitert[open] > .automatik-einstellungskopf { padding-right: 20px; }
  }
`;
