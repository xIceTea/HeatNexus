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

/** Text eines Knotens, ohne Rand. */
const text = (knoten) => String((knoten && knoten.textContent) || "").trim();

/** Namen der Zeitprogramme, groß wie klein, in der Reihenfolge auf der Seite. */
const programmNamen = (wurzel) => [
  ...wurzel.querySelectorAll(".zp-programmname"),
  ...wurzel.querySelectorAll(".zp-mininame"),
].map(text);

/** Der Name des Programms, an dem eine Taste steht. */
const programmVon = (taste) => {
  const gross = taste.closest(".zp-programm");
  if (gross) return text(gross.querySelector(".zp-programmname"));
  return text(taste.closest(".zp-mini").querySelector(".zp-mininame"));
};

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

// Der Störspeicher: ein erledigter Eintrag und darunter ein älterer, der noch anliegt.
const STOERSPEICHER = [
  { id: 156, code: 346, symbol: "E", art: "Fehler", text: "Verkleidungstür offen", geraet: "PuroWIN",
    aktiv: false, status: "receipted", zuerst: "2026-10-14T21:41:00+02:00", zuruecksetzbar: false, quittierbar: false, loeschbar: true },
  { id: 155, code: 346, symbol: "E", art: "Fehler", text: "Verkleidungstür offen", geraet: "PuroWIN",
    aktiv: true, status: "new", zuerst: "2026-10-14T21:40:34+02:00", zuruecksetzbar: false, quittierbar: true, loeschbar: false },
];
const ANLIEGEND = STOERSPEICHER[1];

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
    // Zeitprogramme: das geltende groß, die übrigen klein, der Hinweis einmal im Fuß.
    aktiveProgramme: [...flaeche.shadowRoot.querySelectorAll(".zp-programm")]
      .filter((programm) => programm.classList.contains("aktiv"))
      .map((programm) => text(programm.querySelector(".zp-programmname"))),
    grosseProgramme: [...flaeche.shadowRoot.querySelectorAll(".zp-programmname")].map(text),
    kleineProgramme: [...flaeche.shadowRoot.querySelectorAll(".zp-mininame")].map(text),
    programmNamen: programmNamen(flaeche.shadowRoot),
    fuss: [...flaeche.shadowRoot.querySelectorAll(".zp-fuss")].map((fuss) => fuss.children.map(text)),
    schaltzeiten: flaeche.shadowRoot.querySelectorAll(".schaltzeit").length,
    segmentWerte: [...flaeche.shadowRoot.querySelectorAll(".zp-segmentwert")].map(text),
    heuteKarten: flaeche.shadowRoot.querySelectorAll(".zp-heute").length,
    legenden: flaeche.shadowRoot.querySelectorAll(".zp-legende").length,
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
const yamlHinweis = yamlFeld && yamlFeld.parentElement.querySelector(".dialog-text");
bilanz.yamlHinweis = yamlHinweis ? String(yamlHinweis.textContent || "") : "";

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

// Reiter lassen sich je Benutzer umordnen und ausblenden.
{
  const vorherAnordnung = flaeche._anordnung;
  const vorherWS = hass.callWS;
  const gesendet = [];
  hass.callWS = async (nachricht) => {
    gesendet.push(nachricht);
    return {};
  };
  const reiterfolge = () => flaeche.shadowRoot.querySelector(".reiter").children.map((t) => t.dataset.reiter);
  flaeche._anordnung = { ...flaeche._anordnung, einstellungen: { reiter_versteckt: ["hilfe"] } };
  flaeche._gebaut = false;
  flaeche._zeichnen();
  const ohneHilfe = reiterfolge();
  for (let i = 0; i < 5; i += 1) flaeche._reiterVerschieben("zeitprogramme", -1);
  const verschoben = reiterfolge();
  flaeche._reiterAusblenden("verlauf");
  bilanz.reiter = {
    ohneHilfe,
    verschoben,
    ausgeblendet: reiterfolge(),
    gesendet: gesendet.length ? gesendet[gesendet.length - 1].einstellungen : null,
  };
  hass.callWS = vorherWS;
  flaeche._anordnung = vorherAnordnung;
  flaeche._gebaut = false;
  flaeche._zeichnen();
}

// Eine gewählte Farbe wird im Browser gemerkt: Die nächste Oberfläche steht
// damit vom ersten Aufbau an richtig, ohne auf die Einstellungen zu warten.
flaeche._darstellungSetzen({ farbsatz: "petrol" });
const zweite = new (customElements.get("heatnexus-panel"))();
bilanz.gemerkt = { gesetzt: flaeche._gemerkt("heatnexus.farbsatz"), beimAufbau: zweite._farbsatz() };

// Die Kopfzeile folgt der Wahl in „Darstellung“ und wird ebenso gemerkt.
{
  const marke = () => flaeche.shadowRoot.querySelector(".markenblock");
  const stand = () => ({ klasse: marke().className, unterzeile: Boolean(marke().querySelector(".unterzeile")) });
  const vorher = stand();
  flaeche._darstellungSetzen({ kopf: "schlicht" });
  const schlicht = stand();
  flaeche._darstellungSetzen({ kopf: "farbig" });
  const farbig = stand();
  flaeche._darstellungSetzen({ kopf: "farbig_schlicht" });
  const kurz = stand();
  const dritte = new (customElements.get("heatnexus-panel"))();
  bilanz.kopf = { vorher, schlicht, farbig, kurz, beimAufbau: dritte._kopfstil() };
  flaeche._darstellungSetzen({ kopf: "standard" });
}

// Die Seitenleiste öffnet das Zeichen selbst; auf Wunsch steht eine Menütaste davor.
{
  const wurzel = flaeche.shadowRoot;
  const kopfTasten = () => wurzel.querySelector(".kopfleiste").querySelectorAll(".menue-taste").map((t) => t.className);
  const gesendet = [];
  const vorherDispatch = flaeche.dispatchEvent;
  flaeche.dispatchEvent = (ereignis) => gesendet.push(ereignis.type);
  wurzel.querySelector(".zeichen-taste").ausloesen("click");
  const zeichen = kopfTasten();
  flaeche._darstellungSetzen({ menue: "taste" });
  const mitTaste = kopfTasten();
  wurzel.querySelector(".seitenleiste-taste").ausloesen("click");
  flaeche.dispatchEvent = vorherDispatch;
  bilanz.menue = { zeichen, mitTaste, gesendet };
  flaeche._darstellungSetzen({ menue: "zeichen" });
}

// Das Fenster „Darstellung“ zeigt je Einstellung Vorschaukacheln; ein Klick wirkt sofort.
{
  const wurzel = flaeche.shadowRoot;
  const vorher = wurzel.querySelectorAll(".schleier").length;
  flaeche._darstellungOeffnen();
  const fenster = wurzel.querySelectorAll(".schleier")[vorher];
  const gruppen = fenster.querySelectorAll(".darstellung-wahl");
  const gedrueckt = () =>
    gruppen.map((g) => g.querySelectorAll(".darstellung-muster").filter((k) => k.getAttribute("aria-pressed") === "true").map((k) => k.dataset.wert));
  const anfangs = gedrueckt();
  gruppen[1].querySelectorAll(".darstellung-muster").find((k) => k.dataset.wert === "farbig").ausloesen("click");
  const nachKlick = gedrueckt();
  const kopfNachKlick = flaeche._kopfstil();
  const [schliessen, uebernehmen] = fenster.querySelector(".dialog-leiste").querySelectorAll(".dialog-taste");
  const leiste = () => ({ text: String(schliessen.textContent), rot: schliessen.classList.contains("betont"), uebernehmen: !uebernehmen.hidden });
  const leisteNachKlick = leiste();
  uebernehmen.ausloesen("click");
  const kopfNachUebernehmen = flaeche._kopfstil();
  // Ein zweites Fenster: geändert und verworfen bleibt die alte Wahl.
  flaeche._darstellungOeffnen();
  const zweites = wurzel.querySelectorAll(".schleier")[vorher];
  const zweiteGruppen = zweites.querySelectorAll(".darstellung-wahl");
  const leisteAnfangs = { text: String(zweites.querySelector(".dialog-leiste").querySelector(".dialog-taste").textContent) };
  zweiteGruppen[1].querySelectorAll(".darstellung-muster").find((k) => k.dataset.wert === "schlicht").ausloesen("click");
  zweites.querySelector(".dialog-leiste").querySelector(".dialog-taste").ausloesen("click");
  bilanz.darstellung = {
    kacheln: gruppen.map((g) => g.querySelectorAll(".darstellung-muster").length),
    anfangs,
    nachKlick,
    kopfNachKlick,
    leisteNachKlick,
    kopfNachUebernehmen,
    leisteAnfangs,
    kopfNachVerwerfen: flaeche._kopfstil(),
    zu: wurzel.querySelectorAll(".schleier").length === vorher,
  };
  flaeche._darstellungSetzen({ kopf: "standard" });
}

