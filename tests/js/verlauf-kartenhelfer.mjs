/**
 * Verlauf ohne vorher geöffnetes Dashboard: Die Kartenhelfer werden nachgeladen.
 *
 * Aufruf: `node verlauf-kartenhelfer.mjs <panel.js>`. Ausgabe: JSON mit den geprüften Fällen.
 */

import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
browserAttrappe();

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

const geladen = [];
// Wie in Home Assistant: Erst das Dashboard-Modul setzt `window.loadCardHelpers`.
globalThis.customElements.define(
  "partial-panel-resolver",
  class {
    _getRoutes(panels) {
      const routes = {};
      for (const panel of panels) {
        routes[panel.url_path] = {
          load: async () => {
            geladen.push(panel.component_name);
            window.loadCardHelpers = async () => ({
              createCardElement: (konfig) => Object.assign(document.createElement("div"), { konfig }),
            });
          },
        };
      }
      return { routes };
    }
  }
);

const faelle = [];
delete window.loadCardHelpers;
const element = new klasse();
element._hass = { states: {} };
element._verlaufskarten = [];
const platz = document.createElement("div");
platz.dataset.stunden = "48";
await element._verlaufNeuLaden(platz, new Set(["sensor.kessel"]));
const karte = element._verlaufskarten[0];
if (geladen.join() !== "lovelace") throw new Error(`Dashboard-Modul nicht geladen: ${geladen}`);
if (!karte || karte.konfig.type !== "history-graph") throw new Error("Keine Verlaufskarte gebaut");
if (JSON.stringify(karte.konfig.entities) !== '["sensor.kessel"]') throw new Error("Falsche Linien");
faelle.push("ohne Dashboard: Kartenhelfer nachgeladen, Verlaufskarte gebaut");

await element._verlaufNeuLaden(platz, new Set(["sensor.puffer"]));
if (geladen.length !== 1) throw new Error("Dashboard-Modul doppelt geladen");
faelle.push("zweiter Aufruf: Kartenhelfer stehen schon bereit");

console.log(JSON.stringify({ faelle }));
