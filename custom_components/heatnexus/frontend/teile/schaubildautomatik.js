/**
 * Die Automatik im Schaubild: Zustand im Kopf, Begründung darunter, eine Marke am Heizkörper.
 * Die Daten stehen an den Heizkreisen der Oberfläche; die Lovelace-Karte führt sie nicht.
 */

import { AUTOMATIK_SYMBOLE, ZUSTAENDE } from "./automatik.js";

export const SchaubildAutomatikMixin = (Basis) =>
  class extends Basis {
    /**
     * Was die Automatik eines Kreises gerade zeigt; `null`, wenn sie fehlt oder aus ist.
     * Eine offene Empfehlung geht dem Zustand vor, denn sie wartet auf eine Antwort.
     */
    _automatikLage(kreis) {
      const zustand = this._zustand(kreis.automatik);
      if (!zustand || !(zustand.state in ZUSTAENDE) || zustand.state === "aus") return null;
      const empfehlung = kreis.automatik_empfehlung ? this._zustand(kreis.automatik_empfehlung) : null;
      if (empfehlung && empfehlung.state in ZUSTAENDE) {
        return {
          art: "empfehlung",
          symbol: "mdi:lightbulb-on-outline",
          text: `${this._t("Empfehlung")} · ${this._t(ZUSTAENDE[empfehlung.state])}`,
          grund: empfehlung.attributes.begruendung || "",
          offen: true,
        };
      }
      return {
        art: zustand.state,
        symbol: AUTOMATIK_SYMBOLE[zustand.state] || "mdi:robot-outline",
        text: zustand.attributes.kurz || `${this._t("Automatik")} · ${this._t(ZUSTAENDE[zustand.state])}`,
        grund: zustand.attributes.begruendung || "",
        offen: false,
      };
    }

    /** Je Kreis mit Automatik eine Pille hinter dem Titel und darunter eine Zeile mit der Begründung. */
    _automatikImBild(anlage, karte) {
      const kreise = (anlage.heizkreise || []).filter((kreis) => kreis.automatik);
      if (!kreise.length) return;
      const kopf = karte.querySelector(".kartenkopf");
      let anker = kopf && kopf.querySelector("h2");
      const zeilen = document.createElement("div");
      zeilen.className = "bild-automatik";
      kreise.forEach((kreis) => {
        const pille = this._automatikPille(kreis, kreise.length > 1);
        // Unter „Alle“ ersetzt der Anlagenname den Titel; die Pille steht dann hinter ihm.
        if (anker) {
          anker.parentElement.insertBefore(pille, anker.nextSibling);
          anker = pille;
        } else {
          zeilen.appendChild(pille);
        }
        zeilen.appendChild(this._automatikZeile(kreis));
      });
      karte.insertBefore(zeilen, kopf ? kopf.nextSibling : karte.firstChild);
    }

    _automatikPille(kreis, mitName) {
      const pille = document.createElement("button");
      pille.type = "button";
      pille.className = "automatik-marke im-bild";
      pille.hidden = true;
      pille.title = this._t("Zur Automatik");
      const symbol = this._symbolKnoten("mdi:robot-outline");
      const text = document.createElement("span");
      pille.append(symbol, text);
      pille.addEventListener("click", (ereignis) => {
        ereignis.stopPropagation();
        this._reiter = "automatik";
        this._gebaut = false;
        this._zeichnen();
      });
      this._bindungen.push(() => {
        const lage = this._automatikLage(kreis);
        pille.hidden = !lage;
        if (!lage) return;
        pille.className = `automatik-marke im-bild z-${lage.art}`;
        pille.dataset.zustand = lage.art;
        symbol.setAttribute("icon", lage.symbol);
        text.textContent = mitName ? `${kreis.titel} · ${lage.text}` : lage.text;
      });
      return pille;
    }

    /** Die Begründung in einem Satz; bei einer offenen Empfehlung die Tasten dazu. */
    _automatikZeile(kreis) {
      const zeile = document.createElement("div");
      zeile.className = "bild-automatik-zeile";
      zeile.hidden = true;
      const grund = document.createElement("span");
      grund.className = "grund";
      const tasten = (["uebernehmen", "verwerfen"]).map((art) =>
        this._empfehlungsTaste((kreis.automatik_tasten || {})[art], art)
      );
      zeile.append(grund, ...tasten);
      this._bindungen.push(() => {
        const lage = this._automatikLage(kreis);
        zeile.hidden = !lage || !lage.grund;
        if (!lage) return;
        grund.textContent = lage.grund;
        const darf = Boolean(this._hass && this._hass.user && this._hass.user.is_admin);
        tasten.forEach((taste) => {
          const zustand = taste.dataset.entity ? this._zustand(taste.dataset.entity) : null;
          taste.hidden = !lage.offen || !zustand || zustand.state === "unavailable";
          taste.disabled = !darf;
        });
      });
      return zeile;
    }

    _empfehlungsTaste(entity, art) {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = art === "uebernehmen" ? "automatik-knopf" : "automatik-knopf leise";
      taste.textContent = this._t(art === "uebernehmen" ? "Übernehmen" : "Verwerfen");
      taste.hidden = true;
      if (entity) taste.dataset.entity = entity;
      taste.addEventListener("click", (ereignis) => {
        ereignis.stopPropagation();
        if (entity) this._hass.callService("button", "press", { entity_id: entity });
      });
      return taste;
    }

    /** Eine Marke oben am Heizkörper, solange die Automatik eingreift oder etwas vorschlägt; ein Klick zeigt die Entität. */
    _automatikMarke(anlage, eintrag, huelle) {
      const kreis = (anlage.heizkreise || []).find(
        (k) => k.automatik && ((eintrag.entity && k.vorlauf === eintrag.entity) || k.titel === eintrag.titel)
      );
      if (!kreis) return;
      const marke = document.createElement("div");
      marke.className = "automatik-bildmarke";
      marke.hidden = true;
      marke.style.left = `calc(${eintrag.left} + ${eintrag.breite})`;
      marke.style.top = eintrag.top;
      marke.style.width = `calc(${eintrag.breite} * 0.3)`;
      const symbol = this._symbolKnoten("mdi:robot-outline");
      marke.appendChild(symbol);
      huelle.appendChild(this._klickbar(marke, kreis.automatik));
      this._bindungen.push(() => {
        const lage = this._automatikLage(kreis);
        marke.hidden = !lage || (!lage.offen && !(lage.art in AUTOMATIK_SYMBOLE));
        if (marke.hidden) return;
        marke.dataset.zustand = lage.art;
        marke.title = lage.text;
        symbol.setAttribute("icon", lage.symbol);
      });
    }
  };
