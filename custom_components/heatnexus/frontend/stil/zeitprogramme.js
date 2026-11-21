/** Stil: Zeitprogramme: Wochenraster und Editor (teile/zeitprogramme.js). Zusammengesetzt in `stil.js`. */

// Schwarz oder Weiß, je nachdem, was vor dem Grund mindestens 4,5:1 hält: Leuchtdichte nach WCAG, Grenze 0,18.
const POL = "clamp(0, (0.18 - (0.2126 * r + 0.7152 * g + 0.0722 * b)) * 100000, 1)";
const gegenpol = (grund) => `color(from ${grund} srgb-linear ${POL} ${POL} ${POL})`;

export const ZEITPROGRAMME = `
  /* --- Zeitprogramme: Wochenraster und Editor -------------------------- */
  /* Die Balken sitzen in Prozent der Spur, nicht in Bildpunkten: Die Karte
     ist mal eine Spalte breit und mal vier. In Bildpunkten säßen die Zeiten
     schon bei der zweiten Breite daneben. */
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
  .zahl-feld input:focus-visible {
    outline: 2px solid var(--hn-akzent); outline-offset: 1px;
    border-color: var(--hn-akzent);
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
  .zahl-pfeil:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  /* Am Telefon braucht ein Finger mehr Fläche als ein Mauszeiger. */
  @media (max-width: 700px) {
    .zahl-pfeil { width: 40px; height: 24px; font-size: 13px; }
  }
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
  .zeitraster .spur {
    position: relative; flex: 1; height: 20px; border-radius: 5px;
    background: var(--hn-flaeche); overflow: hidden;
  }
  .zeitraster .spur.duenn { height: 7px; border-radius: 3px; }
  .zeitraster .spur.leer { opacity: 0.5; }
  .zeitraster .balken {
    position: absolute; top: 0; bottom: 0; overflow: hidden;
    display: flex; align-items: center; justify-content: center;
  }
  /* Der Wert im Segment; ein schmales Segment schneidet ihn ab statt umzubrechen. */
  .zeitraster .balken .zp-segmentwert {
    font-size: 11px; font-weight: 600; color: #fff; white-space: nowrap;
    text-shadow: 0 0 3px rgba(0, 0, 0, 0.6); padding: 0 3px;
  }
  /* Passt der Wert nicht ins Segment, steht er nur im Tooltip statt abgeschnitten. */
  .zeitraster .balken { container-type: inline-size; }
  @container (max-width: 44px) { .zeitraster .balken .zp-segmentwert { visibility: hidden; } }
  .zeitraster .jetzt-linie {
    position: absolute; top: -2px; bottom: -2px; width: 2px; margin-left: -1px;
    background: var(--hn-text); box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35);
  }
  .zeitraster-zeile.vorlauf { margin-top: 3px; }
  .zeitraster-zeile.vorlauf .tag { font-weight: 400; opacity: 0.55; }
  .zeitraster-abschnitt { margin: 10px 0 2px; font-size: 12px; font-weight: 600; opacity: 0.6; }

  /* Karte je Anlagenteil: ein Reiter je Programm, je Block eine Spur im Rahmen und darunter die Tabelle.
     Die Farbstufen mischen einen festen Ton mit dem Grund; so passen sie hell und dunkel. */
  :host {
    --zp-t14: color-mix(in oklab, oklch(0.6 0.05 250) 65%, var(--hn-grund));
    --zp-t17: color-mix(in oklab, oklch(0.66 0.02 250) 65%, var(--hn-grund));
    --zp-t19: color-mix(in oklab, oklch(0.76 0.08 82) 82%, var(--hn-grund));
    --zp-t21: color-mix(in oklab, oklch(0.76 0.13 66) 90%, var(--hn-grund));
    --zp-t23: color-mix(in oklab, oklch(0.68 0.17 44) 95%, var(--hn-grund));
    --zp-aus: color-mix(in srgb, var(--hn-text) 8%, var(--hn-grund));
    /* Tarife tragen feste Töne ohne Rangfolge; ihre Helligkeit hält hell wie dunkel 3:1 zu jeder Fläche. */
    --zp-tarif1: oklch(0.618 0.12 258);
    --zp-tarif2: oklch(0.62 0.11 80);
    --zp-tarif3: oklch(0.632 0.13 320);
    --zp-tarif4: oklch(0.608 0.09 205);
    --zp-tarif5: oklch(0.616 0.015 260);
    --zp-gilt: #f0882a;
  }
  .zp-kartensymbol { --mdc-icon-size: 20px; opacity: 0.8; }
  .zp-gruppe + .zp-gruppe { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--hn-linie); }
  .zp-programm { display: flex; flex-direction: column; gap: 10px; }
  .zp-lage { font-size: 13px; color: var(--hn-gedaempft); text-wrap: pretty; }
  .zp-programmname { font-weight: 600; color: var(--hn-text); }
  /* Nur für Vorleser; sichtbar steht der Punkt. */
  .zp-aktiv {
    position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap;
  }
  .zp-reiter {
    flex: 1; min-width: 0; display: flex; gap: 3px; padding: 3px; border-radius: 12px; background: var(--hn-flaeche);
  }
  .zp-reiter button {
    position: relative; flex: 1; min-width: 0; display: flex; align-items: center; justify-content: center; gap: 6px;
    padding: 7px 8px; border: 0; border-radius: 9px; background: transparent; color: var(--hn-gedaempft);
    font: inherit; font-size: 13px; white-space: nowrap; cursor: pointer;
  }
  .zp-reiter button:hover { color: var(--hn-text); }
  .zp-reiter button[aria-selected="true"] {
    background: var(--hn-karte); color: var(--hn-text); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
  }
  .zp-reiter button.leer, .zp-reiter button.leer[aria-selected="true"] { color: var(--hn-gedaempft); }
  /* Das geltende Programm: oranger Punkt und Rahmen; „gewählt“ ist nur die angehobene Fläche. */
  .zp-reiter button.gilt { box-shadow: inset 0 0 0 1.5px var(--zp-gilt); }
  .zp-reiter button.gilt[aria-selected="true"] { box-shadow: inset 0 0 0 1.5px var(--zp-gilt), 0 1px 2px rgba(0, 0, 0, 0.25); }
  .zp-punkt-gilt { flex: none; width: 7px; height: 7px; border-radius: 50%; background: var(--zp-gilt); }
  .zp-reiter button:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .zp-reiter .zp-programmname, .zp-reiter .zp-mininame { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  @media (max-width: 420px) {
    .zp-reiter button { flex: 1 1 auto; padding: 7px 5px; gap: 5px; }
  }
  .zp-zeilen { display: flex; flex-direction: column; }
  .zp-zeile { display: flex; flex-direction: column; gap: 6px; padding: 10px 6px; border-radius: 10px; cursor: pointer; }
  .zp-zeile + .zp-zeile { border-top: 1px solid var(--hn-linie); }
  .zp-zeile:hover { background: color-mix(in srgb, var(--hn-flaeche) 60%, transparent); }
  .zp-zeile:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .zp-tagname { font-size: 13px; font-weight: 600; white-space: nowrap; }
  .zp-rahmen {
    --zp-unter: var(--hn-grund);
    padding: 3px; border: 1px solid var(--hn-linie); border-radius: 12px; background: var(--zp-unter);
  }
  .zp-spur { position: relative; display: flex; gap: 2px; height: 30px; }
  /* Die Schrift im Stück ist Schwarz oder Weiß, je nach seiner Farbe; ohne relative Farben gilt die erste Angabe.
     Der Ruhewert tritt zurück, indem seine Fläche mit dem Grund mischt; die Schrift bleibt voll deckend. */
  .zp-stueck {
    --zp-fond: var(--zp-ton, var(--zp-aus));
    flex: 0 0 auto; min-width: 0; height: 100%; border-radius: 8px; background: var(--zp-fond);
    display: grid; place-items: center; overflow: hidden; white-space: nowrap;
    font-size: 11.5px; font-style: normal; font-weight: 600; font-variant-numeric: tabular-nums;
    color: rgba(10, 15, 20, 0.82);
    color: ${gegenpol("var(--zp-fond)")};
  }
  .zp-stueck.ruhe {
    --zp-fond: color-mix(in srgb, var(--zp-ton, var(--zp-aus)) 60%, var(--zp-unter));
    color: var(--hn-text);
    color: ${gegenpol("var(--zp-fond)")};
  }
  .zp-spur .jetzt-linie {
    position: absolute; top: -6px; bottom: -6px; width: 2px; margin-left: -1px; border-radius: 1px;
    background: var(--hn-text); pointer-events: none;
  }
  .zp-tipp {
    position: absolute; top: calc(100% + 8px); z-index: 2; transform: translateX(-50%);
    padding: 5px 9px; border-radius: 8px; background: var(--hn-text); color: var(--hn-grund);
    font-size: 12.5px; font-weight: 600; white-space: nowrap; font-variant-numeric: tabular-nums; pointer-events: none;
  }
  .zp-achse {
    position: relative; height: 14px; margin: 0 3px; font-size: 11px; color: var(--hn-gedaempft);
    font-variant-numeric: tabular-nums;
  }
  .zp-tipphinweis { font-size: 12px; color: var(--hn-gedaempft); }
  /* Mit Maus zeigt schon das Überfahren Zeit und Wert; der Hinweis gilt dem Finger. */
  @media (hover: hover) { .zp-tipphinweis { display: none; } }
  .zp-achse span { position: absolute; transform: translateX(-50%); }
  .zp-achse span:first-child { transform: none; }
  .zp-achse span:last-child { transform: translateX(-100%); }
  .zp-tabelle {
    display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; column-gap: 12px; row-gap: 4px;
    align-items: center; font-size: 13px; line-height: 1.35; font-variant-numeric: tabular-nums;
  }
  .zp-feld { width: 10px; height: 10px; border-radius: 3px; background: var(--hn-akzent); }
  .zp-feld.leer { background: transparent; }
  .zp-twert { font-weight: 600; text-align: right; }
  .zp-tzeit.rest, .zp-twert.rest { color: var(--hn-gedaempft); font-weight: 400; }
  .zp-ohne-fenster {
    display: flex; justify-content: space-between; gap: 10px; padding: 9px 12px; border: 1px dashed var(--hn-linie);
    border-radius: 12px; color: var(--hn-gedaempft); font-size: 13px;
  }
  .zp-ohne-fenster b { color: var(--hn-text); font-weight: 600; }
  .zp-kopfzeile { display: flex; align-items: center; gap: 8px; }
  .zp-titel { flex: 1; min-width: 0; font-size: 14px; font-weight: 600; line-height: 1.3; color: var(--hn-text); }
  .zp-vorsatz { font-size: 14px; font-weight: 600; line-height: 1.3; color: var(--hn-text); }
  .zp-stift {
    flex: none; display: inline-flex; padding: 3px; border: 0; border-radius: 6px; background: transparent;
    color: var(--hn-gedaempft); cursor: pointer; --mdc-icon-size: 18px;
  }
  .zp-stift:hover { color: var(--hn-text); background: var(--hn-flaeche); }
  .zp-stift:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .zp-benennen { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border-radius: 10px; background: var(--hn-flaeche); }
  .zp-benennen .zp-bezeichnung-zeile { margin-bottom: 0; }
  .zp-benennen .zp-meldung { margin-top: 0; min-height: 0; }
  .zp-benennen .zp-meldung:empty { display: none; }
  .zp-zeile.offen { background: var(--hn-flaeche); border-radius: 8px 8px 0 0; }
  /* Der Editor hängt unter seiner Zeile und gehört sichtbar zu ihr. */
  .zp-zeileneditor {
    display: flex; flex-direction: column; gap: 8px; margin: 0 0 6px; padding: 10px 12px 12px;
    border-radius: 0 0 10px 10px; background: var(--hn-flaeche);
  }
  .zp-ze-kopf { font-size: 12px; font-weight: 600; color: var(--hn-gedaempft); text-wrap: pretty; }
  .zp-ze-punkte { display: flex; flex-direction: column; gap: 6px; }
  .zp-ze-punkt { display: grid; grid-template-columns: auto minmax(0, 7em) minmax(0, 6em) auto auto; gap: 6px 8px; align-items: center; }
  .zp-ze-ab { font-size: 13px; color: var(--hn-gedaempft); }
  .zp-ze-feld {
    min-width: 0; padding: 5px 8px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600;
    color: inherit; background: var(--hn-karte); border: 1px solid var(--hn-linie);
  }
  .zp-ze-weg, .zp-ze-mehr {
    font: inherit; font-size: 13px; color: var(--hn-gedaempft); background: transparent; cursor: pointer;
    border: 1px solid var(--hn-linie); border-radius: 999px; padding: 3px 10px;
  }
  .zp-ze-weg { border: 0; font-size: 15px; }
  .zp-ze-mehr { align-self: flex-start; }
  .zp-ze-mehr:disabled { opacity: 0.4; cursor: default; }
  .zp-ze-tage { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; }
  .zp-tagwahl {
    padding: 4px 0; border-radius: 999px; font: inherit; font-size: 13px; cursor: pointer; color: inherit;
    background: transparent; border: 1px solid var(--hn-linie);
  }
  .zp-tagwahl[aria-pressed="true"] {
    background: color-mix(in srgb, var(--hn-akzent) 22%, transparent); border-color: var(--hn-akzent); font-weight: 600;
  }
  .zp-tagwahl:focus-visible, .zp-ze-feld:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .zp-ze-vorschau .zp-rahmen { --zp-unter: var(--hn-karte); }
  .zp-ze-aktionen { display: flex; justify-content: flex-end; gap: 8px; }
  .zp-zeileneditor .zp-meldung { margin-top: 0; min-height: 0; }
  .zp-zeileneditor .zp-meldung:empty { display: none; }
  .zp-abschnitt { margin-top: 4px; font-size: 12px; font-weight: 600; color: var(--hn-gedaempft); }
  .zp-leer { font-size: 12px; font-style: italic; }
  .zp-zustand { font-size: 13px; opacity: 0.75; margin-bottom: 2px; }
  /* Das Orange von Home Assistant ist auf heller Karte zu schwach; es mischt deshalb mit dem Pol der Karte. */
  .zp-warnung {
    font-size: 13px; margin-bottom: 2px;
    color: var(--warning-color);
    color: color-mix(in oklab, var(--warning-color, #ffa600) 70%, ${gegenpol("var(--hn-karte)")});
  }
  .zp-fuss {
    margin-top: auto; padding-top: 12px; font-size: 12px; opacity: 0.6;
    display: flex; flex-direction: column; gap: 3px;
  }
  .zp-gruppe:last-of-type { margin-bottom: 4px; }
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
  .zp-weg:hover { background: rgba(229, 57, 53, 0.25); color: var(--hn-fehler); }
  .zp-blockleiste { display: flex; gap: 8px; margin-top: 10px; }
  .zp-meldung { font-size: 13px; margin-top: 10px; min-height: 18px; }
  .zp-meldung.fehler { color: var(--hn-fehler); }
`;
