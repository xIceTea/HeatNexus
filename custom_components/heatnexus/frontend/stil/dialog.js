/** Stil: Dialoge. Zusammengesetzt in `stil.js`. */

export const DIALOG = `
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
`;
