/**
 * „Alle“ als ein Raster: Gleiche Karten aller Anlagen verschmelzen zu einer, ein Abschnitt je Anlage.
 * Mixin von `heatnexus-panel.js`; gewählt wird unter „Darstellung“.
 */

export const GemeinsamMixin = (Basis) =>
  class extends Basis {
    /** Die Fläche unter „Alle“, wenn sie alle Anlagen zusammen zeigt; sonst `null`. */
    _gemeinsameFlaeche() {
      if (this._reiter === "automatik") return this._automatikAlle();
      if (this._reiter === "befund") return this._befundAlle();
      if (this._reiter === "hilfe") return this._hilfeAlle();
      if (this._alleStil() !== "zusammen") return null;
      let leer = "";
      const teile = this._anlagen().flatMap((anlage) =>
        this._kartenInSprache(anlage, (sicht) => {
          const gebaut = sicht._reiterKarten(anlage);
          leer = gebaut.leer;
          return gebaut.karten;
        }).map((karte) => ({
          ...karte,
          id: this._kartenVorwahl(anlage) + karte.id,
          basis: karte.id,
          anlage: anlage.name || "",
        }))
      );
      // Das „?“ einer verschmolzenen Karte erklärt in der Sprache der Oberfläche.
      const eigene = this._anlagen().find((anlage) => this._sicht(anlage) === this);
      this._hilfe = (eigene && eigene.hilfe) || {};
      return this._raster(null, this._kartenVerschmelzen(teile), leer, { nachArt: true });
    }

    /** Karten mit gleicher Kennung aus mehreren Anlagen werden eine; eine einzelne trägt ihre Anlage im Titel. */
    _kartenVerschmelzen(teile) {
      const jeKennung = new Map();
      teile.forEach((teil) => {
        if (!jeKennung.has(teil.basis)) jeKennung.set(teil.basis, []);
        jeKennung.get(teil.basis).push(teil);
      });
      return [...jeKennung.values()].map((gleiche) => {
        const [erste] = gleiche;
        if (gleiche.length === 1) {
          if (erste.anlage) this._anlageMarkieren(erste.knoten, erste.anlage);
          return { ...erste, titel: [erste.anlage, this._t(erste.titel || "")].filter(Boolean).join(" · ") };
        }
        const karte = this._karte(erste.titel);
        karte.classList.add("verschmolzen");
        gleiche.forEach((teil) => {
          if (teil.anlage) this._anlageMarkieren(teil.knoten, teil.anlage, true);
          teil.knoten.classList.add("eingebettet");
          karte.appendChild(teil.knoten);
        });
        const breite = Math.max(...gleiche.map((teil) => teil.breite || 1));
        return { id: this._kartenVorwahl({ id: "alle" }) + erste.basis, titel: erste.titel, knoten: karte, breite };
      });
    }

    /** Der Name der Anlage vor dem Kartentitel oder an seiner Stelle; ohne Titel oben in der Karte. */
    _anlageMarkieren(knoten, name, anStelle = false) {
      const marke = document.createElement("span");
      marke.className = "karten-anlage";
      marke.dataset.roh = "";
      marke.textContent = name;
      const titel = knoten.querySelector("h2");
      if (!titel || !titel.parentElement) {
        knoten.prepend(marke);
        return;
      }
      titel.parentElement.insertBefore(marke, titel);
      if (!anStelle) return;
      // Titel und Erklärung stehen einmal im gemeinsamen Kopf; die „?“ an den Feldern bleiben.
      const erklaerung = [...titel.parentElement.children].find((kind) => kind.classList.contains("fragezeichen"));
      if (erklaerung) erklaerung.remove();
      titel.remove();
    }
  };
