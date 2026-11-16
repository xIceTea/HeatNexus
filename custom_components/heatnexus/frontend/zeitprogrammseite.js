/**
 * Bausteine des Reiters „Zeitprogramme“: Gruppen je Anlagenteil, Heute-Text, Legende.
 *
 * Den Reiter selbst baut teile/zeitprogramme.js; hier steht, was ohne Panel prüfbar ist.
 */

import {
  SKALEN,
  TAGE,
  TAG_MINUTEN,
  einsetzen,
  farbe,
  naechsterWechsel,
  tagText,
  uhrzeit,
  wertJetzt,
  wertText,
} from "./zeitprogramm.js";

/** Reihenfolge der Gruppen in einer Karte; Programme ohne Gruppe folgen danach. */
export const GRUPPEN = ["heizen", "warmwasser", "zirkulation", "puffer"];

/** Gruppen mit einer Zeile im Heute-Streifen. Zirkulation fehlt: Ein/Aus sagt über den Tag wenig. */
export const HEUTE_GRUPPEN = new Set(["heizen", "warmwasser", "puffer"]);

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

/** „jetzt 21 °C · ab 22:00 16 °C“; ein Wechsel an einem späteren Tag nennt den Wochentag. */
export function heuteText(bloecke, zeit, grenzen, t = OHNE) {
  const jetzt = wertJetzt(bloecke, zeit);
  if (jetzt === null) return t("heute kein Zeitplan");
  const teile = [einsetzen(t("jetzt {wert}"), { wert: wertText(jetzt, grenzen, t) })];
  const wechsel = naechsterWechsel(bloecke, zeit);
  if (wechsel) {
    const um = uhrzeit(wechsel.minute);
    const wann = wechsel.tage ? `${tagText(wechsel.tag, t)} ${um}` : um;
    teile.push(einsetzen(t("ab {zeit} {wert}"), { zeit: wann, wert: wertText(wechsel.wert, grenzen, t) }));
  }
  return teile.join(" · ");
}

// Zwischen Zahl und Einheit bricht keine Zeile.
const GESCHUETZT = " ";

function bisText(minute) {
  return minute >= TAG_MINUTEN ? "24:00" : uhrzeit(minute);
}

