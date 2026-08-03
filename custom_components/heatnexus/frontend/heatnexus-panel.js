/**
 * HeatNexus – eigene Oberfläche für die Heizung.
 *
 * Die Aufteilung kommt fertig aus der Integration (`panel.config.daten`);
 * hier wird sie nur dargestellt und mit den aktuellen Werten aus `hass`
 * gefüllt. Es gibt keine fest verdrahteten Entitäts-IDs.
 *
 * Bewusst ohne Framework und ohne Bauschritt: Die Datei wird so ausgeliefert,
 * wie sie hier steht.
 */

const OHNE_WERT = ["unavailable", "unknown", "none", ""];

// Wie lange „übertragen ✓" stehen bleibt, bevor wieder der Zustand erscheint.
const RUECKMELDUNG_MS = 4000;

// Wie lange auf die Bestätigung der Anlage gewartet wird, bevor die
// Rückmeldung aufgibt. Die Anlage wird nur alle 30 s abgefragt – drei
// Minuten reichen also für mehrere Versuche. Länger zu warten hilft nicht:
// Wird der Vorgang inzwischen an der Anlage selbst abgebrochen, bliebe
// „wird ausgeführt …" sonst minutenlang stehen, obwohl nichts mehr läuft.
const BESTAETIGUNG_MAX_MS = 3 * 60 * 1000;

const REITER = [
  { schluessel: "uebersicht", titel: "Übersicht", symbol: "mdi:view-dashboard-outline" },
  { schluessel: "steuerung", titel: "Steuerung", symbol: "mdi:tune-vertical" },
  { schluessel: "wartung", titel: "Wartung", symbol: "mdi:wrench-outline" },
  { schluessel: "verlauf", titel: "Verlauf", symbol: "mdi:chart-line" },
];

// Wie breit eine Karte höchstens werden darf, in Spalten. Deckt sich mit
// `anordnung.BREITE_MAX` auf der Serverseite – was hier durchgeht, muss dort
// gespeichert werden können.
const BREITE_MAX = 4;

// Wie lange nach der letzten Änderung gewartet wird, bevor die Anordnung
// gespeichert wird. Beim Ziehen fallen mehrere Änderungen kurz hintereinander
// an; jede einzeln zu schreiben hieße, dieselbe Liste mehrfach abzulegen.
const SPEICHERN_MS = 500;

/**
 * Zwei Reihenfolgen zusammenführen: `basis` gilt, `rest` füllt auf.
 *
 * Was in `basis` steht, behält seinen Platz. Alles, was nur in `rest` steht,
 * wird dort eingefügt, wo es nach `rest` hingehört – direkt hinter dem
 * nächsten Vorgänger, der bereits einen Platz hat. Hat es keinen, kommt es
 * nach vorn.
 */
function reihenfolgeMischen(basis, rest) {
  const ergebnis = [...basis];
  (rest || []).forEach((kennung, stelle) => {
    if (ergebnis.includes(kennung)) return;
    let ziel = 0;
    for (let vorher = stelle - 1; vorher >= 0; vorher--) {
      const platz = ergebnis.indexOf(rest[vorher]);
      if (platz >= 0) {
        ziel = platz + 1;
        break;
      }
    }
    ergebnis.splice(ziel, 0, kennung);
  });
  return ergebnis;
}

/**
 * Die gespeicherte Reihenfolge auf die tatsächlich vorhandenen Karten anwenden.
 *
 * **Neue Anlagenteile dürfen die Anordnung nicht zerreißen.** Gespeichert ist
 * nur die Reihenfolge bekannter Kennungen; was neu dazukommt, landet an der
 * Stelle, an der es von Haus aus stünde, und nicht am Ende. Kennungen, die es
 * nicht mehr gibt, fallen still weg. Dieselbe Rechnung steht in
 * `anordnung.ordnung_anwenden` auf der Serverseite.
 */
function ordnungAnwenden(standard, gespeichert) {
  const vorhanden = new Set(standard);
  return reihenfolgeMischen(
    (gespeichert || []).filter((kennung) => vorhanden.has(kennung)),
    standard
  );
}

const STIL = `
  :host {
    display: block;
    background: var(--primary-background-color, #0e1419);
    color: var(--primary-text-color, #e6edf3);
    min-height: 100%;
    box-sizing: border-box;
  }
  * { box-sizing: border-box; }

  /* --- Kopfleiste: Menütaste, Marke, Anlagenwahl, Reiter --------------- */
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
  /* Ein Raster für alle vier Reiter. Bis 1.2.0 hatte die Übersicht ein
     eigenes mit drei festen Spalten und je Spalte einem Stapel Karten. Damit
     ließ sich nichts umsortieren: Die Reihenfolge steckte im Stapel und
     nicht in einer Liste. Jetzt liegt jede Karte einzeln im Raster, und die
     Reihenfolge ist genau die, die der Nutzer wählt.

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
  .schaubild { width: 100%; position: relative; }
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
  .taste[disabled] { opacity: 0.6; cursor: progress; }
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
`;

class HeatNexusPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._gebaut = false;
    this._daten = null;
    this._bindungen = [];
    this._verlaufskarten = [];
    // „Alle" ist der Standard: Wer zwei Anlagen hat, will beide sehen, nicht
    // die erste. Bei nur einer Anlage gibt es die Wahl gar nicht.
    this._anlageIndex = -1;
    this._reiter = "uebersicht";
    // Laufende Bedienvorgänge: Anzeige -> wann begonnen, wann bestätigt.
    this._wartend = [];
    // Selbst gewählte Anordnung je Reiter; leer heißt: Standard.
    this._anordnung = {};
    this._anordnen = false;
    this._speicherAuftrag = null;
    // Welche Karte gerade gezogen wird; null, solange niemand zieht.
    this._gezogen = null;
    // Betriebswahl je Kreis, wie sie **vor** einer Warmwasserladung stand.
    // Beim Abbrechen wird genau die wiederhergestellt.
    this._wahlVorLadung = {};
  }

  set panel(panel) {
    const daten = panel && panel.config ? panel.config.daten : null;
    if (daten !== this._daten) {
      this._daten = daten;
      this._gebaut = false;
    }
    this._zeichnen();
  }

  set hass(hass) {
    const erster = !this._hass;
    this._hass = hass;
    // Die Aufteilung aus `panel.config` stammt aus dem Augenblick der
    // Einrichtung – da war die Anlage erst zur Hälfte eingelesen. Deshalb
    // wird sie beim Öffnen einmal frisch geholt.
    if (erster) {
      this._datenHolen();
      this._anordnungHolen();
    }
    this._zeichnen();
  }

  async _datenHolen() {
    try {
      const daten = await this._hass.callWS({ type: "heatnexus/panel_daten" });
      if (!daten || !daten.anlagen || !daten.anlagen.length) return;
      this._daten = daten;
      this._gebaut = false;
      this._zeichnen();
    } catch (err) {
      // Ohne frische Daten bleibt der Stand aus der Panel-Konfiguration.
      console.warn("HeatNexus: Aufteilung konnte nicht geladen werden", err);
    }
  }

  /** Die eigene Anordnung holen; ohne sie gilt die Standardanordnung. */
  async _anordnungHolen() {
    try {
      this._anordnung = (await this._hass.callWS({ type: "heatnexus/anordnung" })) || {};
      this._gebaut = false;
      this._zeichnen();
    } catch (err) {
      console.warn("HeatNexus: Anordnung konnte nicht geladen werden", err);
    }
  }

  set narrow(_narrow) {
    /* Die Aufteilung regelt CSS. */
  }

  // -------------------------------------------------------------------
  // Werte
  // -------------------------------------------------------------------
  _zustand(entity) {
    return this._hass && this._hass.states ? this._hass.states[entity] : undefined;
  }

  _hatWert(entity) {
    const zustand = this._zustand(entity);
    return !!zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase());
  }

  _text(entity) {
    const zustand = this._zustand(entity);
    if (!this._hatWert(entity)) return "–";
    if (this._hass.formatEntityState) return this._hass.formatEntityState(zustand);
    const einheit = zustand.attributes.unit_of_measurement;
    return einheit ? `${zustand.state} ${einheit}` : zustand.state;
  }

  _zahl(entity) {
    const zustand = this._zustand(entity);
    if (!this._hatWert(entity)) return null;
    const wert = Number.parseFloat(zustand.state);
    return Number.isNaN(wert) ? null : wert;
  }

  _name(entity) {
    const zustand = this._zustand(entity);
    return (zustand && zustand.attributes.friendly_name) || entity;
  }

  /**
   * Ein Element zur Entität führen: Klick öffnet die Detailansicht.
   *
   * `hass-more-info` ist das Ereignis, das auch die Lovelace-Karten benutzen.
   * Es muss den Schattenbaum verlassen, sonst hört Home Assistant es nicht –
   * daher `composed`.
   */
  _klickbar(element, entity) {
    if (!entity) return element;
    element.classList.add("klickbar");
    element.setAttribute("role", "button");
    element.setAttribute("tabindex", "0");
    const oeffnen = () => {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId: entity },
          bubbles: true,
          composed: true,
        })
      );
    };
    element.addEventListener("click", oeffnen);
    element.addEventListener("keydown", (ereignis) => {
      if (ereignis.key === "Enter" || ereignis.key === " ") {
        ereignis.preventDefault();
        oeffnen();
      }
    });
    return element;
  }

  /** Ob eine Pumpe fördert. Manche melden keinen Zustand, sondern ihre Drehzahl. */
  _foerdert(entity) {
    const zahl = this._zahl(entity);
    return zahl !== null ? zahl > 0 : this._istAn(entity);
  }

  /** Ob an dieser Anlage gerade irgendeine Pumpe fördert. */
  _foerdertEtwas(anlage) {
    return (anlage.schema_pumpen || []).some((eintrag) => this._foerdert(eintrag.entity));
  }

  _stoerung(anlage) {
    return (anlage.stoerungen || []).some((s) => {
      const zustand = this._zustand(s.entity);
      return zustand && zustand.attributes.stoerung_aktiv === true;
    });
  }

  // -------------------------------------------------------------------
  // Aufbau
  // -------------------------------------------------------------------
  _zeichnen() {
    if (!this._hass || !this._daten) return;
    if (!this._gebaut) {
      this._aufbauen();
      this._gebaut = true;
    }
    this._aktualisieren();
  }

  _anlagen() {
    return (this._daten && this._daten.anlagen) || [];
  }

  _alleAnlagen() {
    return this._anlageIndex < 0 && this._anlagen().length > 1;
  }

  _aktuelleAnlage() {
    const anlagen = this._anlagen();
    if (this._anlageIndex < 0) return anlagen[0];
    return anlagen[Math.min(this._anlageIndex, anlagen.length - 1)];
  }

  _aufbauen() {
    this._bindungen = [];
    this._verlaufskarten = [];
    this._wartend = [];
    const anlage = this._aktuelleAnlage();
    const stil = document.createElement("style");
    stil.textContent = STIL;
    if (!anlage) {
      this.shadowRoot.replaceChildren(stil);
      return;
    }

    const inhalt = document.createElement("div");
    inhalt.append(this._kopfleiste(anlage), this._reiterleiste());
    if (this._anordnen) inhalt.appendChild(this._anordnenLeiste());
    if (this._alleAnlagen()) {
      this._anlagen().forEach((eintrag) => {
        const ueberschrift = document.createElement("div");
        ueberschrift.className = "anlagen-trenner";
        ueberschrift.textContent = eintrag.name || "Anlage";
        inhalt.append(ueberschrift, this._inhalt(eintrag));
      });
    } else {
      inhalt.appendChild(this._inhalt(anlage));
    }
    this.shadowRoot.replaceChildren(stil, inhalt);
    this._verlaufKarteLaden();
  }

  /** Kopfleiste mit Menütaste, Marke und Anlagenwahl. */
  _kopfleiste(anlage) {
    const leiste = document.createElement("div");
    leiste.className = "kopfleiste";

    // Auf schmalen Bildschirmen verdeckt das Panel die Seitenleiste; über
    // diese Taste kommt sie zurück. Das Ereignis ist dasselbe, das die
    // eigenen Ansichten von Home Assistant benutzen – es muss den
    // Schattenbaum verlassen, daher `composed`.
    const menue = document.createElement("button");
    menue.className = "menue-taste";
    menue.type = "button";
    menue.title = "Seitenleiste anzeigen (Karten, Energie, Einstellungen)";
    menue.setAttribute("aria-label", "Seitenleiste anzeigen");
    // Das eigene Symbol statt eines Hamburgers: Es ist zugleich der Weg
    // zurueck in die uebrigen Ansichten von Home Assistant - auf dem Handy
    // sonst nur ueber eine Wischgeste erreichbar.
    menue.appendChild(this._symbolKnoten("mdi:radiator"));
    menue.addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    });
    leiste.appendChild(menue);

    const marke = document.createElement("div");
    marke.className = "marke";
    marke.textContent = "HeatNexus";
    leiste.appendChild(marke);

    const abstand = document.createElement("div");
    abstand.className = "abstand";
    leiste.appendChild(abstand);

    // Die Außentemperatur gilt für die ganze Anlage – an der Anlage selbst
    // steht sie deshalb in der Kopfzeile und nicht bei einem Anlagenteil.
    //
    // Unter „Alle" gibt es keine einzelne Anlage, deren Fühler gälte; dort
    // zählt die in den Optionen gewählte Entität. Steht keine da, nimmt die
    // Kopfzeile den Wert der ersten Anlage.
    if (this._alleAnlagen() && this._daten && this._daten.aussentemperatur) {
      anlage = { ...anlage, aussentemperatur: this._daten.aussentemperatur };
    }
    if (anlage.aussentemperatur) {
      const aussen = document.createElement("div");
      aussen.className = "aussen";
      aussen.appendChild(this._symbolKnoten("mdi:thermometer"));
      const wert = document.createElement("span");
      aussen.appendChild(wert);
      leiste.appendChild(this._klickbar(aussen, anlage.aussentemperatur));
      this._bindungen.push(() => {
        wert.textContent = this._text(anlage.aussentemperatur);
      });
    }

    const anlagen = this._anlagen();
    if (anlagen.length > 1) {
      const waehler = document.createElement("div");
      waehler.className = "waehler";
      waehler.setAttribute("role", "tablist");
      // "Alle" stellt die Anlagen untereinander - mit Ueberschrift je Anlage,
      // damit man beim Scrollen sieht, wo die naechste anfaengt.
      const eintraege = [{ name: "Alle", index: -1 }].concat(
        anlagen.map((a, index) => ({ name: a.name || `Anlage ${index + 1}`, index }))
      );
      eintraege.forEach(({ name, index }) => {
        const taste = document.createElement("button");
        taste.type = "button";
        taste.setAttribute("role", "tab");
        taste.setAttribute("aria-selected", String(index === this._anlageIndex));
        taste.textContent = name;
        taste.addEventListener("click", () => {
          this._anlageIndex = index;
          this._gebaut = false;
          this._zeichnen();
        });
        waehler.appendChild(taste);
      });
      leiste.appendChild(waehler);
    }

    // Anordnen steht ganz außen: Es gehört nicht zum Ablesen, sondern zum
    // Einrichten. Zwischen Außentemperatur und Anlagenwahl stand es mitten in
    // den Angaben, die man ständig liest.
    const anordnen = document.createElement("button");
    anordnen.className = "menue-taste";
    anordnen.type = "button";
    anordnen.title = this._anordnen ? "Anordnen beenden" : "Karten anordnen";
    anordnen.setAttribute("aria-label", anordnen.title);
    anordnen.setAttribute("aria-pressed", String(this._anordnen));
    anordnen.appendChild(
      this._symbolKnoten(this._anordnen ? "mdi:check" : "mdi:view-dashboard-edit-outline")
    );
    anordnen.addEventListener("click", () => this._anordnenUmschalten());
    leiste.appendChild(anordnen);

    return leiste;
  }

  _reiterleiste() {
    const leiste = document.createElement("div");
    leiste.className = "reiter";
    leiste.setAttribute("role", "tablist");
    REITER.forEach((reiter) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.setAttribute("role", "tab");
      taste.setAttribute("aria-selected", String(reiter.schluessel === this._reiter));
      taste.appendChild(this._symbolKnoten(reiter.symbol));
      const beschriftung = document.createElement("span");
      beschriftung.textContent = reiter.titel;
      taste.appendChild(beschriftung);
      taste.addEventListener("click", () => {
        this._reiter = reiter.schluessel;
        this._gebaut = false;
        this._zeichnen();
      });
      leiste.appendChild(taste);
    });
    return leiste;
  }

  _inhalt(anlage) {
    // Die Karten holen ihre Erklärung über den Titel.
    this._hilfe = anlage.hilfe || {};
    if (this._reiter === "steuerung") {
      return this._raster(anlage, this._steuerung(anlage), "Keine bedienbaren Werte gefunden.");
    }
    if (this._reiter === "wartung") {
      return this._raster(anlage, this._wartung(anlage), "Keine Wartungswerte gefunden.");
    }
    if (this._reiter === "verlauf") {
      return this._raster(
        anlage,
        this._verlaufReiter(anlage),
        "Keine Werte für einen Verlauf gefunden."
      );
    }
    return this._raster(anlage, this._uebersicht(anlage), "Keine Werte gefunden.");
  }

  // -------------------------------------------------------------------
  // Reiter „Übersicht"
  // -------------------------------------------------------------------
  /**
   * Die Karten der Übersicht in ihrer Standardreihenfolge.
   *
   * Zurück kommen **Beschreibungen**, keine fertige Aufteilung: Kennung,
   * Titel, Knoten und die Standardbreite in Spalten. Erst `_raster` bringt
   * sie in die Reihenfolge, die der Nutzer gewählt hat. Die Kennungen sind
   * fest verdrahtet und nicht durchnummeriert – nur so findet eine gespeicherte
   * Anordnung ihre Karten wieder, wenn ein Anlagenteil dazukommt.
   */
  _uebersicht(anlage) {
    const wasser = this._warmwasserkarte(anlage);
    return [
      { id: "seite", titel: "Heizungsübersicht", knoten: this._seite(anlage) },
      { id: "schaubild", titel: "Anlagenübersicht", knoten: this._schaubild(anlage), breite: 2 },
      { id: "status", titel: "Systemstatus", knoten: this._statuskarte(anlage) },
      { id: "heizkreise", titel: "Heizkreise", knoten: this._heizkreiskarte(anlage) },
      {
        id: "schnellzugriff",
        titel: "Schnellzugriff",
        knoten: this._schnellzugriff(anlage),
        // Ohne Warmwasserkreis bleibt in der Zeile ein Platz frei; den nimmt
        // der Schnellzugriff ein, statt ein Loch stehen zu lassen.
        breite: wasser ? 1 : 2,
      },
      { id: "warmwasser", titel: "Warmwasser", knoten: wasser },
      { id: "stoerungen", titel: "Störungen", knoten: this._stoerungskarte(anlage) },
      {
        id: "verlauf24",
        titel: "Verlauf (24 Stunden)",
        knoten: this._klappbar(this._verlauf(anlage, 24)),
        breite: 2,
      },
    ];
  }

  // -------------------------------------------------------------------
  // Anordnung: Reihenfolge, Breite, Spaltenzahl, Verstecktes
  // -------------------------------------------------------------------
  /** Die gespeicherte Anordnung des aktuellen Reiters. */
  _reiterAnordnung() {
    return (this._anordnung && this._anordnung[this._reiter]) || {};
  }

  /**
   * Aus Kartenbeschreibungen das Raster bauen.
   *
   * Karten ohne Knoten gibt es an dieser Anlage nicht; sie fallen weg, bevor
   * die Reihenfolge gebildet wird. Damit verschiebt eine Anlage ohne
   * Warmwasser nichts, und die gespeicherte Reihenfolge bleibt für beide
   * Anlagen dieselbe.
   */
  _raster(anlage, karten, leerText) {
    const raster = document.createElement("div");
    raster.className = "raster";

    // Die Kennung trägt die Anlage vorneweg. Ohne sie teilten sich Heizhaus
    // und Wohnhaus dieselbe „schnellzugriff"-Karte: Wer im Heizhaus schob,
    // schob im Wohnhaus mit.
    const vorwahl = `${(anlage && anlage.id) || anlage.name || ""}|`;
    const vorhanden = (karten || [])
      .filter((karte) => karte && karte.knoten)
      .map((karte) => ({ ...karte, id: vorwahl + karte.id }));
    const anordnung = this._reiterAnordnung();
    const spalten = Number(anordnung.spalten) || 0;
    if (spalten > 0) {
      raster.style.setProperty("--raster-spalten", `repeat(${spalten}, minmax(0, 1fr))`);
    }
    const versteckt = new Set(anordnung.versteckt || []);
    const breiten = anordnung.breite || {};

    const reihenfolge = ordnungAnwenden(
      vorhanden.map((karte) => karte.id),
      anordnung.ordnung || []
    );
    const jeKennung = new Map(vorhanden.map((karte) => [karte.id, karte]));

    reihenfolge.forEach((kennung) => {
      const karte = jeKennung.get(kennung);
      if (!karte) return;
      const istVersteckt = versteckt.has(kennung);
      if (istVersteckt && !this._anordnen) return;
      const breite = Math.max(1, Math.min(BREITE_MAX, breiten[kennung] || karte.breite || 1));
      const knoten = this._anordnen
        ? this._anordner(karte, breite, istVersteckt, reihenfolge)
        : karte.knoten;
      knoten.style.setProperty("--breite", String(breite));
      raster.appendChild(knoten);
    });

    if (!raster.childElementCount) {
      const leer = this._karte("HeatNexus");
      leer.appendChild(this._hinweisKnoten(leerText));
      raster.appendChild(leer);
    }
    return raster;
  }

  /**
   * Eine Karte im Anordnen-Modus: Griffleiste oben, Karte darunter.
   *
   * Gezogen wird mit der Maus, verschoben auch mit den Pfeiltasten – am
   * Tablet vor dem Kessel ist Ziehen unzuverlässig, und ohne Tasten käme man
   * mit der Tastatur gar nicht weiter.
   */
  _anordner(karte, breite, istVersteckt, reihenfolge) {
    const huelle = document.createElement("div");
    huelle.className = istVersteckt ? "anordner versteckt" : "anordner";
    huelle.dataset.kennung = karte.id;

    const griff = document.createElement("div");
    griff.className = "anordner-griff";
    griff.appendChild(this._symbolKnoten("mdi:drag"));

    const name = document.createElement("div");
    name.className = "name";
    name.textContent = karte.titel || karte.id;
    griff.appendChild(name);

    const platz = reihenfolge.indexOf(karte.id);
    griff.appendChild(
      this._griffTaste("mdi:chevron-left", "Nach vorn", platz <= 0, () =>
        this._verschieben(karte.id, -1)
      )
    );
    griff.appendChild(
      this._griffTaste(
        "mdi:chevron-right",
        "Nach hinten",
        platz < 0 || platz >= reihenfolge.length - 1,
        () => this._verschieben(karte.id, 1)
      )
    );

    // Breite: schmaler, Anzeige, breiter. Vorher lief eine einzige Taste im
    // Kreis – wer einmal zu weit klickte, musste bis 4× durch und wieder von
    // vorn.
    const grenze = Math.min(Number(this._reiterAnordnung().spalten) || BREITE_MAX, BREITE_MAX);
    griff.appendChild(
      this._griffTaste("mdi:minus", "Schmaler", breite <= 1, () =>
        this._breiteAendern(karte.id, breite - 1)
      )
    );
    const breitenwert = document.createElement("div");
    breitenwert.className = "breite";
    breitenwert.textContent = `${breite}×`;
    breitenwert.title = "Breite in Spalten";
    griff.appendChild(breitenwert);
    griff.appendChild(
      this._griffTaste("mdi:plus", "Breiter", breite >= grenze, () =>
        this._breiteAendern(karte.id, breite + 1)
      )
    );

    griff.appendChild(
      this._griffTaste(
        istVersteckt ? "mdi:eye-off-outline" : "mdi:eye-outline",
        istVersteckt ? "Wieder einblenden" : "Ausblenden",
        false,
        () => this._sichtbarkeitUmschalten(karte.id)
      )
    );

    huelle.append(griff, karte.knoten);
    this._ziehenVerdrahten(huelle, griff, karte.id);
    return huelle;
  }

  _griffTaste(symbol, beschriftung, gesperrt, beiKlick) {
    const taste = document.createElement("button");
    taste.type = "button";
    taste.title = beschriftung;
    taste.setAttribute("aria-label", beschriftung);
    taste.disabled = !!gesperrt;
    taste.appendChild(this._symbolKnoten(symbol));
    taste.addEventListener("click", beiKlick);
    return taste;
  }

  /** Ziehen und Ablegen: der schnelle Weg für die Maus. */
  _ziehenVerdrahten(huelle, griff, kennung) {
    huelle.draggable = true;
    // Nur am Griff anfassen: Sonst startete jeder Klick in der Karte – etwa
    // auf ein Auswahlfeld – einen Ziehvorgang.
    huelle.addEventListener("dragstart", (ereignis) => {
      if (!griff.contains(ereignis.target) && ereignis.target !== huelle) {
        ereignis.preventDefault();
        return;
      }
      this._gezogen = kennung;
      huelle.classList.add("gezogen");
      ereignis.dataTransfer.effectAllowed = "move";
      // Firefox startet ohne gesetzte Nutzlast gar nicht erst.
      ereignis.dataTransfer.setData("text/plain", kennung);
    });
    huelle.addEventListener("dragend", () => {
      this._gezogen = null;
      huelle.classList.remove("gezogen");
    });
    huelle.addEventListener("dragover", (ereignis) => {
      if (!this._gezogen || this._gezogen === kennung) return;
      ereignis.preventDefault();
      ereignis.dataTransfer.dropEffect = "move";
      const feld = huelle.getBoundingClientRect();
      const davor = ereignis.clientX < feld.left + feld.width / 2;
      huelle.classList.toggle("ziel-vor", davor);
      huelle.classList.toggle("ziel-nach", !davor);
    });
    huelle.addEventListener("dragleave", () => {
      huelle.classList.remove("ziel-vor", "ziel-nach");
    });
    huelle.addEventListener("drop", (ereignis) => {
      ereignis.preventDefault();
      const davor = huelle.classList.contains("ziel-vor");
      huelle.classList.remove("ziel-vor", "ziel-nach");
      const gezogen = this._gezogen;
      this._gezogen = null;
      if (gezogen && gezogen !== kennung) this._ablegen(gezogen, kennung, davor);
    });
  }

  /** Eine Karte vor oder hinter eine andere setzen. */
  _ablegen(kennung, ziel, davor) {
    this._ordnungAendern((reihenfolge) => {
      const ohne = reihenfolge.filter((eintrag) => eintrag !== kennung);
      const stelle = ohne.indexOf(ziel);
      if (stelle < 0) return reihenfolge;
      ohne.splice(davor ? stelle : stelle + 1, 0, kennung);
      return ohne;
    });
  }

  /** Eine Karte um einen Platz verschieben. */
  _verschieben(kennung, richtung) {
    this._ordnungAendern((reihenfolge) => {
      const stelle = reihenfolge.indexOf(kennung);
      const ziel = stelle + richtung;
      if (stelle < 0 || ziel < 0 || ziel >= reihenfolge.length) return reihenfolge;
      const neu = [...reihenfolge];
      neu.splice(ziel, 0, neu.splice(stelle, 1)[0]);
      return neu;
    });
  }

  /**
   * Die Reihenfolge ändern.
   *
   * Die sichtbaren Karten bestimmen die neue Reihenfolge, aber sie sind nicht
   * alles: Unter „Alle" zeigt der Reiter nur die Karten *einer* Anlage, und
   * die Kennungen der anderen dürfen dabei nicht aus dem Speicher fallen. Was
   * gerade nicht auf dem Bildschirm steht, wird deshalb wieder eingefügt –
   * dort, wo es vorher stand.
   */
  _ordnungAendern(aenderung) {
    const anordnung = this._reiterAnordnung();
    const sichtbar = this._sichtbareKennungen();
    const alt = anordnung.ordnung || [];
    const neu = aenderung(ordnungAnwenden(sichtbar, alt));
    this._anordnungSetzen({ ...anordnung, ordnung: reihenfolgeMischen(neu, alt) });
  }

  /**
   * Die Kennungen der Karten, die dieser Reiter gerade zeigt.
   *
   * Unter „Alle" steht jede Kartenart einmal je Anlage auf dem Bildschirm –
   * „Kessel" also zweimal. Die Reihenfolge gilt aber für alle Anlagen
   * gemeinsam, deshalb zählt jede Kennung nur einmal.
   */
  _sichtbareKennungen() {
    const kennungen = [];
    this.shadowRoot.querySelectorAll(".anordner[data-kennung]").forEach((knoten) => {
      if (!kennungen.includes(knoten.dataset.kennung)) kennungen.push(knoten.dataset.kennung);
    });
    return kennungen;
  }

  _breiteAendern(kennung, breite) {
    const anordnung = this._reiterAnordnung();
    const grenze = Math.min(Number(anordnung.spalten) || BREITE_MAX, BREITE_MAX);
    const neu = Math.max(1, Math.min(grenze, breite));
    this._anordnungSetzen({
      ...anordnung,
      breite: { ...(anordnung.breite || {}), [kennung]: neu },
    });
  }

  _sichtbarkeitUmschalten(kennung) {
    const anordnung = this._reiterAnordnung();
    const versteckt = new Set(anordnung.versteckt || []);
    if (versteckt.has(kennung)) versteckt.delete(kennung);
    else versteckt.add(kennung);
    this._anordnungSetzen({ ...anordnung, versteckt: [...versteckt] });
  }

  _spaltenSetzen(spalten) {
    this._anordnungSetzen({ ...this._reiterAnordnung(), spalten });
  }

  /** Eine geänderte Anordnung übernehmen, anzeigen und sichern. */
  _anordnungSetzen(anordnung) {
    const reiter = this._reiter;
    this._anordnung = { ...this._anordnung, [reiter]: anordnung };
    this._gebaut = false;
    this._zeichnen();
    this._anordnungSichern(reiter, anordnung);
  }

  /**
   * Die Anordnung speichern – gesammelt, nicht bei jedem Klick.
   *
   * Beim Ziehen entstehen mehrere Änderungen kurz hintereinander; jede
   * einzeln zu schreiben hieße, die Platte für dieselbe Liste mehrfach
   * anzufassen.
   */
  _anordnungSichern(reiter, anordnung) {
    if (this._speicherAuftrag) clearTimeout(this._speicherAuftrag);
    this._speicherAuftrag = setTimeout(async () => {
      this._speicherAuftrag = null;
      try {
        await this._hass.callWS({
          type: "heatnexus/anordnung/setzen",
          reiter,
          anordnung,
        });
      } catch (err) {
        console.warn("HeatNexus: Anordnung konnte nicht gespeichert werden", err);
      }
    }, SPEICHERN_MS);
  }

  _anordnenUmschalten() {
    this._anordnen = !this._anordnen;
    this._gebaut = false;
    this._zeichnen();
  }

  /** Die Leiste, die im Anordnen-Modus über dem Raster steht. */
  _anordnenLeiste() {
    const leiste = document.createElement("div");
    leiste.className = "anordnen-leiste";

    const titel = document.createElement("div");
    titel.className = "titel";
    titel.textContent = "Anordnen";
    leiste.appendChild(titel);

    const hinweis = document.createElement("div");
    hinweis.className = "hinweis";
    hinweis.textContent =
      "Karten am Griff ziehen oder mit den Pfeilen verschieben. Die Anordnung gilt " +
      "nur für dich und nur für diesen Reiter.";
    leiste.appendChild(hinweis);

    const wahl = document.createElement("div");
    wahl.className = "spaltenwahl";
    wahl.setAttribute("role", "group");
    wahl.setAttribute("aria-label", "Spaltenzahl");
    const jetzt = Number(this._reiterAnordnung().spalten) || 0;
    [
      { wert: 0, name: "Auto" },
      { wert: 1, name: "1" },
      { wert: 2, name: "2" },
      { wert: 3, name: "3" },
      { wert: 4, name: "4" },
    ].forEach(({ wert, name }) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.textContent = name;
      taste.title = wert === 0 ? "So viele Spalten, wie nebeneinander passen" : `${name} Spalten`;
      taste.setAttribute("aria-pressed", String(wert === jetzt));
      taste.addEventListener("click", () => this._spaltenSetzen(wert));
      wahl.appendChild(taste);
    });
    leiste.appendChild(wahl);

    const fertig = document.createElement("button");
    fertig.type = "button";
    fertig.className = "anordnen-taste fertig";
    fertig.appendChild(this._symbolKnoten("mdi:check"));
    const fertigText = document.createElement("span");
    fertigText.textContent = "Fertig";
    fertig.appendChild(fertigText);
    fertig.addEventListener("click", () => this._anordnenUmschalten());
    leiste.appendChild(fertig);

    // Das Zurücksetzen steckt hinter dem Menü und hinter einer Rückfrage.
    // Als Taste in der Leiste läge es neben „Fertig" – und ein Fehlgriff
    // dort wirft eine ganze Anordnung weg, die niemand wiederherstellen kann.
    const mehr = document.createElement("button");
    mehr.type = "button";
    mehr.className = "anordnen-taste";
    mehr.title = "Weitere Möglichkeiten";
    mehr.setAttribute("aria-label", "Weitere Möglichkeiten");
    mehr.appendChild(this._symbolKnoten("mdi:dots-vertical"));
    mehr.addEventListener("click", () => this._anordnenMenue());
    leiste.appendChild(mehr);

    return leiste;
  }

  /** Das Menü hinter „⋮": nur das Zurücksetzen, jeweils mit Rückfrage. */
  _anordnenMenue() {
    const reiterName = (REITER.find((r) => r.schluessel === this._reiter) || {}).titel || "Reiter";
    this._menueDialog("Anordnung zurücksetzen", [
      {
        titel: `Nur „${reiterName}" zurücksetzen`,
        symbol: "mdi:restore",
        frage: `Die eigene Anordnung des Reiters „${reiterName}" verwerfen und zur Standardanordnung zurückgehen?`,
        tun: () => this._zuruecksetzen(this._reiter),
      },
      {
        titel: "Alle Reiter zurücksetzen",
        symbol: "mdi:restore-alert",
        frage:
          "Die eigene Anordnung aller vier Reiter verwerfen? Reihenfolge, " +
          "Breiten, ausgeblendete Karten und Spaltenzahl gehen dabei verloren.",
        tun: () => this._zuruecksetzen(null),
      },
    ]);
  }

  async _zuruecksetzen(reiter) {
    if (this._speicherAuftrag) {
      clearTimeout(this._speicherAuftrag);
      this._speicherAuftrag = null;
    }
    if (reiter) {
      const rest = { ...this._anordnung };
      delete rest[reiter];
      this._anordnung = rest;
    } else {
      this._anordnung = {};
    }
    this._gebaut = false;
    this._zeichnen();
    try {
      await this._hass.callWS({
        type: "heatnexus/anordnung/zuruecksetzen",
        ...(reiter ? { reiter } : {}),
      });
    } catch (err) {
      console.warn("HeatNexus: Anordnung konnte nicht zurückgesetzt werden", err);
    }
  }

  /**
   * Ein kleines Menüfenster; jeder Eintrag stellt vor der Tat seine Rückfrage.
   *
   * Bewusst dieselben Klassen wie die übrigen Fenster – und bewusst nicht
   * `window.confirm`: Der blockiert den Browser und sieht in Home Assistant
   * wie ein Fremdkörper aus.
   */
  _menueDialog(titel, eintraege) {
    const schleier = document.createElement("div");
    schleier.className = "schleier";
    const dialog = document.createElement("div");
    dialog.className = "dialog";

    const ueberschrift = document.createElement("h3");
    ueberschrift.className = "dialog-titel";
    ueberschrift.textContent = titel;
    dialog.appendChild(ueberschrift);

    const weg = () => {
      schleier.remove();
      document.removeEventListener("keydown", beiTaste);
    };
    const beiTaste = (ereignis) => {
      if (ereignis.key === "Escape") weg();
    };

    eintraege.forEach((eintrag) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "anordnen-taste";
      taste.style.width = "100%";
      taste.style.marginTop = "10px";
      taste.appendChild(this._symbolKnoten(eintrag.symbol));
      const text = document.createElement("span");
      text.textContent = eintrag.titel;
      taste.appendChild(text);
      taste.addEventListener("click", async () => {
        // Zweiter Schritt: erst die Rückfrage, dann die Tat.
        if (!(await this._bestaetigen(eintrag.titel, eintrag.frage))) return;
        weg();
        eintrag.tun();
      });
      dialog.appendChild(taste);
    });

    const leiste = document.createElement("div");
    leiste.className = "dialog-leiste";
    const schliessen = document.createElement("button");
    schliessen.type = "button";
    schliessen.className = "dialog-taste";
    schliessen.textContent = "Schließen";
    schliessen.addEventListener("click", weg);
    leiste.appendChild(schliessen);
    dialog.appendChild(leiste);

    schleier.appendChild(dialog);
    schleier.addEventListener("click", (ereignis) => {
      if (ereignis.target === schleier) weg();
    });
    document.addEventListener("keydown", beiTaste);
    this.shadowRoot.appendChild(schleier);
  }

  /**
   * Eine Karte zuklappbar machen.
   *
   * Der Kartenkopf wird zur Zusammenfassung, der Rest verschwindet, bis man
   * daraufdrückt. Gebaut wird der Inhalt trotzdem – nur so stimmen die
   * Bindungen, wenn jemand aufklappt, ohne dass die Ansicht neu entsteht.
   */
  _klappbar(karte) {
    if (!karte) return null;
    const kopf = karte.querySelector(".kartenkopf");
    const details = document.createElement("details");
    details.className = "karte klappkarte";
    const zusammenfassung = document.createElement("summary");
    if (kopf) {
      while (kopf.firstChild) zusammenfassung.appendChild(kopf.firstChild);
      kopf.remove();
    }
    zusammenfassung.appendChild(this._symbolKnoten("mdi:chevron-down", "pfeil"));
    details.appendChild(zusammenfassung);
    while (karte.firstChild) details.appendChild(karte.firstChild);
    return details;
  }

  _karte(titel, hilfe) {
    const karte = document.createElement("div");
    karte.className = "karte";
    if (titel) {
      const kopf = document.createElement("div");
      kopf.className = "kartenkopf";
      const ueberschrift = document.createElement("h2");
      ueberschrift.textContent = titel;
      kopf.appendChild(ueberschrift);
      const text = hilfe || (this._hilfe && this._hilfe[titel]);
      if (text) kopf.appendChild(this._fragezeichen(titel, text));
      karte.appendChild(kopf);
    }
    return karte;
  }

  /**
   * Ein „?", das erklärt, was hier eigentlich passiert.
   *
   * Die Anlage bringt zu jeder Einstellung eine Erklärung mit – nur liegt die
   * Anleitung beim Heizen selten daneben. Der Text kommt aus der Integration;
   * abschalten lässt er sich in den Optionen.
   */
  _fragezeichen(titel, text) {
    const taste = document.createElement("button");
    taste.type = "button";
    taste.className = "fragezeichen";
    taste.textContent = "?";
    taste.title = "Erklärung";
    taste.setAttribute("aria-label", `Erklärung zu ${titel}`);
    taste.addEventListener("click", (ereignis) => {
      ereignis.stopPropagation();
      this._erklaeren(titel, text);
    });
    return taste;
  }

  /** Erklärung als Hinweisfenster – bewusst dieselbe Form wie die Rückfrage. */
  _erklaeren(titel, text) {
    const schleier = document.createElement("div");
    schleier.className = "schleier";
    const dialog = document.createElement("div");
    dialog.className = "dialog erklaerung";
    dialog.setAttribute("role", "dialog");

    const ueberschrift = document.createElement("h3");
    ueberschrift.className = "dialog-titel";
    ueberschrift.textContent = titel;
    const inhalt = document.createElement("div");
    inhalt.className = "dialog-text";
    inhalt.textContent = text;

    const leiste = document.createElement("div");
    leiste.className = "dialog-leiste";
    const schliessen = document.createElement("button");
    schliessen.type = "button";
    schliessen.className = "dialog-taste";
    schliessen.textContent = "Verstanden";
    leiste.appendChild(schliessen);

    dialog.append(ueberschrift, inhalt, leiste);
    schleier.appendChild(dialog);
    const weg = () => {
      schleier.remove();
      document.removeEventListener("keydown", beiTaste);
    };
    const beiTaste = (ereignis) => {
      if (ereignis.key === "Escape") weg();
    };
    schliessen.addEventListener("click", weg);
    schleier.addEventListener("click", (e) => {
      if (e.target === schleier) weg();
    });
    document.addEventListener("keydown", beiTaste);
    this.shadowRoot.appendChild(schleier);
    schliessen.focus();
  }

  _symbolKnoten(symbol, klasse) {
    const ikone = document.createElement("ha-icon");
    ikone.setAttribute("icon", symbol);
    if (klasse) ikone.className = klasse;
    return ikone;
  }

  _hinweisKnoten(text) {
    const hinweis = document.createElement("div");
    hinweis.className = "hinweis";
    hinweis.textContent = text;
    return hinweis;
  }

  // -------------------------------------------------------------------
  // Linke Spalte: Marke, Zustand, Kennwerte
  // -------------------------------------------------------------------
  _seite(anlage) {
    // Eine Überschrift wie jede andere Karte. Marke und Logo standen hier ein
    // zweites Mal, obwohl beide in der Kopfleiste darüber stehen; der Name der
    // Anlage steht unter „Alle" in der Trennzeile und sonst im gewählten
    // Reiter oben rechts.
    const karte = this._karte("Heizungsübersicht");

    const abzeichen = document.createElement("div");
    abzeichen.className = "abzeichen";
    abzeichen.appendChild(this._symbolKnoten("mdi:check-circle-outline"));
    const abzeichenText = document.createElement("span");
    abzeichen.appendChild(abzeichenText);
    karte.appendChild(abzeichen);
    this._bindungen.push(() => {
      const stoerung = this._stoerung(anlage);
      abzeichen.classList.toggle("stoerung", stoerung);
      abzeichenText.textContent = stoerung ? "Störung anliegend" : "Anlage in Ordnung";
      abzeichen.firstChild.setAttribute(
        "icon",
        stoerung ? "mdi:alert-circle-outline" : "mdi:check-circle-outline"
      );
    });

    const liste = document.createElement("div");
    liste.style.marginTop = "16px";
    (anlage.kennwerte || []).forEach((kennwert) => {
      liste.appendChild(
        this._wertzeile(kennwert.entity, kennwert.titel, kennwert.untertitel, kennwert.symbol)
      );
    });
    karte.appendChild(liste);
    return karte;
  }

  /**
   * Kennwertzeile wie im Muster: links Anlagenteil, rechts der große Wert und
   * darunter klein, worum es sich handelt („Kesseltemperatur").
   */
  _wertzeile(entity, titel, bezeichnung, symbol, nurUeberNull) {
    const zeile = document.createElement("div");
    zeile.className = "zeile";
    if (symbol) zeile.appendChild(this._symbolKnoten(symbol));
    const text = document.createElement("div");
    text.className = "text";
    const oben = document.createElement("div");
    oben.className = "titel";
    oben.textContent = titel;
    text.appendChild(oben);

    const rechts = document.createElement("div");
    rechts.className = "rechts";
    const wert = document.createElement("div");
    wert.className = "wert";
    const unten = document.createElement("div");
    unten.className = "bezeichnung";
    unten.textContent = bezeichnung || "";
    rechts.append(wert, unten);

    zeile.append(text, rechts);
    this._bindungen.push(() => {
      // `nurUeberNull` gilt für Werte, die nur etwas bedeuten, solange sie
      // über null stehen – die Wärmeanforderung des Pumpen-/Relaismoduls etwa.
      // Liegt keine an, verschwindet die Zeile ganz: Ein „–" sähe aus wie ein
      // fehlender Messwert, dabei ist schlicht nichts angefordert.
      if (nurUeberNull) {
        const zahl = this._zahl(entity);
        zeile.hidden = !(zahl !== null && zahl > 0);
        if (zeile.hidden) return;
      }
      wert.textContent = this._text(entity);
      unten.textContent = bezeichnung || "";
      // Lange Texte („Betriebsbereit") umbrechen statt zu schrumpfen.
      wert.classList.toggle("lang", wert.textContent.length > 8);
    });
    return this._klickbar(zeile, entity);
  }

  // -------------------------------------------------------------------
  // Schaubild
  // -------------------------------------------------------------------
  _schaubild(anlage) {
    if (!anlage.schema) return null;
    const karte = this._karte("Anlagenübersicht");
    const huelle = document.createElement("div");
    huelle.className = "schaubild";
    const bild = document.createElement("img");
    bild.src = anlage.schema;
    bild.alt = "Anlagenschaubild";
    huelle.appendChild(bild);

    // Strömung: zwei Bänder auf Vor- und Rücklauf. Sie laufen, solange
    // irgendeine Pumpe der Anlage fördert – steht alles, steht auch das Bild.
    const leitungen = anlage.schema_leitungen;
    if (leitungen) {
      ["vorlauf", "ruecklauf"].forEach((richtung) => {
        const band = document.createElement("div");
        band.className = `fluss ${richtung}`;
        band.style.left = leitungen.left;
        band.style.width = leitungen.width;
        band.style.top = leitungen[`${richtung}_top`];
        huelle.appendChild(band);
        this._bindungen.push(() => {
          band.classList.toggle("laeuft", this._foerdertEtwas(anlage));
        });
      });
    }

    // Glutbett im Kessel. Die Helligkeit folgt der Leistung: Bei 30 % glimmt
    // es, bei Volllast leuchtet es.
    (anlage.schema_brenner || []).forEach((eintrag) => {
      const glut = document.createElement("div");
      glut.className = "glut";
      glut.style.left = eintrag.left;
      glut.style.top = eintrag.top;
      glut.style.width = eintrag.breite;
      huelle.appendChild(this._klickbar(glut, eintrag.entity || eintrag.ersatz));
      this._bindungen.push(() => {
        // Die Leistung ist der beste Massstab. Meldet die Anlage keine, dient
        // die Brennkammertemperatur als Ersatz: unter 100 Grad glimmt nichts,
        // ab 500 laeuft der Kessel voll, darueber bleibt es bei voll - heisser
        // heisst nicht mehr Leistung.
        const leistung = eintrag.entity ? this._zahl(eintrag.entity) : null;
        let anteil = null;
        let text = "";
        if (leistung !== null) {
          anteil = Math.max(0, Math.min(100, leistung)) / 100;
          text = `${Math.round(leistung)} %`;
        } else if (eintrag.ersatz) {
          const grad = this._zahl(eintrag.ersatz);
          if (grad !== null) {
            const kalt = Number(eintrag.ersatz_min) || 100;
            const heiss = Number(eintrag.ersatz_max) || 500;
            anteil = Math.max(0, Math.min(1, (grad - kalt) / (heiss - kalt)));
            text = `${Math.round(grad)} °C`;
          }
        }
        const brennt = anteil !== null && anteil > 0;
        glut.classList.toggle("brennt", brennt);
        glut.style.opacity = brennt ? String(0.35 + anteil * 0.65) : "0";
        glut.title = `${eintrag.titel} – ${brennt ? text : "aus"}`;
      });
    });

    // Mischerstellung. Bewusst keine Dauerbewegung: Eine Mischerstellung ist
    // ein Zustand, kein Vorgang – ein sich drehendes Ventil läse sich wie eine
    // Pumpe, und die dreht sich daneben schon. Der Anzeiger schwenkt zwischen
    // Rücklauf (0 %) und Vorlauf (100 %), das Stück Leitung darüber färbt sich
    // nach der Beimischung. Bewegt wird nur der Übergang.
    (anlage.schema_mischer || []).forEach((eintrag) => {
      const stutzen = document.createElement("div");
      stutzen.className = "mischer-stutzen";
      stutzen.style.left = eintrag.left;
      stutzen.style.top = eintrag.stutzen_top;
      stutzen.style.height = eintrag.stutzen_hoehe;
      huelle.appendChild(stutzen);

      const marke = document.createElement("div");
      marke.className = "mischer";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      marke.style.width = eintrag.groesse;
      marke.style.height = eintrag.groesse;
      const zeiger = document.createElement("div");
      zeiger.className = "zeiger";
      marke.appendChild(zeiger);
      huelle.appendChild(this._klickbar(marke, eintrag.entity));

      this._bindungen.push(() => {
        const stellwert = this._zahl(eintrag.entity);
        const da = stellwert !== null;
        marke.hidden = !da;
        stutzen.hidden = !da;
        if (!da) return;
        const anteil = Math.max(0, Math.min(100, stellwert)) / 100;
        // −60° steht auf dem Rücklaufschenkel, +60° auf dem Vorlauf.
        zeiger.style.transform = `rotate(${-60 + anteil * 120}deg)`;
        stutzen.style.background = `color-mix(in oklab, #e2543a ${Math.round(
          anteil * 100
        )}%, #3a7fe2)`;
        marke.title = `${eintrag.titel} – Mischer ${Math.round(stellwert)} %`;
      });
    });

    // Die Lampen des Pumpen-/Relaismoduls. Liegt eine Wärmeanforderung an,
    // blinken die Klemmen grün und die Betriebslampe wechselt von Rot auf
    // Grün. Sie liegen als eigene Ebene über dem Bild – die Zeichnung im
    // <img> kennt keine Zustände.
    (anlage.schema_lampen || []).forEach((eintrag) => {
      const lampe = document.createElement("div");
      lampe.className = `lampe ${eintrag.art}`;
      lampe.style.left = eintrag.left;
      lampe.style.top = eintrag.top;
      // Nur die Breite setzen: „groesse" ist ein Anteil der Bild*breite*.
      // Auf die Höhe angewandt ergäbe derselbe Prozentsatz einen anderen
      // Bildpunktwert – die Lampe wurde oval. `aspect-ratio` hält sie rund.
      lampe.style.width = eintrag.groesse;
      huelle.appendChild(lampe);
      this._bindungen.push(() => {
        const soll = this._zahl(eintrag.entity);
        const an = soll !== null && soll > 0;
        lampe.classList.toggle("an", an);
        lampe.title = an
          ? `${eintrag.titel} – fordert ${Math.round(soll)} °C`
          : `${eintrag.titel} – keine Anforderung`;
      });
    });

    // Wärmeanforderung: Steht der Analog-Sollwert über null, fordert das
    // Modul gerade Wärme an – und mit welcher Temperatur.
    (anlage.schema_anforderung || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "speicher anforderung";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      huelle.appendChild(marke);
      this._bindungen.push(() => {
        const soll = this._zahl(eintrag.entity);
        const an = soll !== null && soll > 0;
        marke.classList.toggle("laedt", an);
        marke.textContent = an ? `fordert ${Math.round(soll)} °C` : "";
        marke.title = `${eintrag.titel} – ${an ? "Wärmeanforderung" : "keine Anforderung"}`;
      });
    });

    // Puffer: lädt, entlädt oder steht. Zwei Temperaturen allein sagen keine
    // Richtung – maßgeblich ist, welche Pumpe fördert.
    (anlage.schema_speicher || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "speicher";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      huelle.appendChild(marke);
      this._bindungen.push(() => {
        // Die Ladepumpe allein genügt nicht: Sie läuft auch, wenn der Kessel
        // gerade direkt in einen Heizkreis fährt. Wärme geht nur dann in den
        // Puffer, wenn der Kessel wärmer ist als dessen oberer Bereich.
        const pumpe = eintrag.laden ? this._foerdert(eintrag.laden) : false;
        const kessel = eintrag.kessel ? this._zahl(eintrag.kessel) : null;
        const oben = eintrag.oben ? this._zahl(eintrag.oben) : null;
        const waermer =
          kessel === null || oben === null
            ? true
            : kessel > oben + (Number(eintrag.hysterese) || 0);
        const laedt = pumpe && waermer;
        const zieht = (eintrag.entnahme || []).some((e) => this._foerdert(e));
        marke.classList.toggle("laedt", laedt);
        marke.classList.toggle("entlaedt", !laedt && zieht);
        marke.textContent = laedt ? "lädt" : zieht ? "entlädt" : "";
        marke.title = `${eintrag.titel} – ${marke.textContent || "keine Förderung"}`;
      });
    });

    (anlage.schema_werte || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "marke-wert";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      huelle.appendChild(this._klickbar(marke, eintrag.entity));
      this._bindungen.push(() => {
        // Ohne Wert keine Marke: Ein „–" mitten im Heizkörper sah aus wie ein
        // Symbol und nicht wie ein fehlender Messwert.
        const da = this._hatWert(eintrag.entity);
        marke.hidden = !da;
        marke.textContent = da ? this._text(eintrag.entity) : "";
      });
    });

    // Pumpen liegen als eigene Marken auf dem Bild: Ein Standbild kann sich
    // nicht drehen, und ohne Bewegung sieht man der Anlage nicht an, ob
    // gerade etwas fließt.
    // Die senkrechten Stichleitungen: Sie strömen nur, solange die Pumpe
    // dieses Anlagenteils fördert. Erst daran sieht man, wohin die Wärme
    // gerade geht – die waagrechten Leitungen allein zeigen nur, dass
    // überhaupt etwas läuft.
    (anlage.schema_pumpen || []).forEach((eintrag) => {
      ["vorlauf", "ruecklauf"].forEach((richtung) => {
        const hoehe = eintrag[`${richtung}_hoehe`];
        if (!hoehe) return;
        const band = document.createElement("div");
        band.className = `fluss senkrecht ${richtung}`;
        band.style.left = eintrag.left;
        band.style.top = eintrag[`${richtung}_top`];
        band.style.height = hoehe;
        huelle.appendChild(band);
        this._bindungen.push(() => {
          band.classList.toggle("laeuft", this._foerdert(eintrag.entity));
        });
      });
    });

    (anlage.schema_pumpen || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "pumpe";
      marke.title = `${eintrag.titel} – Pumpe`;
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      const ikone = this._symbolKnoten("mdi:fan");
      marke.appendChild(ikone);
      huelle.appendChild(this._klickbar(marke, eintrag.entity));
      this._bindungen.push(() => {
        // Manche Pumpen melden keinen Zustand, sondern ihre Drehzahl.
        const zahl = this._zahl(eintrag.entity);
        const laeuft = zahl !== null ? zahl > 0 : this._istAn(eintrag.entity);
        marke.classList.toggle("laeuft", laeuft);
        marke.title = `${eintrag.titel} – Pumpe ${laeuft ? "läuft" : "steht"}`;
      });
    });

    karte.appendChild(huelle);
    return karte;
  }

  // -------------------------------------------------------------------
  // Heizkreise und Warmwasser
  // -------------------------------------------------------------------
  /**
   * Die Heizkreise, unter der Anlagenübersicht in derselben Spalte.
   *
   * Dort wächst die Karte nach unten, wenn eine Anlage mehr als einen Kreis
   * hat, ohne das Schaubild zu verschieben.
   *
   * Was es nicht gibt, bekommt auch keine Karte – so hält es die Anlage
   * selbst: Was keinen Wert liefert, wird ausgeblendet.
   */
  _heizkreiskarte(anlage) {
    const kreise = anlage.heizkreise || [];
    if (!kreise.length) return null;
    const karte = this._karte("Heizkreise");
    kreise.forEach((kreis) => karte.appendChild(this._heizkreiszeile(kreis)));
    return karte;
  }

  /**
   * Warmwasser, unter dem Schaubild und genauso breit.
   *
   * Eine Anlage ohne Warmwasserbereitung bekommt gar keine Karte – eine leere
   * Karte behauptet, da fehle etwas.
   */
  _warmwasserkarte(anlage) {
    const wasser = anlage.warmwasser || [];
    if (!wasser.length) return null;
    const karte = this._karte("Warmwasser");
    wasser.forEach((eintrag) => {
      karte.appendChild(this._statuszeile(eintrag.entity, eintrag.titel));
    });
    return karte;
  }

  /**
   * Eine Heizkreiszeile nach dem Vorbild der Anlage.
   *
   * Links Symbol, Name und die Betriebsart farbig darunter; rechts der große
   * Ist-Wert mit dem Sollwert klein daneben, dahinter zwei Symbole: die
   * Betriebsart (Sonne, Mond, Standby …) und das Zeitprogramm.
   */
  _heizkreiszeile(kreis) {
    const zeile = document.createElement("div");
    zeile.className = "zeile kreis";
    zeile.appendChild(this._symbolKnoten("mdi:home-outline"));

    const text = document.createElement("div");
    text.className = "text";
    const oben = document.createElement("div");
    oben.className = "titel";
    oben.textContent = kreis.titel;
    const unten = document.createElement("div");
    unten.className = "betriebsart-klein";
    text.append(oben, unten);

    const rechts = document.createElement("div");
    rechts.className = "rechts";
    const wert = document.createElement("div");
    wert.className = "wert";
    const sollzeile = document.createElement("div");
    sollzeile.className = "bezeichnung";
    rechts.append(wert, sollzeile);

    const symbole = document.createElement("div");
    symbole.className = "kreis-symbole";
    const artSymbol = this._symbolKnoten("mdi:white-balance-sunny");
    const uhr = this._symbolKnoten("mdi:clock-outline");
    symbole.append(artSymbol, uhr);

    zeile.append(text, rechts, symbole);
    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      if (!zustand) {
        wert.textContent = "–";
        return;
      }
      const ist = zustand.attributes.current_temperature;
      const soll = zustand.attributes.temperature;
      wert.textContent = ist !== undefined && ist !== null ? `${ist} °C` : "–";
      sollzeile.textContent =
        soll !== undefined && soll !== null ? `${soll} °C` : "Raumtemperatur";

      const art = zustand.attributes.preset_mode ? this._presetName(zustand) : "";
      const rest = this._restzeit(zustand);
      unten.textContent = rest ? `${art} · ${rest}` : art;
      // Farbe wie im Muster: Heizen warm, Absenken kühl.
      const heizt = zustand.state === "heat" || zustand.attributes.hvac_action === "heating";
      unten.className = `betriebsart-klein ${heizt ? "heizt" : "abgesenkt"}`;
      artSymbol.setAttribute("icon", heizt ? "mdi:white-balance-sunny" : "mdi:weather-night");
      artSymbol.className = heizt ? "heizt" : "abgesenkt";
      uhr.style.display = kreis.programm ? "" : "none";
    });
    return this._klickbar(zeile, kreis.entity);
  }

  _presetName(zustand) {
    // Die Betriebsarten heißen am Gerät "0".."7"; die Klartexte liefert die
    // Übersetzung der Integration mit.
    if (this._hass.formatEntityAttributeValue) {
      return this._hass.formatEntityAttributeValue(zustand, "preset_mode");
    }
    return zustand.attributes.preset_mode;
  }

  /**
   * Text zur laufenden Sollwert-Vorgabe.
   *
   * Ein am Thermostat gesetzter Wert gilt befristet; die Anlage meldet die
   * Restzeit in Minuten (2/10). Ohne diese Anzeige sieht man dem Heizkreis
   * nicht an, dass gerade eine Vorgabe läuft.
   */
  _restzeit(zustand) {
    if (!zustand || zustand.attributes.override_aktiv !== true) return "";
    const minuten = Number(zustand.attributes.override_restzeit_min) || 0;
    if (minuten <= 0) return "";
    const ende = new Date(Date.now() + minuten * 60000);
    const uhrzeit = ende.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return minuten >= 60
      ? `noch bis ${uhrzeit}`
      : `noch ${minuten} min (bis ${uhrzeit})`;
  }

  // -------------------------------------------------------------------
  // Systemstatus und Störungen
  // -------------------------------------------------------------------
  _statuszeile(entity, titel, symbol) {
    const zeile = document.createElement("div");
    zeile.className = "status-zeile";
    if (symbol) zeile.appendChild(this._symbolKnoten(symbol));
    const links = document.createElement("div");
    links.className = "titel";
    links.textContent = titel;
    const wert = document.createElement("div");
    wert.className = "wert";
    zeile.append(links, wert);
    this._bindungen.push(() => {
      const text = this._text(entity);
      wert.textContent = text;
      wert.title = text;
      // Farbe nach Art des Wertes: kurze Zustände grün, Leistungen orange,
      // Zahlen blau – so wie im Muster. Ein langer Text bleibt neutral, sonst
      // leuchtet die halbe Karte.
      const zustand = this._zustand(entity);
      const einheit = zustand && zustand.attributes.unit_of_measurement;
      wert.className = "wert";
      if (einheit === "%" || einheit === "kW") wert.classList.add("warm");
      else if (!einheit && this._hatWert(entity) && text.length <= 20) {
        wert.classList.add("zustand");
      }
    });
    return this._klickbar(zeile, entity);
  }

  /**
   * Der Systemstatus – **ohne** die Störungskarte.
   *
   * Beide standen bis 1.2.0-beta.4 in einer gemeinsamen Hülle. In einer Spalte
   * wären sie damit ein einziger Block und könnten nicht getrennt aufrücken.
   *
   * Kein dritter Störungshinweis: Derselbe Zustand steht in der
   * Anlagenübersicht („Anlage in Ordnung") und in der Störungskarte.
   */
  _statuskarte(anlage) {
    const karte = this._karte("Systemstatus");
    (anlage.status || []).forEach((eintrag) => {
      karte.appendChild(this._statuszeile(eintrag.entity, eintrag.titel, eintrag.symbol));
    });
    if (!(anlage.status || []).length) {
      karte.appendChild(this._hinweisKnoten("Keine Statuswerte gefunden."));
    }
    return karte;
  }

  _stoerungskarte(anlage) {
    const karte = this._karte("Störungen");
    const eintraege = anlage.stoerungen || [];

    const mitte = document.createElement("div");
    mitte.className = "mitte";
    const symbol = this._symbolKnoten("mdi:shield-check-outline");
    const haupt = document.createElement("div");
    haupt.className = "haupt";
    const neben = document.createElement("div");
    neben.className = "neben";
    mitte.append(symbol, haupt, neben);
    karte.appendChild(mitte);

    eintraege.forEach((eintrag) => {
      const zeile = document.createElement("div");
      zeile.className = "status-zeile";
      const links = document.createElement("div");
      links.className = "titel";
      const wert = document.createElement("div");
      wert.className = "wert";
      zeile.append(links, wert);
      karte.appendChild(this._klickbar(zeile, eintrag.entity));
      this._bindungen.push(() => {
        links.textContent = this._name(eintrag.entity).replace(" Meldung Klartext", "");
        const zustand = this._zustand(eintrag.entity);
        const aktiv = zustand && zustand.attributes.stoerung_aktiv === true;
        wert.textContent = this._text(eintrag.entity);
        wert.className = `wert ${aktiv ? "schlecht" : "gut"}`;
        // Ohne Störung sagt der Kasten oben schon alles; die Zeilen sind dann
        // nur Wiederholung.
        zeile.style.display = aktiv ? "flex" : "none";
      });
    });

    this._bindungen.push(() => {
      const stoerung = this._stoerung(anlage);
      symbol.setAttribute("icon", stoerung ? "mdi:shield-alert-outline" : "mdi:shield-check-outline");
      symbol.className = stoerung ? "schlecht" : "gut";
      haupt.textContent = stoerung ? "Störung anliegend" : "Keine Störung";
      neben.textContent = stoerung
        ? "Die Anlage meldet mindestens eine aktive Störung."
        : "Alles läuft.";
      mitte.style.display = stoerung ? "none" : "block";
    });
    return karte;
  }

  // -------------------------------------------------------------------
  // Verlauf
  // -------------------------------------------------------------------
  /**
   * Verlaufskarte mit an- und abwählbaren Linien.
   *
   * Die Vorauswahl kommt aus der Integration; welche Linien der Nutzer
   * zusätzlich sehen will, entscheidet er hier. Die Auswahl überlebt einen
   * Reiterwechsel, weil sie am Element hängt und nicht an der Karte.
   */
  _verlauf(anlage, stunden) {
    if (!(anlage.verlauf || []).length) return null;
    const schluessel = `${anlage.name || ""}|${stunden}`;
    if (!this._linien) this._linien = {};
    if (!this._linien[schluessel]) this._linien[schluessel] = new Set(anlage.verlauf);
    const gewaehlt = this._linien[schluessel];

    const karte = this._karte(`Verlauf (${stunden} Stunden)`);

    const auswahl = document.createElement("div");
    auswahl.className = "linienwahl";
    const moeglich = anlage.verlauf_moeglich || anlage.verlauf.map((e) => ({ entity: e }));
    moeglich.forEach((eintrag) => {
      const kennung = eintrag.entity || eintrag;
      const marke = document.createElement("button");
      marke.type = "button";
      marke.className = "linie";
      marke.textContent = eintrag.titel || this._name(kennung);
      marke.setAttribute("aria-pressed", String(gewaehlt.has(kennung)));
      marke.addEventListener("click", () => {
        if (gewaehlt.has(kennung)) gewaehlt.delete(kennung);
        else gewaehlt.add(kennung);
        marke.setAttribute("aria-pressed", String(gewaehlt.has(kennung)));
        this._verlaufNeuLaden(platz, gewaehlt);
      });
      auswahl.appendChild(marke);
    });
    karte.appendChild(auswahl);

    const platz = document.createElement("div");
    platz.dataset.verlauf = "1";
    platz.dataset.stunden = String(stunden);
    platz.dataset.entities = JSON.stringify([...gewaehlt]);
    karte.appendChild(platz);
    return karte;
  }

  async _verlaufNeuLaden(platz, gewaehlt) {
    platz.dataset.entities = JSON.stringify([...gewaehlt]);
    if (!window.loadCardHelpers) return;
    const helfer = await window.loadCardHelpers();
    const karte = helfer.createCardElement({
      type: "history-graph",
      hours_to_show: Number(platz.dataset.stunden) || 24,
      entities: [...gewaehlt],
    });
    karte.hass = this._hass;
    platz.replaceChildren(karte);
    const alt = this._verlaufskarten.findIndex((k) => k.parentElement === platz);
    if (alt >= 0) this._verlaufskarten[alt] = karte;
    else this._verlaufskarten.push(karte);
  }

  _verlaufReiter(anlage) {
    return [
      {
        id: "verlauf48",
        titel: "Verlauf (48 Stunden)",
        knoten: this._verlauf(anlage, 48),
        // Ein Diagramm über die halbe Breite liest sich schlechter als eines
        // über zwei Spalten; schmaler machen kann man es im Anordnen-Modus.
        breite: 2,
      },
    ];
  }

  async _verlaufKarteLaden() {
    const plaetze = this.shadowRoot.querySelectorAll("[data-verlauf]");
    if (!plaetze.length || !window.loadCardHelpers) return;
    const helfer = await window.loadCardHelpers();
    this._verlaufskarten = [];
    plaetze.forEach((platz) => {
      const karte = helfer.createCardElement({
        type: "history-graph",
        hours_to_show: Number(platz.dataset.stunden) || 24,
        entities: JSON.parse(platz.dataset.entities),
      });
      karte.hass = this._hass;
      platz.replaceChildren(karte);
      this._verlaufskarten.push(karte);
    });
  }

  // -------------------------------------------------------------------
  // Reiter „Steuerung"
  // -------------------------------------------------------------------
  _steuerung(anlage) {
    const steuerung = anlage.steuerung || {};
    // Je Heizkreis eine Karte – die Kennung hängt an der Gerätekennung, nicht
    // an der Position: Kommt ein Kreis dazu, behalten die anderen ihren Platz.
    const karten = (steuerung.heizkreise || []).map((kreis) => ({
      id: `heizkreis:${kreis.id || kreis.entity}`,
      titel: kreis.titel,
      knoten: this._heizkreisKarte(kreis),
    }));
    karten.push(
      {
        id: "warmwasser",
        titel: "Warmwasser",
        knoten: steuerung.warmwasser ? this._warmwasserKarte(steuerung.warmwasser) : null,
      },
      {
        id: "kessel",
        titel: "Kessel",
        knoten: (steuerung.kessel || []).length ? this._kesselKarte(steuerung.kessel) : null,
      },
      {
        id: "lagerraum",
        titel: "Lagerraum befüllen",
        knoten: steuerung.lagerraum ? this._lagerraumKarte(steuerung.lagerraum) : null,
      }
    );
    return karten;
  }

  /**
   * Eine Taste für Eco bzw. Comfort.
   *
   * Geschrieben werden zwei Werte: die Temperatur (3/4) und die Dauer (2/10) –
   * dieselbe befristete Übersteuerung, die das Bediengerät setzt. Die Vorgaben
   * stehen in den Optionen der Integration und gelten für alle Kreise.
   */
  _uebersteuerungsTaste(kreis, schluessel, beschriftungText, symbol) {
    const werte = ((this._daten && this._daten.uebersteuerung) || {})[schluessel] || {};
    const taste = document.createElement("button");
    taste.className = "taste";
    taste.type = "button";
    taste.appendChild(this._symbolKnoten(symbol));
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = beschriftungText;
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    taste.append(beschriftung, rueckmeldung);

    taste.addEventListener("click", async () => {
      if (taste.disabled) return;
      const temperatur = Number(werte.temperatur);
      const dauer = Number(werte.dauer);
      if (!Number.isFinite(temperatur) || !Number.isFinite(dauer)) return;
      taste.disabled = true;
      try {
        await this._uebertragen(
          rueckmeldung,
          async () => {
            await this._hass.callService("number", "set_value", {
              entity_id: kreis.uebersteuerung_temperatur,
              value: temperatur,
            });
            return this._hass.callService("number", "set_value", {
              entity_id: kreis.uebersteuerung_dauer,
              value: dauer,
            });
          },
          () => {
            const jetzt = this._zustand(kreis.entity);
            return !!jetzt && Math.abs(Number(jetzt.attributes.temperature) - temperatur) < 0.3;
          }
        );
      } finally {
        taste.disabled = false;
      }
    });

    this._bindungen.push(() => {
      if (rueckmeldung.dataset.belegt === "1") return;
      const zustand = this._zustand(kreis.entity);
      const soll = zustand ? Number(zustand.attributes.temperature) : NaN;
      const aktiv =
        !!zustand &&
        zustand.attributes.override_aktiv === true &&
        Math.abs(soll - Number(werte.temperatur)) < 0.3;
      taste.classList.toggle("an", aktiv);
      rueckmeldung.className = "rueckmeldung";
      const grad = Number(werte.temperatur);
      rueckmeldung.textContent = Number.isFinite(grad)
        ? `${grad} °C · ${Math.round(Number(werte.dauer) || 0)} min`
        : "";
    });
    return taste;
  }

  /** Heizkreis mit Sollwertregler, Betriebswahl und Zeitprogramm. */
  _heizkreisKarte(kreis) {
    const karte = this._karte(kreis.titel);

    // Die Anlage stellt in ihrer Detailansicht die Betriebsart als Klartext
    // ueber den Wert - dort sucht man sie.
    const betriebsart = document.createElement("div");
    betriebsart.className = "betriebsart";
    karte.appendChild(betriebsart);
    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      betriebsart.textContent =
        zustand && zustand.attributes.preset_mode ? this._presetName(zustand) : "";
    });

    const gross = document.createElement("div");
    gross.className = "gross";
    const zahl = document.createElement("div");
    zahl.className = "zahl";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = "Raumtemperatur";
    gross.append(zahl, beschriftung);
    karte.appendChild(this._klickbar(gross, kreis.entity));

    const laufzeit = document.createElement("div");
    laufzeit.className = "laufzeit";
    laufzeit.appendChild(this._symbolKnoten("mdi:timer-sand"));
    const laufzeitText = document.createElement("span");
    laufzeit.appendChild(laufzeitText);
    // Eine laufende Vorgabe muss sich beenden lassen, ohne dass man den
    // Sollwert zurückdreht. Die Dauer (2/10) auf null zu setzen ist derselbe
    // Weg, den die Anlage beim Wechsel der Betriebswahl selbst geht – danach
    // gilt wieder das Zeitprogramm.
    const abbruch = document.createElement("button");
    abbruch.type = "button";
    abbruch.className = "laufzeit-abbruch";
    abbruch.textContent = "abbrechen";
    abbruch.title = "Vorgabe beenden und zum Programm zurückkehren";
    if (kreis.uebersteuerung_dauer) laufzeit.appendChild(abbruch);
    karte.appendChild(laufzeit);

    // Sollwertregler
    const regler = document.createElement("div");
    regler.className = "regler";
    const runter = document.createElement("button");
    runter.type = "button";
    runter.textContent = "−";
    runter.setAttribute("aria-label", "Sollwert senken");
    const mitte = document.createElement("div");
    mitte.className = "sollwert";
    const sollZahl = document.createElement("div");
    sollZahl.className = "zahl";
    const sollText = document.createElement("div");
    sollText.className = "beschriftung";
    sollText.textContent = "Sollwert";
    mitte.append(sollZahl, sollText);
    const hoch = document.createElement("button");
    hoch.type = "button";
    hoch.textContent = "+";
    hoch.setAttribute("aria-label", "Sollwert anheben");
    regler.append(runter, mitte, hoch);
    karte.appendChild(regler);

    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    karte.appendChild(rueckmeldung);

    const stellen = async (richtung) => {
      const zustand = this._zustand(kreis.entity);
      if (!zustand) return;
      const schritt = Number(zustand.attributes.target_temp_step) || 0.5;
      const soll = Number(zustand.attributes.temperature);
      if (Number.isNaN(soll)) return;
      const neu = Math.round((soll + richtung * schritt) * 10) / 10;
      await this._uebertragen(
        rueckmeldung,
        () =>
          this._hass.callService("climate", "set_temperature", {
            entity_id: kreis.entity,
            temperature: neu,
          }),
        // Bestätigt ist die Vorgabe erst, wenn die Anlage sie zurückmeldet.
        () => {
          const jetzt = this._zustand(kreis.entity);
          return !!jetzt && Math.abs(Number(jetzt.attributes.temperature) - neu) < 0.3;
        }
      );
    };
    runter.addEventListener("click", () => stellen(-1));
    hoch.addEventListener("click", () => stellen(1));

    abbruch.addEventListener("click", async () => {
      if (abbruch.disabled || !kreis.uebersteuerung_dauer) return;
      abbruch.disabled = true;
      try {
        await this._uebertragen(
          rueckmeldung,
          () =>
            this._hass.callService("number", "set_value", {
              entity_id: kreis.uebersteuerung_dauer,
              value: 0,
            }),
          () => {
            const jetzt = this._zustand(kreis.entity);
            return !!jetzt && jetzt.attributes.override_aktiv !== true;
          }
        );
        this._nachfassen({
          entity: kreis.uebersteuerung_dauer,
          betriebswahl: kreis.betriebswahl,
        });
      } finally {
        abbruch.disabled = false;
      }
    });

    // Eco und Comfort: dieselbe befristete Übersteuerung, die auch das
    // Bediengerät schreibt. Die Anlage kennt je Kreis nur *einen*
    // Übersteuerungswert – ob er Eco oder Comfort heißt, entscheidet sie
    // daran, ob er unter oder über dem Programmsollwert liegt.
    if (kreis.uebersteuerung_temperatur && kreis.uebersteuerung_dauer) {
      const paar = document.createElement("div");
      paar.className = "gitter";
      paar.style.marginTop = "12px";
      [
        ["eco", "Eco", "mdi:leaf"],
        ["comfort", "Comfort", "mdi:sofa"],
      ].forEach(([schluessel, beschriftung, symbol]) => {
        paar.appendChild(this._uebersteuerungsTaste(kreis, schluessel, beschriftung, symbol));
      });
      karte.appendChild(paar);
    }

    if (kreis.betriebswahl) {
      karte.appendChild(
        this._auswahlFeld("Betriebswahl", kreis.betriebswahl, kreis.betriebswahl_hilfe)
      );
    }
    if (kreis.programm) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.append(trenner, this._statuszeile(kreis.programm, "Zeitprogramm"));
    }
    if (kreis.vorlauf) {
      karte.appendChild(this._statuszeile(kreis.vorlauf, "Vorlauf"));
    }

    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      const ist = zustand && zustand.attributes.current_temperature;
      zahl.textContent = ist !== undefined && ist !== null ? `${ist} °C` : "–";
      const soll = zustand && zustand.attributes.temperature;
      sollZahl.textContent = soll !== undefined && soll !== null ? `${soll} °C` : "–";
      const rest = this._restzeit(zustand);
      laufzeit.style.display = rest ? "inline-flex" : "none";
      laufzeitText.textContent = rest ? `Vorgabe ${rest}` : "";
      // Ohne laufende Vorgabe gibt es nichts zu beenden.
      laufzeit.hidden = !rest;
    });
    return karte;
  }

  /**
   * Warmwasser mit Ist, Soll und Einmalladung.
   *
   * Die Einmalladung läuft minutenlang. Die Taste bleibt deshalb markiert,
   * solange die Anlage sie als aktiv meldet, und springt von selbst zurück,
   * wenn die Ladung fertig ist – so wie in der Windhager-App.
   */
  _warmwasserKarte(wasser) {
    const karte = this._karte("Warmwasser");

    // Wie bei der Anlage: die Betriebsart im Klartext über dem Wert.
    if (wasser.betriebsart) {
      const betriebsart = document.createElement("div");
      betriebsart.className = "betriebsart";
      karte.appendChild(betriebsart);
      this._bindungen.push(() => {
        betriebsart.textContent = this._text(wasser.betriebsart);
      });
    }

    const gross = document.createElement("div");
    gross.className = "gross";
    const zahl = document.createElement("div");
    zahl.className = "zahl";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = "Isttemperatur";
    gross.append(zahl, beschriftung);
    karte.appendChild(wasser.ist ? this._klickbar(gross, wasser.ist) : gross);
    this._bindungen.push(() => {
      zahl.textContent = wasser.ist ? this._text(wasser.ist) : "–";
    });

    if (wasser.soll) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.append(trenner, this._statuszeile(wasser.soll, "Sollwert"));
    }
    if (wasser.programm) {
      karte.appendChild(this._statuszeile(wasser.programm, "Programm"));
    }

    if (wasser.laden) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.appendChild(trenner);
      // Die Anlage kennt zur Einmalladung beides: die Temperatur, auf die
      // geladen wird, und das Ausloesen.
      if (wasser.laden_temperatur) {
        karte.appendChild(this._statuszeile(wasser.laden_temperatur, "Ladetemperatur"));
      }
      karte.appendChild(this._ladeTaste(wasser));
    }
    return karte;
  }

  /**
   * Taste für die Warmwasser-Einmalladung.
   *
   * Der Auslöser selbst (`2/16`) fällt zurück, sobald die Anlage den Auftrag
   * angenommen hat – er taugt deshalb nicht als Anzeige. Ob wirklich geladen
   * wird, sagt die WW-Ladepumpe; im Zweifel wird gegengeprüft, ob die
   * Warmwassertemperatur noch unter dem Sollwert liegt.
   */
  _ladeTaste(wasser) {
    const entity = wasser.laden;
    const bereich = entity.split(".")[0];
    // Was die Anlage gerade tut, steht in der Betriebsart. Meldet sie keine,
    // bleibt die Ladepumpe als Anhaltspunkt.
    const laedt = () => {
      const zustand = this._zustand(wasser.betriebsart);
      if (zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase())) {
        return (wasser.laedt_wenn || []).includes(zustand.state);
      }
      if (wasser.laeuft) return this._istAn(wasser.laeuft);
      return this._istAn(entity);
    };
    const taste = document.createElement("button");
    taste.className = "taste";
    taste.type = "button";
    taste.appendChild(this._symbolKnoten("mdi:water-boiler"));
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = "Einmalladung";
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    taste.append(beschriftung, rueckmeldung);

    taste.addEventListener("click", async () => {
      if (taste.disabled) return;
      const lief = laedt();
      // Ein zweiter Druck während „wird ausgeführt …" ist ein Abbruchwunsch:
      // Die Anzeige wird freigegeben und der Grundzustand wiederhergestellt.
      delete rueckmeldung.dataset.belegt;
      taste.disabled = true;
      try {
        if (lief && wasser.betriebswahl) {
          // Abbrechen heißt an der Anlage: die dauerhafte Betriebswahl wieder
          // setzen. Der vorübergehende Zustand fällt damit weg – denselben Weg
          // geht die Anlagen-App über die Taste „Programm".
          const wahl = this._zustand(wasser.betriebswahl);
          if (!wahl) return;
          await this._uebertragen(
            rueckmeldung,
            () =>
              this._hass.callService("select", "select_option", {
                entity_id: wasser.betriebswahl,
                option: wahl.state,
              }),
            () => !laedt()
          );
          return;
        }
        await this._uebertragen(
          rueckmeldung,
          () =>
            bereich === "button"
              ? this._hass.callService("button", "press", { entity_id: entity })
              : this._hass.callService("homeassistant", "turn_on", { entity_id: entity }),
          // Bestätigt ist der Auftrag, wenn die Anlage anfängt zu laden.
          () => laedt()
        );
      } finally {
        taste.disabled = false;
      }
    });

    this._bindungen.push(() => {
      const laeuft = laedt();
      taste.classList.toggle("an", laeuft);
      beschriftung.textContent = laeuft ? "Ladung abbrechen" : "Einmalladung";
      if (rueckmeldung.dataset.belegt === "1") return;
      rueckmeldung.className = "rueckmeldung";
      rueckmeldung.textContent = laeuft ? "lädt gerade" : "bereit";
    });
    return taste;
  }

  _istAn(entity) {
    const zustand = this._zustand(entity);
    return !!zustand && zustand.state === "on";
  }

  _auswahlFeld(titel, entity, hilfe) {
    const feld = document.createElement("div");
    feld.className = "feld";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    const wort = document.createElement("span");
    wort.textContent = titel;
    beschriftung.appendChild(wort);
    // Gerade der Brennstoff braucht die Erklärung: Welche der vier
    // Einstellungen richtig ist, sieht man der Auswahlliste nicht an.
    const text = hilfe || (this._hilfe && this._hilfe[titel]);
    if (text) beschriftung.appendChild(this._fragezeichen(titel, text));
    const auswahl = document.createElement("select");
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    feld.append(beschriftung, auswahl, rueckmeldung);

    auswahl.addEventListener("change", async () => {
      const gewaehlt = auswahl.value;
      await this._uebertragen(
        rueckmeldung,
        () =>
          this._hass.callService("select", "select_option", {
            entity_id: entity,
            option: gewaehlt,
          }),
        () => {
          const zustand = this._zustand(entity);
          return !!zustand && zustand.state === gewaehlt;
        }
      );
    });

    this._bindungen.push(() => {
      const zustand = this._zustand(entity);
      const optionen = (zustand && zustand.attributes.options) || [];
      if (auswahl.dataset.optionen !== optionen.join("|")) {
        auswahl.dataset.optionen = optionen.join("|");
        auswahl.replaceChildren(
          ...optionen.map((option) => {
            const knoten = document.createElement("option");
            knoten.value = option;
            knoten.textContent = option;
            return knoten;
          })
        );
      }
      if (rueckmeldung.dataset.belegt === "1") return;
      // Die Rückmeldung gehört ausdrücklich zurückgesetzt. Ohne das blieb
      // „übernommen ✓" für immer stehen: `_freigeben` löscht nur die Sperre
      // und stößt die Bindungen an – den Text löscht niemand.
      rueckmeldung.textContent = "";
      rueckmeldung.className = "rueckmeldung";
      if (zustand) auswahl.value = zustand.state;
    });
    return feld;
  }

  /**
   * Lagerraumbefüllung, aufgebaut wie die Seite am Bediengerät.
   *
   * Erst anfordern, dann ablesen: Die Anlage gibt das Befüllen nur frei, wenn
   * ihr Zustand es zulässt – bei pneumatischer Zuführung etwa erst bei leerem
   * Vorratsbehälter. Erst wenn dort „freigegeben" steht, darf weiterbefüllt
   * werden; das ist keine Anzeigefrage, sondern steht so in der Anleitung des
   * Kessels (Beschädigung des Rührwerks).
   */
  _lagerraumKarte(lagerraum) {
    const karte = this._karte("Lagerraum befüllen");

    (lagerraum.zeilen || []).forEach((zeile) => {
      karte.appendChild(this._statuszeile(zeile.entity, zeile.titel));
    });

    const trenner = document.createElement("div");
    trenner.className = "trenner";
    karte.appendChild(trenner);
    karte.appendChild(
      this._bedientaste(
        {
          entity: lagerraum.anfordern,
          titel: "Befüllung anfordern",
          symbol: "mdi:warehouse",
          frage: lagerraum.frage,
        },
        true
      )
    );
    return karte;
  }

  /**
   * Kesselbedienung: Auswahlfelder oben, Tasten darunter im Raster.
   *
   * Untereinander gestapelt wuchs die Karte mit jeder Reinigungstaste weiter
   * in die Länge; nebeneinander bleibt sie überschaubar und sieht aus wie der
   * Schnellzugriff.
   */
  _kesselKarte(eintraege) {
    const karte = this._karte("Kessel");
    const gitter = document.createElement("div");
    gitter.className = "gitter";
    gitter.style.marginTop = "10px";

    eintraege.forEach((eintrag) => {
      const bereich = eintrag.entity.split(".")[0];
      if (bereich === "select") {
        karte.appendChild(this._auswahlFeld(eintrag.titel, eintrag.entity, eintrag.hilfe));
        return;
      }
      gitter.appendChild(this._bedientaste(eintrag, false));
    });

    if (gitter.childElementCount) karte.appendChild(gitter);
    return karte;
  }

  // -------------------------------------------------------------------
  // Reiter „Wartung"
  // -------------------------------------------------------------------
  _wartung(anlage) {
    const wartung = anlage.wartung || {};
    const abschnitte = [
      ["restlaufzeiten", "Restlaufzeiten", wartung.restlaufzeiten],
      ["brennstoff", "Brennstoff", wartung.brennstoff],
      ["zaehler", "Zählerstände", wartung.zaehler],
      ["weiteres", "Weiteres", wartung.weitere],
    ];
    return abschnitte.map(([id, titel, zeilen]) => {
      if (!zeilen || !zeilen.length) return { id, titel, knoten: null };
      const karte = this._karte(titel);
      zeilen.forEach((zeile) => {
        karte.appendChild(this._statuszeile(zeile.entity, zeile.titel));
      });
      return { id, titel, knoten: karte };
    });
  }

  // -------------------------------------------------------------------
  // Schnellzugriff
  // -------------------------------------------------------------------
  _schnellzugriff(anlage) {
    const eintraege = anlage.schnellzugriff || [];
    if (!eintraege.length) return null;
    const karte = this._karte("Schnellzugriff");
    const gitter = document.createElement("div");
    gitter.className = "gitter";

    eintraege.forEach((eintrag) => {
      if (eintrag.entity.split(".")[0] === "select") {
        const huelle = this._auswahlFeld(eintrag.titel, eintrag.entity, eintrag.hilfe);
        huelle.style.gridColumn = "1 / -1";
        gitter.appendChild(huelle);
        return;
      }
      gitter.appendChild(this._bedientaste(eintrag, false));
    });

    karte.appendChild(gitter);
    return karte;
  }

  /** Eine Kachel, die einen Befehl auslöst – mit Rückfrage und Rückmeldung. */
  _bedientaste(eintrag, breit) {
    const bereich = eintrag.entity.split(".")[0];
    // Manche Bedienungen melden ihren Zustand woanders: Die Warmwasserladung
    // steht in der Betriebsart, ihr Auslöser fällt sofort zurück.
    const laeuft = () => {
      // Die Ladepumpe ist der handfeste Beleg: Sie läuft, solange geladen
      // wird. Die Betriebsart meldet je nach Baureihe andere Worte und an
      // manchen Kreisen gar nichts.
      if (eintrag.zustand_pumpe && this._istAn(eintrag.zustand_pumpe)) return true;
      if (eintrag.zustand_an) {
        const zustand = this._zustand(eintrag.zustand_an);
        if (zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase())) {
          return (eintrag.zustand_wenn || []).includes(zustand.state);
        }
      }
      return this._istAn(eintrag.entity);
    };
    const taste = document.createElement("button");
    taste.className = "taste";
    taste.type = "button";
    if (breit) taste.style.marginTop = "10px";
    taste.appendChild(this._symbolKnoten(eintrag.symbol || "mdi:gesture-tap-button"));
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = eintrag.titel;
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    taste.append(beschriftung, rueckmeldung);
    if (eintrag.hilfe) {
      const hinweis = this._fragezeichen(eintrag.titel, eintrag.hilfe);
      hinweis.classList.add("auf-taste");
      taste.appendChild(hinweis);
    }

    taste.addEventListener("click", async () => {
      if (taste.disabled) return;
      const lief = laeuft();
      // Läuft die Ladung schon, bricht dieselbe Taste sie ab. Der Auslöser
      // selbst taugt dafür nicht: Er fällt zurück, sobald die Anlage den
      // Auftrag angenommen hat, und hat danach keinen Zustand mehr, den man
      // zurücknehmen könnte. Beendet wird über die Betriebswahl – genauso wie
      // an der Anlage selbst.
      if (lief && eintrag.betriebswahl && eintrag.betriebswahl_zurueck) {
        // Zurück auf das, was **vor** der Ladung eingestellt war. Nur wenn das
        // unbekannt ist – etwa nach einem Neuladen der Seite –, greift das
        // Zeitprogramm als Rückfall. Blind aufs Zeitprogramm zu stellen würde
        // sonst einen laufenden Heiz- oder Absenkbetrieb stillschweigend
        // beenden.
        const gemerkt = this._wahlVorLadung[eintrag.betriebswahl];
        const ziel =
          gemerkt || this._optionWie(eintrag.betriebswahl, eintrag.betriebswahl_zurueck);
        if (ziel) {
          taste.disabled = true;
          try {
            await this._uebertragen(
              rueckmeldung,
              () =>
                this._hass.callService("select", "select_option", {
                  entity_id: eintrag.betriebswahl,
                  option: ziel,
                }),
              () => !laeuft()
            );
            delete this._wahlVorLadung[eintrag.betriebswahl];
            this._nachfassen(eintrag);
          } finally {
            taste.disabled = false;
          }
        }
        return;
      }

      // Zu warm für eine Ladung: Die Anlage nimmt den Auftrag gar nicht an,
      // und die Taste stünde minutenlang auf „wird ausgeführt …". Lieber
      // gleich sagen, warum nichts passiert.
      if (eintrag.ist && eintrag.soll) {
        const ist = this._zahl(eintrag.ist);
        const soll = this._zahl(eintrag.soll);
        const abstand = Number(eintrag.abstand) || 0;
        if (ist !== null && soll !== null && ist > soll - abstand) {
          this._abgelehnt(
            taste,
            rueckmeldung,
            `schon ${Math.round(ist)} °C – erst ab ${Math.round(soll - abstand)} °C`
          );
          return;
        }
      }

      if (eintrag.frage && !(await this._bestaetigen(eintrag.titel, eintrag.frage))) return;
      taste.disabled = true;
      try {
        await this._uebertragen(
          rueckmeldung,
          async () => {
            // Auf Standby ist der Kreis abgeschaltet und nimmt den
            // Ladeauftrag nicht an. Nur dann wird vorher umgeschaltet – wer
            // im Heiz- oder Absenkbetrieb lädt, soll den nicht verlieren.
            if (eintrag.betriebswahl && eintrag.betriebswahl_aus && eintrag.betriebswahl_ww) {
              const jetzt = this._zustand(eintrag.betriebswahl);
              // Was jetzt eingestellt ist, gilt als Rückkehrpunkt.
              if (jetzt && !OHNE_WERT.includes(String(jetzt.state).toLowerCase())) {
                this._wahlVorLadung[eintrag.betriebswahl] = jetzt.state;
              }
              const aus = new RegExp(eintrag.betriebswahl_aus, "i");
              if (jetzt && aus.test(jetzt.state)) {
                const ww = this._optionWie(eintrag.betriebswahl, eintrag.betriebswahl_ww);
                if (ww) {
                  await this._hass.callService("select", "select_option", {
                    entity_id: eintrag.betriebswahl,
                    option: ww,
                  });
                }
              }
            }
            return bereich === "button"
              ? this._hass.callService("button", "press", { entity_id: eintrag.entity })
              : this._hass.callService(
                  "homeassistant",
                  eintrag.zustand_an ? "turn_on" : "toggle",
                  { entity_id: eintrag.entity }
                );
          },
          bereich === "button" ? null : () => laeuft() !== lief
        );
        this._nachfassen(eintrag);
      } finally {
        taste.disabled = false;
      }
    });

    this._bindungen.push(() => {
      const zustand = this._zustand(eintrag.entity);
      const an = laeuft();
      taste.classList.toggle("an", an);
      // Läuft die Ladung, sagt die Taste, was ein Druck jetzt bewirkt.
      const abbrechbar = an && !!eintrag.titel_abbrechen && !!eintrag.betriebswahl;
      beschriftung.textContent = abbrechbar ? eintrag.titel_abbrechen : eintrag.titel;
      taste.classList.toggle("abbrechen", abbrechbar);
      // Solange eine Übertragung läuft, gehört die Zeile der Rückmeldung.
      if (rueckmeldung.dataset.belegt === "1") return;
      rueckmeldung.className = "rueckmeldung";
      rueckmeldung.textContent = eintrag.zustand_an
        ? (an ? "läuft" : "bereit")
        : this._tastenZustand(bereich, zustand, an);
    });
    return taste;
  }

  /**
   * Ein Eingriff, den die Anlage gar nicht erst annimmt.
   *
   * Zweimal rot aufblitzen und kurz sagen, woran es liegt – danach steht
   * wieder der Zustand da. Ein Dialog wäre für „geht gerade nicht" zu viel,
   * ein stummes Nichts zu wenig.
   */
  _abgelehnt(taste, anzeige, grund) {
    anzeige.dataset.belegt = "1";
    anzeige.className = "rueckmeldung fehler";
    anzeige.textContent = grund;
    taste.classList.remove("blinkt");
    // Neustart der Animation erzwingen: Ohne das Auslesen läuft sie beim
    // zweiten Druck nicht noch einmal.
    void taste.offsetWidth;
    taste.classList.add("blinkt");
    window.setTimeout(() => taste.classList.remove("blinkt"), 1200);
    this._freigeben(anzeige, RUECKMELDUNG_MS);
  }

  /**
   * Die beteiligten Entitäten sofort neu abfragen.
   *
   * Die Anlage wird nur alle 30 s abgerufen. Nach einem Eingriff stünde die
   * Anzeige bis dahin auf dem alten Stand – gerade beim Abbrechen, wo die
   * Betriebswahl den Ausschlag gibt, wirkte die Taste dadurch wirkungslos.
   */
  _nachfassen(eintrag) {
    const entitaeten = [
      eintrag.betriebswahl,
      eintrag.zustand_an,
      eintrag.zustand_pumpe,
      eintrag.entity,
    ].filter(Boolean);
    if (!entitaeten.length) return;
    this._hass
      .callService("homeassistant", "update_entity", { entity_id: entitaeten })
      .catch((err) => console.warn("HeatNexus: Nachfassen fehlgeschlagen", err));
  }

  /**
   * Die erste Auswahlmöglichkeit einer Entität, die zu einem Muster passt.
   *
   * Welche Einträge eine Betriebswahl anbietet, meldet die Anlage selbst –
   * eine feste Liste im Quelltext ginge bei der nächsten Baureihe daneben.
   */
  _optionWie(entity, muster) {
    const zustand = this._zustand(entity);
    const optionen = (zustand && zustand.attributes.options) || [];
    const regex = new RegExp(muster, "i");
    return optionen.find((option) => regex.test(option)) || null;
  }

  // -------------------------------------------------------------------
  // Bedienen: nachfragen, übertragen, zurückmelden
  // -------------------------------------------------------------------

  /**
   * Rückfrage vor einem Eingriff, der die Anlage wirklich etwas kostet.
   *
   * Bewusst ein eigener Dialog statt `window.confirm`: Der blockiert den
   * Browser und sieht in Home Assistant wie ein Fremdkörper aus.
   */
  _bestaetigen(titel, frage) {
    return new Promise((antworten) => {
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog";
      dialog.setAttribute("role", "alertdialog");

      const ueberschrift = document.createElement("h3");
      ueberschrift.className = "dialog-titel";
      ueberschrift.textContent = titel;
      const text = document.createElement("div");
      text.className = "dialog-text";
      text.textContent = frage;

      const leiste = document.createElement("div");
      leiste.className = "dialog-leiste";
      const abbrechen = document.createElement("button");
      abbrechen.type = "button";
      abbrechen.className = "dialog-taste";
      abbrechen.textContent = "Abbrechen";
      const ausloesen = document.createElement("button");
      ausloesen.type = "button";
      ausloesen.className = "dialog-taste betont";
      ausloesen.textContent = "Ja, ausführen";
      leiste.append(abbrechen, ausloesen);

      dialog.append(ueberschrift, text, leiste);
      schleier.appendChild(dialog);

      const schliessen = (antwort) => {
        schleier.remove();
        document.removeEventListener("keydown", beiTaste);
        antworten(antwort);
      };
      const beiTaste = (ereignis) => {
        if (ereignis.key === "Escape") schliessen(false);
      };
      abbrechen.addEventListener("click", () => schliessen(false));
      ausloesen.addEventListener("click", () => schliessen(true));
      schleier.addEventListener("click", (ereignis) => {
        if (ereignis.target === schleier) schliessen(false);
      });
      document.addEventListener("keydown", beiTaste);

      this.shadowRoot.appendChild(schleier);
      ausloesen.focus();
    });
  }

  /**
   * Einen Dienstaufruf ausführen und den Verlauf sichtbar machen.
   *
   * Die Anlage wird nur alle 30 s abgefragt; ohne Rückmeldung drückt man und
   * nichts passiert. Deshalb drei Stufen: „wird übertragen" während des
   * Aufrufs, danach „wird ausgeführt …", solange die Anlage den neuen Zustand
   * noch nicht zurückmeldet, und erst dann „übernommen ✓".
   *
   * Ohne `bestaetigt` bleibt es bei den ersten beiden Stufen – bei einer
   * Taste ohne Zustand gibt es nichts, worauf man warten könnte.
   */
  async _uebertragen(anzeige, aufruf, bestaetigt) {
    // Ein neuer Auftrag löst den alten ab – sonst hinge die Anzeige an einer
    // Bestätigung, auf die niemand mehr wartet.
    this._wartend = this._wartend.filter((v) => v.anzeige !== anzeige);
    anzeige.dataset.belegt = "1";
    anzeige.className = "rueckmeldung laeuft";
    anzeige.textContent = "wird übertragen …";
    try {
      await aufruf();
    } catch (err) {
      anzeige.className = "rueckmeldung fehler";
      anzeige.textContent = "nicht übernommen";
      console.warn("HeatNexus: Befehl abgelehnt", err);
      this._freigeben(anzeige, RUECKMELDUNG_MS);
      return;
    }

    if (!bestaetigt) {
      anzeige.className = "rueckmeldung erfolg";
      anzeige.textContent = "übertragen ✓";
      this._freigeben(anzeige, RUECKMELDUNG_MS);
      return;
    }

    anzeige.className = "rueckmeldung wartet";
    anzeige.textContent = "wird ausgeführt …";
    this._wartend.push({ anzeige, bestaetigt, seit: Date.now() });
    this._pruefeWartende();
  }

  /** Die Anzeige nach kurzer Zeit wieder dem Zustand überlassen. */
  _freigeben(anzeige, verzoegerung) {
    window.setTimeout(() => {
      delete anzeige.dataset.belegt;
      this._aktualisieren();
    }, verzoegerung);
  }

  /**
   * Laufende Vorgänge prüfen.
   *
   * Läuft bei jedem Zustandswechsel mit – die Anlage meldet ihren neuen
   * Zustand mit dem nächsten Abruf, und genau darauf wird gewartet.
   */
  _pruefeWartende() {
    if (!this._wartend.length) return;
    const offen = [];
    this._wartend.forEach((vorgang) => {
      let fertig = false;
      try {
        fertig = vorgang.bestaetigt();
      } catch (err) {
        console.warn("HeatNexus: Zustand nicht prüfbar", err);
        fertig = true;
      }
      if (fertig) {
        vorgang.anzeige.className = "rueckmeldung erfolg";
        vorgang.anzeige.textContent = "übernommen ✓";
        this._freigeben(vorgang.anzeige, RUECKMELDUNG_MS);
        return;
      }
      if (Date.now() - vorgang.seit > BESTAETIGUNG_MAX_MS) {
        vorgang.anzeige.className = "rueckmeldung";
        vorgang.anzeige.textContent = "keine Rückmeldung";
        this._freigeben(vorgang.anzeige, RUECKMELDUNG_MS);
        return;
      }
      offen.push(vorgang);
    });
    this._wartend = offen;
  }

  /** Was unter einer Taste steht, wenn gerade nichts übertragen wird. */
  _tastenZustand(bereich, zustand, laeuft) {
    if (!zustand) return "";
    if (bereich === "button") {
      const zeitpunkt = new Date(zustand.state);
      if (Number.isNaN(zeitpunkt.getTime())) return "noch nie ausgelöst";
      return `zuletzt ${zeitpunkt.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      })}`;
    }
    return laeuft ? "läuft" : "aus";
  }

  // -------------------------------------------------------------------
  _aktualisieren() {
    this._bindungen.forEach((binden) => binden());
    this._pruefeWartende();
    (this._verlaufskarten || []).forEach((karte) => {
      karte.hass = this._hass;
    });
  }
}

/*
 * Der Name des Anzeigeelements trägt die Fassungsnummer.
 *
 * Ein Element lässt sich im Browser nur einmal je Seitensitzung anmelden. Mit
 * festem Namen übersprang eine neu geladene Fassung die Anmeldung, und die
 * alte Klasse zeichnete weiter – sichtbar wurde die Änderung erst nach
 * Strg+Umschalt+R. Die Fassung steht schon im Pfad dieser Datei
 * (`/heatnexus-frontend/<fassung>/heatnexus-panel.js`), von dort kommt sie.
 *
 * Passt der Pfad nicht zum Muster, bleibt es beim bisherigen Namen; dann ist
 * das Verhalten wie vorher, aber nichts kaputt. Die Integration bildet
 * denselben Namen in `const.panel_element`.
 */
const FASSUNG = (import.meta.url.match(/\/heatnexus-frontend\/([^/]+)\//) || [])[1];
const ELEMENT = FASSUNG ? `heatnexus-panel-${FASSUNG}` : "heatnexus-panel";
if (!customElements.get(ELEMENT)) {
  customElements.define(ELEMENT, HeatNexusPanel);
}
