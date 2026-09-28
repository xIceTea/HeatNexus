/**
 * Die Oberfläche auf Englisch aufbauen und jeden sichtbaren Text ausgeben.
 *
 * Aufruf: `node englisch-durchlauf.mjs <panel.js> <daten.json>`
 *
 * Die Daten tragen das Wörterbuch unter `texte`, wie der Server es mitgibt.
 * Ausgegeben werden Texte und die Merkmale title, aria-label und placeholder
 * nach Aufbau und Aktualisierung; der Test sucht darin deutsche Reste.
 */

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel, pfadDaten] = process.argv.slice(2);
browserAttrappe();
const daten = JSON.parse(readFileSync(pfadDaten, "utf-8"));

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];

const entitaeten = new Set();
const sammeln = (wert) => {
  if (Array.isArray(wert)) return wert.forEach(sammeln);
  if (!wert || typeof wert !== "object") return;
  Object.values(wert).forEach((inhalt) => {
    if (typeof inhalt === "string" && /^[a-z_]+\.[a-z0-9_]+$/.test(inhalt)) entitaeten.add(inhalt);
    else sammeln(inhalt);
  });
};
sammeln(daten);

const states = {};
entitaeten.forEach((entity) => {
  const bereich = entity.split(".")[0];
  states[entity] = {
    entity_id: entity,
    state: bereich === "binary_sensor" || bereich === "switch" ? "on" : "21.5",
    attributes: {
      friendly_name: entity,
      unit_of_measurement: "°C",
      stoerung_aktiv: false,
      // Ein Schaltprogramm, damit das Wochenraster Ein und Aus beschriftet.
      blocks: [
        {
          weekdays: ["Mo"],
          switchPoints: [
            { time: "05:00", value: 1 },
            { time: "08:00", value: 0 },
          ],
        },
      ],
    },
  };
});

const flaeche = new klasse();
flaeche.hass = {
  states,
  callWS: async () => ({}),
  callService: async () => true,
  formatEntityState: (zustand) => `${zustand.state} °C`,
};
flaeche.panel = { config: { daten } };
// Wie nach `_datenHolen`: Das Wörterbuch kommt mit der Nutzlast.
flaeche._texte = daten.texte || {};

const MERKMALE = ["title", "aria-label", "placeholder"];
const texte = new Set();
const gehe = (knoten) => {
  if (knoten.tagName === "STYLE" || knoten.tagName === "SCRIPT") return;
  MERKMALE.forEach((merkmal) => {
    const wert = knoten.getAttribute(merkmal) || knoten[merkmal];
    if (typeof wert === "string" && wert.trim()) texte.add(wert.trim());
  });
  if (!knoten.children.length) {
    const text = String(knoten.textContent || "").trim();
    if (text) texte.add(text);
    return;
  }
  knoten.children.forEach(gehe);
};

["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme"].forEach((reiter) => {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  gehe(flaeche.shadowRoot);
});

console.log(JSON.stringify([...texte].sort()));
