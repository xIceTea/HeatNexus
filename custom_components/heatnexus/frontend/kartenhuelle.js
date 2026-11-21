/**
 * Hülle und Umsetzung der Lovelace-Karten: Unter dem festen Namen steht eine Hülle,
 * gezeichnet wird von einem Element, dessen Name die Fassung trägt.
 */

// Stand des Vertrags zwischen Hülle und Umsetzung. Die Hülle bleibt für die Seitensitzung;
// verlangt der Server einen höheren Stand, zeigt sie den Hinweis zum Neuladen.
const VERTRAG = 1;
const ABLAGE = "heatnexusKarten";
const EREIGNIS = "heatnexus-karten-wechsel";
const BEFEHL = "heatnexus/fassung";
// Was Home Assistant an einer Karte setzt; die Hülle reicht es an die Umsetzung weiter.
const EIGENSCHAFTEN = ["hass", "layout", "preview", "editMode", "isPanel"];
const WARTEZEIT_MS = 10000;
const VERSUCHE_MAX = 6;

const STIL = `
  :host { display: flex; flex-direction: column; }
  .meldung ~ * { flex: 1 1 auto; min-width: 0; }
  .meldung { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    margin-bottom: 8px; padding: 8px 12px; font-size: 14px; color: var(--primary-text-color);
    background: var(--ha-card-background, var(--card-background-color));
    border: 1px solid var(--warning-color, #f2b33d);
    border-radius: var(--ha-card-border-radius, 12px); }
  .meldung:empty { display: none; }
  button { font: inherit; cursor: pointer; padding: 4px 12px; border: 0; border-radius: 16px;
    color: var(--text-primary-color, #fff); background: var(--primary-color, #03a9f4); }
`;

