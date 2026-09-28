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

// Die Automatik mit festen Daten; ihre Sätze übersetzt schon der Server.
const anlageId = (daten.anlagen[0] || {}).id;
const stunden = Array.from({ length: 24 }, (_, stunde) => ({
  stunde,
  at: 10,
  korrigiert: 11,
  gedaempft: 12,
  raum: 21,
  aktion: stunde > 11 ? "nur_ww" : "programm",
  vorrang: stunde === 12,
}));
flaeche._automatik = {
  darf_aendern: true,
  profile: { standard: { sonnenquote: 60 } },
  heizkreise: [
    {
      heizkreis: "SN1-2-0",
      name: "Heizkreis",
      anlage_id: anlageId,
      eingerichtet: true,
      konfig: { aktiv: true, modus: "beobachten", profil: "standard", heizflaechen: "gemischt", ausrichtung: "eco" },
      werte: { sonnenquote: 55, stark: true, anpassen: true, lernfenster: 7 },
      zustand: "nur_ww",
      begruendung: "Sunny day – 21,0 °C until 16:54.",
      kennwerte: {
        at: 14, at_gedaempft: 15, heizgrenze: 18, grenze_steuerung: 18, grenze_absenk: 5, hysterese: 1,
        sonnenquote: 70, sonne_schwelle: 55, stark_quote: 80, stark_k: 1, rueckkehr_k: 0.5, sonne_raum_k: 0.5,
        abweichung: 0.4, raum: 21.4, soll: 21, eigene_ziele: true, raum_art: "minimum", eingriffe: 1, budget: 4,
        naechste_pruefung: "2026-09-28T07:00:00+02:00", modus_seit: "2026-09-28T11:00:00+02:00",
        vorrang: { laeuft: false, minuten: 90 },
        raeume: [
          { entity_id: "climate.bad", name: "Bath", wert: 20.8, ziel: 21, heizt: true },
          { entity_id: "sensor.alt", name: "Old", wert: 19, veraltet: true },
        ],
      },
      tag: { sonne: [0, 0.5, 0], stunden, jetzt: 12.5 },
      vorschau: [{ titel: "Morgen", begruendung: "Heating by program.", tag: { stunden } }],
      korrektur: { an: true, noetig: 7, temperatur: { versatz: null, tage: 2 }, sonne: { aktiv: true, faktor: 1.1, tage: 8 } },
      protokoll: [
        { zeit: new Date().toISOString(), art: "geschrieben", text: "Sunny day – 21,0 °C until 16:54." },
        { zeit: "2026-09-20T07:00:00+02:00", art: "haette", text: "Sunny day over – back to the program." },
      ],
      beobachtet_seit: "2026-09-20T07:00:00+02:00",
    },
    { heizkreis: "SN1-3-0", name: "Heizkreis 2", anlage_id: anlageId, eingerichtet: false },
  ],
};
flaeche._automatikZeit = Date.now();
flaeche._automatikOffen = new Set(["SN1-2-0"]);

["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme", "automatik"].forEach((reiter) => {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  gehe(flaeche.shadowRoot);
});

clearInterval(flaeche._automatikUhr);
console.log(JSON.stringify([...texte].sort()));
