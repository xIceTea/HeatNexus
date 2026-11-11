/**
 * Reihenfolge und Sichtbarkeit der Karten.
 *
 * Reine Funktionen ohne Zustand – deshalb eigene Datei und deshalb
 * prüfbar: `tests/test_anordnung.py` lädt genau dieses Modul in Node und
 * vergleicht sein Ergebnis mit der Python-Fassung in `anordnung.py`.
 * Laufen die beiden auseinander, verschiebt der Browser Karten anders als
 * der Server sie speichert.
 */

export const OHNE_WERT = ["unavailable", "unknown", "none", ""];

// Wie lange „übertragen ✓" stehen bleibt, bevor wieder der Zustand erscheint.
//
// **Muss ausgeführt werden.** Beim Schnitt in ES-Module blieben die beiden
// Zeitwerte hier ohne `export` liegen, während die Oberfläche sie weiter
// benutzte. Ergebnis: Beim ersten Aufräumen einer Rückmeldung flog ein
// `ReferenceError`, und „wird ausgeführt …" blieb für immer stehen.
export const RUECKMELDUNG_MS = 4000;

/** Wie lange ein Zahlenfeld nach der letzten Eingabe wartet, bevor es
 *  überträgt. Ohne die Pause ginge jede getippte Ziffer einzeln zur
 *  Anlage - bei "15" erst die 1, dann die 15. */
export const ZAHL_VERZOEGERUNG_MS = 2500;

// Wie lange auf die Bestätigung der Anlage gewartet wird, bevor die
// Rückmeldung aufgibt. Die Anlage wird nur alle 30 s abgefragt – drei
// Minuten reichen also für mehrere Versuche. Länger zu warten hilft nicht:
// Wird der Vorgang inzwischen an der Anlage selbst abgebrochen, bliebe
// „wird ausgeführt …" sonst minutenlang stehen, obwohl nichts mehr läuft.
export const BESTAETIGUNG_MAX_MS = 3 * 60 * 1000;

/**
 * Wie lange eine Bedienung ihrem eigenen Ergebnis glaubt, bevor wieder die
 * Anlage recht bekommt.
 *
 * Die Anlage wird alle 30 s abgefragt, und dazwischen meldet sie noch den
 * alten Stand. Ohne diese Annahme:
 *
 * * „Warmwasser laden abbrechen" liess die Taste unverändert auf „läuft"
 *   stehen – es sah aus, als sei der Druck ins Leere gegangen, also drückte
 *   man noch einmal;
 * * ein Zahlenfeld sprang nach dem Tippen auf den alten Wert zurück und zwei
 *   Sekunden später auf den neuen.
 *
 * Beides zeigt deshalb sofort, was bedient wurde, und hält daran fest, bis
 * die Anlage dasselbe meldet oder diese Zeit um ist. Etwas mehr als ein
 * Abrufabstand, damit ein knapp verpasster Durchlauf noch zählt.
 */
export const ANNAHME_MS = 45 * 1000;

/**
 * Wie lange eine Taste nach einem Druck gesperrt bleibt.
 *
 * Bewusst kürzer als die Annahme: Die Sperre soll nur verhindern, dass ein
 * zweiter Druck den ersten überholt. An die Annahme gekoppelt hielte sie auch
 * dann, wenn die Anlage den Auftrag nie übernimmt – die Annahme wird in dem
 * Fall nicht verbraucht. Ein gezieltes Nachlesen ist nach gut einer Sekunde
 * zurück.
 */
export const SPERRE_MS = 5 * 1000;

/**
 * Wann nach einer Bedienung nachgelesen wird, in Sekunden nach dem Befehl.
 *
 * Die Steuerung rechnet einen neuen Sollwert unterschiedlich schnell: mal in
 * Sekunden, mal erst nach einer Minute. Die Abstände wachsen deshalb, und
 * gelesen wird nur, solange sich noch nichts bewegt hat.
 */
export const NACHFASS_PLAN = [0, 4, 8, 12, 20, 30, 45, 60];

