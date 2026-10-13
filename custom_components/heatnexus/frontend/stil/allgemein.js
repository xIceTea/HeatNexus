/** Stil: Klickbare Elemente, Hinweise, YAML-Feld und Bewertungsfarben. Zusammengesetzt in `stil.js`. */

export const ALLGEMEIN = `
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
`;
