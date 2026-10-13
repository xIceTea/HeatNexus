/** Stil: Tasten und Rückmeldungen. Zusammengesetzt in `stil.js`. */

export const TASTEN = `
  /* --- Tasten ---------------------------------------------------------- */
  .taste {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 16px 10px; border-radius: 14px; cursor: pointer;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-flaeche);
    color: inherit; font: inherit; text-align: center;
  }
  .taste:hover { background: var(--hn-linie); }
  .taste .beschriftung { font-size: 13px; font-weight: 600; }
  .taste.an { border-color: color-mix(in srgb, var(--hn-akzent) 50%, transparent); color: var(--hn-akzent); }
  .taste.an .beschriftung { text-shadow: 0 0 12px color-mix(in srgb, var(--hn-akzent) 60%, transparent); }
  /* Läuft die Ladung, bricht dieselbe Taste sie ab. Eigene Farbe statt der
     von „an": Blau mit gleichfarbigem Schein sackt auf dunklem Grund ab, und
     warm sagt, dass ein Druck hier einen Gegenbefehl auslöst. */
  .taste.abbrechen { border-color: rgba(255, 176, 122, 0.55); color: #ffc9a3; }
  .taste.abbrechen .beschriftung { text-shadow: none; }
  /* Zweimal rot aufblitzen, wenn die Anlage einen Eingriff nicht annimmt.
     Der Grund steht klein darunter und wird sonst überlesen. */
  @keyframes taste-abgewiesen {
    0%, 100% { border-color: rgba(255, 138, 128, 0.15); }
    50% { border-color: #ff8a80; background: rgba(255, 138, 128, 0.12); }
  }
  .taste.blinkt { animation: taste-abgewiesen 0.6s ease-in-out 2; }
  /* Gesperrt, aber ohne Wartezeiger: Die Anlage braucht für eine Antwort gut
     zwei Sekunden, und dass etwas läuft, sagt die Zeile darunter. */
  .taste[disabled] { opacity: 0.6; cursor: default; }
  select {
    width: 100%; padding: 9px 10px; border-radius: 10px;
    background: var(--hn-flaeche); color: inherit;
    border: 1px solid var(--hn-linie); font: inherit;
  }
  .rueckmeldung { font-size: 11px; opacity: 0.5; min-height: 14px; }
  .rueckmeldung.laeuft { opacity: 0.9; color: var(--hn-akzent); }
  .rueckmeldung.erfolg { opacity: 1; color: #7bd88f; }
  .rueckmeldung.fehler { opacity: 1; color: #ff8a80; }
  .rueckmeldung.wartet { opacity: 0.9; color: #ffab6f; }
`;
