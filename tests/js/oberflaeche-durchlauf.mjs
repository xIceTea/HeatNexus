/**
 * Die Oberfläche einmal komplett aufbauen – in Node, ohne Browser.
 *
 * Aufruf: `node oberflaeche-durchlauf.mjs <panel.js> <daten.json>`
 *
 * Die Aufteilung kommt aus der **echten** Serverseite (`panel/daten.py`), der
 * Test schreibt sie vorher als JSON heraus. Damit prüft dieser Durchlauf
 * beides zugleich: dass der Browser mit dem umgeht, was der Server liefert.
 *
 * Ausgegeben wird eine Bilanz je Reiter. Ein Fehler beim Aufbau bricht den
 * Lauf ab – genau darum geht es.
 */

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel, pfadDaten] = process.argv.slice(2);
const zeit = browserAttrappe();

/** Kartentitel ohne die Marke „aktiv", die in derselben Überschrift steht. */
function titelOhneMarke(ueberschrift) {
  const marke = ueberschrift.querySelector(".zp-aktiv");
  const text = String(ueberschrift.textContent || "");
  return (marke ? text.replace(String(marke.textContent || ""), "") : text).trim();
}
const daten = JSON.parse(readFileSync(pfadDaten, "utf-8"));

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

// ---------------------------------------------------------------------------
// Zustände: zu jeder Entität, die in der Aufteilung vorkommt, einen Wert
// ---------------------------------------------------------------------------
const entitaeten = new Set();
const sammeln = (wert) => {
  if (Array.isArray(wert)) return wert.forEach(sammeln);
  if (!wert || typeof wert !== "object") return;
  Object.entries(wert).forEach(([schluessel, inhalt]) => {
    if (typeof inhalt === "string" && /^[a-z_]+\.[a-z0-9_]+$/.test(inhalt)) entitaeten.add(inhalt);
    else sammeln(inhalt);
    if (schluessel === "entity" && typeof inhalt === "string") entitaeten.add(inhalt);
  });
};
sammeln(daten);

const zeitprogramme = new Set(
  (daten.anlagen || []).flatMap((anlage) => (anlage.zeitprogramme || []).map((p) => p.entity))
);

// Werte, die nur über null etwas bedeuten – die Wärmeanforderung des
// Pumpen-/Relaismoduls. Sie stehen im Durchlauf auf null, damit sich prüfen
// lässt, dass dort dann ein Strich steht.
const ohneAnforderung = new Set(
  (daten.anlagen || []).flatMap((anlage) =>
    (anlage.kennwerte || []).filter((k) => k.ersatz_unter_null).map((k) => k.entity)
  )
);

const states = {};
entitaeten.forEach((entity) => {
  const bereich = entity.split(".")[0];
  states[entity] = {
    entity_id: entity,
    state: bereich === "binary_sensor" || bereich === "switch" ? "on" : "21.5",
    attributes: {
      friendly_name: entity,
      unit_of_measurement: "°C",
      options: ["Standby", "Programm 1", "Heizbetrieb"],
      temperature: 21.5,
      current_temperature: 20.8,
      target_temp_step: 0.5,
      preset_mode: "1",
      preset_modes: ["0", "1", "2"],
      hvac_action: "heating",
      override_aktiv: false,
      override_restzeit_min: 0,
      stoerung_aktiv: false,
      meldungen: [{ code: 346, kind: "Fehler", text: "Verkleidungstür offen", info: "schließen" }],
    },
  };
  if (ohneAnforderung.has(entity)) states[entity].state = "0";
  if (zeitprogramme.has(entity)) {
    states[entity].state = "täglich: 06:00→21°";
    states[entity].attributes.blocks = [
      {
        weekdays: ["Mo", "Tu", "We", "Th", "Fr"],
        switchPoints: [
          { time: "06:00", value: 21 },
          { time: "22:00", value: 16 },
        ],
      },
      { weekdays: ["Sa", "Su"], switchPoints: [{ time: "07:30", value: 21 }] },
    ];
  }
});

