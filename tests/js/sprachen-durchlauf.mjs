/**
 * Zwei Anlagen in zwei Sprachen aufbauen und die Texte je Bereich ausgeben.
 *
 * Aufruf: `node sprachen-durchlauf.mjs <panel.js> <daten.json>`
 * Bereiche: Rahmen, Anlagenteil mit `lang`, Fenster. Ansichten: Seite der zweiten Anlage, „Alle“.
 */

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel, pfadDaten] = process.argv.slice(2);
browserAttrappe();
const daten = JSON.parse(readFileSync(pfadDaten, "utf-8"));

// Wie im Browser: Eingebaute Methoden des Elements verweigern jeden anderen Empfänger.
let flaeche = null;
const { dispatchEvent } = HTMLElement.prototype;
HTMLElement.prototype.dispatchEvent = function (ereignis) {
  if (this !== flaeche) throw new TypeError("Illegal invocation");
  return dispatchEvent.call(this, ereignis);
};

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];

const states = {};
const sammeln = (wert) => {
  if (Array.isArray(wert)) return wert.forEach(sammeln);
  if (!wert || typeof wert !== "object") return;
  Object.values(wert).forEach((inhalt) => {
    if (typeof inhalt === "string" && /^[a-z_]+\.[a-z0-9_]+$/.test(inhalt)) {
      const bereich = inhalt.split(".")[0];
      states[inhalt] = {
        entity_id: inhalt,
        state: bereich === "binary_sensor" || bereich === "switch" ? "on" : "21.5",
        attributes: { friendly_name: inhalt, unit_of_measurement: "°C", stoerung_aktiv: false, current_temperature: 20.8 },
      };
    } else sammeln(inhalt);
  });
};
sammeln(daten);

flaeche = new klasse();
const geoeffnet = [];
flaeche.addEventListener("hass-more-info", (ereignis) => geoeffnet.push(ereignis.detail.entityId));
flaeche.hass = {
  states,
  callWS: async () => ({}),
  callService: async () => true,
  formatEntityState: (zustand) => `${zustand.state} °C`,
};
flaeche.panel = { config: { daten } };
flaeche._texte = daten.texte || {};

const MERKMALE = ["title", "aria-label", "placeholder"];
/** Texte eines Teilbaums, getrennt nach Rahmen, Anlage mit eigener Sprache und Fenster. */
const texte = (wurzel, ablage, bereich = "rahmen") => {
  if (wurzel.tagName === "STYLE" || wurzel.tagName === "SCRIPT") return;
  if (wurzel.getAttribute("lang")) bereich = "anlage";
  if (wurzel.classList.contains("schleier")) bereich = "fenster";
  MERKMALE.forEach((merkmal) => {
    const wert = wurzel.getAttribute(merkmal);
    if (typeof wert === "string" && wert.trim()) ablage[bereich].add(wert.trim());
  });
  if (!wurzel.children.length) {
    const text = String(wurzel.textContent || "").trim();
    if (text) ablage[bereich].add(text);
    return;
  }
  wurzel.children.forEach((kind) => texte(kind, ablage, bereich));
};
const neu = () => ({ rahmen: new Set(), anlage: new Set(), fenster: new Set() });
const alsListen = (ablage) =>
  Object.fromEntries(Object.entries(ablage).map(([k, v]) => [k, [...v].sort()]));

const ergebnis = { seite: neu(), alle: neu(), zusammen: neu() };

// Je Anlage ein eingerichteter Heizkreis; die Sätze übersetzt der Server, hier bleiben sie leer.
const stunden = Array.from({ length: 24 }, (_, stunde) => ({ stunde, at: 10, raum: 21, aktion: "programm" }));
const automatikKreis = (anlage, nummer) => ({
  heizkreis: `SN1-${nummer}-0`,
  name: `HK ${nummer}`,
  anlage: anlage.name,
  anlage_id: anlage.id,
  eingerichtet: true,
  konfig: { aktiv: false, modus: "beobachten", profil: "standard", heizflaechen: "gemischt", ausrichtung: "eco" },
  werte: { sonnenquote: 55, lernfenster: 7 },
  zustand: "programm",
  begruendung: "",
  kennwerte: { at: 14, heizgrenze: 18, raum: 21.4, soll: 21, raeume: [] },
  tag: { sonne: [0, 0.5, 0], stunden, jetzt: 12.5 },
  vorschau: [],
  protokoll: [],
});
flaeche._automatik = {
  darf_aendern: true,
  profile: { standard: { sonnenquote: 60 } },
  heizkreise: daten.anlagen.map((anlage, i) => automatikKreis(anlage, i + 2)),
};
flaeche._automatikZeit = Date.now();

