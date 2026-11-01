/**
 * Reiter „Hybrid“.
 *
 * Wie der Hybridmanager zwischen Kessel und Wärmepumpe wählt: Zustand,
 * Einsatzgrenzen, der Kostenvergleich Pellets gegen Strom und Diagramme.
 * Die Aufteilung kommt fertig aus `panel/hybrid.py`; gerechnet wird hier nur
 * der Kostenvergleich, weil er den aktuellen Werten folgen muss.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

export const HybridMixin = (Basis) =>
  class extends Basis {
  _hybridReiter(anlage) {
    const hybrid = anlage.hybrid;
    if (!hybrid) return [];
    const karten = [];
    if ((hybrid.zustand || []).length) {
      karten.push({ id: "hybrid-zustand", titel: "Hybrid-Zustand", knoten: this._hybridZeilen("Hybrid-Zustand", hybrid.zustand) });
    }
    const kosten = this._hybridKosten(hybrid.wirtschaftlichkeit || {});
    if (kosten) karten.push({ id: "hybrid-kosten", titel: "Wirtschaftlichkeit", knoten: kosten, breite: 2 });
    if ((hybrid.grenzen || []).length) {
      karten.push({ id: "hybrid-grenzen", titel: "Einsatzgrenzen", knoten: this._hybridZeilen("Einsatzgrenzen", hybrid.grenzen) });
    }
    (hybrid.diagramme || []).forEach((diagramm, nummer) => {
      const karte = this._karte(diagramm.titel);
      const platz = document.createElement("div");
      platz.dataset.karte = JSON.stringify(diagramm.karte);
      karte.appendChild(platz);
      karten.push({ id: `hybrid-diagramm-${nummer}`, titel: diagramm.titel, knoten: karte, breite: 2 });
    });
    return karten;
  }

  _hybridZeilen(titel, zeilen) {
    const karte = this._karte(titel);
    zeilen.forEach((zeile) => karte.appendChild(this._statuszeile(zeile.entity, zeile.titel, zeile.symbol)));
    return karte;
  }

  /** Eine Zahl aus dem Zustand einer Entität; ohne gültigen Wert `null`. */
  _hybridZahl(entity) {
    const zustand = entity && this._zustand(entity);
    const zahl = zustand ? Number.parseFloat(zustand.state) : Number.NaN;
    return Number.isFinite(zahl) ? zahl : null;
  }

  /** Wärmepreis der Pellets in €/kWh: Preis je Tonne durch nutzbare Wärme je Kilogramm. */
  _hybridWaermepreis(w) {
    const kosten = this._hybridZahl(w.kosten);
    const heizwert = this._hybridZahl(w.heizwert);
    const wirkungsgrad = this._hybridZahl(w.wirkungsgrad);
    if (kosten === null || !heizwert || !wirkungsgrad) return null;
    return kosten / 1000 / (heizwert * (wirkungsgrad / 100));
  }

  _hybridZahlText(zahl, stellen) {
    return zahl.toLocaleString(this._hass?.locale?.language || undefined, {
      minimumFractionDigits: stellen,
      maximumFractionDigits: stellen,
    });
  }

  /**
   * Der Kostenvergleich: Wärme aus Pellets gegen Wärme aus Strom.
   *
   * Die Wärmepumpe ist günstiger, solange ihre Leistungszahl über dem
   * Verhältnis Strompreis zu Wärmepreis liegt. Welcher Tarif gerade gilt,
   * steht im Zeitprogramm der Stromtarife – deshalb je Tarif eine Zeile.
   */
  _hybridKosten(w) {
    if (!w.kosten || !w.heizwert || !w.wirkungsgrad) return null;
    const karte = this._karte("Wirtschaftlichkeit");
    const kopf = document.createElement("div");
    kopf.className = "abhilfe";
    karte.appendChild(kopf);
    const liste = document.createElement("div");
    karte.appendChild(liste);
    const formel = document.createElement("div");
    formel.className = "abhilfe";
    formel.textContent = this._t(
      "Wärmepreis = Pelletpreis ÷ (Heizwert × Wirkungsgrad). Grenz-COP = Strompreis ÷ Wärmepreis: Liegt die Leistungszahl darüber, heizt die Wärmepumpe günstiger."
    );
    karte.appendChild(formel);

    this._bindungen.push(() => {
      const preis = this._hybridWaermepreis(w);
      const cop = this._hybridZahl(w.cop);
      const copHeute = this._hybridZahl(w.cop_heute);
      if (preis === null) {
        kopf.textContent = this._t("Für den Vergleich fehlen Pelletpreis, Heizwert oder Wirkungsgrad.");
        liste.replaceChildren();
        return;
      }
      const teile = [`${this._t("Wärmepreis Pellets")}: ${this._hybridZahlText(preis * 100, 2)} ct/kWh`];
      if (cop !== null) teile.push(`${this._t("COP aktuell")}: ${this._hybridZahlText(cop, 1)}`);
      if (copHeute !== null) teile.push(`${this._t("COP Heizen heute")}: ${this._hybridZahlText(copHeute, 1)}`);
      kopf.textContent = teile.join(" · ");
      const vergleich = copHeute ?? cop;
      liste.replaceChildren(
        ...(w.tarife || []).map((tarif) => {
          const strom = this._hybridZahl(tarif.entity);
          const zeile = document.createElement("div");
          zeile.className = "status-zeile";
          zeile.appendChild(this._symbolKnoten("mdi:flash"));
          const links = document.createElement("div");
          links.className = "titel";
          const rechts = document.createElement("div");
          rechts.className = "wert";
          if (strom === null) {
            links.textContent = `${this._t("Tarif")} ${tarif.nummer}`;
            rechts.textContent = "–";
          } else {
            const grenze = strom / preis;
            links.textContent = `${this._t("Tarif")} ${tarif.nummer} · ${this._hybridZahlText(strom * 100, 1)} ct/kWh`;
            rechts.textContent = `${this._t("Grenz-COP")} ${this._hybridZahlText(grenze, 2)}`;
            if (vergleich !== null) {
              const guenstiger = vergleich > grenze;
              rechts.classList.add(guenstiger ? "zustand" : "warm");
              rechts.textContent += ` · ${this._t(guenstiger ? "Wärmepumpe" : "Pellets")}`;
            }
          }
          zeile.append(links, rechts);
          return this._klickbar(zeile, tarif.entity);
        })
      );
    });
    return karte;
  }
  };
