// Strang im Panel: Reihen nach Kartenbreite, Live-Werte in jeder Reihe, kein Neubau ohne Not.
// Aufruf: node strang-reihen.mjs <panel.js>; gibt die Befunde als JSON aus.
import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
const uhr = browserAttrappe();
const beobachter = [];
globalThis.ResizeObserver = class {
  constructor(ruf) {
    this.ruf = ruf;
    this.getrennt = false;
    beobachter.push(this);
  }
  observe(ziel) {
    this.ziel = ziel;
  }
  disconnect() {
    this.getrennt = true;
  }
  melden(breite) {
    this.ruf([{ contentRect: { width: breite } }]);
    uhr.bilderLaufenLassen();
  }
};
await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];

const PUMPE = "binary_sensor.pumpe";
const anlage = {
  schema_svg:
    "<svg xmlns='http://www.w3.org/2000/svg'><rect/>" +
    '<text data-teil="3" x="724">Puffer</text><text data-teil="6" x="1324">Kreis</text></svg>',
  schema_breite: 48 + 7 * 200,
  schema_pumpen: [
    { titel: "Puffer", entity: PUMPE, left: "50%", top: "60%" },
    { titel: "Kreis", entity: PUMPE, left: "90%", top: "60%" },
  ],
};

function panel(einstellungen) {
  const element = new klasse();
  element._einstellungen = () => einstellungen;
  element._aufbauAbbruch = new AbortController();
  element._hass = { states: { [PUMPE]: { entity_id: PUMPE, state: "off", attributes: {} } } };
  return element;
}
const breiten = (karte) => karte.querySelectorAll(".strang-reihe").map((fenster) => fenster.style.width);
const ergebnis = {};

const element = panel({});
ergebnis.standard = element._strangWahl();
const karte = element._schaubild(anlage);
ergebnis.vorMessung = karte.querySelectorAll(".schaubild").length;
const messung = beobachter.at(-1);
messung.melden(700);
ergebnis.schmal = breiten(karte);
ergebnis.fokus = karte.querySelectorAll(".strang-reihe").map((fenster) => ({
  marken: fenster.querySelectorAll(".pumpe").map((marke) => [marke.style.left, marke.getAttribute("tabindex"), marke.getAttribute("aria-hidden")]),
  alt: fenster.querySelector("img").alt,
}));
// Die erste Grafik ist die geschnittene Zeichnung, die zweite trägt die Namen der Reihe.
const namenIn = (bild) => [...decodeURIComponent(bild.src).matchAll(/<text[^>]*>([^<]*)</g)].map((treffer) => treffer[1]);
ergebnis.namen = karte.querySelectorAll(".strang-reihe").map((fenster) => ({
  bilder: fenster.querySelectorAll("img").map(namenIn),
  geschnitten: fenster.children[0].className,
}));
element._hass.states[PUMPE].state = "on";
element._bindungen.forEach((binden) => binden());
ergebnis.laufen = karte.querySelectorAll(".pumpe").map((marke) => marke.classList.contains("laeuft"));
const ersteHuelle = karte.querySelector(".schaubild");
messung.melden(705);
ergebnis.ohneNeubau = karte.querySelector(".schaubild") === ersteHuelle;
messung.melden(2000);
ergebnis.breit = breiten(karte);
ergebnis.bindungen = element._bindungen.length;
messung.ruf([{ contentRect: { width: 700 } }]);
element._aufbauAbbruch.abort();
uhr.bilderLaufenLassen();
ergebnis.nachAbbruch = breiten(karte);
ergebnis.getrennt = messung.getrennt;

const klein = panel({ strang: "verkleinern", strang_groesse: "gross" });
const karteKlein = klein._schaubild(anlage);
beobachter.at(-1).melden(700);
ergebnis.verkleinern = breiten(karteKlein);

const ohneWahl = panel({});
ohneWahl._strangWahl = () => null;
const karteOhne = ohneWahl._schaubild(anlage);
ergebnis.ohneWahl = {
  strang: karteOhne.querySelectorAll(".schaubild-strang").length,
  huellen: karteOhne.querySelectorAll(".schaubild").length,
};

console.log(JSON.stringify(ergebnis));
