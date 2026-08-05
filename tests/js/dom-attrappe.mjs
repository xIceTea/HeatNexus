/**
 * Eine Attrappe des Browsers, gerade groß genug für die Oberfläche.
 *
 * Node bringt kein DOM mit, und ein vollständiges (jsdom) wäre eine
 * Abhängigkeit samt Bauschritt – für ein Projekt ohne beides der falsche
 * Preis. Diese Attrappe kann genau das, was `heatnexus-panel.js` benutzt:
 * Elemente anlegen, aneinanderhängen, Klassen und Datenfelder setzen,
 * Ereignisse anmelden und auslösen, und suchen (`querySelector`).
 *
 * Sie prüft nichts. Sie sorgt nur dafür, dass der Aufbau der Oberfläche in
 * Node **wirklich läuft** statt nur zu laden – Fehler wie eine nicht
 * importierte Konstante zeigen sich erst dabei.
 */

class KlassenListe {
  constructor() {
    this._werte = new Set();
  }
  add(...namen) {
    namen.filter(Boolean).forEach((name) => this._werte.add(name));
  }
  remove(...namen) {
    namen.forEach((name) => this._werte.delete(name));
  }
  contains(name) {
    return this._werte.has(name);
  }
  toggle(name, an) {
    const soll = an === undefined ? !this._werte.has(name) : !!an;
    if (soll) this._werte.add(name);
    else this._werte.delete(name);
    return soll;
  }
  get wert() {
    return [...this._werte].join(" ");
  }
}

class Knoten {
  constructor(name) {
    this.tagName = String(name).toUpperCase();
    this.children = [];
    this.parentElement = null;
    this.attribute = new Map();
    this.dataset = {};
    this.style = new Proxy(
      { setProperty(schluessel, wert) {
          this[schluessel] = wert;
        } },
      { get: (ziel, schluessel) => ziel[schluessel], set: (ziel, schluessel, wert) => {
          ziel[schluessel] = wert;
          return true;
        } }
    );
    this._klassen = new KlassenListe();
    this._text = "";
    this._hoerer = new Map();
  }

  // --- Klassen und Attribute ---------------------------------------------
  get classList() {
    return this._klassen;
  }
  get className() {
    return this._klassen.wert;
  }
  set className(wert) {
    this._klassen = new KlassenListe();
    String(wert)
      .split(/\s+/)
      .forEach((name) => this._klassen.add(name));
  }
  setAttribute(name, wert) {
    this.attribute.set(name, String(wert));
  }
  getAttribute(name) {
    return this.attribute.has(name) ? this.attribute.get(name) : null;
  }
  removeAttribute(name) {
    this.attribute.delete(name);
  }

  // --- Inhalt -------------------------------------------------------------
  get textContent() {
    if (this.children.length) return this.children.map((kind) => kind.textContent).join("");
    return this._text;
  }
  set textContent(wert) {
    this.children.forEach((kind) => {
      kind.parentElement = null;
    });
    this.children = [];
    this._text = wert === null || wert === undefined ? "" : String(wert);
  }
  get firstChild() {
    return this.children[0] || null;
  }
  get childElementCount() {
    return this.children.length;
  }

  // --- Baum ---------------------------------------------------------------
  appendChild(kind) {
    if (!kind) return kind;
    if (kind.parentElement) kind.parentElement.removeChild(kind);
    kind.parentElement = this;
    this.children.push(kind);
    this._text = "";
    return kind;
  }
  append(...kinder) {
    kinder.forEach((kind) => this.appendChild(kind));
  }
  prepend(kind) {
    if (!kind) return;
    kind.parentElement = this;
    this.children.unshift(kind);
  }
  removeChild(kind) {
    this.children = this.children.filter((eintrag) => eintrag !== kind);
    kind.parentElement = null;
    return kind;
  }
  remove() {
    if (this.parentElement) this.parentElement.removeChild(this);
  }
  replaceChildren(...kinder) {
    this.children.forEach((kind) => {
      kind.parentElement = null;
    });
    this.children = [];
    this.append(...kinder);
  }
  insertBefore(kind, vor) {
    const stelle = this.children.indexOf(vor);
    if (stelle < 0) return this.appendChild(kind);
    kind.parentElement = this;
    this.children.splice(stelle, 0, kind);
    return kind;
  }
  closest(wahl) {
    let knoten = this;
    while (knoten) {
      if (knoten._passt && knoten._passt(wahl)) return knoten;
      knoten = knoten.parentElement;
    }
    return null;
  }

