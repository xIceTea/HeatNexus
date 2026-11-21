/** Stil: Grundlage: verborgene Elemente, Farbsätze und das Wirtselement. Zusammengesetzt in `stil.js`. */

// Auf heller Karte (Leuchtdichte über 0,18) dunkelt ein Ton im linearen sRGB ab, auf dunkler bleibt er.
const HELL = "clamp(0, (0.2126 * r + 0.7152 * g + 0.0722 * b - 0.18) * 100000, 1)";
const linear = (kanal) => (kanal <= 0.04045 ? kanal / 12.92 : ((kanal + 0.055) / 1.055) ** 2.4);

/** Ein Ton, der auf heller Karte mit dem Faktor abdunkelt und so 4,5:1 hält. */
function aufKarte(hex, faktor) {
  const kanaele = [1, 3, 5].map((stelle) => linear(parseInt(hex.slice(stelle, stelle + 2), 16) / 255));
  const ausdruck = (kanal) => `calc(${kanal.toFixed(4)} * (1 - ${(1 - faktor).toFixed(3)} * ${HELL}))`;
  return `color(from var(--hn-karte) srgb-linear ${kanaele.map(ausdruck).join(" ")})`;
}

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
    /* Fehler und Warnung für Schrift; ohne relative Farben gilt die Schriftfarbe. */
    --hn-fehler: ${aufKarte("#ff8a80", 0.34)};
    --hn-warnung: ${aufKarte("#ffd54f", 0.2)};
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
