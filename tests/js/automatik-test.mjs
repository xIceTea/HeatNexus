// Reine Hilfen des Reiters „Automatik“ in Node prüfen.
// Aufruf: node automatik-test.mjs <Pfad zu teile/automatik.js>
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const modul = await import(pathToFileURL(process.argv[2]).href);
const { zahl, kelvin, raumzeile, FELDER, ZUSTAENDE } = modul;
const tagesbild = await import(new URL("./tagesbild.js", pathToFileURL(process.argv[2])).href);
const { uhrzeit, tagesleisteSvg, tagesleisteTipp, stundenKasten, wetterSymbol, istHell, korrekturMarken, tagesleisteBereich } = tagesbild;

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
    "grenze_versatz",
    "hysterese",
    "lernfenster",
    "melden",
    "mindestdauer_h",
    "nachpruefung",
    "rueckkehr_k",
    "ruhe_h",
    "sonnenquote",
    "sonnentag",
    "spielraum_k",
    "stark",
    "stark_k",
    "tau_h",
  ]
);
assert.equal(Object.keys(ZUSTAENDE).length, 10);

// Abweichung der Räume von ihrem Ziel, mit echtem Minuszeichen.
assert.equal(kelvin(-0.14), "−0,1 K");
assert.equal(kelvin(0.5), "+0,5 K");
assert.equal(kelvin(null), "–");
assert.equal(raumzeile({ name: "Bad", wert: 20.8, ziel: 21, heizt: true }), "Bad 20,8 °C → 21,0 °C · heizt");
assert.equal(raumzeile({ name: "Küche", wert: 18.9, ziel: null, heizt: null }), "Küche 18,9 °C");
assert.equal(raumzeile({ name: "Bad", wert: 20.1, ziel: null, heizt: false, aus: true }), "Bad 20,1 °C · aus");

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

// Tageslicht folgt Auf- und Untergang, nicht der Einstrahlung: bedeckter Mittag bleibt hell.
const bedeckt = { aufgang: 7.2, untergang: 18.9, sonne: Array(25).fill(0) };
assert.equal(istHell(bedeckt, 14), true);
assert.equal(istHell(bedeckt, 7), false);
assert.equal(istHell(bedeckt, 20), false);
assert.equal(wetterSymbol(100, istHell(bedeckt, 14)), "☁");
// Ohne Auf- und Untergang zählt weiter die Einstrahlung.
assert.equal(istHell({ sonne: [0, 0.4] }, 1), true);
assert.equal(istHell({ sonne: [0, 0.4] }, 0), false);


// Wirkung der Prognoseanpassung: Versatz in K, Sonne in Prozent, sonst der Lernstand.
assert.deepEqual(korrekturMarken(null), []);
assert.deepEqual(
  korrekturMarken({ an: true, noetig: 7, temperatur: { versatz: null, tage: 2 }, sonne: { aktiv: true, faktor: null, tage: 1 } }),
  [
    { text: "Außen lernt noch 2/7", wirkt: false },
    { text: "Sonne lernt noch 1/7", wirkt: false },
  ]
);
assert.deepEqual(
  korrekturMarken({ an: true, noetig: 7, temperatur: { versatz: -1.4, tage: 9 }, sonne: { aktiv: true, faktor: 1.12, tage: 8 } }),
  [
    { text: "Außen −1,4 K", wirkt: true },
    { text: "Sonne +12 %", wirkt: true },
  ]
);
// Vor dem letzten Lerntag steht der bisherige Wert als vorläufig da und wirkt nicht.
assert.deepEqual(
  korrekturMarken({
    an: true,
    noetig: 7,
    temperatur: { versatz: null, versatz_bisher: -0.8, tage: 2 },
    sonne: { aktiv: true, faktor: null, faktor_bisher: 1.12, tage: 1 },
  }),
  [
    { text: "Außen −0,8 K (vorläufig 2/7)", wirkt: false },
    { text: "Sonne +12 % (vorläufig 1/7)", wirkt: false },
  ]
);
// Ausgeschaltet bleibt die Wirkung sichtbar, aber nicht als wirksam markiert.
assert.deepEqual(korrekturMarken({ an: false, noetig: 7, temperatur: { versatz: 0.5 }, sonne: { aktiv: false } }), [
  { text: "Außen +0,5 K", wirkt: false },
]);

