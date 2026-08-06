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
const LADEPUMPE = "binary_sensor.ww_ladepumpe";

/** Ein Panel mit nachgebildeten Zuständen und mitschreibendem Dienstaufruf. */
function panelBauen({ laedt, optionen, betriebswahl = BETRIEBSWAHL, zusatz = {} }) {
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
      [LADEPUMPE]: { entity_id: LADEPUMPE, state: laedt ? "on" : "off", attributes: {} },
    },
    callService: async (bereich, dienst, daten) => {
      gerufen.push({ bereich, dienst, daten });
    },
  };
  const eintrag = {
    entity: AUSLOESER,
    titel: "Warmwasser laden",
    titel_abbrechen: "Warmwasser laden abbrechen",
    symbol: "mdi:water-boiler",
    betriebswahl,
    betriebswahl_zurueck: "^programm",
    zustand_an: BETRIEBSART,
    zustand_wenn: ["WW-Ladung", "Warmwasser Einmalladung"],
    zustand_pumpe: LADEPUMPE,
    ...zusatz,
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

// --- Der Druck wirkt sofort, nicht erst beim nächsten Abruf ----------------
//
// Die Anlage wird alle 30 s abgefragt. Bis dahin stand unverändert „läuft" und
// dieselbe Beschriftung da – es sah aus, als sei nichts passiert, und man
// drückte noch einmal. Der zweite Druck traf dann auf den alten Zustand.
{
  const { element, taste, gerufen } = panelBauen({
    laedt: true,
    optionen: ["Standby", "Programm 1", "Heizbetrieb", "WW-Betrieb"],
  });
  element._wahlVorLadung[BETRIEBSWAHL] = "Programm 1";
  // Einmal zeichnen, wie es die Oberfläche beim Aufbau tut.
  element._bindungen.forEach((bindung) => bindung());
  const vorher = taste.querySelector(".beschriftung").textContent;
  if (vorher !== "Warmwasser laden abbrechen") {
    throw new Error(`Die laufende Ladung wird nicht angeboten: "${vorher}"`);
  }
  taste.ausloesen("click");
  await abwarten();

  // Ohne neue Zustände von der Anlage: allein der Druck muss die Anzeige
  // umstellen.
  const nachher = taste.querySelector(".beschriftung").textContent;
  if (vorher === nachher) {
    throw new Error(`Beschriftung blieb nach dem Druck auf "${nachher}"`);
  }
  if (!taste.disabled) {
    throw new Error("Taste liess sich sofort erneut druecken");
  }

  const vorZweitem = gerufen.length;
  taste.ausloesen("click");
  await abwarten();
  if (gerufen.length !== vorZweitem) {
    throw new Error("Ein zweiter Druck ging trotzdem an die Anlage");
  }
  faelle.push("Druck wirkt sofort, zweiter Druck ist gesperrt");
}

// --- Meldet die Anlage dasselbe, gibt die Annahme die Taste wieder frei -----
{
  const { element, taste } = panelBauen({
    laedt: true,
    optionen: ["Standby", "Programm 1", "Heizbetrieb", "WW-Betrieb"],
  });
  element._wahlVorLadung[BETRIEBSWAHL] = "Programm 1";
  taste.ausloesen("click");
  await abwarten();
  if (!taste.disabled) throw new Error("Taste war nach dem Druck nicht gesperrt");

  // Die Anlage bestätigt: Sie lädt nicht mehr.
  element._hass.states[BETRIEBSART].state = "Heizbetrieb";
  element._bindungen.forEach((bindung) => bindung());
  if (taste.disabled) {
    throw new Error("Taste blieb gesperrt, obwohl die Anlage bestaetigt hat");
  }
  faelle.push("bestaetigte Bedienung gibt die Taste sofort wieder frei");
}

// --- Die nachlaufende Ladepumpe ist keine laufende Ladung ------------------
//
// Der gemeldete Fehler: Nach dem Abbrechen schaltete die Anlage sofort um, die
// Ladepumpe lief aber weiter (`5/5` Modus Ladepumpennachlauf). Weil die Pumpe
// vor der Betriebsart abgefragt wurde, meldete die Taste wieder "laeuft" und
// bot ein zweites Mal Abbrechen an - fuer eine Ladung, die es nicht mehr gab.
{
  const { element, taste } = panelBauen({
    laedt: false,
    optionen: ["Standby", "Programm 1", "WW-Betrieb"],
  });
  // Anlage: Heizbetrieb. Pumpe: laeuft noch nach.
  element._hass.states[LADEPUMPE].state = "on";
  element._bindungen.forEach((bindung) => bindung());

  const beschriftung = taste.querySelector(".beschriftung").textContent;
  if (beschriftung !== "Warmwasser laden") {
    throw new Error(`Nachlaufende Pumpe gilt als Ladung: "${beschriftung}"`);
  }
  faelle.push("nachlaufende Pumpe gilt nicht als laufende Ladung");
}

// --- Ohne lesbare Betriebsart bleibt die Pumpe der Beleg -------------------
//
// An einem Kreis mit nur einem zulaessigen Wert meldet die Betriebsart den
// Ladezustand gar nicht. Dann ist die Pumpe alles, was es gibt.
{
  const { element, taste } = panelBauen({
    laedt: false,
    optionen: ["Standby", "WW-Betrieb"],
  });
  element._hass.states[BETRIEBSART].state = "unavailable";
  element._hass.states[LADEPUMPE].state = "on";
  element._bindungen.forEach((bindung) => bindung());

  const beschriftung = taste.querySelector(".beschriftung").textContent;
  if (beschriftung !== "Warmwasser laden abbrechen") {
    throw new Error(`Ohne Betriebsart zaehlt die Pumpe nicht: "${beschriftung}"`);
  }
  faelle.push("ohne lesbare Betriebsart bleibt die Pumpe der Beleg");
}

// --- Aus einem Programm heraus wird nichts gemerkt -------------------------
//
// Der gemeldete Fehler: Ladung aus „Programm 1" gestartet, Abbrechen ohne
// Wirkung – auch in der Windhager-App lief sie weiter. Die Anlage stellt die
// Betriebswahl während einer Ladung selbst auf WW-Betrieb und kehrt danach
// allein zurück; das Bediengerät schreibt zum Abbrechen nur die Freigabe auf
// Nein. Weil hier bei **jedem** Start gemerkt wurde, schickte das Abbrechen
// hinterher noch eine Betriebswahl – und die Ladung lief weiter.
{
  const zusatz = { betriebswahl_aus: "^standby", betriebswahl_ww: "ww" };
  const { element, taste, gerufen } = panelBauen({
    laedt: false,
    optionen: ["Standby", "Programm 1", "Heizbetrieb", "WW-Betrieb"],
    zusatz,
  });
  element._hass.states[BETRIEBSWAHL].state = "Programm 1";
  taste.ausloesen("click");
  await abwarten();
  if (gerufen.some((r) => r.dienst === "select_option")) {
    throw new Error("aus einem Programm heraus wurde die Betriebswahl verstellt");
  }
  if (element._wahlVorLadung[BETRIEBSWAHL] !== undefined) {
    throw new Error("gemerkt, obwohl nichts verstellt wurde");
  }
  faelle.push("Start aus einem Programm: nichts verstellt, nichts gemerkt");

  // Jetzt läuft die Ladung, die Anlage meldet von sich aus WW-Betrieb.
  element._hass.states[BETRIEBSART].state = "Warmwasser Einmalladung";
  element._hass.states[BETRIEBSWAHL].state = "WW-Betrieb";
  element._ladungAnnahmen = {};
  gerufen.length = 0;
  element._bindungen.forEach((bindung) => bindung());
  taste.ausloesen("click");
  await abwarten();
  if (!gerufen.some((r) => r.dienst === "turn_off" && r.daten.entity_id === AUSLOESER)) {
    throw new Error("Abbruch nahm die Freigabe nicht zurück");
  }
  if (gerufen.some((r) => r.dienst === "select_option")) {
    throw new Error("Abbruch schickte eine überflüssige Betriebswahl hinterher");
  }
  faelle.push("Abbruch aus einem Programm: nur die Freigabe zurück");
}

console.log(JSON.stringify({ faelle }, null, 1));