const gerufeneDienste = [];
const dienstAufrufe = [];
const hass = {
  states,
  callWS: async () => {
    throw new Error("kein Server im Test");
  },
  callService: async (bereich, dienst, angaben) => {
    gerufeneDienste.push(`${bereich}.${dienst}`);
    dienstAufrufe.push({ dienst: `${bereich}.${dienst}`, angaben });
    return true;
  },
  formatEntityState: (zustand) => `${zustand.state} °C`,
};

// ---------------------------------------------------------------------------
// Aufbau je Reiter
// ---------------------------------------------------------------------------
const flaeche = new klasse();
flaeche.hass = hass;
flaeche.panel = { config: { daten } };

// Die Betriebswahl steht auf einem der Programme – genau dessen Karte soll
// sich im Reiter Zeitprogramme abheben.
if (states["select.betriebswahl"]) states["select.betriebswahl"].state = "Programm 1";

// Eine anstehende Störung, damit die Störungskarte ihre Zeilen zeigt.
if (states["sensor.meldung_klartext"]) states["sensor.meldung_klartext"].attributes.stoerung_aktiv = true;

const bilanz = {};
const REITER = ["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme"];
REITER.forEach((reiter) => {
  flaeche._reiter = reiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  const zeilen = flaeche.shadowRoot.querySelectorAll(".zeile");
  bilanz[reiter] = {
    karten: flaeche.shadowRoot.querySelectorAll(".karte").length,
    titel: [...flaeche.shadowRoot.querySelectorAll(".kartenkopf")].map((kopf) =>
      String(kopf.textContent || "").trim()
    ),
    bindungen: flaeche._bindungen.length,
    // Die hervorgehobene Karte: das Programm, auf dem die Betriebswahl steht.
    // Einfache Wähler, keine zusammengesetzten – mehr kann die DOM-Attrappe nicht.
    aktiveKarten: [...flaeche.shadowRoot.querySelectorAll(".karte")]
      .filter((karte) => karte.classList.contains("aktiv"))
      .map((karte) => {
        // Die Überschrift, nicht den ganzen Kopf: daneben steht das Fragezeichen.
        const ueberschrift = karte.querySelector("h2");
        return ueberschrift ? titelOhneMarke(ueberschrift) : "";
      }),
    // Die Textmarke „aktiv": Farbe allein trägt keine Aussage.
    aktivMarken: [...flaeche.shadowRoot.querySelectorAll(".zp-aktiv")]
      .filter((marke) => !marke.hidden)
      .map((marke) => String(marke.textContent || "").trim()),
    zeilen: zeilen.length,
    versteckteZeilen: zeilen.filter((zeile) => zeile.hidden).length,
    // Statt zu verschwinden steht in der Zeile jetzt ein Strich.
    ohneAnforderung: [...flaeche.shadowRoot.querySelectorAll(".wert")].filter(
      (knoten) => String(knoten.textContent || "").trim() === "–"
    ).length,
    // Die Schaltzeiten unter dem Wochenraster: Uhrzeit, Strich, Wert.
    schaltzeiten: [...flaeche.shadowRoot.querySelectorAll(".schaltzeit")].map((knoten) =>
      String(knoten.textContent || "").trim()
    ),
    // Eigene Pfeile am Zahlenfeld – die des Browsers sind abgeschaltet.
    zahlPfeile: flaeche.shadowRoot.querySelectorAll(".zahl-pfeil").length,
    // Unter der aktiven Störung steht die Handlungsempfehlung.
    abhilfe: [...flaeche.shadowRoot.querySelectorAll(".abhilfe")]
      .filter((knoten) => knoten.style.display !== "none")
      .map((knoten) => String(knoten.textContent || "").trim()),
    zahlFelder: [...flaeche.shadowRoot.querySelectorAll(".status-zeile")]
      .filter((zeile) => zeile.querySelector(".zahl-feld"))
      .map((zeile) => String(zeile.querySelector(".titel").textContent || "").trim()),
  };
});

