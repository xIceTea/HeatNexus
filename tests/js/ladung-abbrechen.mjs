/**
 * Abbrechen einer laufenden Warmwasserladung – der Tastendruck, nicht der Aufbau.
 *
 * Aufruf: `node ladung-abbrechen.mjs <panel.js>`
 *
 * **Der Anlass.** Bis 1.5.0 hing der Abbruchzweig zusätzlich an der
 * Betriebswahl und ihrem Rückkehrmuster. Fehlte eines von beiden, fiel der
 * Druck durch bis zum Auslöser und startete die Ladung noch einmal. Am Gerät
 * sah das aus, als passierte gar nichts: „lädt gerade" stand sofort wieder da.
 *
 * Geprüft wird deshalb genau das, was man von außen sieht: Welcher Dienst wird
 * gerufen, wenn die Ladung läuft – und welcher auf keinen Fall.
 *
 * Ausgegeben wird eine Zeile je Fall; ein Fehlschlag bricht ab.
 */

import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
browserAttrappe();

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

const BETRIEBSWAHL = "select.betriebswahl";
const AUSLOESER = "switch.ww_einmalladung";
const BETRIEBSART = "sensor.betriebsart";

/** Ein Panel mit nachgebildeten Zuständen und mitschreibendem Dienstaufruf. */
function panelBauen({ laedt, optionen, betriebswahl = BETRIEBSWAHL }) {
  const element = new klasse();
  const gerufen = [];
  element._hass = {
    states: {
      [BETRIEBSART]: {
        entity_id: BETRIEBSART,
        state: laedt ? "Warmwasser Einmalladung" : "Heizbetrieb",
        attributes: {},
      },
      [BETRIEBSWAHL]: {
        entity_id: BETRIEBSWAHL,
        state: "WW-Betrieb",
        attributes: { options: optionen },
      },
      [AUSLOESER]: { entity_id: AUSLOESER, state: "off", attributes: {} },
    },
    callService: async (bereich, dienst, daten) => {
      gerufen.push({ bereich, dienst, daten });
    },
  };
  const eintrag = {
    entity: AUSLOESER,
    titel: "Warmwasser laden",
    symbol: "mdi:water-boiler",
    betriebswahl,
    betriebswahl_zurueck: "^programm",
    zustand_an: BETRIEBSART,
    zustand_wenn: ["WW-Ladung", "Warmwasser Einmalladung"],
  };
  const taste = element._bedientaste(eintrag, false);
  return { element, taste, gerufen };
}

/** Der Klickbehandler ist asynchron – ihm ein paar Runden Zeit lassen. */
const abwarten = async () => {
  for (let runde = 0; runde < 8; runde++) await Promise.resolve();
};

const faelle = [];

// --- Der gemeldete Fehler: Abbruch startete die Ladung neu ------------------
{
  const { element, taste, gerufen } = panelBauen({
    laedt: true,
    optionen: ["Standby", "Programm 1", "Programm 2", "Heizbetrieb", "WW-Betrieb"],
  });
  // Wie nach einem Start über dieselbe Taste: Der Zustand von vorher steht.
  element._wahlVorLadung[BETRIEBSWAHL] = "Programm 2";
  taste.ausloesen("click");
  await abwarten();
  const wahl = gerufen.find((r) => r.dienst === "select_option");
  if (!wahl) throw new Error("Abbruch schrieb die Betriebswahl nicht");
  if (wahl.daten.option !== "Programm 2") {
    throw new Error(`Abbruch stellte auf ${wahl.daten.option} statt auf Programm 2`);
  }
  if (gerufen.some((r) => r.dienst === "turn_on" || r.dienst === "press")) {
    throw new Error("Abbruch löste die Ladung erneut aus");
  }
  faelle.push("laufende Ladung: zurück auf den Zustand von vorher");
}

