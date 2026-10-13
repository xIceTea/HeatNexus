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
  befund.stilknoten = flaeche.shadowRoot.children.filter((kind) => kind.tagName === "STYLE").length;
  befund.geteilteBoegen = flaeche.shadowRoot.adoptedStyleSheets.length;
  const zweite = bauen().flaeche;
  befund.bogenGeteilt = zweite.shadowRoot.adoptedStyleSheets[0] === flaeche.shadowRoot.adoptedStyleSheets[0];
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

// --- Abbau: Zeitgeber und offener Speicherauftrag --------------------------
{
  const { flaeche, gerufen } = bauen();
  let nachgefasst = 0;
  flaeche._zeitgeber(() => nachgefasst++, 5000);
  flaeche._takt(() => nachgefasst++, 1000);
  flaeche._anordnungSichern("uebersicht", { karten: ["a"] });
  flaeche.disconnectedCallback();
  zeit.zeitLaufenLassen();
  await abwarten();
  befund.zeitgeberNachAbbau = nachgefasst;
  befund.gespeichertBeimAbbau = gerufen.filter((n) => n.type === "heatnexus/anordnung/setzen").length;
}

// --- Fenster: Gerüst, Neuaufbau, Escape, Abbau ------------------------------
{
  const { flaeche } = bauen();
  const ausloeser = flaeche.shadowRoot.querySelector("button");
  ausloeser.focus();
  flaeche._erklaeren("Heizgrenze", "Ab dieser Außentemperatur heizt der Kreis.");
  const schleier = () => flaeche.shadowRoot.querySelectorAll(".schleier");
  document.ausloesen("keydown", { key: "Escape" });
  befund.fokusZurueck = flaeche.shadowRoot.activeElement === ausloeser;
  flaeche._erklaeren("Heizgrenze", "Ab dieser Außentemperatur heizt der Kreis.");
  const fenster = flaeche.shadowRoot.querySelector(".dialog");
  befund.fensterRolle = [fenster.getAttribute("role"), fenster.getAttribute("aria-modal")];
  befund.fensterBeschriftet = Boolean(fenster.getAttribute("aria-labelledby"));
  flaeche._gebaut = false;
  flaeche._zeichnen();
  befund.fensterNachNeuaufbau = schleier().length;
  document.ausloesen("keydown", { key: "Escape" });
  befund.fensterNachEscape = schleier().length;
  befund.tastenhoerer = document.hoererZahl("keydown");
  flaeche._erklaeren("A", "B");
  flaeche.disconnectedCallback();
  befund.fensterNachAbbau = schleier().length;
  befund.tastenhoererNachAbbau = document.hoererZahl("keydown");
}

// --- Reiter und Werkzeugmenü per Tastatur ------------------------------------
{
  const { flaeche } = bauen();
  const wurzel = flaeche.shadowRoot;
  const reiter = [...wurzel.querySelector(".reiter").children];
  befund.reiterTabindex = reiter.map((taste) => taste.getAttribute("tabindex"));
  befund.reiterSteuernFlaeche = Boolean(reiter[0].getAttribute("aria-controls"));
  befund.flaecheBeschriftet = wurzel.querySelectorAll('[role="tabpanel"]').length;
  const aktiv = reiter.findIndex((taste) => taste.getAttribute("aria-selected") === "true");
  reiter[aktiv].focus();
  wurzel.querySelector(".reiter").ausloesen("keydown", { key: "ArrowRight", target: reiter[aktiv] });
  befund.pfeilFokus = reiter.indexOf(wurzel.activeElement) === (aktiv + 1) % reiter.length;

  const huelle = wurzel.querySelector(".werkzeuge");
  const taste = huelle.querySelector("button");
  taste.ausloesen("click", { detail: 0 });
  const liste = huelle.querySelector(".werkzeugliste");
  befund.menueOffen = !liste.hidden;
  befund.menueFokus = wurzel.activeElement === liste.children[0];
  huelle.ausloesen("keydown", { key: "Escape", target: liste.children[0] });
  befund.menueNachEscape = [liste.hidden, wurzel.activeElement === taste];
}

// --- Menütaste ---------------------------------------------------------------
{
  const { flaeche } = bauen();
  const taste = () => flaeche.shadowRoot.querySelector(".menue-taste").style.display;
  const ergebnis = { breit: (flaeche._aktualisieren(), taste()) };
  flaeche.narrow = true;
  zeit.zeitLaufenLassen();
  ergebnis.schmal = taste();
  flaeche.narrow = false;
  flaeche.hass = { ...flaeche._hass, dockedSidebar: "always_hidden" };
  zeit.zeitLaufenLassen();
  ergebnis.versteckteLeiste = taste();
  befund.menuetaste = ergebnis;
}

process.stdout.write(JSON.stringify(befund, null, 2));