// ---------------------------------------------------------------------------
// Werkzeugmenü der Kopfzeile
//
// Anordnen und Dashboard-Vorlage stehen dort gemeinsam. Die Vorlage nur für
// Verwalter: Wer keine Dashboards anlegen darf, kann damit nichts anfangen.
// ---------------------------------------------------------------------------
hass.user = { is_admin: true };
hass.callWS = async (anfrage) =>
  anfrage.type === "heatnexus/dashboard_yaml"
    ? { yaml: "title: Heizung\nviews: []\n" }
    : {};
flaeche._reiter = "uebersicht";
flaeche._gebaut = false;
flaeche._zeichnen();

const werkzeugliste = flaeche.shadowRoot.querySelector(".werkzeugliste");
bilanz.werkzeugmenueDa = !!werkzeugliste;
bilanz.werkzeugeZu = !!werkzeugliste && werkzeugliste.hidden === true;
bilanz.werkzeuge = werkzeugliste
  ? werkzeugliste.children.map((punkt) => String(punkt.textContent || "").trim())
  : [];
const werkzeugTaste = flaeche.shadowRoot
  .querySelector(".werkzeuge")
  .querySelector("button");
werkzeugTaste.ausloesen("click");
bilanz.werkzeugeOffen = werkzeugliste.hidden === false;

const vorlagePunkt = werkzeugliste.children.find(
  (punkt) => String(punkt.textContent || "").trim() === "Dashboard-Vorlage"
);
bilanz.vorlageFuerVerwalter = !!vorlagePunkt;
if (vorlagePunkt) {
  vorlagePunkt.ausloesen("click");
  for (let runde = 0; runde < 5; runde++) await Promise.resolve();
}
bilanz.werkzeugeNachKlickZu = werkzeugliste.hidden === true;
const yamlFeld = flaeche.shadowRoot.querySelector(".yaml-feld");
bilanz.yamlImFenster = !!yamlFeld && String(yamlFeld.value || "").includes("views");

// Ohne Verwalterrecht fehlt der Eintrag, das Anordnen bleibt.
hass.user = { is_admin: false };
flaeche._gebaut = false;
flaeche._zeichnen();
bilanz.werkzeugeOhneRecht = flaeche.shadowRoot
  .querySelector(".werkzeugliste")
  .children.map((punkt) => String(punkt.textContent || "").trim());
hass.user = { is_admin: true };

// ---------------------------------------------------------------------------
// Farbsatz des Schaubilds
//
// Die Zeichnung liegt als Daten-URL in einem `<img>` und erbt darin kein CSS.
// Beide Fassungen kommen deshalb mit; gewählt wird hier, bei jedem Abgleich.
// ---------------------------------------------------------------------------
flaeche._reiter = "uebersicht";
flaeche._gebaut = false;
flaeche._zeichnen();
flaeche._aktualisieren();
// Zwei Schritte, weil die Attrappe nur einfache Wähler kennt.
const huelle = flaeche.shadowRoot.querySelector(".schaubild");
const schaubild = huelle ? huelle.querySelector("img") : null;
const beiDunkel = schaubild ? schaubild.src : null;
hass.themes = { darkMode: false };
flaeche._aktualisieren();
const beiHell = schaubild ? schaubild.src : null;
// Eine eigene Wahl schlägt das Erscheinungsbild: dunkles Bild trotz hellem HA.
flaeche._anordnung = { ...flaeche._anordnung, einstellungen: { farbsatz: "terrakotta" } };
flaeche._aktualisieren();
const beiTerrakotta = schaubild ? schaubild.src : null;
flaeche._anordnung = { ...flaeche._anordnung, einstellungen: { farbsatz: "dunkel" } };
flaeche._aktualisieren();
const beiWahlDunkel = schaubild ? schaubild.src : null;
flaeche._anordnung = { ...flaeche._anordnung, einstellungen: {} };
flaeche._aktualisieren();
bilanz.schaubild = {
  dunkel: beiDunkel,
  hell: beiHell,
  terrakotta: beiTerrakotta,
  wahlDunkel: beiWahlDunkel,
};

