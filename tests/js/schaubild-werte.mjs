// Werte im Schaubild: Lage und Größe nach der Darstellung, Wertleiste je Reihe, Füllstand.
// Aufruf: node schaubild-werte.mjs <panel.js>; gibt die Befunde als JSON aus.
import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
const uhr = browserAttrappe();
const beobachter = [];
globalThis.ResizeObserver = class {
  constructor(ruf) {
    this.ruf = ruf;
    beobachter.push(this);
  }
  observe() {}
  disconnect() {}
  melden(breite) {
    this.ruf([{ contentRect: { width: breite } }]);
    uhr.bilderLaufenLassen();
  }
};
await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];

const zustand = (state, unit) => ({ state, attributes: unit ? { unit_of_measurement: unit } : {} });
// Sieben Anlagenteile; 50 % liegt in Teil 3, 90 % in Teil 6, 5 % in Teil 0.
const anlage = {
  schema_svg: "<svg xmlns='http://www.w3.org/2000/svg'/>",
  schema_breite: 48 + 7 * 200,
  schema_werte: [
    { entity: "sensor.kessel", left: "50%", top: "40%", beschriftung: null, name: "Kessel" },
    { entity: "sensor.cop", left: "90%", top: "60%", beschriftung: "COP", name: "COP" },
  ],
  schema_vorrat: [
    {
      art: "behaelter",
      entity: "sensor.behaelter",
      titel: "PuroWIN",
      stufen: { "Vorratsbehälter voll": "voll", "Fehler Vorratsbehälter ": "fehler" },
      left: "3%",
      top: "36%",
      breite: "2%",
      hoehe: "27%",
      bild: "<svg><g class='koerner-flaeche'></g><path class='umriss-linie'/></svg>",
    },
    { art: "fuellgrad", entity: "sensor.lager", titel: "BioWIN", left: "5%", top: "27%" },
    {
      art: "behaelter",
      entity: "sensor.lager",
      titel: "BioWIN",
      anteil: true,
      fest: "33.85%",
      left: "4%",
      top: "36%",
      breite: "2%",
      hoehe: "27%",
      bild: "<svg><g class='koerner-flaeche'></g><path class='umriss-linie'/></svg>",
    },
  ],
};

function panel(einstellungen, lager = "63") {
  const element = new klasse();
  element._einstellungen = () => einstellungen;
  element._aufbauAbbruch = new AbortController();
  element._hass = {
    states: {
      "sensor.kessel": zustand("71.5", "°C"),
      "sensor.cop": zustand("3.6"),
      "sensor.behaelter": zustand("Vorratsbehälter voll"),
      "sensor.lager": zustand(lager, "%"),
    },
  };
  return element;
}

function aufbauen(einstellungen, breite, lager) {
  const element = panel(einstellungen, lager);
  const karte = element._schaubild(anlage);
  beobachter.at(-1).melden(breite);
  element._bindungen.forEach((binden) => binden());
  return karte;
}

const leisten = (karte) =>
  karte.querySelectorAll(".strang-reihe").map((fenster) => {
    const leiste = fenster.querySelector(".wertleiste");
    if (!leiste) return null;
    return leiste.children.map((spalte) =>
      spalte.children.filter((zeile) => !zeile.hidden).map((zeile) => zeile.textContent)
    );
  });
const marken = (karte) =>
  karte.querySelectorAll(".marke-wert").filter((marke) => !marke.hidden).map((marke) => marke.textContent);

const ergebnis = {};

const unter = aufbauen({ werte_lage: "unter" }, 700);
ergebnis.unter_leisten = leisten(unter);
ergebnis.unter_marken = marken(unter);
ergebnis.unter_hoehe = unter.querySelectorAll(".strang-reihe").map((fenster) => fenster.style.height);

const bild = aufbauen({ werte_lage: "bild" }, 700);
ergebnis.bild_leisten = leisten(bild);
ergebnis.bild_marken = marken(bild);
ergebnis.bild_je_reihe = bild.querySelectorAll(".strang-reihe").map(marken);

// Verkleinern auf 700 px: ein Teil steht unter 100 px breit, die Zahlen rücken unter das Bild.
ergebnis.auto_schmal = leisten(aufbauen({ strang: "verkleinern" }, 700)).length;
ergebnis.auto_schmal_leiste = Boolean(leisten(aufbauen({ strang: "verkleinern" }, 700))[0]);
ergebnis.auto_breit_leiste = Boolean(leisten(aufbauen({ strang: "verkleinern" }, 2000))[0]);

ergebnis.lager_null = marken(aufbauen({ werte_lage: "bild" }, 2000, "0"));

const behaelter = aufbauen({}, 2000).querySelector(".vorrat");
ergebnis.behaelter = [behaelter.dataset.stufe, behaelter.hidden, behaelter.children.map((teil) => teil.className)];

