/** Stil: Karten, Klappkarten, Überschriften und Abzeichen. Zusammengesetzt in `stil.js`. */

export const KARTEN = `
  /* --- Karte zum Aufklappen -------------------------------------------- */
  /* Der Verlauf ist in der Übersicht zugeklappt: Er ist das größte Element
     der Seite, und wer ihn wirklich lesen will, geht in den eigenen Reiter. */
  .klappkarte > summary {
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .klappkarte > summary::-webkit-details-marker { display: none; }
  .klappkarte > summary h2 { flex: 1; margin: 0; }
  .klappkarte > summary .pfeil {
    flex: none; opacity: 0.5; transition: transform 0.15s ease;
    --mdc-icon-size: 20px;
  }
  .klappkarte[open] > summary { margin-bottom: 12px; }
  .klappkarte[open] > summary .pfeil { transform: rotate(180deg); }
  .karte {
    background: var(--hn-karte);
    border: 1px solid var(--hn-flaeche);
    border-radius: 16px;
    padding: 14px 16px;
  }
  .karte + .karte { margin-top: 16px; }
  /* Das Programm, nach dem die Anlage gerade faehrt. Voller Akzentrahmen und
     ein Balken an der Kante; der Ring liegt als Schatten aussen an, damit die
     Karte nicht um einen Punkt springt. Nicht Rot: Das heisst hier Stoerung. */
  .karte.aktiv {
    background: color-mix(in srgb, var(--hn-akzent) 12%, var(--hn-karte));
    border-color: var(--hn-akzent);
    box-shadow: inset 5px 0 0 0 var(--hn-akzent), 0 0 0 1px var(--hn-akzent);
  }
  /* Der Abstand liegt am Kopf, nicht am Titel; sonst rückt das „?“ unter die Titelmitte. */
  .kartenkopf { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
  .zp-aktiv { margin-left: 6px; color: var(--hn-akzent); font-weight: 600; }
  .kartenkopf h2 { flex: 1; margin-bottom: 0; }
  .fragezeichen {
    width: 22px; height: 22px; flex: none; border-radius: 50%; padding: 0;
    display: inline-flex; align-items: center; justify-content: center;
    font: inherit; font-size: 13px; font-weight: 700; line-height: 1;
    cursor: pointer; color: var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--hn-akzent) 35%, transparent);
  }
  .fragezeichen:hover {
    background: color-mix(in srgb, var(--hn-akzent) 28%, transparent);
    border-color: color-mix(in srgb, var(--hn-akzent) 70%, transparent);
  }
  .fragezeichen.auf-taste { position: absolute; top: 6px; right: 6px; }
  .taste { position: relative; }
  h2 {
    margin: 0 0 12px;
    font-size: 17px;
    font-weight: 600;
    letter-spacing: 0.2px;
  }
  h3 {
    margin: 18px 0 10px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    opacity: 0.55;
  }
  .abzeichen {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 14px; border-radius: 999px; font-weight: 600; font-size: 14px;
    background: rgba(67, 160, 71, 0.15); color: #7bd88f;
  }
  .abzeichen.stoerung { background: rgba(229, 57, 53, 0.15); color: #ff8a80; }
`;
