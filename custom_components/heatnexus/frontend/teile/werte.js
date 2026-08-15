/**
 * Zustände lesen: Text, Zahl, Name, und ob etwas läuft.
 *
 * Kein Wissen über die Anlage, nur über `hass.states`. Deshalb eigene Datei –
 * Oberfläche und Lovelace-Karte brauchen dieselben Griffe.
 */

import { OHNE_WERT } from "../ordnung.js";

export const WerteMixin = (Basis) =>
  class extends Basis {
    _zustand(entity) {
      return this._hass && this._hass.states ? this._hass.states[entity] : undefined;
    }

    _hatWert(entity) {
      const zustand = this._zustand(entity);
      return !!zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase());
    }

    _text(entity) {
      const zustand = this._zustand(entity);
      if (!this._hatWert(entity)) return "–";
      if (this._hass.formatEntityState) return this._hass.formatEntityState(zustand);
      const einheit = zustand.attributes.unit_of_measurement;
      return einheit ? `${zustand.state} ${einheit}` : zustand.state;
    }

    _zahl(entity) {
      const zustand = this._zustand(entity);
      if (!this._hatWert(entity)) return null;
      const wert = Number.parseFloat(zustand.state);
      return Number.isNaN(wert) ? null : wert;
    }

    _name(entity) {
      const zustand = this._zustand(entity);
      return (zustand && zustand.attributes.friendly_name) || entity;
    }

    _istAn(entity) {
      const zustand = this._zustand(entity);
      return !!zustand && zustand.state === "on";
    }

    /**
     * Klick öffnet die Detailansicht über `hass-more-info`.
     *
     * Das Ereignis muss den Schattenbaum verlassen – daher `composed`.
     */
    _klickbar(element, entity) {
      if (!entity) return element;
      element.classList.add("klickbar");
      element.setAttribute("role", "button");
      element.setAttribute("tabindex", "0");
      const oeffnen = () => {
        this.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: { entityId: entity },
            bubbles: true,
            composed: true,
          })
        );
      };
      element.addEventListener("click", oeffnen);
      element.addEventListener("keydown", (ereignis) => {
        if (ereignis.key === "Enter" || ereignis.key === " ") {
          ereignis.preventDefault();
          oeffnen();
        }
      });
      return element;
    }

    /** Ob eine Pumpe fördert. Manche melden keinen Zustand, sondern ihre Drehzahl. */
    _foerdert(entity) {
      const zahl = this._zahl(entity);
      return zahl !== null ? zahl > 0 : this._istAn(entity);
    }

    /** Ob an dieser Anlage gerade irgendeine Pumpe fördert. */
    _foerdertEtwas(anlage) {
      return (anlage.schema_pumpen || []).some((eintrag) => this._foerdert(eintrag.entity));
    }
  };
