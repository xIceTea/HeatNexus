/**
 * Einstellungen der Schaubild-Karte.
 *
 * Eigenes Element statt eines festen Formularschemas: Anlagen, Anlagenteile
 * und deren Werte stehen erst fest, wenn die Integration sie gemeldet hat –
 * ein Schema wird ohne `hass` gebaut und kennt sie nicht.
 */

import { FARBSAETZE, SCHRIFTMASSE } from "./ordnung.js";

const ELEMENT = "heatnexus-schaubild-editor";
const ALLE = "alle";

const BESCHRIFTUNG = {
  anlage: "Anlage",
  farbsatz: "Farbsatz",
  schrift: "Schriftgröße im Schaubild",
  animation: "Animation",
  pumpen: "Pumpen im Schaubild",
  liste: "Werteliste",
  zusatzwerte: "Werte der Anlage",
  weitere: "Eigene Sensoren",
  eigene_ab: "Eigene Sensoren",
  mischer: "Mischer im Schaubild",
  zeichnungen: "Zeichnungen",
  allgemein: "Allgemeines",
  titel_bild: "Überschrift über dem Bild",
  titel_liste: "Überschrift über der Liste",
  teile_aus: "Anlagenteile ausblenden",
  darstellung: "Darstellung",
  werte: "Werte im Schaubild",
  zeilen_ab: "Aufbau der Zeilen",
  aufbau: "Aufbau",
  teil: "Anlagenteil",
  symbol: "Symbol",
  name: "Name",
  farbe: "Symbolfarbe",
  beschriftung: "Anlagenteil beschriften",
  anordnung: "Anordnung",
  einheit: "Einheit anzeigen",
  klick: "Klick öffnet Details",
};

const AUFBAUTEN = [
  { value: "name_links", label: "Name links, Wert rechts" },
  { value: "wert_rechts", label: "Anlagenteil links, Wert rechts" },
  { value: "kompakt", label: "Kompakt, eine Zeile" },
];

const TEILORTE = [
  { value: "unter_wert", label: "unter dem Wert" },
  { value: "unter_name", label: "unter dem Namen" },
  { value: "aus", label: "nicht anzeigen" },
];

class HeatNexusSchaubildEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._anlagen = [];
    this._offen = null;
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
    return this._gewaehlteAnlagen().flatMap((a) => a.schema_teile || []);
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

  /** Was die Anlage zu einem Wert meldet: Name, Anlagenteil, Symbol. */
  _bekannt(entity) {
    for (const teil of this._teile()) {
      const treffer = (teil.werte || []).find((w) => w.entity === entity);
      if (treffer) return { ...treffer, teil: teil.titel };
    }
    return null;
  }

  // Ein Eintrag ist die Entität allein oder ein Satz eigener Angaben.
  _eintraege() {
    return (this._config.zusatzwerte || []).map((eintrag) =>
      typeof eintrag === "string" ? { entity: eintrag } : { ...(eintrag || {}) }
    );
  }

  /** Angaben zu einem Wert; fremde Entitäten kommen aus ihrem Zustand. */
  _angaben(entity) {
    const bekannt = this._bekannt(entity);
    if (bekannt) return bekannt;
    const zustand = this._hass && this._hass.states ? this._hass.states[entity] : null;
    const attribute = (zustand && zustand.attributes) || {};
    return { name: attribute.friendly_name || entity, teil: "", symbol: attribute.icon || "" };
  }

  /** Die gezeichneten Anlagenteile, auch Warmwasser und Zirkulation. */
  _zeichenbar() {
    const gesehen = new Map();
    this._gewaehlteAnlagen().forEach((anlage) => {
      (anlage.schema_zeichenbar || []).forEach((teil) => {
        if (!gesehen.has(teil.id)) gesehen.set(teil.id, teil);
      });
    });
    return [...gesehen.values()];
  }

  /** Alle Bauteilzeichnungen, die die Integration mitbringt. */
  _bauteile() {
    const anlage = this._gewaehlteAnlagen()[0];
    return (anlage && anlage.schema_bauteile) || [];
  }

  /** Die Anlagen, auf die sich die Karte gerade bezieht. */
  _gewaehlteAnlagen() {
    const gewuenscht = this._config.anlage;
    if (gewuenscht === ALLE || !gewuenscht) {
      return gewuenscht === ALLE ? this._anlagen : this._anlagen.slice(0, 1);
    }
    return this._anlagen.filter((a) => a.id === gewuenscht || a.name === gewuenscht);
  }

  /** Ob der Wert von der Anlage kommt; alles andere ist frei hinzugefügt. */
  _ausDerAnlage(entity) {
    return this._alleWerte().some((wert) => wert.value === entity);
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
        name: "allgemein",
        title: BESCHRIFTUNG.allgemein,
        icon: "mdi:card-text-outline",
        flatten: true,
        schema: [
          { name: "titel_bild", selector: { text: {} } },
          { name: "titel_liste", selector: { text: {} } },
        ],
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
            name: "schrift",
            selector: {
              select: {
                mode: "dropdown",
                options: SCHRIFTMASSE.map((m) => ({ value: m.schluessel, label: m.titel })),
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
          { name: "pumpen", selector: { boolean: {} } },
          { name: "mischer", selector: { boolean: {} } },
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
        name: "eigene_ab",
        title: BESCHRIFTUNG.eigene_ab,
        icon: "mdi:playlist-plus",
        flatten: true,
        schema: [{ name: "weitere", selector: { entity: { multiple: true } } }],
      },
      {
        type: "expandable",
        name: "zeilen_ab",
        title: BESCHRIFTUNG.zeilen_ab,
        icon: "mdi:format-align-left",
        flatten: true,
        schema: [
          { name: "aufbau", selector: { select: { mode: "dropdown", options: AUFBAUTEN } } },
          { name: "teil", selector: { select: { mode: "dropdown", options: TEILORTE } } },
          { name: "symbol", selector: { boolean: {} } },
        ],
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
            name: "zeichnungen",
            title: BESCHRIFTUNG.zeichnungen,
            schema: this._zeichenbar().map((teil) => ({
              name: teil.id,
              selector: {
                select: {
                  mode: "dropdown",
                  options: [
                    { value: "", label: "wie erkannt" },
                    ...this._bauteile().map((n) => ({ value: n, label: n })),
                  ],
                },
              },
            })),
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

  /** Zweite Ebene: was für einen einzelnen Wert gilt. */
  _schemaEintrag() {
    return [
      { name: "name", selector: { text: {} } },
      { name: "symbol", selector: { icon: {} } },
      {
        name: "aufbau",
        selector: {
          select: {
            mode: "dropdown",
            options: [{ value: "", label: "wie in der Karte" }, ...AUFBAUTEN],
          },
        },
      },
      {
        name: "teil",
        selector: {
          select: {
            mode: "dropdown",
            options: [{ value: "", label: "wie in der Karte" }, ...TEILORTE],
          },
        },
      },
      { name: "beschriftung", selector: { text: {} } },
      { name: "farbe", selector: { ui_color: { default_color: "state" } } },
      { name: "einheit", selector: { boolean: {} } },
      { name: "klick", selector: { boolean: {} } },
    ];
  }

  // Anlagenteile heißen nach der Anlage, nicht nach ihrer Kennung.
  _beschriftung(feld) {
    const teil = this._teile().find((t) => t.id === feld.name);
    if (teil) return teil.titel;
    const gezeichnet = this._zeichenbar().find((t) => t.id === feld.name);
    if (gezeichnet) return gezeichnet.titel;
    return BESCHRIFTUNG[feld.name] || feld.title || feld.name;
  }

  /** Vorbelegung: die Vorgabe der Anlage, damit nichts leer beginnt. */
  _daten() {
    const werte = { ...(this._config.werte || {}) };
    this._teile().forEach((teil) => {
      if (werte[teil.id] === undefined) werte[teil.id] = teil.vorgabe;
    });
    const zeilen = this._config.zeilen || {};
    return {
      anlage: this._config.anlage || ALLE,
      farbsatz: "auto",
      schrift: "normal",
      animation: true,
      pumpen: true,
      mischer: true,
      liste: "rechts",
      teile_aus: [],
      titel_bild: "Anlagenübersicht",
      titel_liste: "Werte",
      ...this._config,
      zusatzwerte: this._eintraege()
        .map((eintrag) => eintrag.entity)
        .filter((entity) => this._ausDerAnlage(entity)),
      weitere: this._eintraege()
        .map((eintrag) => eintrag.entity)
        .filter((entity) => !this._ausDerAnlage(entity)),
      zeichnungen: { ...(this._config.zeichnungen || {}) },
      aufbau: zeilen.aufbau || "name_links",
      teil: zeilen.teil || "unter_wert",
      symbol: zeilen.symbol !== "aus",
      werte,
    };
  }

  // Kein Neuaufbau nach jeder Eingabe: Ein Textfeld verlöre dabei den Fokus.
  _melden(config) {
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true })
    );
  }

  // Aufbau, Anlagenteil und Symbol gehören zusammen und stehen deshalb unter
  // `zeilen`, nicht einzeln in der Konfiguration.
  _hauptGeaendert(wert) {
    const config = { ...this._config, ...wert };
    const bisher = new Map(this._eintraege().map((e) => [e.entity, e]));
    const gewaehlt = [...(wert.zusatzwerte || []), ...(wert.weitere || [])];
    config.zusatzwerte = gewaehlt.map((entity) => bisher.get(entity) || entity);
    delete config.weitere;
    config.zeilen = { aufbau: wert.aufbau, teil: wert.teil, symbol: wert.symbol ? "an" : "aus" };
    config.zeichnungen = Object.fromEntries(
      Object.entries(wert.zeichnungen || {}).filter(([, name]) => name)
    );
    delete config.aufbau;
    delete config.teil;
    delete config.symbol;
    this._melden(config);
    this._listeAuffrischen();
  }

  /** Leere Angaben fallen weg, damit der Eintrag eine Zeichenkette bleiben kann. */
  _eintragGeaendert(entity, wert) {
    const geaendert = { entity };
    ["name", "symbol", "aufbau", "teil", "farbe", "beschriftung"].forEach((feld) => {
      if (wert[feld]) geaendert[feld] = wert[feld];
    });
    ["einheit", "klick"].forEach((feld) => {
      if (wert[feld] === false) geaendert[feld] = false;
    });
    const config = { ...this._config };
    config.zusatzwerte = this._eintraege().map((vorher) => {
      const ziel = vorher.entity === entity ? geaendert : vorher;
      return Object.keys(ziel).length === 1 ? ziel.entity : ziel;
    });
    this._melden(config);
  }

  _formular(schema, daten, beiAenderung) {
    const formular = document.createElement("ha-form");
    formular.hass = this._hass;
    formular.computeLabel = (feld) => this._beschriftung(feld);
    formular.schema = schema;
    formular.data = daten;
    formular.addEventListener("value-changed", (ereignis) => {
      ereignis.stopPropagation();
      beiAenderung(ereignis.detail.value);
    });
    return formular;
  }

  /** Einen Eintrag an eine andere Stelle der Liste setzen. */
  _verschieben(von, nach) {
    const eintraege = this._config.zusatzwerte || [];
    if (von === nach || von < 0 || nach < 0 || von >= eintraege.length) return;
    const neu = [...eintraege];
    const [genommen] = neu.splice(von, 1);
    neu.splice(Math.min(nach, neu.length), 0, genommen);
    this._melden({ ...this._config, zusatzwerte: neu });
    this._zeichnen();
  }

  /** Die gewählten Werte als Liste; ein Klick führt zu den Einzelheiten. */
  _liste() {
    const kasten = document.createElement("div");
    kasten.style.marginTop = "16px";
    const kopf = document.createElement("div");
    kopf.textContent = BESCHRIFTUNG.anordnung;
    kopf.style.cssText = "font-weight:500;margin:0 0 4px 4px";
    kasten.appendChild(kopf);
    this._eintraege().forEach((eintrag, platz) => {
      const bekannt = this._angaben(eintrag.entity);
      const zeile = document.createElement("div");
      zeile.setAttribute("role", "button");
      zeile.setAttribute("tabindex", "0");
      zeile.draggable = true;
      zeile.addEventListener("dragstart", () => {
        this._gezogen = platz;
      });
      zeile.addEventListener("dragover", (ereignis) => ereignis.preventDefault());
      zeile.addEventListener("drop", (ereignis) => {
        ereignis.preventDefault();
        if (this._gezogen !== undefined) this._verschieben(this._gezogen, platz);
        this._gezogen = undefined;
      });
      zeile.style.cssText =
        "display:flex;align-items:center;gap:12px;padding:8px 4px;cursor:pointer;" +
        "border-bottom:1px solid var(--divider-color)";
      const griff = document.createElement("ha-icon");
      griff.icon = "mdi:drag";
      griff.style.opacity = "0.5";
      const symbol = document.createElement("ha-icon");
      symbol.icon = eintrag.symbol || bekannt.symbol || "mdi:gauge";
      const text = document.createElement("div");
      text.style.flex = "1";
      text.innerHTML =
        `<div>${eintrag.name || bekannt.name || eintrag.entity}</div>` +
        `<div style="font-size:12px;opacity:0.6">${bekannt.teil || ""}</div>`;
      const pfeil = document.createElement("ha-icon");
      pfeil.icon = "mdi:chevron-right";
      zeile.append(griff, symbol, text, pfeil);
      const oeffnen = () => {
        this._offen = eintrag.entity;
        this._zeichnen();
      };
      zeile.addEventListener("click", oeffnen);
      zeile.addEventListener("keydown", (ereignis) => {
        if (ereignis.key === "Enter" || ereignis.key === " ") oeffnen();
      });
      kasten.appendChild(zeile);
    });
    return kasten;
  }

  /** Kopfzeile der zweiten Ebene, mit dem Weg zurück. */
  _kopf(titel) {
    const kopf = document.createElement("div");
    kopf.style.cssText = "display:flex;align-items:center;gap:12px;margin-bottom:12px";
    const zurueck = document.createElement("ha-icon-button");
    zurueck.setAttribute("label", "Zurück");
    const pfeil = document.createElement("ha-icon");
    pfeil.icon = "mdi:arrow-left";
    zurueck.appendChild(pfeil);
    zurueck.addEventListener("click", () => {
      this._offen = null;
      this._zeichnen();
    });
    const text = document.createElement("div");
    text.textContent = titel;
    kopf.append(zurueck, text);
    return kopf;
  }

  _eintragDaten(eintrag, bekannt) {
    return {
      name: eintrag.name || "",
      symbol: eintrag.symbol || bekannt.symbol || "",
      aufbau: eintrag.aufbau || "",
      teil: eintrag.teil || "",
      farbe: eintrag.farbe || "",
      beschriftung: eintrag.beschriftung || "",
      einheit: eintrag.einheit !== false,
      klick: eintrag.klick !== false,
    };
  }

  // Das Formular wird gepflegt, nicht neu gebaut: Jede Zustandsmeldung setzt
  // `hass` neu, und ein neues Element klappte die aufgeschlagenen Abschnitte
  // sofort wieder zu.
  _pflegen(formular, schema, daten) {
    formular.hass = this._hass;
    const neu = JSON.stringify(schema);
    if (formular._hnSchema !== neu) {
      formular.schema = schema;
      formular._hnSchema = neu;
    }
    formular.data = daten;
  }

  async _zeichnen() {
    if (!this._hass) return;
    await customElements.whenDefined("ha-form");
    const eintrag = this._offen
      ? this._eintraege().find((e) => e.entity === this._offen)
      : null;
    if (this._offen && !eintrag) this._offen = null;
    const ebene = this._offen || "haupt";
    if (this._ebene !== ebene) {
      this.replaceChildren();
      this._hauptFormular = null;
      this._detailFormular = null;
      this._listeKnoten = null;
      this._ebene = ebene;
    }

    if (eintrag) {
      const bekannt = this._angaben(eintrag.entity);
      if (!this._detailFormular) {
        this._detailFormular = this._formular(this._schemaEintrag(), {}, (wert) =>
          this._eintragGeaendert(eintrag.entity, wert)
        );
        this.append(this._kopf(bekannt.name || eintrag.entity), this._detailFormular);
      }
      this._pflegen(this._detailFormular, this._schemaEintrag(), this._eintragDaten(eintrag, bekannt));
      return;
    }

    if (!this._hauptFormular) {
      this._hauptFormular = this._formular(this._schema(), {}, (wert) =>
        this._hauptGeaendert(wert)
      );
      this._listeKnoten = this._liste();
      this.append(this._hauptFormular, this._listeKnoten);
    }
    this._pflegen(this._hauptFormular, this._schema(), this._daten());
    this._listeAuffrischen();
  }

  /** Die Liste nur neu bauen, wenn sich ihre Einträge geändert haben. */
  _listeAuffrischen() {
    const stand = JSON.stringify(this._config.zusatzwerte || []);
    if (!this._listeKnoten || this._listeStand === stand) return;
    const neu = this._liste();
    this._listeKnoten.replaceWith(neu);
    this._listeKnoten = neu;
    this._listeStand = stand;
  }
}

if (!customElements.get(ELEMENT)) {
  customElements.define(ELEMENT, HeatNexusSchaubildEditor);
}

export { HeatNexusSchaubildEditor, ELEMENT };
