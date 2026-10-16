/** Stil: Die Automatik (teile/automatik.js). Zusammengesetzt in `stil.js`. */

export const AUTOMATIK = `
  /* --- Automatik ------------------------------------------------------- */
  /* Gelb steht für Sonne, Blau für nur Warmwasser; Rot bleibt der Störung vorbehalten. */
  .automatik-bereich { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .raster:has(> .automatik-bereich) > * { align-self: start; }
  /* Die Hauptspalte reicht über viele Zeilen; Protokoll und Einladungen stapeln sich rechts daneben. */
  @media (min-width: 1181px) { .raster > .automatik-bereich { grid-row: span 24; } }
  .automatik-bereich > .karte + .karte { margin-top: 0; }
  .automatik-bereich h3 { margin: 0; font-size: 16px; font-weight: 700; text-transform: none; letter-spacing: normal; opacity: 1; }

  /* Kopfkarte */
  .karte.automatik { padding: 18px 20px; }
  .karte.automatik > .kartenkopf { margin-bottom: 0; flex-wrap: wrap; gap: 8px 12px; align-items: center; }
  .karte.automatik > .kartenkopf h2 { flex: 0 1 auto; min-width: 0; margin: 0; overflow-wrap: anywhere; line-height: 1.25; }
  .karte.automatik > .kartenkopf .automatik-knopf { margin-left: auto; }
  .automatik-marke {
    display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
    font-size: 12px; font-weight: 600; white-space: nowrap; line-height: 1.2;
    background: var(--hn-flaeche); color: var(--hn-gedaempft);
  }
  .automatik-marke::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
  .automatik-marke.z-sonnentag { background: color-mix(in srgb, var(--hn-sonne) 16%, transparent); color: var(--hn-sonne); }
  .automatik-marke.z-heizpause { background: color-mix(in srgb, var(--hn-at) 16%, transparent); color: var(--hn-at); }
  .automatik-marke.z-nur_ww { background: color-mix(in srgb, var(--hn-ww) 16%, transparent); color: var(--hn-ww); }
  .automatik-marke.z-programm { background: color-mix(in srgb, var(--hn-gut) 16%, transparent); color: var(--hn-gut); }
  .automatik-marke.z-pausiert, .automatik-marke.z-fenster, .automatik-marke.z-abwesend {
    background: color-mix(in srgb, var(--hn-akzent) 14%, transparent); color: var(--hn-akzent);
  }
  .automatik-marke.z-sicherheit, .automatik-marke.z-keine_daten {
    background: rgba(255, 171, 111, 0.15); color: #ffab6f;
  }
  .automatik-meta {
    display: flex; flex-wrap: wrap; gap: 4px 20px; margin: 6px 0 0;
    font-size: 13px; color: var(--hn-gedaempft);
  }
  .automatik-warum { margin: 16px 0 0; font-size: 17px; line-height: 1.5; }
  .automatik-zeile {
    display: flex; align-items: center; gap: 12px 24px; flex-wrap: wrap;
    margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--hn-linie);
  }
  .automatik-gruppe { display: inline-flex; align-items: center; gap: 10px; }
  .automatik-gruppe + .automatik-gruppe, .automatik-schalter + .automatik-gruppe {
    padding-left: 24px; border-left: 1px solid var(--hn-linie);
  }
  .automatik-gruppentitel {
    display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--hn-gedaempft);
  }
  .automatik-gruppentitel .fragezeichen { width: 18px; height: 18px; font-size: 11px; }
  /* Schalter: Text vorn, dahinter eine eckige Spur wie die Segmenttasten; eingeschaltet mit Haken. */
  .automatik-schalter {
    display: inline-flex; align-items: center; gap: 12px; padding: 0; cursor: pointer;
    background: none; border: none; color: inherit; font: inherit; font-size: 14px; font-weight: 600;
  }
  .automatik-schalter i {
    flex: none; width: 42px; height: 24px; border-radius: 8px; position: relative;
    background: var(--hn-flaeche); border: 1px solid var(--hn-linie);
    transition: background 0.2s, border-color 0.2s;
  }
  .automatik-schalter i::after {
    content: ""; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 5px;
    background: var(--hn-gedaempft); transition: transform 0.2s, background 0.2s;
  }
  /* Der Haken sitzt im Knopf der eingeschalteten Seite. */
  .automatik-schalter i::before {
    content: ""; position: absolute; z-index: 1; top: 6px; left: 27px; width: 4px; height: 8px;
    border: solid var(--hn-akzent-text); border-width: 0 2px 2px 0; transform: rotate(45deg);
    opacity: 0; transition: opacity 0.15s;
  }
  .automatik-schalter.an i {
    background: color-mix(in srgb, var(--hn-akzent) 20%, transparent); border-color: var(--hn-akzent);
  }
  .automatik-schalter.an i::after { transform: translateX(18px); background: var(--hn-akzent); }
  .automatik-schalter.an i::before { opacity: 1; }
  .automatik-schalter:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 3px; border-radius: 8px; }
  @media (prefers-reduced-motion: reduce) {
    .automatik-schalter i, .automatik-schalter i::before, .automatik-schalter i::after { transition: none; }
  }
  .automatik-befundschalter { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 32px; padding: 16px 20px 0; }
  .automatik-befundschalter h4 {
    flex: 1 1 100%; margin: 0; font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--hn-gedaempft);
  }
  .automatik-segment {
    display: inline-flex; padding: 3px; border-radius: 10px;
    background: var(--hn-flaeche); border: 1px solid var(--hn-linie);
  }
  .automatik-segment button {
    padding: 6px 12px; border-radius: 7px; border: none; background: none; cursor: pointer;
    color: var(--hn-gedaempft); font: inherit; font-size: 13px; font-weight: 500;
  }
  .automatik-segment button:hover:not([disabled]) { color: var(--hn-text); }
  .automatik-segment button[aria-pressed="true"] {
    background: color-mix(in srgb, var(--hn-akzent) 20%, transparent); color: var(--hn-akzent); font-weight: 600;
  }
  .automatik-segment button:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .automatik-hinweis {
    display: flex; gap: 12px; align-items: center; margin-top: 14px; padding: 10px 14px;
    border-radius: 12px; font-size: 13px;
    background: color-mix(in srgb, var(--hn-akzent) 10%, transparent);
    border: 1px dashed color-mix(in srgb, var(--hn-akzent) 45%, transparent);
  }
  .automatik-hinweis .text { flex: 1; }
  .automatik-hinweis.empfehlung {
    padding: 12px 16px; border: 1px solid var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 16%, transparent);
    box-shadow: inset 4px 0 0 var(--hn-akzent);
  }
  .empfehlung-titel {
    display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
    font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: var(--hn-akzent);
  }
  .empfehlung-titel ha-icon { --mdc-icon-size: 16px; }
  .empfehlung-grund { font-size: 14px; line-height: 1.45; }

  /* Tasten */
  .automatik-knopf {
    padding: 8px 16px; border-radius: 10px; border: 1px solid transparent; cursor: pointer; white-space: nowrap;
    font: inherit; font-size: 13px; font-weight: 600;
    background: var(--hn-akzent); color: var(--hn-akzent-text);
    transition: background 0.15s, color 0.15s, border-color 0.15s;
  }
  .automatik-knopf:hover:not([disabled]) { filter: brightness(1.08); }
  .automatik-knopf:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }
  .automatik-knopf.leise { background: transparent; color: inherit; border-color: var(--hn-linie); }
  .automatik-knopf.leise:hover:not([disabled]) { background: var(--hn-flaeche); filter: none; }
  .automatik-knopf.umriss {
    background: color-mix(in srgb, var(--hn-akzent) 10%, transparent); color: var(--hn-akzent);
    border-color: color-mix(in srgb, var(--hn-akzent) 45%, transparent);
  }
  .automatik-knopf.klein { padding: 6px 12px; font-size: 13px; }
  .automatik-knopf.warnung { color: #ffab6f; border-color: rgba(255, 171, 111, 0.45); }
  .automatik-knopf[disabled], .automatik-segment button[disabled], .automatik-schalter[disabled] {
    opacity: 0.5; cursor: default;
  }
  /* Speichern bleibt grau, bis ein Feld vom gespeicherten Wert abweicht. */
  .automatik-knopf.speichern[disabled] {
    opacity: 1; background: var(--hn-flaeche); color: var(--hn-gedaempft); border-color: var(--hn-linie);
  }
  .automatik-gespeichert { align-self: center; font-size: 12px; color: var(--hn-gut); }
  .automatik-bereich .klickbar { border-radius: 6px; }
  .automatik-bereich .klickbar:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; }

  /* Kennwerte */
  .automatik-werte { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
  .automatik-wert {
    padding: 16px 18px; border-radius: 16px; min-width: 0;
    background: var(--hn-karte); border: 1px solid var(--hn-flaeche);
  }
  .automatik-wert .titel {
    display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--hn-gedaempft); margin-bottom: 8px;
  }
  .automatik-wert .titel .fragezeichen { width: 18px; height: 18px; font-size: 11px; }
  /* Breite Kacheln wie die Auswertung stehen über zwei Spalten. */
  .automatik-wert.breit { grid-column: span 2; }
  .automatik-wert .werte { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
  .automatik-wert .zahl { font-size: 30px; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
  .automatik-wert.sonne .zahl { color: var(--hn-sonne); }
  .automatik-wert .neben { font-size: 13px; color: var(--hn-gedaempft); }
  .automatik-wert .fuss { font-size: 11px; margin-top: 8px; color: var(--hn-gedaempft); line-height: 1.4; }
  .automatik-wert .automatik-knopf { margin-top: 10px; }
  .automatik-wert .raeume { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
  .automatik-wert .raeume .raum { display: flex; justify-content: space-between; gap: 10px; }
  .automatik-wert .raeume .name { color: var(--hn-gedaempft); }
  .automatik-wert .raeume .wert { font-variant-numeric: tabular-nums; text-align: right; }
  .automatik-wert .raeume .heizt { color: #ffab6f; }
  .automatik-wert .raeume .veraltet { color: #ffab6f; }
  .automatik-wert .vorschlaege { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; font-size: 13px; }
  .automatik-wert .vorschlag { border-top: 1px solid var(--hn-linie); padding-top: 8px; }
  .automatik-wert .vorschlag .kopf { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  .automatik-wert .vorschlag .name { font-weight: 500; }
  .automatik-wert .vorschlag .empfehlung { font-size: 12px; padding: 2px 8px; border-radius: 10px; text-align: right;
    background: color-mix(in srgb, var(--hn-akzent) 18%, transparent); }
  .automatik-wert .vorschlag .empfehlung.passt { background: color-mix(in srgb, var(--hn-gut) 22%, transparent); }
  .automatik-wert .vorschlag .empfehlung.vorlaeufig { background: transparent; border: 1px dashed var(--hn-gedaempft); }
  .automatik-wert .vorschlag .angabe { color: var(--hn-gedaempft); font-size: 12px; margin-top: 2px; font-variant-numeric: tabular-nums; }
  .automatik-skala { margin-top: 14px; }
  .automatik-skala .bahn { position: relative; height: 18px; }
  .automatik-skala .bahn::before {
    content: ""; position: absolute; left: 0; right: 0; top: 7px; height: 4px;
    border-radius: 2px; background: var(--hn-linie);
  }
  .automatik-skala .zone { position: absolute; top: 7px; height: 4px; }
  .automatik-skala .zone:first-child { border-radius: 2px 0 0 2px; }
  .automatik-skala .zone.heizt, .automatik-skala .zone.kalt { background: color-mix(in srgb, #ff8a80 55%, transparent); }
  .automatik-skala .zone.hysterese { background: color-mix(in srgb, var(--hn-text) 25%, transparent); }
  .automatik-skala .zone.aus { background: color-mix(in srgb, var(--hn-gut) 55%, transparent); }
  .automatik-skala .zone.sonne { background: var(--hn-sonne); border-radius: 2px; }
  .automatik-skala .zone.neutral { background: color-mix(in srgb, var(--hn-text) 18%, transparent); }
  .automatik-skala .zone.moeglich { background: color-mix(in srgb, var(--hn-sonne) 45%, transparent); }
  .automatik-skala .zone.ueber { background: color-mix(in srgb, var(--hn-gut) 45%, transparent); }
  .automatik-skala .punkt-wert {
    position: absolute; top: -14px; transform: translateX(-50%);
    font-size: 11px; font-weight: 700; color: var(--hn-text); white-space: nowrap;
  }
  .automatik-skala .bahn:has(.punkt-wert) { margin-top: 14px; }
  .automatik-skala .marke { position: absolute; top: 2px; height: 14px; width: 0; border-left: 2px solid var(--hn-text); }
  .automatik-skala .marke.automatik { border-left-style: dashed; border-left-color: var(--hn-akzent); }
  .automatik-skala .marke.stark, .automatik-skala .marke.schwelle { opacity: 0.6; }
  .automatik-skala .marke.ziel { opacity: 0.35; }
  .automatik-skala .punkt {
    position: absolute; top: 3px; width: 12px; height: 12px; margin-left: -6px; border-radius: 50%;
    background: var(--hn-karte); border: 2px solid var(--hn-text);
  }
  .automatik-skala .punkt.gedaempft { border-color: var(--hn-gedaempft); }
  .automatik-skala .punkt.jetzt { width: 3px; height: 16px; top: 1px; margin-left: -1px; border: none; border-radius: 1px; background: var(--hn-text); }
  .automatik-skala .achse {
    display: flex; justify-content: space-between; gap: 6px; margin-top: 8px;
    font-size: 12px; color: var(--hn-gedaempft);
  }
  .automatik-skala .achse > span { white-space: nowrap; }
  .automatik-skala .achse .vorrang-zeile { color: var(--hn-gedaempft); }

  /* Tagesverlauf */
  .karte.automatik-verlauf { padding: 18px 20px; }
  .automatik-verlaufkopf { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 16px; margin-bottom: 14px; }
  .automatik-verlaufkopf .automatik-tagwahl { margin: 0; }
  .automatik-tagwahl {
    display: inline-flex; gap: 2px; padding: 3px; border-radius: 10px;
    background: var(--hn-flaeche); border: 1px solid var(--hn-linie);
  }
  .automatik-tagwahl button {
    padding: 5px 12px; border-radius: 7px; border: none; background: none; cursor: pointer;
    color: var(--hn-gedaempft); font: inherit; font-size: 13px; font-weight: 500;
  }
  .automatik-tagwahl button[aria-pressed="true"] {
    background: color-mix(in srgb, var(--hn-akzent) 20%, transparent); color: var(--hn-akzent); font-weight: 600;
  }
  .automatik-stundenlegende {
    display: flex; flex-wrap: wrap; gap: 4px 16px; margin-left: auto;
    font-size: 12px; color: var(--hn-gedaempft); cursor: help;
  }
  .automatik-stundenlegende i { display: inline-block; width: 12px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
  .automatik-stundenlegende i.m-absenkung { background: var(--hn-sonne); }
  .automatik-stundenlegende i.m-heizpause { background: var(--hn-at); }
  .automatik-stundenlegende i.m-nur_ww { background: var(--hn-ww); }
  .automatik-stundenlegende i.m-programm { background: color-mix(in srgb, var(--hn-text) 35%, transparent); }
  .automatik-vorschau {
    margin: 0 0 12px; padding: 8px 12px; border-radius: 10px; font-size: 13px;
    background: var(--hn-flaeche); border: 1px dashed var(--hn-linie);
  }
  .automatik-stunden {
    display: grid; grid-template-columns: repeat(17, minmax(0, 1fr)); gap: 2px; margin-bottom: 12px;
    user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent;
  }
  .automatik-stunde {
    text-align: center; font: inherit; font-size: 11px; color: var(--hn-gedaempft); cursor: pointer;
    border-radius: 10px; padding: 6px 0 5px; background: none; border: 1px solid transparent;
  }
  .automatik-stunde:hover { background: var(--hn-flaeche); }
  .automatik-stunde:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .automatik-stunde.gezeigt { background: var(--hn-flaeche); border-color: var(--hn-linie); }
  .automatik-stunde.plan .sym, .automatik-stunde.plan .t, .automatik-stunde.plan .raum { opacity: 0.55; }
  .automatik-stunde.plan .streifen { opacity: 0.45; }
  .automatik-stunde .sym { font-size: 15px; line-height: 1.4; color: var(--hn-gedaempft); }
  .automatik-stunde .sym.sonne { color: var(--hn-sonne); }
  .automatik-stunde .sym.mond { color: color-mix(in srgb, var(--hn-sonne) 70%, var(--hn-text)); }
  .automatik-stunde .sym.wolke { color: #9fb3c8; }
  .automatik-stunde .uhr { white-space: nowrap; }
  .automatik-stunde .t { font-size: 14px; font-weight: 700; color: var(--hn-text); }
  .automatik-stunde .t.kalt { color: var(--hn-text); }
  .automatik-stunde .t.warm { color: var(--hn-text); }
  .automatik-stunde .streifen {
    height: 3px; border-radius: 2px; margin: 6px 6px 5px;
    background: color-mix(in srgb, var(--hn-text) 30%, transparent);
  }
  .automatik-stunde .streifen.absenkung { background: var(--hn-sonne); }
  .automatik-stunde .streifen.heizpause { background: var(--hn-at); }
  .automatik-stunde .streifen.nur_ww { background: var(--hn-ww); }
  .automatik-stunde .raum { font-size: 11px; color: var(--hn-gedaempft); font-variant-numeric: tabular-nums; }
  .automatik-stundenkasten {
    margin: 0 0 14px; padding: 10px 14px; border-radius: 10px;
    background: var(--hn-flaeche); font-size: 13px; line-height: 1.5;
  }
  .automatik-stundenwerte { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 20px; }
  .automatik-stundenwerte .kopf { font-weight: 700; }
  .automatik-stundenwerte .modus { font-weight: 600; }
  .automatik-stundenwerte .modus.m-absenkung { color: var(--hn-sonne); }
  .automatik-stundenwerte .modus.m-heizpause { color: var(--hn-at); }
  .automatik-stundenwerte .modus.m-nur_ww { color: var(--hn-ww); }
  .automatik-stundenwerte .vorrang { color: var(--hn-sonne); }
  .automatik-verlaufkopf .korrektur {
    display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px 8px;
    font-size: 12px; color: var(--hn-gedaempft);
  }
  .automatik-schalter.klein { font-size: 12px; font-weight: 500; gap: 8px; }
  .automatik-schalter.klein i { width: 32px; height: 18px; border-radius: 6px; }
  .automatik-schalter.klein i::after { top: 2px; left: 2px; width: 12px; height: 12px; border-radius: 4px; }
  .automatik-schalter.klein i::before { top: 4px; left: 21px; width: 3px; height: 6px; }
  .automatik-schalter.klein.an i::after { transform: translateX(14px); }
  .automatik-korrekturmarke {
    padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap;
    background: var(--hn-flaeche); color: var(--hn-gedaempft); opacity: 0.75;
  }
  .automatik-korrekturmarke.wirkt {
    opacity: 1; background: color-mix(in srgb, var(--hn-akzent) 16%, transparent); color: var(--hn-akzent);
  }
  .automatik-stundenkasten .protokoll { font-size: 12px; color: var(--hn-gedaempft); margin-top: 2px; }
  .automatik-tag-bild {
    position: relative; touch-action: pan-y; cursor: crosshair;
    user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent;
  }
  .automatik-tag-bild svg { display: block; width: 100%; height: 190px; }
  .automatik-bildmarke {
    position: absolute; transform: translateY(-110%); font-size: 11px; line-height: 1;
    color: var(--hn-gedaempft); pointer-events: none;
  }
  .automatik-bildmarke.achse { left: 4px; }
  .automatik-bildmarke.grenze { right: 4px; }
  .automatik-zeiger {
    position: absolute; top: 0; bottom: 0; width: 0; pointer-events: none;
    border-left: 1px solid var(--hn-text); opacity: 0.6;
  }
  .automatik-tipp {
    position: absolute; top: 4px; pointer-events: none; z-index: 2;
    background: var(--hn-karte); border: 1px solid var(--hn-linie); border-radius: 8px;
    padding: 6px 9px; font-size: 12px; line-height: 1.45; white-space: nowrap;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
  }
  .automatik-tipp > div:first-child { font-weight: 700; }
  .automatik-tag .al-sonne {
    fill: color-mix(in srgb, var(--hn-sonne) 22%, transparent);
    stroke: color-mix(in srgb, var(--hn-sonne) 55%, transparent); stroke-width: 1; vector-effect: non-scaling-stroke;
  }
  .automatik-tag .al-grund { fill: var(--hn-flaeche); }
  .automatik-tag .al-m-programm { fill: color-mix(in srgb, var(--hn-text) 28%, transparent); }
  .automatik-tag .al-m-absenkung, .automatik-tag .al-absenkung { fill: var(--hn-sonne); }
  .automatik-tag .al-m-heizpause { fill: var(--hn-at); }
  .automatik-tag .al-m-nur_ww { fill: var(--hn-ww); }
  .automatik-tag .al-plan, .automatik-tag .al-verlaengerung { opacity: 0.45; }
  .automatik-tag .al-verlaengerung { fill: var(--hn-sonne); }
  .automatik-tag .al-jetzt {
    stroke: var(--hn-text); stroke-width: 1; stroke-dasharray: 3 3; vector-effect: non-scaling-stroke; opacity: 0.7;
  }
  .automatik-tag .al-aussen { fill: none; stroke: #ffab6f; stroke-width: 2; vector-effect: non-scaling-stroke; }
  .automatik-tag .al-prognose {
    fill: none; stroke: #ffab6f; stroke-width: 2; stroke-dasharray: 3 4; vector-effect: non-scaling-stroke;
  }
  .automatik-tag .al-gedaempft { fill: none; stroke: var(--hn-at); stroke-width: 2; vector-effect: non-scaling-stroke; }
  .automatik-tag .al-vorhersage {
    fill: none; stroke: var(--hn-akzent); stroke-width: 2; stroke-dasharray: 4 3; vector-effect: non-scaling-stroke;
  }
  .automatik-tag .al-grenze { stroke: var(--hn-gedaempft); stroke-dasharray: 6 5; vector-effect: non-scaling-stroke; }
  .automatik-achse { display: flex; justify-content: space-between; font-size: 11px; color: var(--hn-gedaempft); margin-top: 6px; }
  .automatik-legende { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12px; color: var(--hn-gedaempft); margin-top: 12px; }
  /* Farbmarke und Text je Eintrag auf einer Mittellinie, auch für die dünnen Linien. */
  .automatik-legende > span { display: inline-flex; align-items: center; }
  .automatik-legende i { display: inline-block; width: 14px; height: 10px; border-radius: 3px; margin-right: 6px; flex-shrink: 0; }
  .automatik-legende i.al-aussen { background: #ffab6f; height: 2px; }
  .automatik-legende i.al-prognose { height: 2px; background: repeating-linear-gradient(90deg, #ffab6f 0 3px, transparent 3px 6px); }
  .automatik-legende i.al-gedaempft { background: var(--hn-at); height: 2px; }
  .automatik-legende i.al-vorhersage { height: 2px; background: repeating-linear-gradient(90deg, var(--hn-akzent) 0 4px, transparent 4px 7px); }
  .automatik-legende i.al-grenze { height: 2px; background: repeating-linear-gradient(90deg, var(--hn-gedaempft) 0 4px, transparent 4px 7px); }
  .automatik-legende i.al-sonne { background: color-mix(in srgb, var(--hn-sonne) 45%, transparent); }

  /* Einstellungen */
  .karte.automatik-erweitert { padding: 0; }
  .automatik-einstellungskopf {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 16px 20px;
    cursor: pointer; list-style: none;
  }
  .automatik-einstellungskopf::-webkit-details-marker { display: none; }
  .automatik-einstellungskopf .pfeil { --mdc-icon-size: 20px; opacity: 0.6; transform: rotate(-90deg); transition: transform 0.15s; }
  .automatik-erweitert[open] .automatik-einstellungskopf .pfeil { transform: none; }
  .automatik-einstellungskopf .titelblock { flex: 1; min-width: 180px; }
  .automatik-einstellungskopf .unter { font-size: 12px; color: var(--hn-gedaempft); margin-top: 2px; }
  .karte.automatik-erweitert { position: relative; }
  /* Die Tasten stehen nach dem summary und sitzen optisch in dessen Zeile; zugeklappt sind sie verborgen. */
  .automatik-einstellungstasten {
    display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
    position: absolute; top: 14px; right: 20px;
  }
  .automatik-erweitert[open] > .automatik-einstellungskopf { padding-right: 380px; }
  .automatik-erweitert:not([open]) .automatik-einstellungstasten { display: none; }
  .automatik-gruppen {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding: 0 20px 4px;
  }
  .automatik-einstellungsgruppe {
    border: 1px solid var(--hn-linie); border-radius: 12px; padding: 4px 16px 6px; min-width: 0;
  }
  .automatik-einstellungsgruppe h4 {
    margin: 10px 0 4px; font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--hn-gedaempft);
  }
  .automatik-feld {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 9px 0; border-top: 1px solid var(--hn-flaeche); min-height: 48px;
  }
  .automatik-einstellungsgruppe h4 + .automatik-feld { border-top: none; }
  .automatik-feldtext { min-width: 0; }
  .automatik-feldtitel {
    padding: 0; border: none; background: none; color: inherit; font: inherit; font-size: 14px; text-align: left;
  }
  button.automatik-feldtitel { cursor: help; }
  button.automatik-feldtitel:hover { text-decoration: underline dotted; text-underline-offset: 3px; }
  button.automatik-feldtitel:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 2px; border-radius: 4px; }
  .automatik-feld.geaendert .automatik-feldtitel::after {
    content: ""; display: inline-block; width: 6px; height: 6px; margin-left: 8px; border-radius: 50%;
    background: var(--hn-akzent); vertical-align: middle;
  }
  .automatik-feld .profilwert { font-size: 11px; color: var(--hn-gedaempft); margin-top: 2px; }
  .automatik-feld .eingabe { display: flex; align-items: center; gap: 8px; flex: none; }
  .automatik-feld input, .automatik-feld select {
    padding: 6px 10px; border-radius: 8px; font: inherit; font-size: 14px;
    background: var(--hn-grund); color: inherit; border: 1px solid var(--hn-linie);
  }
  .automatik-feld input { width: 72px; text-align: right; font-variant-numeric: tabular-nums; }
  .automatik-feld input[type="time"] { width: 96px; }
  .automatik-feld select { min-width: 100px; }
  .automatik-feld.breit select { min-width: 200px; }
  .automatik-feld.geaendert input, .automatik-feld.geaendert select { border-color: color-mix(in srgb, var(--hn-akzent) 55%, transparent); }
  .automatik-feld input:focus-visible, .automatik-feld select:focus-visible { outline: 2px solid var(--hn-akzent); outline-offset: 1px; }
  .automatik-feld .einheit { width: 28px; font-size: 12px; color: var(--hn-gedaempft); }
  .automatik-leiste { display: flex; gap: 8px; margin: 0; padding: 16px 20px; flex-wrap: wrap; }

  /* Protokoll */
  .automatik-protokollkarte { padding: 18px 20px; }
  .automatik-protokollkarte > .kartenkopf { margin-bottom: 0; }
  .automatik-verweis {
    padding: 0; border: none; background: none; cursor: pointer;
    font: inherit; font-size: 13px; color: var(--hn-akzent);
  }
  .automatik-verweis:hover { text-decoration: underline; }
  .automatik-protokolltag {
    margin: 16px 0 2px; padding-bottom: 6px; border-bottom: 1px solid var(--hn-linie);
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--hn-gedaempft);
  }
  .automatik-protokoll { list-style: none; margin: 0; padding: 0; }
  .automatik-protokoll li {
    display: grid; grid-template-columns: 48px 1fr; gap: 12px; align-items: baseline;
    padding: 10px 0; border-bottom: 1px solid var(--hn-flaeche); font-size: 13px; line-height: 1.45;
  }
  .automatik-protokoll li:last-child { border-bottom: none; }
  .automatik-protokoll .zeit {
    color: var(--hn-gedaempft); font-variant-numeric: tabular-nums;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px;
  }
  .automatik-protokoll .inhalt { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
  .automatik-protokoll .art { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
  .automatik-protokoll .art.geschrieben { background: color-mix(in srgb, var(--hn-gut) 16%, transparent); color: var(--hn-gut); }
  .automatik-protokoll .art.haette, .automatik-protokoll .art.empfohlen, .automatik-protokoll .art.verworfen { border: 1px dashed rgba(245, 196, 81, 0.6); color: var(--hn-sonne); }
  .automatik-protokoll .art.abgelehnt { background: rgba(229, 57, 53, 0.15); color: #ff8a80; }
  .automatik-protokoll .art.budget, .automatik-protokoll .art.eingriff { background: rgba(255, 171, 111, 0.15); color: #ffab6f; }
  .automatik-protokoll .art.geprueft, .automatik-protokoll .art.einstellung { background: var(--hn-flaeche); color: var(--hn-gedaempft); }
  .automatik-protokoll .art.schreibt { background: color-mix(in srgb, var(--hn-gut) 16%, transparent); color: var(--hn-gut); }
  .automatik-protokoll .art.zaehlt, .automatik-protokoll .art.haelt, .automatik-protokoll .art.bleibt { background: var(--hn-flaeche); color: var(--hn-gedaempft); }
  .automatik-kern { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-top: 6px; }
  .automatik-kern .anstehend { font-size: 12px; font-weight: 600; margin-right: 4px; }
  .bewertung { font-size: 11px; padding: 1px 7px; border-radius: 999px; background: var(--hn-flaeche); color: var(--hn-gedaempft); white-space: nowrap; }
  .bewertung.nein { color: #ff8a80; }
  .bewertung.kern { outline: 1px solid var(--hn-linie); color: inherit; }

  /* Einladung */
  .automatik-einladungskarte { border-style: dashed; padding: 18px 20px; }
  .automatik-einladungskarte > .kartenkopf { margin-bottom: 0; }
  .automatik-stand { margin-left: auto; font-size: 12px; color: var(--hn-gedaempft); white-space: nowrap; }
  .automatik-einladung { font-size: 13px; line-height: 1.55; color: var(--hn-gedaempft); margin: 10px 0 14px; }
  .karte > .automatik-knopf { align-self: flex-start; }

  /* Einrichtungsdialog */
  .automatik-beschriftet { margin-top: 8px; }
  .automatik-unter { font-size: 12px; color: var(--hn-gedaempft); margin-bottom: 4px; }
  .automatik-haken-zeile.veraltet { color: #ffab6f; }
  .automatik-dialog {
    max-width: 560px; max-height: 86vh; padding: 0; overflow: hidden;
    display: flex; flex-direction: column;
  }
  .automatik-dialog .dialog-kopf {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 14px 14px 12px 24px; border-bottom: 1px solid var(--hn-linie);
  }
  .automatik-dialog .dialog-titel { margin: 0; }
  .automatik-dialog-inhalt { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 4px 24px 18px; }
  .automatik-dialog .dialog-leiste {
    margin-top: 0; padding: 14px 24px 18px; border-top: 1px solid var(--hn-linie);
  }
  .dialog-schliessen {
    flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%;
    border: none; background: transparent; color: inherit; opacity: 0.7;
    font-size: 24px; line-height: 1; cursor: pointer;
  }
  .dialog-schliessen:hover { background: var(--hn-flaeche); opacity: 1; }
  .dialog-schliessen:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
  .automatik-dialog section { margin-top: 14px; }
  .automatik-dialog h4 { margin: 0 0 6px; font-size: 13px; font-weight: 600; opacity: 0.7; }
  .automatik-dialog select { margin-top: 6px; }
  .automatik-haken {
    max-height: 160px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px;
  }
  .automatik-haken-zeile {
    display: flex; align-items: center; gap: 8px; font-size: 13px; flex-shrink: 0;
  }
  .automatik-beschriftet > .automatik-haken-zeile { margin-bottom: 6px; }
  @media (max-width: 900px) {
    .automatik-gruppen { grid-template-columns: minmax(0, 1fr); }
  }
  @media (max-width: 700px) {
    .automatik-stunden {
      grid-template-columns: repeat(17, minmax(52px, 1fr)); overflow-x: auto;
      scroll-snap-type: x proximity; scrollbar-width: thin; padding-bottom: 4px;
    }
    .automatik-stunde { scroll-snap-align: start; }
    .automatik-werte { grid-template-columns: minmax(0, 1fr); }
    .automatik-wert.breit { grid-column: auto; }
    .automatik-feld.breit select { min-width: 0; max-width: 55vw; }
    .automatik-gruppe + .automatik-gruppe, .automatik-schalter + .automatik-gruppe { padding-left: 0; border-left: none; }
    /* Das Segment nimmt die ganze Zeile unter dem Titel ein; lange Tasten brechen um, statt überzustehen. */
    .automatik-gruppe { flex: 1 1 100%; min-width: 0; flex-wrap: wrap; gap: 6px 10px; }
    .automatik-segment { flex: 1 1 100%; min-width: 0; flex-wrap: wrap; }
    .automatik-segment button { flex: 1 1 auto; padding: 6px 8px; white-space: nowrap; }
    .automatik-hinweis { flex-wrap: wrap; }
    .automatik-hinweis .text { flex: 1 1 100%; }
    .automatik-stundenlegende { margin-left: 0; }
    .automatik-einstellungstasten { position: static; padding: 0 20px 12px; }
    .automatik-erweitert[open] > .automatik-einstellungskopf { padding-right: 20px; }
  }
`;
