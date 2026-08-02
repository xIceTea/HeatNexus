/**
 * HeatNexus – eigene Oberfläche für die Heizung.
 *
 * Die Aufteilung kommt fertig aus der Integration (`panel.config.daten`);
 * hier wird sie nur dargestellt und mit den aktuellen Werten aus `hass`
 * gefüllt. Es gibt keine fest verdrahteten Entitäts-IDs.
 *
 * Bewusst ohne Framework und ohne Bauschritt: Die Datei wird so ausgeliefert,
 * wie sie hier steht.
 */

const OHNE_WERT = ["unavailable", "unknown", "none", ""];

// Wie lange „übertragen ✓" stehen bleibt, bevor wieder der Zustand erscheint.
const RUECKMELDUNG_MS = 4000;

// Wie lange auf die Bestätigung der Anlage gewartet wird, bevor die
// Rückmeldung aufgibt. Die Anlage wird nur alle 30 s abgefragt – drei
// Minuten reichen also für mehrere Versuche. Länger zu warten hilft nicht:
// Wird der Vorgang inzwischen an der Anlage selbst abgebrochen, bliebe
// „wird ausgeführt …" sonst minutenlang stehen, obwohl nichts mehr läuft.
const BESTAETIGUNG_MAX_MS = 3 * 60 * 1000;

const REITER = [
  { schluessel: "uebersicht", titel: "Übersicht", symbol: "mdi:view-dashboard-outline" },
  { schluessel: "steuerung", titel: "Steuerung", symbol: "mdi:tune-vertical" },
  { schluessel: "wartung", titel: "Wartung", symbol: "mdi:wrench-outline" },
  { schluessel: "verlauf", titel: "Verlauf", symbol: "mdi:chart-line" },
];

const STIL = `
  :host {
    display: block;
    background: var(--primary-background-color, #0e1419);
    color: var(--primary-text-color, #e6edf3);
    min-height: 100%;
    box-sizing: border-box;
  }
  * { box-sizing: border-box; }

  /* --- Kopfleiste: Menütaste, Marke, Anlagenwahl, Reiter --------------- */
  .kopfleiste {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px 0;
    flex-wrap: wrap;
  }
  .menue-taste {
    display: inline-flex;
    align-items: center; justify-content: center;
    width: 40px; height: 40px; flex: none;
    border-radius: 12px; cursor: pointer;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: inherit;
  }
  .menue-taste:hover { background: rgba(255, 255, 255, 0.1); }
  .kopfleiste .marke { font-size: 20px; font-weight: 700; }
  .kopfleiste .abstand { flex: 1; }
  .aussen {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 12px; border-radius: 999px; font-size: 14px; font-weight: 600;
    background: rgba(255, 255, 255, 0.05);
  }
  .aussen ha-icon { --mdc-icon-size: 18px; }
  .waehler { display: flex; gap: 6px; flex-wrap: wrap; }
  .waehler button {
    padding: 8px 14px; border-radius: 999px; font: inherit; font-size: 13px;
    font-weight: 600; cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .waehler button:hover { background: rgba(255, 255, 255, 0.1); }
  .waehler button[aria-selected="true"] {
    background: rgba(111, 178, 245, 0.18);
    border-color: rgba(111, 178, 245, 0.5);
    color: #6fb2f5;
  }
  .reiter { display: flex; gap: 4px; padding: 12px 16px 0; overflow-x: auto; }
  .reiter button {
    display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
    padding: 10px 16px; border: none; border-bottom: 2px solid transparent;
    background: none; color: inherit; font: inherit; font-size: 14px;
    font-weight: 600; cursor: pointer; opacity: 0.55;
  }
  .reiter button:hover { opacity: 0.85; }
  .reiter button[aria-selected="true"] {
    opacity: 1; color: #6fb2f5; border-bottom-color: #6fb2f5;
  }
  .anlagen-trenner {
    display: flex; align-items: center; gap: 12px;
    margin: 8px 16px 0; padding-top: 16px;
    font-size: 15px; font-weight: 700; letter-spacing: 0.3px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }
  .anlagen-trenner:first-of-type { border-top: none; padding-top: 4px; }

  /* --- Raster der Übersicht ------------------------------------------- */
  .rahmen {
    display: grid;
    gap: 16px;
    padding: 16px;
    grid-template-columns: minmax(280px, 340px) minmax(0, 1fr) minmax(280px, 340px);
    grid-template-areas:
      "seite schema status"
      "seite kreise status"
      "verlauf verlauf schnell";
    align-items: start;
    grid-auto-rows: min-content;
  }
  .rahmen > div { align-self: start; }
  @media (max-width: 1180px) {
    .rahmen {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: "seite" "schema" "kreise" "status" "verlauf" "schnell";
    }
  }
  .spalten {
    display: grid; gap: 16px; padding: 16px;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    align-items: start;
  }
  .karte {
    background: var(--card-background-color, #151d26);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 14px 16px;
  }
  .karte + .karte { margin-top: 16px; }
  .kartenkopf { display: flex; align-items: center; gap: 8px; }
  .kartenkopf h2 { flex: 1; }
  .fragezeichen {
    width: 22px; height: 22px; flex: none; border-radius: 50%;
    font: inherit; font-size: 13px; font-weight: 700; line-height: 1;
    cursor: pointer; color: #6fb2f5;
    background: rgba(111, 178, 245, 0.12);
    border: 1px solid rgba(111, 178, 245, 0.35);
  }
  .fragezeichen:hover {
    background: rgba(111, 178, 245, 0.28);
    border-color: rgba(111, 178, 245, 0.7);
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
  .kopf { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
  .kopf .marke { font-size: 24px; font-weight: 700; line-height: 1.15; }
  .kopf .unterzeile { font-size: 13px; opacity: 0.6; }
  .abzeichen {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 14px; border-radius: 999px; font-weight: 600; font-size: 14px;
    background: rgba(67, 160, 71, 0.15); color: #7bd88f;
  }
  .abzeichen.stoerung { background: rgba(229, 57, 53, 0.15); color: #ff8a80; }

  /* --- Zeilen ---------------------------------------------------------- */
  .zeile {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 12px; border-radius: 12px;
    background: rgba(255, 255, 255, 0.03);
  }
  .zeile + .zeile { margin-top: 6px; }
  .zeile .text { flex: 1; min-width: 0; }
  .zeile .titel { font-size: 14px; font-weight: 600; }
  .zeile .unter { font-size: 12px; opacity: 0.55; }
  /* Rechte Spalte einer Zeile: großer Wert, darunter die Bezeichnung. */
  .zeile .rechts { text-align: right; min-width: 0; }
  .zeile .wert {
    font-size: 20px; font-weight: 600; line-height: 1.2;
    overflow-wrap: anywhere;
  }
  .zeile .wert.lang { font-size: 15px; }
  .zeile .bezeichnung { font-size: 11px; opacity: 0.5; margin-top: 2px; }
  .betriebsart-klein { font-size: 12px; font-weight: 600; margin-top: 2px; }
  .betriebsart-klein.heizt { color: #ffab6f; }
  .betriebsart-klein.abgesenkt { color: #6fb2f5; }
  .kreis-symbole { display: flex; gap: 10px; margin-left: 12px; }
  .kreis-symbole ha-icon { --mdc-icon-size: 20px; opacity: 0.7; }
  .kreis-symbole ha-icon.heizt { color: #ffab6f; opacity: 1; }
  .kreis-symbole ha-icon.abgesenkt { color: #6fb2f5; opacity: 1; }
  .status-zeile {
    display: flex; align-items: center; gap: 12px; padding: 8px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }
  .status-zeile:last-child { border-bottom: none; }
  .status-zeile .titel {
    flex: 1; font-size: 14px; min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  /* Lange Werte (z.B. ein ganzes Zeitprogramm) sprengten die Karte über
     zwanzig Zeilen. Sie werden gekürzt; der volle Text steht im Tooltip und
     in der Detailansicht. */
  .status-zeile .wert {
    font-weight: 600; font-size: 14px; color: #6fb2f5;
    max-width: 60%; text-align: right;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .status-zeile .wert.zustand { color: #7bd88f; }
  .status-zeile .wert.warm { color: #ffab6f; }
  ha-icon { --mdc-icon-size: 22px; opacity: 0.85; flex: none; }

  /* --- Schaubild ------------------------------------------------------- */
  .schaubild { width: 100%; position: relative; }
  .schaubild img { width: 100%; display: block; border-radius: 12px; }
  .schaubild .pumpe {
    position: absolute; transform: translate(-50%, -50%);
    width: 30px; height: 30px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: rgba(10, 14, 19, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: rgba(255, 255, 255, 0.35);
  }
  .schaubild .pumpe ha-icon { --mdc-icon-size: 18px; opacity: 1; }
  .schaubild .pumpe.laeuft {
    color: #6fb2f5; border-color: rgba(111, 178, 245, 0.6);
    box-shadow: 0 0 10px rgba(111, 178, 245, 0.35);
  }
  .schaubild .pumpe.laeuft ha-icon { animation: dreht 1.6s linear infinite; }
  @keyframes dreht { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .pumpe.laeuft ha-icon { animation: none; }
  }
  .schaubild .marke-wert {
    position: absolute; transform: translate(-50%, -50%);
    background: rgba(10, 14, 19, 0.72); color: #fff;
    font-size: 15px; font-weight: 600; padding: 3px 9px;
    border-radius: 8px; white-space: nowrap;
  }

  .einzeln { display: block; }
  .linienwahl { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .linie {
    padding: 5px 10px; border-radius: 999px; font: inherit; font-size: 12px;
    font-weight: 600; cursor: pointer; color: inherit; opacity: 0.45;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .linie:hover { opacity: 0.8; }
  .linie[aria-pressed="true"] {
    opacity: 1; color: #6fb2f5;
    background: rgba(111, 178, 245, 0.15);
    border-color: rgba(111, 178, 245, 0.45);
  }
  /* Karten wachsen nur so hoch wie ihr Inhalt. Ohne das zieht die längste
     Karte einer Zeile alle anderen mit und die Seite wirkt zerklüftet. */
  .doppel {
    display: grid; gap: 16px; align-items: start;
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  }
  @media (max-width: 900px) { .doppel { grid-template-columns: minmax(0, 1fr); } }
  .gitter { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }

  /* --- Tasten ---------------------------------------------------------- */
  .taste {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 16px 10px; border-radius: 14px; cursor: pointer;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: inherit; font: inherit; text-align: center;
  }
  .taste:hover { background: rgba(255, 255, 255, 0.08); }
  .taste .beschriftung { font-size: 13px; font-weight: 600; }
  .taste.an { border-color: rgba(111, 178, 245, 0.5); color: #6fb2f5; }
  .taste.an .beschriftung { text-shadow: 0 0 12px rgba(111, 178, 245, 0.6); }
  .taste[disabled] { opacity: 0.6; cursor: progress; }
  select {
    width: 100%; padding: 9px 10px; border-radius: 10px;
    background: rgba(255, 255, 255, 0.05); color: inherit;
    border: 1px solid rgba(255, 255, 255, 0.1); font: inherit;
  }
  .rueckmeldung { font-size: 11px; opacity: 0.5; min-height: 14px; }
  .rueckmeldung.laeuft { opacity: 0.9; color: #6fb2f5; }
  .rueckmeldung.erfolg { opacity: 1; color: #7bd88f; }
  .rueckmeldung.fehler { opacity: 1; color: #ff8a80; }
  .rueckmeldung.wartet { opacity: 0.9; color: #ffab6f; }

  /* --- Steuerung ------------------------------------------------------- */
  .regler { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
  .regler button {
    width: 42px; height: 42px; border-radius: 12px; font: inherit;
    font-size: 20px; font-weight: 600; cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .regler button:hover { background: rgba(255, 255, 255, 0.1); }
  .regler .sollwert { flex: 1; text-align: center; }
  .regler .sollwert .zahl { font-size: 30px; font-weight: 700; line-height: 1.1; }
  .regler .sollwert .beschriftung { font-size: 11px; opacity: 0.5; }
  .betriebsart {
    font-size: 13px; font-weight: 600; color: #6fb2f5;
    margin-bottom: 4px; min-height: 16px;
  }
  .gross { display: flex; align-items: baseline; gap: 10px; }
  .gross .zahl { font-size: 32px; font-weight: 700; }
  .gross .beschriftung { font-size: 12px; opacity: 0.55; }
  .trenner { height: 1px; background: rgba(255, 255, 255, 0.07); margin: 14px 0; }
  .laufzeit {
    display: inline-flex; align-items: center; gap: 6px; margin-top: 10px;
    padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
    background: rgba(255, 171, 111, 0.15); color: #ffab6f;
  }
  .feld { margin-top: 12px; }
  .feld > .beschriftung { font-size: 11px; opacity: 0.5; margin-bottom: 6px; }

  /* --- Dialog ---------------------------------------------------------- */
  .schleier {
    position: fixed; inset: 0; z-index: 20;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, 0.55); padding: 16px;
  }
  .dialog {
    background: var(--card-background-color, #151d26);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px; padding: 22px 24px; max-width: 420px; width: 100%;
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
  }
  .dialog-titel { margin: 0 0 10px; font-size: 17px; font-weight: 600;
    text-transform: none; letter-spacing: 0; opacity: 1; }
  .dialog-text { font-size: 14px; line-height: 1.5; opacity: 0.8; }
  .dialog-leiste { display: flex; gap: 10px; justify-content: flex-end; margin-top: 22px; }
  .dialog-taste {
    padding: 9px 16px; border-radius: 10px; font: inherit; font-weight: 600;
    cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }
  .dialog-taste:hover { background: rgba(255, 255, 255, 0.12); }
  .dialog-taste.betont { background: rgba(229, 57, 53, 0.2); border-color: rgba(229, 57, 53, 0.5);
    color: #ff8a80; }

  .klickbar { cursor: pointer; }
  .klickbar:hover { background: rgba(255, 255, 255, 0.07); }
  .status-zeile.klickbar:hover { background: rgba(255, 255, 255, 0.05); border-radius: 8px; }
  .marke-wert.klickbar:hover { background: rgba(10, 14, 19, 0.92); }
  .klickbar:focus-visible { outline: 2px solid #6fb2f5; outline-offset: 2px; }
  .hinweis { opacity: 0.6; font-size: 14px; padding: 6px 0; }
  .gut { color: #7bd88f; }
  .schlecht { color: #ff8a80; }
  .mitte { text-align: center; padding: 18px 0; }
  .mitte ha-icon { --mdc-icon-size: 46px; opacity: 0.8; }
  .mitte .haupt { font-size: 16px; font-weight: 600; margin-top: 10px; }
  .mitte .neben { font-size: 13px; opacity: 0.6; margin-top: 4px; }
`;

class HeatNexusPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._gebaut = false;
    this._daten = null;
    this._bindungen = [];
    this._verlaufskarten = [];
    this._anlageIndex = 0;
    this._reiter = "uebersicht";
    // Laufende Bedienvorgänge: Anzeige -> wann begonnen, wann bestätigt.
    this._wartend = [];
  }

  set panel(panel) {
    const daten = panel && panel.config ? panel.config.daten : null;
    if (daten !== this._daten) {
      this._daten = daten;
      this._gebaut = false;
    }
    this._zeichnen();
  }

  set hass(hass) {
    const erster = !this._hass;
    this._hass = hass;
    // Die Aufteilung aus `panel.config` stammt aus dem Augenblick der
    // Einrichtung – da war die Anlage erst zur Hälfte eingelesen. Deshalb
    // wird sie beim Öffnen einmal frisch geholt.
    if (erster) this._datenHolen();
    this._zeichnen();
  }

  async _datenHolen() {
    try {
      const daten = await this._hass.callWS({ type: "heatnexus/panel_daten" });
      if (!daten || !daten.anlagen || !daten.anlagen.length) return;
      this._daten = daten;
      this._gebaut = false;
      this._zeichnen();
    } catch (err) {
      // Ohne frische Daten bleibt der Stand aus der Panel-Konfiguration.
      console.warn("HeatNexus: Aufteilung konnte nicht geladen werden", err);
    }
  }

  set narrow(_narrow) {
    /* Die Aufteilung regelt CSS. */
  }

  // -------------------------------------------------------------------
  // Werte
  // -------------------------------------------------------------------
  _zustand(entity) {
    return this._hass && this._hass.states ? this._hass.states[entity] : undefined;
  }

  _hatWert(entity) {
    const zustand = this._zustand(entity);
    return !!zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase());
  }

  _text(entity) {
    const zustand = this._zustand(entity);
    if (!this._hatWert(entity)) return "–";
    if (this._hass.formatEntityState) return this._hass.formatEntityState(zustand);
    const einheit = zustand.attributes.unit_of_measurement;
    return einheit ? `${zustand.state} ${einheit}` : zustand.state;
  }

  _zahl(entity) {
    const zustand = this._zustand(entity);
    if (!this._hatWert(entity)) return null;
    const wert = Number.parseFloat(zustand.state);
    return Number.isNaN(wert) ? null : wert;
  }

  _name(entity) {
    const zustand = this._zustand(entity);
    return (zustand && zustand.attributes.friendly_name) || entity;
  }

  /**
   * Ein Element zur Entität führen: Klick öffnet die Detailansicht.
   *
   * `hass-more-info` ist das Ereignis, das auch die Lovelace-Karten benutzen.
   * Es muss den Schattenbaum verlassen, sonst hört Home Assistant es nicht –
   * daher `composed`.
   */
  _klickbar(element, entity) {
    if (!entity) return element;
    element.classList.add("klickbar");
    element.setAttribute("role", "button");
    element.setAttribute("tabindex", "0");
    const oeffnen = () => {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId: entity },
          bubbles: true,
          composed: true,
        })
      );
    };
    element.addEventListener("click", oeffnen);
    element.addEventListener("keydown", (ereignis) => {
      if (ereignis.key === "Enter" || ereignis.key === " ") {
        ereignis.preventDefault();
        oeffnen();
      }
    });
    return element;
  }

  _stoerung(anlage) {
    return (anlage.stoerungen || []).some((s) => {
      const zustand = this._zustand(s.entity);
      return zustand && zustand.attributes.stoerung_aktiv === true;
    });
  }

  // -------------------------------------------------------------------
  // Aufbau
  // -------------------------------------------------------------------
  _zeichnen() {
    if (!this._hass || !this._daten) return;
    if (!this._gebaut) {
      this._aufbauen();
      this._gebaut = true;
    }
    this._aktualisieren();
  }

  _anlagen() {
    return (this._daten && this._daten.anlagen) || [];
  }

  _alleAnlagen() {
    return this._anlageIndex < 0 && this._anlagen().length > 1;
  }

  _aktuelleAnlage() {
    const anlagen = this._anlagen();
    if (this._anlageIndex < 0) return anlagen[0];
    return anlagen[Math.min(this._anlageIndex, anlagen.length - 1)];
  }

  _aufbauen() {
    this._bindungen = [];
    this._verlaufskarten = [];
    this._wartend = [];
    const anlage = this._aktuelleAnlage();
    const stil = document.createElement("style");
    stil.textContent = STIL;
    if (!anlage) {
      this.shadowRoot.replaceChildren(stil);
      return;
    }

    const inhalt = document.createElement("div");
    inhalt.append(this._kopfleiste(anlage), this._reiterleiste());
    if (this._alleAnlagen()) {
      this._anlagen().forEach((eintrag) => {
        const ueberschrift = document.createElement("div");
        ueberschrift.className = "anlagen-trenner";
        ueberschrift.textContent = eintrag.name || "Anlage";
        inhalt.append(ueberschrift, this._inhalt(eintrag));
      });
    } else {
      inhalt.appendChild(this._inhalt(anlage));
    }
    this.shadowRoot.replaceChildren(stil, inhalt);
    this._verlaufKarteLaden();
  }

  /** Kopfleiste mit Menütaste, Marke und Anlagenwahl. */
  _kopfleiste(anlage) {
    const leiste = document.createElement("div");
    leiste.className = "kopfleiste";

    // Auf schmalen Bildschirmen verdeckt das Panel die Seitenleiste; über
    // diese Taste kommt sie zurück. Das Ereignis ist dasselbe, das die
    // eigenen Ansichten von Home Assistant benutzen – es muss den
    // Schattenbaum verlassen, daher `composed`.
    const menue = document.createElement("button");
    menue.className = "menue-taste";
    menue.type = "button";
    menue.title = "Seitenleiste anzeigen (Karten, Energie, Einstellungen)";
    menue.setAttribute("aria-label", "Seitenleiste anzeigen");
    // Das eigene Symbol statt eines Hamburgers: Es ist zugleich der Weg
    // zurueck in die uebrigen Ansichten von Home Assistant - auf dem Handy
    // sonst nur ueber eine Wischgeste erreichbar.
    menue.appendChild(this._symbolKnoten("mdi:radiator"));
    menue.addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    });
    leiste.appendChild(menue);

    const marke = document.createElement("div");
    marke.className = "marke";
    marke.textContent = "HeatNexus";
    leiste.appendChild(marke);

    const abstand = document.createElement("div");
    abstand.className = "abstand";
    leiste.appendChild(abstand);

    // Die Außentemperatur gilt für die ganze Anlage – an der Anlage selbst
    // steht sie deshalb in der Kopfzeile und nicht bei einem Anlagenteil.
    if (anlage.aussentemperatur) {
      const aussen = document.createElement("div");
      aussen.className = "aussen";
      aussen.appendChild(this._symbolKnoten("mdi:thermometer"));
      const wert = document.createElement("span");
      aussen.appendChild(wert);
      leiste.appendChild(this._klickbar(aussen, anlage.aussentemperatur));
      this._bindungen.push(() => {
        wert.textContent = this._text(anlage.aussentemperatur);
      });
    }

    const anlagen = this._anlagen();
    if (anlagen.length > 1) {
      const waehler = document.createElement("div");
      waehler.className = "waehler";
      waehler.setAttribute("role", "tablist");
      // "Alle" stellt die Anlagen untereinander - mit Ueberschrift je Anlage,
      // damit man beim Scrollen sieht, wo die naechste anfaengt.
      const eintraege = [{ name: "Alle", index: -1 }].concat(
        anlagen.map((a, index) => ({ name: a.name || `Anlage ${index + 1}`, index }))
      );
      eintraege.forEach(({ name, index }) => {
        const taste = document.createElement("button");
        taste.type = "button";
        taste.setAttribute("role", "tab");
        taste.setAttribute("aria-selected", String(index === this._anlageIndex));
        taste.textContent = name;
        taste.addEventListener("click", () => {
          this._anlageIndex = index;
          this._gebaut = false;
          this._zeichnen();
        });
        waehler.appendChild(taste);
      });
      leiste.appendChild(waehler);
    }
    return leiste;
  }

  _reiterleiste() {
    const leiste = document.createElement("div");
    leiste.className = "reiter";
    leiste.setAttribute("role", "tablist");
    REITER.forEach((reiter) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.setAttribute("role", "tab");
      taste.setAttribute("aria-selected", String(reiter.schluessel === this._reiter));
      taste.appendChild(this._symbolKnoten(reiter.symbol));
      const beschriftung = document.createElement("span");
      beschriftung.textContent = reiter.titel;
      taste.appendChild(beschriftung);
      taste.addEventListener("click", () => {
        this._reiter = reiter.schluessel;
        this._gebaut = false;
        this._zeichnen();
      });
      leiste.appendChild(taste);
    });
    return leiste;
  }

  _inhalt(anlage) {
    // Die Karten holen ihre Erklärung über den Titel.
    this._hilfe = anlage.hilfe || {};
    if (this._reiter === "steuerung") return this._steuerung(anlage);
    if (this._reiter === "wartung") return this._wartung(anlage);
    if (this._reiter === "verlauf") return this._verlaufReiter(anlage);
    return this._uebersicht(anlage);
  }

  // -------------------------------------------------------------------
  // Reiter „Übersicht"
  // -------------------------------------------------------------------
  _uebersicht(anlage) {
    const rahmen = document.createElement("div");
    rahmen.className = "rahmen";
    rahmen.append(
      this._bereich("seite", this._seite(anlage)),
      this._bereich("schema", this._schaubild(anlage)),
      this._bereich("kreise", this._kreiseUndWasser(anlage)),
      this._bereich("status", this._status(anlage)),
      this._bereich("verlauf", this._verlauf(anlage, 24)),
      this._bereich("schnell", this._schnellzugriff(anlage))
    );
    return rahmen;
  }

  _bereich(name, knoten) {
    const huelle = document.createElement("div");
    huelle.style.gridArea = name;
    huelle.style.minWidth = "0";
    if (knoten) huelle.appendChild(knoten);
    return huelle;
  }

  _karte(titel, hilfe) {
    const karte = document.createElement("div");
    karte.className = "karte";
    if (titel) {
      const kopf = document.createElement("div");
      kopf.className = "kartenkopf";
      const ueberschrift = document.createElement("h2");
      ueberschrift.textContent = titel;
      kopf.appendChild(ueberschrift);
      const text = hilfe || (this._hilfe && this._hilfe[titel]);
      if (text) kopf.appendChild(this._fragezeichen(titel, text));
      karte.appendChild(kopf);
    }
    return karte;
  }

  /**
   * Ein „?", das erklärt, was hier eigentlich passiert.
   *
   * Die Anlage bringt zu jeder Einstellung eine Erklärung mit – nur liegt die
   * Anleitung beim Heizen selten daneben. Der Text kommt aus der Integration;
   * abschalten lässt er sich in den Optionen.
   */
  _fragezeichen(titel, text) {
    const taste = document.createElement("button");
    taste.type = "button";
    taste.className = "fragezeichen";
    taste.textContent = "?";
    taste.title = "Erklärung";
    taste.setAttribute("aria-label", `Erklärung zu ${titel}`);
    taste.addEventListener("click", (ereignis) => {
      ereignis.stopPropagation();
      this._erklaeren(titel, text);
    });
    return taste;
  }

  /** Erklärung als Hinweisfenster – bewusst dieselbe Form wie die Rückfrage. */
  _erklaeren(titel, text) {
    const schleier = document.createElement("div");
    schleier.className = "schleier";
    const dialog = document.createElement("div");
    dialog.className = "dialog";
    dialog.setAttribute("role", "dialog");

    const ueberschrift = document.createElement("h3");
    ueberschrift.className = "dialog-titel";
    ueberschrift.textContent = titel;
    const inhalt = document.createElement("div");
    inhalt.className = "dialog-text";
    inhalt.textContent = text;

    const leiste = document.createElement("div");
    leiste.className = "dialog-leiste";
    const schliessen = document.createElement("button");
    schliessen.type = "button";
    schliessen.className = "dialog-taste";
    schliessen.textContent = "Verstanden";
    leiste.appendChild(schliessen);

    dialog.append(ueberschrift, inhalt, leiste);
    schleier.appendChild(dialog);
    const weg = () => {
      schleier.remove();
      document.removeEventListener("keydown", beiTaste);
    };
    const beiTaste = (ereignis) => {
      if (ereignis.key === "Escape") weg();
    };
    schliessen.addEventListener("click", weg);
    schleier.addEventListener("click", (e) => {
      if (e.target === schleier) weg();
    });
    document.addEventListener("keydown", beiTaste);
    this.shadowRoot.appendChild(schleier);
    schliessen.focus();
  }

  _symbolKnoten(symbol) {
    const ikone = document.createElement("ha-icon");
    ikone.setAttribute("icon", symbol);
    return ikone;
  }

  _hinweisKnoten(text) {
    const hinweis = document.createElement("div");
    hinweis.className = "hinweis";
    hinweis.textContent = text;
    return hinweis;
  }

  // -------------------------------------------------------------------
  // Linke Spalte: Marke, Zustand, Kennwerte
  // -------------------------------------------------------------------
  _seite(anlage) {
    const karte = this._karte(null);

    const kopf = document.createElement("div");
    kopf.className = "kopf";
    kopf.appendChild(this._symbolKnoten("mdi:radiator"));
    const beschriftung = document.createElement("div");
    beschriftung.innerHTML =
      '<div class="marke">HeatNexus</div><div class="unterzeile"></div>';
    beschriftung.querySelector(".unterzeile").textContent = anlage.name
      ? `Heizungsübersicht · ${anlage.name}`
      : "Heizungsübersicht";
    kopf.appendChild(beschriftung);
    karte.appendChild(kopf);

    const abzeichen = document.createElement("div");
    abzeichen.className = "abzeichen";
    abzeichen.appendChild(this._symbolKnoten("mdi:check-circle-outline"));
    const abzeichenText = document.createElement("span");
    abzeichen.appendChild(abzeichenText);
    karte.appendChild(abzeichen);
    this._bindungen.push(() => {
      const stoerung = this._stoerung(anlage);
      abzeichen.classList.toggle("stoerung", stoerung);
      abzeichenText.textContent = stoerung ? "Störung anliegend" : "Anlage in Ordnung";
      abzeichen.firstChild.setAttribute(
        "icon",
        stoerung ? "mdi:alert-circle-outline" : "mdi:check-circle-outline"
      );
    });

    const liste = document.createElement("div");
    liste.style.marginTop = "16px";
    (anlage.kennwerte || []).forEach((kennwert) => {
      liste.appendChild(
        this._wertzeile(kennwert.entity, kennwert.titel, kennwert.untertitel, kennwert.symbol)
      );
    });
    karte.appendChild(liste);
    return karte;
  }

  /**
   * Kennwertzeile wie im Muster: links Anlagenteil, rechts der große Wert und
   * darunter klein, worum es sich handelt („Kesseltemperatur").
   */
  _wertzeile(entity, titel, bezeichnung, symbol) {
    const zeile = document.createElement("div");
    zeile.className = "zeile";
    if (symbol) zeile.appendChild(this._symbolKnoten(symbol));
    const text = document.createElement("div");
    text.className = "text";
    const oben = document.createElement("div");
    oben.className = "titel";
    oben.textContent = titel;
    text.appendChild(oben);

    const rechts = document.createElement("div");
    rechts.className = "rechts";
    const wert = document.createElement("div");
    wert.className = "wert";
    const unten = document.createElement("div");
    unten.className = "bezeichnung";
    unten.textContent = bezeichnung || "";
    rechts.append(wert, unten);

    zeile.append(text, rechts);
    this._bindungen.push(() => {
      wert.textContent = this._text(entity);
      // Lange Texte („Betriebsbereit") umbrechen statt zu schrumpfen.
      wert.classList.toggle("lang", wert.textContent.length > 8);
    });
    return this._klickbar(zeile, entity);
  }

  // -------------------------------------------------------------------
  // Schaubild
  // -------------------------------------------------------------------
  _schaubild(anlage) {
    if (!anlage.schema) return null;
    const karte = this._karte("Anlagenübersicht");
    const huelle = document.createElement("div");
    huelle.className = "schaubild";
    const bild = document.createElement("img");
    bild.src = anlage.schema;
    bild.alt = "Anlagenschaubild";
    huelle.appendChild(bild);

    (anlage.schema_werte || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "marke-wert";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      huelle.appendChild(this._klickbar(marke, eintrag.entity));
      this._bindungen.push(() => {
        marke.textContent = this._text(eintrag.entity);
      });
    });

    // Pumpen liegen als eigene Marken auf dem Bild: Ein Standbild kann sich
    // nicht drehen, und ohne Bewegung sieht man der Anlage nicht an, ob
    // gerade etwas fließt.
    (anlage.schema_pumpen || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "pumpe";
      marke.title = `${eintrag.titel} – Pumpe`;
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      const ikone = this._symbolKnoten("mdi:fan");
      marke.appendChild(ikone);
      huelle.appendChild(this._klickbar(marke, eintrag.entity));
      this._bindungen.push(() => {
        // Manche Pumpen melden keinen Zustand, sondern ihre Drehzahl.
        const zahl = this._zahl(eintrag.entity);
        const laeuft = zahl !== null ? zahl > 0 : this._istAn(eintrag.entity);
        marke.classList.toggle("laeuft", laeuft);
        marke.title = `${eintrag.titel} – Pumpe ${laeuft ? "läuft" : "steht"}`;
      });
    });

    karte.appendChild(huelle);
    return karte;
  }

  // -------------------------------------------------------------------
  // Heizkreise und Warmwasser
  // -------------------------------------------------------------------
  _kreiseUndWasser(anlage) {
    const kreise = anlage.heizkreise || [];
    const wasser = anlage.warmwasser || [];
    if (!kreise.length && !wasser.length) return null;

    const doppel = document.createElement("div");
    // Ohne Warmwasser bleibt sonst eine leere Spalte stehen und der Heizkreis
    // steht verloren in der Mitte.
    doppel.className = wasser.length ? "doppel" : "einzeln";

    // Was es nicht gibt, bekommt auch keine Karte – so hält es die Anlage
    // selbst: Was keinen Wert liefert, wird ausgeblendet.
    if (kreise.length) {
      const linkeKarte = this._karte("Heizkreise");
      kreise.forEach((kreis) => linkeKarte.appendChild(this._heizkreiszeile(kreis)));
      doppel.appendChild(linkeKarte);
    }
    // Eine Anlage ohne Warmwasserbereitung bekommt gar keine Karte – eine
    // leere Karte behauptet, da fehle etwas.
    if (wasser.length) {
      const rechteKarte = this._karte("Warmwasser");
      wasser.forEach((eintrag) => {
        rechteKarte.appendChild(this._statuszeile(eintrag.entity, eintrag.titel));
      });
      doppel.appendChild(rechteKarte);
    }
    return doppel;
  }

  /**
   * Eine Heizkreiszeile nach dem Vorbild der Anlage.
   *
   * Links Symbol, Name und die Betriebsart farbig darunter; rechts der große
   * Ist-Wert mit dem Sollwert klein daneben, dahinter zwei Symbole: die
   * Betriebsart (Sonne, Mond, Standby …) und das Zeitprogramm.
   */
  _heizkreiszeile(kreis) {
    const zeile = document.createElement("div");
    zeile.className = "zeile kreis";
    zeile.appendChild(this._symbolKnoten("mdi:home-outline"));

    const text = document.createElement("div");
    text.className = "text";
    const oben = document.createElement("div");
    oben.className = "titel";
    oben.textContent = kreis.titel;
    const unten = document.createElement("div");
    unten.className = "betriebsart-klein";
    text.append(oben, unten);

    const rechts = document.createElement("div");
    rechts.className = "rechts";
    const wert = document.createElement("div");
    wert.className = "wert";
    const sollzeile = document.createElement("div");
    sollzeile.className = "bezeichnung";
    rechts.append(wert, sollzeile);

    const symbole = document.createElement("div");
    symbole.className = "kreis-symbole";
    const artSymbol = this._symbolKnoten("mdi:white-balance-sunny");
    const uhr = this._symbolKnoten("mdi:clock-outline");
    symbole.append(artSymbol, uhr);

    zeile.append(text, rechts, symbole);
    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      if (!zustand) {
        wert.textContent = "–";
        return;
      }
      const ist = zustand.attributes.current_temperature;
      const soll = zustand.attributes.temperature;
      wert.textContent = ist !== undefined && ist !== null ? `${ist} °C` : "–";
      sollzeile.textContent =
        soll !== undefined && soll !== null ? `${soll} °C` : "Raumtemperatur";

      const art = zustand.attributes.preset_mode ? this._presetName(zustand) : "";
      const rest = this._restzeit(zustand);
      unten.textContent = rest ? `${art} · ${rest}` : art;
      // Farbe wie im Muster: Heizen warm, Absenken kühl.
      const heizt = zustand.state === "heat" || zustand.attributes.hvac_action === "heating";
      unten.className = `betriebsart-klein ${heizt ? "heizt" : "abgesenkt"}`;
      artSymbol.setAttribute("icon", heizt ? "mdi:white-balance-sunny" : "mdi:weather-night");
      artSymbol.className = heizt ? "heizt" : "abgesenkt";
      uhr.style.display = kreis.programm ? "" : "none";
    });
    return this._klickbar(zeile, kreis.entity);
  }

  _presetName(zustand) {
    // Die Betriebsarten heißen am Gerät "0".."7"; die Klartexte liefert die
    // Übersetzung der Integration mit.
    if (this._hass.formatEntityAttributeValue) {
      return this._hass.formatEntityAttributeValue(zustand, "preset_mode");
    }
    return zustand.attributes.preset_mode;
  }

  /**
   * Text zur laufenden Sollwert-Vorgabe.
   *
   * Ein am Thermostat gesetzter Wert gilt befristet; die Anlage meldet die
   * Restzeit in Minuten (2/10). Ohne diese Anzeige sieht man dem Heizkreis
   * nicht an, dass gerade eine Vorgabe läuft.
   */
  _restzeit(zustand) {
    if (!zustand || zustand.attributes.override_aktiv !== true) return "";
    const minuten = Number(zustand.attributes.override_restzeit_min) || 0;
    if (minuten <= 0) return "";
    const ende = new Date(Date.now() + minuten * 60000);
    const uhrzeit = ende.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return minuten >= 60
      ? `noch bis ${uhrzeit}`
      : `noch ${minuten} min (bis ${uhrzeit})`;
  }

  // -------------------------------------------------------------------
  // Systemstatus und Störungen
  // -------------------------------------------------------------------
  _statuszeile(entity, titel, symbol) {
    const zeile = document.createElement("div");
    zeile.className = "status-zeile";
    if (symbol) zeile.appendChild(this._symbolKnoten(symbol));
    const links = document.createElement("div");
    links.className = "titel";
    links.textContent = titel;
    const wert = document.createElement("div");
    wert.className = "wert";
    zeile.append(links, wert);
    this._bindungen.push(() => {
      const text = this._text(entity);
      wert.textContent = text;
      wert.title = text;
      // Farbe nach Art des Wertes: kurze Zustände grün, Leistungen orange,
      // Zahlen blau – so wie im Muster. Ein langer Text bleibt neutral, sonst
      // leuchtet die halbe Karte.
      const zustand = this._zustand(entity);
      const einheit = zustand && zustand.attributes.unit_of_measurement;
      wert.className = "wert";
      if (einheit === "%" || einheit === "kW") wert.classList.add("warm");
      else if (!einheit && this._hatWert(entity) && text.length <= 20) {
        wert.classList.add("zustand");
      }
    });
    return this._klickbar(zeile, entity);
  }

  _status(anlage) {
    const huelle = document.createElement("div");

    const karte = this._karte("Systemstatus");
    (anlage.status || []).forEach((eintrag) => {
      karte.appendChild(this._statuszeile(eintrag.entity, eintrag.titel, eintrag.symbol));
    });
    if (!(anlage.status || []).length) {
      karte.appendChild(this._hinweisKnoten("Keine Statuswerte gefunden."));
    }

    // Der grüne bzw. rote Kasten unter dem Status, wie im Muster.
    const kasten = document.createElement("div");
    kasten.className = "abzeichen";
    kasten.style.marginTop = "14px";
    kasten.style.width = "100%";
    kasten.appendChild(this._symbolKnoten("mdi:check-circle-outline"));
    const kastenText = document.createElement("span");
    kasten.appendChild(kastenText);
    karte.appendChild(kasten);
    this._bindungen.push(() => {
      const stoerung = this._stoerung(anlage);
      kasten.classList.toggle("stoerung", stoerung);
      kastenText.textContent = stoerung ? "Störung anliegend" : "Keine Störung";
      kasten.firstChild.setAttribute(
        "icon",
        stoerung ? "mdi:alert-circle-outline" : "mdi:check-circle-outline"
      );
    });
    huelle.appendChild(karte);
    huelle.appendChild(this._stoerungskarte(anlage));
    return huelle;
  }

  _stoerungskarte(anlage) {
    const karte = this._karte("Störungen");
    const eintraege = anlage.stoerungen || [];

    const mitte = document.createElement("div");
    mitte.className = "mitte";
    const symbol = this._symbolKnoten("mdi:shield-check-outline");
    const haupt = document.createElement("div");
    haupt.className = "haupt";
    const neben = document.createElement("div");
    neben.className = "neben";
    mitte.append(symbol, haupt, neben);
    karte.appendChild(mitte);

    eintraege.forEach((eintrag) => {
      const zeile = document.createElement("div");
      zeile.className = "status-zeile";
      const links = document.createElement("div");
      links.className = "titel";
      const wert = document.createElement("div");
      wert.className = "wert";
      zeile.append(links, wert);
      karte.appendChild(this._klickbar(zeile, eintrag.entity));
      this._bindungen.push(() => {
        links.textContent = this._name(eintrag.entity).replace(" Meldung Klartext", "");
        const zustand = this._zustand(eintrag.entity);
        const aktiv = zustand && zustand.attributes.stoerung_aktiv === true;
        wert.textContent = this._text(eintrag.entity);
        wert.className = `wert ${aktiv ? "schlecht" : "gut"}`;
        // Ohne Störung sagt der Kasten oben schon alles; die Zeilen sind dann
        // nur Wiederholung.
        zeile.style.display = aktiv ? "flex" : "none";
      });
    });

    this._bindungen.push(() => {
      const stoerung = this._stoerung(anlage);
      symbol.setAttribute("icon", stoerung ? "mdi:shield-alert-outline" : "mdi:shield-check-outline");
      symbol.className = stoerung ? "schlecht" : "gut";
      haupt.textContent = stoerung ? "Störung anliegend" : "Keine Störung";
      neben.textContent = stoerung
        ? "Die Anlage meldet mindestens eine aktive Störung."
        : "Alles läuft.";
      mitte.style.display = stoerung ? "none" : "block";
    });
    return karte;
  }

  // -------------------------------------------------------------------
  // Verlauf
  // -------------------------------------------------------------------
  /**
   * Verlaufskarte mit an- und abwählbaren Linien.
   *
   * Die Vorauswahl kommt aus der Integration; welche Linien der Nutzer
   * zusätzlich sehen will, entscheidet er hier. Die Auswahl überlebt einen
   * Reiterwechsel, weil sie am Element hängt und nicht an der Karte.
   */
  _verlauf(anlage, stunden) {
    if (!(anlage.verlauf || []).length) return null;
    const schluessel = `${anlage.name || ""}|${stunden}`;
    if (!this._linien) this._linien = {};
    if (!this._linien[schluessel]) this._linien[schluessel] = new Set(anlage.verlauf);
    const gewaehlt = this._linien[schluessel];

    const karte = this._karte(`Verlauf (${stunden} Stunden)`);

    const auswahl = document.createElement("div");
    auswahl.className = "linienwahl";
    const moeglich = anlage.verlauf_moeglich || anlage.verlauf.map((e) => ({ entity: e }));
    moeglich.forEach((eintrag) => {
      const kennung = eintrag.entity || eintrag;
      const marke = document.createElement("button");
      marke.type = "button";
      marke.className = "linie";
      marke.textContent = eintrag.titel || this._name(kennung);
      marke.setAttribute("aria-pressed", String(gewaehlt.has(kennung)));
      marke.addEventListener("click", () => {
        if (gewaehlt.has(kennung)) gewaehlt.delete(kennung);
        else gewaehlt.add(kennung);
        marke.setAttribute("aria-pressed", String(gewaehlt.has(kennung)));
        this._verlaufNeuLaden(platz, gewaehlt);
      });
      auswahl.appendChild(marke);
    });
    karte.appendChild(auswahl);

    const platz = document.createElement("div");
    platz.dataset.verlauf = "1";
    platz.dataset.stunden = String(stunden);
    platz.dataset.entities = JSON.stringify([...gewaehlt]);
    karte.appendChild(platz);
    return karte;
  }

  async _verlaufNeuLaden(platz, gewaehlt) {
    platz.dataset.entities = JSON.stringify([...gewaehlt]);
    if (!window.loadCardHelpers) return;
    const helfer = await window.loadCardHelpers();
    const karte = helfer.createCardElement({
      type: "history-graph",
      hours_to_show: Number(platz.dataset.stunden) || 24,
      entities: [...gewaehlt],
    });
    karte.hass = this._hass;
    platz.replaceChildren(karte);
    const alt = this._verlaufskarten.findIndex((k) => k.parentElement === platz);
    if (alt >= 0) this._verlaufskarten[alt] = karte;
    else this._verlaufskarten.push(karte);
  }

  _verlaufReiter(anlage) {
    const spalten = document.createElement("div");
    spalten.className = "spalten";
    const karte = this._verlauf(anlage, 48);
    if (!karte) {
      const leer = this._karte("Verlauf");
      leer.appendChild(this._hinweisKnoten("Keine Werte für einen Verlauf gefunden."));
      spalten.appendChild(leer);
      return spalten;
    }
    spalten.appendChild(karte);
    return spalten;
  }

  async _verlaufKarteLaden() {
    const plaetze = this.shadowRoot.querySelectorAll("[data-verlauf]");
    if (!plaetze.length || !window.loadCardHelpers) return;
    const helfer = await window.loadCardHelpers();
    this._verlaufskarten = [];
    plaetze.forEach((platz) => {
      const karte = helfer.createCardElement({
        type: "history-graph",
        hours_to_show: Number(platz.dataset.stunden) || 24,
        entities: JSON.parse(platz.dataset.entities),
      });
      karte.hass = this._hass;
      platz.replaceChildren(karte);
      this._verlaufskarten.push(karte);
    });
  }

  // -------------------------------------------------------------------
  // Reiter „Steuerung"
  // -------------------------------------------------------------------
  _steuerung(anlage) {
    const steuerung = anlage.steuerung || {};
    const spalten = document.createElement("div");
    spalten.className = "spalten";

    (steuerung.heizkreise || []).forEach((kreis) => {
      spalten.appendChild(this._heizkreisKarte(kreis));
    });
    if (steuerung.warmwasser) {
      spalten.appendChild(this._warmwasserKarte(steuerung.warmwasser));
    }
    if ((steuerung.kessel || []).length) {
      spalten.appendChild(this._kesselKarte(steuerung.kessel));
    }
    if (steuerung.lagerraum) {
      spalten.appendChild(this._lagerraumKarte(steuerung.lagerraum));
    }
    if (!spalten.childElementCount) {
      const leer = this._karte("Steuerung");
      leer.appendChild(this._hinweisKnoten("Keine bedienbaren Werte gefunden."));
      spalten.appendChild(leer);
    }
    return spalten;
  }

  /** Heizkreis mit Sollwertregler, Betriebswahl und Zeitprogramm. */
  _heizkreisKarte(kreis) {
    const karte = this._karte(kreis.titel);

    // Die Anlage stellt in ihrer Detailansicht die Betriebsart als Klartext
    // ueber den Wert - dort sucht man sie.
    const betriebsart = document.createElement("div");
    betriebsart.className = "betriebsart";
    karte.appendChild(betriebsart);
    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      betriebsart.textContent =
        zustand && zustand.attributes.preset_mode ? this._presetName(zustand) : "";
    });

    const gross = document.createElement("div");
    gross.className = "gross";
    const zahl = document.createElement("div");
    zahl.className = "zahl";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = "Raumtemperatur";
    gross.append(zahl, beschriftung);
    karte.appendChild(this._klickbar(gross, kreis.entity));

    const laufzeit = document.createElement("div");
    laufzeit.className = "laufzeit";
    laufzeit.appendChild(this._symbolKnoten("mdi:timer-sand"));
    const laufzeitText = document.createElement("span");
    laufzeit.appendChild(laufzeitText);
    karte.appendChild(laufzeit);

    // Sollwertregler
    const regler = document.createElement("div");
    regler.className = "regler";
    const runter = document.createElement("button");
    runter.type = "button";
    runter.textContent = "−";
    runter.setAttribute("aria-label", "Sollwert senken");
    const mitte = document.createElement("div");
    mitte.className = "sollwert";
    const sollZahl = document.createElement("div");
    sollZahl.className = "zahl";
    const sollText = document.createElement("div");
    sollText.className = "beschriftung";
    sollText.textContent = "Sollwert";
    mitte.append(sollZahl, sollText);
    const hoch = document.createElement("button");
    hoch.type = "button";
    hoch.textContent = "+";
    hoch.setAttribute("aria-label", "Sollwert anheben");
    regler.append(runter, mitte, hoch);
    karte.appendChild(regler);

    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    karte.appendChild(rueckmeldung);

    const stellen = async (richtung) => {
      const zustand = this._zustand(kreis.entity);
      if (!zustand) return;
      const schritt = Number(zustand.attributes.target_temp_step) || 0.5;
      const soll = Number(zustand.attributes.temperature);
      if (Number.isNaN(soll)) return;
      const neu = Math.round((soll + richtung * schritt) * 10) / 10;
      await this._uebertragen(
        rueckmeldung,
        () =>
          this._hass.callService("climate", "set_temperature", {
            entity_id: kreis.entity,
            temperature: neu,
          }),
        // Bestätigt ist die Vorgabe erst, wenn die Anlage sie zurückmeldet.
        () => {
          const jetzt = this._zustand(kreis.entity);
          return !!jetzt && Math.abs(Number(jetzt.attributes.temperature) - neu) < 0.3;
        }
      );
    };
    runter.addEventListener("click", () => stellen(-1));
    hoch.addEventListener("click", () => stellen(1));

    if (kreis.betriebswahl) {
      karte.appendChild(this._auswahlFeld("Betriebswahl", kreis.betriebswahl));
    }
    if (kreis.programm) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.append(trenner, this._statuszeile(kreis.programm, "Zeitprogramm"));
    }
    if (kreis.vorlauf) {
      karte.appendChild(this._statuszeile(kreis.vorlauf, "Vorlauf"));
    }

    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      const ist = zustand && zustand.attributes.current_temperature;
      zahl.textContent = ist !== undefined && ist !== null ? `${ist} °C` : "–";
      const soll = zustand && zustand.attributes.temperature;
      sollZahl.textContent = soll !== undefined && soll !== null ? `${soll} °C` : "–";
      const rest = this._restzeit(zustand);
      laufzeit.style.display = rest ? "inline-flex" : "none";
      laufzeitText.textContent = rest ? `Vorgabe ${rest}` : "";
    });
    return karte;
  }

  /**
   * Warmwasser mit Ist, Soll und Einmalladung.
   *
   * Die Einmalladung läuft minutenlang. Die Taste bleibt deshalb markiert,
   * solange die Anlage sie als aktiv meldet, und springt von selbst zurück,
   * wenn die Ladung fertig ist – so wie in der Windhager-App.
   */
  _warmwasserKarte(wasser) {
    const karte = this._karte("Warmwasser");

    // Wie bei der Anlage: die Betriebsart im Klartext über dem Wert.
    if (wasser.betriebsart) {
      const betriebsart = document.createElement("div");
      betriebsart.className = "betriebsart";
      karte.appendChild(betriebsart);
      this._bindungen.push(() => {
        betriebsart.textContent = this._text(wasser.betriebsart);
      });
    }

    const gross = document.createElement("div");
    gross.className = "gross";
    const zahl = document.createElement("div");
    zahl.className = "zahl";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = "Isttemperatur";
    gross.append(zahl, beschriftung);
    karte.appendChild(wasser.ist ? this._klickbar(gross, wasser.ist) : gross);
    this._bindungen.push(() => {
      zahl.textContent = wasser.ist ? this._text(wasser.ist) : "–";
    });

    if (wasser.soll) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.append(trenner, this._statuszeile(wasser.soll, "Sollwert"));
    }
    if (wasser.programm) {
      karte.appendChild(this._statuszeile(wasser.programm, "Programm"));
    }

    if (wasser.laden) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.appendChild(trenner);
      // Die Anlage kennt zur Einmalladung beides: die Temperatur, auf die
      // geladen wird, und das Ausloesen.
      if (wasser.laden_temperatur) {
        karte.appendChild(this._statuszeile(wasser.laden_temperatur, "Ladetemperatur"));
      }
      karte.appendChild(this._ladeTaste(wasser));
    }
    return karte;
  }

  /**
   * Taste für die Warmwasser-Einmalladung.
   *
   * Der Auslöser selbst (`2/16`) fällt zurück, sobald die Anlage den Auftrag
   * angenommen hat – er taugt deshalb nicht als Anzeige. Ob wirklich geladen
   * wird, sagt die WW-Ladepumpe; im Zweifel wird gegengeprüft, ob die
   * Warmwassertemperatur noch unter dem Sollwert liegt.
   */
  _ladeTaste(wasser) {
    const entity = wasser.laden;
    const bereich = entity.split(".")[0];
    // Was die Anlage gerade tut, steht in der Betriebsart. Meldet sie keine,
    // bleibt die Ladepumpe als Anhaltspunkt.
    const laedt = () => {
      const zustand = this._zustand(wasser.betriebsart);
      if (zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase())) {
        return (wasser.laedt_wenn || []).includes(zustand.state);
      }
      if (wasser.laeuft) return this._istAn(wasser.laeuft);
      return this._istAn(entity);
    };
    const taste = document.createElement("button");
    taste.className = "taste";
    taste.type = "button";
    taste.appendChild(this._symbolKnoten("mdi:water-boiler"));
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = "Einmalladung";
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    taste.append(beschriftung, rueckmeldung);

    taste.addEventListener("click", async () => {
      if (taste.disabled) return;
      const lief = laedt();
      // Ein zweiter Druck während „wird ausgeführt …" ist ein Abbruchwunsch:
      // Die Anzeige wird freigegeben und der Grundzustand wiederhergestellt.
      delete rueckmeldung.dataset.belegt;
      taste.disabled = true;
      try {
        if (lief && wasser.betriebswahl) {
          // Abbrechen heißt an der Anlage: die dauerhafte Betriebswahl wieder
          // setzen. Der vorübergehende Zustand fällt damit weg – denselben Weg
          // geht die Anlagen-App über die Taste „Programm".
          const wahl = this._zustand(wasser.betriebswahl);
          if (!wahl) return;
          await this._uebertragen(
            rueckmeldung,
            () =>
              this._hass.callService("select", "select_option", {
                entity_id: wasser.betriebswahl,
                option: wahl.state,
              }),
            () => !laedt()
          );
          return;
        }
        await this._uebertragen(
          rueckmeldung,
          () =>
            bereich === "button"
              ? this._hass.callService("button", "press", { entity_id: entity })
              : this._hass.callService("homeassistant", "turn_on", { entity_id: entity }),
          // Bestätigt ist der Auftrag, wenn die Anlage anfängt zu laden.
          () => laedt()
        );
      } finally {
        taste.disabled = false;
      }
    });

    this._bindungen.push(() => {
      const laeuft = laedt();
      taste.classList.toggle("an", laeuft);
      beschriftung.textContent = laeuft ? "Ladung abbrechen" : "Einmalladung";
      if (rueckmeldung.dataset.belegt === "1") return;
      rueckmeldung.className = "rueckmeldung";
      rueckmeldung.textContent = laeuft ? "lädt gerade" : "bereit";
    });
    return taste;
  }

  _istAn(entity) {
    const zustand = this._zustand(entity);
    return !!zustand && zustand.state === "on";
  }

  _auswahlFeld(titel, entity) {
    const feld = document.createElement("div");
    feld.className = "feld";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = titel;
    const auswahl = document.createElement("select");
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    feld.append(beschriftung, auswahl, rueckmeldung);

    auswahl.addEventListener("change", async () => {
      const gewaehlt = auswahl.value;
      await this._uebertragen(
        rueckmeldung,
        () =>
          this._hass.callService("select", "select_option", {
            entity_id: entity,
            option: gewaehlt,
          }),
        () => {
          const zustand = this._zustand(entity);
          return !!zustand && zustand.state === gewaehlt;
        }
      );
    });

    this._bindungen.push(() => {
      const zustand = this._zustand(entity);
      const optionen = (zustand && zustand.attributes.options) || [];
      if (auswahl.dataset.optionen !== optionen.join("|")) {
        auswahl.dataset.optionen = optionen.join("|");
        auswahl.replaceChildren(
          ...optionen.map((option) => {
            const knoten = document.createElement("option");
            knoten.value = option;
            knoten.textContent = option;
            return knoten;
          })
        );
      }
      if (zustand && rueckmeldung.dataset.belegt !== "1") auswahl.value = zustand.state;
    });
    return feld;
  }

  /**
   * Lagerraumbefüllung, aufgebaut wie die Seite am Bediengerät.
   *
   * Erst anfordern, dann ablesen: Die Anlage gibt das Befüllen nur frei, wenn
   * ihr Zustand es zulässt – bei pneumatischer Zuführung etwa erst bei leerem
   * Vorratsbehälter. Erst wenn dort „freigegeben" steht, darf weiterbefüllt
   * werden; das ist keine Anzeigefrage, sondern steht so in der Anleitung des
   * Kessels (Beschädigung des Rührwerks).
   */
  _lagerraumKarte(lagerraum) {
    const karte = this._karte("Lagerraum befüllen");

    (lagerraum.zeilen || []).forEach((zeile) => {
      karte.appendChild(this._statuszeile(zeile.entity, zeile.titel));
    });

    const trenner = document.createElement("div");
    trenner.className = "trenner";
    karte.appendChild(trenner);
    karte.appendChild(
      this._bedientaste(
        {
          entity: lagerraum.anfordern,
          titel: "Befüllung anfordern",
          symbol: "mdi:warehouse",
          frage: lagerraum.frage,
        },
        true
      )
    );
    return karte;
  }

  _kesselKarte(eintraege) {
    const karte = this._karte("Kessel");
    eintraege.forEach((eintrag) => {
      const bereich = eintrag.entity.split(".")[0];
      if (bereich === "select") {
        karte.appendChild(this._auswahlFeld(eintrag.titel, eintrag.entity));
        return;
      }
      karte.appendChild(this._bedientaste(eintrag, true));
    });
    return karte;
  }

  // -------------------------------------------------------------------
  // Reiter „Wartung"
  // -------------------------------------------------------------------
  _wartung(anlage) {
    const wartung = anlage.wartung || {};
    const spalten = document.createElement("div");
    spalten.className = "spalten";

    const abschnitte = [
      ["Restlaufzeiten", wartung.restlaufzeiten, "mdi:progress-clock"],
      ["Brennstoff", wartung.brennstoff, "mdi:sack"],
      ["Zählerstände", wartung.zaehler, "mdi:counter"],
      ["Weiteres", wartung.weitere, "mdi:wrench-outline"],
    ];
    abschnitte.forEach(([titel, zeilen]) => {
      if (!zeilen || !zeilen.length) return;
      const karte = this._karte(titel);
      zeilen.forEach((zeile) => {
        karte.appendChild(this._statuszeile(zeile.entity, zeile.titel));
      });
      spalten.appendChild(karte);
    });

    if (!spalten.childElementCount) {
      const leer = this._karte("Wartung");
      leer.appendChild(this._hinweisKnoten("Keine Wartungswerte gefunden."));
      spalten.appendChild(leer);
    }
    return spalten;
  }

  // -------------------------------------------------------------------
  // Schnellzugriff
  // -------------------------------------------------------------------
  _schnellzugriff(anlage) {
    const eintraege = anlage.schnellzugriff || [];
    if (!eintraege.length) return null;
    const karte = this._karte("Schnellzugriff");
    const gitter = document.createElement("div");
    gitter.className = "gitter";

    eintraege.forEach((eintrag) => {
      if (eintrag.entity.split(".")[0] === "select") {
        const huelle = this._auswahlFeld(eintrag.titel, eintrag.entity);
        huelle.style.gridColumn = "1 / -1";
        gitter.appendChild(huelle);
        return;
      }
      gitter.appendChild(this._bedientaste(eintrag, false));
    });

    karte.appendChild(gitter);
    return karte;
  }

  /** Eine Kachel, die einen Befehl auslöst – mit Rückfrage und Rückmeldung. */
  _bedientaste(eintrag, breit) {
    const bereich = eintrag.entity.split(".")[0];
    // Manche Bedienungen melden ihren Zustand woanders: Die Warmwasserladung
    // steht in der Betriebsart, ihr Auslöser fällt sofort zurück.
    const laeuft = () => {
      if (eintrag.zustand_an) {
        const zustand = this._zustand(eintrag.zustand_an);
        if (zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase())) {
          return (eintrag.zustand_wenn || []).includes(zustand.state);
        }
      }
      return this._istAn(eintrag.entity);
    };
    const taste = document.createElement("button");
    taste.className = "taste";
    taste.type = "button";
    if (breit) taste.style.marginTop = "10px";
    taste.appendChild(this._symbolKnoten(eintrag.symbol || "mdi:gesture-tap-button"));
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = eintrag.titel;
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    taste.append(beschriftung, rueckmeldung);
    if (eintrag.hilfe) {
      const hinweis = this._fragezeichen(eintrag.titel, eintrag.hilfe);
      hinweis.classList.add("auf-taste");
      taste.appendChild(hinweis);
    }

    taste.addEventListener("click", async () => {
      if (taste.disabled) return;
      if (eintrag.frage && !(await this._bestaetigen(eintrag.titel, eintrag.frage))) return;
      const lief = laeuft();
      taste.disabled = true;
      try {
        await this._uebertragen(
          rueckmeldung,
          () =>
            bereich === "button"
              ? this._hass.callService("button", "press", { entity_id: eintrag.entity })
              : this._hass.callService(
                  "homeassistant",
                  eintrag.zustand_an ? "turn_on" : "toggle",
                  { entity_id: eintrag.entity }
                ),
          bereich === "button" ? null : () => laeuft() !== lief
        );
      } finally {
        taste.disabled = false;
      }
    });

    this._bindungen.push(() => {
      const zustand = this._zustand(eintrag.entity);
      const an = laeuft();
      taste.classList.toggle("an", an);
      // Solange eine Übertragung läuft, gehört die Zeile der Rückmeldung.
      if (rueckmeldung.dataset.belegt === "1") return;
      rueckmeldung.className = "rueckmeldung";
      rueckmeldung.textContent = eintrag.zustand_an
        ? (an ? "läuft" : "bereit")
        : this._tastenZustand(bereich, zustand, an);
    });
    return taste;
  }

  // -------------------------------------------------------------------
  // Bedienen: nachfragen, übertragen, zurückmelden
  // -------------------------------------------------------------------

  /**
   * Rückfrage vor einem Eingriff, der die Anlage wirklich etwas kostet.
   *
   * Bewusst ein eigener Dialog statt `window.confirm`: Der blockiert den
   * Browser und sieht in Home Assistant wie ein Fremdkörper aus.
   */
  _bestaetigen(titel, frage) {
    return new Promise((antworten) => {
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog";
      dialog.setAttribute("role", "alertdialog");

      const ueberschrift = document.createElement("h3");
      ueberschrift.className = "dialog-titel";
      ueberschrift.textContent = titel;
      const text = document.createElement("div");
      text.className = "dialog-text";
      text.textContent = frage;

      const leiste = document.createElement("div");
      leiste.className = "dialog-leiste";
      const abbrechen = document.createElement("button");
      abbrechen.type = "button";
      abbrechen.className = "dialog-taste";
      abbrechen.textContent = "Abbrechen";
      const ausloesen = document.createElement("button");
      ausloesen.type = "button";
      ausloesen.className = "dialog-taste betont";
      ausloesen.textContent = "Ja, ausführen";
      leiste.append(abbrechen, ausloesen);

      dialog.append(ueberschrift, text, leiste);
      schleier.appendChild(dialog);

      const schliessen = (antwort) => {
        schleier.remove();
        document.removeEventListener("keydown", beiTaste);
        antworten(antwort);
      };
      const beiTaste = (ereignis) => {
        if (ereignis.key === "Escape") schliessen(false);
      };
      abbrechen.addEventListener("click", () => schliessen(false));
      ausloesen.addEventListener("click", () => schliessen(true));
      schleier.addEventListener("click", (ereignis) => {
        if (ereignis.target === schleier) schliessen(false);
      });
      document.addEventListener("keydown", beiTaste);

      this.shadowRoot.appendChild(schleier);
      ausloesen.focus();
    });
  }

  /**
   * Einen Dienstaufruf ausführen und den Verlauf sichtbar machen.
   *
   * Die Anlage wird nur alle 30 s abgefragt; ohne Rückmeldung drückt man und
   * nichts passiert. Deshalb drei Stufen: „wird übertragen" während des
   * Aufrufs, danach „wird ausgeführt …", solange die Anlage den neuen Zustand
   * noch nicht zurückmeldet, und erst dann „übernommen ✓".
   *
   * Ohne `bestaetigt` bleibt es bei den ersten beiden Stufen – bei einer
   * Taste ohne Zustand gibt es nichts, worauf man warten könnte.
   */
  async _uebertragen(anzeige, aufruf, bestaetigt) {
    // Ein neuer Auftrag löst den alten ab – sonst hinge die Anzeige an einer
    // Bestätigung, auf die niemand mehr wartet.
    this._wartend = this._wartend.filter((v) => v.anzeige !== anzeige);
    anzeige.dataset.belegt = "1";
    anzeige.className = "rueckmeldung laeuft";
    anzeige.textContent = "wird übertragen …";
    try {
      await aufruf();
    } catch (err) {
      anzeige.className = "rueckmeldung fehler";
      anzeige.textContent = "nicht übernommen";
      console.warn("HeatNexus: Befehl abgelehnt", err);
      this._freigeben(anzeige, RUECKMELDUNG_MS);
      return;
    }

    if (!bestaetigt) {
      anzeige.className = "rueckmeldung erfolg";
      anzeige.textContent = "übertragen ✓";
      this._freigeben(anzeige, RUECKMELDUNG_MS);
      return;
    }

    anzeige.className = "rueckmeldung wartet";
    anzeige.textContent = "wird ausgeführt …";
    this._wartend.push({ anzeige, bestaetigt, seit: Date.now() });
    this._pruefeWartende();
  }

  /** Die Anzeige nach kurzer Zeit wieder dem Zustand überlassen. */
  _freigeben(anzeige, verzoegerung) {
    window.setTimeout(() => {
      delete anzeige.dataset.belegt;
      this._aktualisieren();
    }, verzoegerung);
  }

  /**
   * Laufende Vorgänge prüfen.
   *
   * Läuft bei jedem Zustandswechsel mit – die Anlage meldet ihren neuen
   * Zustand mit dem nächsten Abruf, und genau darauf wird gewartet.
   */
  _pruefeWartende() {
    if (!this._wartend.length) return;
    const offen = [];
    this._wartend.forEach((vorgang) => {
      let fertig = false;
      try {
        fertig = vorgang.bestaetigt();
      } catch (err) {
        console.warn("HeatNexus: Zustand nicht prüfbar", err);
        fertig = true;
      }
      if (fertig) {
        vorgang.anzeige.className = "rueckmeldung erfolg";
        vorgang.anzeige.textContent = "übernommen ✓";
        this._freigeben(vorgang.anzeige, RUECKMELDUNG_MS);
        return;
      }
      if (Date.now() - vorgang.seit > BESTAETIGUNG_MAX_MS) {
        vorgang.anzeige.className = "rueckmeldung";
        vorgang.anzeige.textContent = "keine Rückmeldung";
        this._freigeben(vorgang.anzeige, RUECKMELDUNG_MS);
        return;
      }
      offen.push(vorgang);
    });
    this._wartend = offen;
  }

  /** Was unter einer Taste steht, wenn gerade nichts übertragen wird. */
  _tastenZustand(bereich, zustand, laeuft) {
    if (!zustand) return "";
    if (bereich === "button") {
      const zeitpunkt = new Date(zustand.state);
      if (Number.isNaN(zeitpunkt.getTime())) return "noch nie ausgelöst";
      return `zuletzt ${zeitpunkt.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      })}`;
    }
    return laeuft ? "läuft" : "aus";
  }

  // -------------------------------------------------------------------
  _aktualisieren() {
    this._bindungen.forEach((binden) => binden());
    this._pruefeWartende();
    (this._verlaufskarten || []).forEach((karte) => {
      karte.hass = this._hass;
    });
  }
}

if (!customElements.get("heatnexus-panel")) {
  customElements.define("heatnexus-panel", HeatNexusPanel);
}
