/** Stil: Fenster „Darstellung“ (teile/darstellung.js). Zusammengesetzt in `stil.js`. */

export const DARSTELLUNG = `
  /* --- Darstellung ----------------------------------------------------- */
  .dialog.darstellung { max-width: 560px; }
  .darstellung-name {
    margin: 18px 0 8px; font-size: 12px; font-weight: 600; letter-spacing: 0.4px;
    text-transform: uppercase; color: var(--hn-gedaempft);
  }
  .darstellung-wahl { display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }
  .darstellung-wahl.farben { grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); }
  .darstellung-muster {
    display: flex; flex-direction: column; gap: 8px; padding: 8px; border-radius: 12px;
    font: inherit; color: inherit; text-align: left; cursor: pointer;
    background: var(--hn-grund); border: 2px solid var(--hn-linie);
  }
  .darstellung-muster:hover { border-color: color-mix(in srgb, var(--hn-akzent) 45%, transparent); }
  .darstellung-muster[aria-pressed="true"] { border-color: var(--hn-akzent); }
  .darstellung-muster:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }
  .muster-name { font-size: 13px; font-weight: 600; }
  .farb-vorschau {
    position: relative; height: 52px; border-radius: 8px; overflow: hidden;
    border: 1px solid rgba(127, 127, 127, 0.3);
  }
  .farb-vorschau i { position: absolute; left: 8px; right: 8px; border-radius: 4px; }
  .farb-vorschau .balken { top: 8px; right: auto; width: 30px; height: 5px; }
  .farb-vorschau .flaeche { top: 19px; bottom: 8px; }
  .kopf-vorschau { display: flex; align-items: center; gap: 8px; min-height: 40px; }
  .kopf-vorschau .zeichen { width: 26px; height: 26px; flex: none; }
  .kopf-vorschau ha-icon { --mdc-icon-size: 22px; color: var(--hn-gedaempft); }
  .kopf-vorschau .wortmarke .marke { font-size: 15px; }
  .kopf-vorschau .wortmarke.farbig .marke { font-size: 16px; }
  .alle-vorschau { display: flex; flex-direction: column; gap: 6px; height: 52px; justify-content: center; }
  .alle-vorschau.zusammen { flex-direction: row; gap: 8px; }
  .alle-vorschau .gruppe { display: flex; gap: 3px; flex: 1; }
  .alle-vorschau i { flex: 1; min-height: 16px; border-radius: 4px; }
  .alle-vorschau i.a { background: var(--hn-akzent); }
  .alle-vorschau i.b { background: color-mix(in srgb, var(--hn-text) 35%, transparent); }
`;
