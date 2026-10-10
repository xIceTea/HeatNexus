/**
 * Zwei Anlagen in zwei Sprachen aufbauen und die Texte je Bereich ausgeben.
 *
 * Aufruf: `node sprachen-durchlauf.mjs <panel.js> <daten.json>`
 * Bereiche: Rahmen, Anlagenteil mit `lang`, Fenster. Ansichten: Seite der zweiten Anlage, „Alle“.
 */

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel, pfadDaten] = process.argv.slice(2);
browserAttrappe();
const daten = JSON.parse(readFileSync(pfadDaten, "utf-8"));

// Wie im Browser: Eingebaute Methoden des Elements verweigern jeden anderen Empfänger.
let flaeche = null;
const { dispatchEvent } = HTMLElement.prototype;
HTMLElement.prototype.dispatchEvent = function (ereignis) {
  if (this !== flaeche) throw new TypeError("Illegal invocation");
  return dispatchEvent.call(this, ereignis);
};

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];

const states = {};
const sammeln = (wert) => {
  if (Array.isArray(wert)) return wert.forEach(sammeln);
  if (!wert || typeof wert !== "object") return;
  Object.values(wert).forEach((inhalt) => {
    if (typeof inhalt === "string" && /^[a-z_]+\.[a-z0-9_]+$/.test(inhalt)) {
      const bereich = inhalt.split(".")[0];
      states[inhalt] = {
        entity_id: inhalt,
        state: bereich === "binary_sensor" || bereich === "switch" ? "on" : "21.5",
        attributes: { friendly_name: inhalt, unit_of_measurement: "°C", stoerung_aktiv: false },
      };
    } else sammeln(inhalt);
  });
};
sammeln(daten);

flaeche = new klasse();
const geoeffnet = [];
flaeche.addEventListener("hass-more-info", (ereignis) => geoeffnet.push(ereignis.detail.entityId));
flaeche.hass = {
  states,
  callWS: async () => ({}),
  callService: async () => true,
  formatEntityState: (zustand) => `${zustand.state} °C`,
};
flaeche.panel = { config: { daten } };
flaeche._texte = daten.texte || {};

const MERKMALE = ["title", "aria-label", "placeholder"];
/** Texte eines Teilbaums, getrennt nach Rahmen, Anlage mit eigener Sprache und Fenster. */
const texte = (wurzel, ablage, bereich = "rahmen") => {
  if (wurzel.tagName === "STYLE" || wurzel.tagName === "SCRIPT") return;
  if (wurzel.getAttribute("lang")) bereich = "anlage";
  if (wurzel.classList.contains("schleier")) bereich = "fenster";
  MERKMALE.forEach((merkmal) => {
    const wert = wurzel.getAttribute(merkmal);
    if (typeof wert === "string" && wert.trim()) ablage[bereich].add(wert.trim());
  });
  if (!wurzel.children.length) {
    const text = String(wurzel.textContent || "").trim();
    if (text) ablage[bereich].add(text);
    return;
  }
  wurzel.children.forEach((kind) => texte(kind, ablage, bereich));
};
const neu = () => ({ rahmen: new Set(), anlage: new Set(), fenster: new Set() });
const alsListen = (ablage) =>
  Object.fromEntries(Object.entries(ablage).map(([k, v]) => [k, [...v].sort()]));

const ergebnis = { seite: neu(), alle: neu() };

// Die Seite der zweiten Anlage, Reiter für Reiter; die Automatik spricht die gemeinsame Sprache.
flaeche._anlageIndex = 1;
for (const reiter of ["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme", "hilfe"]) {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  texte(flaeche.shadowRoot, ergebnis.seite);
}

// Ein Fenster und eine Rückmeldung entstehen erst nach dem Aufbau.
flaeche._reiter = "uebersicht";
flaeche._gebaut = false;
flaeche._zeichnen();
const bereich = flaeche.shadowRoot.querySelector("[lang]");
ergebnis.lang = bereich && bereich.getAttribute("lang");
bereich.querySelector(".fragezeichen").ausloesen("click");
texte(flaeche.shadowRoot, ergebnis.seite);
bereich.querySelector(".klickbar").ausloesen("click");
ergebnis.geoeffnet = geoeffnet;

const sicht = flaeche._sicht(daten.anlagen[1]);
const anzeige = document.createElement("div");
let bestaetigt = false;
await sicht._uebertragen(anzeige, async () => {}, () => bestaetigt);
bestaetigt = true;
flaeche._aktualisieren();
ergebnis.rueckmeldung = anzeige.textContent;

// „Alle“: beide Anlagen untereinander, jede in ihrer Sprache.
flaeche._anlageIndex = -1;
for (const reiter of ["uebersicht", "steuerung", "wartung"]) {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  texte(flaeche.shadowRoot, ergebnis.alle);
}

console.log(
  JSON.stringify({
    seite: alsListen(ergebnis.seite),
    alle: alsListen(ergebnis.alle),
    lang: ergebnis.lang,
    geoeffnet: ergebnis.geoeffnet,
    rueckmeldung: ergebnis.rueckmeldung,
  })
);