// „Schließen" im Menü neben „Fertig" schließt das Fenster.
{
  const fenster = () => flaeche.shadowRoot.querySelectorAll(".schleier");
  const vorher = fenster().length;
  flaeche._anordnenMenue();
  const offen = fenster().length - vorher;
  const neuestes = fenster()[fenster().length - 1];
  neuestes.querySelector(".dialog-leiste").querySelector(".dialog-taste").ausloesen("click");
  bilanz.anordnenMenue = { offen, danach: fenster().length - vorher };
}

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

// Ohne Raumfühler zeigt die Karte als große Zahl nur den Sollwert; auch er öffnet die Detailansicht.
const geoeffnet = [];
flaeche.addEventListener("hass-more-info", (ereignis) => geoeffnet.push(ereignis.detail.entityId));
const heizkreisKarte = flaeche._heizkreisKarte({ titel: "Heizkreis", entity: "climate.heizkreis" });
heizkreisKarte.querySelector(".sollwert").ausloesen("click");
bilanz.betriebswahl.sollwertOeffnet = geoeffnet;

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
  // Montag, 10:00 in der Zone von Home Assistant.
  flaeche._jetzt = () => new Date("2026-09-21T10:00:00Z");
  hass.config = { time_zone: "UTC" };
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
    jetzt: dialog
      .querySelectorAll(".zp-spanne")
      .filter((zeile) => zeile.classList.contains("jetzt"))
      .map((zeile) => String(zeile.querySelector(".zp-spannezeit").textContent)),
    jetztFolge: dialog
      .querySelectorAll(".zp-spanne")
      .filter((zeile) => zeile.classList.contains("jetzt"))
      .map((zeile) => zeile.children.map((kind) => kind.className).filter(Boolean)),
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

// Die Programme, an denen die Taste gerade sichtbar ist.
const mitAktivieren = () => sichtbareAktivieren().map(programmVon);

states["select.betriebswahl"].state = "Programm 2";
flaeche._aktualisieren();
const waehrendUmstellung = sichtbareAktivieren().length;
zeit.zeitLaufenLassen();
bilanz.aktivieren = {
  vorher: vorAktivieren,
  frage: frageText,
  nachNein,
  gesetzt: gesetzt ? gesetzt.angaben.option : null,
  waehrendUmstellung,
  danach: mitAktivieren(),
  // Das neu geltende Programm rückt nach oben, das alte in die Minibalken.
  grossDanach: [...flaeche.shadowRoot.querySelectorAll(".zp-programmname")].map(text),
};

// Eine nicht verfügbare Auswahl behält ihre Optionen, stellt aber nichts um.
states["select.betriebswahl"].state = "unavailable";
flaeche._aktualisieren();
bilanz.aktivieren.nichtVerfuegbar = mitAktivieren();
states["select.betriebswahl"].state = "Programm 2";
flaeche._aktualisieren();

// ---------------------------------------------------------------------------
// Bezeichnung: im Dialog ändern, ohne das Programm neu zu schreiben
// ---------------------------------------------------------------------------
const wsAufrufe = [];
hass.callWS = async (anfrage) => {
  wsAufrufe.push(anfrage);
  return anfrage.type === "heatnexus/panel_daten" ? daten : { gespeichert: true };
};
const programmZwei = (daten.anlagen || [])
  .flatMap((anlage) => anlage.zeitprogramme || [])
  .find((programm) => programm.titel === "Programm 2");
let bezeichnung = null;
if (programmZwei) {
  const vorBezeichnung = dienstAufrufe.length;
  const offeneDialoge = flaeche.shadowRoot.querySelectorAll(".zp-dialog").length;
  flaeche._zeitprogrammBearbeiten(programmZwei, document.createElement("div"));
  // Der zuletzt geöffnete; ein früherer Programmdialog kann noch im Baum stehen.
  const dialog = flaeche.shadowRoot.querySelectorAll(".zp-dialog").at(-1);
  const titel = String(dialog.querySelector(".dialog-titel").textContent);
  const imLesen = dialog.querySelectorAll(".zp-bezeichnung").length;
  dialog._bearbeiten();
  const feld = dialog.querySelector(".zp-bezeichnung");
  const vorbelegt = feld ? feld.value : null;
  if (feld) feld.value = "  Winter ";
  const uebernehmen = dialog
    .querySelectorAll(".dialog-taste")
    .find((taste) => taste.classList.contains("betont"));
  uebernehmen.ausloesen("click");
  // Bis die Antwort da ist, nimmt die Taste keinen zweiten Druck an.
  const gesperrt = uebernehmen.disabled === true;
  for (let runde = 0; runde < 5; runde++) await Promise.resolve();
  bezeichnung = {
    gesperrt,
    titel,
    imLesen,
    vorbelegt,
    gesendet: wsAufrufe.filter((anfrage) => anfrage.type === "heatnexus/bezeichnung"),
    neuGeholt: wsAufrufe.some((anfrage) => anfrage.type === "heatnexus/panel_daten"),
    programmGeschrieben: dienstAufrufe
      .slice(vorBezeichnung)
      .some((aufruf) => aufruf.dienst === "heatnexus.set_time_program"),
    dialogZu: flaeche.shadowRoot.querySelectorAll(".zp-dialog").length <= offeneDialoge,
  };
}
bilanz.bezeichnung = bezeichnung;

// Die Betriebswahl zeigt die Bezeichnung, der Wert bleibt der Optionstext.
states["select.betriebswahl"].state = "Programm 1";
const beschriftetesFeld = flaeche._auswahlFeld("Betriebswahl", "select.betriebswahl", null, null);
flaeche._aktualisieren();
bilanz.optionen = beschriftetesFeld
  .querySelector("select")
  .children.map((knoten) => ({ wert: knoten.value, text: String(knoten.textContent) }));

// ---------------------------------------------------------------------------
// Bezeichnung und Zeiten zugleich
//
// Die neue Bezeichnung baut die Oberfläche neu auf. Die Rückmeldung zum
// Schreiben der Zeiten muss an der Karte stehen, die danach zu sehen ist.
// ---------------------------------------------------------------------------
let gespeicherteBezeichnung = null;
hass.callWS = async (anfrage) => {
  if (anfrage.type === "heatnexus/bezeichnung") {
    gespeicherteBezeichnung = anfrage.bezeichnung;
    return { gespeichert: true };
  }
  if (anfrage.type !== "heatnexus/panel_daten") return {};
  const neu = JSON.parse(JSON.stringify(daten));
  neu.anlagen
    .flatMap((anlage) => anlage.zeitprogramme || [])
    .filter((programm) => programm.titel === "Programm 2")
    .forEach((programm) => {
      programm.bezeichnung = gespeicherteBezeichnung;
    });
  return neu;
};
flaeche._reiter = "zeitprogramme";
flaeche._gebaut = false;
flaeche._zeichnen();
// Programm 2 gilt nicht und steht als Minibalken; sein Name öffnet den Dialog.
const nameZwei = flaeche.shadowRoot
  .querySelectorAll(".zp-mininame")
  .find((name) => text(name).startsWith("Programm 2"));
let bezeichnungUndZeiten = null;
if (nameZwei) {
  const vorZugleich = dienstAufrufe.length;
  nameZwei.ausloesen("click");
  const dialog = flaeche.shadowRoot.querySelectorAll(".zp-dialog").at(-1);
  dialog._bearbeiten();
  dialog.querySelector(".zp-bezeichnung").value = "Sommer";
  const sollwert = dialog.querySelector(".zp-wert");
  sollwert.value = "22";
  sollwert.ausloesen("change");
  dialog
    .querySelectorAll(".dialog-taste")
    .find((taste) => taste.classList.contains("betont"))
    .ausloesen("click");
  for (let runde = 0; runde < 10; runde++) await Promise.resolve();
  const sichtbareRueckmeldungen = () =>
    flaeche.shadowRoot
      .querySelectorAll(".rueckmeldung")
      .map((knoten) => String(knoten.textContent || "").trim())
      .filter(Boolean);
  const waehrend = sichtbareRueckmeldungen();
  const geschrieben = dienstAufrufe
    .slice(vorZugleich)
    .find((aufruf) => aufruf.dienst === "heatnexus.set_time_program");
  // Die Anlage meldet die neuen Zeiten zurück, in der Schreibweise des Zustands.
  if (geschrieben) {
    states[geschrieben.angaben.entity_id].attributes.blocks = geschrieben.angaben.blocks.map(
      (block) => ({ weekdays: block.weekdays, switchPoints: block.switch_points })
    );
  }
  flaeche._aktualisieren();
  bezeichnungUndZeiten = {
    geschrieben: !!geschrieben,
    waehrend,
    bestaetigt: sichtbareRueckmeldungen(),
    titel: programmNamen(flaeche.shadowRoot),
  };
  zeit.zeitLaufenLassen();
}
bilanz.bezeichnungUndZeiten = bezeichnungUndZeiten;