// Der Farbsatz färbt auch die Oberfläche, nicht nur das Bild: gesetzt werden
// die Variablen am Wirtselement.
flaeche._anordnung = { ...flaeche._anordnung, einstellungen: { farbsatz: "terrakotta" } };
flaeche._gebaut = false;
flaeche._zeichnen();
const beiWahl = flaeche.style.getPropertyValue("--hn-akzent");
flaeche._anordnung = { ...flaeche._anordnung, einstellungen: {} };
flaeche._gebaut = false;
flaeche._zeichnen();
bilanz.palette = { terrakotta: beiWahl, auto: flaeche.style.getPropertyValue("--hn-akzent") };

// Eine gewählte Farbe wird im Browser gemerkt: Die nächste Oberfläche steht
// damit vom ersten Aufbau an richtig, ohne auf die Einstellungen zu warten.
flaeche._farbsatzSetzen("petrol");
const zweite = new (customElements.get("heatnexus-panel"))();
bilanz.gemerkt = { gesetzt: flaeche._farbsatzGemerkt(), beimAufbau: zweite._farbsatz() };

// Nach einem Verbindungsabriss stellt Home Assistant die Panel-Anmeldung
// erneut zu. Der Abzug darin ist älter als das, was schon geholt wurde.
const frisch = new (customElements.get("heatnexus-panel"))();
const frischeDaten = { anlagen: [{ ...daten.anlagen[0], name: "frisch" }] };
frisch.hass = {
  ...hass,
  callWS: async (anfrage) =>
    anfrage.type === "heatnexus/panel_daten" ? frischeDaten : {},
};
await Promise.resolve();
await Promise.resolve();
frisch.panel = { config: { daten: { anlagen: [{ ...daten.anlagen[0], name: "veraltet" }] } } };
bilanz.wiederverbunden = { name: frisch._daten && frisch._daten.anlagen[0].name };

// Anordnen-Modus: eigener Zweig mit Griffen, Menü und Speicherauftrag.
flaeche._reiter = "uebersicht";
flaeche._anordnen = true;
flaeche._gebaut = false;
flaeche._zeichnen();
bilanz.anordnen = { griffe: flaeche.shadowRoot.querySelectorAll(".anordner-griff").length };
flaeche._anordnen = false;

// ---------------------------------------------------------------------------
// Bedienen: der Weg von der Taste bis zum Aufräumen der Rückmeldung
// ---------------------------------------------------------------------------
const anzeige = document.createElement("div");
anzeige.className = "rueckmeldung";
let bestaetigt = false;
await flaeche._uebertragen(
  anzeige,
  () => hass.callService("climate", "set_temperature", {}),
  () => bestaetigt,
  "climate.pruefung"
);
const beiUebertragung = anzeige.textContent;
bestaetigt = true;
flaeche._pruefeWartende();
const nachBestaetigung = anzeige.textContent;
// Erst hier räumt die Anzeige sich auf – und genau dabei ist beim Schnitt in
// ES-Module eine nicht ausgeführte Konstante aufgefallen.
zeit.zeitLaufenLassen();

bilanz.bedienen = {
  dienste: gerufeneDienste,
  waehrend: beiUebertragung,
  bestaetigt: nachBestaetigung,
  aufgeraeumt: anzeige.textContent,
};

// ---------------------------------------------------------------------------
// Betriebswahl: verwandte Werte ziehen nicht von allein nach
//
// Die Anlage setzt mit der Betriebswahl auch den Sollwert neu. Ohne
// Nachfassen stünde er bis zum nächsten Abruf auf dem alten Stand.
// ---------------------------------------------------------------------------
states["climate.heizkreis"] = {
  entity_id: "climate.heizkreis",
  state: "heat",
  attributes: { friendly_name: "Heizkreis", temperature: 20 },
};
states["select.betriebswahl"] = {
  entity_id: "select.betriebswahl",
  state: "Programm 3",
  attributes: { friendly_name: "Betriebswahl", options: ["Programm 2", "Programm 3"] },
};

