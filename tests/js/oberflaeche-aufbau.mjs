/**
 * Jeden Reiter der Oberfläche mit echten Panel-Daten und Zuständen aufbauen.
 *
 * Aufruf: `node oberflaeche-aufbau.mjs <panel.js> <eingabe.json>`
 * Eingabe: `{ daten, states }` aus einer eingerichteten Anlage. Ausgabe: Karten
 * je Reiter. Jede Ausnahme und jede Meldung auf `console.error` bricht ab.
 */

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel, pfadEingabe] = process.argv.slice(2);
browserAttrappe();

const fehler = [];
const meldeFehler = console.error;
console.error = (...teile) => {
  fehler.push(teile.map(String).join(" "));
  meldeFehler(...teile);
};
// Ohne Server scheitern die Nachladeaufrufe; das ist hier gewollt und keine Störung.
console.warn = () => {};

const { daten, states } = JSON.parse(readFileSync(pfadEingabe, "utf-8"));

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

const hass = {
  states,
  language: "de",
  locale: { language: "de" },
  callWS: async () => {
    throw new Error("kein Server im Test");
  },
  callService: async () => true,
  formatEntityState: (zustand) => String(zustand.state),
};

const flaeche = new klasse();
flaeche.panel = { config: { daten } };
flaeche.hass = hass;

const bilanz = {};
for (const reiter of ["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme"]) {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  bilanz[reiter] = { karten: flaeche.shadowRoot.querySelectorAll(".karte").length };
}
for (let runde = 0; runde < 8; runde++) await Promise.resolve();

if (fehler.length) {
  meldeFehler(`Fehler beim Aufbau:\n${fehler.join("\n")}`);
  process.exit(1);
}
console.log(JSON.stringify(bilanz));
process.exit(0);
