/**
 * Bedienung des Reiters „Zeitprogramme“: Reiter, Zeilen, Tipp, Editor, Tastatur und Vorleser.
 *
 * Aufruf: `node zeitprogramme-bedienung.mjs <frontend-ordner> <sprachen-ordner>`
 * Ausgabe: ein JSON-Objekt mit einem Befund je Abschnitt; geprüft wird in
 * `test_oberflaeche_zeitprogramme_bedienung.py`. Ein Fehler steht als `fehler` im Abschnitt.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { Knoten, browserAttrappe } from "./dom-attrappe.mjs";

const [ordner, sprachen] = process.argv.slice(2);
browserAttrappe();
console.warn = () => {};

await import(pathToFileURL(join(ordner, "heatnexus-panel.js")).href);
const seite = await import(pathToFileURL(join(ordner, "zeitprogrammseite.js")).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
const woerterbuch = (sprache) => JSON.parse(readFileSync(join(sprachen, `${sprache}.json`), "utf-8"));

const text = (knoten) => String((knoten && knoten.textContent) || "").trim();
const punkte = (...paare) => paare.map(([time, value]) => ({ time, value }));
const WERKTAGE = ["Mo", "Tu", "We", "Th", "Fr"];

const BETRIEBSWAHL = { entity: "select.betriebswahl", wahl_name: "Betriebswahl" };
const ZIRKULATION = { entity: "select.zirkulation", wahl_name: "WW-Zirkulationspumpe" };

/** Zwei Heizprogramme und zwei Zirkulationsprogramme eines Heizkreises. */
function programme(namen = {}) {
  const programm = (entity, titel, extra) => ({
    entity,
    titel: namen[titel] || titel,
    anlagenteil: "Heizkreis",
    teil: "heizkreis",
    symbol: "mdi:radiator",
    ...extra,
  });
  return [
    programm("sensor.heizprogramm_1", "Heizprogramm 1", {
      gruppe: "heizen", art: "raum", nummer: 1, wirkung: { ...BETRIEBSWAHL, muster: "programm 1", ziel: "Programm 1" },
    }),
    programm("sensor.heizprogramm_2", "Heizprogramm 2", {
      gruppe: "heizen", art: "raum", nummer: 2, wirkung: { ...BETRIEBSWAHL, muster: "programm 2", ziel: "Programm 2" },
    }),
    programm("sensor.zirkulation_temperatur", "WW-Zirkulationsprogramm Temperatursteuerung", {
      gruppe: "zirkulation", art: "wasser",
      wirkung: { ...ZIRKULATION, muster: "mit temperatursteuerung", ziel: "Mit Temperatursteuerung" },
    }),
    programm("sensor.zirkulation_zeit", "WW-Zirkulationsprogramm Zeitsteuerung", {
      gruppe: "zirkulation",
      wirkung: { ...ZIRKULATION, muster: "mit zeitsteuerung", muster_auch: "mit impulssteuerung", ziel: "Mit Zeitsteuerung" },
    }),
  ];
}

function zustaende(bloecke = {}) {
  const zustand = (entity, state, attributes = {}) => ({ entity_id: entity, state, attributes });
  const plan = (eigene, vorgabe) => zustand(eigene, "", { blocks: bloecke[eigene] || vorgabe });
  return {
    "select.betriebswahl": zustand("select.betriebswahl", "Programm 1", { options: ["Standby", "Programm 1", "Programm 2"] }),
    "select.zirkulation": zustand("select.zirkulation", "Mit Zeitsteuerung", {
      options: ["Aus", "Mit Zeitsteuerung", "Mit Temperatursteuerung"],
    }),
    "sensor.heizprogramm_1": plan("sensor.heizprogramm_1", [
      { weekdays: WERKTAGE, switchPoints: punkte(["06:00", 21], ["22:00", 16]) },
      { weekdays: ["Sa", "Su"], switchPoints: punkte(["07:30", 21], ["23:00", 16]) },
    ]),
    "sensor.heizprogramm_2": plan("sensor.heizprogramm_2", [
      { weekdays: [...WERKTAGE, "Sa", "Su"], switchPoints: punkte(["06:00", 20], ["21:00", 17]) },
    ]),
    "sensor.zirkulation_temperatur": plan("sensor.zirkulation_temperatur", [
      { weekdays: [...WERKTAGE, "Sa", "Su"], switchPoints: punkte(["05:00", 45], ["22:00", 40]) },
    ]),
    "sensor.zirkulation_zeit": plan("sensor.zirkulation_zeit", [
      { weekdays: [...WERKTAGE, "Sa", "Su"], switchPoints: punkte(["06:00", 1], ["08:00", 0]) },
    ]),
  };
}

