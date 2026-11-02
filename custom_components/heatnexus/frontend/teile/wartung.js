/**
 * Reiter „Wartung“.
 *
 * Restlaufzeiten, Brennstoff und Zählerstände – drei Listen, die die
 * Integration fertig zusammenstellt.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

export const WartungMixin = (Basis) =>
  class extends Basis {
  // -------------------------------------------------------------------
  // Reiter „Wartung"
  // -------------------------------------------------------------------
  _wartung(anlage) {
    const wartung = anlage.wartung || {};
    const abschnitte = [
      ["restlaufzeiten", "Restlaufzeiten", wartung.restlaufzeiten],
      ["brennstoff", "Brennstoff", wartung.brennstoff],
      ["zaehler", "Zählerstände", wartung.zaehler],
      ["weiteres", "Weiteres", wartung.weitere],
    ];
    return abschnitte.map(([id, titel, zeilen]) => {
      if (!zeilen || !zeilen.length) return { id, titel, knoten: null };
      const karte = this._karte(titel);
      // Mischt eine Karte mehrere Anlagenteile, trennt sie eine Zwischenzeile
      // mit dem Namen – sonst bliebe offen, ob ein Zähler zum Kessel oder zur
      // Wärmepumpe gehört.
      const gemischt = new Set(zeilen.map((zeile) => zeile.teil)).size > 1;
      let vorher = null;
      zeilen.forEach((zeile) => {
        if (gemischt && zeile.teil !== vorher) {
          const kopf = document.createElement("div");
          kopf.className = "status-abschnitt";
          kopf.textContent = zeile.teil;
          karte.appendChild(kopf);
          vorher = zeile.teil;
        }
        karte.appendChild(this._statuszeile(zeile.entity, zeile.titel));
      });
      return { id, titel, knoten: karte };
    });
  }
  };
