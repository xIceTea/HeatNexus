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

console.log(JSON.stringify(bilanz));