/**
 * Wie lange der Sollwert nach einer Betriebswahl „lädt …" zeigt, höchstens.
 * Ändert er sich früher, erscheint der neue Wert sofort.
 */
export const SOLLWERT_WARTEN_MS = 45 * 1000;

/**
 * Wie oft ein Abbruch nachgesetzt wird, den die Anlage überging.
 *
 * Wiederholt wird ausschließlich die Freigabe auf Nein – ein Zustand, kein
 * Auslöser, und damit gefahrlos wiederholbar. Die Betriebswahl bleibt außen
 * vor: Ein zusätzlicher Befehl dorthin macht den Abbruch unwirksam.
 */
export const ABBRUCH_VERSUCHE = 2;
export const ABBRUCH_PAUSE_MS = 6 * 1000;

export const REITER = [
  { schluessel: "uebersicht", titel: "Übersicht", symbol: "mdi:view-dashboard-outline" },
  { schluessel: "steuerung", titel: "Steuerung", symbol: "mdi:tune-vertical" },
  { schluessel: "automatik", titel: "Automatik", symbol: "mdi:weather-sunny-alert" },
  { schluessel: "befund", titel: "Auswertung", symbol: "mdi:clipboard-pulse-outline" },
  { schluessel: "wartung", titel: "Wartung", symbol: "mdi:wrench-outline" },
  { schluessel: "verlauf", titel: "Verlauf", symbol: "mdi:chart-line" },
  { schluessel: "zeitprogramme", titel: "Zeitprogramme", symbol: "mdi:calendar-clock" },
  { schluessel: "hilfe", titel: "Hilfe", symbol: "mdi:help-circle-outline" },
];

// Farbsätze der Oberfläche. Die Schlüssel decken sich mit `schema.FARBSAETZE`
// auf der Serverseite - was hier gewählt wird, muss dort gespeichert werden
// können. Die Werte stehen in `PALETTEN` und gelten für Oberfläche und
// Schaubild gemeinsam.

// Marke in der Kopfzeile, Weg zur Seitenleiste und Ansicht „Alle“. Die Schlüssel
// decken sich mit `KOPFSTILE`, `MENUESTILE` und `ALLESTILE` in `anordnung.py`.
export const KOPFSTILE = [
  { schluessel: "standard", titel: "Standard", hinweis: "Zeichen, Name und Hersteller", farbig: false, unterzeile: true },
  { schluessel: "schlicht", titel: "Schlicht", hinweis: "Zeichen und Name ohne Hersteller", farbig: false, unterzeile: false },
  {
    schluessel: "farbig",
    titel: "Farbig",
    hinweis: "Name in den Farben des Zeichens, Hersteller darunter",
    farbig: true,
    unterzeile: true,
  },
  {
    schluessel: "farbig_schlicht",
    titel: "Farbig schlicht",
    hinweis: "Nur der Name in den Farben des Zeichens",
    farbig: true,
    unterzeile: false,
  },
];
export const MENUESTILE = [
  { schluessel: "zeichen", titel: "Über das Zeichen", hinweis: "Ein Klick auf das Zeichen öffnet die Seitenleiste" },
  { schluessel: "taste", titel: "Eigene Menütaste", hinweis: "Eine Menütaste steht vor dem Zeichen" },
];
export const ALLESTILE = [
  { schluessel: "getrennt", titel: "Getrennt", hinweis: "Jede Anlage für sich, untereinander" },
  { schluessel: "zusammen", titel: "Zusammen", hinweis: "Gleiche Karten in einem Rahmen, ein Abschnitt je Anlage" },
];
// Strang im Schaubild und Größe je Anlagenteil. Die Schlüssel decken sich mit
// `STRANGSTILE` und `STRANGGROESSEN` in `anordnung.py`.
export const STRANGSTILE = [
  { schluessel: "umbrechen", titel: "Umbrechen", hinweis: "Was nicht in die Karte passt, steht in der nächsten Reihe" },
  { schluessel: "verkleinern", titel: "Verkleinern", hinweis: "Bei wenig Platz werden die Anlagenteile kleiner" },
];
export const STRANGGROESSEN = [
  { schluessel: "klein", titel: "Klein (80 px)", hinweis: "Jedes Anlagenteil ist 80 Pixel breit", pixel: 80 },
  { schluessel: "mittel", titel: "Mittel (120 px)", hinweis: "Jedes Anlagenteil ist 120 Pixel breit", pixel: 120 },
  { schluessel: "gross", titel: "Groß (160 px)", hinweis: "Jedes Anlagenteil ist 160 Pixel breit", pixel: 160 },
];
// Größe und Lage der Werte im Schaubild. Die Schlüssel decken sich mit
// `WERTEGROESSEN` und `WERTELAGEN` in `anordnung.py`. „Mittel“ ist das bisherige Maß.
export const WERTEGROESSEN = [
  { schluessel: "klein", titel: "Klein", hinweis: "Kleine Schrift für viele Anlagenteile", faktor: 1 },
  { schluessel: "mittel", titel: "Mittel", hinweis: "Die übliche Schrift", faktor: 1.25 },
  { schluessel: "gross", titel: "Groß", hinweis: "Große Schrift für einen Bildschirm in der Ferne", faktor: 1.5 },
];
export const WERTELAGEN = [
  { schluessel: "automatisch", titel: "Automatisch", hinweis: "Unter dem Bild, sobald ein Anlagenteil schmaler als 100 px steht" },
  { schluessel: "bild", titel: "Im Bild", hinweis: "Die Werte stehen immer in der Zeichnung" },
  { schluessel: "unter", titel: "Unter dem Bild", hinweis: "Die Werte stehen immer mit Namen unter der Zeichnung" },
];