  // --- Suchen -------------------------------------------------------------
  _passt(wahl) {
    if (wahl.startsWith(".")) return this._klassen.contains(wahl.slice(1));
    if (wahl.startsWith("[") && wahl.endsWith("]")) {
      const name = wahl.slice(1, -1);
      return this.attribute.has(name) || name.replace(/^data-/, "") in this.dataset;
    }
    return this.tagName === wahl.toUpperCase();
  }
  _alle(wahl, treffer) {
    this.children.forEach((kind) => {
      if (kind._passt(wahl)) treffer.push(kind);
      kind._alle(wahl, treffer);
    });
    return treffer;
  }
  querySelector(wahl) {
    return this._alle(wahl, [])[0] || null;
  }
  querySelectorAll(wahl) {
    return this._alle(wahl, []);
  }

  // --- Ereignisse ---------------------------------------------------------
  addEventListener(art, ruf) {
    if (!this._hoerer.has(art)) this._hoerer.set(art, []);
    this._hoerer.get(art).push(ruf);
  }
  removeEventListener(art, ruf) {
    const liste = this._hoerer.get(art) || [];
    this._hoerer.set(
      art,
      liste.filter((eintrag) => eintrag !== ruf)
    );
  }
  dispatchEvent(ereignis) {
    (this._hoerer.get(ereignis.type) || []).forEach((ruf) => ruf(ereignis));
    return true;
  }
  /** Ein Ereignis auslösen, wie es der Nutzer täte. */
  ausloesen(art, ereignis = {}) {
    const liste = [...(this._hoerer.get(art) || [])];
    liste.forEach((ruf) => ruf({ type: art, target: this, preventDefault() {}, stopPropagation() {}, ...ereignis }));
    return liste.length;
  }
  focus() {}
}

/** Die Attrappe in `globalThis` einhängen. Gibt die Zeitschaltung zurück. */
export function browserAttrappe() {
  const auftraege = [];
  globalThis.document = {
    createElement: (name) => new Knoten(name),
    addEventListener() {},
    removeEventListener() {},
  };
  globalThis.HTMLElement = class {
    constructor() {
      this._hoerer = new Map();
    }
    attachShadow() {
      this.shadowRoot = new Knoten("shadow-root");
      return this.shadowRoot;
    }
    addEventListener(art, ruf) {
      if (!this._hoerer.has(art)) this._hoerer.set(art, []);
      this._hoerer.get(art).push(ruf);
    }
    dispatchEvent() {
      return true;
    }
  };
  globalThis.CustomEvent = class {
    constructor(art, angaben = {}) {
      this.type = art;
      Object.assign(this, angaben);
    }
  };
  globalThis.customElements = {
    _klassen: new Map(),
    get(name) {
      return this._klassen.get(name);
    },
    define(name, klasse) {
      this._klassen.set(name, klasse);
    },
  };
  globalThis.window = globalThis;
  globalThis.setTimeout = (ruf, ms) => {
    auftraege.push({ ruf, ms });
    return auftraege.length;
  };
  globalThis.clearTimeout = () => {};

  return {
    /** Alle wartenden Zeitaufträge ausführen – ohne echte Wartezeit. */
    zeitLaufenLassen() {
      while (auftraege.length) auftraege.shift().ruf();
    },
    offeneAuftraege: () => auftraege.length,
  };
}

export { Knoten };
