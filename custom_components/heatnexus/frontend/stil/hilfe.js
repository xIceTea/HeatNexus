/** Stil: Die Hilfe (teile/hilfe.js). Zusammengesetzt in `stil.js`. */

export const HILFE = `
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
