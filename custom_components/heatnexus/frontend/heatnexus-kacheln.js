/**
 * Drei schlichte Lovelace-Karten für die Übersicht des Dashboards:
 * Leitwert (eine große Zahl), Kennwerte (Raster aus Beschriftung und Wert)
 * und Puffer (Säule mit Farbverlauf). Farben und Formen kommen aus dem Theme.
 *
 * Beschriftungen stehen in der Konfiguration; der Server setzt sie in der
 * Sprache der Anlage. Die Karten zeigen Zahlen selbst formatiert.
 */

const LEER = "–";
const AN = "on";
const AUS = "off";
const UNGUELTIG = new Set(["unknown", "unavailable", "none", ""]);
const SPALTEN_VORGABE = 3;
const SPALTEN_MAX = 6;

const STIL = `
  :host { display: block; }
  ha-card { height: 100%; box-sizing: border-box; padding: 16px 18px; }
  .klick { cursor: pointer; border-radius: 8px; min-width: 0; }
  .klick:hover { background: rgba(var(--rgb-primary-text-color, 128,128,128), .05); }
  .klein { font-size: 12px; color: var(--secondary-text-color); white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; }
  .wert { font-size: 16px; font-weight: 700; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; color: var(--primary-text-color); }
  .titel { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
`;

const STIL_LEITWERT = `
  ha-card { background: linear-gradient(135deg,
    color-mix(in srgb, var(--hn-akzent) 14%, transparent) 0%,
    var(--ha-card-background, var(--card-background-color)) 70%); }
  .raster { display: grid; grid-template-columns: minmax(0,1fr) auto; column-gap: 12px; align-items: end; }
  .ueber { font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase;
    color: var(--secondary-text-color); }
  .zustand { font-size: 20px; font-weight: 700; margin: 2px 0; }
  .gross { font-size: 34px; font-weight: 700; letter-spacing: -1px; text-align: right; line-height: 1; }
  .gross .klein { text-align: right; letter-spacing: 0; }
`;

const STIL_KENNWERTE = `
  .raster { display: grid; grid-template-columns: repeat(var(--hn-spalten), minmax(0,1fr));
    gap: 12px 10px; }
  .raster > div { padding: 2px 4px; }
  /* Schmale Karte: höchstens zwei Spalten, sonst brechen die Werte um. */
  :host { container-type: inline-size; }
  @container (max-width: 340px) {
    .raster { grid-template-columns: repeat(min(var(--hn-spalten), 2), minmax(0,1fr)); }
  }
`;

const STIL_PUFFER = `
  .raster { display: grid; grid-template-columns: 48px minmax(0,1fr); column-gap: 14px; }
  .saeule { width: 40px; height: 104px; border-radius: 14px;
    border: 2px solid var(--divider-color, rgba(127,127,127,.2)); }
  .werte { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }
  .titel { margin-bottom: 8px; }
`;

function zustand(hass, entity) {
  const s = entity && hass && hass.states ? hass.states[entity] : null;
  return s && !UNGUELTIG.has(String(s.state).toLowerCase()) ? s : null;
}

/** Zahl mit Einheit im Format der HA-Sprache, Text unverändert. */
export function anzeige(hass, entity, stellen) {
  const s = zustand(hass, entity);
  if (!s) return LEER;
  const zahl = Number(s.state);
  if (Number.isNaN(zahl)) return s.state;
  const einheit = s.attributes && s.attributes.unit_of_measurement;
  const d = stellen ?? (Math.abs(zahl) >= 100 ? 0 : 1);
  const sprache = (hass.locale && hass.locale.language) || hass.language || "de";
  const text = zahl.toLocaleString(sprache, { minimumFractionDigits: d, maximumFractionDigits: d });
  return einheit ? `${text} ${einheit}` : text;
}

export function istAn(hass, entity) {
  const s = zustand(hass, entity);
  return !!s && String(s.state).toLowerCase() === AN;
}

/** Ein Schaltzustand als Wort, eine Drehzahl als Zahl. */
function schaltwert(hass, w) {
  const s = zustand(hass, w.entity);
  const roh = s ? String(s.state).toLowerCase() : "";
  if (roh === AN) return w.an || s.state;
  if (roh === AUS) return w.aus || s.state;
  return anzeige(hass, w.entity, w.stellen);
}

/** Farbe einer Wassertemperatur, kalt nach heiß. */
export function waermefarbe(grad) {
  if (Number.isNaN(grad)) return "var(--disabled-text-color, #666)";
  if (grad >= 65) return "var(--error-color, #ef5350)";
  if (grad >= 50) return "var(--deep-orange-color, #ff8a3d)";
  if (grad >= 40) return "var(--amber-color, #f2b33d)";
  return "var(--blue-color, #4d8eff)";
}

// Felder einer Wertzeile im Editor: Entität, Beschriftung, Nachkommastellen.
const ZEILE = {
  entity: { required: true, selector: { entity: {} } },
  name: { selector: { text: {} } },
  stellen: { selector: { number: { min: 0, max: 3, mode: "box" } } },
};
const ZEILEN = { object: { multiple: true, label_field: "name", fields: ZEILE } };

