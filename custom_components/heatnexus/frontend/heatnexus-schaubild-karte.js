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
import { FARBSAETZE, SCHRIFTMASSE, schriftmass } from "./ordnung.js";

const ELEMENT = "heatnexus-schaubild";
const ALLE = "alle";
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

  // Eigener Editor statt eines festen Schemas: Nur er kann die Anlagen zur
  // Auswahl stellen – ein Schema wird ohne `hass` gebaut und kennt sie nicht.
  static async getConfigElement() {
    await import("./heatnexus-schaubild-editor.js");
    await customElements.whenDefined(EDITOR);
    return document.createElement(EDITOR);
  }

  static getStubConfig() {
    return { type: `custom:${ELEMENT}`, farbsatz: "auto", schrift: "normal", animation: true };
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
    if (config && config.schrift && !SCHRIFTMASSE.some((m) => m.schluessel === config.schrift)) {
      throw new Error(`Unbekanntes Schriftmaß: ${config.schrift}`);
    }
    const vorher = JSON.stringify([this._config.werte, this._config.teile_aus]);
    this._config = { farbsatz: "auto", schrift: "normal", animation: true, ...(config || {}) };
    this._gebaut = false;
    if (this._hass && vorher !== JSON.stringify([this._config.werte, this._config.teile_aus])) {
      this._laden = this._datenHolen();
      return;
    }
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

  /** Das im Editor gewählte Schriftmaß der Marken. */
  _schriftmass() {
    return schriftmass(this._config.schrift);
  }

  async _datenHolen() {
    try {
      const anfrage = { type: "heatnexus/schaubild" };
      if (this._config.werte) anfrage.auswahl = this._config.werte;
      if (this._config.teile_aus) anfrage.teile_aus = this._config.teile_aus;
      this._anlagen = await this._hass.callWS(anfrage);
    } catch (err) {
      console.warn("HeatNexus: Schaubild konnte nicht geladen werden", err);
      this._anlagen = [];
    }
    this._gebaut = false;
    this._zeichnen();
  }

  // Ohne Angabe die erste Anlage: Eine Karte, die ohne Konfiguration leer
  // bleibt, wirkt kaputt.
  _gewaehlteAnlagen() {
    if (!this._anlagen.length) return [];
    const gewuenscht = this._config.anlage;
    if (gewuenscht === ALLE) return this._anlagen;
    if (!gewuenscht) return this._anlagen.slice(0, 1);
    const treffer = this._anlagen.find((a) => a.id === gewuenscht || a.name === gewuenscht);
    return treffer ? [treffer] : [];
  }

  /** Alle Werte aller gewählten Anlagen, für die Liste daneben. */
  _wertevorrat() {
    const vorrat = new Map();
    this._gewaehlteAnlagen().forEach((anlage) => {
      (anlage.schema_teile || []).forEach((teil) => {
        teil.werte.forEach((wert) => {
          if (!vorrat.has(wert.entity)) vorrat.set(wert.entity, { ...wert, teil: teil.titel });
        });
      });
    });
    return vorrat;
  }

  _zeichnen() {
    if (!this.shadowRoot || this._gebaut) return;
    this._bindungen = [];
    this.shadowRoot.replaceChildren();
    const stil = document.createElement("style");
    stil.textContent = STIL;
    this.shadowRoot.appendChild(stil);

    const anlagen = this._gewaehlteAnlagen();
    const bilder = anlagen.map((a) => this._schaubild(a)).filter(Boolean);
    if (!bilder.length && !this._zusatzwerte().length) {
      this.shadowRoot.appendChild(this._hinweis());
      this._gebaut = true;
      this._aktualisieren();
      return;
    }
    if (this._config.animation === false) {
      bilder.forEach((bild) => {
        const huelle = bild.querySelector(".schaubild");
        if (huelle) huelle.classList.add("ruhig");
      });
    }
    const liste = this._werteliste();
    const stelle = liste ? this._config.liste || "rechts" : "aus";
    const rahmen = document.createElement("div");
    rahmen.className = `karte-zweispaltig lage-${stelle}`;
    const links = document.createElement("div");
    bilder.forEach((bild) => links.appendChild(bild));
    rahmen.appendChild(links);
    if (liste) rahmen.appendChild(liste);
    this.shadowRoot.appendChild(rahmen);
    this._gebaut = true;
    this._aktualisieren();
  }

  _zusatzwerte() {
    const vorrat = this._wertevorrat();
    return (this._config.zusatzwerte || []).filter((entity) => vorrat.has(entity));
  }

  // Die Liste behauptet nichts über Rohre – hier darf frei gewählt werden,
  // quer über alle Anlagenteile.
  _werteliste() {
    const gewaehlt = this._zusatzwerte();
    if (!gewaehlt.length) return null;
    const vorrat = this._wertevorrat();
    const karte = this._karte("Werte");
    gewaehlt.forEach((entity) => {
      const eintrag = vorrat.get(entity);
      karte.appendChild(this._wertzeile(entity, eintrag.teil || "", eintrag.name));
    });
    return karte;
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

export { HeatNexusSchaubildKarte, ELEMENT, EDITOR, ALLE };