const vorAuswahl = dienstAufrufe.length;
const auswahlFeld = flaeche._auswahlFeld("Betriebswahl", "select.betriebswahl", null, {
  entity: "climate.heizkreis",
  betriebswahl: "select.betriebswahl",
});
const auswahlKnoten = auswahlFeld.querySelector("select");
auswahlKnoten.value = "Programm 2";
auswahlKnoten.ausloesen("change");
for (let runde = 0; runde < 5; runde++) await Promise.resolve();
const geplanteRunden = zeit.offeneAuftraege();
// Die Anlage zieht nach – ab hier ist nichts mehr nachzufassen.
states["climate.heizkreis"].attributes.temperature = 23;
zeit.zeitLaufenLassen();

bilanz.betriebswahl = {
  aufrufe: dienstAufrufe.slice(vorAuswahl).map((eintrag) => ({
    dienst: eintrag.dienst,
    entitaeten: [].concat((eintrag.angaben || {}).entity_id || []),
  })),
  geplant: geplanteRunden,
};

// Die Anzeige der Auswahl selbst kommt erst nach dem Aufruf an, der Sollwert
// steht noch. Das Nachfassen läuft weiter, bis der Sollwert nachzieht.
zeit.zeitLaufenLassen();
states["select.betriebswahl"].state = "Programm 3";
const vorSpaeterAnzeige = dienstAufrufe.length;
const spaetesFeld = flaeche._auswahlFeld("Betriebswahl", "select.betriebswahl", null, {
  entity: "climate.heizkreis",
});
const spaeterKnoten = spaetesFeld.querySelector("select");
spaeterKnoten.value = "Programm 2";
spaeterKnoten.ausloesen("change");
for (let runde = 0; runde < 5; runde++) await Promise.resolve();
states["select.betriebswahl"].state = "Programm 2";
zeit.zeitLaufenLassen();
bilanz.betriebswahl.spaeteAnzeige = dienstAufrufe
  .slice(vorSpaeterAnzeige)
  .filter((eintrag) => eintrag.dienst === "homeassistant.update_entity").length;

// Die Steuerung rechnet den Sollwert erst Sekunden nach der Betriebswahl neu.
// Bis dahin steht „lädt …" statt des alten Werts.
states["climate.heizkreis"].attributes.temperature = 20;
flaeche._sollwertAbwarten("climate.heizkreis");
bilanz.betriebswahl.sollwert = {
  wartet: flaeche._sollwertText("climate.heizkreis", 20),
  nachgezogen: flaeche._sollwertText("climate.heizkreis", 21.5),
  danach: flaeche._sollwertText("climate.heizkreis", 20),
};
zeit.zeitLaufenLassen();

// Lehnt die Anlage die Auswahl ab, bleibt nichts zu erwarten.
const echterAufruf = hass.callService;
hass.callService = async () => {
  throw new Error("abgelehnt");
};
const abgelehntesFeld = flaeche._auswahlFeld("Betriebswahl", "select.betriebswahl", null, {
  entity: "climate.heizkreis",
});
const abgelehnterKnoten = abgelehntesFeld.querySelector("select");
abgelehnterKnoten.value = "Programm 3";
abgelehnterKnoten.ausloesen("change");
for (let runde = 0; runde < 5; runde++) await Promise.resolve();
bilanz.betriebswahl.sollwert.abgelehnt = flaeche._sollwertText("climate.heizkreis", 20);
hass.callService = echterAufruf;
zeit.zeitLaufenLassen();

// ---------------------------------------------------------------------------
// Zeitprogramm-Dialog: erst lesen, dann bearbeiten
//
// Im Bediengerät stehen die Zeiten als „von – bis"; eingestellt wird dagegen
// der Startpunkt, weil ein Punkt gilt, bis der nächste kommt. Beides in einer
// Ansicht zu mischen hiess, beim Verstellen die falsche Zeit zu erwischen.
// ---------------------------------------------------------------------------
const einProgramm = (daten.anlagen || []).flatMap((anlage) => anlage.zeitprogramme || [])[0];

