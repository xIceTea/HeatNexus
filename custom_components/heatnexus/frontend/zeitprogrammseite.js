/**
 * Bausteine des Reiters „Zeitprogramme“: Gruppen je Anlagenteil, Tabelle und Spur einer Tageszeile.
 *
 * Den Reiter selbst baut teile/zeitprogramme.js; hier steht, was ohne Panel prüfbar ist.
 */

import {
  TAGE,
  TAG_MINUTEN,
  farbe,
  uhrzeit,
} from "./zeitprogramm.js";

/** Reihenfolge der Gruppen in einer Karte; Programme ohne Gruppe folgen danach. */
export const GRUPPEN = ["heizen", "warmwasser", "zirkulation", "puffer"];

const OHNE = (text) => text;

/** Die Programme je Anlagenteil, in der Reihenfolge, in der die Anlage sie meldet. */
export function nachTeilen(programme) {
  const teile = new Map();
  (programme || []).forEach((programm) => {
    const schluessel = programm.teil || programm.anlagenteil || "";
    if (!teile.has(schluessel)) {
      teile.set(schluessel, { teil: schluessel, anlagenteil: programm.anlagenteil || "", programme: [] });
    }
    teile.get(schluessel).programme.push(programm);
  });
  return [...teile.values()].map((teil) => ({ ...teil, gruppen: gruppieren(teil.programme) }));
}

function raumprogramm(programme, vorlauf) {
  return programme.find(
    (programm) => programm.art === "raum" && programm.nummer === vorlauf.nummer && programm.gruppe === vorlauf.gruppe
  );
}

/**
 * Die Programme eines Anlagenteils nach Gruppen; ein Programm ohne Gruppe steht allein.
 *
 * Ein Vorlaufprogramm hängt am Raumprogramm gleicher Nummer, sofern es eines gibt.
 */
export function gruppieren(programme) {
  const liste = programme || [];
  const gruppen = new Map();
  liste.forEach((programm) => {
    if (programm.art === "vorlauf" && raumprogramm(liste, programm)) return;
    const schluessel = programm.gruppe || `allein:${programm.entity}`;
    if (!gruppen.has(schluessel)) {
      gruppen.set(schluessel, { schluessel, gruppe: programm.gruppe || null, eintraege: [] });
    }
    const vorlauf =
      programm.art === "raum"
        ? liste.find((p) => p.art === "vorlauf" && raumprogramm(liste, p) === programm) || null
        : null;
    gruppen.get(schluessel).eintraege.push({ programm, vorlauf });
  });
  const rang = (gruppe) => (gruppe.gruppe ? GRUPPEN.indexOf(gruppe.gruppe) : GRUPPEN.length);
  return [...gruppen.values()].sort((a, b) => rang(a) - rang(b));
}

// Zwischen Zahl und Einheit bricht keine Zeile.
const GESCHUETZT = " ";

function bisText(minute) {
  return minute >= TAG_MINUTEN ? "24:00" : uhrzeit(minute);
}

// „20 °C“ und „20,5 °C“: ein glatter Wert ohne „,0“.
function zahlText(wert, sprache) {
  return Number(wert).toLocaleString(sprache || undefined, { minimumFractionDigits: 0, maximumFractionDigits: 1 });
}

function temperatur(wert, sprache) {
  return `${zahlText(wert, sprache)}${GESCHUETZT}°C`;
}

/** Die Abschnitte über dem Grundwert; ein Fenster über Mitternacht wird zu einem. */
function fenster(stuecke, grund) {
  const liste = stuecke.filter((s) => s.wert !== grund).map((s) => ({ ...s }));
  const erstes = liste[0];
  const letztes = liste[liste.length - 1];
  if (liste.length > 1 && erstes.von === 0 && letztes.bis === TAG_MINUTEN && erstes.wert === letztes.wert) {
    return [...liste.slice(1, -1), { von: letztes.von, bis: erstes.bis, wert: erstes.wert }];
  }
  return liste;
}

