/**
 * Reiter „Verlauf“ und die Verlaufskarte der Übersicht.
 *
 * Gezeichnet wird mit der Verlaufskarte von Home Assistant. Sie kommt über
 * `loadCardHelpers` und muss deshalb nachgeladen werden, wenn die Ansicht
 * schon steht.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import { LINIEN_SPEICHER } from "../ordnung.js";

// Mehr Vorschläge passen nicht sinnvoll unter das Suchfeld; die Suche grenzt ein.
const LINIEN_VORSCHLAEGE = 12;

export const VerlaufMixin = (Basis) =>
  class extends Basis {
  // -------------------------------------------------------------------
  // Verlauf
  // -------------------------------------------------------------------
  /**
   * Verlaufskarte mit frei wählbaren Linien: Chips über dem Diagramm, Suche zum
   * Hinzufügen, „Standard“ für die Vorauswahl. Die Wahl gilt je Anlage und
   * Zeitraum und bleibt über das Neuladen der Seite erhalten.
   */
  _verlauf(anlage, stunden) {
    if (!(anlage.verlauf || []).length) return null;
    const moeglich = (anlage.verlauf_moeglich || anlage.verlauf).map((eintrag) => ({
      entity: eintrag.entity || eintrag,
      titel: eintrag.titel || "",
    }));
    const wahl = {
      schluessel: `${anlage.name || ""}|${stunden}`,
      vorauswahl: anlage.verlauf,
      moeglich,
      titel: (kennung) => {
        const eintrag = moeglich.find((e) => e.entity === kennung);
        return (eintrag && eintrag.titel) || this._name(kennung);
      },
    };
    wahl.gewaehlt = new Set(
      this._linienGewaehlt(wahl.schluessel, anlage.verlauf, moeglich.map((e) => e.entity))
    );

    const karte = this._karte(`Verlauf (${stunden} Stunden)`);
    wahl.chips = document.createElement("div");
    wahl.chips.className = "linienwahl";
    karte.appendChild(wahl.chips);

    const werkzeuge = document.createElement("div");
    werkzeuge.className = "linien-werkzeuge";
    werkzeuge.appendChild(this._linienSuche(wahl));
    wahl.standard = document.createElement("button");
    wahl.standard.type = "button";
    wahl.standard.className = "linien-standard";
    wahl.standard.textContent = this._t("Standard");
    wahl.standard.title = this._t("Vorauswahl der Integration wiederherstellen");
    wahl.standard.addEventListener("click", () => {
      wahl.gewaehlt = new Set(wahl.vorauswahl);
      this._linienGeaendert(wahl, null);
    });
    werkzeuge.appendChild(wahl.standard);
    karte.appendChild(werkzeuge);

    wahl.platz = document.createElement("div");
    wahl.platz.dataset.verlauf = "1";
    wahl.platz.dataset.stunden = String(stunden);
    wahl.platz.dataset.entities = JSON.stringify([...wahl.gewaehlt]);
    karte.appendChild(wahl.platz);
    this._linienChips(wahl);
    return karte;
  }

  /** Chips der gewählten Linien und den Standard-Knopf auf den Stand bringen. */
  _linienChips(wahl) {
    const chips = [...wahl.gewaehlt].map((kennung) => {
      const chip = document.createElement("span");
      chip.className = "linie";
      chip.dataset.entity = kennung;
      const name = document.createElement("span");
      name.dataset.roh = "";
      name.textContent = wahl.titel(kennung);
      const weg = document.createElement("button");
      weg.type = "button";
      weg.className = "linie-weg";
      weg.textContent = "×";
      weg.setAttribute("aria-label", this._tMit("{name} entfernen", { name: wahl.titel(kennung) }));
      weg.addEventListener("click", () => {
        wahl.gewaehlt.delete(kennung);
        this._linienGeaendert(wahl, [...wahl.gewaehlt]);
      });
      chip.append(name, weg);
      return chip;
    });
    if (!chips.length) {
      const leer = document.createElement("span");
      leer.className = "linien-leer";
      leer.textContent = this._t("Keine Linie gewählt.");
      chips.push(leer);
    }
    wahl.chips.replaceChildren(...chips);
    const vorauswahl = new Set(wahl.vorauswahl);
    wahl.standard.hidden =
      vorauswahl.size === wahl.gewaehlt.size && [...vorauswahl].every((k) => wahl.gewaehlt.has(k));
  }

  /** Nach jeder Änderung: merken, Chips und Diagramm neu. `null` vergisst die Wahl. */
  _linienGeaendert(wahl, kennungen) {
    this._linienMerken(wahl.schluessel, kennungen);
    this._linienChips(wahl);
    this._verlaufNeuLaden(wahl.platz, wahl.gewaehlt);
  }

  /**
   * Suchfeld mit Vorschlagsliste. Ein Klick, die Taste daneben oder Pfeil nach unten zeigen alle
   * freien Linien; Tippen filtert, Enter übernimmt den markierten Treffer, Escape schließt.
   */
  _linienSuche(wahl) {
    const huelle = document.createElement("div");
    huelle.className = "linien-suche-huelle";
    const feld = document.createElement("input");
    feld.type = "search";
    feld.className = "linien-suche";
    feld.placeholder = this._t("Linie hinzufügen …");
    feld.setAttribute("aria-label", this._t("Sensor für den Verlauf suchen"));
    feld.setAttribute("role", "combobox");
    feld.setAttribute("aria-expanded", "false");
    const liste = document.createElement("ul");
    liste.className = "linien-vorschlaege";
    liste.setAttribute("role", "listbox");
    liste.hidden = true;
    const aufklappen = document.createElement("button");
    aufklappen.type = "button";
    aufklappen.className = "linien-aufklappen";
    aufklappen.tabIndex = -1;
    aufklappen.title = this._t("Alle Linien zeigen");
    aufklappen.setAttribute("aria-label", this._t("Alle Linien zeigen"));
    aufklappen.appendChild(this._symbolKnoten("mdi:menu-down"));
    huelle.append(feld, aufklappen, liste);

    const suche = { feld, liste, treffer: [], aktiv: -1 };
    suche.waehlen = (kennung) => {
      wahl.gewaehlt.add(kennung);
      feld.value = "";
      this._linienVorschlaegeZeigen(wahl, suche, false);
      this._linienGeaendert(wahl, [...wahl.gewaehlt]);
      feld.focus();
    };
    feld.addEventListener("input", () => this._linienVorschlaegeZeigen(wahl, suche, true));
    feld.addEventListener("click", () => this._linienVorschlaegeZeigen(wahl, suche, true));
    // `mousedown` hält den Fokus im Feld; sonst schlösse `blur` die Liste gleich wieder.
    aufklappen.addEventListener("mousedown", (ereignis) => {
      ereignis.preventDefault();
      const zu = liste.hidden;
      if (zu) feld.focus();
      this._linienVorschlaegeZeigen(wahl, suche, zu);
    });
    feld.addEventListener("blur", () => this._linienVorschlaegeZeigen(wahl, suche, false));
    feld.addEventListener("keydown", (ereignis) => this._linienTaste(wahl, suche, ereignis));
    return huelle;
  }

  _linienTaste(wahl, suche, ereignis) {
    const offen = !suche.liste.hidden && suche.treffer.length > 0;
    if (ereignis.key === "Escape" && !suche.liste.hidden) {
      ereignis.stopPropagation();
      this._linienVorschlaegeZeigen(wahl, suche, false);
    } else if (offen && (ereignis.key === "ArrowDown" || ereignis.key === "ArrowUp")) {
      ereignis.preventDefault();
      const schritt = ereignis.key === "ArrowDown" ? 1 : -1;
      suche.aktiv = (suche.aktiv + schritt + suche.treffer.length) % suche.treffer.length;
      this._linienVorschlaegeMarkieren(suche);
    } else if (offen && ereignis.key === "Enter") {
      ereignis.preventDefault();
      suche.waehlen(suche.treffer[Math.max(suche.aktiv, 0)].entity);
    } else if (!offen && ereignis.key === "ArrowDown") {
      ereignis.preventDefault();
      this._linienVorschlaegeZeigen(wahl, suche, true);
    }
  }

  /** Ohne Begriff alle freien Linien, sonst Treffer auf Titel und Entitäts-ID; `offen` false schließt. */
  _linienVorschlaegeZeigen(wahl, suche, offen) {
    const begriff = String(suche.feld.value || "").trim().toLowerCase();
    const frei = offen ? wahl.moeglich.filter((e) => !wahl.gewaehlt.has(e.entity)) : [];
    suche.treffer = begriff
      ? frei.filter((e) => `${e.titel} ${e.entity}`.toLowerCase().includes(begriff)).slice(0, LINIEN_VORSCHLAEGE)
      : frei;
    suche.aktiv = suche.treffer.length ? 0 : -1;
    const eintraege = suche.treffer.map((eintrag) => {
      const zeile = document.createElement("li");
      zeile.className = "linien-vorschlag";
      zeile.setAttribute("role", "option");
      zeile.dataset.roh = "";
      zeile.dataset.entity = eintrag.entity;
      const titel = document.createElement("span");
      titel.textContent = wahl.titel(eintrag.entity);
      const kennung = document.createElement("small");
      kennung.textContent = eintrag.entity;
      zeile.append(titel, kennung);
      // `mousedown` statt `click`: Sonst schließt der Fokusverlust des Felds
      // die Liste, bevor der Klick ankommt.
      zeile.addEventListener("mousedown", (ereignis) => {
        ereignis.preventDefault();
        suche.waehlen(eintrag.entity);
      });
      return zeile;
    });
    if (offen && !eintraege.length) {
      const leer = document.createElement("li");
      leer.className = "linien-vorschlag leer";
      leer.textContent = this._t(begriff ? "Kein Sensor passt zu dieser Suche." : "Alle Linien sind gewählt.");
      eintraege.push(leer);
    }
    suche.liste.replaceChildren(...eintraege);
    suche.liste.hidden = !eintraege.length;
    suche.feld.setAttribute("aria-expanded", String(!suche.liste.hidden));
    this._linienVorschlaegeMarkieren(suche);
  }

  _linienVorschlaegeMarkieren(suche) {
    Array.from(suche.liste.children).forEach((zeile, stelle) => {
      zeile.setAttribute("aria-selected", String(stelle === suche.aktiv));
    });
  }

  /**
   * Die gemerkte Wahl, beschränkt auf Linien, die es an der Anlage noch gibt.
   * Bleibt davon nichts übrig, gilt wieder die Vorauswahl der Integration.
   */
  _linienGewaehlt(schluessel, vorauswahl, kennungen) {
    const gemerkt = (this._linien || {})[schluessel];
    if (!Array.isArray(gemerkt)) return vorauswahl;
    const vorhanden = gemerkt.filter((kennung) => kennungen.includes(kennung));
    return vorhanden.length || !gemerkt.length ? vorhanden : vorauswahl;
  }

  /** Die Linienwahl aus den Nutzerdaten holen, ohne sie aus dem Browser. */
  async _linienHolen() {
    let gemerkt;
    try {
      const antwort = await this._hass.callWS({ type: "frontend/get_user_data", key: LINIEN_SPEICHER });
      gemerkt = (antwort && antwort.value) || this._linienAusBrowser();
    } catch (err) {
      gemerkt = this._linienAusBrowser();
    }
    if (!gemerkt || typeof gemerkt !== "object" || !Object.keys(gemerkt).length) return;
    // Was der Nutzer bis hierher schon umgestellt hat, gilt vor dem Gemerkten.
    this._linien = { ...gemerkt, ...(this._linien || {}) };
    this._gebaut = false;
    this._zeichnen();
  }

  /** Eine Wahl merken, `null` vergisst sie; scheitern die Nutzerdaten, hält sie der Browser. */
  _linienMerken(schluessel, kennungen) {
    const linien = { ...(this._linien || {}) };
    if (kennungen) linien[schluessel] = kennungen;
    else delete linien[schluessel];
    this._linien = linien;
    this._hass
      .callWS({ type: "frontend/set_user_data", key: LINIEN_SPEICHER, value: linien })
      .catch((err) => {
        console.warn("HeatNexus: Linienwahl liegt nur im Browser", err);
        try {
          window.localStorage.setItem(LINIEN_SPEICHER, JSON.stringify(linien));
        } catch (fehler) {
          /* Ohne Speicher gilt die Wahl bis zum Neuladen. */
        }
      });
  }

  _linienAusBrowser() {
    try {
      return JSON.parse(window.localStorage.getItem(LINIEN_SPEICHER) || "null");
    } catch (err) {
      return null;
    }
  }

  async _verlaufNeuLaden(platz, gewaehlt) {
    platz.dataset.entities = JSON.stringify([...gewaehlt]);
    if (!window.loadCardHelpers) return;
    const helfer = await window.loadCardHelpers();
    const karte = helfer.createCardElement({
      type: "history-graph",
      hours_to_show: Number(platz.dataset.stunden) || 24,
      entities: [...gewaehlt],
    });
    karte.hass = this._hass;
    platz.replaceChildren(karte);
    const alt = this._verlaufskarten.findIndex((k) => k.parentElement === platz);
    if (alt >= 0) this._verlaufskarten[alt] = karte;
    else this._verlaufskarten.push(karte);
  }

  _verlaufReiter(anlage) {
    return [
      {
        id: "verlauf48",
        titel: "Verlauf (48 Stunden)",
        knoten: this._verlauf(anlage, 48),
        // Ein Diagramm über die halbe Breite liest sich schlechter als eines
        // über zwei Spalten; schmaler machen kann man es im Anordnen-Modus.
        breite: 2,
      },
    ];
  }

  async _verlaufKarteLaden() {
    const plaetze = this.shadowRoot.querySelectorAll("[data-verlauf]");
    if (!plaetze.length || !window.loadCardHelpers) return;
    const helfer = await window.loadCardHelpers();
    this._verlaufskarten = [];
    plaetze.forEach((platz) => {
      const karte = helfer.createCardElement({
        type: "history-graph",
        hours_to_show: Number(platz.dataset.stunden) || 24,
        entities: JSON.parse(platz.dataset.entities),
      });
      karte.hass = this._hass;
      platz.replaceChildren(karte);
      this._verlaufskarten.push(karte);
    });
  }
  };
