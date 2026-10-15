/**
 * Störspeicher des Bediengeräts in der Karte „Störungen“.
 *
 * Anliegende Einträge stehen als Kachel oben, mit der Taste, die das
 * Bediengerät dafür anbietet. Darunter folgt der Verlauf in festen Spalten:
 * Symbol, Klartext, Zeit, Papierkorb. Was erlaubt ist, entscheidet der Server.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

import { zeitzone } from "./zeit.js";

// Art des Eintrags nach dem Kennbuchstaben der Meldung: Alarm, Fehler, Info.
const ARTEN = {
  A: ["mdi:alert-octagon-outline", "alarm"],
  E: ["mdi:alert-outline", "fehler"],
  I: ["mdi:information-outline", "info"],
};

export const StoerspeicherMixin = (Basis) =>
  class extends Basis {
    _stoerspeicherEintraege(entity) {
      const zustand = entity && this._zustand(entity);
      return (zustand && zustand.attributes.eintraege) || [];
    }

    /** Kacheln hinter `vor`, den Verlauf ans Ende der Karte; ohne Störspeicher bleibt die Karte, wie sie ist. */
    _stoerspeicherListe(karte, entity, vor) {
      if (!entity) return;
      const kacheln = document.createElement("div");
      kacheln.className = "stoerspeicher-kacheln";
      karte.insertBefore(kacheln, vor ? vor.nextSibling : null);
      const kopf = document.createElement("div");
      kopf.className = "stoerspeicher-kopf";
      const liste = document.createElement("div");
      liste.className = "stoerspeicher";
      karte.append(kopf, liste);
      let stand = null;
      this._bindungen.push(() => {
        const eintraege = this._stoerspeicherEintraege(entity);
        const neu = JSON.stringify(eintraege);
        if (neu === stand) return;
        stand = neu;
        const anliegend = eintraege.filter((eintrag) => eintrag.aktiv);
        const verlauf = eintraege.filter((eintrag) => !eintrag.aktiv);
        kacheln.replaceChildren(...anliegend.map((eintrag) => this._stoerspeicherKachel(eintrag, entity)));
        kopf.textContent = this._t(anliegend.length ? "Verlauf" : "Störspeicher");
        liste.replaceChildren(...verlauf.map((eintrag) => this._stoerspeicherZeile(eintrag, entity)));
        const leer = !eintraege.length;
        if (leer) liste.appendChild(this._hinweisKnoten(this._t("Der Störspeicher ist leer.")));
        kopf.style.display = verlauf.length || leer ? "block" : "none";
      });
    }

    _stoerspeicherZeit(iso, mitJahr) {
      if (!iso) return "";
      const sprache = (this._hass && this._hass.locale && this._hass.locale.language) || undefined;
      try {
        const zeit = new Date(iso);
        return new Intl.DateTimeFormat(sprache, {
          weekday: mitJahr ? "short" : undefined,
          day: "2-digit",
          month: "2-digit",
          year: mitJahr || zeit.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined,
          hour: "2-digit",
          minute: "2-digit",
          timeZone: zeitzone(this._hass),
        }).format(zeit);
      } catch {
        return iso;
      }
    }

    _stoerspeicherHerkunft(eintrag) {
      return [eintrag.geraet, [eintrag.art, eintrag.code].filter(Boolean).join(" ")].filter(Boolean).join(" · ");
    }

    /** Symbol in einem Feld, getönt nach Art; erledigte Einträge grau. */
    _stoerspeicherSymbol(eintrag, getoent) {
      const [symbol, art] = ARTEN[eintrag.symbol] || ARTEN.E;
      const feld = document.createElement("div");
      feld.className = `stoerspeicher-symbol ${getoent ? art : "erledigt"}`;
      feld.appendChild(this._symbolKnoten(symbol));
      return feld;
    }

    _stoerspeicherOeffnen(knoten, eintrag, entity) {
      knoten.tabIndex = 0;
      knoten.setAttribute("role", "button");
      const oeffnen = () => this._stoerspeicherDetail(eintrag, entity);
      knoten.addEventListener("click", oeffnen);
      knoten.addEventListener("keydown", (ereignis) => {
        if (ereignis.key === "Enter" || ereignis.key === " ") {
          ereignis.preventDefault();
          oeffnen();
        }
      });
    }

    /** Eine Zeile im gemeinsamen Raster: Symbol, Klartext mit Herkunft und Zeit, Taste. */
    _stoerspeicherReihe(klasse, eintrag, entity, symbol, taste) {
      const reihe = document.createElement("div");
      reihe.className = klasse;
      const mitte = document.createElement("div");
      mitte.className = "stoerspeicher-mitte";
      const text = document.createElement("div");
      text.className = "stoerspeicher-text";
      text.textContent = eintrag.text || "";
      const herkunft = document.createElement("div");
      herkunft.className = "stoerspeicher-herkunft";
      herkunft.textContent = [this._stoerspeicherHerkunft(eintrag), this._stoerspeicherZeit(eintrag.zuerst)]
        .filter(Boolean)
        .join(" · ");
      mitte.append(text, herkunft);
      const ende = document.createElement("div");
      ende.className = "stoerspeicher-ende";
      if (taste) ende.appendChild(taste);
      reihe.append(symbol, mitte, ende);
      this._stoerspeicherOeffnen(reihe, eintrag, entity);
      return reihe;
    }

    /** Eine Taste als Symbol in der letzten Spalte; der Klick öffnet nicht zusätzlich das Detail. */
    _stoerspeicherTaste(klasse, symbol, beschriftung, aktion, eintrag, entity) {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = klasse;
      taste.title = this._t(beschriftung);
      taste.setAttribute("aria-label", this._t(beschriftung));
      taste.appendChild(this._symbolKnoten(symbol));
      taste.addEventListener("click", (ereignis) => {
        ereignis.stopPropagation();
        this._stoerspeicherAktion(aktion, eintrag, entity);
      });
      return taste;
    }

    /** Ein anliegender Eintrag: dieselbe Zeile, getönt mit Farbleiste, die erste erlaubte Taste rechts. */
    _stoerspeicherKachel(eintrag, entity) {
      const art = (ARTEN[eintrag.symbol] || ARTEN.E)[1];
      const aktion = eintrag.zuruecksetzbar ? "zuruecksetzen" : eintrag.quittierbar ? "quittieren" : null;
      const taste =
        aktion &&
        this._stoerspeicherTaste(
          "stoerspeicher-taste",
          aktion === "zuruecksetzen" ? "mdi:restore" : "mdi:check",
          aktion === "zuruecksetzen" ? "Zurücksetzen" : "Quittieren",
          aktion,
          eintrag,
          entity
        );
      const symbol = this._stoerspeicherSymbol(eintrag, true);
      return this._stoerspeicherReihe(`stoerspeicher-kachel ${art}`, eintrag, entity, symbol, taste);
    }

    /** Ein erledigter Eintrag im Verlauf; die letzte Spalte bleibt auch ohne Papierkorb frei. */
    _stoerspeicherZeile(eintrag, entity) {
      const taste =
        eintrag.loeschbar &&
        this._stoerspeicherTaste("stoerspeicher-muell", "mdi:delete-outline", "Meldung löschen", "loeschen", eintrag, entity);
      const symbol = this._stoerspeicherSymbol(eintrag, false);
      return this._stoerspeicherReihe("stoerspeicher-zeile", eintrag, entity, symbol, taste);
    }

    /** Das Detail wie am Bediengerät: Klartext, Abhilfe und die Tasten, die für diesen Eintrag gelten. */
    _stoerspeicherDetail(eintrag, entity) {
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog";
      const titel = document.createElement("h3");
      titel.className = "dialog-titel";
      titel.textContent = eintrag.text || [eintrag.art, eintrag.code].filter(Boolean).join(" ");
      const herkunft = document.createElement("div");
      herkunft.className = "stoerspeicher-herkunft";
      herkunft.textContent = [this._stoerspeicherHerkunft(eintrag), this._stoerspeicherZeit(eintrag.zuerst, true)]
        .filter(Boolean)
        .join(" · ");
      dialog.append(titel, herkunft);
      const abhilfe = eintrag.behebung || eintrag.info;
      if (abhilfe) {
        const kopf = document.createElement("div");
        kopf.className = "stoerspeicher-kopf";
        kopf.textContent = this._t("Abhilfe");
        const text = document.createElement("div");
        text.className = "dialog-text";
        text.textContent = abhilfe;
        dialog.append(kopf, text);
      }
      const leiste = document.createElement("div");
      leiste.className = "dialog-leiste";
      const schliessen = document.createElement("button");
      schliessen.type = "button";
      schliessen.className = "dialog-taste";
      schliessen.textContent = this._t("Schließen");
      leiste.appendChild(schliessen);
      const aktionen = [
        ["zuruecksetzen", "Zurücksetzen", eintrag.zuruecksetzbar],
        ["quittieren", "Quittieren", eintrag.quittierbar],
        ["loeschen", "Löschen", eintrag.loeschbar],
      ];
      let zu = () => {};
      for (const [aktion, beschriftung, erlaubt] of aktionen) {
        if (!erlaubt) continue;
        const taste = document.createElement("button");
        taste.type = "button";
        taste.className = "dialog-taste betont";
        taste.textContent = this._t(beschriftung);
        taste.addEventListener("click", async () => {
          zu();
          await this._stoerspeicherAktion(aktion, eintrag, entity);
        });
        leiste.appendChild(taste);
      }
      dialog.appendChild(leiste);
      schleier.appendChild(dialog);
      zu = this._dialogOeffnen(schleier, { fokus: schliessen });
      schliessen.addEventListener("click", zu);
    }

    /** Rückfrage, dann der Dienst; ein Fehler erscheint in der Leiste von Home Assistant. */
    async _stoerspeicherAktion(aktion, eintrag, entity) {
      const fragen = {
        zuruecksetzen: [
          "Störung zurücksetzen",
          "Die Störung wird wie mit der Taste am Bediengerät zurückgesetzt. Steuerungen ab Fassung 2 heben damit die Störung am Kessel auf. Ist die Ursache behoben?",
        ],
        quittieren: [
          "Störung quittieren",
          "Die Meldung gilt als gelesen und schließt sich am Bediengerät. Die Störung am Kessel bleibt bestehen.",
        ],
        loeschen: ["Meldung löschen", "Der Eintrag verschwindet aus dem Störspeicher des Bediengeräts."],
      };
      const [titel, frage] = fragen[aktion];
      if (!(await this._bestaetigen(this._t(titel), this._t(frage)))) return;
      try {
        await this._hass.callService("heatnexus", `stoerung_${aktion}`, {
          entity_id: entity,
          eintrag: eintrag.id,
        });
      } catch (fehler) {
        this._melden((fehler && fehler.message) || String(fehler));
      }
    }
  };
