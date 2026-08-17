/**
 * Die Lovelace-Karte im Node-Durchlauf.
 *
 * Geprüft wird der Vertrag, den Home Assistant an eine Karte stellt: sofortige
 * Registrierung, `setConfig` vor `hass`, und ein Bild, sobald Daten da sind.
 */

import { readFileSync } from "node:fs";
import { browserAttrappe } from "./dom-attrappe.mjs";

const [, , modulPfad, datenPfad] = process.argv;
browserAttrappe();

const anlagen = JSON.parse(readFileSync(datenPfad, "utf-8"));
const bilanz = {};

// Das Modul definiert beim Laden, ohne Umweg über ein `await`.
await import(modulPfad);
bilanz.sofortRegistriert = !!customElements.get("heatnexus-schaubild");
bilanz.inKartenauswahl = (window.customCards || []).some((k) => k.type === "heatnexus-schaubild");

const Klasse = customElements.get("heatnexus-schaubild");
bilanz.stubHatTyp = Klasse.getStubConfig().type === "custom:heatnexus-schaubild";
const editor = await Klasse.getConfigElement();
bilanz.editorElement = editor.tagName.toLowerCase();
editor.setConfig({});
editor.hass = { states: {}, callWS: async () => anlagen };
await editor._laden;
bilanz.editorFelder = editor._schema().map((f) => f.name);
bilanz.editorAnlagen = editor._schema()[0].selector.select.options.map((o) => o.label);
// Je Anlagenteil ein Abschnitt mit Kästchen, vorbelegt mit der Vorgabe.
editor.setConfig({ anlage: anlagen[0].id });
const bildAb = editor._schema().find((f) => f.name === "bild_ab");
const jeTeil = bildAb.schema.find((f) => f.name === "werte");
bilanz.abschnitteJeTeil = jeTeil.schema.map((f) => editor._beschriftung(f));
bilanz.werteAuswaehlbar = jeTeil.schema[0].selector.select.multiple === true;
bilanz.vorbelegt = (editor._daten().werte[jeTeil.schema[0].name] || []).length > 0;
bilanz.zusatzwerteVorrat = editor
  ._schema()
  .find((f) => f.name === "liste_ab")
  .schema[0].selector.select.options.length;

const karte = new Klasse();
// Reihenfolge wie in Home Assistant: erst die Konfiguration, dann `hass`.
karte.setConfig({ farbsatz: "petrol" });
bilanz.groesseOhneHass = karte.getCardSize();
bilanz.rasterOhneHass = karte.getGridOptions();

const hass = {
  states: {},
  themes: { darkMode: true },
  callWS: async () => anlagen,
};
karte.hass = hass;
await karte._laden;

const bild = karte.shadowRoot.querySelector("img");
bilanz.bildVorhanden = !!bild;
bilanz.bildAdresse = bild ? String(bild.src).slice(0, 30) : null;

// Maßstab und Laufrad: Die Überlagerungen sollen mit dem Bild wachsen, und
// das Rad ist eine eigene Zeichnung statt eines Symbols.
const huelle = karte.shadowRoot.querySelector(".schaubild");
bilanz.einheitGesetzt = !!huelle && String(huelle.style["--hn-einheit"] || "").endsWith("cqw");
const pumpe = karte.shadowRoot.querySelector(".pumpe");
bilanz.laufradIstZeichnung = !!pumpe && pumpe.children[0].tagName === "SVG";

// Eine zweite Anlage wird über die Kennung gewählt, nicht über die Lage.
karte.setConfig({ anlage: anlagen[1].id, farbsatz: "dunkel" });
const zweites = karte.shadowRoot.querySelector("img");
bilanz.zweiteAnlageAnders = !!zweites && String(zweites.src) !== String(bild.src);

// Abgeschaltete Bewegung: die Zustände bleiben, nur die Animation geht.
karte.setConfig({ animation: false });
const ruhig = karte.shadowRoot.querySelector(".schaubild");
bilanz.ohneAnimationRuhig = !!ruhig && String(ruhig.className).includes("ruhig");
karte.setConfig({ animation: true });
const bewegt = karte.shadowRoot.querySelector(".schaubild");
bilanz.mitAnimationBewegt = !!bewegt && !String(bewegt.className).includes("ruhig");

// Unbekannter Farbsatz: Home Assistant erwartet einen Fehler, damit der
// Editor auf YAML zurückfällt.
try {
  karte.setConfig({ farbsatz: "gibtsnicht" });
  bilanz.unbekannterSatzWirft = false;
} catch {
  bilanz.unbekannterSatzWirft = true;
}
try {
  karte.setConfig({ schrift: "gibtsnicht" });
  bilanz.unbekanntesMassWirft = false;
} catch {
  bilanz.unbekanntesMassWirft = true;
}

