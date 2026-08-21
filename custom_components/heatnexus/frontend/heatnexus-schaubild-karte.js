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

  // Volle Breite im Raster der Ansicht: Neben dem Bild steht die Werteliste,
  // auf halber Spur bleibt für sie nur eine Spalte übrig. Die Höhe folgt dem
  // Inhalt – sie hängt an der Zahl der Anlagenteile und der Werte daneben.
  getGridOptions() {
    return { columns: 24, rows: "auto", min_columns: 12, min_rows: 4 };
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
    const vorher = JSON.stringify([
      this._config.werte,
      this._config.teile_aus,
      this._config.zeichnungen,
      this._config.mischer,
    ]);
    this._config = { farbsatz: "auto", schrift: "normal", animation: true, ...(config || {}) };
    this._gebaut = false;
    const jetzt = JSON.stringify([
      this._config.werte,
      this._config.teile_aus,
      this._config.zeichnungen,
      this._config.mischer,
    ]);
    if (this._hass && vorher !== jetzt) {
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

  _zeigtPumpen() {
    return this._config.pumpen !== false;
  }

  _zeigtMischer() {
    return this._config.mischer !== false;
  }

  // Eine leere Überschrift blendet sie aus; ohne Angabe bleibt die gewohnte.
  _bildtitel() {
    const titel = this._config.titel_bild;
    return titel === undefined ? "Anlagenübersicht" : titel;
  }

  _listentitel() {
    const titel = this._config.titel_liste;
    return titel === undefined ? "Werte" : titel;
  }

  async _datenHolen() {
    this._abrufFehler = false;
    try {
      const anfrage = { type: "heatnexus/schaubild" };
      if (this._config.werte) anfrage.auswahl = this._config.werte;
      if (this._config.teile_aus) anfrage.teile_aus = this._config.teile_aus;
      if (this._config.zeichnungen) anfrage.zeichnungen = this._config.zeichnungen;
      if (this._config.mischer === false) anfrage.mischer = false;
      this._anlagen = await this._hass.callWS(anfrage);
    } catch (err) {
      console.warn("HeatNexus: Schaubild konnte nicht geladen werden", err);
      this._anlagen = [];
      this._abrufFehler = true;
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

  // Ein Eintrag ist die Entität allein oder ein Satz eigener Angaben. Beides
  // steht nebeneinander in derselben Liste, damit ältere Karten weiterlaufen.
  _eintraege() {
    const vorrat = this._wertevorrat();
    return (this._config.zusatzwerte || [])
      .map((eintrag) => (typeof eintrag === "string" ? { entity: eintrag } : eintrag || {}))
      .filter(
        (eintrag) => eintrag.entity && (vorrat.has(eintrag.entity) || this._zustand(eintrag.entity))
      );
  }

  /** Was zu einem Wert bekannt ist – aus der Anlage oder aus dem Zustand. */
  _wertangaben(entity) {
    const bekannt = this._wertevorrat().get(entity);
    if (bekannt) return bekannt;
    const zustand = this._zustand(entity);
    const attribute = (zustand && zustand.attributes) || {};
    return { name: this._name(entity), teil: "", symbol: attribute.icon || null };
  }

  _zusatzwerte() {
    return this._eintraege().map((eintrag) => eintrag.entity);
  }

  /** Der Aufbau der Zeile: Vorgabe der Karte, je Eintrag überschreibbar. */
  _zeilenform(eintrag) {
    const vorgabe = this._config.zeilen || {};
    const gilt = (feld) => (eintrag[feld] !== undefined ? eintrag[feld] : vorgabe[feld]);
    return {
      aufbau: eintrag.aufbau || vorgabe.aufbau || "name_links",
      teil: eintrag.teil || vorgabe.teil || "unter_wert",
      farbe: eintrag.farbe || vorgabe.farbe || "",
      einheit: gilt("einheit") !== false,
      klick: gilt("klick") !== false,
    };
  }

  // Die Liste behauptet nichts über Rohre – hier darf frei gewählt werden,
  // quer über alle Anlagenteile.
  _werteliste() {
    const gewaehlt = this._eintraege();
    if (!gewaehlt.length) return null;
    const karte = this._karte(this._listentitel());
    const symbole = (this._config.zeilen || {}).symbol !== "aus";
    gewaehlt.forEach((eintrag) => {
      const bekannt = this._wertangaben(eintrag.entity);
      const symbol = eintrag.symbol || (symbole ? bekannt.symbol : null);
      karte.appendChild(
        this._wertzeile(
          eintrag.entity,
          eintrag.beschriftung || bekannt.teil || "",
          eintrag.name || bekannt.name,
          symbol,
          null,
          this._zeilenform(eintrag)
        )
      );
    });
    return karte;
  }

  _hinweis() {
    const karte = this._karte("Anlagenschaubild");
    const zeile = document.createElement("div");
    zeile.className = "hinweis";
    // Ein misslungener Abruf ist etwas anderes als eine Anlage, die noch
    // nicht eingelesen ist – der Satz darf das nicht vertauschen.
    if (this._abrufFehler) {
      zeile.textContent = "Das Schaubild konnte nicht geladen werden.";
    } else {
      zeile.textContent = this._anlagen.length
        ? "Diese Anlage gibt es nicht mehr."
        : "Noch keine Anlage eingelesen.";
    }
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
