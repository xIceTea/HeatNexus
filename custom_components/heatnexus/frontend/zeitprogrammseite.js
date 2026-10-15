/**
 * Bausteine des Reiters „Zeitprogramme“: Gruppen je Anlagenteil, Heute-Text, Legende.
 *
 * Den Reiter selbst baut teile/zeitprogramme.js; hier steht, was ohne Panel prüfbar ist.
 */

import {
  SKALEN,
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