// Wie viele Temperaturen ein Puffer im Bild zeigt. Die dritte erscheint nur, wo er einen mittleren Fühler meldet.
export const PUFFERWERTE = [
  { schluessel: "zwei", titel: "Oben und unten", hinweis: "Zwei Temperaturen, dazwischen der Ladezustand" },
  { schluessel: "drei", titel: "Oben, mitte, unten", hinweis: "Drei Temperaturen, wo der Puffer einen mittleren Fühler meldet" },
];

// Farben der Beschriftung im Schaubild: frei gewählt, als Text gespeichert. Die Werte hier
// sind der ausgelieferte Stand. Die Schlüssel decken sich mit `anordnung.py`.
export const BESCHRIFTUNG = {
  beschriftung_grund: "#0a0e13",
  beschriftung_deckkraft: "72",
  beschriftung_schrift: "#ffffff",
};

// Vorgegebene Felder im Fenster „Darstellung“. Der erste Wert ist der ausgelieferte Stand.
export const BESCHRIFTUNG_FARBEN = {
  beschriftung_grund: [
    { farbe: "#0a0e13", titel: "Schwarz" },
    { farbe: "#1f2937", titel: "Schiefer" },
    { farbe: "#0f2a43", titel: "Nachtblau" },
    { farbe: "#123524", titel: "Dunkelgrün" },
    { farbe: "#3b1d12", titel: "Braun" },
    { farbe: "#6b7280", titel: "Grau" },
    { farbe: "#e5e7eb", titel: "Hellgrau" },
    { farbe: "#ffffff", titel: "Weiß" },
  ],
  beschriftung_schrift: [
    { farbe: "#ffffff", titel: "Weiß" },
    { farbe: "#e5e7eb", titel: "Hellgrau" },
    { farbe: "#ffd166", titel: "Gelb" },
    { farbe: "#ff9f5a", titel: "Orange" },
    { farbe: "#7dd3fc", titel: "Hellblau" },
    { farbe: "#86efac", titel: "Hellgrün" },
    { farbe: "#374151", titel: "Dunkelgrau" },
    { farbe: "#0a0e13", titel: "Schwarz" },
  ],
};

