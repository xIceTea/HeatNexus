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
  /* Abweichung der Automatik unter der Betriebsart; Sonne warm, alles andere im Akzent. */
  .automatik-abzeichen {
    display: inline-flex; align-items: center; gap: 4px; margin-top: 4px; padding: 2px 8px 2px 6px;
    border: none; border-radius: 999px; font: inherit; font-size: 12px; font-weight: 600; cursor: pointer;
    color: var(--hn-akzent); background: color-mix(in srgb, var(--hn-akzent) 15%, transparent);
    --mdc-icon-size: 15px;
  }
  .automatik-abzeichen[hidden] { display: none; }
  .automatik-abzeichen[data-zustand="sonnentag"] {
    color: var(--hn-sonne); background: color-mix(in srgb, var(--hn-sonne) 16%, transparent);
  }
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
  .stoerspeicher-kopf {
    margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--hn-flaeche);
    font-size: 13px; font-weight: 600; color: var(--hn-gedaempft);
  }
  .stoerspeicher-kacheln { display: grid; }
  .stoerspeicher-kachel, .stoerspeicher-zeile {
    display: grid; grid-template-columns: 36px minmax(0, 1fr) 32px; gap: 12px; align-items: center;
    padding: 8px; cursor: pointer;
  }
  .stoerspeicher-kachel {
    padding-left: 5px; border-left: 3px solid var(--hn-farbe); background: var(--hn-ton);
  }
  .stoerspeicher-kachel .stoerspeicher-text { font-weight: 600; }
  .stoerspeicher-kachel .stoerspeicher-herkunft { color: var(--hn-farbe); }
  .stoerspeicher-zeile { border-bottom: 1px solid var(--hn-flaeche); }
  .stoerspeicher-zeile:last-child { border-bottom: none; }
  .stoerspeicher-taste, .stoerspeicher-muell {
    background: none; border: none; color: var(--hn-gedaempft); cursor: pointer; padding: 4px;
    display: flex; align-items: center; justify-content: center; border-radius: 6px;
  }
  .stoerspeicher-taste { color: var(--hn-farbe); }
  .stoerspeicher-taste:hover, .stoerspeicher-muell:hover { background: rgba(255, 255, 255, 0.08); }
  .stoerspeicher-text { font-size: 14px; overflow-wrap: anywhere; }
  .stoerspeicher-herkunft { font-size: 12px; color: var(--hn-gedaempft); }
  .stoerspeicher-symbol {
    width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
    background: var(--hn-ton); color: var(--hn-farbe);
  }
  .stoerspeicher-symbol ha-icon { opacity: 1; }
  .stoerspeicher-kachel.alarm, .stoerspeicher-symbol.alarm { --hn-ton: rgba(229, 57, 53, 0.14); --hn-farbe: #ff8a80; }
  .stoerspeicher-kachel.fehler, .stoerspeicher-symbol.fehler { --hn-ton: rgba(255, 193, 7, 0.12); --hn-farbe: #ffd54f; }
  .stoerspeicher-kachel.info, .stoerspeicher-symbol.info { --hn-ton: rgba(66, 165, 245, 0.14); --hn-farbe: #64b5f6; }
  .stoerspeicher-symbol.erledigt { --hn-ton: var(--hn-flaeche); --hn-farbe: var(--hn-gedaempft); }
  .stoerspeicher-kachel .stoerspeicher-symbol { background: rgba(0, 0, 0, 0.18); }
  .stoerspeicher-ende { display: flex; justify-content: center; }
`;
