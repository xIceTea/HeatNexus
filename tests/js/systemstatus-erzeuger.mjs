/**
 * Der Systemstatus ab zwei Erzeugern: Kopfzeile je Erzeuger, auf- und zuklappbar.
 *
 * Aufruf: `node systemstatus-erzeuger.mjs <panel.js>`
 *
 * Ausgegeben wird je Fall ein Eintrag; ein Fehlschlag bricht ab.
 */

import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
browserAttrappe();

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

const zustand = (entity_id, state, unit) => ({
  entity_id,
  state,
  attributes: unit ? { unit_of_measurement: unit } : {},
});

const ANLAGE = {
  name: "Hybrid",
  status: [{ entity: "sensor.aussen", titel: "Außentemperatur", symbol: "mdi:thermometer" }],
  erzeuger: [
    {
      id: "aero",
      name: "AeroWIN",
      kopf: [
        { entity: "sensor.wp_phase", titel: "Betriebszustand", symbol: "mdi:state-machine" },
        { entity: "sensor.wp_leistung", titel: "Leistung", symbol: "mdi:gauge" },
        { entity: "sensor.wp_cop", titel: "COP aktuell", symbol: "mdi:speedometer", vorsatz: "COP" },
      ],
      zeilen: [{ entity: "sensor.wp_starts", titel: "Starts", symbol: "mdi:restart" }],
    },
    {
      id: "bio",
      name: "BioWIN",
      kopf: [
        { entity: "sensor.bio_phase", titel: "Betriebszustand", symbol: "mdi:state-machine" },
        { entity: "sensor.bio_fehlt", titel: "Kesselleistung", symbol: "mdi:fire" },
      ],
      zeilen: [{ entity: "sensor.bio_abgas", titel: "Abgastemperatur", symbol: "mdi:smoke" }],
    },
  ],
};

function panelBauen({ alle = false, einstellungen = {} } = {}) {
  const element = new klasse();
  const gespeichert = [];
  element._hass = {
    states: Object.fromEntries(
      [
        zustand("sensor.aussen", "8.8", "°C"),
        zustand("sensor.wp_phase", "Heizen"),
        zustand("sensor.wp_leistung", "62", "%"),
        zustand("sensor.wp_cop", "3.6"),
        zustand("sensor.wp_starts", "13791"),
        zustand("sensor.bio_phase", "Standby"),
        zustand("sensor.bio_fehlt", "unavailable"),
        zustand("sensor.bio_abgas", "18.3", "°C"),
      ].map((z) => [z.entity_id, z])
    ),
    callWS: async (nachricht) => {
      gespeichert.push(nachricht);
      return {};
    },
    callService: async () => {},
  };
  element._daten = { anlagen: [ANLAGE, { ...ANLAGE, name: "Zweite" }] };
  element._anlageIndex = alle ? -1 : 0;
  element._anordnung = { einstellungen };
  element._bindungen = [];
  const karte = element._statuskarte(ANLAGE);
  element._bindungen.forEach((binden) => binden());
  return { element, karte, gespeichert };
}

const bloecke = (karte) => karte.querySelectorAll(".status-erzeuger");
const kopftext = (block) => block.querySelector(".erzeuger-werte").textContent;
const ergebnis = {};

{
  const { karte } = panelBauen();
  const [aero, bio] = bloecke(karte);
  ergebnis.namen = bloecke(karte).map((b) => b.querySelector(".erzeuger-name").textContent);
  ergebnis.kopf_aero = kopftext(aero);
  ergebnis.kopf_bio = kopftext(bio);
  ergebnis.offen_je_anlage = bloecke(karte).map((b) => b.open);
  ergebnis.zeilen_aero = aero.querySelectorAll(".status-zeile").map((z) => z.querySelector(".titel").textContent);
  ergebnis.oben = karte.children
    .filter((k) => k.className === "status-zeile" || String(k.className).startsWith("status-zeile "))
    .map((z) => z.querySelector(".titel").textContent);
}
{
  const { karte } = panelBauen({ alle: true });
  ergebnis.offen_unter_alle = bloecke(karte).map((b) => b.open);
}
{
  const { karte } = panelBauen({ einstellungen: { erzeuger: { "anlage:bio": false } } });
  ergebnis.gemerkt = bloecke(karte).map((b) => b.open);
}
{
  const { karte, gespeichert } = panelBauen();
  const [aero] = bloecke(karte);
  aero.dispatchEvent(new CustomEvent("toggle"));
  ergebnis.ohne_klick_gespeichert = gespeichert.length;
  aero.open = false;
  aero.dispatchEvent(new CustomEvent("toggle"));
  await Promise.resolve();
  ergebnis.nach_klick = gespeichert.map((n) => n.einstellungen);
}

process.stdout.write(JSON.stringify(ergebnis));
