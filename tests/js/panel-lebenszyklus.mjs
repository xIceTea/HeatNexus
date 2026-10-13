/**
 * Lebenszyklus der Oberfläche: Neuaufbau, Hörer, Zeitgeber, Dialoge, Tastatur.
 *
 * Aufruf: `node panel-lebenszyklus.mjs <panel.js>`
 * Ausgabe: ein JSON-Objekt mit je einem Befund je Prüfung; geprüft wird in
 * `test_panel_lebenszyklus.py`.
 */

import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
const zeit = browserAttrappe();
console.warn = () => {};

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

const abwarten = async () => {
  for (let runde = 0; runde < 8; runde++) await Promise.resolve();
};

function anlage(name, id) {
  return {
    id,
    name,
    hilfe_liste: [{ titel: "Heizgrenze", text: "Ab dieser Außentemperatur heizt der Kreis." }],
  };
}

const DATEN = { anlagen: [anlage("Heizhaus", "a"), anlage("Wohnhaus", "b")] };

/** Eine Oberfläche mit zwei Anlagen im Reiter „Hilfe“; `ws` beantwortet WebSocket-Aufrufe. */
function bauen({ ws = async () => ({}), daten = DATEN, reiter = "hilfe" } = {}) {
  const flaeche = new klasse();
  const gerufen = [];
  flaeche._reiter = reiter;
  flaeche.hass = {
    states: { "sensor.aussen": { entity_id: "sensor.aussen", state: "5", attributes: {} } },
    user: { is_admin: true },
    language: "de",
    locale: { language: "de" },
    callWS: async (nachricht) => {
      gerufen.push(nachricht);
      return ws(nachricht);
    },
    callService: async () => true,
  };
  flaeche.panel = { config: { daten } };
  return { flaeche, gerufen };
}

const inhalt = (flaeche) => flaeche.shadowRoot.children.find((kind) => !kind.classList.contains("schleier") && kind.tagName !== "STYLE");
const befund = {};

// --- Neuaufbau: Hörer am Schattenbaum und das Stylesheet --------------------
{
  const { flaeche } = bauen();
  for (let runde = 0; runde < 5; runde++) {
    flaeche._gebaut = false;
    flaeche._zeichnen();
  }
  befund.klickhoererNachFuenfAufbauten = flaeche.shadowRoot.hoererZahl("click");
}

// --- Gleiche Daten lösen keinen Neuaufbau aus -------------------------------
{
  const { flaeche } = bauen({ ws: async () => JSON.parse(JSON.stringify(DATEN)) });
  await abwarten();
  const knoten = inhalt(flaeche);
  await flaeche._datenHolen();
  flaeche.panel = { config: { daten: DATEN } };
  await abwarten();
  befund.neuaufbauBeiGleichenDaten = inhalt(flaeche) !== knoten;
}

// --- Zustandsmeldungen: nur gelesene Entitäten, gebündelt je Bild -------------
{
  const { flaeche } = bauen();
  let durchlaeufe = 0;
  const alt = flaeche._aktualisieren.bind(flaeche);
  flaeche._aktualisieren = () => {
    durchlaeufe++;
    alt();
  };
  const hass = flaeche._hass;
  flaeche._gelesen.add("sensor.aussen");
  const mit = (zustaende) => ({ ...hass, states: { ...hass.states, ...zustaende } });
  flaeche.hass = mit({ "sensor.fremd": { state: "1", attributes: {} } });
  zeit.zeitLaufenLassen();
  befund.durchlaeufeBeiFremderEntitaet = durchlaeufe;
  flaeche.hass = mit({ "sensor.aussen": { state: "6", attributes: {} } });
  flaeche.hass = mit({ "sensor.aussen": { state: "7", attributes: {} } });
  zeit.zeitLaufenLassen();
  befund.durchlaeufeBeiGelesenerEntitaet = durchlaeufe;
}

process.stdout.write(JSON.stringify(befund, null, 2));
