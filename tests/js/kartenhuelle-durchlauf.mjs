/**
 * Hülle und Umsetzung der Karten im Node-Durchlauf: Die Seite lädt eine Fassung,
 * der Server meldet eine andere. Ausgabe ist eine Bilanz als JSON.
 */

import { browserAttrappe } from "./dom-attrappe.mjs";

const [, , adresseA, adresseB, adresseFehlt] = process.argv;
const echteWartezeit = globalThis.setTimeout;
browserAttrappe();

const bilanz = {};
const NAMEN = ["heatnexus-schaubild", "heatnexus-leitwert", "heatnexus-kennwerte", "heatnexus-puffer"];
const HINWEIS = { hinweis: "HeatNexus wurde aktualisiert.", neu_laden: "Neu laden" };

// Jede Anmeldung zählen: Ein Name darf im Browser nur einmal vergeben werden.
const anmeldungen = {};
const anmelden = customElements.define.bind(customElements);
customElements.define = (name, klasse) => {
  anmeldungen[name] = (anmeldungen[name] || 0) + 1;
  anmelden(name, klasse);
};
const warnungen = [];
console.warn = (...teile) => warnungen.push(teile.map(String).join(" "));
let neuGeladen = 0;
globalThis.location = { reload: () => (neuGeladen += 1) };
const echteUhr = Date.now;
let vorgestellt = 0;
Date.now = () => echteUhr() + vorgestellt;

// Der Server: Seine Antwort auf die Frage nach der Fassung wechselt im Lauf.
const server = { antwort: { fassung: "a", karte: adresseA, vertrag: 1, ...HINWEIS }, fehler: false };
const fragen = { fassung: 0, schaubild: 0 };
const bereit = [];
const verbindung = { addEventListener: (art, ruf) => art === "ready" && bereit.push(ruf) };
function hassObjekt(zustand = "RUNNING") {
  return {
    states: { "sensor.oben": { state: "68", attributes: { unit_of_measurement: "°C" } } },
    language: "de",
    locale: { language: "de" },
    themes: { darkMode: false },
    config: { state: zustand },
    connection: verbindung,
    callWS: async (anfrage) => {
      if (anfrage.type === "heatnexus/fassung") {
        fragen.fassung += 1;
        if (server.fehler) throw new Error("unknown_command");
        return server.antwort;
      }
      if (anfrage.type === "heatnexus/schaubild") {
        fragen.schaubild += 1;
        return [];
      }
      return {};
    },
  };
}
const neuVerbunden = () => bereit.forEach((ruf) => ruf());

async function bis(bedingung) {
  for (let runde = 0; runde < 4000 && !bedingung(); runde += 1) {
    await new Promise((weiter) => echteWartezeit(weiter, 5));
  }
  return bedingung();
}
const ruhe = () => new Promise((weiter) => echteWartezeit(weiter, 50));

function karte(name, config) {
  const el = document.createElement(name);
  el.setConfig(config);
  el.connectedCallback();
  return el;
}
const innen = (el) => el.shadowRoot.children[2];
const innenName = (el) => innen(el).tagName.toLowerCase();
const meldung = (el) => el.shadowRoot.children[1];

// --- Die Seite lädt Fassung a ------------------------------------------------
const modul = await import(adresseA);
const huelle = await import(new URL("./kartenhuelle.js", adresseA).href);
bilanz.fassungAus = [
  "https://ha.example/heatnexus-karte-1-16-0-ab12cd34/heatnexus-schaubild-karte.js",
  "https://ha.example/heatnexus-frontend/1-16-0-ab12cd34/heatnexus-kacheln.js?x=1",
  "https://ha.example/heatnexus-karte/heatnexus-schaubild-karte.js",
  "file:///arbeit/heatnexus-karte-fix/custom_components/heatnexus/frontend/kartenhuelle.js",
].map(huelle.fassungAus);
bilanz.festeNamen = NAMEN.filter((n) => customElements.get(n));
bilanz.umsetzungenA = NAMEN.filter((n) => customElements.get(`${n}-a`));
bilanz.huelleIstNichtDieUmsetzung =
  customElements.get("heatnexus-schaubild") !== modul.HeatNexusSchaubildKarte &&
  customElements.get("heatnexus-schaubild-a") === modul.HeatNexusSchaubildKarte;
bilanz.inKartenauswahl = NAMEN.filter((n) => window.customCards.some((k) => k.type === n));
// Dieselbe Fassung unter einer zweiten Adresse: Der Browser wertet das Modul erneut aus.
const zweit = await import(`${adresseA}?zweit=1`);
bilanz.zweiteAdresse = zweit.HeatNexusSchaubildKarte !== modul.HeatNexusSchaubildKarte;

const Puffer = customElements.get("heatnexus-puffer");
const Schaubild = customElements.get("heatnexus-schaubild");
bilanz.stub = Puffer.getStubConfig().type;
bilanz.formular = Puffer.getConfigForm().schema.map((f) => f.name).includes("oben");
bilanz.editorA = (await Schaubild.getConfigElement()).tagName.toLowerCase();
bilanz.editorFormularFehlt = Schaubild.getConfigForm() === undefined;

const PUFFER = { type: "custom:heatnexus-puffer", titel: "Puffer", oben: "sensor.oben", unten: "sensor.fehlt" };
const erste = karte("heatnexus-puffer", PUFFER);
const zweite = karte("heatnexus-kennwerte", { type: "custom:heatnexus-kennwerte", werte: [] });
const bild = karte("heatnexus-schaubild", { type: "custom:heatnexus-schaubild" });
// Eine Hülle, die gerade nicht im Dokument hängt, hört den Wechsel nicht.
const abgehaengt = document.createElement("heatnexus-puffer");
abgehaengt.setConfig(PUFFER);

