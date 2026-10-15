/** Stil: Der Anordnen-Modus (teile/anordnen.js). Zusammengesetzt in `stil.js`. */

export const ANORDNEN = `
  /* --- Anordnen -------------------------------------------------------- */
  .anordnen-leiste {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    margin: 10px 16px 12px; padding: 10px 14px; border-radius: 14px;
    max-height: 45vh; overflow-y: auto;
    background: color-mix(in srgb, var(--hn-akzent) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--hn-akzent) 35%, transparent);
  }
  .anordnen-leiste .titel { font-weight: 700; font-size: 15px; color: var(--hn-akzent); }
  .anordnen-leiste .hinweis { font-size: 12px; opacity: 0.7; flex: 1; min-width: 180px; }
  .anordnen-leiste .abstand { flex: 1; }
  .anordnen-taste {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 14px; border-radius: 999px; cursor: pointer;
    font: inherit; font-size: 13px; font-weight: 600; color: inherit;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .anordnen-taste:hover { background: var(--hn-linie); }
  .anordnen-taste.fertig {
    background: color-mix(in srgb, var(--hn-akzent) 25%, transparent); border-color: color-mix(in srgb, var(--hn-akzent) 50%, transparent);
    color: #cfe6ff;
  }
  .anordnen-taste ha-icon { --mdc-icon-size: 18px; }
  /* Die Spaltenwahl sieht aus wie die Anlagenwahl oben – gleiche Geste. */
  /* Umbrechend statt überlaufend: Was auf einem Telefon rechts hinausläuft,
     ist nicht erreichbar. */
  .spaltenwahl { display: flex; flex-wrap: wrap; gap: 4px; max-width: 100%; }
  .spalten-feld { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .wahl-name { font-size: 13px; font-weight: 600; color: var(--hn-gedaempft); }
  .spaltenwahl button {
    min-width: 34px; padding: 7px 10px; border-radius: 999px;
    font: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
    color: inherit; opacity: 0.6;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .spaltenwahl button[aria-pressed="true"] {
    opacity: 1; color: var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 15%, transparent);
    border-color: color-mix(in srgb, var(--hn-akzent) 45%, transparent);
  }

  /* Die Hülle, die im Anordnen-Modus um jede Karte liegt. Ohne sie müsste die
     Karte selbst die Griffleiste tragen – und jede Kartenart hätte sie neu
     bekommen müssen. */
  .anordner { display: flex; flex-direction: column; min-width: 0; }
  .anordner > .karte, .anordner > .klappkarte {
    flex: 1;
    border-color: color-mix(in srgb, var(--hn-akzent) 35%, transparent);
    border-top-left-radius: 0; border-top-right-radius: 0;
  }
  .anordner-griff {
    display: flex; align-items: center; gap: 4px;
    padding: 6px 8px; cursor: grab;
    border: 1px solid color-mix(in srgb, var(--hn-akzent) 35%, transparent); border-bottom: none;
    border-radius: 14px 14px 0 0;
    background: color-mix(in srgb, var(--hn-akzent) 16%, transparent);
  }
  .anordner-griff .name {
    flex: 1; min-width: 0; font-size: 12px; font-weight: 600;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .anordner-griff button {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; flex: none; border-radius: 8px;
    background: var(--hn-flaeche); border: 1px solid var(--hn-linie);
    color: inherit; font: inherit; cursor: pointer;
  }
  .anordner-griff button:hover { background: var(--hn-linie); }
  .anordner-griff button:disabled { opacity: 0.3; cursor: default; }
  .anordner-griff button ha-icon { --mdc-icon-size: 16px; }
  /* Die Breite ist eine Anzeige, keine Taste – geklickt wird links und rechts
     davon. */
  .anordner-griff .breite {
    flex: none; min-width: 26px; padding: 0 2px;
    font-size: 12px; font-weight: 700; text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .anordner.gezogen { opacity: 0.4; }
  .anordner.ziel-vor { box-shadow: -3px 0 0 0 var(--hn-akzent); }
  .anordner.ziel-nach { box-shadow: 3px 0 0 0 var(--hn-akzent); }
  /* Versteckte Karten verschwinden nur außerhalb des Anordnen-Modus. Drin
     bleiben sie blass stehen – sonst wüsste niemand mehr, wo sie hinkommen. */
  .anordner.versteckt > .karte, .anordner.versteckt > .klappkarte {
    opacity: 0.35; filter: grayscale(1);
  }
`;