// Das Schriftmaß der Marken: eine Einstellung der Karte, kein fester Wert.
karte.setConfig({ schrift: "gross" });
const grosseSchrift = karte.shadowRoot.querySelector(".schaubild");
bilanz.schriftmass = grosseSchrift ? grosseSchrift.style["--hn-schrift"] : null;
karte.setConfig({ schrift: "normal" });

// Ohne Anlage bleibt ein Hinweis stehen, keine leere Fläche.
const leer = new Klasse();
leer.setConfig({});
leer.hass = { states: {}, callWS: async () => [] };
await leer._laden;
bilanz.hinweisOhneAnlage = (leer.shadowRoot.textContent || "").includes("Noch keine Anlage");

// Der Speicher: Beim Entnehmen kehrt sich die Strömung in den Stichleitungen
// um, beim Laden nicht.
const strom = new Klasse();
strom.setConfig({});
const zustaende = {
  "switch.pufferladepumpe": { state: "off", attributes: {} },
  "switch.heizkreispumpe": { state: "on", attributes: {} },
  "sensor.kessel": { state: "80", attributes: {} },
  "sensor.tpe": { state: "50", attributes: {} },
};
strom.hass = { states: zustaende, themes: { darkMode: true }, callWS: async () => anlagen };
await strom._laden;
const senkrechte = (teil) =>
  Array.from(strom.shadowRoot.querySelectorAll(".fluss")).filter(
    (b) =>
      String(b.className).includes("senkrecht") && (!teil || b.dataset.teil === teil)
  );
const rueckwaerts = (teil) =>
  senkrechte(teil).map((b) => String(b.className).includes("rueckwaerts"));
bilanz.senkrechteVorhanden = senkrechte().length;
bilanz.beimEntnehmenRueckwaerts = rueckwaerts("B-PLMi PUFFER").some(Boolean);
// Jetzt lädt der Kessel den Puffer: keine Umkehr mehr.
zustaende["switch.pufferladepumpe"].state = "on";
zustaende["switch.heizkreispumpe"].state = "off";
strom.hass = { states: zustaende, themes: { darkMode: true }, callWS: async () => anlagen };
bilanz.beimLadenVorwaerts = rueckwaerts("B-PLMi PUFFER").every((r) => !r);
// Der Wärmeerzeuger strömt immer nach oben – ob der Puffer lädt oder nicht.
bilanz.kesselImmerAufwaerts =
  rueckwaerts("PuroWIN").length > 0 && rueckwaerts("PuroWIN").every(Boolean);
bilanz.verbraucherAbwaerts = rueckwaerts("UML Heizkreis").every((r) => !r);



// Die Überlagerungen liegen über dem Bild und müssen den Farbsatz mitmachen.
const bunt = new Klasse();
bunt.setConfig({ farbsatz: "terrakotta" });
bunt.hass = { states: { "sensor.mischer": { state: "50", attributes: {} } },
  themes: { darkMode: true }, callWS: async () => anlagen };
await bunt._laden;
const grundfarben = anlagen[0].schema_grundfarben || {};
const stutzen = bunt.shadowRoot.querySelector(".mischer-stutzen");
bilanz.stutzenVorhanden = !!stutzen;
// Der Stutzen mischt Vor- und Rücklauf. Beide sind in jedem Satz derselbe
// Wert – hier muss also genau der dunkle Wert stehen.
const stutzenfarbe = String((stutzen && stutzen.style.background) || "");
bilanz.stutzenMitLeitungsfarben =
  stutzenfarbe.includes(grundfarben.vorlauf) && stutzenfarbe.includes(grundfarben.ruecklauf);
// Die Schichtung mischt warm und kalt – die folgen dem Satz.
const schichtung = bunt.shadowRoot.querySelector(".schichtung");
const schichtfarbe = String((schichtung && schichtung.style.background) || "");
bilanz.schichtungOhneDunkelwert =
  !!schichtung &&
  !schichtfarbe.includes(grundfarben.warm) &&
  !schichtfarbe.includes(grundfarben.kalt);
bilanz.grundfarbenMitgeliefert = Object.keys(grundfarben).length;

