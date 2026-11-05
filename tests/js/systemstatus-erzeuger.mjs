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
  heizkreise: [
    { titel: "Kreis 1", automatik: "sensor.kreis1_automatik" },
    { titel: "Kreis 2", automatik: "sensor.kreis2_automatik" },
  ],
  regelung: {
    hybrid: {
      betriebsart: "select.hybrid_art",
      lieferanten: [
        { name: "AeroWIN", entity: "sensor.wp_leistung" },
        { name: "BioWIN", entity: "sensor.bio_fehlt" },
      ],
    },
    zeilen: [{ entity: "sensor.sg", titel: "SG Ready", symbol: "mdi:transmission-tower" }],
    automatik: "sensor.automatik_status",
  },
};

function panelBauen({ alle = false, einstellungen = {}, kreis2 = "programm", anlage = ANLAGE } = {}) {
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
        zustand("select.hybrid_art", "Eco-Betrieb"),
        zustand("sensor.sg", "Normalbetrieb"),
        zustand("sensor.automatik_status", "beobachten"),
        zustand("sensor.kreis1_automatik", "programm"),
        zustand("sensor.kreis2_automatik", kreis2),
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
  element._zeichnen = () => {
    element.gezeichnet = true;
  };
  const karte = element._statuskarte(anlage);
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
  ergebnis.namen_roh = bloecke(karte).map((b) => b.querySelector(".erzeuger-name").dataset.roh === "");
  ergebnis.kopf_aero = kopftext(aero);
  ergebnis.kopf_bio = kopftext(bio);
  ergebnis.offen_je_anlage = bloecke(karte).map((b) => b.open);
  ergebnis.zeilen_aero = aero.querySelectorAll(".status-zeile").map((z) => z.querySelector(".titel").textContent);
  const abschnitt = karte.children.findIndex((k) => k.className === "status-abschnitt");
  ergebnis.oben = karte.children
    .slice(0, abschnitt)
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

{
  const { element, karte } = panelBauen();
  const kinder = karte.children;
  const stelle = kinder.findIndex((k) => k.className === "status-abschnitt");
  ergebnis.regelung = kinder.slice(stelle).map((k) =>
    k.className === "status-abschnitt"
      ? k.textContent
      : [k.querySelector(".titel").textContent, k.querySelector(".wert").textContent]
  );
  ergebnis.regelung_nach_erzeugern = kinder.slice(0, stelle).some((k) => k.tagName === "DETAILS");
  const automatik = kinder.at(-1);
  automatik.dispatchEvent(new CustomEvent("click"));
  ergebnis.klick_automatik = [element._reiter, element.gezeichnet === true];
}
{
  const { karte } = panelBauen({ kreis2: "sonnentag" });
  ergebnis.kreise_abweichend = karte.children.find((k) => k.querySelector && k.querySelector(".titel")?.textContent === "Heizkreise")
    .querySelector(".wert").textContent;
}
{
  const { karte } = panelBauen({ anlage: { ...ANLAGE, erzeuger: [], regelung: null } });
  ergebnis.ohne_regelung = karte.children.filter((k) => k.className === "status-abschnitt").length;
}

process.stdout.write(JSON.stringify(ergebnis));
