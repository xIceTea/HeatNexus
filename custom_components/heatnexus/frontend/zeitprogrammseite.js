/**
 * Bausteine des Reiters „Zeitprogramme“: Gruppen je Anlagenteil, Tabelle und Spur einer Tageszeile.
 *
 * Den Reiter selbst baut teile/zeitprogramme.js; hier steht, was ohne Panel prüfbar ist.
 */

import {
  TAGE,
  TAG_MINUTEN,
  farbe,
  tagesbereich,
  tarifText,
  uhrzeit,
  vortagText,
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
      teile.set(schluessel, {
        teil: schluessel,
        anlagenteil: programm.anlagenteil || "",
        geraet: programm.geraet || "",
        programme: [],
      });
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

/**
 * Reiterbeschriftungen ohne die Wörter, mit denen alle Namen beginnen; diese stehen als `vorsatz` darüber.
 * Bliebe einem Namen nichts Eigenes, bleiben alle ganz.
 */
export function reiterNamen(namen) {
  const liste = [...(namen || [])];
  const woerter = liste.map((name) => String(name).trim().split(/\s+/));
  let gemeinsam = 0;
  const weiter = () =>
    woerter.every((worte) => worte.length > gemeinsam + 1 && worte[gemeinsam] === woerter[0][gemeinsam]);
  while (woerter.length > 1 && weiter()) gemeinsam += 1;
  if (!gemeinsam) return { vorsatz: "", namen: liste };
  const gross = (text) => text.charAt(0).toLocaleUpperCase() + text.slice(1);
  return {
    vorsatz: woerter[0].slice(0, gemeinsam).join(" "),
    namen: woerter.map((worte) => gross(worte.slice(gemeinsam).join(" "))),
  };
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

/** Das Stromtarifprogramm lässt sich nur ansehen; der Dienst schreibt keine Tarife. */
export function nurLesen(programm) {
  return !!programm && programm.art === "tarif";
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
  if (!stuecke || !stuecke.length) return [{ stufe: null, zeit: t("Kein Zeitplan"), wert: "" }];
  const zeit = (s) => `${uhrzeit(s.von)} – ${bisText(s.bis)}`;
  const text = (wert) =>
    grenzen.tarif ? tarifText(wert, t) : grenzen.schalt ? t(wert >= 0.5 ? "Ein" : "Aus") : temperatur(wert, sprache);
  // Ein Stück je nach Vortag steht vorn für sich; die Fenster ergeben sich aus den übrigen.
  const vorn = stuecke
    .filter((s) => s.jeNachVortag)
    .map((s) => ({ stufe: null, farbe: null, zeit: zeit(s), wert: t("je nach Vortag") }));
  const feste = stuecke.filter((s) => !s.jeNachVortag);
  const werte = feste.map((s) => (grenzen.schalt ? (s.wert >= 0.5 ? 1 : 0) : s.wert));
  const grund = Math.min(...werte);
  const hoch = Math.max(...werte);
  const ton = (wert) => (grenzen.schalt && wert < 0.5 ? null : farbe(wert, grenzen));
  if (hoch === grund) {
    const stufe = grenzen.schalt && !hoch ? null : "voll";
    const wann = vorn.length ? zeit({ von: feste[0].von, bis: TAG_MINUTEN }) : t("ganztags");
    return [...vorn, { stufe, farbe: ton(grund), zeit: wann, wert: text(grund) }];
  }
  const zeilen = fensterDesTages(feste, grenzen).map((s) => ({
    stufe: grenzen.schalt || s.wert === hoch ? "voll" : "halb",
    farbe: ton(s.wert),
    zeit: zeit(s),
    wert: text(s.wert),
  }));
  return [...vorn, ...zeilen, { stufe: null, farbe: ton(grund), zeit: t("Übrige Zeit"), wert: text(grund) }];
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
    const offen = stueck.jeNachVortag || null;
    const anschluss = vorige && !vorige.offen && !offen && vorige.bis === stueck.von;
    if (anschluss && vorige.wert === wertVon(stueck)) vorige.bis = stueck.bis;
    else flaechen.push({ von: stueck.von, bis: stueck.bis, wert: wertVon(stueck), offen });
  });
  const grund = grenzen.schalt ? 0 : Math.min(...flaechen.filter((f) => !f.offen).map((f) => f.wert));
  // Ein Tag nur mit Aus wäre sonst eine leere Fläche; er trägt das Wort.
  const ganzAus = grenzen.schalt && flaechen.length === 1 && flaechen[0].wert === 0;
  const text = (wert) =>
    grenzen.tarif ? tarifText(wert, t) : grenzen.schalt ? t(wert ? "Ein" : "Aus") : temperatur(wert, sprache);
  return flaechen.map(({ von, bis, wert, offen }) => {
    // Ohne einzelnen Wert bleibt das Stück ohne Farbe; der Tipp nennt die Werte je Tag.
    if (offen) {
      return { von, bis, ruhe: false, farbe: null, text: "", tipp: `${uhrzeit(von)}–${bisText(bis)} · ${vortagText(offen, text, t)}` };
    }
    const ruhe = wert === grund;
    const leer = grenzen.schalt && ruhe;
    const breit = bis - von >= BESCHRIFTUNG_AB_MINUTEN;
    const kurz = grenzen.schalt || grenzen.tarif ? text(wert) : `${zahlText(wert, sprache)}°`;
    return {
      von,
      bis,
      ruhe,
      farbe: leer ? null : farbe(wert, grenzen),
      text: ganzAus ? text(wert) : beschriften && breit && !leer ? kurz : "",
      tipp: `${uhrzeit(von)}–${bisText(bis)} · ${text(wert)}`,
    };
  });
}

