/**
 * Aufteilung des Strangs im Schaubild auf Reihen; reine Rechnung ohne DOM.
 * Die Maße stimmen mit `schema/zeichnung.py` überein.
 */

export const RAND = 24;
export const MODUL = 200;
export const HOEHE = 392;

// Der Name eines Anlagenteils in der Zeichnung, siehe `_kasten` in `schema/zeichnung.py`.
const NAME = /<text data-teil="(\d+)"[^>]*>[^<]*<\/text>/g;

/** Die Zeichnung ohne die Namen; sie stehen im Strang ungeschnitten darüber. */
export function ohneNamen(svg) {
  return svg.replace(NAME, "");
}

/** Dasselbe Bildformat, aber nur mit den Namen der Teile `erstes` bis `erstes + anzahl - 1`. */
export function nurNamen(svg, erstes, anzahl) {
  const kopf = svg.slice(0, svg.indexOf(">") + 1);
  const namen = [...svg.matchAll(NAME)].filter(([, teil]) => Number(teil) >= erstes && Number(teil) < erstes + anzahl);
  return `${kopf}${namen.map(([text]) => text).join("")}</svg>`;
}

/** Zu welchem Anlagenteil eine Lage in Prozent der Zeichnungsbreite gehört. */
export function teilAn(links, breite) {
  return Math.floor(((parseFloat(links) / 100) * breite - RAND) / MODUL);
}

/** Wie viele Anlagenteile eine Zeichnung dieser Breite trägt; sie ist nie schmaler als 400. */
export function teileAus(breite) {
  return Math.max(1, Math.floor((breite - 2 * RAND) / MODUL));
}

/**
 * Maßstab und Reihen `[erstes, anzahl]`. `groesse` ist die Breite eines Teils in Pixeln.
 * Umbrechen hält die Größe und verteilt die Teile gleichmäßig auf möglichst wenige Reihen.
 * `verfuegbar` muss größer als 0 sein; ohne Breite plant der Aufrufer nicht.
 */
export function reihenPlanen({ teile, breite, verfuegbar, modus, groesse }) {
  if (modus === "verkleinern") {
    return { massstab: verfuegbar / breite, reihen: [[0, teile]] };
  }
  let massstab = groesse / MODUL;
  if (verfuegbar >= breite * massstab) {
    return { massstab, reihen: [[0, teile]] };
  }
  let jeReihe = Math.floor((verfuegbar - 2 * RAND * massstab) / (MODUL * massstab));
  if (jeReihe < 1) {
    jeReihe = 1;
    massstab = verfuegbar / (MODUL + 2 * RAND);
  }
  // Die ersten Reihen nehmen den Rest auf, damit keine Reihe mehr als ein Teil kürzer ist.
  const anzahl = Math.ceil(teile / jeReihe);
  const grund = Math.floor(teile / anzahl);
  const reihen = [];
  let erstes = 0;
  for (let i = 0; i < anzahl; i += 1) {
    const laenge = grund + (i < teile % anzahl ? 1 : 0);
    reihen.push([erstes, laenge]);
    erstes += laenge;
  }
  return { massstab, reihen };
}
