/**
 * Reiter „Zeitprogramme“.
 *
 * Je Programm ein Wochenraster und ein Editor. Gerechnet wird in
 * `../zeitprogramm.js`; hier steht nur, was daraus auf den Bildschirm kommt.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import {
  bereich,
  bloeckeLesen,
  editorKnoten,
  gleich,
  nachDienst,
  pruefen,
  rasterKnoten,
} from "../zeitprogramm.js";

export const ZeitprogrammeMixin = (Basis) =>
  class extends Basis {
  // -------------------------------------------------------------------
  // Reiter „Zeitprogramme"
  // -------------------------------------------------------------------
  /**
   * Je Zeitprogramm eine Karte mit Wochenraster.
   *
   * Welche Entitäten in Frage kommen, entscheidet die Integration am Namen;
   * ob es wirklich ein Zeitprogramm ist, steht erst im Zustand. Nur Entitäten
   * mit `blocks` bekommen eine Karte – so fällt ein Sensor, der zufällig
   * „Programm" heißt, von selbst heraus, ohne dass die Liste im Server dafür
   * jeden Sonderfall kennen müsste.
   */
  _zeitprogrammeReiter(anlage) {
    return (anlage.zeitprogramme || []).map((programm) => ({
      id: `zeitprogramm:${programm.entity}`,
      titel: programm.titel,
      knoten: this._zeitprogrammKarte(programm),
      breite: 2,
    }));
  }

  _zeitprogrammKarte(programm) {
    const zustand = this._zustand(programm.entity);
    const bloecke = bloeckeLesen(zustand && zustand.attributes && zustand.attributes.blocks);
    if (!bloecke.length) return null;

    const karte = this._karte(programm.titel, programm.hilfe);
    if (programm.anlagenteil) {
      const unter = document.createElement("div");
      unter.className = "zp-anlagenteil";
      unter.textContent = programm.anlagenteil;
      karte.appendChild(unter);
    }

    const platz = document.createElement("div");
    platz.appendChild(rasterKnoten(bloecke));
    karte.appendChild(platz);

    // Ein Programm, das gerade nichts bewirkt, wird nicht versteckt, sondern
    // beschriftet: Das Zirkulationsprogramm lässt sich vorbereiten, bevor die
    // Pumpe auf „Mit Zeitsteuerung" gestellt wird.
    if (programm.wirkung) {
      const hinweis = document.createElement("div");
      hinweis.className = "zp-wirkung";
      hinweis.textContent = programm.wirkung.hinweis;
      karte.appendChild(hinweis);
      this._bindungen.push(() => {
        const zustand = this._zustand(programm.wirkung.entity);
        const text = zustand ? String(zustand.state).toLowerCase() : "";
        hinweis.hidden = text.includes(programm.wirkung.muster);
      });
    }

    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";

    const leiste = document.createElement("div");
    leiste.className = "zp-karteleiste";
    const bearbeiten = document.createElement("button");
    bearbeiten.type = "button";
    bearbeiten.className = "zp-taste betont";
    bearbeiten.textContent = "Bearbeiten";
    bearbeiten.addEventListener("click", () => this._zeitprogrammBearbeiten(programm, rueckmeldung));
    leiste.append(bearbeiten, rueckmeldung);
    karte.appendChild(leiste);

    // Das Raster hängt am Zustand: Wird das Programm an der Anlage selbst
    // geändert, steht hier sonst der Stand vom Öffnen.
    this._bindungen.push(() => {
      const jetzt = this._zustand(programm.entity);
      const neu = bloeckeLesen(jetzt && jetzt.attributes && jetzt.attributes.blocks);
      if (!neu.length || gleich(neu, this._zeitprogrammStand.get(programm.entity))) return;
      this._zeitprogrammStand.set(programm.entity, neu);
      platz.replaceChildren(rasterKnoten(neu));
    });
    this._zeitprogrammStand.set(programm.entity, bloecke);

    return karte;
  }

  /**
   * Der Editor als Dialog – dieselbe Form wie Rückfrage und Erklärung.
   *
   * Geschrieben wird erst beim Speichern, und dann das **ganze** Programm:
   * Die Anlage kennt keinen Weg, einen einzelnen Schaltpunkt zu ändern.
   * `heatnexus.set_time_program` liest das Objekt vorher und tauscht nur den
   * Wert aus, damit der Umschlag des Geräts erhalten bleibt.
   */
  _zeitprogrammBearbeiten(programm, rueckmeldung) {
    const zustand = this._zustand(programm.entity);
    const bloecke = bloeckeLesen(zustand && zustand.attributes && zustand.attributes.blocks);
    if (!bloecke.length) return;

    const schleier = document.createElement("div");
    schleier.className = "schleier";
    const dialog = document.createElement("div");
    dialog.className = "dialog zp-dialog";
    dialog.setAttribute("role", "dialog");

    const ueberschrift = document.createElement("h3");
    ueberschrift.className = "dialog-titel";
    ueberschrift.textContent = programm.titel;

    const editor = editorKnoten(bloecke, { grenzen: bereich(bloecke) });

    const meldung = document.createElement("div");
    meldung.className = "zp-meldung";

    const leiste = document.createElement("div");
    leiste.className = "dialog-leiste";
    const abbrechen = document.createElement("button");
    abbrechen.type = "button";
    abbrechen.className = "dialog-taste";
    abbrechen.textContent = "Abbrechen";
    const speichern = document.createElement("button");
    speichern.type = "button";
    speichern.className = "dialog-taste betont";
    speichern.textContent = "Speichern";
    leiste.append(abbrechen, speichern);

    dialog.append(ueberschrift, editor.knoten, meldung, leiste);
    schleier.appendChild(dialog);

    const weg = () => {
      schleier.remove();
      document.removeEventListener("keydown", beiTaste);
    };
    const beiTaste = (ereignis) => {
      if (ereignis.key === "Escape") weg();
    };
    abbrechen.addEventListener("click", weg);
    schleier.addEventListener("click", (ereignis) => {
      if (ereignis.target === schleier) weg();
    });
    document.addEventListener("keydown", beiTaste);

    speichern.addEventListener("click", async () => {
      const neu = editor.lesen();
      const fehler = pruefen(neu);
      if (fehler.length) {
        meldung.className = "zp-meldung fehler";
        meldung.textContent = fehler.join(" ");
        return;
      }
      meldung.textContent = "";
      weg();
      await this._uebertragen(
        rueckmeldung,
        () =>
          this._hass.callService("heatnexus", "set_time_program", {
            entity_id: programm.entity,
            blocks: nachDienst(neu),
          }),
        // Übernommen ist es erst, wenn die Anlage dasselbe zurückmeldet.
        () => {
          const jetzt = this._zustand(programm.entity);
          const gemeldet = bloeckeLesen(jetzt && jetzt.attributes && jetzt.attributes.blocks);
          return gleich(gemeldet, neu);
        },
        programm.entity
      );
      this._nachfassen({ entity: programm.entity });
    });

    this.shadowRoot.appendChild(schleier);
    speichern.focus();
  }
  };