const MINDESTKONTRAST = 2;
const DECKEND_AB = 50;

function helligkeit(farbe) {
  const anteile = [1, 3, 5].map((stelle) => Number.parseInt(farbe.slice(stelle, stelle + 2), 16) / 255);
  const [rot, gruen, blau] = anteile.map((wert) => (wert <= 0.03928 ? wert / 12.92 : ((wert + 0.055) / 1.055) ** 2.4));
  return 0.2126 * rot + 0.7152 * gruen + 0.0722 * blau;
}

/** Ob sich die Schrift vom Hintergrund abhebt; ein fast durchsichtiger Hintergrund zählt nicht. */
export function beschriftungLesbar(grund, schrift, deckkraft) {
  if (Number(deckkraft) < DECKEND_AB) return true;
  const [hell, dunkel] = [helligkeit(grund), helligkeit(schrift)].sort((a, b) => b - a);
  return (hell + 0.05) / (dunkel + 0.05) >= MINDESTKONTRAST;
}

/** Ob ein Wert für eine Farbe der Beschriftung taugt: `#rrggbb` oder eine Deckkraft von 0 bis 100. */
export function beschriftungGueltig(schluessel, wert) {
  const muster = schluessel === "beschriftung_deckkraft" ? /^(100|[1-9]?[0-9])$/ : /^#[0-9a-fA-F]{6}$/;
  return typeof wert === "string" && muster.test(wert);
}

// Wo der zuletzt gelesene Aufbau der Schaubild-Karte liegt. Ohne ihn steht die
// Karte beim Öffnen leer, bis die Anlagendaten über WebSocket da sind.
export const SCHAUBILD_SPEICHER = "heatnexus.schaubild";

// Unter diesem Schlüssel liegt die Linienwahl der Verlaufskarten: in den
// Nutzerdaten von Home Assistant, ohne sie im Browserspeicher.
export const LINIEN_SPEICHER = "heatnexus.verlauf_linien";

export const FARBSAETZE = [
  { schluessel: "auto", titel: "Auto", hinweis: "Folgt dem Erscheinungsbild von Home Assistant" },
  { schluessel: "dunkel", titel: "Dunkel", hinweis: "Graphit mit blauem Akzent" },
  { schluessel: "hell", titel: "Hell", hinweis: "Kühles Weiß mit blauem Akzent" },
  { schluessel: "terrakotta", titel: "Terrakotta", hinweis: "Warmes Dunkel mit Terrakotta" },
  { schluessel: "petrol", titel: "Petrol", hinweis: "Ruhiges Dunkel mit Petrolgrün" },
  { schluessel: "pflaume", titel: "Pflaume", hinweis: "Dunkles Violett mit Pflaume" },
];

// Die Einstellungen im Fenster „Darstellung“: Schlüssel am Server, dazu die
// erlaubten Werte. Der Browser merkt sich jede Wahl, weil der erste Aufbau
// vor den Einstellungen vom Server steht und sonst umspringen würde.
export const DARSTELLUNG = {
  farbsatz: FARBSAETZE,
  kopf: KOPFSTILE,
  menue: MENUESTILE,
  alle: ALLESTILE,
  strang: STRANGSTILE,
  strang_groesse: STRANGGROESSEN,
  werte_groesse: WERTEGROESSEN,
  werte_lage: WERTELAGEN,
  puffer_werte: PUFFERWERTE,
};

// Wo der Standard nicht der erste Eintrag der Liste ist.
export const DARSTELLUNG_STANDARD = { strang_groesse: "mittel", werte_groesse: "mittel" };

// Wie viele Erzeuger sich ihre Wahl „offen“ oder „zu“ merken. Muss zu
// `ERZEUGER_MAX` in `anordnung.py` passen.
export const ERZEUGER_MAX = 64;

/** Wo eine Wahl der Darstellung im Browser liegt. */
export function darstellungSpeicher(schluessel) {
  return `heatnexus.${schluessel}`;
}

