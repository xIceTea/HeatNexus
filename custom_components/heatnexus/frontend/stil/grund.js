/** Stil: Grundlage: verborgene Elemente, Farbsätze und das Wirtselement. Zusammengesetzt in `stil.js`. */

export const GRUND = `
  /* Klassen mit eigenem display schlagen sonst die Browserregel für hidden. */
  [hidden] { display: none !important; }

  /* Farbsätze der Oberfläche.

     Die Vorgabe folgt Home Assistant; wählt jemand einen festen Satz, setzt
     die Oberfläche dieselben Variablen am Wirtselement neu. */
  :host {
    --hn-grund: var(--primary-background-color, #0e1419);
    --hn-karte: var(--card-background-color, #151d26);
    --hn-text: var(--primary-text-color, #e6edf3);
    --hn-gedaempft: color-mix(in srgb, var(--hn-text) 72%, transparent);
    /* Der Akzent mischt etwas Textfarbe zu: Im hellen Erscheinungsbild wird
       er dunkler, im dunklen heller; beide erreichen so 4,5:1 zum Grund. */
    --hn-akzent: color-mix(in srgb, var(--primary-color, #6fb2f5) 60%, var(--hn-text));
    --hn-akzent-text: var(--hn-grund);
    --hn-linie: color-mix(in srgb, var(--hn-text) 14%, transparent);
    --hn-flaeche: color-mix(in srgb, var(--hn-text) 7%, transparent);
    --hn-sonne: #f5c451;
    --hn-ww: #5aa9e6;
    --hn-gut: #7bd88f;
    --hn-at: #4fd1b5;
  }

  :host {
    display: block;
    /* iOS-Safari hebt die Schrift langer Zeilen sonst eigenmächtig an. */
    -webkit-text-size-adjust: 100%;
    text-size-adjust: 100%;
    background: var(--hn-grund);
    color: var(--hn-text);
    min-height: 100%;
    box-sizing: border-box;
  }
  * { box-sizing: border-box; }
`;