const BESCHRIFTUNG = {
  ueberschrift: "Überschrift",
  titel: "Titel",
  zustand: "Zustand",
  gross: "Großer Wert",
  gross_name: "Beschriftung des großen Werts",
  neben: "Nebenwerte",
  aktiv: "Hervorgehobene Zustände",
  akzent: "Akzentfarbe",
  spalten: "Spalten",
  werte: "Werte",
  an: "Text für an",
  aus: "Text für aus",
  oben: "Fühler oben",
  name_oben: "Beschriftung oben",
  mitte: "Fühler Mitte",
  name_mitte: "Beschriftung Mitte",
  unten: "Fühler unten",
  name_unten: "Beschriftung unten",
};

function formular(schema) {
  return { schema, computeLabel: (feld) => BESCHRIFTUNG[feld.name] };
}

class Grundkarte extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    if (!config) throw new Error("Konfiguration fehlt");
    this._config = config;
    this._zeichnen();
  }

  set hass(hass) {
    const alt = this._hass;
    this._hass = hass;
    if (!alt || this._entitaeten().some((e) => alt.states[e] !== hass.states[e])) this._zeichnen();
  }

  getGridOptions() {
    return { columns: 12, rows: "auto" };
  }

  getCardSize() {
    return 2;
  }

  _entitaeten() {
    return [];
  }

  _mehr(entity) {
    this.dispatchEvent(new CustomEvent("hass-more-info", {
      detail: { entityId: entity }, bubbles: true, composed: true }));
  }

  _el(tag, klasse, text) {
    const el = document.createElement(tag);
    if (klasse) el.className = klasse;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  _klickbar(el, entity) {
    if (!entity) return el;
    el.classList.add("klick");
    el.addEventListener("click", () => this._mehr(entity));
    return el;
  }

  _rahmen(eigenerStil) {
    const card = document.createElement("ha-card");
    const stil = this._el("style", null, STIL + eigenerStil);
    this.shadowRoot.replaceChildren(stil, card);
    return card;
  }

  _zeichnen() {}
}

/** Große Zahl rechts, Gerät, Zustand und Nebenwerte links. */
class HeatNexusLeitwert extends Grundkarte {
  static getConfigForm() {
    return formular([
      { name: "ueberschrift", selector: { text: {} } },
      { name: "zustand", selector: { entity: {} } },
      { name: "gross", selector: { entity: {} } },
      { name: "gross_name", selector: { text: {} } },
      { name: "neben", selector: ZEILEN },
      { name: "aktiv", selector: { text: { multiple: true } } },
      { name: "akzent", selector: { text: {} } },
    ]);
  }

  static getStubConfig() {
    return { type: "custom:heatnexus-leitwert", ueberschrift: "", neben: [] };
  }

  _entitaeten() {
    const c = this._config;
    return [c.zustand, c.gross, ...(c.neben || []).map((n) => n.entity)].filter(Boolean);
  }

  _zeichnen() {
    if (!this._hass) return;
    const c = this._config;
    const card = this._rahmen(STIL_LEITWERT);
    card.style.setProperty("--hn-akzent", c.akzent || "var(--deep-orange-color, #ff8a3d)");
    const raster = this._el("div", "raster");
    const links = this._el("div");
    links.append(this._el("div", "ueber", c.ueberschrift || ""));
    const z = this._klickbar(this._el("div", "zustand", anzeige(this._hass, c.zustand)), c.zustand);
    const aktuell = zustand(this._hass, c.zustand);
    if (aktuell && (c.aktiv || []).includes(aktuell.state)) z.style.color = "var(--hn-akzent)";
    links.append(z);
    const neben = (c.neben || []).map((n) => `${n.name || ""} ${anzeige(this._hass, n.entity, n.stellen)}`);
    links.append(this._el("div", "klein", neben.join(" · ")));
    const rechts = this._klickbar(this._el("div", "gross", anzeige(this._hass, c.gross, 0)), c.gross);
    rechts.append(this._el("div", "klein", c.gross_name || ""));
    raster.append(links, rechts);
    card.append(raster);
  }
}

/** Raster aus Beschriftung und Wert; ein Tipp öffnet den Verlauf. */
class HeatNexusKennwerte extends Grundkarte {
  static getConfigForm() {
    const zeile = {
      ...ZEILE,
      warnung_unter: { selector: { number: { mode: "box" } } },
      art: { selector: { select: { options: [{ value: "schalter", label: "Schalter" }] } } },
      an: { selector: { text: {} } },
      aus: { selector: { text: {} } },
    };
    return formular([
      { name: "titel", selector: { text: {} } },
      { name: "spalten", selector: { number: { min: 1, max: SPALTEN_MAX, mode: "box" } } },
      { name: "werte", selector: { object: { multiple: true, label_field: "name", fields: zeile } } },
    ]);
  }

  static getStubConfig() {
    return { type: "custom:heatnexus-kennwerte", spalten: SPALTEN_VORGABE, werte: [] };
  }

