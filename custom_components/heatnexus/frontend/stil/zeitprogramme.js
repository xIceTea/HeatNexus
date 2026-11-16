/** Stil: Zeitprogramme: Wochenraster und Editor (teile/zeitprogramme.js). Zusammengesetzt in `stil.js`. */

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

  /* Heute-Streifen: Name, Tagesbalken, Text in festen Spalten, damit die Balken untereinander stehen. */
  .zp-heute-zeile {
    display: grid; grid-template-columns: minmax(130px, 200px) 1fr minmax(170px, 230px);
    align-items: center; gap: 4px 14px; padding: 6px 0;
  }
  .zp-heute-kopf { padding: 0; }
  .zp-heute-kopf .zeitraster-skala { margin-left: 0; }
  .zp-heute-anlagenname {
    margin: 10px 0 2px; font-size: 12px; font-weight: 700; letter-spacing: 0.04em;
    text-transform: uppercase; opacity: 0.6;
  }
  .zp-heute-name { display: grid; grid-template-columns: auto 1fr; column-gap: 6px; align-items: center; }
  .zp-heute-name ha-icon { --mdc-icon-size: 18px; grid-row: span 2; opacity: 0.8; }
  .zp-heute-titel { font-size: 13px; font-weight: 600; }
  .zp-heute-programm { font-size: 12px; opacity: 0.6; }
  .zp-heute-text { font-size: 13px; font-variant-numeric: tabular-nums; }
  /* In der Spalte gilt flex:1 der Höhe, nicht der Breite; hier bleibt die Spur so hoch, wie sie ist. */
  .zp-heute-spur .spur { flex: none; }
  @media (max-width: 700px) {
    .zp-heute-zeile { grid-template-columns: 1fr; }
    .zp-heute-kopf > span { display: none; }
  }
  .zp-legende {
    display: flex; flex-wrap: wrap; gap: 6px 20px; margin-top: 12px;
    padding-top: 10px; border-top: 1px solid var(--hn-flaeche); font-size: 12px; opacity: 0.8;
  }
  .zp-legende-eintrag { display: inline-flex; align-items: center; gap: 6px; }
  .zp-legende-eintrag span:first-child { font-weight: 600; }
  .zp-verlauf { display: inline-block; width: 72px; height: 8px; border-radius: 4px; }
  .zp-ein { display: inline-block; width: 18px; height: 8px; border-radius: 4px; }

  /* Karte je Anlagenteil: Lagezeile, ein Reiter je Programm, je Block eine Spur in einer Farbe mit Klartext. */
  .zp-kartensymbol { --mdc-icon-size: 20px; opacity: 0.8; }
  .zp-gruppe + .zp-gruppe { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--hn-flaeche); }
  .zp-programm { display: flex; flex-direction: column; gap: 8px; }
  .zp-lage { font-size: 13px; color: var(--hn-gedaempft); text-wrap: pretty; }
  .zp-stueck { white-space: nowrap; }
  .zp-programmname, .zp-lagename { font-weight: 600; color: var(--hn-text); }
  .zp-aktiv { font-weight: 600; color: var(--hn-akzent); }
  .zp-reiter {
    display: flex; gap: 4px; padding: 3px; border-radius: 10px; background: var(--hn-flaeche);
  }
  .zp-reiter button {
    flex: 1; min-width: 0; display: flex; align-items: center; justify-content: center; gap: 6px;
    padding: 6px 8px; border: 0; border-radius: 8px; background: transparent; color: var(--hn-gedaempft);
    font: inherit; font-size: 13px; white-space: nowrap; cursor: pointer;
  }
  .zp-reiter button:hover { color: var(--hn-text); }
  .zp-reiter button[aria-selected="true"] {
    background: var(--hn-karte); color: var(--hn-text); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
  }
  .zp-reiter button.leer { opacity: 0.55; }
  .zp-reiter button:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .zp-reiter .zp-programmname, .zp-reiter .zp-mininame { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .zp-reiter .zp-mininame { font-weight: 400; }
  .zp-punkt-gilt { flex: none; width: 7px; height: 7px; border-radius: 50%; background: var(--hn-akzent); }
  /* Auf dem Telefon richten sich die Reiter nach ihrem Inhalt; der Zusatz „leer“ entfällt, der Reiter bleibt blass. */
  @media (max-width: 420px) {
    .zp-reiter .zp-zusatz { display: none; }
    .zp-reiter button { flex: 1 1 auto; padding: 6px 5px; gap: 5px; }
  }
  .zp-zeilen { display: flex; flex-direction: column; }
  .zp-zeile {
    display: grid; grid-template-columns: 64px 1fr; row-gap: 3px; padding: 6px 0;
    border-radius: 8px; cursor: pointer;
  }
  .zp-zeile:hover { background: color-mix(in srgb, var(--hn-flaeche) 60%, transparent); }
  .zp-zeile:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .zp-zeilenkopf, .zp-zeilenkopf:hover { padding: 0; cursor: default; background: none; }
  .zp-zeilenkopf .zeitraster-skala { margin: 0 6px 0 0; }
  .zp-tagname { align-self: center; padding-left: 6px; font-size: 13px; font-weight: 600; white-space: nowrap; }
  .zp-tagname.heute { color: var(--hn-akzent); }
  .zp-spur {
    position: relative; height: 14px; margin-right: 6px; border-radius: 7px;
    background: var(--hn-flaeche); overflow: hidden;
  }
  .zp-stunde { position: absolute; top: 3px; bottom: 3px; width: 1px; background: var(--hn-linie); }
  .zp-fuellung { position: absolute; top: 0; bottom: 0; border-radius: 7px; background: var(--hn-akzent); }
  .zp-fuellung.halb { opacity: 0.45; }
  .zp-spur .jetzt-linie {
    position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: var(--hn-text);
  }
  .zp-klartext {
    grid-column: 2; font-size: 12.5px; color: var(--hn-gedaempft);
    font-variant-numeric: tabular-nums; text-wrap: pretty;
  }
  .zp-abschnitt { margin-top: 4px; font-size: 12px; font-weight: 600; color: var(--hn-gedaempft); }
  .zp-leer { font-size: 12px; font-style: italic; }
  .zp-zustand { font-size: 13px; opacity: 0.75; margin-bottom: 2px; }
  .zp-warnung { font-size: 13px; color: var(--warning-color); margin-bottom: 2px; }
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
  .zp-weg:hover { background: rgba(229, 57, 53, 0.25); color: #ff8a80; }
  .zp-blockleiste { display: flex; gap: 8px; margin-top: 10px; }
  .zp-meldung { font-size: 13px; margin-top: 10px; min-height: 18px; }
  .zp-meldung.fehler { color: #ff8a80; }
`;