bilanz.groesseOhneHass = [erste.getCardSize(), erste.getGridOptions().columns, bild.getCardSize()];
const hass = hassObjekt();
for (const el of [erste, zweite, bild, abgehaengt]) el.hass = hass;
erste.layout = "grid";
await innen(bild)._laden;
await ruhe();
bilanz.start = {
  innen: [erste, zweite, bild].map(innenName),
  fragen: fragen.fassung,
  text: innen(erste).shadowRoot.textContent,
  hassGereicht: innen(erste)._hass === hass && erste.hass === hass,
  layoutGereicht: innen(erste).layout,
  hinweis: meldung(erste).children.length,
};

// --- Home Assistant startet mit Fassung b neu --------------------------------
neuVerbunden();
bilanz.startetNochKeineFrage = (() => {
  erste.hass = hassObjekt("STARTING");
  return fragen.fassung;
})();
server.antwort = { fassung: "b", karte: adresseB, vertrag: 1, ...HINWEIS };
const schaubildVorher = fragen.schaubild;
erste.hass = hass;
bilanz.getauscht = await bis(() => innenName(zweite) === "heatnexus-kennwerte-b");
await innen(bild)._laden;
for (let lauf = 0; lauf < 3; lauf += 1) erste.hass = hass;
await ruhe();
bilanz.nachWechsel = {
  innen: [erste, zweite, bild].map(innenName),
  kinder: [erste, zweite, bild].map((el) => el.shadowRoot.children.length),
  fragen: fragen.fassung,
  text: innen(erste).shadowRoot.textContent,
  hassGereicht: innen(erste)._hass === hass,
  layoutGereicht: innen(erste).layout,
  schaubildNeuGefragt: fragen.schaubild > schaubildVorher,
  hinweis: meldung(erste).children.length,
  abgehaengtVorher: innenName(abgehaengt),
  editor: (await Schaubild.getConfigElement()).tagName.toLowerCase(),
  neueKarte: innenName(karte("heatnexus-leitwert", { type: "custom:heatnexus-leitwert" })),
  warnungen: warnungen.length,
};
abgehaengt.connectedCallback();
bilanz.nachWechsel.abgehaengtNachher = innenName(abgehaengt);

// --- Die nächste Fassung lässt sich nicht laden ------------------------------
neuVerbunden();
server.antwort = { fassung: "c", karte: adresseFehlt, vertrag: 1, ...HINWEIS };
erste.hass = hass;
bilanz.hinweisErschienen = await bis(() => meldung(zweite).children.length === 2);
const fragenVorher = fragen.fassung;
neuVerbunden();
erste.hass = hass;
await bis(() => fragen.fassung > fragenVorher);
await ruhe();
meldung(zweite).children[1].ausloesen("click");
bilanz.fehlschlag = {
  innen: [erste, zweite, bild].map(innenName),
  text: meldung(erste).textContent,
  taste: meldung(erste).children[1].tagName.toLowerCase(),
  neuGeladen,
  warnungen: warnungen.length,
  erneutGefragt: fragen.fassung - fragenVorher,
  neueKarteMitHinweis: meldung(karte("heatnexus-puffer", PUFFER)).children.length,
};

// --- Der Server verlangt einen neueren Vertrag -------------------------------
neuVerbunden();
server.antwort = { fassung: "b", karte: adresseB, vertrag: 1, ...HINWEIS };
erste.hass = hass;
bilanz.hinweisWieder_weg = await bis(() => meldung(zweite).children.length === 0);
neuVerbunden();
// Fassung a ist geladen und wäre nutzbar; allein der Vertrag steht dem Wechsel entgegen.
server.antwort = { fassung: "a", karte: adresseA, vertrag: 2, ...HINWEIS };
erste.hass = hass;
bilanz.vertrag = {
  hinweis: await bis(() => meldung(zweite).children.length === 2),
  innen: innenName(erste),
  warnungen: warnungen.length,
};

// --- Zurück auf a: Das Modul ist schon geladen -------------------------------
neuVerbunden();
server.antwort = { fassung: "a", karte: adresseA, vertrag: 1, ...HINWEIS };
erste.hass = hass;
bilanz.zurueck = {
  getauscht: await bis(() => innenName(zweite) === "heatnexus-kennwerte-a"),
  hinweis: meldung(zweite).children.length,
};

// --- Während des Starts kennt der Server den Befehl noch nicht ---------------
neuVerbunden();
server.fehler = true;
const vorStart = fragen.fassung;
erste.hass = hass;
await bis(() => fragen.fassung > vorStart);
await ruhe();
erste.hass = hass;
await ruhe();
const sofort = fragen.fassung - vorStart;
server.fehler = false;
server.antwort = { fassung: "b", karte: adresseB, vertrag: 1, ...HINWEIS };
vorgestellt += 11000;
erste.hass = hass;
bilanz.startphase = {
  sofort,
  nachWartezeit: await bis(() => innenName(zweite) === "heatnexus-kennwerte-b"),
  fragen: fragen.fassung - vorStart,
};

bilanz.anmeldungen = anmeldungen;
erste.disconnectedCallback();
console.log(JSON.stringify(bilanz));