const lagerfuellung = (lager) => {
  const flaeche = aufbauen({}, 2000, lager).querySelectorAll(".vorrat")[1];
  return [flaeche.dataset.stufe, flaeche.hidden, flaeche.style["--hn-leer"]];
};
ergebnis.lagerfuellung = ["63", "0", "unavailable"].map(lagerfuellung);

// Der Lüfter einer Wärmepumpe: an der Leistung (AeroWIN) oder an der Wärmelieferung (fremd).
const lueftend = (lieferung, leistung) => {
  const element = panel({});
  element._hass.states["binary_sensor.wp_lieferung"] = zustand(lieferung);
  element._hass.states["sensor.wp_leistung"] = zustand(leistung, "kW");
  const lage = { left: "1%", top: "1%", breite: "1%", hoehe: "1%", rad_left: "1%", rad_top: "1%", rad_groesse: "1%" };
  const karte = element._schaubild({
    schema_svg: anlage.schema_svg,
    schema_breite: 448,
    schema_luefter: [
      { ...lage, entity: "binary_sensor.wp_lieferung", titel: "Wärmepumpe" },
      { ...lage, entity: "sensor.wp_leistung", titel: "AeroWIN" },
    ],
  });
  beobachter.at(-1).melden(448);
  element._bindungen.forEach((binden) => binden());
  return karte
    .querySelectorAll(".uebergabe-rad")
    .filter((rad) => rad.classList.contains("luefter"))
    .map((rad) => rad.classList.contains("an"));
};
ergebnis.luefter = [lueftend("on", "4.2"), lueftend("off", "0")];

ergebnis.schrift = ["klein", "mittel", "gross", undefined].map((groesse) =>
  panel(groesse ? { werte_groesse: groesse } : {})._schriftmass()
);

// Die Fläche über dem Bild: Tooltip, Klick und Platz direkt hinter der Zeichnung.
const zielAngaben = (element, ziel) => {
  if (!ziel) return null;
  let geoeffnet = null;
  const huelle = ziel.parentElement;
  element.addEventListener("hass-more-info", (ereignis) => {
    geoeffnet = ereignis.detail.entityId;
  });
  ziel.ausloesen("click");
  const geschwister = huelle.children;
  return {
    titel: ziel.title,
    klickbar: ziel.classList.contains("klickbar"),
    nachBild: geschwister[geschwister.indexOf(ziel) - 1]?.tagName?.toLowerCase() === "img",
    geoeffnet,
  };
};

// Ein Puffer mit mittlerem Fühler und Beladegrad: zwei oder drei Zahlen nach der Darstellung.
const puffer = (einstellungen, beladegrad = "38") => {
  const element = panel(einstellungen);
  Object.assign(element._hass.states, {
    "sensor.oben": zustand("60.5", "°C"),
    "sensor.mitte": zustand("50.7", "°C"),
    "sensor.unten": zustand("46.6", "°C"),
    "sensor.bg": zustand(beladegrad, "%"),
  });
  const lage = { left: "50%", top: "50%", breite: "20%", hoehe: "40%", ecke: "1%" };
  const karte = element._schaubild({
    schema_svg: anlage.schema_svg,
    schema_breite: 448,
    schema_werte: [
      { entity: "sensor.oben", left: "50%", top: "40%", beschriftung: null, name: "oben" },
      { entity: "sensor.unten", left: "50%", top: "60%", beschriftung: null, name: "unten" },
    ],
    schema_werte_mitte: [{ entity: "sensor.mitte", left: "50%", top: "50%", beschriftung: null, name: "mitte" }],
    schema_schichtung: [
      { ...lage, oben: "sensor.oben", mitte: "sensor.mitte", unten: "sensor.unten", beladegrad: "sensor.bg",
        kalt: 25, heiss: 80, grund: "grau", titel: "Puffer" },
    ],
    schema_speicher: [
      { left: "50%", top: "50%", top_drei: "30%", mitte: "sensor.mitte", oben: "sensor.oben",
        unten: "sensor.unten", laden: null, quellen: [], entnahme: [], kessel: null, toleranz: 0.5, titel: "Puffer" },
    ],
  });
  beobachter.at(-1).melden(448);
  element._bindungen.forEach((binden) => binden());
  return {
    marken: marken(karte),
    wort: karte.querySelector(".speicher").style.top,
    titel: karte.querySelector(".schichtung").title,
    ziel: zielAngaben(element, karte.querySelector(".schichtung-ziel")),
  };
};
ergebnis.puffer_zwei = puffer({ werte_lage: "bild" });
ergebnis.puffer_drei = puffer({ werte_lage: "bild", puffer_werte: "drei" });
ergebnis.puffer_ohne_beladegrad = puffer({ werte_lage: "bild" }, "unavailable");

console.log(JSON.stringify(ergebnis));