function fensterDesTages(stuecke, grenzen) {
  if (grenzen.schalt) return fenster(stuecke.map((s) => ({ ...s, wert: s.wert >= 0.5 ? 1 : 0 })), 0);
  return fenster(stuecke, Math.min(...stuecke.map((s) => s.wert)));
}

/** Je Abschnitt die Farbe seiner Temperatur; ein Schaltprogramm färbt nur „Ein“. */
export function farben(stuecke, grenzen) {
  if (grenzen.schalt) return stuecke.map((s) => (s.wert >= 0.5 ? farbe(1, grenzen) : null));
  return stuecke.map((s) => farbe(s.wert, grenzen));
}

/**
 * Die Tabelle unter einer Tageszeile: je Fenster Stufe, Farbe, Zeit und Wert, zuletzt die übrige Zeit.
 * Zeilen: {stufe: "voll"|"halb"|null, farbe, zeit, wert}; `farbe` ist `null`, wo die Spur leer bleibt.
 */
export function tabelle(stuecke, grenzen, { t = OHNE, sprache } = {}) {
  if (!stuecke || !stuecke.length) return [{ stufe: null, zeit: t("kein Zeitplan"), wert: "" }];
  const zeit = (s) => `${uhrzeit(s.von)} – ${bisText(s.bis)}`;
  const text = (wert) => (grenzen.schalt ? t(wert >= 0.5 ? "Ein" : "Aus") : temperatur(wert, sprache));
  const werte = stuecke.map((s) => (grenzen.schalt ? (s.wert >= 0.5 ? 1 : 0) : s.wert));
  const grund = Math.min(...werte);
  const hoch = Math.max(...werte);
  const ton = (wert) => (grenzen.schalt && wert < 0.5 ? null : farbe(wert, grenzen));
  if (hoch === grund) {
    const stufe = grenzen.schalt && !hoch ? null : "voll";
    return [{ stufe, farbe: ton(grund), zeit: t("ganztags"), wert: text(grund) }];
  }
  const zeilen = fensterDesTages(stuecke, grenzen).map((s) => ({
    stufe: grenzen.schalt || s.wert === hoch ? "voll" : "halb",
    farbe: ton(s.wert),
    zeit: zeit(s),
    wert: text(s.wert),
  }));
  return [...zeilen, { stufe: null, farbe: ton(grund), zeit: t("sonst"), wert: text(grund) }];
}

/** Ob ein Tag nur einen Wert oder keinen Plan hat; dann steht eine Zeile statt Spur und Tabelle. */
export function ohneFenster(zeilen) {
  return zeilen.length === 1;
}

// Ab dieser Länge trägt ein Abschnitt seinen Wert; schmaler passt die Zahl am Handy nicht hinein.
const BESCHRIFTUNG_AB_MINUTEN = 120;

/**
 * Die Abschnitte der Spur: Farbe, Ruhewert, Beschriftung und der Text für den Tipp.
 * Nachbarn gleichen Werts werden zu einem; der niedrigste Wert eines Tages ist der Ruhewert.
 */
export function spurteile(stuecke, grenzen, { beschriften = false, t = OHNE, sprache } = {}) {
  if (!stuecke || !stuecke.length) return [];
  const wertVon = (s) => (grenzen.schalt ? (s.wert >= 0.5 ? 1 : 0) : s.wert);
  const flaechen = [];
  stuecke.forEach((stueck) => {
    const vorige = flaechen[flaechen.length - 1];
    if (vorige && vorige.wert === wertVon(stueck) && vorige.bis === stueck.von) vorige.bis = stueck.bis;
    else flaechen.push({ von: stueck.von, bis: stueck.bis, wert: wertVon(stueck) });
  });
  const grund = grenzen.schalt ? 0 : Math.min(...flaechen.map((f) => f.wert));
  const text = (wert) => (grenzen.schalt ? t(wert ? "Ein" : "Aus") : temperatur(wert, sprache));
  return flaechen.map(({ von, bis, wert }) => {
    const ruhe = wert === grund;
    const leer = grenzen.schalt && ruhe;
    const breit = bis - von >= BESCHRIFTUNG_AB_MINUTEN;
    const kurz = grenzen.schalt ? text(wert) : `${zahlText(wert, sprache)}°`;
    return {
      von,
      bis,
      ruhe,
      farbe: leer ? null : farbe(wert, grenzen),
      text: beschriften && breit && !leer ? kurz : "",
      tipp: `${uhrzeit(von)}–${bisText(bis)} · ${text(wert)}`,
    };
  });
}