// ---------------------------------------------------------------------------
// Reiterleiste am Telefon: Sie behält ihre Position; nur ein verdeckter Reiter rückt nach.
// ---------------------------------------------------------------------------
{
  const inhalt = flaeche.shadowRoot;
  const leiste = inhalt.querySelector(".reiter");
  const taste = leiste.querySelector('[aria-selected="true"]');
  Object.assign(leiste, { scrollWidth: 900, clientWidth: 375 });
  leiste.getBoundingClientRect = () => ({ left: 0, right: 375, width: 375 });
  taste.getBoundingClientRect = () => ({ left: 100, right: 220, width: 120 });
  flaeche._reiterZeigen(inhalt, 200);
  const sichtbar = leiste.scrollLeft;
  taste.getBoundingClientRect = () => ({ left: 600, right: 720, width: 120 });
  flaeche._reiterZeigen(inhalt, 0);
  const rechtsVerdeckt = leiste.scrollLeft;
  taste.getBoundingClientRect = () => ({ left: -50, right: 70, width: 120 });
  flaeche._reiterZeigen(inhalt, 300);
  const linksVerdeckt = leiste.scrollLeft;
  bilanz.reiterImBild = { gewaehlt: taste.dataset.reiter, sichtbar, rechtsVerdeckt, linksVerdeckt };
}

// ---------------------------------------------------------------------------
// Heute-Streifen, leeres Programm, „Alle“
// ---------------------------------------------------------------------------
{
  flaeche._jetzt = () => new Date("2026-09-21T10:00:00Z");
  hass.config = { time_zone: "UTC" };
  states["select.betriebswahl"].state = "Programm 1";
  const zwei = states["sensor.programm_2"];
  const zweiBloecke = zwei.attributes.blocks;
  zwei.attributes.blocks = [{ weekdays: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], switchPoints: [] }];
  flaeche._reiter = "zeitprogramme";
  flaeche._gebaut = false;
  flaeche._zeichnen();
  const wurzel = flaeche.shadowRoot;
  const heute = {
    zeilen: [...wurzel.querySelectorAll(".zp-heute-zeile")]
      .filter((zeile) => zeile.dataset.gruppe)
      .map((zeile) => ({
        gruppe: zeile.dataset.gruppe,
        programm: text(zeile.querySelector(".zp-heute-programm")),
        text: text(zeile.querySelector(".zp-heute-text")),
        jetztLinien: zeile.querySelectorAll(".jetzt-linie").length,
      })),
    leer: wurzel.querySelectorAll(".zp-mini").filter((zeile) => zeile.classList.contains("leer")).map((zeile) => ({
      name: text(zeile.querySelector(".zp-mininame")),
      spuren: zeile.querySelectorAll(".spur").length,
      aktivieren: zeile.querySelectorAll(".zp-aktivieren").length,
    })),
  };
  zwei.attributes.blocks = zweiBloecke;

  const vorherDaten = flaeche._daten;
  const vorherIndex = flaeche._anlageIndex;
  const erste = vorherDaten.anlagen[0];
  flaeche._daten = {
    ...vorherDaten,
    anlagen: [
      { ...erste, id: "anlage-a", name: "Anlage A" },
      { ...erste, id: "anlage-b", name: "Anlage B" },
    ],
  };
  flaeche._anlageIndex = -1;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  heute.alle = {
    karten: wurzel.querySelectorAll(".zp-heute").length,
    anlagen: [...wurzel.querySelectorAll(".zp-heute-anlagenname")].map(text),
    legenden: wurzel.querySelectorAll(".zp-legende").length,
  };
  flaeche._daten = vorherDaten;
  flaeche._anlageIndex = vorherIndex;
  flaeche._gebaut = false;
  bilanz.heute = heute;
}

