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
      zeilen.forEach((zeile) => {
        karte.appendChild(this._statuszeile(zeile.entity, zeile.titel));
      });
      return { id, titel, knoten: karte };
    });
  }
  };