  _entitaeten() {
    return (this._config.werte || []).map((w) => w.entity);
  }

  _spalten() {
    const zahl = Math.round(Number(this._config.spalten));
    return zahl >= 1 && zahl <= SPALTEN_MAX ? zahl : SPALTEN_VORGABE;
  }

  _text(w) {
    if (w.art === "schalter") return schaltwert(this._hass, w);
    return anzeige(this._hass, w.entity, w.stellen);
  }

  _farbe(w) {
    const s = zustand(this._hass, w.entity);
    if (w.art === "schalter") return istAn(this._hass, w.entity) ? "var(--success-color, #3ecf8e)" : null;
    if (w.warnung_unter !== undefined && s && Number(s.state) < w.warnung_unter) {
      return "var(--warning-color, #f2b33d)";
    }
    return null;
  }

  _zeichnen() {
    if (!this._hass) return;
    const c = this._config;
    const card = this._rahmen(STIL_KENNWERTE);
    card.style.setProperty("--hn-spalten", String(this._spalten()));
    if (c.titel) card.append(this._el("div", "titel", c.titel));
    const raster = this._el("div", "raster");
    for (const w of c.werte || []) {
      const zelle = this._klickbar(this._el("div"), w.entity);
      const wert = this._el("div", "wert", this._text(w));
      const farbe = this._farbe(w);
      if (farbe) wert.style.color = farbe;
      zelle.append(this._el("div", "klein", w.name || ""), wert);
      raster.append(zelle);
    }
    card.append(raster);
  }
}

/** Puffersäule: Farbe oben und unten nach Temperatur, daneben die Werte. */
class HeatNexusPuffer extends Grundkarte {
  static getConfigForm() {
    return formular([
      { name: "titel", selector: { text: {} } },
      { name: "oben", selector: { entity: {} } },
      { name: "name_oben", selector: { text: {} } },
      { name: "mitte", selector: { entity: {} } },
      { name: "name_mitte", selector: { text: {} } },
      { name: "unten", selector: { entity: {} } },
      { name: "name_unten", selector: { text: {} } },
      { name: "neben", selector: ZEILEN },
    ]);
  }

  static getStubConfig() {
    return { type: "custom:heatnexus-puffer", titel: "", neben: [] };
  }

  _entitaeten() {
    const c = this._config;
    return [c.oben, c.mitte, c.unten, ...(c.neben || []).map((n) => n.entity)].filter(Boolean);
  }

  _grad(entity) {
    const s = zustand(this._hass, entity);
    return s ? Number(s.state) : Number.NaN;
  }

  _zeichnen() {
    if (!this._hass) return;
    const c = this._config;
    const card = this._rahmen(STIL_PUFFER);
    const fuehler = [c.oben, c.mitte, c.unten].filter(Boolean);
    const stufen = fuehler.map((e) => waermefarbe(this._grad(e)));
    const saeule = this._klickbar(this._el("div", "saeule"), c.oben);
    // Ein Verlauf braucht zwei Farben; mit einem Fühler steht seine Farbe oben und unten.
    const farben = stufen.length === 1 ? [stufen[0], stufen[0]] : stufen;
    if (farben.length) saeule.style.background = `linear-gradient(to bottom, ${farben.join(", ")})`;
    const rechts = this._el("div");
    rechts.append(this._el("div", "titel", c.titel || ""));
    const werte = this._el("div", "werte");
    const zeilen = [
      [c.name_oben, c.oben], [c.name_mitte, c.mitte], [c.name_unten, c.unten],
      ...(c.neben || []).map((n) => [n.name, n.entity, n.stellen]),
    ].filter(([, e]) => e);
    for (const [name, entity, stellen] of zeilen) {
      const zelle = this._klickbar(this._el("div"), entity);
      zelle.append(this._el("div", "klein", name || ""), this._el("div", "wert", anzeige(this._hass, entity, stellen)));
      werte.append(zelle);
    }
    rechts.append(werte);
    const raster = this._el("div", "raster");
    raster.append(saeule, rechts);
    card.append(raster);
  }
}

const KARTEN = [
  ["heatnexus-leitwert", HeatNexusLeitwert, "HeatNexus Leitwert", "Zustand und Kesseltemperatur groß, Nebenwerte klein."],
  ["heatnexus-kennwerte", HeatNexusKennwerte, "HeatNexus Kennwerte", "Werte im Raster; ein Tipp öffnet den Verlauf."],
  ["heatnexus-puffer", HeatNexusPuffer, "HeatNexus Puffer", "Puffersäule mit Temperaturen oben, Mitte und unten."],
];

window.customCards = window.customCards || [];
for (const [name, klasse, titel, beschreibung] of KARTEN) {
  if (!customElements.get(name)) customElements.define(name, klasse);
  if (!window.customCards.some((k) => k.type === name)) {
    window.customCards.push({ type: name, name: titel, description: beschreibung, preview: true });
  }
}

export { HeatNexusLeitwert, HeatNexusKennwerte, HeatNexusPuffer };