// ---------------------------------------------------------------------------
// Reiter „Automatik“
//
// Die Daten stehen fest; geholt wird nichts. Ein Heizkreis ist eingerichtet,
// einer lädt zum Einrichten ein.
// ---------------------------------------------------------------------------
{
  const anlageId = (daten.anlagen[0] || {}).id;
  flaeche._automatik = {
    darf_aendern: true,
    profile: {
      standard: { heizgrenze: 17, absenkung_k: 1.5, sonnenquote: 60, stark: false, entscheidung: "07:00" },
    },
    heizkreise: [
      {
        heizkreis: "SN1-2-0",
        name: "Heizkreis",
        anlage_id: anlageId,
        eingerichtet: true,
        konfig: { aktiv: true, modus: "beobachten", profil: "standard", heizflaechen: "gemischt" },
        werte: { heizgrenze: 17, absenkung_k: 2, sonnenquote: 60, stark: false, entscheidung: "07:00" },
        zustand: "sonnentag",
        begruendung: "Sonnenquote 78 % – 19,5 °C bis 16:55.",
        kennwerte: {
          sonnenquote: 78,
          raum: 21.4,
          soll: 21,
          at_gedaempft: 11.8,
          heizgrenze: 17,
          eingriffe: 1,
          budget: 4,
          abweichung: 0.4,
          rueckkehr_k: 1,
          stark_k: 1.5,
          naechste_pruefung: "2026-09-28T07:00:00+02:00",
          modus_seit: "2026-09-27T07:00:00+02:00",
        },
        tag: { sonne: [0, 0.5, 0], absenkung_von: 7, absenkung_bis: 13.67, absenkung_ziel: 16.92, entscheidungen: [7], jetzt: 11.3 },
        protokoll: [{ zeit: "2026-09-27T07:00:00+02:00", art: "haette", text: "Sonnenquote 78 %.", werte: [] }],
        beobachtet_seit: "2026-09-20T07:00:00+02:00",
        pausiert_bis: null,
        korrektur: { an: true, noetig: 7, temperatur: { versatz: -1.4, tage: 9 }, sonne: { aktiv: true, faktor: 1.12, tage: 8 } },
        entitaeten: {
          zustand: "sensor.heizkreis_automatik_zustand",
          gedaempft: "sensor.heizkreis_automatik_gedaempft",
          sonnenquote: "sensor.heizkreis_automatik_sonnenquote",
          abweichung: "sensor.heizkreis_automatik_abweichung",
          eingriffe: "sensor.heizkreis_automatik_eingriffe",
          naechste_entscheidung: "sensor.heizkreis_automatik_naechste_entscheidung",
          aussen: "sensor.heizkreis_aussentemperatur",
          auskuehlzeit: "sensor.heizkreis_automatik_auskuehlzeit",
        },
      },
      { heizkreis: "SN1-3-0", name: "Heizkreis 2", anlage_id: anlageId, eingerichtet: false },
    ],
  };
  flaeche._automatikZeit = Date.now();
  flaeche._reiter = "automatik";
  flaeche._gebaut = false;
  flaeche._zeichnen();
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  const wurzel = flaeche.shadowRoot;
  bilanz.automatik = {
    karten: wurzel.querySelectorAll(".karte").length,
    marken: [...wurzel.querySelectorAll(".automatik-marke")].map((m) => String(m.textContent || "").trim()),
    felder: wurzel.querySelectorAll(".automatik-feld").length,
    geaendert: [...wurzel.querySelectorAll(".automatik-feld")].filter((f) => f.classList.contains("geaendert")).length,
    protokoll: [...wurzel.querySelectorAll(".automatik-protokoll")].reduce(
      (anzahl, liste) => anzahl + liste.childNodes.length,
      0
    ),
    einladungen: wurzel.querySelectorAll(".automatik-einladung").length,
    hinweise: [...wurzel.querySelectorAll(".automatik-hinweis")].map((t) => String(t.textContent || "").trim()),
    tagesleiste: wurzel.querySelectorAll(".automatik-tag-bild").length,
    knoepfe: [...wurzel.querySelectorAll(".automatik-knopf")].map((k) => String(k.textContent || "").trim()),
    kacheln: wurzel.querySelectorAll(".automatik-wert").map((k) => String(k.className).split(" ")[1]),
    skalen: wurzel.querySelectorAll(".automatik-skala").length,
    meta: String((wurzel.querySelector(".automatik-meta") || {}).textContent || ""),
    // In der Zone von Home Assistant, nicht in der des Rechners, auf dem der Test läuft.
    naechstePruefungUhrzeit: new Intl.DateTimeFormat("de", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: (hass.config || {}).time_zone,
    }).format(new Date("2026-09-28T07:00:00+02:00")),
    alteEingriffe: wurzel.querySelectorAll(".automatik-eingriffe").length,
    alteProfilzeile: wurzel.querySelectorAll(".automatik-profil").length,
    raumZonen: (wurzel.querySelectorAll(".automatik-wert").find((k) => k.classList.contains("raum")) || { querySelectorAll: () => [] })
      .querySelectorAll(".zone").length,
    raumWert: String(((wurzel.querySelectorAll(".automatik-wert").find((k) => k.classList.contains("raum")) || { querySelector: () => null })
      .querySelector(".punkt-wert") || {}).textContent || ""),
    grenzenEingaben: wurzel
      .querySelectorAll(".automatik-feld")
      .filter((f) => f.classList.contains("grenze"))
      .reduce((anzahl, f) => anzahl + f.querySelectorAll("input").length, 0),
    gruppen: wurzel.querySelectorAll(".automatik-einstellungsgruppe").map((g) => String((g.querySelector("h4") || {}).textContent || "")),
    klickbar: (wurzel.querySelector(".automatik-bereich") || { querySelectorAll: () => [] })
      .querySelectorAll(".klickbar")
      .map((k) => String(k.className).split(" ")[0]),
    korrektur: wurzel
      .querySelectorAll(".automatik-korrekturmarke")
      .map((m) => [String(m.textContent || ""), m.classList.contains("wirkt")]),
    korrekturSchalter: wurzel
      .querySelectorAll(".automatik-schalter")
      .filter((k) => k.classList.contains("klein"))
      .map((k) => k.getAttribute("aria-checked")),
    speichernGrau: (wurzel.querySelectorAll(".automatik-knopf").find((k) => k.classList.contains("speichern")) || {}).disabled,
    // Ja/Nein-Felder der Einstellungen sind Schalter; jeder Schalter mit Text nennt ihn vor der Spur.
    jaNein: wurzel
      .querySelectorAll(".automatik-feld")
      .flatMap((f) => f.querySelectorAll(".automatik-schalter"))
      .map((k) => [k.getAttribute("aria-label"), k.getAttribute("aria-checked")]),
    textVorn: wurzel
      .querySelectorAll(".automatik-schalter")
      .filter((k) => String(k.textContent || "").trim())
      .every((k) => k.children[0].tagName === "SPAN" && k.children[k.children.length - 1].tagName === "I"),
    ausrichtung: wurzel
      .querySelectorAll(".automatik-segment")
      .filter((segment) => segment.classList.contains("ausrichtung"))
      .flatMap((segment) => segment.children.map((t) => [String(t.textContent || "").trim(), t.getAttribute("aria-pressed")])),
    // Name · Zustand links, Einrichtung und Hilfe rechts.
    kopf: wurzel
      .querySelector(".automatik")
      .querySelector(".kartenkopf")
      .children.map((k) => (k.tagName === "H2" ? "h2" : String(k.className).split(" ")[0])),
  };

  // Ein Klick auf einen Ja/Nein-Schalter ist eine Änderung wie jede Eingabe: Speichern wird aktiv.
  {
    const speichern = wurzel.querySelectorAll(".automatik-knopf").find((k) => k.classList.contains("speichern"));
    const schalter = wurzel
      .querySelectorAll(".automatik-feld")
      .flatMap((f) => f.querySelectorAll(".automatik-schalter"))
      .find((k) => k.getAttribute("aria-label") === "Sonnentag absenken");
    const vorher = schalter.value;
    schalter.ausloesen("click");
    bilanz.automatik.jaNeinKlick = [vorher, schalter.value, schalter.getAttribute("aria-checked"), speichern.disabled];
    schalter.ausloesen("click");
    bilanz.automatik.jaNeinZurueck = [schalter.value, speichern.disabled];
  }

  // Speichern wird erst mit einer Abweichung vom gespeicherten Wert aktiv, und zurück wieder grau.
  {
    const speichern = wurzel.querySelectorAll(".automatik-knopf").find((k) => k.classList.contains("speichern"));
    const feld = wurzel.querySelectorAll(".automatik-feld").find((f) => f.classList.contains("grenze"));
    const eingabe = feld.querySelector("input");
    const vorher = eingabe.value;
    eingabe.value = "19";
    eingabe.ausloesen("input");
    const nachAenderung = speichern.disabled;
    eingabe.value = vorher;
    eingabe.ausloesen("input");
    bilanz.automatik.speichernFolge = [nachAenderung, speichern.disabled];
  }

  // Eine nicht gespeicherte Eingabe übersteht den Neuaufbau, etwa nach einem Klick ins Stundenraster.
  {
    const grenzfeld = () =>
      wurzel.querySelectorAll(".automatik-feld").find((f) => f.classList.contains("grenze")).querySelector("input");
    grenzfeld().value = "19";
    grenzfeld().ausloesen("input");
    flaeche._automatikNeuZeichnen();
    clearInterval(flaeche._automatikUhr);
    flaeche._automatikUhr = null;
    const speichern = wurzel.querySelectorAll(".automatik-knopf").find((k) => k.classList.contains("speichern"));
    bilanz.automatik.entwurfNachAufbau = [grenzfeld().value, speichern.disabled, flaeche._automatikBearbeitet];

    // Heizgrenze und eigener Wert zusammen: zwei Aufrufe, danach einmal nachladen.
    const aufrufe = [];
    const vorherWs = hass.callWS;
    hass.callWS = async (nachricht) => {
      aufrufe.push(nachricht.type);
      return nachricht.type === "heatnexus/automatik" ? flaeche._automatik : {};
    };
    const hysterese = wurzel
      .querySelectorAll(".automatik-feld")
      .find((f) => String((f.querySelector(".automatik-feldtitel") || {}).textContent) === "Hysterese Saison")
      .querySelector("input");
    hysterese.value = "0.8";
    hysterese.ausloesen("input");
    speichern.ausloesen("click");
    // Die Attrappe führt Zeitgeber selbst; die Aufrufe laufen über Microtasks durch.
    for (let runde = 0; runde < 20; runde += 1) await Promise.resolve();
    await flaeche._automatikLaeuft;
    clearInterval(flaeche._automatikUhr);
    flaeche._automatikUhr = null;
    hass.callWS = vorherWs;
    bilanz.automatik.gemeinsamGespeichert = aufrufe;
    bilanz.automatik.entwurfNachSpeichern = flaeche._automatikHatEntwurf();
  }

  // Ein offener Dialog übersteht das Nachladen im Takt.
  flaeche._dialogeSchliessen();
  const schleier = document.createElement("div");
  schleier.className = "schleier";
  wurzel.appendChild(schleier);
  const vorherWS = hass.callWS;
  hass.callWS = async () => flaeche._automatik;
  await flaeche._automatikHolen(true);
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  bilanz.automatik.dialogBleibt = wurzel.querySelectorAll(".schleier").length === 1;
  schleier.remove();
  hass.callWS = vorherWS;

  // Frisch gebaute Felder tragen keine Eingabe; die Sperre fürs Nachladen fällt.
  flaeche._automatikBearbeitet = true;
  flaeche._gebaut = false;
  flaeche._zeichnen();
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  bilanz.automatik.sperreNachAufbau = flaeche._automatikBearbeitet;

  // Wer „Erweitert“ zuklappt, gibt die Ansicht wieder frei.
  flaeche._automatikBearbeitet = true;
  const erweitert = wurzel.querySelector(".automatik-erweitert");
  erweitert.open = false;
  erweitert.ausloesen("toggle");
  bilanz.automatik.sperreNachZuklappen = flaeche._automatikBearbeitet;

  // Nach dem Speichern baut der Reiter neu; ein offenes „Erweitert“ bleibt offen.
  erweitert.open = true;
  erweitert.ausloesen("toggle");
  const vorherSpeichern = hass.callWS;
  hass.callWS = async () => flaeche._automatik;
  await flaeche._automatikAufruf({ type: "heatnexus/automatik/einstellen" });
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  hass.callWS = vorherSpeichern;
  const neu = wurzel.querySelector(".automatik-erweitert");
  bilanz.automatik.erweitertBleibtOffen = neu !== erweitert && neu.open === true;

  // Speichern unter „Erweitert“ meldet sich nach dem Neuaufbau mit „übernommen ✓“.
  hass.callWS = async () => flaeche._automatik;
  await flaeche._automatikSpeichern(flaeche._automatik.heizkreise[0], { eigene: {} });
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  hass.callWS = vorherSpeichern;
  bilanz.automatik.gespeichert = [...wurzel.querySelectorAll(".automatik-gespeichert")].map((t) => String(t.textContent || ""));

  // Der Einrichtungsdialog schließt oben rechts; Kopf und Tasten scrollen nicht mit.
  const vorherDialog = hass.callWS;
  hass.callWS = async () => ({
    temperatur: [],
    wetter: [],
    pv: [],
    pv_ist: [],
    personen: [],
    fenster: [],
    vorrang: [{ entity_id: "binary_sensor.solaranlage", name: "Solaranlage", bereich: "" }],
  });
  // Eine eingetragene Wetter-Entität, die nicht mehr zur Wahl steht, liefert keine Vorhersage.
  const vorherKonfig = flaeche._automatik.heizkreise[0].konfig;
  flaeche._automatik.heizkreise[0].konfig = { ...vorherKonfig, wetter: "weather.alt" };
  await flaeche._automatikDialog(flaeche._automatik.heizkreise[0]);
  flaeche._automatik.heizkreise[0].konfig = vorherKonfig;
  hass.callWS = vorherDialog;
  const dialog = wurzel.querySelector(".automatik-dialog");
  bilanz.automatik.wetterOptionen = dialog
    .querySelectorAll("option")
    .filter((o) => String(o.value).startsWith("weather."))
    .map((o) => String(o.textContent || ""));
  bilanz.automatik.vorrangWahl = dialog
    .querySelectorAll("input")
    .some((e) => e.value === "binary_sensor.solaranlage");
  const kopfzeile = dialog.querySelector(".dialog-kopf");
  const kreuz = kopfzeile && kopfzeile.querySelector(".dialog-schliessen");
  const inhalt = dialog.querySelector(".automatik-dialog-inhalt");
  bilanz.automatik.dialogKopf = Boolean(kreuz) && Boolean(inhalt) && !inhalt.querySelector(".dialog-leiste");
  if (kreuz) kreuz.ausloesen("click");
  bilanz.automatik.kreuzSchliesst = wurzel.querySelectorAll(".schleier").length === 0;

  // Nach „Übernehmen“ zeigt die Seite den neuen Stand, obwohl er geladen wurde, als der Dialog noch offen war.
  {
    const [kreisVorher] = flaeche._automatik.heizkreise;
    const bearbeitet = { ...kreisVorher, eingerichtet: true, konfig: { ...kreisVorher.konfig, raeume: ["sensor.raum"], wetter: "weather.test" } };
    const raum = "sensor.raum";
    const neuerStand = { ...flaeche._automatik, heizkreise: [{ ...bearbeitet, name: "Nach dem Bearbeiten" }, ...flaeche._automatik.heizkreise.slice(1)] };
    const vorherStand = flaeche._automatik;
    const vorherRuf = hass.callWS;
    hass.callWS = async (nachricht) => {
      if (nachricht.type === "heatnexus/automatik/kandidaten") {
        return {
          temperatur: [{ entity_id: raum, name: "Raum", bereich: "" }],
          wetter: [{ entity_id: bearbeitet.konfig.wetter, name: "Wetter", bereich: "" }],
          pv: [],
          pv_ist: [],
          personen: [],
          fenster: [],
          vorrang: [],
        };
      }
      return nachricht.type === "heatnexus/automatik" ? neuerStand : {};
    };
    flaeche._reiter = "automatik";
    // Die Attrappe kennt kein `:checked`; die Nachricht steht deshalb fest.
    flaeche._automatikDialogNachricht = (k) => ({ type: "heatnexus/automatik/einstellen", heizkreis: k.heizkreis, raeume: [raum], wetter: "weather.test" });
    flaeche._dialogeSchliessen();
    await flaeche._automatikDialog(bearbeitet);
    const uebernehmen = wurzel
      .querySelector(".automatik-dialog")
      .querySelectorAll("button")
      .find((t) => String(t.textContent || "") === "Übernehmen");
    uebernehmen.ausloesen("click");
    for (let runde = 0; runde < 20; runde += 1) await Promise.resolve();
    clearInterval(flaeche._automatikUhr);
    flaeche._automatikUhr = null;
    hass.callWS = vorherRuf;
    bilanz.automatik.nachDemDialog = [
      wurzel.querySelectorAll(".schleier").length,
      wurzel.querySelectorAll("h2").some((h) => String(h.textContent || "").includes("Nach dem Bearbeiten")),
    ];
    delete flaeche._automatikDialogNachricht;
    flaeche._automatik = vorherStand;
    flaeche._gebaut = false;
    flaeche._zeichnen();
    clearInterval(flaeche._automatikUhr);
    flaeche._automatikUhr = null;
  }

  // Mit eigenen Zielen nennt die Raum-Kachel jeden Raum mit Ist und Ziel.
  const [mitZielen] = flaeche._automatik.heizkreise;
  const vorherKennwerte = mitZielen.kennwerte;
  mitZielen.kennwerte = {
    ...vorherKennwerte,
    eigene_ziele: true,
    abweichung: -0.2,
    raeume: [{ entity_id: "climate.bad", name: "Bad", wert: 20.8, ziel: 21, heizt: true, veraltet: false }],
    vorrang: { laeuft: false, minuten: 90 },
  };
  const vorherTag = mitZielen.tag;
  mitZielen.tag = { ...vorherTag, stunden: Array.from({ length: 24 }, (_, stunde) => ({ stunde, vorrang: stunde === 10 })) };
  flaeche._gebaut = false;
  flaeche._zeichnen();
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  bilanz.automatik.raumliste = wurzel
    .querySelectorAll(".raeume")
    .flatMap((l) => l.children.map((z) => z.children.map((t) => String(t.textContent || ""))));
  const raumKachel = wurzel.querySelectorAll(".automatik-wert").find((k) => k.classList.contains("raum"));
  bilanz.automatik.raumKachel = [...raumKachel.querySelectorAll(".zahl"), ...raumKachel.querySelectorAll(".neben")].map((teil) =>
    String(teil.textContent || "")
  );
  bilanz.automatik.raumSkalaMitListe = raumKachel.querySelectorAll(".zone").length;
  bilanz.automatik.vorrangZeile = [...wurzel.querySelectorAll(".vorrang-zeile")].map((l) => String(l.textContent || ""));
  bilanz.automatik.modusStunden = wurzel.querySelectorAll(".automatik-stunde").filter((z) => z.classList.contains("m-programm")).length;
  bilanz.automatik.stundenLegende = wurzel.querySelectorAll(".automatik-stundenlegende").length;
  bilanz.automatik.legendeHilfe = wurzel
    .querySelectorAll(".automatik-stundenlegende")
    .map((l) => l.querySelectorAll(".fragezeichen").length);
  const zehn = wurzel.querySelectorAll(".automatik-stunde").find((z) => String((z.querySelector(".uhr") || {}).textContent) === "10 Uhr");
  zehn.ausloesen("click");
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  bilanz.automatik.stundenKasten = flaeche.shadowRoot.querySelectorAll(".automatik-stundenkasten").map((k) => String((k.querySelector(".kopf") || {}).textContent || ""));
  bilanz.automatik.stundeJeKreis = Object.entries(flaeche._automatikStundeOffen || {});
  bilanz.automatik.stundeOffen = flaeche.shadowRoot.querySelectorAll(".automatik-stunde").filter((z) => z.classList.contains("offen")).length;
  flaeche._automatikStundeOffen = {};
  mitZielen.kennwerte = vorherKennwerte;
  mitZielen.tag = vorherTag;
}