// Wie groß die Marken im Schaubild stehen. Der Faktor wirkt auf die Schrift,
// nicht auf die Zeichnung – die bleibt im Maßstab der Karte.
export const SCHRIFTMASSE = [
  { schluessel: "klein", titel: "Klein", faktor: 0.85 },
  { schluessel: "normal", titel: "Normal", faktor: 1 },
  { schluessel: "gross", titel: "Groß", faktor: 1.25 },
  { schluessel: "sehr_gross", titel: "Sehr groß", faktor: 1.5 },
];

/** Der Faktor zu einem Schlüssel; unbekannte Angaben gelten als „normal". */
export function schriftmass(schluessel) {
  const treffer = SCHRIFTMASSE.find((m) => m.schluessel === schluessel);
  return treffer ? treffer.faktor : 1;
}

// Was ein fester Satz an der Oberfläche setzt. `auto` steht nicht darin: Dann
// gelten die Vorgaben aus `stil.js`, die den Variablen von Home Assistant
// folgen.
export const PALETTEN = {
  dunkel: {
    "--hn-grund": "#14171c",
    "--hn-karte": "#1e232b",
    "--hn-text": "#eceff1",
    "--hn-gedaempft": "#9aa3ad",
    "--hn-akzent": "#5b8def",
    "--hn-akzent-text": "#0e1116",
    "--hn-linie": "#262b33",
    "--hn-flaeche": "#262b33",
    "--hn-sonne": "#f5c451",
    "--hn-ww": "#5aa9e6",
    "--hn-gut": "#7bd88f",
    "--hn-at": "#4fd1b5",
  },
  hell: {
    "--hn-grund": "#f4f5f7",
    "--hn-karte": "#ffffff",
    "--hn-text": "#1c1f24",
    "--hn-gedaempft": "#6b7480",
    "--hn-akzent": "#2e6de0",
    "--hn-akzent-text": "#ffffff",
    "--hn-linie": "#e0e3e8",
    "--hn-flaeche": "#eef1f5",
    "--hn-sonne": "#b7791f",
    "--hn-ww": "#1f6fb2",
    "--hn-gut": "#2e7d32",
    "--hn-at": "#00796b",
  },
  terrakotta: {
    "--hn-grund": "#1a1816",
    "--hn-karte": "#242220",
    "--hn-text": "#ece8e4",
    "--hn-gedaempft": "#a39a90",
    "--hn-akzent": "#d98e46",
    "--hn-akzent-text": "#1a1210",
    "--hn-linie": "#2c2926",
    "--hn-flaeche": "#2c2926",
    "--hn-sonne": "#f2c14e",
    "--hn-ww": "#5aa9e6",
    "--hn-gut": "#7bd88f",
    "--hn-at": "#4fd1b5",
  },
  petrol: {
    "--hn-grund": "#10171a",
    "--hn-karte": "#192226",
    "--hn-text": "#e4ecec",
    "--hn-gedaempft": "#93a3a3",
    "--hn-akzent": "#3fa89a",
    "--hn-akzent-text": "#08120f",
    "--hn-linie": "#222d31",
    "--hn-flaeche": "#222d31",
    "--hn-sonne": "#f5c451",
    "--hn-ww": "#5aa9e6",
    "--hn-gut": "#7bd88f",
    "--hn-at": "#4fd1b5",
  },
  pflaume: {
    "--hn-grund": "#16121c",
    "--hn-karte": "#211b2a",
    "--hn-text": "#ece7f0",
    "--hn-gedaempft": "#a297ad",
    "--hn-akzent": "#a878e0",
    "--hn-akzent-text": "#150e1c",
    "--hn-linie": "#2b2336",
    "--hn-flaeche": "#2b2336",
    "--hn-sonne": "#f5c451",
    "--hn-ww": "#5aa9e6",
    "--hn-gut": "#7bd88f",
    "--hn-at": "#4fd1b5",
  },
};

