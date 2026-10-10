/**
 * Die Karten der Übersicht im Node-Durchlauf: Anmeldung, Editor-Schema,
 * Aufbau mit und ohne Zustände. Ausgabe ist eine Bilanz als JSON.
 */

import { browserAttrappe } from "./dom-attrappe.mjs";

const [, , modulPfad, schaubildPfad] = process.argv;
browserAttrappe();

const bilanz = {};
const NAMEN = ["heatnexus-leitwert", "heatnexus-kennwerte", "heatnexus-puffer"];

// Die Schaubild-Datei bringt die Karten mit: Eine Ressource reicht.
await import(schaubildPfad);
bilanz.ueberSchaubildGeladen = NAMEN.filter((n) => customElements.get(n));
const modul = await import(modulPfad);
bilanz.inKartenauswahl = NAMEN.filter((n) => (window.customCards || []).some((k) => k.type === n));

bilanz.stub = {};
bilanz.formular = {};
for (const name of NAMEN) {
  const Klasse = customElements.get(name);
  const stub = Klasse.getStubConfig();
  bilanz.stub[name] = stub.type === `custom:${name}`;
  const form = Klasse.getConfigForm();
  bilanz.formular[name] = form.schema.map((f) => f.name);
}

function text(knoten) {
  return knoten.textContent;
}

function karte(name, config, hass) {
  const el = document.createElement(name);
  el.setConfig(config);
  if (hass) el.hass = hass;
  return el;
}

const LEITWERT = {
  type: "custom:heatnexus-leitwert",
  ueberschrift: "PuroWIN",
  zustand: "sensor.phase",
  gross: "sensor.kessel",
  gross_name: "Kessel",
  aktiv: ["Modulation"],
  neben: [{ name: "Leistung", entity: "sensor.leistung", stellen: 0 }],
};
const KENNWERTE = {
  type: "custom:heatnexus-kennwerte",
  titel: "Speicher",
  werte: [
    { name: "Vorlauf", entity: "sensor.vorlauf" },
    { name: "Asche", entity: "sensor.asche", stellen: 0, warnung_unter: 20 },
    { name: "Pumpe", entity: "binary_sensor.pumpe", art: "schalter", an: "läuft", aus: "aus" },
    { name: "Drehzahl", entity: "sensor.drehzahl", stellen: 0, art: "schalter", an: "läuft", aus: "aus" },
  ],
};
const PUFFER = {
  type: "custom:heatnexus-puffer",
  titel: "Puffer",
  oben: "sensor.oben",
  name_oben: "Oben",
  mitte: null,
  name_mitte: "Mitte",
  unten: "sensor.unten",
  name_unten: "Unten",
  neben: [{ name: "Ladepumpe", entity: "sensor.ladepumpe" }],
};

// Ohne jede Entität: Die Karten zeichnen Striche statt zu scheitern.
const leer = { states: {}, language: "de", locale: { language: "de" } };
bilanz.ohneEntitaeten = {};
for (const [name, config] of [
  ["heatnexus-leitwert", LEITWERT],
  ["heatnexus-kennwerte", KENNWERTE],
  ["heatnexus-puffer", PUFFER],
]) {
  try {
    const el = karte(name, config, leer);
    bilanz.ohneEntitaeten[name] = text(el.shadowRoot).includes("–");
  } catch (fehler) {
    bilanz.ohneEntitaeten[name] = `Fehler: ${fehler.message}`;
  }
}

// Konfiguration ohne `hass` und eine leere Konfiguration.
try {
  karte("heatnexus-kennwerte", { type: "custom:heatnexus-kennwerte" });
  karte("heatnexus-puffer", { type: "custom:heatnexus-puffer" }, leer);
  karte("heatnexus-leitwert", { type: "custom:heatnexus-leitwert" }, leer);
  bilanz.leereKonfiguration = true;
} catch (fehler) {
  bilanz.leereKonfiguration = `Fehler: ${fehler.message}`;
}

const zustand = (state, attributes = {}) => ({ state, attributes });
const hass = {
  language: "de",
  locale: { language: "de" },
  states: {
    "sensor.phase": zustand("Modulation"),
    "sensor.kessel": zustand("71.4", { unit_of_measurement: "°C" }),
    "sensor.leistung": zustand("54.6", { unit_of_measurement: "%" }),
    "sensor.vorlauf": zustand("45.24", { unit_of_measurement: "°C" }),
    "sensor.asche": zustand("12", { unit_of_measurement: "h" }),
    "binary_sensor.pumpe": zustand("on"),
    "sensor.drehzahl": zustand("80", { unit_of_measurement: "%" }),
    "sensor.oben": zustand("68.0", { unit_of_measurement: "°C" }),
    "sensor.unten": zustand("31.0", { unit_of_measurement: "°C" }),
    "sensor.ladepumpe": zustand("unavailable"),
  },
};

const leitwert = karte("heatnexus-leitwert", LEITWERT, hass);
bilanz.leitwertText = text(leitwert.shadowRoot);
const zustandFeld = leitwert.shadowRoot.querySelector(".zustand");
bilanz.leitwertAktiv = !!zustandFeld && !!zustandFeld.style.color;

const kennwerte = karte("heatnexus-kennwerte", KENNWERTE, hass);
const zellen = kennwerte.shadowRoot.querySelectorAll(".wert");
bilanz.kennwerte = zellen.map((z) => z.textContent);
bilanz.warnfarbe = !!zellen[1].style.color;
bilanz.ohneWarnfarbe = !zellen[0].style.color;

const puffer = karte("heatnexus-puffer", PUFFER, hass);
bilanz.pufferText = text(puffer.shadowRoot);
const saeule = puffer.shadowRoot.querySelector(".saeule");
bilanz.saeuleVerlauf = !!saeule && String(saeule.style.background).startsWith("linear-gradient");

// Ein Klick öffnet den Verlauf der Entität.
let geoeffnet = null;
kennwerte.addEventListener("hass-more-info", (e) => {
  geoeffnet = e.detail.entityId;
});
zellen[0].parentElement.ausloesen("click");
bilanz.klickOeffnet = geoeffnet;

// Hilfen: Zahl im Format der Sprache, Wärmefarbe.
bilanz.anzeige = modul.anzeige(hass, "sensor.vorlauf");
bilanz.anzeigeFehlt = modul.anzeige(hass, "sensor.gibt_es_nicht");

process.stdout.write(JSON.stringify(bilanz));