const gleichePunkte = (eine, andere) =>
  eine.length === andere.length && eine.every((punkt, n) => punkt.zeit === andere[n].zeit && punkt.wert === andere[n].wert);

// Gleiche Schaltzeiten, aber ein anderer Wert vom Vortag ergeben einen anderen Morgen; je nach Vortag passt keiner.
const gleicherMorgen = (eine, andere) => {
  const [erstes, zweites] = [eine[0] || {}, andere[0] || {}];
  return !erstes.jeNachVortag && !zweites.jeNachVortag && erstes.wert === zweites.wert;
};

const grenzenAn = (eine, andere) =>
  eine.some((tag) => andere.some((nachbar) => Math.abs(TAGE.indexOf(tag) - TAGE.indexOf(nachbar)) === 1));

/**
 * Zeilen mit gleichen Schaltzeiten und aneinandergrenzenden Tagen in einer Zeile: Fünf gleiche Werktage stehen als „Mo–Fr“.
 * Die Zeile behält die Stelle ihres ersten Blocks; gespeichert wird ein Block für alle ihre Tage.
 */
export function nachbarnZusammenfassen(zeilen, t = OHNE) {
  const liste = (zeilen || []).map((zeile) => ({ ...zeile, tage: [...zeile.tage] }));
  for (let n = 0; n < liste.length; n += 1) {
    for (let m = n + 1; m < liste.length; m += 1) {
      const [eine, andere] = [liste[n], liste[m]];
      const passt =
        eine.stelle >= 0 &&
        andere.stelle >= 0 &&
        gleichePunkte(eine.punkte, andere.punkte) &&
        gleicherMorgen(eine.abschnitte || [], andere.abschnitte || []);
      if (!passt || !grenzenAn(eine.tage, andere.tage)) continue;
      eine.tage = TAGE.filter((tag) => eine.tage.includes(tag) || andere.tage.includes(tag));
      eine.text = tagesbereich(eine.tage, t);
      liste.splice(m, 1);
      // Die Zeile ist gewachsen; eine schon geprüfte kann jetzt an sie grenzen.
      m = n;
    }
  }
  return liste;
}

/** Ob zwei Programme an jedem Wochentag dieselben Schaltzeiten haben, gleich wie sie in Blöcke geteilt sind. */
export function tageGleich(einer, anderer) {
  const plan = (bloecke, tag) => {
    const block = (bloecke || []).find((eintrag) => eintrag.tage.includes(tag));
    if (!block) return "";
    const sortiert = [...block.punkte].sort((a, b) => a.zeit - b.zeit);
    return JSON.stringify(sortiert.map((punkt) => [punkt.zeit, Math.round(punkt.wert * 10) / 10]));
  };
  return TAGE.every((tag) => plan(einer, tag) === plan(anderer, tag));
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
  // Die Stundenmarken ordnen nur das Bild; vorgelesen werden Zeiten aus Tabelle und Tipp.
  achse.setAttribute("aria-hidden", "true");
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
    if (teil.farbe) stueck.style.setProperty("--zp-ton", teil.farbe);
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

// Höchstens ein Tipp ist offen; Antippen daneben oder Escape schließt ihn.
let offenerTipp = null;

function tippSchliessen() {
  if (!offenerTipp) return;
  offenerTipp.halt.abort();
  offenerTipp.knoten.remove();
  offenerTipp = null;
}

/** Die Mitte des Tipps über seinem Stück, so weit verschoben, dass er ganz in der Spur bleibt. */
function tippMitte(spur, stueck, tipp) {
  const mitte = stueck.offsetLeft + stueck.offsetWidth / 2;
  const halb = tipp.offsetWidth / 2;
  const breite = spur.clientWidth;
  if (!breite || !halb) return mitte;
  if (halb * 2 >= breite) return breite / 2;
  return Math.min(breite - halb, Math.max(halb, mitte));
}

/** Der Tipp unter einem Stück; ein zweiter Tipp auf dasselbe Stück schließt ihn. */
function tippZeigen(spur, stueck, ereignis) {
  ereignis.stopPropagation();
  const offen = offenerTipp && offenerTipp.knoten;
  const gleich = offen && offen.parentElement === spur && offen.dataset.zu === stueck.dataset.tipp;
  tippSchliessen();
  if (gleich) return;
  const tipp = document.createElement("span");
  tipp.className = "zp-tipp";
  tipp.textContent = stueck.dataset.tipp;
  tipp.dataset.zu = stueck.dataset.tipp;
  spur.appendChild(tipp);
  tipp.style.left = `${tippMitte(spur, stueck, tipp)}px`;
  // Ein Klick auf ein Stück endet dort; was am Dokument ankommt, lag daneben.
  const halt = new AbortController();
  offenerTipp = { knoten: tipp, halt };
  document.addEventListener("click", tippSchliessen, { signal: halt.signal });
  document.addEventListener("keydown", (taste) => taste.key === "Escape" && tippSchliessen(), { signal: halt.signal });
}
