// Reine Hilfen des Reiters „Automatik“ in Node prüfen.
// Aufruf: node automatik-test.mjs <Pfad zu teile/automatik.js>
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const modul = await import(pathToFileURL(process.argv[2]).href);
const { zahl, uhrzeit, tagesleisteSvg, wetterSymbol, korrekturText, kelvin, raumzeile, FELDER, ZUSTAENDE } = modul;

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
    "anpassen",
    "budget",
    "entscheidung",
    "fenster_k_je_h",
    "heizgrenze",
    "hysterese",
    "lernfenster",
    "mindestdauer_h",
    "nachpruefung",
    "rueckkehr_k",
    "ruhe_h",
    "sonnenquote",
    "sonnentag",
    "stark",
    "stark_k",
    "tau_h",
  ]
);
assert.equal(Object.keys(ZUSTAENDE).length, 9);

// Abweichung der Räume von ihrem Ziel, mit echtem Minuszeichen.
assert.equal(kelvin(-0.14), "−0,1 K");
assert.equal(kelvin(0.5), "+0,5 K");
assert.equal(kelvin(null), "–");
assert.equal(raumzeile({ name: "Bad", wert: 20.8, ziel: 21, heizt: true }), "Bad 20,8 °C → 21,0 °C · heizt");
assert.equal(raumzeile({ name: "Küche", wert: 18.9, ziel: null, heizt: null }), "Küche 18,9 °C");

// Temperaturen: gemessen bis jetzt, angepasste Prognose ab jetzt, Heizgrenze.
const mitTemperatur = tagesleisteSvg(
  {
    jetzt: 12.5,
    stunden: Array.from({ length: 24 }, (_, h) => ({ stunde: h, at: 10 + h / 2, korrigiert: 9 + h / 2, roh: 10 + h / 2 })),
  },
  1000,
  17
);
assert.ok(mitTemperatur.includes("al-aussen"));
assert.ok(mitTemperatur.includes("al-prognose"));
assert.ok(mitTemperatur.includes("al-grenze"));
assert.ok(!/NaN|undefined/.test(mitTemperatur), mitTemperatur);

assert.equal(wetterSymbol(10, true), "☀");
assert.equal(wetterSymbol(50, true), "⛅");
assert.equal(wetterSymbol(90, true), "☁");
assert.equal(wetterSymbol(10, false), "☾");

assert.equal(korrekturText("temperatur", { versatz: -1.4, tage: 9 }, 7), "Außen angepasst −1,4 K");
assert.equal(korrekturText("temperatur", { versatz: null, tage: 3 }, 7), "Außen: lernt noch 3/7");
assert.equal(korrekturText("sonne", { aktiv: true, faktor: 0.88, tage: 8 }, 7), "Sonne angepasst −12 %");
assert.equal(korrekturText("sonne", { aktiv: false }, 7), "Sonne unkorrigiert");
console.log("ok");