/** Eine Oberfläche im Reiter „Zeitprogramme“; `stil` wählt „tabelle“ oder „spur“. */
function bauen({ namen = {}, bloecke = {}, texte = {}, stil = null } = {}) {
  const flaeche = new klasse();
  const aufrufe = [];
  flaeche._texte = texte;
  flaeche._reiter = "zeitprogramme";
  flaeche._jetzt = () => new Date("2026-11-18T10:00:00Z");
  flaeche.hass = {
    states: zustaende(bloecke),
    user: { is_admin: true },
    language: "de",
    locale: { language: "de" },
    config: { time_zone: "UTC" },
    callWS: async () => ({}),
    callService: async (bereich, dienst, angaben) => {
      aufrufe.push({ dienst: `${bereich}.${dienst}`, angaben });
      return true;
    },
  };
  flaeche.panel = { config: { daten: { anlagen: [{ id: "a", name: "Heizhaus", zeitprogramme: programme(namen) }] } } };
  if (stil) flaeche._vorschau = { zeitprogramme: stil };
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  return { flaeche, aufrufe, wurzel: flaeche.shadowRoot };
}

const gruppe = (wurzel, name) => wurzel.querySelectorAll(".zp-gruppe").find((knoten) => knoten.dataset.gruppe === name);
const reiter = (knoten) => knoten.querySelectorAll("[role=tab]");

const befund = {};
function abschnitt(name, pruefung) {
  try {
    befund[name] = pruefung();
  } catch (err) {
    befund[name] = { fehler: String((err && err.stack) || err) };
  }
}

// --- Reiter ohne gemeinsamen Vorsatz -----------------------------------------
abschnitt("reiter", () => {
  const lesen = (wurzel, name) => {
    const knoten = gruppe(wurzel, name);
    return {
      vorsatz: text(knoten.querySelector(".zp-vorsatz")),
      namen: reiter(knoten).map((taste) => text(taste.querySelector(".zp-programmname") || taste.querySelector(".zp-mininame"))),
    };
  };
  const deutsch = bauen().wurzel;
  const englisch = bauen({
    namen: {
      "WW-Zirkulationsprogramm Temperatursteuerung": "DHW circulation program temperature control",
      "WW-Zirkulationsprogramm Zeitsteuerung": "DHW circulation program time control",
    },
  }).wurzel;
  return {
    zirkulation: lesen(deutsch, "zirkulation"),
    heizen: lesen(deutsch, "heizen"),
    englisch: lesen(englisch, "zirkulation"),
    gleich: seite.reiterNamen(["Programm", "Programm"]),
    teil: seite.reiterNamen(["Programm", "Programm 2"]),
    ohne: seite.reiterNamen(["Heizprogramm 1", "Warmwasserprogramm"]),
    bezeichnung: seite.reiterNamen(["Heizprogramm 1", "Heizprogramm 2 – Übergangszeit"]),
  };
});

