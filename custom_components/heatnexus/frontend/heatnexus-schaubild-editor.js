/**
 * Einstellungen der Schaubild-Karte.
 *
 * Eigenes Element statt eines festen Formularschemas: Anlagen, Anlagenteile
 * und deren Werte stehen erst fest, wenn die Integration sie gemeldet hat –
 * ein Schema wird ohne `hass` gebaut und kennt sie nicht.
 */

import { FARBSAETZE } from "./ordnung.js";

const ELEMENT = "heatnexus-schaubild-editor";
const ALLE = "alle";

const BESCHRIFTUNG = {
  anlage: "Anlage",
  farbsatz: "Farbsatz",
  animation: "Animation",
  liste: "Werteliste",
  zusatzwerte: "Werte in der Liste",
  teile_aus: "Anlagenteile ausblenden",
  darstellung: "Darstellung",
  werte: "Werte im Schaubild",
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

  /** Die Anlagenteile, die zur gewählten Anlage gehören. */
  _teile() {
    const gewuenscht = this._config.anlage;
    const anlagen =
      gewuenscht === ALLE || !gewuenscht
        ? gewuenscht === ALLE
          ? this._anlagen
          : this._anlagen.slice(0, 1)
        : this._anlagen.filter((a) => a.id === gewuenscht || a.name === gewuenscht);
    return anlagen.flatMap((a) => a.schema_teile || []);
  }

  _alleWerte() {
    const gesehen = new Map();
    this._teile().forEach((teil) => {
      teil.werte.forEach((wert) => {
        if (!gesehen.has(wert.entity)) {
          gesehen.set(wert.entity, { value: wert.entity, label: `${teil.titel} · ${wert.name}` });
        }
      });
    });
    return [...gesehen.values()];
  }

  _auswahl(werte, mehrfach = true) {
    return { select: { multiple: mehrfach, reorder: mehrfach, mode: "list", options: werte } };
  }

  _schema() {
    const teile = this._teile();
    return [
      {
        name: "anlage",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: ALLE, label: "Alle Anlagen" },
              ...this._anlagen.map((a) => ({ value: a.id, label: a.name || a.id })),
            ],
          },
        },
      },
      {
        type: "expandable",
        name: "darstellung",
        title: BESCHRIFTUNG.darstellung,
        icon: "mdi:palette-outline",
        flatten: true,
        schema: [
          {
            name: "farbsatz",
            selector: {
              select: {
                mode: "dropdown",
                options: FARBSAETZE.map((s) => ({ value: s.schluessel, label: s.titel })),
              },
            },
          },
          {
            name: "liste",
            selector: {
              select: {
                mode: "dropdown",
                options: [
                  { value: "rechts", label: "rechts neben dem Schaubild" },
                  { value: "unten", label: "unter dem Schaubild" },
                ],
              },
            },
          },
          { name: "animation", selector: { boolean: {} } },
        ],
      },
      {
        type: "expandable",
        name: "liste_ab",
        title: BESCHRIFTUNG.zusatzwerte,
        icon: "mdi:format-list-bulleted",
        flatten: true,
        schema: [{ name: "zusatzwerte", selector: this._auswahl(this._alleWerte()) }],
      },
      {
        type: "expandable",
        name: "bild_ab",
        title: BESCHRIFTUNG.werte,
        icon: "mdi:sitemap-outline",
        flatten: true,
        schema: [
          {
            name: "teile_aus",
            selector: this._auswahl(teile.map((t) => ({ value: t.id, label: t.titel }))),
          },
          {
            type: "expandable",
            name: "werte",
            title: "Je Anlagenteil",
            schema: teile.map((teil) => ({
              name: teil.id,
              selector: this._auswahl(
                teil.werte.map((w) => ({ value: w.entity, label: w.name }))
              ),
            })),
          },
        ],
      },
    ];
  }

  // Anlagenteile heißen nach der Anlage, nicht nach ihrer Kennung.
  _beschriftung(feld) {
    const teil = this._teile().find((t) => t.id === feld.name);
    if (teil) return teil.titel;
    return BESCHRIFTUNG[feld.name] || feld.title || feld.name;
  }

  /** Vorbelegung: die Vorgabe der Anlage, damit nichts leer beginnt. */
  _daten() {
    const werte = { ...(this._config.werte || {}) };
    this._teile().forEach((teil) => {
      if (werte[teil.id] === undefined) werte[teil.id] = teil.vorgabe;
    });
    return {
      anlage: this._config.anlage || ALLE,
      farbsatz: "auto",
      animation: true,
      liste: "rechts",
      zusatzwerte: [],
      teile_aus: [],
      ...this._config,
      werte,
    };
  }

  async _zeichnen() {
    if (!this._hass) return;
    await customElements.whenDefined("ha-form");
    if (!this._formular) {
      this._formular = document.createElement("ha-form");
      this._formular.computeLabel = (feld) => this._beschriftung(feld);
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
    this._formular.data = this._daten();
  }
}

if (!customElements.get(ELEMENT)) {
  customElements.define(ELEMENT, HeatNexusSchaubildEditor);
}

export { HeatNexusSchaubildEditor, ELEMENT };
