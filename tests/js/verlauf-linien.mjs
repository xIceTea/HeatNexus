/**
 * Die Linienwahl der Verlaufskarte: Chips, Suche, Standard – und gemerkt über
 * das Neuladen hinaus.
 *
 * Aufruf: `node verlauf-linien.mjs <panel.js>`
 *
 * Jedes neue Element steht für eine frisch geladene Seite. Geprüft wird, was
 * an die Nutzerdaten geht, was davon zurückkommt und welche Linien die Karte
 * dann zeichnet.
 */

import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
browserAttrappe();

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

const SPEICHER = "heatnexus.verlauf_linien";
const VORAUSWAHL = ["sensor.kessel", "sensor.puffer_oben"];
const anlage = {
  name: "Anlage A",
  verlauf: VORAUSWAHL,
  verlauf_moeglich: [
    { entity: "sensor.kessel", titel: "Kessel" },
    { entity: "sensor.puffer_oben", titel: "Puffer oben" },
    { entity: "sensor.puffer_mitte", titel: "Puffer Mitte" },
    { entity: "sensor.aussen", titel: "Außentemperatur" },
  ],
};

/** Eine frisch geladene Seite; `antwort` beantwortet jede WebSocket-Anfrage. */
function seite(antwort) {
  const element = new klasse();
  const gesendet = [];
  element._hass = {
    states: {},
    callWS: async (nachricht) => {
      gesendet.push(nachricht);
      return antwort(nachricht);
    },
  };
  return { element, gesendet };
}

const linienDerKarte = (karte) => JSON.parse(karte.querySelector("[data-verlauf]").dataset.entities);
const linien = (element, stunden = 48) => linienDerKarte(element._verlauf(anlage, stunden));
const chips = (karte) => karte.querySelectorAll(".linie").map((chip) => chip.dataset.entity);
const vorschlaege = (karte) =>
  karte.querySelector(".linien-vorschlaege").children.map((z) => z.dataset.entity || "leer");
const tippen = (karte, text) => {
  const feld = karte.querySelector(".linien-suche");
  feld.value = text;
  feld.ausloesen("input");
  return feld;
};
const letzteWahl = (gesendet) => {
  const geschrieben = gesendet.filter((n) => n.type === "frontend/set_user_data").pop();
  return geschrieben ? { key: geschrieben.key, value: geschrieben.value } : null;
};

const ruhe = async () => {
  for (let runde = 0; runde < 5; runde++) await Promise.resolve();
};

const bilanz = {};

// Ohne gemerkte Wahl gilt die Vorauswahl der Integration; „Standard“ ruht.
const leer = seite(() => ({ value: null }));
await leer.element._linienHolen();
const karte = leer.element._verlauf(anlage, 48);
bilanz.ohneWahl = {
  linien: linienDerKarte(karte),
  chips: chips(karte),
  standardVersteckt: karte.querySelector(".linien-standard").hidden,
};

// Die Suche trifft Titel und Entitäts-ID und lässt Gewähltes weg.
bilanz.suche = {
  puffer: (tippen(karte, "puffer"), vorschlaege(karte)),
  kennung: (tippen(karte, "sensor.aus"), vorschlaege(karte)),
  nichts: (tippen(karte, "xyz"), vorschlaege(karte)),
};

// Escape schließt die Liste.
const feld = tippen(karte, "e");
const offenVorEscape = !karte.querySelector(".linien-vorschlaege").hidden;
feld.ausloesen("keydown", { key: "Escape" });
bilanz.escape = { vorher: offenVorEscape, nachher: karte.querySelector(".linien-vorschlaege").hidden };

// Pfeil runter und Enter übernehmen den zweiten Treffer als Chip.
tippen(karte, "e");
const treffer = vorschlaege(karte);
feld.ausloesen("keydown", { key: "ArrowDown" });
feld.ausloesen("keydown", { key: "Enter" });
await ruhe();
bilanz.enter = {
  treffer,
  chips: chips(karte),
  linien: linienDerKarte(karte),
  feldLeer: feld.value === "",
  listeZu: karte.querySelector(".linien-vorschlaege").hidden,
  standardVersteckt: karte.querySelector(".linien-standard").hidden,
  geschrieben: letzteWahl(leer.gesendet),
};

// Das × entfernt eine Linie.
karte
  .querySelectorAll(".linie")
  .find((chip) => chip.dataset.entity === "sensor.kessel")
  .querySelector(".linie-weg")
  .ausloesen("click");
await ruhe();
bilanz.entfernt = { chips: chips(karte), geschrieben: letzteWahl(leer.gesendet) };

// „Standard“ stellt die Vorauswahl her und vergisst die eigene Wahl.
karte.querySelector(".linien-standard").ausloesen("click");
await ruhe();
bilanz.standard = {
  chips: chips(karte),
  versteckt: karte.querySelector(".linien-standard").hidden,
  geschrieben: letzteWahl(leer.gesendet),
};

// Die nächste Seite liest die Wahl zurück; verschwundene Entitäten fallen weg.
const wieder = seite((nachricht) =>
  nachricht.type === "frontend/get_user_data"
    ? { value: { "Anlage A|48": ["sensor.kessel", "sensor.puffer_mitte", "sensor.weg"] } }
    : {}
);
await wieder.element._linienHolen();
bilanz.gemerkt = linien(wieder.element);
bilanz.andererZeitraum = linien(wieder.element, 24);

// Ist keine gemerkte Linie mehr da, gilt wieder die Vorauswahl.
const verwaist = seite(() => ({ value: { "Anlage A|48": ["sensor.weg"] } }));
await verwaist.element._linienHolen();
bilanz.verwaist = linien(verwaist.element);

// Wer alle Linien entfernt, bekommt eine leere Karte – auch nach dem Neuladen.
const abgewaehlt = seite(() => ({ value: { "Anlage A|48": [] } }));
await abgewaehlt.element._linienHolen();
const leereKarte = abgewaehlt.element._verlauf(anlage, 48);
bilanz.abgewaehlt = {
  linien: linienDerKarte(leereKarte),
  hinweis: !!leereKarte.querySelector(".linien-leer"),
};

// Scheitern die Nutzerdaten, hält der Browser die Wahl.
const ohneServer = () => {
  throw new Error("kein Server im Test");
};
const lokal = seite(ohneServer);
lokal.element._linienMerken("Anlage A|48", ["sensor.puffer_mitte"]);
await ruhe();
bilanz.imBrowser = JSON.parse(globalThis.localStorage.getItem(SPEICHER));
const lokalWieder = seite(ohneServer);
await lokalWieder.element._linienHolen();
bilanz.ausBrowser = linien(lokalWieder.element);

console.log(JSON.stringify(bilanz));
