// Reine Hilfen des Reiters „Automatik“ in Node prüfen.
// Aufruf: node automatik-test.mjs <Pfad zu teile/automatik.js>
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const modul = await import(pathToFileURL(process.argv[2]).href);
const { zahl, uhrzeit, tagesleisteSvg, FELDER, ZUSTAENDE } = modul;

assert.equal(zahl(19.5), "19,5");
assert.equal(zahl(78, 0), "78");
assert.equal(zahl(null), "–");
assert.equal(zahl("x"), "–");

assert.equal(uhrzeit(16.6667), "16:40");
assert.equal(uhrzeit(7), "07:00");

const leer = tagesleisteSvg({});
assert.ok(leer.startsWith("<svg"));
assert.ok(!leer.includes("al-absenkung"));

const tag = {
  sonne: Array.from({ length: 25 }, (_, h) => (h > 7 && h < 19 ? 0.5 : 0)),
  absenkung_von: 7,
  absenkung_bis: 13.667,
  absenkung_ziel: 16.917,
  entscheidungen: [7],
  jetzt: 11.33,
};
const bild = tagesleisteSvg(tag, 1000);
assert.ok(bild.includes("al-sonne"));
assert.ok(bild.includes('class="al-absenkung" x="291.7"'));
assert.ok(bild.includes("al-verlaengerung"));
assert.ok(bild.includes("al-jetzt"));
assert.ok(!/NaN|undefined/.test(bild), bild);

const namen = FELDER.map((feld) => feld.name);
assert.deepEqual(
  [...namen].sort(),
  [
    "absenkung_k",
    "budget",
    "entscheidung",
    "fenster_k_je_h",
    "heizgrenze",
    "hysterese",
    "mindestdauer_h",
    "nachpruefung",
    "rueckkehr_k",
    "sonnenquote",
    "stark",
    "tau_h",
  ]
);
assert.equal(Object.keys(ZUSTAENDE).length, 9);
console.log("ok");
