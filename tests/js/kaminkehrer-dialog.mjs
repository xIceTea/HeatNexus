/**
 * Der Rückfragedialog des Kaminkehrers – mit mehr als einem Zahlenfeld.
 *
 * Aufruf: `node kaminkehrer-dialog.mjs <panel.js>`
 *
 * Leistung und Laufzeit gelten beide für die ganze Messung und stehen deshalb
 * vor dem Auslösen fest. Geprüft wird, was von außen zählt: welche Dienste in
 * welcher Reihenfolge gerufen werden und dass ein Abbruch nichts schreibt.
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

const AUSLOESER = "switch.kaminkehrerbetrieb";
const LEISTUNG = "number.kaminkehrer_leistung";
const LAUFZEIT = "number.kaminkehrer_laufzeit";

function panelBauen({ laufzeit = LAUFZEIT } = {}) {
  const element = new klasse();
  const gerufen = [];
  element._hass = {
    states: {
      [AUSLOESER]: { entity_id: AUSLOESER, state: "off", attributes: {} },
      [LEISTUNG]: {
        entity_id: LEISTUNG,
        state: "50",
        attributes: { unit_of_measurement: "%", min: 30, max: 100, step: 1 },
      },
      [LAUFZEIT]: {
        entity_id: LAUFZEIT,
        state: "90",
        attributes: { unit_of_measurement: "min", min: 0, max: 240, step: 1 },
      },
    },
    callService: async (bereich, dienst, daten) => {
      gerufen.push({ bereich, dienst, daten });
    },
  };
  const eintrag = {
    entity: AUSLOESER,
    titel: "Kaminkehrer",
    symbol: "mdi:account-hard-hat",
    frage: "Der Kessel fährt auf feste Leistung.",
    leistung: LEISTUNG,
    ...(laufzeit ? { laufzeit } : {}),
  };
  const taste = element._bedientaste(eintrag, false);
  return { element, taste, gerufen };
}

const abwarten = async () => {
  for (let runde = 0; runde < 8; runde++) await Promise.resolve();
};

const felder = (element) => element.shadowRoot.querySelectorAll(".dialog-zahl");
const knopf = (element, beschriftung) =>
  element.shadowRoot
    .querySelectorAll(".dialog-taste")
    .find((taste) => taste.textContent === beschriftung);

const faelle = [];

// --- Beide Werte stehen im selben Dialog und werden beide geschrieben -------
{
  const { element, taste, gerufen } = panelBauen();
  taste.ausloesen("click");
  await abwarten();

  const zahlen = felder(element);
  if (zahlen.length !== 2) throw new Error(`${zahlen.length} Zahlenfelder statt zwei`);
  if (zahlen[0].value !== 50 && zahlen[0].value !== "50") {
    throw new Error(`Leistung stand auf ${zahlen[0].value} statt auf dem gelesenen Wert`);
  }
  zahlen[0].value = "60";
  zahlen[1].value = "120";
  knopf(element, "Ja, ausführen").ausloesen("click");
  await abwarten();

  const werte = gerufen.filter((ruf) => ruf.dienst === "set_value");
  if (werte.length !== 2) throw new Error(`${werte.length} Schreibvorgänge statt zwei`);
  const nach = Object.fromEntries(werte.map((ruf) => [ruf.daten.entity_id, ruf.daten.value]));
  if (nach[LEISTUNG] !== 60) throw new Error(`Leistung wurde als ${nach[LEISTUNG]} geschrieben`);
  if (nach[LAUFZEIT] !== 120) throw new Error(`Laufzeit wurde als ${nach[LAUFZEIT]} geschrieben`);
  if (!gerufen.some((ruf) => ruf.daten.entity_id === AUSLOESER)) {
    throw new Error("der Kaminkehrer wurde nach den Werten nicht ausgelöst");
  }
  faelle.push("zwei Felder: beide Werte geschrieben, dann ausgelöst");
}

// --- Abbrechen schreibt nichts ---------------------------------------------
{
  const { element, taste, gerufen } = panelBauen();
  taste.ausloesen("click");
  await abwarten();
  knopf(element, "Abbrechen").ausloesen("click");
  await abwarten();

  if (gerufen.length) throw new Error(`Abbruch rief ${gerufen[0].dienst}`);
  faelle.push("Abbruch: kein Schreibvorgang");
}

// --- Ohne schreibbare Laufzeit bleibt es beim einen Feld --------------------
{
  const { element, taste, gerufen } = panelBauen({ laufzeit: null });
  taste.ausloesen("click");
  await abwarten();

  const zahlen = felder(element);
  if (zahlen.length !== 1) throw new Error(`${zahlen.length} Zahlenfelder statt eines`);
  zahlen[0].value = "70";
  knopf(element, "Ja, ausführen").ausloesen("click");
  await abwarten();

  const werte = gerufen.filter((ruf) => ruf.dienst === "set_value");
  if (werte.length !== 1 || werte[0].daten.entity_id !== LEISTUNG) {
    throw new Error("ohne Laufzeit wurde etwas anderes als die Leistung geschrieben");
  }
  faelle.push("ohne Laufzeit: nur die Leistung");
}

process.stdout.write(JSON.stringify({ faelle }, null, 2));
