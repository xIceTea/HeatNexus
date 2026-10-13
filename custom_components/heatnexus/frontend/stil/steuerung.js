/** Stil: Die Steuerung (teile/steuerung.js). Zusammengesetzt in `stil.js`. */

export const STEUERUNG = `
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
`;
