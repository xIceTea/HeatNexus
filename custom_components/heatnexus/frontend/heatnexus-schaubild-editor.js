/**
 * Einstellungen der Schaubild-Karte.
 *
 * Eigenes Element statt eines festen Formularschemas: Die Auswahl der Anlagen
 * steht erst fest, wenn die Integration sie gemeldet hat – ein Schema kennt
 * `hass` nicht und könnte nur ein Textfeld anbieten.
 */

import { FARBSAETZE } from "./ordnung.js";

const ELEMENT = "heatnexus-schaubild-editor";

const BESCHRIFTUNG = {
  anlage: "Anlage",
  farbsatz: "Farbsatz",
  animation: "Animation",
};

class HeatNexusSchaubildEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._anlagen = [];
  }

  setConfig(config) {
    this._config = { ...(config || {}) };
    this._zeichnen();
  }

  set hass(hass) {
    const erster = !this._hass;
    this._hass = hass;
    if (erster) this._laden = this._anlagenHolen();
    else this._zeichnen();
  }

  async _anlagenHolen() {
    try {
      this._anlagen = await this._hass.callWS({ type: "heatnexus/schaubild" });
    } catch (err) {
      console.warn("HeatNexus: Anlagen konnten nicht geladen werden", err);
      this._anlagen = [];
    }
    this._zeichnen();
  }

  // Ohne Anlagen bleibt die Auswahl leer statt zu verschwinden – sonst sähe
  // die Maske aus, als fehlte sie.
  _schema() {
    return [
      {
        name: "anlage",
        selector: {
          select: {
            mode: "dropdown",
            options: this._anlagen.map((a) => ({ value: a.id, label: a.name || a.id })),
          },
        },
      },
      {
        name: "farbsatz",
        selector: {
          select: {
            mode: "dropdown",
            options: FARBSAETZE.map((s) => ({ value: s.schluessel, label: s.titel })),
          },
        },
      },
      { name: "animation", selector: { boolean: {} } },
    ];
  }

  async _zeichnen() {
    if (!this._hass) return;
    await customElements.whenDefined("ha-form");
    if (!this._formular) {
      this._formular = document.createElement("ha-form");
      this._formular.computeLabel = (feld) => BESCHRIFTUNG[feld.name] || feld.name;
      this._formular.addEventListener("value-changed", (ereignis) => {
        ereignis.stopPropagation();
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: { ...this._config, ...ereignis.detail.value } },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._formular);
    }
    this._formular.hass = this._hass;
    this._formular.schema = this._schema();
    this._formular.data = { farbsatz: "auto", animation: true, ...this._config };
  }
}

if (!customElements.get(ELEMENT)) {
  customElements.define(ELEMENT, HeatNexusSchaubildEditor);
}

export { HeatNexusSchaubildEditor, ELEMENT };
