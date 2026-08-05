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

export const VerlaufMixin = (Basis) =>
  class extends Basis {
  // -------------------------------------------------------------------
  // Verlauf
  // -------------------------------------------------------------------
  /**
   * Verlaufskarte mit an- und abwählbaren Linien.
   *
   * Die Vorauswahl kommt aus der Integration; welche Linien der Nutzer
   * zusätzlich sehen will, entscheidet er hier. Die Auswahl überlebt einen
   * Reiterwechsel, weil sie am Element hängt und nicht an der Karte.
   */
  _verlauf(anlage, stunden) {
    if (!(anlage.verlauf || []).length) return null;
    const schluessel = `${anlage.name || ""}|${stunden}`;
    if (!this._linien) this._linien = {};
    if (!this._linien[schluessel]) this._linien[schluessel] = new Set(anlage.verlauf);
    const gewaehlt = this._linien[schluessel];

    const karte = this._karte(`Verlauf (${stunden} Stunden)`);

    const auswahl = document.createElement("div");
    auswahl.className = "linienwahl";
    const moeglich = anlage.verlauf_moeglich || anlage.verlauf.map((e) => ({ entity: e }));
    moeglich.forEach((eintrag) => {
      const kennung = eintrag.entity || eintrag;
      const marke = document.createElement("button");
      marke.type = "button";
      marke.className = "linie";
      marke.textContent = eintrag.titel || this._name(kennung);
      marke.setAttribute("aria-pressed", String(gewaehlt.has(kennung)));
      marke.addEventListener("click", () => {
        if (gewaehlt.has(kennung)) gewaehlt.delete(kennung);
        else gewaehlt.add(kennung);
        marke.setAttribute("aria-pressed", String(gewaehlt.has(kennung)));
        this._verlaufNeuLaden(platz, gewaehlt);
      });
      auswahl.appendChild(marke);
    });
    karte.appendChild(auswahl);

    const platz = document.createElement("div");
    platz.dataset.verlauf = "1";
    platz.dataset.stunden = String(stunden);
    platz.dataset.entities = JSON.stringify([...gewaehlt]);
    karte.appendChild(platz);
    return karte;
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
