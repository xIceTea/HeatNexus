/**
 * Die Oberfläche einmal komplett aufbauen – in Node, ohne Browser.
 *
 * Aufruf: `node oberflaeche-durchlauf.mjs <panel.js> <daten.json>`
 *
 * Die Aufteilung kommt aus der **echten** Serverseite (`panel/daten.py`), der
 * Test schreibt sie vorher als JSON heraus. Damit prüft dieser Durchlauf
 * beides zugleich: dass der Browser mit dem umgeht, was der Server liefert.
 *
 * Ausgegeben wird eine Bilanz je Reiter. Ein Fehler beim Aufbau bricht den
 * Lauf ab – genau darum geht es.
 */

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel, pfadDaten] = process.argv.slice(2);
const zeit = browserAttrappe();
const daten = JSON.parse(readFileSync(pfadDaten, "utf-8"));

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

// ---------------------------------------------------------------------------
// Zustände: zu jeder Entität, die in der Aufteilung vorkommt, einen Wert
// ---------------------------------------------------------------------------
const entitaeten = new Set();
const sammeln = (wert) => {
  if (Array.isArray(wert)) return wert.forEach(sammeln);
  if (!wert || typeof wert !== "object") return;
  Object.entries(wert).forEach(([schluessel, inhalt]) => {
    if (typeof inhalt === "string" && /^[a-z_]+\.[a-z0-9_]+$/.test(inhalt)) entitaeten.add(inhalt);
    else sammeln(inhalt);
    if (schluessel === "entity" && typeof inhalt === "string") entitaeten.add(inhalt);
  });
};
sammeln(daten);

const zeitprogramme = new Set(
  (daten.anlagen || []).flatMap((anlage) => (anlage.zeitprogramme || []).map((p) => p.entity))
);

// Werte, die nur über null etwas bedeuten – die Wärmeanforderung des
// Pumpen-/Relaismoduls. Sie stehen im Durchlauf auf null, damit sich prüfen
// lässt, dass ihre Zeile dann verschwindet.
const ohneAnforderung = new Set(
  (daten.anlagen || []).flatMap((anlage) =>
    (anlage.kennwerte || []).filter((k) => k.nur_ueber_null).map((k) => k.entity)
  )
);

const states = {};
entitaeten.forEach((entity) => {
  const bereich = entity.split(".")[0];
  states[entity] = {
    entity_id: entity,
    state: bereich === "binary_sensor" || bereich === "switch" ? "on" : "21.5",
    attributes: {
      friendly_name: entity,
      unit_of_measurement: "°C",
      options: ["Standby", "Programm 1", "Heizbetrieb"],
      temperature: 21.5,
      current_temperature: 20.8,
      target_temp_step: 0.5,
      preset_mode: "1",
      preset_modes: ["0", "1", "2"],
      hvac_action: "heating",
      override_aktiv: false,
      override_restzeit_min: 0,
      stoerung_aktiv: false,
      meldungen: [{ code: 346, kind: "Fehler", text: "Verkleidungstür offen", info: "schließen" }],
    },
  };
  if (ohneAnforderung.has(entity)) states[entity].state = "0";
  if (zeitprogramme.has(entity)) {
    states[entity].state = "täglich: 06:00→21°";
    states[entity].attributes.blocks = [
      {
        weekdays: ["Mo", "Tu", "We", "Th", "Fr"],
        switchPoints: [
          { time: "06:00", value: 21 },
          { time: "22:00", value: 16 },
        ],
      },
      { weekdays: ["Sa", "Su"], switchPoints: [{ time: "07:30", value: 21 }] },
    ];
  }
});

const gerufeneDienste = [];
const hass = {
  states,
  callWS: async () => {
    throw new Error("kein Server im Test");
  },
  callService: async (bereich, dienst, angaben) => {
    gerufeneDienste.push(`${bereich}.${dienst}`);
    return true;
  },
  formatEntityState: (zustand) => `${zustand.state} °C`,
};

// ---------------------------------------------------------------------------
// Aufbau je Reiter
// ---------------------------------------------------------------------------
const flaeche = new klasse();
flaeche.hass = hass;
flaeche.panel = { config: { daten } };

const bilanz = {};
const REITER = ["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme"];
REITER.forEach((reiter) => {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  const zeilen = flaeche.shadowRoot.querySelectorAll(".zeile");
  bilanz[reiter] = {
    karten: flaeche.shadowRoot.querySelectorAll(".karte").length,
    bindungen: flaeche._bindungen.length,
    zeilen: zeilen.length,
    versteckteZeilen: zeilen.filter((zeile) => zeile.hidden).length,
  };
});

// ---------------------------------------------------------------------------
// Farbsatz des Schaubilds
//
// Die Zeichnung liegt als Daten-URL in einem `<img>` und erbt darin kein CSS.
// Beide Fassungen kommen deshalb mit; gewählt wird hier, bei jedem Abgleich.
// ---------------------------------------------------------------------------
flaeche._reiter = "uebersicht";
flaeche._gebaut = false;
flaeche._zeichnen();
flaeche._aktualisieren();
// Zwei Schritte, weil die Attrappe nur einfache Wähler kennt.
const huelle = flaeche.shadowRoot.querySelector(".schaubild");
const schaubild = huelle ? huelle.querySelector("img") : null;
const beiDunkel = schaubild ? schaubild.src : null;
hass.themes = { darkMode: false };
flaeche._aktualisieren();
bilanz.schaubild = { dunkel: beiDunkel, hell: schaubild ? schaubild.src : null };

// Anordnen-Modus: eigener Zweig mit Griffen, Menü und Speicherauftrag.
flaeche._reiter = "uebersicht";
flaeche._anordnen = true;
flaeche._gebaut = false;
flaeche._zeichnen();
bilanz.anordnen = { griffe: flaeche.shadowRoot.querySelectorAll(".anordner-griff").length };
flaeche._anordnen = false;

// ---------------------------------------------------------------------------
// Bedienen: der Weg von der Taste bis zum Aufräumen der Rückmeldung
// ---------------------------------------------------------------------------
const anzeige = document.createElement("div");
anzeige.className = "rueckmeldung";
let bestaetigt = false;
await flaeche._uebertragen(
  anzeige,
  () => hass.callService("climate", "set_temperature", {}),
  () => bestaetigt,
  "climate.pruefung"
);
const beiUebertragung = anzeige.textContent;
bestaetigt = true;
flaeche._pruefeWartende();
const nachBestaetigung = anzeige.textContent;
// Erst hier räumt die Anzeige sich auf – und genau dabei ist beim Schnitt in
// ES-Module eine nicht ausgeführte Konstante aufgefallen.
zeit.zeitLaufenLassen();

bilanz.bedienen = {
  dienste: gerufeneDienste,
  waehrend: beiUebertragung,
  bestaetigt: nachBestaetigung,
  aufgeraeumt: anzeige.textContent,
};

console.log(JSON.stringify(bilanz));