// --- Gleiche Nachbartage in einer Zeile ---------------------------------------
const abwarten = async () => {
  for (let runde = 0; runde < 10; runde++) await Promise.resolve();
};
const tagesbloecke = (tage, schaltpunkte) => tage.map((tag) => ({ weekdays: [tag], switchPoints: schaltpunkte }));
const ARBEIT = punkte(["06:00", 21], ["22:00", 16]);
const FREI = punkte(["07:30", 21], ["23:00", 16]);
const EINZELN = {
  "sensor.heizprogramm_1": [...tagesbloecke(WERKTAGE, ARBEIT), ...tagesbloecke(["Sa", "Su"], FREI)],
  "sensor.heizprogramm_2": [
    { weekdays: ["Mo"], switchPoints: ARBEIT },
    { weekdays: ["Tu"], switchPoints: FREI },
    { weekdays: ["We"], switchPoints: ARBEIT },
  ],
};
const tagnamen = (wurzel) => gruppe(wurzel, "heizen").querySelectorAll(".zp-tagname").map(text);
const zeitprogrammAufrufe = (aufrufe) => aufrufe.filter((aufruf) => aufruf.dienst === "heatnexus.set_time_program");
const speichernMit = async (bloecke, aendern) => {
  const { wurzel, aufrufe } = bauen({ bloecke });
  gruppe(wurzel, "heizen").querySelector(".zp-zeile").ausloesen("click");
  const editor = gruppe(wurzel, "heizen").querySelector(".zp-zeileneditor");
  aendern(editor);
  editor.querySelector(".zp-speichern").ausloesen("click");
  await abwarten();
  return zeitprogrammAufrufe(aufrufe).map((aufruf) => aufruf.angaben.blocks);
};
{
  let zusammen;
  try {
    const { wurzel, flaeche } = bauen({ bloecke: EINZELN });
    const werktage = tagnamen(wurzel);
    const zwei = wurzel.querySelectorAll("[role=tab]").find((taste) => taste.getAttribute("aria-label") === "Heizprogramm 2");
    zwei.ausloesen("click");
    const getrennt = tagnamen(flaeche.shadowRoot);
    const unveraendert = await speichernMit(EINZELN, () => {});
    const geaendert = await speichernMit(EINZELN, (editor) => {
      const feld = editor.querySelector(".zp-wert");
      feld.value = "22";
      feld.ausloesen("change");
    });
    zusammen = { werktage, getrennt, unveraendert, geaendert };
  } catch (err) {
    zusammen = { fehler: String((err && err.stack) || err) };
  }
  befund.zusammen = zusammen;
}

// --- Der Tipp bleibt in der Spur und lässt sich schließen ----------------------
// Maße wie am Telefon: Die Spur ist 330 px breit, ein Tipp 120 px.
const masse = (name, vorgabe) =>
  Object.defineProperty(Knoten.prototype, name, {
    configurable: true,
    get() {
      return this._mass && this._mass[name] !== undefined ? this._mass[name] : vorgabe(this);
    },
  });
masse("offsetWidth", (knoten) => (knoten.classList.contains("zp-tipp") ? 120 : 0));
masse("offsetLeft", () => 0);
masse("clientWidth", () => 0);
abschnitt("tipp", () => {
  const grenzen = { min: 14, max: 24, schalt: false, art: "raum" };
  const spurBauen = () => {
    const stuecke = [{ von: 0, bis: 60, wert: 21 }, { von: 60, bis: 1380, wert: 16 }, { von: 1380, bis: 1440, wert: 21 }];
    const spur = seite.tagesspur(stuecke, grenzen, { tippen: true }).querySelector(".zp-spur");
    spur._mass = { clientWidth: 330 };
    const teile = spur.children.filter((kind) => kind.classList.contains("zp-stueck"));
    [[0, 12], [14, 290], [306, 24]].forEach(([links, breite], n) => {
      teile[n]._mass = { offsetLeft: links, offsetWidth: breite };
    });
    return { spur, teile };
  };
  const { spur, teile } = spurBauen();
  const tipp = () => spur.querySelector(".zp-tipp");
  const lage = (stueck) => {
    stueck.ausloesen("click");
    const links = tipp() ? parseFloat(tipp().style.left) : null;
    document.ausloesen("click");
    return links;
  };
  const lagen = teile.map(lage);
  teile[2].ausloesen("click");
  const offen = !!tipp();
  document.ausloesen("keydown", { key: "a" });
  const nachTaste = !!tipp();
  document.ausloesen("keydown", { key: "Escape" });
  const nachEscape = !!tipp();
  teile[1].ausloesen("click");
  const nachbar = spurBauen();
  nachbar.teile[1].ausloesen("click");
  const zweiOffen = [spur, nachbar.spur].filter((eine) => eine.querySelector(".zp-tipp")).length;
  document.ausloesen("click");
  return { lagen, offen, nachTaste, nachEscape, zweiOffen, nachKlick: !!nachbar.spur.querySelector(".zp-tipp") };
});

