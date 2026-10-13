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

// Ein Symbol, damit das Feld keine gleichnamige Methode der Oberfläche
// verdeckt: Am echten Element gibt es diese Ablage gar nicht.
const TEXT = Symbol("textinhalt");

// Welches Element zuletzt `focus()` bekam; `activeElement` liest es.
const fokus = { element: null };

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
    this[TEXT] = "";
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
  // Wie im Browser spiegeln title und placeholder ihr Attribut.
  get title() {
    return this.getAttribute("title") || "";
  }
  set title(wert) {
    this.setAttribute("title", wert);
  }
  get placeholder() {
    return this.getAttribute("placeholder") || "";
  }
  set placeholder(wert) {
    this.setAttribute("placeholder", wert);
  }

  // --- Inhalt -------------------------------------------------------------
  get textContent() {
    if (this.children.length) return this.children.map((kind) => kind.textContent).join("");
    return this[TEXT];
  }
  set textContent(wert) {
    this.children.forEach((kind) => {
      kind.parentElement = null;
    });
    this.children = [];
    this[TEXT] = wert === null || wert === undefined ? "" : String(wert);
  }
  // Nur ablegen, nicht auswerten: Geprüft wird, dass der Aufbau läuft, nicht
  // dass die Attrappe einen Parser hat.
  set innerHTML(wert) {
    this[TEXT] = wert === null || wert === undefined ? "" : String(wert);
  }
  get innerHTML() {
    return this[TEXT];
  }
  get firstChild() {
    return this.children[0] || null;
  }
  // Der Browser trennt Text- und Elementkinder; hier stehen beide in
  // `children`. Wer `childNodes` liest, bekommt dasselbe.
  get childNodes() {
    return this.children;
  }
  get childElementCount() {
    return this.children.length;
  }
  // Am Schattenbaum ist der Elternknoten kein Element; hier steht beides gleich.
  get parentNode() {
    return this.parentElement;
  }
  contains(knoten) {
    for (let stelle = knoten; stelle; stelle = stelle.parentElement) {
      if (stelle === this) return true;
    }
    return false;
  }
  /** Das fokussierte Element, sofern es in diesem Teilbaum liegt. */
  get activeElement() {
    return fokus.element && fokus.element !== this && this.contains(fokus.element) ? fokus.element : null;
  }

  // --- Baum ---------------------------------------------------------------
  appendChild(kind) {
    if (!kind) return kind;
    // Wie im Browser: Ein String wird zum Textknoten. Beschriftungen im
    // Dialog stehen so neben ihrem Feld.
    if (typeof kind === "string") {
      const text = new Knoten("#text");
      text.textContent = kind;
      kind = text;
    }
    // Wie im Browser: Ein zuvor gesetzter Text bleibt als Textknoten vorn stehen.
    if (!this.children.length && this[TEXT] && this.tagName !== "#TEXT") {
      const vorher = new Knoten("#text");
      vorher.textContent = this[TEXT];
      vorher.parentElement = this;
      this.children.push(vorher);
      this[TEXT] = "";
    }
    if (kind.parentElement) kind.parentElement.removeChild(kind);
    kind.parentElement = this;
    this.children.push(kind);
    this[TEXT] = "";
    return kind;
  }
  append(...kinder) {
    kinder.forEach((kind) => this.appendChild(kind));
  }
  prepend(kind) {
    if (!kind) return;
    if (kind.parentElement) kind.parentElement.removeChild(kind);
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
  replaceWith(neu) {
    const eltern = this.parentElement;
    if (!eltern) return;
    eltern.insertBefore(neu, this);
    eltern.removeChild(this);
  }
  insertBefore(kind, vor) {
    const stelle = this.children.indexOf(vor);
    if (stelle < 0) return this.appendChild(kind);
    if (kind.parentElement) kind.parentElement.removeChild(kind);
    kind.parentElement = this;
    this.children.splice(stelle, 0, kind);
    return kind;
  }
  get nextSibling() {
    if (!this.parentElement) return null;
    const geschwister = this.parentElement.children;
    return geschwister[geschwister.indexOf(this) + 1] || null;
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
  // Wie im Browser: Ein abgebrochenes `signal` meldet den Hörer wieder ab.
  addEventListener(art, ruf, optionen) {
    const signal = optionen && optionen.signal;
    if (signal && signal.aborted) return;
    if (!this._hoerer.has(art)) this._hoerer.set(art, []);
    this._hoerer.get(art).push(ruf);
    if (signal) signal.addEventListener("abort", () => this.removeEventListener(art, ruf), { once: true });
  }
  /** Wie viele Hörer für eine Ereignisart angemeldet sind. */
  hoererZahl(art) {
    return (this._hoerer.get(art) || []).length;
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
  focus() {
    fokus.element = this;
  }
  blur() {
    if (fokus.element === this) fokus.element = null;
  }
}

/** Die Attrappe in `globalThis` einhängen. Gibt die Zeitschaltung zurück. */
export function browserAttrappe() {
  const auftraege = [];
  const bilder = [];
  let naechsteKennung = 0;
  fokus.element = null;
  globalThis.document = Object.assign(new Knoten("#document"), {
    // Registrierte eigene Elemente werden aufgewertet, wie im Browser.
    createElement: (name) => {
      const Klasse = globalThis.customElements && globalThis.customElements.get(name);
      if (!Klasse) return new Knoten(name);
      const knoten = new Klasse();
      knoten.tagName = String(name).toUpperCase();
      return knoten;
    },
    // Das Schaubild zeichnet sein Laufrad selbst; dafür braucht es SVG-Knoten.
    createElementNS: (_raum, name) => new Knoten(name),
  });
  globalThis.HTMLElement = class extends Knoten {
    constructor() {
      super("html-element");
      this._hoerer = new Map();
      // Wie am echten Element: Die Oberfläche setzt hier ihre Farbvariablen.
      this.style = {
        _werte: new Map(),
        setProperty(name, wert) {
          this._werte.set(name, wert);
        },
        removeProperty(name) {
          this._werte.delete(name);
        },
        getPropertyValue(name) {
          return this._werte.get(name) || "";
        },
      };
    }
    attachShadow() {
      this.shadowRoot = new Knoten("shadow-root");
      this.shadowRoot.host = this;
      this.shadowRoot.adoptedStyleSheets = [];
      return this.shadowRoot;
    }
  };
  // Ein geteiltes Stylesheet; `replaceSync` legt den Text nur ab.
  globalThis.CSSStyleSheet = class {
    replaceSync(text) {
      this.text = String(text);
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
      (this._warten.get(name) || []).forEach((loesen) => loesen(klasse));
      this._warten.delete(name);
    },
    // Registrierte Elemente stehen sofort bereit; auf die übrigen wird
    // gewartet, wie es der Browser auch tut.
    _warten: new Map(),
    whenDefined(name) {
      const da = this._klassen.get(name);
      if (da) return Promise.resolve(da);
      return new Promise((loesen) => {
        const liste = this._warten.get(name) || [];
        liste.push(loesen);
        this._warten.set(name, liste);
      });
    },
  };
  globalThis.window = globalThis;
  // Der Browserspeicher, in dem der zuletzt gewählte Farbsatz liegt.
  const speicher = new Map();
  globalThis.localStorage = {
    getItem: (schluessel) => (speicher.has(schluessel) ? speicher.get(schluessel) : null),
    setItem: (schluessel, wert) => speicher.set(schluessel, String(wert)),
    removeItem: (schluessel) => speicher.delete(schluessel),
  };
  const austragen = (liste, kennung) => {
    const stelle = liste.findIndex((eintrag) => eintrag.kennung === kennung);
    if (stelle >= 0) liste.splice(stelle, 1);
  };
  globalThis.setTimeout = (ruf, ms) => {
    const kennung = ++naechsteKennung;
    auftraege.push({ ruf, ms, kennung });
    return kennung;
  };
  globalThis.clearTimeout = (kennung) => austragen(auftraege, kennung);
  // Ein Takt läuft nur, wenn der Test ihn ausdrücklich anstößt.
  const takte = [];
  globalThis.setInterval = (ruf, ms) => {
    const kennung = ++naechsteKennung;
    takte.push({ ruf, ms, kennung });
    return kennung;
  };
  globalThis.clearInterval = (kennung) => austragen(takte, kennung);
  globalThis.requestAnimationFrame = (ruf) => {
    const kennung = ++naechsteKennung;
    bilder.push({ ruf, kennung });
    return kennung;
  };
  globalThis.cancelAnimationFrame = (kennung) => austragen(bilder, kennung);

  return {
    /** Alle wartenden Zeitaufträge und Bilder ausführen – ohne echte Wartezeit. */
    zeitLaufenLassen() {
      while (auftraege.length || bilder.length) {
        if (bilder.length) bilder.shift().ruf(0);
        else auftraege.shift().ruf();
      }
    },
    /** Nur die vorgemerkten Bilder zeichnen. */
    bilderLaufenLassen() {
      while (bilder.length) bilder.shift().ruf(0);
    },
    offeneAuftraege: () => auftraege.length,
    offeneBilder: () => bilder.length,
    offeneTakte: () => takte.length,
  };
}

export { Knoten };