/**
 * Ein Schaubild auf einen anderen Farbsatz umstellen.
 *
 * In **einem** Durchgang, nicht als Kette einzelner Ersetzungen: Sonst traefe
 * die naechste Regel eine gerade eingesetzte Farbe noch einmal. Die Tabelle
 * kommt vom Server (`schema.FARBABBILDUNGEN`), der dunkle Satz steht im Bild.
 */
export function farbenUmstellen(svg, abbildung) {
  if (!svg || !abbildung) return svg;
  const werte = Object.keys(abbildung);
  if (!werte.length) return svg;
  const stellen = new RegExp(werte.sort().reverse().join("|"), "g");
  return svg.replace(stellen, (treffer) => abbildung[treffer]);
}

/**
 * Ein Schaubild als `data:`-Adresse fuer ein `<img>`.
 *
 * Ohne Base64: Der Umweg ueber `btoa` verlangt eine eigene UTF-8-Behandlung,
 * und die Beschriftungen tragen Umlaute.
 */
export function schaubildAdresse(svg) {
  if (!svg) return null;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

// Wochentage, wie die Anlage sie schreibt, mit deutscher Beschriftung. Die
// Reihenfolge ist die der Woche - die Anlage liefert sie unsortiert.
export const WOCHENTAGE = [
  ["Mo", "Mo"],
  ["Tu", "Di"],
  ["We", "Mi"],
  ["Th", "Do"],
  ["Fr", "Fr"],
  ["Sa", "Sa"],
  ["Su", "So"],
];

// Betriebsarten des Heizkreises (`preset_mode` "0".."7"), deutsch wie in
// `translations/de.json`. Übersetzt wird über das Wörterbuch der Integration,
// nicht über Home Assistant: Das folgt der Sprache des Nutzers, nicht der Option.
export const BETRIEBSARTEN = {
  0: "Standby",
  1: "Heizprogramm 1",
  2: "Heizprogramm 2",
  3: "Heizprogramm 3",
  4: "Heizbetrieb",
  5: "Absenkbetrieb",
  6: "WW-Betrieb",
  7: "Handbetrieb",
};

// Mehr Schaltzeiten nimmt die Anlage je Block nicht an.
export const SCHALTPUNKTE_MAX = 6;

// Wie breit eine Karte höchstens werden darf, in Spalten. Deckt sich mit
// `anordnung.BREITE_MAX` auf der Serverseite – was hier durchgeht, muss dort
// gespeichert werden können.
export const BREITE_MAX = 4;

// Wie lange nach der letzten Änderung gewartet wird, bevor die Anordnung
// gespeichert wird. Beim Ziehen fallen mehrere Änderungen kurz hintereinander
// an; jede einzeln zu schreiben hieße, dieselbe Liste mehrfach abzulegen.
export const SPEICHERN_MS = 500;

/**
 * Zwei Reihenfolgen zusammenführen: `basis` gilt, `rest` füllt auf.
 *
 * Was in `basis` steht, behält seinen Platz. Alles, was nur in `rest` steht,
 * wird dort eingefügt, wo es nach `rest` hingehört – direkt hinter dem
 * nächsten Vorgänger, der bereits einen Platz hat. Hat es keinen, kommt es
 * nach vorn.
 */
export function reihenfolgeMischen(basis, rest) {
  const ergebnis = [...basis];
  (rest || []).forEach((kennung, stelle) => {
    if (ergebnis.includes(kennung)) return;
    let ziel = 0;
    for (let vorher = stelle - 1; vorher >= 0; vorher--) {
      const platz = ergebnis.indexOf(rest[vorher]);
      if (platz >= 0) {
        ziel = platz + 1;
        break;
      }
    }
    ergebnis.splice(ziel, 0, kennung);
  });
  return ergebnis;
}

/**
 * Die gespeicherte Reihenfolge auf die tatsächlich vorhandenen Karten anwenden.
 *
 * **Neue Anlagenteile dürfen die Anordnung nicht zerreißen.** Gespeichert ist
 * nur die Reihenfolge bekannter Kennungen; was neu dazukommt, landet an der
 * Stelle, an der es von Haus aus stünde, und nicht am Ende. Kennungen, die es
 * nicht mehr gibt, fallen still weg. Dieselbe Rechnung steht in
 * `anordnung.ordnung_anwenden` auf der Serverseite.
 */
export function ordnungAnwenden(standard, gespeichert) {
  const vorhanden = new Set(standard);
  return reihenfolgeMischen(
    (gespeichert || []).filter((kennung) => vorhanden.has(kennung)),
    standard
  );
}

/** Die Art einer Karte: ihre Kennung ohne Anlage davor und ohne Gerät dahinter. */
export function kartenart(kennung) {
  return kennung.slice(kennung.indexOf("|") + 1).split(":")[0];
}

/** Karten gleicher Art zusammenrücken; Arten und Karten behalten die Folge ihrer ersten Nennung. */
export function nachArtOrdnen(reihenfolge) {
  const jeArt = new Map();
  reihenfolge.forEach((kennung) => {
    const art = kartenart(kennung);
    if (!jeArt.has(art)) jeArt.set(art, []);
    jeArt.get(art).push(kennung);
  });
  return [...jeArt.values()].flat();
}

/** Einen Eintrag um einen Platz schieben; am Rand kommt dieselbe Liste zurück. */
export function schritt(liste, eintrag, richtung) {
  const stelle = liste.indexOf(eintrag);
  const ziel = stelle + richtung;
  if (stelle < 0 || ziel < 0 || ziel >= liste.length) return liste;
  const neu = [...liste];
  neu.splice(ziel, 0, neu.splice(stelle, 1)[0]);
  return neu;
}

/** Einen Eintrag vor oder hinter ein Ziel legen; fehlt das Ziel, kommt dieselbe Liste zurück. */
export function ablegen(liste, eintrag, ziel, davor) {
  const ohne = liste.filter((vorhanden) => vorhanden !== eintrag);
  const stelle = ohne.indexOf(ziel);
  if (stelle < 0) return liste;
  ohne.splice(davor ? stelle : stelle + 1, 0, eintrag);
  return ohne;
}

/** Eine nach Art geordnete Folge in ihre Gruppen zerlegen, je Art eine Liste. */
function artGruppen(reihenfolge) {
  const gruppen = [];
  let letzteArt = null;
  reihenfolge.forEach((kennung) => {
    const art = kartenart(kennung);
    if (gruppen.length && art === letzteArt) gruppen[gruppen.length - 1].push(kennung);
    else gruppen.push([kennung]);
    letzteArt = art;
  });
  return gruppen;
}

/** Eine Karte um einen Platz schieben; am Rand ihrer Gruppe wandert die ganze Gruppe. Ohne Wirkung die alte Folge. */
export function artSchritt(reihenfolge, kennung, richtung) {
  const gruppen = artGruppen(reihenfolge);
  const gruppe = gruppen.find((liste) => liste.includes(kennung));
  if (!gruppe) return reihenfolge;
  const innen = schritt(gruppe, kennung, richtung);
  const neu = innen !== gruppe ? gruppen.map((liste) => (liste === gruppe ? innen : liste)) : schritt(gruppen, gruppe, richtung);
  return neu === gruppen ? reihenfolge : neu.flat();
}

/** Eine Karte vor oder hinter eine andere legen; liegt das Ziel in einer anderen Art, wandert die ganze Gruppe. */
export function artAblegen(reihenfolge, kennung, ziel, davor) {
  const gruppen = artGruppen(reihenfolge);
  const von = gruppen.find((liste) => liste.includes(kennung));
  const nach = gruppen.find((liste) => liste.includes(ziel));
  if (!von || !nach) return reihenfolge;
  const neu =
    von === nach
      ? gruppen.map((liste) => (liste === von ? ablegen(liste, kennung, ziel, davor) : liste))
      : ablegen(gruppen, von, nach, davor);
  return neu.flat();
}

