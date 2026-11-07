/**
 * Eingaben der Auswertung: Befüllung, Bestand und Datum der letzten Pflege.
 *
 * Aufruf: `node befund-eingabe.mjs <panel.js>`. Geprüft wird, welcher Dienst mit
 * welchen Daten gerufen wird und dass ungültige Eingaben und Abbruch nichts schreiben.
 */

import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
browserAttrappe();

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

const VORRAT = "number.purowin_brennstoffvorrat";
const DATUM = "date.purowin_letzte_hauptreinigung";

function panelBauen() {
  const element = new klasse();
  const gerufen = [];
  element._hass = {
    states: { [DATUM]: { entity_id: DATUM, state: "2026-10-24", attributes: {} } },
    callService: async (bereich, dienst, daten, ziel) => {
      gerufen.push({ bereich, dienst, daten, ziel });
    },
    callWS: async () => ({ anlagen: {} }),
  };
  return { element, gerufen };
}

const BRENNSTOFF = { art: "brennstoff", angaben: { einheit: "Srm" }, eingabe: { art: "vorrat", entity: VORRAT } };
const PFLEGE = { art: "pflege_hauptreinigung", angaben: {}, eingabe: { art: "datum", entity: DATUM, pflege: "hauptreinigung" } };

const abwarten = async () => {
  for (let runde = 0; runde < 8; runde++) await Promise.resolve();
};
const taste = (wurzel, text) => wurzel.querySelectorAll("button").find((t) => t.textContent === text);
const felder = (element) => element.shadowRoot.querySelectorAll("input");

function oeffnen(befund, beschriftung) {
  const { element, gerufen } = panelBauen();
  const leiste = element._befundEingabe(befund);
  taste(leiste, beschriftung).ausloesen("click");
  return { element, gerufen, leiste };
}

async function speichern(element) {
  taste(element.shadowRoot, "Speichern").ausloesen("click");
  await abwarten();
}

const faelle = [];

{
  const { element, gerufen } = oeffnen(BRENNSTOFF, "Befüllung eintragen");
  felder(element)[0].value = "12";
  await speichern(element);
  const ruf = gerufen[0];
  if (gerufen.length !== 1 || ruf.dienst !== "brennstoff_geliefert") throw new Error(JSON.stringify(gerufen));
  if (JSON.stringify(ruf.daten) !== '{"menge":12}' || ruf.ziel.entity_id !== VORRAT) throw new Error(JSON.stringify(ruf));
  faelle.push("Befüllung ohne Rest: nur die Menge");
}

{
  const { element, gerufen } = oeffnen(BRENNSTOFF, "Befüllung eintragen");
  felder(element)[0].value = "12";
  felder(element)[1].value = "3";
  await speichern(element);
  if (JSON.stringify(gerufen[0].daten) !== '{"menge":12,"rest":3}') throw new Error(JSON.stringify(gerufen));
  faelle.push("Befüllung mit Rest: Menge und Rest");
}

{
  const { element, gerufen } = oeffnen(BRENNSTOFF, "Befüllung eintragen");
  await speichern(element);
  const fehler = element.shadowRoot.querySelector(".befund-fehler");
  if (gerufen.length || !fehler || fehler.hidden) throw new Error("leere Menge wurde geschrieben oder nicht gemeldet");
  faelle.push("Befüllung ohne Menge: kein Aufruf, Hinweis");
}

{
  const { element, gerufen } = oeffnen(BRENNSTOFF, "Bestand eintragen");
  felder(element)[0].value = "7.5";
  await speichern(element);
  const ruf = gerufen[0];
  if (gerufen.length !== 1 || ruf.bereich !== "number" || ruf.daten.entity_id !== VORRAT || ruf.daten.value !== 7.5) {
    throw new Error(JSON.stringify(gerufen));
  }
  faelle.push("Bestand: Zahl auf den Vorrat");
}

{
  const { element, gerufen, leiste } = oeffnen(PFLEGE, "Datum nachtragen");
  if (!leiste.querySelectorAll("span").some((s) => s.textContent.includes("24.10.2026"))) {
    throw new Error("das bisherige Datum fehlt");
  }
  const feld = felder(element)[0];
  if (feld.value !== "2026-10-24") throw new Error(`Vorgabe ${feld.value}`);
  feld.value = "2026-11-01";
  await speichern(element);
  const ruf = gerufen[0];
  if (gerufen.length !== 1 || ruf.bereich !== "date" || ruf.daten.entity_id !== DATUM || ruf.daten.date !== "2026-11-01") {
    throw new Error(JSON.stringify(gerufen));
  }
  faelle.push("Datum: Tag auf die Datumsentität");
}

{
  const { element, gerufen } = oeffnen(PFLEGE, "Datum nachtragen");
  felder(element)[0].value = "2999-01-01";
  await speichern(element);
  if (gerufen.length) throw new Error("ein Tag in der Zukunft wurde geschrieben");
  faelle.push("Datum in der Zukunft: kein Aufruf");
}

{
  const { element, gerufen } = oeffnen(BRENNSTOFF, "Bestand eintragen");
  taste(element.shadowRoot, "Abbrechen").ausloesen("click");
  await abwarten();
  if (gerufen.length || element.shadowRoot.querySelector(".schleier")) throw new Error("Abbruch schrieb oder blieb offen");
  faelle.push("Abbruch: kein Aufruf");
}

{
  const { element } = panelBauen();
  if (element._befundEingabe({ art: "laufzeit", angaben: {} }) !== null) throw new Error("Karte ohne Eingabe zeigt Tasten");
  faelle.push("ohne Eingabe: keine Tasten");
}

process.stdout.write(JSON.stringify({ faelle }, null, 2), () => process.exit(0));
