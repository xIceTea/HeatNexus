/** Stil: Kopfleiste mit Menütaste, Marke, Anlagenwahl und Reitern. Zusammengesetzt in `stil.js`. */

export const KOPFLEISTE = `
  /* --- Kopfleiste: Menütaste, Marke, Anlagenwahl, Reiter --------------- */
  /* Kopfleiste und Reiter bleiben beim Blättern stehen; nur die Karten
     darunter laufen durch. Beide stecken dafür in einem gemeinsamen Kasten:
     Zwei getrennt klebende Elemente würden übereinander rutschen, weil jedes
     für sich am oberen Rand hängen bliebe.

     Der Hintergrund ist Pflicht – ohne ihn scheinen die Karten durch die
     Leiste hindurch. Der Farbwert ist derselbe wie am Wirtselement, damit die
     Leiste im hellen wie im dunklen Erscheinungsbild nicht auffällt. */
  .leiste {
    position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5;
    background: var(--hn-grund);
    border-bottom: 1px solid var(--hn-flaeche);
    /* Am iPhone klebt die Leiste unter der Statusleiste; der Schatten deckt den Streifen darüber. */
    box-shadow: 0 calc(-1 * env(safe-area-inset-top, 0px)) 0 0 var(--hn-grund);
  }
  .kopfleiste {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px 0;
    flex-wrap: wrap;
  }
  /* Runde Tasten ohne Rahmen wie in den Ansichten von Home Assistant. */
  .menue-taste {
    display: inline-flex;
    align-items: center; justify-content: center;
    width: 44px; height: 44px; flex: none;
    border-radius: 50%; cursor: pointer;
    background: none; border: none; padding: 0;
    color: inherit;
  }
  .menue-taste:hover { background: var(--hn-flaeche); }
  .menue-taste ha-icon { --mdc-icon-size: 24px; }
  .seitenleiste-taste { margin: 0 -8px 0 -6px; }
  .zeichen-taste { margin: 0 -4px 0 -7px; }
  .markenblock { display: flex; align-items: center; gap: 10px; }
  .markenblock .zeichen { width: 30px; height: 30px; flex: none; }
  .markenblock.kurz { gap: 8px; }
  .markenblock.kurz .zeichen { width: 26px; height: 26px; }
  .zeichen .knoten { fill: var(--hn-grund); }
  .wortmarke .marke { font-size: 18px; font-weight: 500; line-height: 1.15; }
  .wortmarke .unterzeile { font-size: 12px; color: var(--hn-gedaempft); }
  .wortmarke.farbig .marke { font-size: 19px; font-weight: 700; letter-spacing: -0.4px; line-height: 1.15; }
  .markenblock.kurz .wortmarke .marke { font-size: 20px; }
  .wortmarke.farbig .heat, .wortmarke.farbig .nexus {
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  .wortmarke.farbig .heat { background-image: linear-gradient(90deg, #f7a23b, #ee5a30); }
  .wortmarke.farbig .nexus { background-image: linear-gradient(90deg, #3d9fe6, #46b6f0); }
  /* Werkzeuge der Kopfzeile: ein Knopf, darunter die Liste. */
  /* Ganz nach rechts, auch wenn die Kopfzeile umbricht: Sonst klebt der
     Knopf an der letzten Anlagentaste statt am Rand. */
  .werkzeuge { position: relative; flex: none; margin-left: auto; }
  .werkzeugliste {
    position: absolute; right: 0; top: calc(100% + 6px); z-index: 20;
    min-width: 220px; padding: 6px; border-radius: 12px;
    background: var(--hn-karte);
    border: 1px solid var(--hn-linie);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
  }
  .werkzeugliste[hidden] { display: none; }
  .werkzeugliste button {
    display: flex; align-items: center; gap: 10px; width: 100%;
    padding: 9px 10px; border-radius: 9px; cursor: pointer;
    background: none; border: none; color: inherit; text-align: left;
    font: inherit; font-size: 14px; font-weight: 600;
  }
  .werkzeugliste button:hover { background: var(--hn-flaeche); }
  .werkzeugliste ha-icon { --mdc-icon-size: 20px; }
  .kopfleiste .abstand { flex: 1; }
  .aussen {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 12px; border-radius: 999px; font-size: 14px; font-weight: 600;
    background: var(--hn-flaeche);
  }
  .aussen ha-icon { --mdc-icon-size: 18px; }
  .waehler { display: flex; gap: 6px; flex-wrap: wrap; }
  .waehler button {
    padding: 8px 14px; border-radius: 999px; font: inherit; font-size: 13px;
    font-weight: 600; cursor: pointer; color: inherit;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .waehler button:hover { background: var(--hn-linie); }
  .waehler button[aria-selected="true"] {
    background: color-mix(in srgb, var(--hn-akzent) 18%, transparent);
    border-color: color-mix(in srgb, var(--hn-akzent) 50%, transparent);
    color: var(--hn-akzent);
  }
  .reiter { display: flex; gap: 4px; padding: 12px 16px 0; overflow-x: auto; }
  .reiter button {
    display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
    padding: 10px 16px; border: none; border-bottom: 2px solid transparent;
    background: none; font: inherit; font-size: 14px;
    font-weight: 600; cursor: pointer; color: var(--hn-gedaempft);
  }
  .reiter button:hover { color: var(--hn-text); }
  .reiter button[aria-selected="true"] {
    color: var(--hn-akzent); border-bottom-color: var(--hn-akzent);
  }
  .reiter button.punkt { position: relative; }
  .reiter button.punkt::after {
    content: ""; position: absolute; top: 6px; right: 6px; width: 8px; height: 8px; border-radius: 50%;
    background: var(--hn-akzent); box-shadow: 0 0 0 2px var(--hn-grund);
  }
  .reiter button.versteckt { text-decoration: line-through; color: var(--hn-gedaempft); }
  .reiter .reiter-griffe { display: inline-flex; align-items: center; margin-right: 8px; }
  .reiter .reiter-griffe button { padding: 4px; border-bottom: none; }
  .reiter .reiter-griffe button:hover { color: var(--hn-text); }
  .menue-taste:focus-visible, .werkzeugliste button:focus-visible,
  .waehler button:focus-visible, .reiter button:focus-visible {
    outline: 2px solid var(--hn-akzent); outline-offset: 2px;
  }
  .anlagen-trenner {
    display: flex; align-items: center; gap: 12px;
    margin: 8px 16px 0; padding-top: 16px;
    font-size: 15px; font-weight: 700; letter-spacing: 0.3px;
    border-top: 1px solid var(--hn-linie);
  }
  .anlagen-trenner:first-of-type { border-top: none; padding-top: 4px; }
`;