// ---------------------------------------------------------------------------
// Reiter „Automatik“: Kachel „Haus“ und Kurve „Raum laut Vorhersage“
//
// Die Kachel folgt dem Stand des Hausmodells: lernt, beobachtet, aktiv. Ohne
// Angabe vom Server (ältere Fassung) fehlt sie.
// ---------------------------------------------------------------------------
{
  const [kreis] = flaeche._automatik.heizkreise;
  const vorherKennwerte = kreis.kennwerte;
  const vorherTag = kreis.tag;
  const wurzel = flaeche.shadowRoot;
  const text = (knoten) => String((knoten || {}).textContent || "");
  const modell = { auskuehlzeit_h: 40, sonne_k_h: 0.6, heizwirkung: 0.03, wind: false, fehler: 0.3, fehler_bleibt: 0.5, vergleiche: 14, tage: 6, status: "aktiv" };
  const zeigen = (hausmodell, vorhersage = undefined) => {
    kreis.kennwerte = { ...vorherKennwerte, hausmodell };
    kreis.tag = { ...vorherTag, vorhersage };
    flaeche._reiter = "automatik";
    flaeche._gebaut = false;
    flaeche._zeichnen();
    clearInterval(flaeche._automatikUhr);
    flaeche._automatikUhr = null;
    const kachel = wurzel.querySelectorAll(".automatik-wert").find((k) => k.classList.contains("haus"));
    return {
      kachel: Boolean(kachel),
      titel: text(kachel && kachel.querySelector(".titel")),
      zahl: text(kachel && kachel.querySelector(".zahl")),
      neben: text(kachel && kachel.querySelector(".neben")),
      fuss: kachel ? kachel.querySelectorAll(".fuss").map(text) : [],
      tasten: kachel ? kachel.querySelectorAll(".automatik-knopf").map(text) : [],
      // Zahl und Einordnung öffnen den Sensor der Auskühlzeit.
      klickbar: kachel ? kachel.querySelectorAll(".klickbar").map((k) => String(k.className).split(" ")[0]) : [],
      kurve: wurzel.querySelectorAll(".al-vorhersage").length,
      legende: wurzel.querySelectorAll(".automatik-legende").flatMap((l) => l.children.map(text)),
    };
  };
  bilanz.automatikHaus = {
    aktiv: zeigen(modell, [[9, 21.4], [10, 21.3]]),
    beobachtetWenige: zeigen({ ...modell, status: "beobachtet", vergleiche: 3 }),
    beobachtetVoll: zeigen({ ...modell, status: "beobachtet", fehler: 0.36, fehler_bleibt: 0.41 }),
    lernt: zeigen({ status: "lernt", grund: "unpassend" }),
    lerntOhneGrund: zeigen({ status: "lernt", grund: null }),
    ohneAngabe: zeigen(undefined),
  };

  // „Hausmodell neu lernen“ steht in den Einstellungen und fragt vorher nach.
  zeigen(modell);
  const aufrufe = [];
  const fragen = [];
  const vorherWs = hass.callWS;
  const vorherFrage = flaeche._bestaetigen;
  hass.callWS = async (nachricht) => {
    aufrufe.push(nachricht);
    return nachricht.type === "heatnexus/automatik" ? flaeche._automatik : {};
  };
  flaeche._bestaetigen = async (titel) => {
    fragen.push(titel);
    return true;
  };
  const einstellungen = wurzel.querySelector(".automatik-erweitert");
  const taste = einstellungen.querySelectorAll(".automatik-knopf").find((k) => text(k) === "Hausmodell neu lernen");
  taste.ausloesen("click");
  for (let runde = 0; runde < 20; runde += 1) await Promise.resolve();
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  hass.callWS = vorherWs;
  flaeche._bestaetigen = vorherFrage;
  bilanz.automatikHaus.frage = fragen;
  bilanz.automatikHaus.neuLernen = aufrufe.map((a) => [a.type, a.heizkreis]);

  kreis.kennwerte = vorherKennwerte;
  kreis.tag = vorherTag;
}