function temperatur(wert, sprache) {
  const zahl = Number(wert).toLocaleString(sprache || undefined, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return `${zahl}${GESCHUETZT}°C`;
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

// Zeitmarken an der Spur brauchen Abstand; auf dem Handy entspricht das etwa ihrer Breite.
const MARKEN_ABSTAND_MINUTEN = 150;

function fensterDesTages(stuecke, grenzen) {
  if (grenzen.schalt) return fenster(stuecke.map((s) => ({ ...s, wert: s.wert >= 0.5 ? 1 : 0 })), 0);
  return fenster(stuecke, Math.min(...stuecke.map((s) => s.wert)));
}

/**
 * Die Tabelle unter einer Tageszeile: je Fenster Stufe, Zeit und Wert, zuletzt die übrige Zeit.
 * Zeilen: {stufe: "voll"|"halb"|null, zeit, wert}.
 */
export function tabelle(stuecke, grenzen, { t = OHNE, sprache } = {}) {
  if (!stuecke || !stuecke.length) return [{ stufe: null, zeit: t("kein Zeitplan"), wert: "" }];
  const zeit = (s) => `${uhrzeit(s.von)} – ${bisText(s.bis)}`;
  const text = (wert) => (grenzen.schalt ? t(wert >= 0.5 ? "Ein" : "Aus") : temperatur(wert, sprache));
  const werte = stuecke.map((s) => (grenzen.schalt ? (s.wert >= 0.5 ? 1 : 0) : s.wert));
  const grund = Math.min(...werte);
  const hoch = Math.max(...werte);
  if (hoch === grund) return [{ stufe: grenzen.schalt && !hoch ? null : "voll", zeit: t("ganztags"), wert: text(grund) }];
  const zeilen = fensterDesTages(stuecke, grenzen).map((s) => ({
    stufe: grenzen.schalt || s.wert === hoch ? "voll" : "halb",
    zeit: zeit(s),
    wert: text(s.wert),
  }));
  return [...zeilen, { stufe: null, zeit: t("übrige Zeit"), wert: text(grund) }];
}

/** Die Uhrzeiten, an denen ein Fenster beginnt oder endet; zu dichte fallen weg, die Tabelle nennt sie. */
export function zeitmarken(stuecke, grenzen) {
  if (!stuecke || !stuecke.length) return [];
  const grenzpunkte = fensterDesTages(stuecke, grenzen)
    .flatMap((s) => [s.von, s.bis])
    .filter((minute) => minute > 0 && minute < TAG_MINUTEN);
  const marken = [];
  [...new Set(grenzpunkte)]
    .sort((a, b) => a - b)
    .forEach((minute) => {
      if (!marken.length || minute - marken[marken.length - 1] >= MARKEN_ABSTAND_MINUTEN) marken.push(minute);
    });
  return marken;
}

/** Je Abschnitt die Füllung der Spur: der höchste Wert „voll“, Zwischenwerte „halb“, der Grundwert leer. */
export function stufen(stuecke, grenzen) {
  if (grenzen.schalt) return stuecke.map((s) => (s.wert >= 0.5 ? "voll" : null));
  const werte = stuecke.map((s) => s.wert);
  const grund = Math.min(...werte);
  const hoch = Math.max(...werte);
  if (hoch === grund) return stuecke.map(() => "voll");
  return stuecke.map((s) => (s.wert === grund ? null : s.wert === hoch ? "voll" : "halb"));
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

/** Eine Tagesspur in einer Farbe: Füllung nach Stufe, Stundenstriche, auf Wunsch die Jetzt-Linie. */
export function tagesspur(stuecke, grenzen, { t = OHNE, jetzt = null } = {}) {
  const spur = document.createElement("div");
  spur.className = "zp-spur";
  [6, 12, 18].forEach((stunde) => {
    const strich = document.createElement("i");
    strich.className = "zp-stunde";
    strich.style.left = `${(stunde / 24) * 100}%`;
    spur.appendChild(strich);
  });
  const stufe = stufen(stuecke, grenzen);
  // Nachbarn gleicher Stufe und gleichen Werts als eine Füllung, sonst stünde eine Fuge darin.
  const flaechen = [];
  stuecke.forEach((stueck, n) => {
    const vorige = flaechen[flaechen.length - 1];
    if (vorige && vorige.stufe === stufe[n] && vorige.wert === stueck.wert && vorige.bis === stueck.von) {
      vorige.bis = stueck.bis;
    } else {
      flaechen.push({ ...stueck, stufe: stufe[n] });
    }
  });
  flaechen.forEach((stueck) => {
    if (!stueck.stufe) return;
    const fuellung = document.createElement("i");
    fuellung.className = `zp-fuellung ${stueck.stufe}`;
    fuellung.style.left = `${(stueck.von / TAG_MINUTEN) * 100}%`;
    fuellung.style.width = `${((stueck.bis - stueck.von) / TAG_MINUTEN) * 100}%`;
    fuellung.title = `${uhrzeit(stueck.von)}–${bisText(stueck.bis)} · ${wertText(stueck.wert, grenzen, t)}`;
    spur.appendChild(fuellung);
  });
  if (Number.isFinite(jetzt)) {
    const linie = document.createElement("i");
    linie.className = "jetzt-linie";
    linie.style.left = `${(jetzt / TAG_MINUTEN) * 100}%`;
    spur.appendChild(linie);
  }
  return spur;
}

/** Die Legende der Skalen, die auf der Seite vorkommen: Raum, Wasser, Ein. */
export function legendeKnoten(arten, t = OHNE) {
  const knoten = document.createElement("div");
  knoten.className = "zp-legende";
  [
    ["raum", "Raum"],
    ["wasser", "Wasser"],
  ]
    .filter(([art]) => arten.has(art))
    .forEach(([art, name]) => {
      const grenzen = { ...SKALEN[art], schalt: false };
      const verlauf = document.createElement("i");
      verlauf.className = "zp-verlauf";
      verlauf.style.background = `linear-gradient(to right, ${farbe(grenzen.min, grenzen)}, ${farbe(
        grenzen.max,
        grenzen
      )})`;
      knoten.appendChild(legendeEintrag(t(name), `${grenzen.min} °C`, verlauf, `${grenzen.max} °C`));
    });
  if (arten.has("schalt")) {
    const ein = document.createElement("i");
    ein.className = "zp-ein";
    ein.style.background = farbe(1, { schalt: true });
    knoten.appendChild(legendeEintrag(t("Ein"), ein));
  }
  return knoten;
}

function legendeEintrag(...teile) {
  const eintrag = document.createElement("span");
  eintrag.className = "zp-legende-eintrag";
  teile.forEach((teil) => {
    if (typeof teil !== "string") {
      eintrag.appendChild(teil);
      return;
    }
    const text = document.createElement("span");
    text.textContent = teil;
    eintrag.appendChild(text);
  });
  return eintrag;
}
