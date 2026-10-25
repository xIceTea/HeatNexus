// Kesselzustand aus der Beschreibung des Servers auswerten.
// Aufruf: node kesselzustand-test.mjs <Pfad zu teile/kesselzustand.js>
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const { kesselzustand } = await import(pathToFileURL(process.argv[2]).href);

const b = {
  bezug: "sensor.art", betriebsart: "sensor.art", betriebswahl: "sensor.wahl", phase: "sensor.phase",
  serviceausbrand: ["Serviceausbrand"],
  offline: { text: "Steuerung nicht erreichbar", symbol: "mdi:lan-disconnect" },
  regeln: [
    { quelle: "betriebsart", wenn: ["Abschaltvorgang"], serviceausbrand: true, text: "Serviceausbrand läuft", symbol: "mdi:fire-off" },
    { quelle: "betriebsart", wenn: ["Ausgeschaltet"], serviceausbrand: true, text: "Kessel aus nach Serviceausbrand", symbol: "mdi:fire-off" },
    { quelle: "betriebsart", wenn: ["Kaminkehrerfunktion"], serviceausbrand: null, text: "Kaminkehrer aktiv", symbol: "mdi:account-hard-hat" },
    { quelle: "betriebsart", wenn: ["Aktorentest"], serviceausbrand: null, text: null, symbol: "mdi:wrench" },
    { quelle: "betriebsart", wenn: ["Abschaltvorgang"], serviceausbrand: false, text: "Kessel schaltet ab", symbol: "mdi:power" },
    { quelle: "betriebsart", wenn: ["Ausgeschaltet"], serviceausbrand: false, text: "Kessel ausgeschaltet", symbol: "mdi:power-off" },
    { quelle: "phase", wenn: ["Brenner gesperrt"], serviceausbrand: null, text: null, symbol: "mdi:lock-outline" },
  ],
};
const lage = (art, wahl, phase) => (id) =>
  ({ "sensor.art": art, "sensor.wahl": wahl, "sensor.phase": phase }[id] === undefined
    ? undefined
    : { state: { "sensor.art": art, "sensor.wahl": wahl, "sensor.phase": phase }[id] });

// Ablauf eines Serviceausbrands: Abschaltvorgang, Ausgeschaltet, nicht erreichbar, wieder im Betrieb.
assert.equal(kesselzustand(b, lage("Abschaltvorgang", "Serviceausbrand", "Ausbrand")).text, "Serviceausbrand läuft");
assert.equal(kesselzustand(b, lage("Ausgeschaltet", "Serviceausbrand", "Brenner gesperrt")).text, "Kessel aus nach Serviceausbrand");
assert.equal(kesselzustand(b, lage("unavailable", "unavailable", "unavailable")).text, "Steuerung nicht erreichbar");
assert.equal(kesselzustand(b, lage("Kessel-Temperatur", "EIN", "Modulation")), null);
// Ohne Serviceausbrand: gewöhnliches Aus.
assert.equal(kesselzustand(b, lage("Ausgeschaltet", "AUS", "Brenner gesperrt")).text, "Kessel ausgeschaltet");
// Eingriffe und Text der Anlage.
assert.equal(kesselzustand(b, lage("Kaminkehrerfunktion", "Kaminkehrer", "Modulation")).text, "Kaminkehrer aktiv");
const test = kesselzustand(b, lage("Aktorentest", "Aktorentest", "Selbsttest"));
assert.deepEqual([test.text, test.uebersetzen], ["Aktorentest", false]);
// Gesperrter Brenner im normalen Betrieb.
const sperre = kesselzustand(b, lage("Kessel-Temperatur", "EIN", "Brenner gesperrt"));
assert.deepEqual([sperre.text, sperre.symbol, sperre.uebersetzen], ["Brenner gesperrt", "mdi:lock-outline", false]);
// „unknown“ nach dem Start ist kein Ausfall.
assert.equal(kesselzustand(b, lage("unknown", "unknown", "unknown")), null);
// Ohne Beschreibung nichts.
assert.equal(kesselzustand(null, lage("Ausgeschaltet")), null);
console.log("ok");