// Die Werteliste: Aufbau der Zeile, eigene Angaben je Wert, fremde Entität.
const liste = new Klasse();
liste.setConfig({
  anlage: anlagen[0].id,
  titel_bild: "",
  titel_liste: "Meine Werte",
  pumpen: false,
  zusatzwerte: [
    "sensor.kessel",
    { entity: "sensor.leistung", name: "Leistung oben", symbol: "mdi:gauge", teil: "aus" },
    { entity: "sensor.fremd", beschriftung: "Heizhaus" },
  ],
});
liste.hass = {
  states: {
    "sensor.kessel": { state: "68", attributes: { unit_of_measurement: "°C" } },
    "sensor.leistung": { state: "40", attributes: { unit_of_measurement: "%" } },
    "sensor.fremd": {
      state: "7",
      attributes: { friendly_name: "Solarertrag", icon: "mdi:solar-power" },
    },
  },
  themes: { darkMode: true },
  callWS: async () => anlagen,
};
await liste._laden;
const zeilen = liste.shadowRoot.querySelectorAll(".zeile");
const inhalt = (zeile, wahl) => {
  const knoten = zeile.querySelector(wahl);
  return knoten ? knoten.textContent : null;
};
bilanz.zeilenAnzahl = zeilen.length;
bilanz.nameLinks = inhalt(zeilen[0], ".titel");
bilanz.teilAmWert = inhalt(zeilen[0], ".bezeichnung");
bilanz.zeileMitSymbol = !!zeilen[0].querySelector("ha-icon");
bilanz.eigenerName = inhalt(zeilen[1], ".titel");
bilanz.teilAbgewaehlt = inhalt(zeilen[1], ".bezeichnung") === "";
bilanz.fremdeEntitaet = inhalt(zeilen[2], ".titel");
bilanz.eigeneBeschriftung = inhalt(zeilen[2], ".bezeichnung");
bilanz.ueberschriften = liste.shadowRoot.querySelectorAll("h2").map((h) => h.textContent);
bilanz.ohnePumpenmarke = !liste.shadowRoot.querySelector(".pumpe");

// Der alte Aufbau bleibt erreichbar: Anlagenteil links, Datenpunkt am Wert.
liste.setConfig({
  anlage: anlagen[0].id,
  zeilen: { aufbau: "wert_rechts" },
  zusatzwerte: ["sensor.kessel"],
});
const altezeile = liste.shadowRoot.querySelector(".zeile");
bilanz.altTeilLinks = inhalt(altezeile, ".titel");
bilanz.altNameAmWert = inhalt(altezeile, ".bezeichnung");

// Einheit, Symbolfarbe und Klick je Zeile.
liste.setConfig({
  anlage: anlagen[0].id,
  zusatzwerte: [
    { entity: "sensor.kessel", einheit: false, klick: false, farbe: "red" },
  ],
});
const knapp = liste.shadowRoot.querySelector(".zeile");
bilanz.ohneEinheit = knapp.querySelector(".wert").textContent;
bilanz.ohneKlick = !String(knapp.className).includes("klickbar");
bilanz.symbolfarbe = knapp.querySelector("ha-icon").style.color;

// Umsortieren im Editor: der Eintrag wandert, die Angaben bleiben.
editor.setConfig({
  anlage: anlagen[0].id,
  zusatzwerte: ["sensor.kessel", { entity: "sensor.leistung", name: "Leistung" }],
});
editor._verschieben(1, 0);
bilanz.umsortiert = editor._config.zusatzwerte.map((e) => (typeof e === "string" ? e : e.entity));
bilanz.umsortiertName = editor._config.zusatzwerte[0].name;

// Eigene Zeichnung je Anlagenteil und der Mischer als Schalter.
const gezeichnet = new Klasse();
gezeichnet.setConfig({ anlage: anlagen[0].id, mischer: false });
let gefragt = null;
gezeichnet.hass = {
  states: {},
  themes: { darkMode: true },
  callWS: async (anfrage) => {
    gefragt = anfrage;
    return anlagen;
  },
};
await gezeichnet._laden;
bilanz.ohneMischermarke = !gezeichnet.shadowRoot.querySelector(".mischer");
gezeichnet.setConfig({ anlage: anlagen[0].id, zeichnungen: { "PuroWIN": "kessel-pellets" } });
await gezeichnet._laden;
bilanz.zeichnungGefragt = gefragt && gefragt.zeichnungen ? gefragt.zeichnungen.PuroWIN : null;

// Der Editor kennt die gezeichneten Teile und die vorhandenen Zeichnungen.
editor.setConfig({ anlage: anlagen[0].id });
const bildAb2 = editor._schema().find((f) => f.name === "bild_ab");
const zeichnungen = bildAb2.schema.find((f) => f.name === "zeichnungen");
bilanz.zeichenbareTeile = zeichnungen.schema.map((f) => editor._beschriftung(f));
bilanz.zeichnungenZurWahl = zeichnungen.schema[0].selector.select.options.length;

console.log(JSON.stringify(bilanz));
