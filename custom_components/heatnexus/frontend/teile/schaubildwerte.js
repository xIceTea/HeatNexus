/**
 * Die Zahlen im Schaubild und der Füllstand am Kessel. Unter dem Bild trägt jede Reihe
 * des Strangs eine Leiste mit einer Spalte je Anlagenteil. Eingebunden unter
 * `teile/schaubild.js`, damit Oberfläche und Karte beides haben.
 */

import { WERTEGROESSEN } from "../ordnung.js";
import { MODUL, RAND } from "./strang.js";

// Schmaler steht ein Anlagenteil, rücken seine Zahlen bei „Automatisch“ unter das Bild.
const UNTER_AB = 100;
// Das bisherige Maß der Oberfläche; es gilt, wo es keine Darstellung gibt.
const FAKTOR_STANDARD = 1.25;

export const SchaubildWerteMixin = (Basis) =>
  class extends Basis {
    /** Schriftmaß der Wertmarken nach der Darstellung. */
    _werteFaktor() {
      if (typeof this._stilwahl !== "function") return FAKTOR_STANDARD;
      const stufe = WERTEGROESSEN.find((eintrag) => eintrag.schluessel === this._stilwahl("werte_groesse"));
      return stufe ? stufe.faktor : FAKTOR_STANDARD;
    }

    /** Ob die Zahlen unter dem Bild stehen; maßgeblich ist die tatsächliche Breite eines Anlagenteils. */
    _werteUnter(massstab) {
      if (typeof this._stilwahl !== "function") return false;
      const lage = this._stilwahl("werte_lage");
      return lage === "unter" || (lage === "automatisch" && MODUL * massstab < UNTER_AB);
    }

    /** Alle Zahlen eines Bildes: die Messwerte und der Befüllgrad des Lagerraums. */
    _zahlwerte(anlage) {
      const lager = (anlage.schema_vorrat || [])
        .filter((eintrag) => eintrag.art === "lagerraum")
        .map((eintrag) => ({ ...eintrag, name: this._t("Lagerraum"), beschriftung: this._t("Lagerraum"), lagerraum: true }));
      return [...(anlage.schema_werte || []), ...lager];
    }

    /** Ohne Wert keine Zahl; der Lagerraum bleibt auch bei 0 % weg. */
    _wertDa(eintrag) {
      if (!this._hatWert(eintrag.entity)) return false;
      return !eintrag.lagerraum || (this._zahl(eintrag.entity) || 0) > 0;
    }

    /** Die Zahlen als Marken in der Zeichnung. */
    _wertmarken(huelle, anlage) {
      this._zahlwerte(anlage).forEach((eintrag) => {
        const marke = document.createElement("div");
        marke.className = eintrag.lagerraum ? "marke-wert lagerraum" : "marke-wert";
        marke.style.left = eintrag.left;
        marke.style.top = eintrag.top;
        huelle.appendChild(this._klickbar(marke, eintrag.entity));
        this._bindungen.push(() => {
          // Ohne Wert keine Marke: Ein „–" mitten im Heizkörper sah aus wie ein
          // Symbol und nicht wie ein fehlender Messwert.
          const da = this._wertDa(eintrag);
          marke.hidden = !da;
          marke.textContent = "";
          if (!da) return;
          // Am Heizkreis stehen zwei ähnliche Temperaturen übereinander; erst
          // die Beschriftung sagt, welche der Vorlauf ist und welche der Raum.
          if (eintrag.beschriftung) {
            const name = document.createElement("span");
            name.className = "marke-name";
            name.textContent = eintrag.beschriftung;
            marke.append(name, " ");
          }
          marke.append(this._text(eintrag.entity));
        });
      });
    }

    /** Die Leiste unter einer Reihe: je Anlagenteil eine Spalte, darin jede Zahl mit ihrem Namen. */
    _wertleiste(anlage, [erstes, anzahl]) {
      const leiste = document.createElement("div");
      leiste.className = "wertleiste";
      leiste.style.setProperty("--hn-schrift", String(this._schriftmass()));
      leiste.style.gridTemplateColumns = `repeat(${anzahl}, minmax(0, 1fr))`;
      const spalten = [];
      for (let nr = 0; nr < anzahl; nr += 1) spalten.push(leiste.appendChild(document.createElement("div")));
      const breite = Number(anlage.schema_breite) || 0;
      this._zahlwerte(anlage).forEach((eintrag) => {
        const teil = Math.floor(((parseFloat(eintrag.left) / 100) * breite - RAND) / MODUL);
        const spalte = spalten[teil - erstes];
        if (!spalte) return;
        const zeile = document.createElement("div");
        zeile.className = "leiste-wert";
        const name = document.createElement("span");
        name.className = "leiste-name";
        name.textContent = eintrag.name || eintrag.beschriftung || "";
        const zahl = document.createElement("span");
        zahl.className = "leiste-zahl";
        zeile.append(name, zahl);
        spalte.appendChild(this._klickbar(zeile, eintrag.entity));
        this._bindungen.push(() => {
          const da = this._wertDa(eintrag);
          zeile.hidden = !da;
          zahl.textContent = da ? this._text(eintrag.entity) : "";
        });
      });
      return leiste;
    }

    /** Die Körnung füllt den Behälter bis zur Stufe; ein Fehler zeigt ihn leer mit orangem Umriss und „!“. */
    _vorratsbehaelter(huelle, anlage) {
      (anlage.schema_vorrat || [])
        .filter((eintrag) => eintrag.art === "behaelter")
        .forEach((eintrag) => {
          const flaeche = document.createElement("div");
          flaeche.className = "vorrat";
          Object.assign(flaeche.style, { left: eintrag.left, top: eintrag.top, width: eintrag.breite, height: eintrag.hoehe });
          // Dasselbe Bild zweimal: einmal beschnittene Körnung, einmal der Umriss für den Fehler.
          ["koerner", "umriss"].forEach((ebene) => {
            const teil = document.createElement("div");
            teil.className = ebene;
            teil.innerHTML = eintrag.bild || "";
            flaeche.appendChild(teil);
          });
          huelle.appendChild(this._klickbar(flaeche, eintrag.entity));
          // Die Texte der Stufen tragen am Gerät mitunter ein Leerzeichen am Ende.
          const stufen = Object.fromEntries(Object.entries(eintrag.stufen || {}).map(([text, stufe]) => [text.trim(), stufe]));
          this._bindungen.push(() => {
            const zustand = this._zustand(eintrag.entity);
            const stufe = (zustand && stufen[String(zustand.state).trim()]) || "";
            flaeche.dataset.stufe = stufe;
            flaeche.hidden = !stufe;
            flaeche.title = `${eintrag.titel} – ${this._text(eintrag.entity)}`;
          });
        });
    }
  };