let zeitprogrammDialog = null;
if (einProgramm) {
  const meldung = document.createElement("div");
  flaeche._zeitprogrammBearbeiten(einProgramm, meldung);
  const dialog = flaeche.shadowRoot.querySelector(".zp-dialog");
  const tasten = () =>
    [...dialog.querySelectorAll(".dialog-taste")].map((t) => String(t.textContent || "").trim());

  const beimLesen = {
    spannen: [...dialog.querySelectorAll(".zp-spanne")].map((knoten) =>
      String(knoten.textContent || "").trim()
    ),
    editoren: dialog.querySelectorAll(".zp-editor").length,
    tasten: tasten(),
  };

  // Der zweite Knopf holt den Editor.
  dialog._bearbeiten();

  const beimBearbeiten = {
    spannen: dialog.querySelectorAll(".zp-spanne").length,
    editoren: dialog.querySelectorAll(".zp-editor").length,
    startpunkte: [...dialog.querySelectorAll(".zp-punktekopf")].map((knoten) =>
      String(knoten.textContent || "").trim()
    ),
    tasten: tasten(),
  };

  zeitprogrammDialog = { lesen: beimLesen, bearbeiten: beimBearbeiten };
}
bilanz.zeitprogrammDialog = zeitprogrammDialog;

// ---------------------------------------------------------------------------
// Zeitprogramm aktivieren: Rückfrage, dann die Betriebswahl umstellen
// ---------------------------------------------------------------------------
states["select.betriebswahl"] = {
  entity_id: "select.betriebswahl",
  state: "Programm 1",
  attributes: {
    friendly_name: "Betriebswahl",
    options: ["Standby", "Programm 1", "Programm 2", "Programm 3"],
  },
};
flaeche._reiter = "zeitprogramme";
flaeche._gebaut = false;
flaeche._zeichnen();
flaeche._aktualisieren();
const sichtbareAktivieren = () =>
  flaeche.shadowRoot.querySelectorAll(".zp-aktivieren").filter((taste) => !taste.hidden);
// Nur die Rückfrage: Ein früher geöffneter Programmdialog kann noch im Baum stehen.
const rueckfrageDialog = () =>
  flaeche.shadowRoot
    .querySelectorAll(".dialog")
    .find((dialog) => dialog.getAttribute("role") === "alertdialog");
const dialogTaste = (betont) =>
  rueckfrageDialog()
    .querySelectorAll(".dialog-taste")
    .find((taste) => taste.classList.contains("betont") === betont);
const vorAktivieren = sichtbareAktivieren().length;

const vorNein = dienstAufrufe.length;
sichtbareAktivieren()[0].ausloesen("click");
await Promise.resolve();
const rueckfrage = rueckfrageDialog() && rueckfrageDialog().querySelector(".dialog-text");
const frageText = rueckfrage ? String(rueckfrage.textContent) : null;
dialogTaste(false).ausloesen("click");
for (let runde = 0; runde < 5; runde++) await Promise.resolve();
const nachNein = dienstAufrufe.length - vorNein;

const vorJa = dienstAufrufe.length;
sichtbareAktivieren()[0].ausloesen("click");
await Promise.resolve();
dialogTaste(true).ausloesen("click");
for (let runde = 0; runde < 5; runde++) await Promise.resolve();
const gesetzt = dienstAufrufe
  .slice(vorJa)
  .find((aufruf) => aufruf.dienst === "select.select_option");

states["select.betriebswahl"].state = "Programm 2";
flaeche._aktualisieren();
bilanz.aktivieren = {
  vorher: vorAktivieren,
  frage: frageText,
  nachNein,
  gesetzt: gesetzt ? gesetzt.angaben.option : null,
  nachher: sichtbareAktivieren().length,
};
zeit.zeitLaufenLassen();

// ---------------------------------------------------------------------------
// Misslungenes Speichern
//
// Die Attrappe wirft bei jedem `callWS`. Wer die Farbwahl anfasst, muss das
// erfahren – sonst springt die Ansicht beim nächsten Laden zurück.
// ---------------------------------------------------------------------------
const meldungen = [];
flaeche.addEventListener("hass-notification", (ereignis) => {
  meldungen.push(ereignis.detail && ereignis.detail.message);
});
hass.callWS = async () => {
  throw new Error("kein Server im Test");
};
flaeche._farbsatzSetzen("kontrast");
await Promise.resolve();
await Promise.resolve();
bilanz.meldungBeimSpeichern = meldungen;

console.log(JSON.stringify(bilanz));
