/**
 * Reiter „Hilfe“.
 *
 * Alle Erklärungen dieser Anlage an einer Stelle, durchsuchbar. Verteilt hinter
 * den Fragezeichen der Karten sind sie schwer zu treffen, und wer nicht weiß,
 * wonach er sucht, findet den Text nicht, der seine Frage beantwortet.
 *
 * Welche Erklärungen überhaupt gelten, entscheidet die Integration; hier wird
 * nur gefiltert und gezeichnet.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import { BREITE_MAX } from "../ordnung.js";

/**
 * Einträge auf eine Suche eingrenzen.
 *
 * Gesucht wird in Titel **und** Text: Wer einen Begriff sucht, kennt die
 * Überschrift meist nicht.
 */
export function filtern(eintraege, suche) {
  const wort = (suche || "").trim().toLowerCase();
  if (!wort) return eintraege || [];
  return (eintraege || []).filter(
    (e) =>
      (e.titel || "").toLowerCase().includes(wort) ||
      (e.text || "").toLowerCase().includes(wort)
  );
}

export const HilfeMixin = (Basis) =>
  class extends Basis {
    // -------------------------------------------------------------------
    // Reiter „Hilfe"
    // -------------------------------------------------------------------
    _hilfeReiter(anlage) {
      const eintraege = anlage.hilfe_liste || [];
      if (!eintraege.length) return [{ id: "hilfe", titel: "Hilfe", knoten: null }];

      const karte = this._karte("Hilfe");

      const suchfeld = document.createElement("input");
      suchfeld.type = "search";
      suchfeld.className = "hilfe-suche";
      suchfeld.placeholder = "Suchen …";
      suchfeld.setAttribute("aria-label", "Erklärungen durchsuchen");
      karte.appendChild(suchfeld);

      const liste = document.createElement("div");
      liste.className = "hilfe-liste";
      karte.appendChild(liste);

      const zeichnen = () => {
        liste.textContent = "";
        const treffer = filtern(eintraege, suchfeld.value);
        if (!treffer.length) {
          const leer = document.createElement("p");
          leer.className = "hilfe-leer";
          leer.textContent = "Kein Eintrag passt zu dieser Suche.";
          liste.appendChild(leer);
          return;
        }
        treffer.forEach((eintrag) => {
          const block = document.createElement("details");
          block.className = "hilfe-eintrag";
          const kopf = document.createElement("summary");
          kopf.textContent = eintrag.titel;
          block.appendChild(kopf);
          const text = document.createElement("p");
          // `textContent`, nicht `innerHTML`: Die Texte tragen Aufzählungen und
          // Absätze, aber kein Markup.
          text.textContent = eintrag.text;
          block.appendChild(text);
          liste.appendChild(block);
        });
      };

      suchfeld.addEventListener("input", zeichnen);
      zeichnen();

      // Die einzige Karte ihres Reiters, und ihr Inhalt ist Fließtext. Auf
      // einer Spalte stünde sie schmal neben leerer Fläche.
      return [{ id: "hilfe", titel: "Hilfe", knoten: karte, breite: BREITE_MAX }];
    }
  };