// --- Ohne gemerkten Zustand: den Auslöser zurücknehmen ---------------------
//
// Der gemeldete Fehler „geht erst beim zweiten Klick". Ist der Zustand von vor
// der Ladung unbekannt, fällt `_rueckkehrWahl` auf die *aktuelle* Betriebswahl
// zurück – und die noch einmal zu schreiben ändert an der Anlage nichts. Bis
// 1.5.0-beta.10 war das der ganze Abbruch: ein Schreibvorgang ohne Wirkung.
{
  const { taste, gerufen } = panelBauen({
    laedt: true,
    optionen: ["Standby", "Programm 1", "Heizbetrieb", "WW-Betrieb"],
  });
  taste.ausloesen("click");
  await abwarten();
  if (!gerufen.some((r) => r.dienst === "turn_off" && r.daten.entity_id === AUSLOESER)) {
    throw new Error("unbekannter Rückkehrpunkt nahm den Auslöser nicht zurück");
  }
  const wahl = gerufen.find((r) => r.dienst === "select_option");
  if (wahl) {
    throw new Error(`wirkungsloser Schreibvorgang auf ${wahl.daten.option}`);
  }
  if (gerufen.some((r) => r.dienst === "turn_on" || r.dienst === "press")) {
    throw new Error("Abbruch löste die Ladung erneut aus");
  }
  faelle.push("unbekannter Rückkehrpunkt: Auslöser zurückgenommen");
}

// --- Ohne Betriebswahl darf die Ladung nicht erneut starten -----------------
{
  const { taste, gerufen } = panelBauen({ laedt: true, optionen: [], betriebswahl: null });
  taste.ausloesen("click");
  await abwarten();
  if (gerufen.some((r) => r.dienst === "turn_on" || r.dienst === "press")) {
    throw new Error("ohne Betriebswahl wurde die Ladung erneut ausgelöst");
  }
  if (!gerufen.some((r) => r.dienst === "turn_off")) {
    throw new Error("ohne Betriebswahl blieb der Auslöser stehen");
  }
  faelle.push("ohne Betriebswahl: Auslöser zurück, kein zweiter Start");
}

// --- Betriebswahl ohne lesbaren Zustand: nur der Auslöser ------------------
{
  const { element, taste, gerufen } = panelBauen({
    laedt: true,
    optionen: ["Standby", "Heizbetrieb", "WW-Betrieb"],
  });
  element._hass.states[BETRIEBSWAHL].state = "unavailable";
  taste.ausloesen("click");
  await abwarten();
  if (gerufen.some((r) => r.dienst === "select_option")) {
    throw new Error("ohne lesbaren Zustand wurde die Betriebswahl geschrieben");
  }
  if (gerufen.some((r) => r.dienst === "turn_on" || r.dienst === "press")) {
    throw new Error("ohne lesbaren Zustand wurde die Ladung erneut ausgelöst");
  }
  faelle.push("Betriebswahl ohne Zustand: nur der Auslöser, kein zweiter Start");
}

// --- Steht sie still, löst dieselbe Taste die Ladung aus --------------------
{
  const { taste, gerufen } = panelBauen({
    laedt: false,
    optionen: ["Standby", "Programm 1", "WW-Betrieb"],
  });
  taste.ausloesen("click");
  await abwarten();
  if (!gerufen.some((r) => r.dienst === "turn_on" || r.dienst === "press")) {
    throw new Error("ohne laufende Ladung wurde nicht ausgelöst");
  }
  faelle.push("ruhende Anlage: Ladung wird ausgelöst");
}

// --- Ohne gemerkten Zustand wird nichts geraten -----------------------------
//
// Der gemeldete Fehler: Beim zweiten Druck war der gemerkte Zustand
// verbraucht, die Ladung noch als laufend gemeldet – und die Taste stellte die
// Anlage auf „Heizprogramm 1", das nie jemand gewählt hatte.
{
  const { taste, gerufen } = panelBauen({
    laedt: true,
    optionen: ["Standby", "Heizprogramm 1", "Heizprogramm 2", "Heizbetrieb", "WW-Betrieb"],
  });
  taste.ausloesen("click");
  await abwarten();
  taste.ausloesen("click");
  await abwarten();
  const geraten = gerufen.find(
    (r) => r.dienst === "select_option" && r.daten.option !== "WW-Betrieb"
  );
  if (geraten) {
    throw new Error(`zweiter Druck stellte auf ${geraten.daten.option}`);
  }
  faelle.push("zweiter Druck: kein geratenes Programm");
}

console.log(JSON.stringify({ faelle }, null, 1));