// ---------------------------------------------------------------------------
// Reiter „Automatik“: Modus „Manuell mit Empfehlung“
//
// Eine offene Empfehlung steht als Hinweis mit Knopf unter dem Kreis; der Knopf
// ruft den Übernahmebefehl auf.
// ---------------------------------------------------------------------------
{
  const [kreis] = flaeche._automatik.heizkreise;
  const vorherKonfig = kreis.konfig;
  kreis.konfig = { ...vorherKonfig, modus: "empfehlen" };
  kreis.empfehlung = { zustand: "heizpause", begruendung: "Heizpause empfohlen: 22 °C Außentemperatur.", seit: "2026-09-27T07:00:00+02:00" };
  flaeche._reiter = "automatik";
  flaeche._gebaut = false;
  flaeche._zeichnen();
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  const wurzel = flaeche.shadowRoot;
  const modus = wurzel
    .querySelectorAll(".automatik-gruppe")
    .find((g) => String((g.querySelector(".automatik-gruppentitel") || {}).textContent) === "Modus");
  const hinweis = wurzel.querySelectorAll(".automatik-hinweis").find((h) => String(h.textContent).includes("Heizpause empfohlen"));
  const knopf = hinweis && hinweis.querySelector("button");
  const aufrufe = [];
  const vorherWs = hass.callWS;
  hass.callWS = async (nachricht) => {
    aufrufe.push(nachricht);
    return nachricht.type === "heatnexus/automatik" ? flaeche._automatik : {};
  };
  if (knopf) knopf.ausloesen("click");
  for (let runde = 0; runde < 20; runde += 1) await Promise.resolve();
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  hass.callWS = vorherWs;
  // Der Punkt am Reiter folgt dem Sensor „Empfehlung“, auch ohne geladene Automatik.
  const vorherEntities = hass.entities;
  const sensor = "sensor.heizkreis_empfehlung";
  hass.entities = { [sensor]: { entity_id: sensor, platform: "heatnexus", translation_key: "automatik_empfehlung" } };
  const punkt = () => {
    flaeche._aktualisieren();
    const taste = wurzel.querySelector(".reiter").querySelectorAll("button").find((b) => b.dataset.reiter === "automatik");
    return Boolean(taste && taste.classList.contains("punkt"));
  };
  const punktFolge = [];
  for (const zustand of ["heizpause", "keine"]) {
    states[sensor] = { entity_id: sensor, state: zustand, attributes: {} };
    punktFolge.push(punkt());
  }
  delete states[sensor];
  hass.entities = vorherEntities;
  bilanz.automatikEmpfehlung = {
    modus: modus ? modus.querySelectorAll("button").map((t) => [String(t.textContent || "").trim(), t.getAttribute("aria-pressed")]) : [],
    hinweise: [...wurzel.querySelectorAll(".automatik-hinweis")].map((t) => String(t.textContent || "").trim()),
    knopf: knopf ? String(knopf.textContent || "").trim() : null,
    knoepfe: hinweis ? hinweis.querySelectorAll("button").map((t) => String(t.textContent || "").trim()) : [],
    markiert: Boolean(hinweis && hinweis.classList.contains("empfehlung")),
    titel: hinweis ? hinweis.querySelectorAll(".empfehlung-titel").map((t) => String(t.textContent || "").trim()) : [],
    aufrufe: aufrufe.map((a) => [a.type, a.heizkreis]),
    punkt: punktFolge,
  };
  // „Aus“ steht in derselben Auswahl wie die Modi und schaltet nur `aktiv` ab.
  {
    const aus = modus ? modus.querySelectorAll("button").find((t) => String(t.textContent || "").trim() === "Aus") : null;
    const gesendet = [];
    hass.callWS = async (nachricht) => {
      gesendet.push(nachricht);
      return flaeche._automatik;
    };
    if (aus) aus.ausloesen("click");
    for (let runde = 0; runde < 20; runde += 1) await Promise.resolve();
    clearInterval(flaeche._automatikUhr);
    flaeche._automatikUhr = null;
    hass.callWS = vorherWs;
    bilanz.automatikEmpfehlung.ausGesendet = gesendet
      .filter((n) => n.type === "heatnexus/automatik/einstellen")
      .map(({ aktiv, modus: wahl }) => ({ aktiv, modus: wahl }));
  }
  delete kreis.empfehlung;
  kreis.konfig = vorherKonfig;
  flaeche._gebaut = false;
}

// ---------------------------------------------------------------------------
// Reiter „Automatik“ über alle Anlagen
//
// Die Automatik arbeitet je Heizkreis. Bei „Alle Anlagen“ stehen die Kreise
// deshalb in einem Raster, eingerichtete zuerst, mit der Anlage im Titel.
// ---------------------------------------------------------------------------
{
  const vorherDaten = flaeche._daten;
  const vorherIndex = flaeche._anlageIndex;
  const erste = vorherDaten.anlagen[0];
  flaeche._daten = {
    ...vorherDaten,
    anlagen: [
      { ...erste, id: "anlage-a", name: "Anlage A" },
      { ...erste, id: "anlage-b", name: "Anlage B" },
    ],
  };
  flaeche._anlageIndex = -1;
  const [eingerichtet] = flaeche._automatik.heizkreise;
  flaeche._automatik = {
    ...flaeche._automatik,
    heizkreise: [
      { heizkreis: "SN9-2-0", name: "Heizkreis 2", anlage: "Anlage A", anlage_id: "anlage-a", eingerichtet: false },
      { ...eingerichtet, anlage: "Anlage B", anlage_id: "anlage-b" },
    ],
  };
  flaeche._reiter = "automatik";
  flaeche._gebaut = false;
  flaeche._zeichnen();
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  const wurzel = flaeche.shadowRoot;
  bilanz.automatikAlle = {
    raster: wurzel.querySelectorAll(".raster").length,
    trenner: wurzel.querySelectorAll(".anlagen-trenner").length,
    titel: [...wurzel.querySelectorAll(".karte")].map((karte) => {
      const kopf = karte.querySelector("h2");
      return kopf ? String(kopf.textContent || "").trim() : "";
    }),
  };
  flaeche._daten = vorherDaten;
  flaeche._anlageIndex = vorherIndex;
  flaeche._gebaut = false;
}