// Das Band unten zeigt den Modus je Stunde; künftige Stunden sind als Plan markiert.
const band = tagesleisteSvg({
  jetzt: 12.5,
  stunden: Array.from({ length: 24 }, (_, h) => ({ stunde: h, aktion: h >= 11 && h < 20 ? "nur_ww" : "programm" })),
});
assert.ok(band.includes('class="al-m-programm"'));
assert.ok(band.includes('class="al-m-nur_ww"'));
assert.ok(band.includes('class="al-m-nur_ww al-plan"'));
assert.equal(tagesleisteBereich({}), null);
const bereich = tagesleisteBereich({ stunden: [{ stunde: 0, at: 10 }] }, 20);
assert.ok(bereich.prozent(20) < bereich.prozent(10));

// Werte unter dem Zeiger im Tagesbild: nur, was für die Stunde vorliegt.
const tagMitWerten = {
  sonne: Array.from({ length: 25 }, (_, h) => (h === 10 ? 0.5 : 0)),
  stunden: [
    { stunde: 10, at: 12.9, korrigiert: 13.8, gedaempft: 12.41, raum: 20.55, aktion: "absenkung" },
    { stunde: 20, at: null, korrigiert: 18.1, gedaempft: null, raum: null, aktion: "programm" },
  ],
};
assert.deepEqual(tagesleisteTipp(tagMitWerten, 10), [
  "10:00 · Sonnentag",
  "Außen gemessen 12,9 °C",
  "Außen Prognose 13,8 °C",
  "gedämpfte AT 12,4 °C",
  "Räume 20,6 °C",
  "Sonne 50 %",
]);
assert.deepEqual(tagesleisteTipp(tagMitWerten, 20), ["20:00 · Programm", "Außen Prognose 18,1 °C"]);
assert.deepEqual(tagesleisteTipp({}, 5), ["05:00"]);
// Skalen der Kennwerte: Lage eines Werts in Prozent, an den Rändern begrenzt.
// Kasten einer Stunde: nur Protokolleinträge von heute aus dieser Stunde.
const halbAcht = new Date();
halbAcht.setHours(7, 30, 0, 0);
const zehnNachNeun = new Date();
zehnNachNeun.setHours(9, 10, 0, 0);
const kasten = stundenKasten(
  { stunden: [{ stunde: 7, aktion: "absenkung", vorrang: true, at: 9.3, raum: 20.5 }] },
  7,
  [
    { zeit: zehnNachNeun.toISOString(), art: "geschrieben", text: "anders", werte: [] },
    { zeit: halbAcht.toISOString(), art: "geschrieben", text: "Sonnenquote 82 % – 21,0 °C bis 16:54.", werte: [] },
  ]
);
assert.equal(kasten[0], "07:00–08:00 · Sonnentag");
assert.ok(kasten.includes("07:30 Sonnenquote 82 % – 21,0 °C bis 16:54."));
assert.ok(!kasten.some((z) => z.startsWith("09:10")));
assert.ok(kasten.includes("Vorrangquelle lieferte"));
assert.ok(kasten.includes("Außen gemessen 9,3 °C"));
assert.ok(kasten.includes("Räume 20,5 °C"));
assert.equal(stundenKasten({ stunden: [] }, 23, [])[0], "23:00–24:00 · Programm");

const kennwerte = await import(new URL("./kennwerte.js", pathToFileURL(process.argv[2])).href);
assert.equal(kennwerte.skalaProzent(18, 6, 26), 60);
assert.equal(kennwerte.skalaProzent(40, 6, 26), 100);
assert.equal(kennwerte.skalaProzent(-3, 6, 26), 0);
assert.equal(kennwerte.skalaProzent(null, 0, 10), null);
assert.deepEqual(kennwerte.aussenBereich(18), [6, 26]);
assert.deepEqual(kennwerte.aussenBereich(null), [5, 25]);
console.log("ok");
