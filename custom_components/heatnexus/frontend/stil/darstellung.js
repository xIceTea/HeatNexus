/** Stil: Fenster „Darstellung“ (teile/darstellung.js). Zusammengesetzt in `stil.js`. */

export const DARSTELLUNG = `
  /* --- Darstellung ----------------------------------------------------- */
  .dialog.darstellung { max-width: 600px; }
  .darstellung-zeile {
    display: grid; grid-template-columns: minmax(0, 150px) minmax(0, 1fr); gap: 16px;
    padding: 16px 0; border-top: 1px solid var(--hn-linie);
  }
  .dialog-text + .darstellung-zeile { margin-top: 14px; }
  .darstellung-name {
    margin: 0; font-size: 14px; font-weight: 600; letter-spacing: 0;
    text-transform: none; opacity: 1; color: var(--hn-text);
  }
  .darstellung-erklaerung { margin: 4px 0 0; font-size: 12px; line-height: 1.4; color: var(--hn-gedaempft); }
  /* Schmal steht die Erklärung über der Wahl. */
  @media (max-width: 560px) {
    .darstellung-zeile { grid-template-columns: minmax(0, 1fr); gap: 10px; }
  }
  .darstellung-wahl { display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
  .darstellung-wahl.farben { grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); }
  .darstellung-wahl.menue, .darstellung-wahl.strang, .darstellung-wahl.alle {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  }
  .darstellung-muster {
    display: flex; flex-direction: column; gap: 8px; padding: 8px; border-radius: 12px;
    font: inherit; color: inherit; text-align: left; cursor: pointer;
    background: var(--hn-grund); border: 2px solid var(--hn-linie);
  }
  .darstellung-muster:hover { border-color: color-mix(in srgb, var(--hn-akzent) 45%, transparent); }
  .darstellung-muster[aria-pressed="true"] { border-color: var(--hn-akzent); }
  .darstellung-muster:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }
  .muster-name { font-size: 13px; font-weight: 600; }

  /* Jede Vorschau ist ein Ausschnitt der Oberfläche: gleiche Fläche, gleicher Rahmen. */
  .farb-vorschau, .kopf-vorschau, .alle-vorschau, .strang-vorschau {
    position: relative; box-sizing: border-box; height: 52px; border-radius: 8px; overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--hn-text) 18%, transparent);
  }
  .farb-vorschau i { position: absolute; left: 8px; right: 8px; border-radius: 4px; }
  .farb-vorschau .balken { top: 8px; right: auto; width: 30px; height: 5px; }
  .farb-vorschau .flaeche { top: 19px; bottom: 8px; }
  .kopf-vorschau { display: flex; align-items: center; gap: 8px; padding: 0 10px; }
  .kopf-vorschau .zeichen { width: 26px; height: 26px; flex: none; }
  .kopf-vorschau ha-icon { --mdc-icon-size: 22px; color: var(--hn-gedaempft); }
  .kopf-vorschau > i { flex: 0 1 44px; min-width: 12px; height: 6px; border-radius: 3px; background: color-mix(in srgb, var(--hn-text) 22%, transparent); }
  .kopf-vorschau .wortmarke .marke { font-size: 15px; }
  .kopf-vorschau .wortmarke.farbig .marke { font-size: 16px; }

  /* Anlagenteile als Kärtchen an einer Leitung, wie im Schaubild. */
  .strang-vorschau { display: flex; align-items: center; justify-content: center; }
  .strang-vorschau .strang { display: flex; flex-direction: column; align-items: flex-start; gap: 5px; }
  .strang-vorschau .gruppe { position: relative; display: flex; gap: 5px; }
  .strang-vorschau .gruppe::before {
    content: ""; position: absolute; left: 4px; right: 4px; top: 50%; height: 2px; margin-top: -1px;
    background: color-mix(in srgb, var(--hn-akzent) 70%, transparent);
  }
  .strang-vorschau i, .alle-vorschau i {
    position: relative; box-sizing: border-box; border-radius: 3px; background: var(--hn-karte);
    border: 1px solid color-mix(in srgb, var(--hn-text) 16%, transparent);
  }
  .strang-vorschau i { width: 20px; height: 15px; }
  .strang-vorschau i::after {
    content: ""; position: absolute; left: 3px; top: 3px; width: 4px; height: 4px;
    border-radius: 50%; background: var(--hn-akzent);
  }
  .strang-vorschau.verkleinern i { width: 12px; height: 10px; }
  .strang-vorschau.verkleinern i::after { left: 2px; top: 2px; width: 3px; height: 3px; }

  /* Zwei Anlagen, unterschieden an der Farbe der Kartenkante. */
  .alle-vorschau { display: flex; flex-direction: column; justify-content: center; gap: 4px; padding: 5px 8px; }
  .alle-vorschau .gruppe { display: flex; gap: 4px; flex: 1; }
  .alle-vorschau i { flex: 1; border-top: 2px solid var(--hn-akzent); }
  .alle-vorschau i.b { border-top-color: var(--hn-gedaempft); }
  .alle-vorschau.zusammen { flex-direction: row; }
  .alle-vorschau.zusammen .gruppe {
    flex-direction: column; gap: 3px; padding: 3px; border-radius: 4px; background: var(--hn-karte);
    border: 1px solid color-mix(in srgb, var(--hn-text) 16%, transparent);
  }
  .alle-vorschau.zusammen i { border-left: 0; border-right: 0; border-bottom: 0;
    background: color-mix(in srgb, var(--hn-text) 7%, var(--hn-karte)); }

  /* Farben der Beschriftung: Name links, Wähler rechts; die Deckkraft mit Prozentzahl. */
  .beschriftung-wahl { display: flex; flex-direction: column; gap: 10px; }
  .beschriftung-feld {
    display: grid; grid-template-columns: minmax(0, 1fr) auto 3.5em; align-items: center; gap: 10px;
    font-size: 13px; color: var(--hn-text);
  }
  .beschriftung-farbzeile { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--hn-text); }
  .beschriftung-farben { display: flex; flex-wrap: wrap; gap: 8px; }
  .beschriftung-warnung { margin: 0; font-size: 12px; color: var(--hn-sonne); }
  .beschriftung-farbe, .beschriftung-eigene {
    width: 34px; height: 34px; padding: 0; border: 1px solid var(--hn-linie); border-radius: 50%;
    cursor: pointer;
  }
  /* Der Regenbogen und die Pipette kennzeichnen das freie Feld; gewählt zeigt es die Farbe selbst. */
  .beschriftung-eigene {
    position: relative; box-sizing: border-box; display: grid; place-items: center;
    color: #fff; --mdc-icon-size: 18px;
    background: conic-gradient(#ef5350, #ffca28, #66bb6a, #29b6f6, #ab47bc, #ef5350);
  }
  .beschriftung-eigene.gewaehlt { background: var(--eigene-farbe); }
  .beschriftung-eigene ha-icon { pointer-events: none; filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.9)); }
  .beschriftung-eigene input {
    position: absolute; inset: 0; width: 100%; height: 100%; padding: 0; border: none;
    opacity: 0; cursor: pointer;
  }
  .beschriftung-farbe[aria-pressed="true"], .beschriftung-eigene.gewaehlt {
    box-shadow: 0 0 0 2px var(--hn-karte), 0 0 0 4px var(--hn-akzent);
  }
  .beschriftung-farbe:focus-visible, .beschriftung-eigene:focus-within {
    outline: 2px solid var(--hn-akzent); outline-offset: 4px;
  }
  .beschriftung-feld input[type="range"] { width: 140px; accent-color: var(--hn-akzent); }
  .beschriftung-zahl { font-size: 12px; color: var(--hn-gedaempft); font-variant-numeric: tabular-nums; }
  .beschriftung-zurueck { align-self: flex-start; }
  /* Eine Wahl, die nur bei einer anderen gilt, steht darunter als schmaler Umschalter. */
  .darstellung-unter { margin-top: 14px; }
  .unter-name {
    display: flex; flex-wrap: wrap; justify-content: space-between; gap: 2px 10px;
    margin-bottom: 6px; font-size: 12px; font-weight: 600; color: var(--hn-text);
  }
  .unter-bedingung { font-weight: 400; color: var(--hn-gedaempft); }
  .darstellung-wahl.kompakt {
    grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0;
    border: 1px solid var(--hn-linie); border-radius: 10px; overflow: hidden;
  }
  .darstellung-wahl.kompakt .darstellung-muster {
    justify-content: center; align-items: center; text-align: center; padding: 8px 6px;
    border: 0; border-radius: 0; background: var(--hn-grund);
  }
  .darstellung-wahl.kompakt .darstellung-muster + .darstellung-muster { border-left: 1px solid var(--hn-linie); }
  .darstellung-wahl.kompakt .darstellung-muster:hover {
    background: color-mix(in srgb, var(--hn-akzent) 14%, var(--hn-grund));
  }
  .darstellung-wahl.kompakt .darstellung-muster[aria-pressed="true"] {
    background: var(--hn-akzent); color: var(--hn-akzent-text, #fff);
  }
  .darstellung-wahl.kompakt .darstellung-muster:focus-visible { outline-offset: -3px; }
  .darstellung-unter.aus .darstellung-wahl { opacity: 0.4; }
  .darstellung-unter.aus .darstellung-muster { cursor: not-allowed; }
  .darstellung-unter.aus .darstellung-muster:hover { background: var(--hn-grund); }
`;