// ---------------------------------------------------------------------------
// „Alle“ zusammen und die Hilfe über alle Anlagen
//
// Zusammen steht ein Raster da, Karten gleicher Art beieinander und jede mit
// ihrer Anlage. Die Hilfe fasst immer zusammen und nennt jede Erklärung einmal.
// ---------------------------------------------------------------------------
{
  const vorherDaten = flaeche._daten;
  const vorherIndex = flaeche._anlageIndex;
  const vorherAnordnung = flaeche._anordnung;
  const erste = vorherDaten.anlagen[0];
  const gleich = { titel: "Heizgrenze", text: "Ab dieser Außentemperatur heizt der Kreis." };
  flaeche._daten = {
    ...vorherDaten,
    anlagen: [
      { ...erste, id: "anlage-a", name: "Anlage A", hilfe_liste: [gleich, { titel: "Puffer", text: "Speicher." }] },
      { ...erste, id: "anlage-b", name: "Anlage B", hilfe_liste: [gleich, { titel: "Kessel", text: "Erzeuger." }] },
    ],
  };
  flaeche._anlageIndex = -1;
  const wurzel = flaeche.shadowRoot;
  const karten = () =>
    wurzel.querySelector(".raster").children.map((karte) => ({
      anlagen: karte.querySelectorAll(".karten-anlage").map((marke) => String(marke.textContent)),
      titel: String((karte.querySelector("h2") || {}).textContent || "").trim(),
      verschmolzen: karte.classList.contains("verschmolzen"),
      klappen: karte.querySelectorAll(".klappkarte").length,
    }));
  const zeichnen = (reiter, einstellungen, ordnung) => {
    flaeche._anordnung = { einstellungen, ...(ordnung ? { [reiter]: { ordnung } } : {}) };
    flaeche._reiter = reiter;
    flaeche._gebaut = false;
    flaeche._zeichnen();
  };
  zeichnen("uebersicht", { alle: "getrennt" });
  const getrennt = { raster: wurzel.querySelectorAll(".raster").length, marken: wurzel.querySelectorAll(".karten-anlage").length };
  zeichnen("uebersicht", { alle: "zusammen" });
  const zusammen = { raster: wurzel.querySelectorAll(".raster").length, trenner: wurzel.querySelectorAll(".anlagen-trenner").length, karten: karten() };
  // Die verschmolzene Karte hat eine eigene Kennung und lässt sich wie jede andere verschieben.
  zeichnen("uebersicht", { alle: "zusammen" }, ["alle|stoerungen", "alle|seite"]);
  const gespeichert = karten().slice(0, 2);
  zeichnen("steuerung", { alle: "zusammen" });
  const steuerung = karten();
  // Jeder Reiter, der zusammenfasst, nennt an jeder Karte ihre Anlage – auch an künftigen Karten.
  const jeReiter = {};
  for (const reiter of ["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme"]) {
    zeichnen(reiter, { alle: "zusammen" });
    const liste = karten().filter((k) => k.titel !== "HeatNexus");
    jeReiter[reiter] = { karten: liste.length, ohneAnlage: liste.filter((k) => !k.anlagen.length).map((k) => k.titel) };
  }
  // Im Anordnen-Modus: Pfeile schieben ganze Karten, am Ende ist der Pfeil gesperrt.
  flaeche._anordnen = true;
  zeichnen("uebersicht", { alle: "zusammen" });
  const griffe = (nr) => wurzel.querySelectorAll(".anordner")[nr].querySelector(".anordner-griff").querySelectorAll("button");
  const erster = griffe(0);
  const anordnen = { linksGesperrt: erster[0].disabled, rechtsGesperrt: erster[1].disabled };
  erster[1].ausloesen("click");
  flaeche._gebaut = false;
  flaeche._zeichnen();
  anordnen.nachSchritt = wurzel.querySelectorAll(".anordner").slice(0, 2).map((h) => h.dataset.kennung);
  flaeche._anordnen = false;
  zeichnen("hilfe", { alle: "getrennt" });
  const hilfe = {
    raster: wurzel.querySelectorAll(".raster").length,
    eintraege: wurzel.querySelectorAll(".hilfe-eintrag").map((e) => String(e.querySelector("summary").textContent)),
  };
  bilanz.alleZusammen = { getrennt, zusammen, gespeichert, steuerung, jeReiter, anordnen, hilfe };
  flaeche._daten = vorherDaten;
  flaeche._anlageIndex = vorherIndex;
  flaeche._anordnung = vorherAnordnung;
  flaeche._reiter = "uebersicht";
  flaeche._gebaut = false;
}

// ---------------------------------------------------------------------------
// Reiter „Befund“
//
// Ein Befund mit Wert bekommt eine Karte, die übrigen stehen in einer Kachel.
// Antippen eines Balkens schreibt seinen Wert unter das Bild.
// ---------------------------------------------------------------------------
{
  const anlageId = (daten.anlagen[0] || {}).id;
  const kreis = flaeche._automatik.heizkreise.find((k) => k.eingerichtet);
  const kennung = kreis.heizkreis;
  const befund = (art, status, wert, angaben = {}, grund = null) => ({ art, status, wert, einheit: "", stufe: "vorlaeufig", angaben, grund, vergleich: {} });
  const stand = {
    lage: { befunde: 3, seit: "2026-08-01", unauffaellig: 1, hinweise: 0, sammelt: 1, braucht_daten: 1 },
    abschnitte: [
      { art: "haus", kennung, titel: "Heizkreis", befunde: [befund("waermespeicher", "braucht_daten", null, {}, "raeume")] },
      {
        art: "heizkreis",
        kennung,
        titel: "Heizkreis",
        befunde: [
          befund("vorlauf", "unauffaellig", 3.5, { je_tag: [["2026-10-01", 0], ["2026-10-02", 4]] }),
          befund("naechte", "sammelt", null),
        ],
      },
    ],
  };
  flaeche._befund = { [anlageId]: stand, [kreis.anlage_id]: stand };
  flaeche._befundZeit = Date.now();
  flaeche._reiter = "befund";
  flaeche._gebaut = false;
  flaeche._zeichnen();
  const wurzel = flaeche.shadowRoot;
  const balken = wurzel.querySelectorAll(".ablesbar");
  if (balken[1]) balken[1].ausloesen("click");
  const klappe = wurzel.querySelector(".klappkarte");
  bilanz.befund = {
    titel: [...wurzel.querySelectorAll(".kartenkopf"), ...wurzel.querySelectorAll("summary")].map((kopf) => String(kopf.textContent || "").trim()),
    offen: (wurzel.querySelector(".befund-offen") || { children: [] }).children.length,
    eingeklappt: klappe ? !klappe.open : null,
    zahlmarke: String((wurzel.querySelector(".befund-zahlmarke") || {}).textContent || ""),
    zurAutomatik: wurzel.querySelectorAll(".befund-sprung").length,
    ablesbar: balken.length,
    abgelesen: [...wurzel.querySelectorAll(".befund-ablesen")].map((a) => String(a.textContent)),
  };
  // Einzelne Karten: Starts mit und ohne Automatik, Räume meist zu warm.
  const gruppe = (tage, starts, gradtage) => ({ tage, starts, gradtage, starts_je_gt: starts / gradtage });
  const startsKarte = flaeche._befundKarte(
    { art: "kessel", kennung: "/1/60/0", titel: "Kessel" },
    befund("starts", "unauffaellig", -50, { mit: gruppe(6, 6, 60), ohne: gruppe(8, 16, 80) })
  );
  const warmKarte = flaeche._befundKarte({ art: "heizkreis", kennung, titel: "Heizkreis" }, befund("raeume", "hinweis", 95, { zu_warm: true }));
  bilanz.befund.starts = String(startsKarte.textContent || "");
  bilanz.befund.zuWarm = String(warmKarte.textContent || "");

  // Unter „Alle“ stehen beide Anlagen in einem Stand: eine Kopfkarte, Zählung addiert,
  // jede Karte mit ihrer Anlage, kein Verweis auf den fremden Kessel.
  const vorherDaten = flaeche._daten;
  const vorherIndex = flaeche._anlageIndex;
  flaeche._daten = {
    ...vorherDaten,
    anlagen: [
      { ...vorherDaten.anlagen[0], id: "anlage-a", name: "Anlage A" },
      { ...vorherDaten.anlagen[0], id: "anlage-b", name: "Anlage B" },
    ],
  };
  flaeche._anlageIndex = -1;
  const ohneKessel = {
    lage: { ...stand.lage },
    abschnitte: [...stand.abschnitte, { art: "waermeerzeuger", kennung: "", titel: "", befunde: [] }],
  };
  const mitKessel = {
    lage: { befunde: 2, seit: "2026-07-15", unauffaellig: 1, hinweise: 1, sammelt: 0, braucht_daten: 0 },
    abschnitte: [
      { art: "heizkreis", kennung: "SN9-2-0", titel: "Heizkreis 2", befunde: [befund("vorlauf", "hinweis", 12)] },
      { art: "kessel", kennung: "/1/60/0", titel: "Kessel", befunde: [befund("laufzeit", "unauffaellig", 2.4)] },
    ],
  };
  flaeche._befund = { "anlage-a": ohneKessel, "anlage-b": mitKessel };
  flaeche._reiter = "befund";
  flaeche._gebaut = false;
  flaeche._zeichnen();
  bilanz.befundAlle = {
    raster: wurzel.querySelectorAll(".raster").length,
    trenner: wurzel.querySelectorAll(".anlagen-trenner").length,
    anzahlen: [...wurzel.querySelectorAll(".befund-anzahl")].map((s) => String(s.textContent)),
    herkunft: [...wurzel.querySelectorAll(".befund-abschnitt")].map((s) => String(s.textContent)),
    offen: (wurzel.querySelector(".befund-offen") || { children: [] }).children.length,
    seit: String((wurzel.querySelector(".befund-seit") || {}).textContent || ""),
    waermeerzeuger: [...wurzel.querySelectorAll("h2")].filter((h) => String(h.textContent) === "Wärmeerzeuger").length,
    sammelkarten: [...wurzel.querySelectorAll(".befund-karte")]
      .filter((k) => k.querySelector(".befund-liste"))
      .map((k) => ({
        titel: String(k.querySelector("h2").textContent),
        hinweis: k.classList.contains("befund-hinweis"),
        zeilen: [...k.querySelectorAll(".name")].map((n) => String(n.textContent)),
      })),
  };
  flaeche._daten = vorherDaten;
  flaeche._anlageIndex = vorherIndex;
  flaeche._befund = { [anlageId]: stand, [kreis.anlage_id]: stand };

  // Im Reiter Automatik steht dieselbe Liste kompakt; Antippen öffnet den Befund.
  flaeche._reiter = "automatik";
  flaeche._gebaut = false;
  flaeche._zeichnen();
  clearInterval(flaeche._automatikUhr);
  flaeche._automatikUhr = null;
  const zeilen = wurzel.querySelectorAll(".befund-zeile");
  bilanz.befund.automatik = {
    zeilen: zeilen.length,
    optimierung: wurzel.querySelectorAll(".optimierung-art").length + wurzel.querySelectorAll(".automatik-optimierung").length,
  };
  if (zeilen[0]) zeilen[0].ausloesen("click");
  bilanz.befund.automatik.nachKlick = flaeche._reiter;
  flaeche._befund = undefined;
  flaeche._gebaut = false;
}

