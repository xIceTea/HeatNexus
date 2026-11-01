/**
 * Der Hybridmanager: Karte in der Steuerung, Diagramme im Verlauf.
 *
 * Die Karte trägt Pelletpreis, Stromtarife und den Kostenvergleich Pellets
 * gegen Strom. Wer den Preis ändert, sieht darunter gleich den neuen
 * Grenz-COP. Die Aufteilung kommt fertig aus `panel/hybrid.py`; gerechnet
 * wird hier nur der Vergleich, weil er den aktuellen Werten folgen muss.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

export const HybridMixin = (Basis) =>
  class extends Basis {
  /** Die Karte „Hybridmanager“ für die Steuerung; ohne Hybridmanager `null`. */
  _hybridKarte(anlage) {
    const w = anlage.hybrid && anlage.hybrid.karte;
    if (!w || !w.kosten) return null;
    const karte = this._karte("Hybridmanager");
    karte.appendChild(this._zahlFeld(this._t("Kosten Pellets"), w.kosten));
    (w.tarife || []).forEach((tarif) => {
      karte.appendChild(this._zahlFeld(`${this._t("Tarif")} ${tarif.nummer}`, tarif.entity));
    });
    const kopf = document.createElement("div");
    kopf.className = "status-abschnitt";
    kopf.textContent = this._t("Kostenvergleich");
    karte.appendChild(kopf);
    karte.appendChild(this._hybridVergleich(w));
    return karte;
  }

  /** Die Diagramme des Hybridmanagers für den Verlauf. */
  _hybridDiagramme(anlage) {
    return ((anlage.hybrid && anlage.hybrid.diagramme) || []).map((diagramm, nummer) => {
      const karte = this._karte(diagramm.titel);
      const platz = document.createElement("div");
      platz.dataset.karte = JSON.stringify(diagramm.karte);
      karte.appendChild(platz);
      return { id: `hybrid-diagramm-${nummer}`, titel: diagramm.titel, knoten: karte, breite: 2 };
    });
  }

  /** Eine Zahl aus dem Zustand einer Entität; ohne gültigen Wert `null`. */
  _hybridZahl(entity) {
    const zustand = entity && this._zustand(entity);
    const zahl = zustand ? Number.parseFloat(zustand.state) : Number.NaN;
    return Number.isFinite(zahl) ? zahl : null;
  }

  /** Eine Leistungszahl; eine stehende Wärmepumpe meldet 0, das ist kein Wert. */
  _hybridCop(entity) {
    const cop = this._hybridZahl(entity);
    return cop !== null && cop > 0 ? cop : null;
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

  /** Eine Zeile je Tarif mit Grenz-COP und der Quelle, die gerade günstiger ist. */
  _hybridTarifzeile(tarif, preis, vergleich) {
    const zeile = document.createElement("div");
    zeile.className = "status-zeile";
    zeile.appendChild(this._symbolKnoten("mdi:flash"));
    const links = document.createElement("div");
    links.className = "titel";
    const rechts = document.createElement("div");
    rechts.className = "wert";
    const strom = this._hybridZahl(tarif.entity);
    links.textContent = `${this._t("Tarif")} ${tarif.nummer}`;
    if (strom === null) {
      rechts.textContent = "–";
    } else {
      const grenze = strom / preis;
      rechts.textContent = `${this._t("Grenz-COP")} ${this._hybridZahlText(grenze, 2)}`;
      if (vergleich !== null) {
        const guenstiger = vergleich > grenze;
        rechts.classList.add(guenstiger ? "zustand" : "warm");
        rechts.textContent += ` · ${this._t(guenstiger ? "Wärmepumpe" : "Pellets")}`;
      }
    }
    zeile.append(links, rechts);
    return zeile;
  }

  /**
   * Der Kostenvergleich: Wärme aus Pellets gegen Wärme aus Strom.
   *
   * Die Wärmepumpe ist günstiger, solange ihre Leistungszahl über dem
   * Verhältnis Strompreis zu Wärmepreis liegt. Fehlen Heizwert oder
   * Wirkungsgrad, sagt die Karte, welche Bedienebene sie bringt.
   */
  _hybridVergleich(w) {
    const bereich = document.createElement("div");
    const kopf = document.createElement("div");
    kopf.className = "abhilfe";
    const liste = document.createElement("div");
    const formel = document.createElement("div");
    formel.className = "abhilfe";
    formel.textContent = this._t(
      "Wärmepreis = Pelletpreis ÷ (Heizwert × Wirkungsgrad). Grenz-COP = Strompreis ÷ Wärmepreis: Liegt die Leistungszahl darüber, heizt die Wärmepumpe günstiger."
    );
    bereich.append(kopf, liste, formel);
    if (!w.heizwert || !w.wirkungsgrad) {
      kopf.textContent = this._t(
        "Für den Vergleich fehlen Heizwert und Wirkungsgrad der Pellets. Beide stehen in der Werksebene: In den Optionen der Steuerung unter „Bedienebenen“ die Werksebene einbinden."
      );
      formel.remove();
      return bereich;
    }
    this._bindungen.push(() => {
      const preis = this._hybridWaermepreis(w);
      if (preis === null) {
        kopf.textContent = this._t("Pelletpreis, Heizwert oder Wirkungsgrad melden gerade keinen Wert.");
        liste.replaceChildren();
        return;
      }
      const cop = this._hybridCop(w.cop);
      const copHeute = this._hybridCop(w.cop_heute);
      const teile = [`${this._t("Wärmepreis Pellets")}: ${this._hybridZahlText(preis * 100, 2)} ct/kWh`];
      if (cop !== null) teile.push(`${this._t("COP aktuell")}: ${this._hybridZahlText(cop, 1)}`);
      if (copHeute !== null) teile.push(`${this._t("COP Heizen heute")}: ${this._hybridZahlText(copHeute, 1)}`);
      kopf.textContent = teile.join(" · ");
      const vergleich = copHeute ?? cop;
      liste.replaceChildren(...(w.tarife || []).map((tarif) => this._hybridTarifzeile(tarif, preis, vergleich)));
    });
    return bereich;
  }
  };