/** Die Fassung aus der Adresse eines Moduls; liegt es nicht im Ordner einer Fassung, keine. */
export function fassungAus(adresse) {
  const pfad = String(adresse).split(/[?#]/)[0];
  const treffer = pfad.match(/\/heatnexus-(?:karte-|frontend\/)([^/]+)\/[^/]+$/);
  return treffer && /^[a-z0-9-]+$/i.test(treffer[1]) ? treffer[1] : null;
}

export const FASSUNG = fassungAus(import.meta.url);

/** Der Elementname für diese Fassung; ohne Fassung bleibt es der feste Name. */
export function elementname(name) {
  return FASSUNG ? `${name}-${FASSUNG.toLowerCase()}` : name;
}

// Die Ablage am Fenster teilen sich alle geladenen Fassungen: je Fassung die Elementnamen
// der Karten, dazu die Fassung, die gerade zeichnet, und der Hinweis zum Neuladen.
function ablage() {
  if (!window[ABLAGE]) window[ABLAGE] = { aktuell: null, fassungen: {}, hinweis: null };
  return window[ABLAGE];
}

/** Der Elementname der Umsetzung, die gerade zeichnet. */
function umsetzung(name) {
  const stand = ablage();
  return (stand.fassungen[stand.aktuell] || {})[name] || null;
}

function statisch(name, methode, angaben = []) {
  const element = umsetzung(name);
  const klasse = element ? customElements.get(element) : null;
  return klasse && typeof klasse[methode] === "function" ? klasse[methode](...angaben) : undefined;
}

let pruefung = null;
let verbindung = null;
let fehlversuche = 0;
let fruehestens = 0;
const versucht = new Set();

// Nach einem Neustart von Home Assistant kann eine andere Fassung laufen: neu fragen.
function beobachten(neu) {
  if (!neu || neu === verbindung || typeof neu.addEventListener !== "function") return;
  verbindung = neu;
  neu.addEventListener("ready", () => {
    pruefung = null;
    fehlversuche = 0;
    fruehestens = 0;
  });
}

/** Die Fassung des Servers erfragen, einmal je Verbindung. */
function pruefen(hass) {
  if (pruefung || !hass || typeof hass.callWS !== "function") return;
  if (fehlversuche > VERSUCHE_MAX || Date.now() < fruehestens) return;
  if (hass.config && hass.config.state && hass.config.state !== "RUNNING") return;
  beobachten(hass.connection);
  const abgelehnt = () => {
    // Solange Home Assistant startet, kennt der Server den Befehl noch nicht:
    // später erneut fragen, mit wachsendem Abstand.
    fehlversuche += 1;
    fruehestens = Date.now() + WARTEZEIT_MS * 2 ** (fehlversuche - 1);
    pruefung = null;
  };
  pruefung = hass
    .callWS({ type: BEFEHL })
    .then(angleichen, abgelehnt)
    .catch((err) => console.warn("HeatNexus: Fassung der Karten nicht abgeglichen", err));
}

/** Weicht die Fassung des Servers ab, ihr Modul laden und alle Hüllen umstellen. */
async function angleichen(antwort) {
  const ziel = antwort && antwort.fassung;
  if (!ziel) return;
  const stand = ablage();
  let nutzbar = ziel === stand.aktuell;
  if (!nutzbar && !(antwort.vertrag > VERTRAG)) {
    // Je Fassung ein Ladeversuch: Ein gescheitertes Modul lädt der Browser nicht erneut.
    if (!stand.fassungen[ziel] && antwort.karte && !versucht.has(ziel)) {
      versucht.add(ziel);
      try {
        await import(antwort.karte);
      } catch (err) {
        console.warn("HeatNexus: Kartenmodul der neuen Fassung konnte nicht geladen werden", err);
      }
    }
    nutzbar = !!stand.fassungen[ziel];
  }
  if (nutzbar && ziel === stand.aktuell && !stand.hinweis) return;
  if (nutzbar) stand.aktuell = ziel;
  stand.hinweis = nutzbar
    ? null
    : { text: antwort.hinweis || "HeatNexus", taste: antwort.neu_laden || "↻" };
  window.dispatchEvent(new CustomEvent(EREIGNIS));
}

/** Die Klasse der Hülle für einen festen Kartennamen. */
function huelle(name) {
  class Huelle extends HTMLElement {
    static getConfigElement() {
      return statisch(name, "getConfigElement");
    }

    static getConfigForm() {
      return statisch(name, "getConfigForm");
    }

    static getStubConfig(...angaben) {
      return statisch(name, "getStubConfig", angaben);
    }

    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._gesetzt = {};
      this._abgleich = () => this._abgleichen();
      const stil = document.createElement("style");
      stil.textContent = STIL;
      this._meldung = document.createElement("div");
      this._meldung.className = "meldung";
      this.shadowRoot.append(stil, this._meldung);
    }

    // Nur eingehängte Hüllen hören auf den Wechsel; beim Einhängen holen sie ihn nach.
    connectedCallback() {
      window.addEventListener(EREIGNIS, this._abgleich);
      this._abgleichen();
    }

    disconnectedCallback() {
      window.removeEventListener(EREIGNIS, this._abgleich);
    }

    setConfig(config) {
      const innen = this._umsetzung();
      innen.setConfig(config);
      const erste = !this._konfiguriert;
      this._config = config;
      this._konfiguriert = true;
      if (erste) this._weitergeben(innen);
    }

    getCardSize() {
      const innen = this._umsetzung();
      return typeof innen.getCardSize === "function" ? innen.getCardSize() : 1;
    }

    getGridOptions() {
      const innen = this._umsetzung();
      return typeof innen.getGridOptions === "function" ? innen.getGridOptions() : {};
    }

    get connectedWhileHidden() {
      return this._innen ? this._innen.connectedWhileHidden : undefined;
    }

    // Reihenfolge wie in Home Assistant: Die Umsetzung bekommt erst die Konfiguration,
    // dann die Eigenschaften.
    _setzen(feld, wert) {
      this._gesetzt[feld] = wert;
      if (this._innen && this._konfiguriert) this._innen[feld] = wert;
      if (feld === "hass") pruefen(wert);
    }

    _weitergeben(innen) {
      for (const feld of EIGENSCHAFTEN) {
        if (feld in this._gesetzt) innen[feld] = this._gesetzt[feld];
      }
    }

    /** Ein inneres Element aufbauen, mit dem Stand, den die Hülle schon kennt. */
    _aufbauen(element) {
      const innen = document.createElement(element);
      if (this._konfiguriert) {
        innen.setConfig(this._config);
        this._weitergeben(innen);
      }
      return innen;
    }

    _einsetzen(innen, element) {
      if (this._innen) this._innen.replaceWith(innen);
      else this.shadowRoot.appendChild(innen);
      this._innen = innen;
      this._element = element;
    }

    _umsetzung() {
      if (!this._innen) {
        const element = umsetzung(name);
        this._einsetzen(this._aufbauen(element), element);
      }
      return this._innen;
    }

    /** Auf die Umsetzung wechseln, die gerade gilt, und den Hinweis nachführen. */
    _abgleichen() {
      const element = umsetzung(name);
      if (this._innen && element && element !== this._element) {
        try {
          this._einsetzen(this._aufbauen(element), element);
        } catch (err) {
          // Weist die neue Umsetzung die Konfiguration ab, zeichnet die bisherige weiter.
          console.warn("HeatNexus: Karte bleibt bei der geladenen Fassung", err);
        }
      }
      this._hinweisZeigen();
    }

    _hinweisZeigen() {
      const hinweis = ablage().hinweis;
      if (!hinweis) {
        this._meldung.replaceChildren();
        return;
      }
      const text = document.createElement("span");
      text.textContent = hinweis.text;
      const taste = document.createElement("button");
      taste.type = "button";
      taste.textContent = hinweis.taste;
      taste.addEventListener("click", () => window.location.reload());
      this._meldung.replaceChildren(text, taste);
    }
  }
  for (const feld of EIGENSCHAFTEN) {
    Object.defineProperty(Huelle.prototype, feld, {
      configurable: true,
      get() {
        return this._gesetzt[feld];
      },
      set(wert) {
        this._setzen(feld, wert);
      },
    });
  }
  return Huelle;
}

/**
 * Eine Karte anmelden: die Umsetzung unter dem Namen mit Fassung, die Hülle unter dem festen.
 * Ohne Fassung in der Adresse steht die Umsetzung selbst unter dem festen Namen.
 */
export function anmelden(name, klasse) {
  const element = elementname(name);
  if (!customElements.get(element)) customElements.define(element, klasse);
  if (!FASSUNG) return;
  const stand = ablage();
  if (!stand.fassungen[FASSUNG]) stand.fassungen[FASSUNG] = {};
  stand.fassungen[FASSUNG][name] = element;
  if (!stand.aktuell) stand.aktuell = FASSUNG;
  if (!customElements.get(name)) customElements.define(name, huelle(name));
}