// ---------------------------------------------------------------------------
// Misslungenes Speichern
//
// Die Attrappe wirft bei jedem `callWS`. Wer die Farbwahl anfasst, muss das
// erfahren – sonst springt die Ansicht beim nächsten Laden zurück.
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Störspeicher: Zeilen, Tasten im Detail, Dienstaufruf
// ---------------------------------------------------------------------------
// Erst hier: Der Übersichtslauf oben prüft den Weg ohne Störspeicher.
const speicherZustand = flaeche._hass.states["sensor.stoerspeicher"];
if (speicherZustand) speicherZustand.attributes.eintraege = STOERSPEICHER;
flaeche._reiter = "uebersicht";
flaeche._gebaut = false;
flaeche._zeichnen();
flaeche._aktualisieren();
const speicherZeilen = [...flaeche.shadowRoot.querySelectorAll(".stoerspeicher-zeile")];
flaeche._stoerspeicherDetail(ANLIEGEND, "sensor.stoerspeicher");
const tasten = [...flaeche.shadowRoot.querySelectorAll(".dialog-taste")].map((t) => String(t.textContent || "").trim());
const echtesBestaetigen = flaeche._bestaetigen;
flaeche._bestaetigen = async () => true;
const vorQuittung = dienstAufrufe.length;
await flaeche._stoerspeicherAktion("quittieren", ANLIEGEND, "sensor.stoerspeicher");
flaeche._bestaetigen = echtesBestaetigen;
bilanz.stoerspeicher = {
  zeilen: speicherZeilen.length,
  kacheln: [...flaeche.shadowRoot.querySelectorAll(".stoerspeicher-kachel")].map((k) => String(k.className)),
  kachelTasten: [...flaeche.shadowRoot.querySelectorAll(".stoerspeicher-taste")].map((t) => t.getAttribute("aria-label")),
  stoerungImKopf: flaeche._stoerung({ stoerungen: [], stoerspeicher: "sensor.stoerspeicher" }),
  stufen: (() => {
    const stufe = (eintraege) => {
      flaeche._hass.states["sensor.stufe"] = { entity_id: "sensor.stufe", state: "1", attributes: { eintraege } };
      return flaeche._stoerungsstufe({ stoerungen: [], stoerspeicher: "sensor.stufe" });
    };
    // Eine Gerätezeile mit E346; ihr Melder liegt an.
    const mitZeile = (eintraege) => {
      flaeche._hass.states["sensor.zeile"] = {
        entity_id: "sensor.zeile",
        state: "Verkleidungstür offen",
        attributes: { stoerung_aktiv: true, meldungen: [{ code: 346 }] },
      };
      flaeche._hass.states["sensor.stufe"] = { entity_id: "sensor.stufe", state: "1", attributes: { eintraege } };
      return flaeche._stoerungsstufe({ stoerungen: [{ entity: "sensor.zeile" }], stoerspeicher: "sensor.stufe" });
    };
    return {
      leer: stufe([]),
      info: stufe([{ aktiv: true, symbol: "I" }]),
      fehler: stufe([{ aktiv: true, symbol: "I" }, { aktiv: true, symbol: "E" }]),
      alarm: stufe([{ aktiv: true, symbol: "I" }, { aktiv: true, symbol: "A" }]),
      erledigt: stufe([{ aktiv: false, symbol: "A" }]),
      zeileOhneEintrag: mitZeile([{ aktiv: true, symbol: "I", code: 9 }]),
      zeileImSpeicher: mitZeile([{ aktiv: true, symbol: "I", code: 346 }]),
    };
  })(),
  muell: flaeche.shadowRoot.querySelectorAll(".stoerspeicher-muell").length,
  tasten,
  aufruf: dienstAufrufe[vorQuittung],
};

const meldungen = [];
flaeche.addEventListener("hass-notification", (ereignis) => {
  meldungen.push(ereignis.detail && ereignis.detail.message);
});
hass.callWS = async () => {
  throw new Error("kein Server im Test");
};
flaeche._darstellungSetzen({ farbsatz: "kontrast" });
await Promise.resolve();
await Promise.resolve();
bilanz.meldungBeimSpeichern = meldungen;

// ---------------------------------------------------------------------------
// Abzeichen der Automatik am Heizkreis: verborgen im Programm, sonst die
// Kurzfassung des Zustands; ein Klick öffnet den Reiter „Automatik“.
// ---------------------------------------------------------------------------
{
  const zustaende = flaeche._hass.states;
  const vorherReiter = flaeche._reiter;
  zustaende["sensor.hk_automatik"] = { entity_id: "sensor.hk_automatik", state: "programm", attributes: { kurz: null } };
  const vorher = flaeche._bindungen.length;
  const zeile = flaeche._heizkreiszeile({ entity: "climate.heizkreis", titel: "HK", automatik: "sensor.hk_automatik" });
  const binden = () => flaeche._bindungen.slice(vorher).forEach((bindung) => bindung());
  const abzeichen = zeile.querySelector(".automatik-abzeichen");
  binden();
  const imProgramm = abzeichen.hidden;
  zustaende["sensor.hk_automatik"] = {
    entity_id: "sensor.hk_automatik",
    state: "sonnentag",
    attributes: { kurz: "Sonnentag · 19 °C" },
  };
  binden();
  const sonnentag = {
    verborgen: abzeichen.hidden,
    text: String(abzeichen.querySelector("span").textContent),
    zustand: abzeichen.dataset.zustand,
  };
  abzeichen.ausloesen("click");
  const reiter = flaeche._reiter;
  const ohneAutomatik = flaeche._heizkreiszeile({ entity: "climate.heizkreis", titel: "HK" });
  bilanz.automatikAbzeichen = { imProgramm, sonnentag, reiter, ohne: !ohneAutomatik.querySelector(".automatik-abzeichen") };
  flaeche._reiter = vorherReiter;
  flaeche._gebaut = false;
  flaeche._zeichnen();
}

console.log(JSON.stringify(bilanz));