// --- Editor: Fokus bleibt, Escape schließt ----------------------------------------
abschnitt("editor", () => {
  const { wurzel } = bauen();
  const heizen = () => gruppe(wurzel, "heizen");
  const editor = () => heizen().querySelector(".zp-zeileneditor");
  const aktiv = () => wurzel.activeElement;
  const lage = () => {
    const element = aktiv();
    if (!element) return null;
    if (element.classList.contains("zp-zeile")) return `zeile ${element.getAttribute("aria-expanded")}`;
    return element.dataset.fokus || element.className;
  };
  const zeile = () => heizen().querySelector(".zp-zeile");
  zeile().focus();
  zeile().ausloesen("keydown", { key: "Enter" });
  const nachEnter = { lage: lage(), offen: !!editor() };
  const tippen = (wahl) => {
    const element = editor().querySelector(wahl);
    element.focus();
    element.ausloesen("click", { detail: 0 });
    return lage();
  };
  const nachMehr = tippen(".zp-ze-mehr");
  const nachTag = tippen('[data-fokus="tag:Sa"]');
  const nachWeg = tippen('[data-fokus="weg:2"]');
  editor().querySelector('[data-fokus="zeit:0"]').focus();
  editor().ausloesen("keydown", { key: "Escape" });
  const nachEscape = { lage: lage(), offen: !!editor() };
  zeile().ausloesen("keydown", { key: " " });
  editor().querySelector(".zp-abbrechen").ausloesen("click");
  const nachAbbrechen = { lage: lage(), offen: !!editor() };
  return { nachEnter, nachMehr, nachTag, nachWeg, nachEscape, nachAbbrechen };
});

// --- Pfeiltasten in Reitern und Zeilen ---------------------------------------------
abschnitt("pfeile", () => {
  const { wurzel } = bauen();
  const leiste = () => gruppe(wurzel, "zirkulation").querySelector("[role=tablist]");
  const tasten = () => reiter(gruppe(wurzel, "zirkulation"));
  const name = (element) => (element ? element.getAttribute("aria-label") : null);
  const tabulator = tasten().map((taste) => [name(taste), taste.getAttribute("tabindex")]);
  const druecken = (ort, key) => {
    ort.ausloesen("keydown", { key, target: wurzel.activeElement });
    return name(wurzel.activeElement);
  };
  tasten().find((taste) => taste.getAttribute("aria-selected") === "true").focus();
  const rechts = druecken(leiste(), "ArrowRight");
  const nochmal = druecken(leiste(), "ArrowRight");
  const ende = druecken(leiste(), "End");
  const anfang = druecken(leiste(), "Home");
  wurzel.activeElement.ausloesen("click", { detail: 0 });
  const gewaehlt = { name: name(wurzel.activeElement), ausgewaehlt: wurzel.activeElement.getAttribute("aria-selected") };
  const liste = gruppe(wurzel, "heizen").querySelector(".zp-zeilen");
  const tage = () => text(wurzel.activeElement.querySelector(".zp-tagname"));
  liste.querySelector(".zp-zeile").focus();
  const zeilen = ["ArrowDown", "ArrowUp", "End", "Home", "ArrowUp"].map((key) => {
    liste.ausloesen("keydown", { key, target: wurzel.activeElement });
    return tage();
  });
  return { tabulator, rechts, nochmal, ende, anfang, gewaehlt, zeilen };
});

// --- Vorleser: Achse still, Reiter mit „gilt“ als eigenem Wort -----------------------
const NAMEN = {
  en: { "Heizprogramm 1": "Heating program 1", "Heizprogramm 2": "Heating program 2" },
  nl: { "Heizprogramm 1": "Verwarmingsprogramma 1", "Heizprogramm 2": "Verwarmingsprogramma 2" },
};
abschnitt("vorleser", () => {
  const { wurzel } = bauen();
  const achsen = wurzel.querySelectorAll(".zp-achse").map((achse) => achse.getAttribute("aria-hidden"));
  const beschriftung = (sprache) => {
    const texte = sprache === "de" ? {} : woerterbuch(sprache);
    const ansicht = bauen({ texte, namen: NAMEN[sprache] || {} }).wurzel;
    return reiter(gruppe(ansicht, "heizen")).map((taste) => taste.getAttribute("aria-label"));
  };
  return { achsen, de: beschriftung("de"), en: beschriftung("en"), nl: beschriftung("nl") };
});

// --- Hinweis, dass Antippen Zeit und Wert zeigt --------------------------------------
abschnitt("hinweis", () => {
  const hinweise = (optionen) =>
    gruppe(bauen(optionen).wurzel, "heizen").querySelectorAll(".zp-tipphinweis").map(text);
  return {
    spur: hinweise({ stil: "spur" }),
    tabelle: hinweise({ stil: "tabelle" }),
    en: hinweise({ stil: "spur", texte: woerterbuch("en") }),
    nl: hinweise({ stil: "spur", texte: woerterbuch("nl") }),
  };
});

console.log(JSON.stringify(befund));
