/** Stil: Zeitprogramme: Wochenraster und Editor (teile/zeitprogramme.js). Zusammengesetzt in `stil.js`. */

export const ZEITPROGRAMME = `
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
`;
