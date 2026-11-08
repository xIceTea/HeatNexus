/**
 * Die Karte einer Wärmepumpe in der Steuerung: der Silentmode.
 *
 * Modus und Faktor schreiben direkt an die Anlage; das Zeitfenster steht als
 * Text darunter und öffnet denselben Dialog wie im Reiter „Zeitprogramme“.
 * Die Aufteilung kommt fertig aus `panel/steuerung.py`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

import { TAG_MINUTEN, abschnitte, bloeckeLesen, tagesbereich, uhrzeit } from "../zeitprogramm.js";

/**
 * Die Zeitfenster, in denen ein Schaltprogramm „Ein“ steht, als Text.
 *
 * Ein Fenster über Mitternacht steht in den Abschnitten als zwei Stücke –
 * bis 24:00 und ab 00:00. Gelesen wird es als eines: „22:00–06:00“.
 */
export function zeitfensterText(bloecke, t = (text) => text) {
  const zeilen = (bloecke || [])
    .filter((block) => block.tage.length)
    .map((block) => {
      const ein = abschnitte(block.punkte).filter((stueck) => stueck.wert === 1);
      if (ein.length > 1 && ein[0].von === 0 && ein[ein.length - 1].bis === TAG_MINUTEN) {
        const erstes = ein.shift();
        ein[ein.length - 1] = { ...ein[ein.length - 1], bis: erstes.bis };
      }
      if (!ein.length) return null;
      const spannen = ein.map((stueck) =>
        stueck.von === 0 && stueck.bis === TAG_MINUTEN
          ? t("ganztägig")
          : `${uhrzeit(stueck.von)}–${uhrzeit(stueck.bis % TAG_MINUTEN)}`
      );
      return `${tagesbereich(block.tage, t)} ${spannen.join(", ")}`;
    })
    .filter(Boolean);
  return zeilen.length ? zeilen.join("; ") : t("kein Zeitfenster");
}

export const WaermepumpeMixin = (Basis) =>
  class extends Basis {
  /** Die Karte einer Wärmepumpe mit Silentmode. */
  _waermepumpeKarte(pumpe) {
    const karte = this._karte(pumpe.titel);
    const kopf = document.createElement("div");
    kopf.className = "status-abschnitt";
    kopf.textContent = this._t("Silentmode");
    karte.appendChild(kopf);
    karte.appendChild(this._auswahlFeld(this._t("Silentmode"), pumpe.silentmode, pumpe.silentmode_hilfe));
    if (pumpe.faktor) karte.appendChild(this._zahlFeld(this._t("Silentmode Faktor"), pumpe.faktor));
    if (pumpe.programm) this._waermepumpeZeitfenster(karte, pumpe.programm);
    return karte;
  }

  /** Das Zeitfenster des Silentmode und der Weg in seinen Editor. */
  _waermepumpeZeitfenster(karte, entity) {
    const text = () => {
      const zustand = this._zustand(entity);
      return zeitfensterText(bloeckeLesen(zustand && zustand.attributes.blocks), this._t.bind(this));
    };
    karte.appendChild(
      this._statuszeile(entity, this._t("Zeitfenster"), "mdi:clock-outline", { text, klick: false })
    );
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    const programm = { entity, titel: this._t("Zeitprogramm Silentmode"), art: "schalt" };
    const taste = this._zpTaste("Zeitfenster bearbeiten", "zp-taste", () =>
      this._zeitprogrammBearbeiten(programm, rueckmeldung)
    );
    const leiste = document.createElement("div");
    leiste.style.marginTop = "10px";
    leiste.append(taste, rueckmeldung);
    karte.appendChild(leiste);
  }
  };
