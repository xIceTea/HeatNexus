/**
 * Die Karte einer Wärmepumpe in der Steuerung: der Silentmode.
 *
 * Modus und Faktor schreiben direkt an die Anlage; das Zeitfenster steht als
 * Text darunter und öffnet denselben Dialog wie im Reiter „Zeitprogramme“.
 * Die Aufteilung kommt fertig aus `panel/steuerung.py`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

import { TAG_MINUTEN, abschnitte, bloeckeLesen, tagesbereich, uhrzeit, zeilenvortag } from "../zeitprogramm.js";

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
      const ein = abschnitte(block.punkte, zeilenvortag(bloecke, block.tage)).filter((stueck) => stueck.wert === 1);
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

/** Das Programm für den Dialog; Art und Bereich kommen aus der Adresse, damit er nur Ein und Aus anbietet. */
export function silentmodeProgramm(pumpe, t = (text) => text) {
  return {
    entity: pumpe.programm,
    titel: t("Zeitprogramm Silentmode"),
    bezeichnung: pumpe.programm_bezeichnung,
    art: pumpe.programm_art,
    bereich: pumpe.programm_bereich,
  };
}

export const WaermepumpeMixin = (Basis) =>
  class extends Basis {
  /** Die Karte einer Wärmepumpe mit Silentmode. */
  _waermepumpeKarte(pumpe) {
    const karte = this._karte(this._waermepumpeTitel(pumpe));
    const kopf = document.createElement("div");
    kopf.className = "status-abschnitt";
    kopf.textContent = this._t("Silentmode");
    karte.appendChild(kopf);
    karte.appendChild(this._auswahlFeld(this._t("Silentmode"), pumpe.silentmode, pumpe.silentmode_hilfe));
    if (pumpe.faktor) karte.appendChild(this._zahlFeld(this._t("Silentmode Faktor"), pumpe.faktor));
    if (pumpe.programm) this._waermepumpeZeitfenster(karte, silentmodeProgramm(pumpe, this._t.bind(this)));
    return karte;
  }

  /** Wie im Reiter Zeitprogramme: Trägt ein zweites Gerät denselben Namen, steht das Modell im Titel. */
  _waermepumpeTitel(pumpe) {
    const programm = ((this._daten && this._daten.anlagen) || [])
      .flatMap((anlage) => anlage.zeitprogramme || [])
      .find((eintrag) => eintrag.teil === pumpe.id && eintrag.geraet);
    return programm ? this._t(programm.geraet) : pumpe.titel;
  }

  /** Das Zeitfenster des Silentmode und der Weg in seinen Editor. */
  _waermepumpeZeitfenster(karte, programm) {
    const { entity } = programm;
    const text = () => {
      const zustand = this._zustand(entity);
      return zeitfensterText(bloeckeLesen(zustand && zustand.attributes.blocks), this._t.bind(this));
    };
    karte.appendChild(
      this._statuszeile(entity, this._t("Zeitfenster"), "mdi:clock-outline", { text, klick: false })
    );
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    // Ändert der Dialog die Bezeichnung, baut das Panel die Karte neu; die
    // Rückmeldung findet ihren neuen Knoten über dieses Attribut.
    rueckmeldung.dataset.programm = entity;
    const taste = this._zpTaste("Zeitfenster bearbeiten", "zp-taste", () =>
      this._zeitprogrammBearbeiten(programm, rueckmeldung)
    );
    const leiste = document.createElement("div");
    leiste.style.marginTop = "10px";
    leiste.append(taste, rueckmeldung);
    karte.appendChild(leiste);
  }
  };