// Die Seite der zweiten Anlage, Reiter für Reiter.
flaeche._anlageIndex = 1;
for (const reiter of ["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme", "hilfe"]) {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  texte(flaeche.shadowRoot, ergebnis.seite);
}

// Die Automatik der zweiten Anlage für sich: Ihre Texte stehen nicht im Rahmen.
const automatik = neu();
flaeche._reiter = "automatik";
flaeche._gebaut = false;
flaeche._zeichnen();
flaeche._aktualisieren();
const leiste = flaeche.shadowRoot.querySelector(".leiste");
leiste.parentElement.children.filter((kind) => kind !== leiste).forEach((kind) => texte(kind, automatik));
ergebnis.automatik = automatik;

// Ein Fenster und eine Rückmeldung entstehen erst nach dem Aufbau.
flaeche._reiter = "uebersicht";
flaeche._gebaut = false;
flaeche._zeichnen();
const bereich = flaeche.shadowRoot.querySelector("[lang]");
ergebnis.lang = bereich && bereich.getAttribute("lang");
bereich.querySelector(".fragezeichen").ausloesen("click");
texte(flaeche.shadowRoot, ergebnis.seite);
bereich.querySelector(".klickbar").ausloesen("click");
ergebnis.geoeffnet = geoeffnet;

const sicht = flaeche._sicht(daten.anlagen[1]);
const anzeige = document.createElement("div");
let bestaetigt = false;
await sicht._uebertragen(anzeige, async () => {}, () => bestaetigt);
bestaetigt = true;
flaeche._aktualisieren();
ergebnis.rueckmeldung = anzeige.textContent;

// „Alle“: beide Anlagen untereinander, jede in ihrer Sprache.
flaeche._anlageIndex = -1;
for (const reiter of ["uebersicht", "steuerung", "wartung", "hilfe"]) {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  texte(flaeche.shadowRoot, ergebnis.alle);
}

// Die Automatik unter „Alle“: ein Raster, jeder Heizkreis in der Sprache seiner Anlage.
const automatikAlle = neu();
flaeche._reiter = "automatik";
flaeche._gebaut = false;
flaeche._zeichnen();
flaeche._aktualisieren();
texte(flaeche.shadowRoot, automatikAlle);
ergebnis.automatikAlle = automatikAlle;

// „Alle“ zusammen: ein Raster, jede Karte in der Sprache ihrer Anlage.
flaeche._anordnung = { ...flaeche._anordnung, einstellungen: { alle: "zusammen" } };
for (const reiter of ["uebersicht", "steuerung", "wartung", "hilfe"]) {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  texte(flaeche.shadowRoot, ergebnis.zusammen);
}

// Das „?“ einer verschmolzenen Karte erklärt in der Sprache der Oberfläche.
flaeche._reiter = "uebersicht";
flaeche._gebaut = false;
flaeche._zeichnen();
const mitErklaerung = flaeche.shadowRoot
  .querySelectorAll(".verschmolzen")
  .find((karte) => karte.children[0].querySelector(".fragezeichen"));
if (mitErklaerung) {
  mitErklaerung.children[0].querySelector(".fragezeichen").ausloesen("click");
  const fenster = flaeche.shadowRoot.querySelectorAll(".schleier").pop();
  ergebnis.erklaerung = {
    titel: String(mitErklaerung.children[0].querySelector("h2").textContent),
    text: String(fenster.querySelector(".dialog-text").textContent),
  };
}

clearInterval(flaeche._automatikUhr);
console.log(
  JSON.stringify({
    seite: alsListen(ergebnis.seite),
    alle: alsListen(ergebnis.alle),
    zusammen: alsListen(ergebnis.zusammen),
    automatik: alsListen(ergebnis.automatik),
    automatikAlle: alsListen(ergebnis.automatikAlle),
    erklaerung: ergebnis.erklaerung || null,
    lang: ergebnis.lang,
    geoeffnet: ergebnis.geoeffnet,
    rueckmeldung: ergebnis.rueckmeldung,
  })
);