/**
 * Einen Block einsetzen, ohne das Programm der Anlage anzufassen: Seine Tage verlassen die übrigen Blöcke,
 * ein Block ohne Tage fällt weg. `stelle` −1 hängt einen neuen Block an.
 */
export function blockEinsetzen(bloecke, stelle, neu) {
  const eigene = new Set(neu.tage);
  const block = { tage: TAGE.filter((tag) => eigene.has(tag)), punkte: neu.punkte.map((punkt) => ({ ...punkt })) };
  const uebrige = (bloecke || []).map((anderer, n) =>
    n === stelle ? block : { ...anderer, tage: anderer.tage.filter((tag) => !eigene.has(tag)) }
  );
  const liste = stelle < 0 ? [...uebrige, block] : uebrige;
  return liste.filter((eintrag) => eintrag.tage.length);
}

/** Die feste Achse unter einer Spur: 0, 6, 12, 18 und 24 Uhr. */
export function achseKnoten() {
  const achse = document.createElement("div");
  achse.className = "zp-achse";
  [0, 6, 12, 18, 24].forEach((stunde) => {
    const marke = document.createElement("span");
    marke.style.left = `${(stunde / 24) * 100}%`;
    marke.textContent = String(stunde);
    achse.appendChild(marke);
  });
  return achse;
}

/**
 * Eine Tagesspur im Rahmen: je Abschnitt ein Stück in der Farbe seiner Temperatur, auf Wunsch mit Wert,
 * dazu die Jetzt-Linie. Mit `tippen` zeigt ein Tipp auf ein Stück Zeit und Wert, statt die Zeile zu öffnen.
 */
export function tagesspur(stuecke, grenzen, { t = OHNE, jetzt = null, beschriften = false, tippen = false, sprache } = {}) {
  const rahmen = document.createElement("div");
  rahmen.className = "zp-rahmen";
  const spur = document.createElement("div");
  spur.className = "zp-spur";
  spurteile(stuecke, grenzen, { beschriften, t, sprache }).forEach((teil) => {
    const stueck = document.createElement("i");
    stueck.className = teil.ruhe ? "zp-stueck ruhe" : "zp-stueck";
    if (teil.farbe) stueck.style.background = teil.farbe;
    stueck.style.flexBasis = `calc(${((teil.bis - teil.von) / TAG_MINUTEN) * 100}% - 2px)`;
    stueck.textContent = teil.text;
    stueck.title = teil.tipp;
    stueck.dataset.tipp = teil.tipp;
    if (tippen) stueck.addEventListener("click", (ereignis) => tippZeigen(spur, stueck, ereignis));
    spur.appendChild(stueck);
  });
  if (Number.isFinite(jetzt)) {
    const linie = document.createElement("i");
    linie.className = "jetzt-linie";
    linie.style.left = `${(jetzt / TAG_MINUTEN) * 100}%`;
    spur.appendChild(linie);
  }
  rahmen.appendChild(spur);
  return rahmen;
}

/** Der Tipp unter einem Stück; ein zweiter Tipp auf dasselbe Stück schließt ihn. */
function tippZeigen(spur, stueck, ereignis) {
  ereignis.stopPropagation();
  const offen = spur.querySelector(".zp-tipp");
  const gleich = offen && offen.dataset.zu === stueck.dataset.tipp;
  if (offen) offen.remove();
  if (gleich) return;
  const tipp = document.createElement("span");
  tipp.className = "zp-tipp";
  tipp.textContent = stueck.dataset.tipp;
  tipp.dataset.zu = stueck.dataset.tipp;
  tipp.style.left = `${stueck.offsetLeft + stueck.offsetWidth / 2}px`;
  spur.appendChild(tipp);
}
