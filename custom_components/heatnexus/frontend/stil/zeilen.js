/** Stil: Zeilen und Statuszeilen der Karten. Zusammengesetzt in `stil.js`. */

export const ZEILEN = `
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
`;
