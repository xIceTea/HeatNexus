/** Stil: Reiter und Kachel „Befund“ (teile/befund.js). Zusammengesetzt in `stil.js`. */

export const BEFUND = `
  /* --- Befund: gemessene Kennwerte, gleiche Karten wie die anderen Reiter --- */
  .befund-lage { display: flex; flex-wrap: wrap; align-items: center; gap: 16px 32px; margin: 8px 0 4px; }
  .befund-seit { margin-left: auto; color: var(--hn-gedaempft); font-size: 14px; font-weight: normal; }
  .befund-ring { width: 150px; height: 150px; flex: none; }
  .befund-ring .bogen { fill: none; stroke-width: 14; stroke: var(--hn-linie); }
  .befund-ring .bogen.unauffaellig { stroke: var(--hn-gut); }
  .befund-ring .bogen.hinweis { stroke: var(--hn-sonne); }
  .befund-ring .ring-zahl { fill: var(--hn-text); font-size: 30px; font-weight: 600; }
  .befund-ring .ring-text { fill: var(--hn-gedaempft); font-size: 12px; }
  .befund-gruppen { flex: 1 1 260px; display: grid; }
  .befund-gruppe { display: grid; grid-template-columns: 48px 1fr; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--hn-linie); }
  .befund-gruppe:last-child { border-bottom: none; }
  .befund-anzahl { font-size: 30px; font-weight: 600; color: var(--hn-text); }
  .befund-gruppe.gut .befund-anzahl { color: var(--hn-gut); }
  .befund-gruppe.hinweis .befund-anzahl { color: var(--hn-sonne); }
  .befund-gruppe.null .befund-anzahl { color: var(--hn-gedaempft); }
  .befund-gruppentitel { font-weight: 600; font-size: 15px; }
  .befund-schutz { display: flex; align-items: center; gap: 10px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--hn-linie); color: var(--hn-gedaempft); font-size: 13px; }
  .befund-schutz ha-icon { --mdc-icon-size: 20px; flex: none; }
  .automatik-wert.befund-kompakt { grid-column: 1 / -1; }
  .befund-kompakt-kopf { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; }
  .befund-kompakt-kopf .befund-sprung { margin: 0 0 0 auto; }
  .befund-kompakt-inhalt { display: grid; grid-template-columns: minmax(200px, 300px) 1fr; gap: 16px 28px; margin-top: 12px; }
  .befund-uebersicht { padding-right: 24px; border-right: 1px solid var(--hn-linie); }
  .befund-gross { display: flex; align-items: baseline; gap: 10px; }
  .befund-gross .zahl { font-size: 56px; font-weight: 600; line-height: 1; color: var(--hn-text); }
  .befund-kaesten { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0; }
  .befund-kasten { display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 9px; border: 2px dashed var(--hn-linie); color: var(--hn-gedaempft); box-sizing: border-box; }
  .befund-kasten ha-icon { --mdc-icon-size: 20px; }
  .befund-kasten.unauffaellig { background: var(--hn-gut); border: none; color: var(--hn-karte); }
  .befund-kasten.hinweis { background: var(--hn-sonne); border: none; color: var(--hn-karte); }
  .befund-zaehlung { display: grid; grid-template-columns: 1fr auto; gap: 6px 12px; font-size: 14px; }
  .befund-zaehlung .anzahl { font-weight: 600; text-align: right; }
  .befund-zaehlung .anzahl.gut { color: var(--hn-gut); }
  .befund-zaehlung .anzahl.hinweis { color: var(--hn-sonne); }
  .befund-zaehlung .anzahl.null { color: var(--hn-gedaempft); }
  .befund-liste { display: grid; align-content: start; }
  .befund-merkmale { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
  .befund-merkmal { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 999px; background: var(--hn-flaeche); color: var(--hn-gedaempft); font-size: 13px; }
  .befund-merkmal ha-icon { --mdc-icon-size: 16px; color: var(--hn-gut); }
  .befund-zahl.klickbar { cursor: pointer; }
  .befund-feldkopf.klickbar { display: inline-flex; align-items: center; gap: 6px; color: var(--hn-akzent); cursor: pointer; }
  .befund-feldkopf ha-icon { --mdc-icon-size: 16px; }
  .befund-pruefung { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 16px; margin: 6px 0 4px; }
  @media (max-width: 700px) {
    .befund-kompakt-inhalt { grid-template-columns: 1fr; }
    .befund-uebersicht { padding-right: 0; border-right: none; padding-bottom: 12px; border-bottom: 1px solid var(--hn-linie); }
  }
  .befund-zeile { display: grid; grid-template-columns: 10px 1fr auto auto; align-items: center; gap: 12px; width: 100%; padding: 9px 2px; font: inherit; font-size: 14px; color: var(--hn-text); text-align: left; background: none; border: none; border-bottom: 1px solid var(--hn-linie); cursor: pointer; }
  .befund-zeile:last-child { border-bottom: none; }
  .befund-zeile .punkt { width: 9px; height: 9px; border-radius: 50%; border: 2px solid var(--hn-gedaempft); box-sizing: border-box; }
  .befund-zeile.unauffaellig .punkt { background: var(--hn-gut); border-color: var(--hn-gut); }
  .befund-zeile.hinweis .punkt { background: var(--hn-sonne); border-color: var(--hn-sonne); }
  .befund-zeile .wert { color: var(--hn-gedaempft); white-space: nowrap; }
  .befund-zeile .befund-marke { white-space: nowrap; }
  .befund-leise { color: var(--hn-gedaempft); font-size: 13px; }
  .befund-kopf { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: -4px 0 6px; }
  .befund-abschnitt { color: var(--hn-gedaempft); font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; }
  .befund-marke { font-size: 12px; padding: 2px 9px; border-radius: 999px; background: var(--hn-flaeche); }
  .befund-marke.unauffaellig { color: var(--hn-gut); }
  .befund-marke.hinweis { color: var(--hn-sonne); }
  .befund-marke.sammelt { color: var(--hn-akzent); }
  .befund-marke.braucht_daten { color: var(--hn-gedaempft); }
  .befund-wert { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; margin: 6px 0 4px; }
  .befund-wert .zahl { font-size: 44px; font-weight: 600; line-height: 1; color: var(--hn-text); }
  .befund-wert .einheit { font-size: 20px; color: var(--hn-gedaempft); }
  .befund-wert .neben { color: var(--hn-gedaempft); font-size: 15px; }
  .befund-feld { background: var(--hn-flaeche); border-radius: 12px; padding: 10px 12px; margin-top: 10px; }
  .befund-feld svg { display: block; width: 100%; height: auto; overflow: visible; }
  .befund-feld svg text { fill: var(--hn-gedaempft); font-size: 11px; }
  .befund-feld .linie { fill: none; stroke: var(--hn-gut); stroke-width: 2.5; }
  .befund-feld .punkt { fill: var(--hn-gedaempft); }
  .befund-feld .punkt.an { fill: var(--hn-gut); }
  .befund-feld circle.punkt:not(.an) { stroke: var(--hn-text); stroke-width: 2; fill: var(--hn-karte); }
  .befund-feld .balken { fill: var(--hn-linie); }
  .befund-feld .balken.an { fill: var(--hn-gut); }
  .befund-feld .balken.warn { fill: var(--hn-sonne); }
  .befund-feld .marke { stroke: var(--hn-text); stroke-dasharray: 4 3; }
  .befund-feld .achse { stroke: var(--hn-linie); }
  .befund-feld .zone { fill: var(--hn-gut); opacity: 0.12; }
  .befund-raum { display: grid; grid-template-columns: minmax(80px, 30%) 1fr auto; gap: 10px; align-items: center; margin: 6px 0; font-size: 14px; }
  .befund-stapel { display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: var(--hn-linie); }
  .befund-stapel .unter, .befund-legende i.unter { background: var(--hn-akzent); }
  .befund-stapel .am, .befund-legende i.am { background: var(--hn-gut); }
  .befund-stapel .leicht, .befund-legende i.leicht { background: color-mix(in srgb, var(--hn-gut) 50%, transparent); }
  .befund-stapel .ueber, .befund-legende i.ueber { background: var(--hn-sonne); }
  .befund-legende { display: flex; flex-wrap: wrap; gap: 4px 14px; color: var(--hn-gedaempft); font-size: 12px; margin-top: 8px; }
  .befund-legende i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
  .befund-vergleich { display: grid; grid-template-columns: 1fr auto; gap: 4px 16px; font-size: 14px; margin-top: 12px; }
  .befund-vergleich span:nth-child(odd) { color: var(--hn-gedaempft); }
  .befund-sprung { align-self: flex-start; margin-top: 10px; font: inherit; font-size: 13px; color: var(--hn-akzent); background: none; border: 1px solid var(--hn-linie); border-radius: 10px; padding: 6px 12px; cursor: pointer; }
  .befund-feld .ablesbar { cursor: pointer; }
  .befund-feld .treffer { fill: transparent; }
  .befund-feld .stelle { fill: transparent; }
  .befund-feld .gewaehlt .treffer { fill: var(--hn-akzent); opacity: 0.14; }
  .befund-feld .gewaehlt .stelle { fill: var(--hn-akzent); }
  .befund-stapel span.gewaehlt { box-shadow: inset 0 0 0 2px var(--hn-text); }
  .befund-ablesen { margin-top: 6px; min-height: 1.4em; }
  .befund-offen { display: grid; gap: 8px; font-size: 14px; }
  .befund-offen > div { display: flex; flex-wrap: wrap; gap: 2px 12px; }
  .befund-fuss { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--hn-linie); color: var(--hn-gedaempft); font-size: 13px; }
`;
