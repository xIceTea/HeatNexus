// Reihenplanung des Strangs im Schaubild in Node prüfen.
// Aufruf: node strang-test.mjs <Pfad zu teile/strang.js>
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const { teileAus, reihenPlanen } = await import(pathToFileURL(process.argv[2]).href);

assert.equal(teileAus(400), 1);
assert.equal(teileAus(448), 2);
assert.equal(teileAus(1448), 7);

const plan = (teile, verfuegbar, modus, groesse) =>
  reihenPlanen({ teile, breite: Math.max(48 + teile * 200, 400), verfuegbar, modus, groesse });

// Passt der Strang, bleibt er in einer Reihe und in der gewählten Größe.
assert.deepEqual(plan(4, 1200, "umbrechen", 120), { massstab: 0.6, reihen: [[0, 4]] });
// Sieben Teile bei Platz für fünf: ausgeglichen 4 + 3, nicht 5 + 2.
assert.deepEqual(plan(7, 700, "umbrechen", 120).reihen, [[0, 4], [4, 3]]);
assert.equal(plan(7, 700, "umbrechen", 120).massstab, 0.6);
assert.deepEqual(plan(6, 500, "umbrechen", 120).reihen, [[0, 3], [3, 3]]);
// Passt nicht einmal ein Teil, schrumpft es auf die Kartenbreite.
const eng = plan(3, 100, "umbrechen", 160);
assert.deepEqual(eng.reihen, [[0, 1], [1, 1], [2, 1]]);
assert.equal(eng.massstab, 100 / 248);
// Verkleinern: eine Reihe auf der Kartenbreite, die Größe gilt nicht.
assert.deepEqual(plan(7, 700, "verkleinern", 120), { massstab: 700 / 1448, reihen: [[0, 7]] });
assert.equal(plan(7, 2000, "verkleinern", 120).massstab, 2000 / 1448);
// Elf Teile bei Platz für fünf: 4 + 4 + 3.
assert.deepEqual(plan(11, 700, "umbrechen", 120).reihen, [[0, 4], [4, 4], [8, 3]]);
// Drei Reihen bleiben ausgeglichen: 7 → 3 + 2 + 2, 10 → 3 + 3 + 2 + 2.
assert.deepEqual(plan(7, 450, "umbrechen", 120).reihen, [[0, 3], [3, 2], [5, 2]]);
assert.deepEqual(plan(10, 500, "umbrechen", 120).reihen, [[0, 3], [3, 3], [6, 2], [8, 2]]);
// Ein Teil passt in 300 px bei 120 px Größe: eine Reihe, Maßstab 0,6.
assert.deepEqual(plan(1, 300, "umbrechen", 120), { massstab: 0.6, reihen: [[0, 1]] });

console.log("ok");
