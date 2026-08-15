/**
 * Das Anlagenschaubild als Lovelace-Karte.
 *
 * Zeichnung, Werte und Bewegung kommen aus denselben Teilen wie im Panel
 * (`teile/schaubild.js`); hier steht nur, was Home Assistant von einer Karte
 * verlangt: Konfiguration, `hass`, Größe im Raster.
 */

import { BausteineMixin } from "./teile/bausteine.js";
import { SchaubildMixin } from "./teile/schaubild.js";
import { WerteMixin } from "./teile/werte.js";
import { STIL } from "./stil.js";
import { FARBSAETZE } from "./ordnung.js";

const ELEMENT = "heatnexus-schaubild";
const EDITOR = "heatnexus-schaubild-editor";

const Grundlage = SchaubildMixin(BausteineMixin(WerteMixin(HTMLElement)));

class HeatNexusSchaubildKarte extends Grundlage {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._anlagen = [];
    this._bindungen = [];
    this._gebaut = false;
  }

  // Ein Formularschema statt eines eigenen Editors: Home Assistant lädt
  // `ha-form` dafür selbst, und der YAML-Rückfall kommt geschenkt.
  static getConfigForm() {
    return {
      schema: [
        { name: "anlage", selector: { text: {} } },
        {
          name: "farbsatz",
          selector: { select: { mode: "dropdown", options: FARBSAETZE.map((s) => s.schluessel) } },
        },
        { name: "animation", selector: { boolean: {} } },
      ],
    };
  }

  static getStubConfig() {
    return { type: `custom:${ELEMENT}`, farbsatz: "auto", animation: true };
  }

  /** Elf Rasterzeilen sind gut zwei Drittel Breite bei voller Zeichnung. */
  getGridOptions() {
    return { columns: 12, rows: 6, min_columns: 6, min_rows: 4 };
  }

  getCardSize() {
    return 6;
  }

  setConfig(config) {
    if (config && config.farbsatz && !FARBSAETZE.some((s) => s.schluessel === config.farbsatz)) {
      throw new Error(`Unbekannter Farbsatz: ${config.farbsatz}`);
    }
    this._config = { farbsatz: "auto", animation: true, ...(config || {}) };
    this._gebaut = false;
    this._zeichnen();
  }

  set hass(hass) {
    const erster = !this._hass;
    this._hass = hass;
    if (erster) {
      // Der Vorgang wird gemerkt, damit die Prüfung ihn abwarten kann.
      this._laden = this._datenHolen();
      return;
    }
    this._aktualisieren();
  }

  /** Der im Editor gewählte Satz gilt; das Panel fragt hier seine Anordnung. */
  _farbsatz() {
    return this._config.farbsatz;
  }

  async _datenHolen() {
    try {
      this._anlagen = await this._hass.callWS({ type: "heatnexus/schaubild" });
    } catch (err) {
      console.warn("HeatNexus: Schaubild konnte nicht geladen werden", err);
      this._anlagen = [];
    }
    this._gebaut = false;
    this._zeichnen();
  }

  // Ohne Angabe die erste Anlage: Eine Karte, die ohne Konfiguration leer
  // bleibt, wirkt kaputt.
  _anlage() {
    if (!this._anlagen.length) return null;
    const gewuenscht = this._config.anlage;
    if (!gewuenscht) return this._anlagen[0];
    return this._anlagen.find((a) => a.id === gewuenscht || a.name === gewuenscht) || null;
  }

  _zeichnen() {
    if (!this.shadowRoot || this._gebaut) return;
    this._bindungen = [];
    this.shadowRoot.replaceChildren();
    const stil = document.createElement("style");
    stil.textContent = STIL;
    this.shadowRoot.appendChild(stil);

    const anlage = this._anlage();
    const bild = anlage && this._schaubild(anlage);
    this.shadowRoot.appendChild(bild || this._hinweis());
    if (bild && this._config.animation === false) {
      const huelle = bild.querySelector(".schaubild");
      if (huelle) huelle.classList.add("ruhig");
    }
    this._gebaut = true;
    this._aktualisieren();
  }

  _hinweis() {
    const karte = this._karte("Anlagenschaubild");
    const zeile = document.createElement("div");
    zeile.className = "hinweis";
    zeile.textContent = this._anlagen.length
      ? "Diese Anlage gibt es nicht mehr."
      : "Noch keine Anlage eingelesen.";
    karte.appendChild(zeile);
    return karte;
  }

  _aktualisieren() {
    if (!this._gebaut) return;
    this._bindungen.forEach((bindung) => bindung());
  }
}

if (!customElements.get(ELEMENT)) {
  customElements.define(ELEMENT, HeatNexusSchaubildKarte);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((k) => k.type === ELEMENT)) {
  window.customCards.push({
    type: ELEMENT,
    name: "HeatNexus Anlagenschaubild",
    description: "Die Anlage als Schaubild, mit Werten und laufenden Pumpen.",
    preview: true,
    documentationURL: "https://github.com/xIceTea/HeatNexus",
  });
}

export { HeatNexusSchaubildKarte, ELEMENT, EDITOR };
