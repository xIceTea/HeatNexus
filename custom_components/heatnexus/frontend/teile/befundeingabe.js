/**
 * Eingaben der Auswertung: Datum der letzten Pflege, Befüllung und Bestand des Lagers.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin. Die Eingaben schreiben
 * nur in HeatNexus (Datums- und Zahlentitäten, Dienst `brennstoff_geliefert`), nie in die Anlage.
 */

// Wie die Pflege im Dialog heißt; der Schlüssel kommt vom Server (`eingabe.pflege`).
const PFLEGE_TITEL = {
  reinigung: "Reinigung",
  hauptreinigung: "Hauptreinigung",
  wartung: "Wartung",
  asche: "Asche entleeren",
  jahresreinigung: "Jahresreinigung",
  verdampfer: "Verdampferreinigung",
};

function element(tag, klasse, text) {
  const el = document.createElement(tag);
  if (klasse) el.className = klasse;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}

/** Heute als „JJJJ-MM-TT“ in der Ortszeit des Browsers. */
function heute() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Der Wert eines Zahlenfelds; ein leeres Feld ist `null`, Unlesbares `NaN`. */
function feldZahl(feld) {
  const text = String(feld.value ?? "").trim();
  return text === "" ? null : Number(text);
}

export const BefundEingabeMixin = (Basis) =>
  class extends Basis {
    /** Die Tasten unter einer Karte oder Zeile; ohne Eingabe nichts. */
    _befundEingabe(b) {
      const e = b.eingabe;
      if (!e || !e.entity) return null;
      const leiste = element("div", "befund-eingabe");
      if (e.art === "vorrat") {
        leiste.append(
          this._befundTaste(this._t("Befüllung eintragen"), () => this._befundBefuellung(e.entity, b)),
          this._befundTaste(this._t("Bestand eintragen"), () => this._befundBestand(e.entity, b))
        );
        return leiste;
      }
      const stand = this._hass && this._hass.states[e.entity];
      const zuletzt = stand && /^\d{4}-\d{2}-\d{2}$/.test(stand.state) ? stand.state : null;
      // Das bisherige Datum zeigt die Karte selbst; die Taste bringt es nur als Vorgabe mit.
      leiste.appendChild(this._befundTaste(this._t("Datum nachtragen"), () => this._befundDatum(e, zuletzt, b.art)));
      return leiste;
    }

    _befundTaste(text, beiKlick) {
      const taste = element("button", "befund-sprung", text);
      taste.type = "button";
      taste.addEventListener("click", (ereignis) => {
        ereignis.stopPropagation();
        beiKlick();
      });
      return taste;
    }

    _befundDatum(e, zuletzt, art) {
      const feld = element("input", "dialog-zahl befund-datum");
      feld.type = "date";
      feld.max = heute();
      feld.value = zuletzt || heute();
      this._befundFenster(
        this._t(PFLEGE_TITEL[e.pflege] || "Datum nachtragen"),
        art.startsWith("pflege_")
          ? this._t("Der Tag, an dem die Pflege zuletzt erledigt wurde.")
          : this._t("Der Tag, an dem die Reinigung zuletzt erledigt wurde. Die ersten Tage danach bilden den Bezug für den Vergleich."),
        [[this._t("Erledigt am"), feld, ""]],
        () => (/^\d{4}-\d{2}-\d{2}$/.test(feld.value) && feld.value <= heute() ? feld.value : null),
        (datum) => this._hass.callService("date", "set_value", { entity_id: e.entity, date: datum })
      );
    }

    _befundBefuellung(entity, b) {
      const menge = this._befundZahlfeld();
      const rest = this._befundZahlfeld();
      const einheit = (b.angaben || {}).einheit || "";
      this._befundFenster(
        this._t("Befüllung eintragen"),
        this._t("Eine Lieferung oder eine eigene Befüllung des Lagers. Mit dem Rest davor lernt die Rechnung den tatsächlichen Verbrauch. Ohne Rest gilt der gerechnete Vorrat."),
        [
          [this._t("Menge"), menge, einheit],
          [this._t("Rest davor (optional)"), rest, einheit],
        ],
        () => {
          const m = feldZahl(menge);
          const r = feldZahl(rest);
          if (m === null || !Number.isFinite(m) || m <= 0) return null;
          if (r !== null && (!Number.isFinite(r) || r < 0)) return null;
          return r === null ? { menge: m } : { menge: m, rest: r };
        },
        (daten) => this._hass.callService("heatnexus", "brennstoff_geliefert", daten, { entity_id: entity })
      );
    }

    _befundBestand(entity, b) {
      const vorrat = this._befundZahlfeld();
      const bestand = (b.angaben || {}).bestand;
      if (bestand !== null && bestand !== undefined) vorrat.value = String(bestand);
      this._befundFenster(
        this._t("Bestand eintragen"),
        this._t("Der Vorrat, der jetzt im Lager liegt. Mit dem vorigen Stand lernt die Rechnung den tatsächlichen Verbrauch."),
        [[this._t("Vorrat"), vorrat, (b.angaben || {}).einheit || ""]],
        () => {
          const v = feldZahl(vorrat);
          return v !== null && Number.isFinite(v) && v >= 0 ? v : null;
        },
        (wert) => this._hass.callService("number", "set_value", { entity_id: entity, value: wert })
      );
    }

    _befundZahlfeld() {
      const feld = element("input", "dialog-zahl");
      feld.type = "number";
      feld.min = "0";
      feld.step = "0.01";
      feld.inputMode = "decimal";
      return feld;
    }

    /**
     * Ein Fenster mit Feldern; `lesen` gibt die Werte oder `null` bei ungültiger Eingabe,
     * `speichern` schreibt sie. Danach lädt die Auswertung neu.
     */
    _befundFenster(titel, text, felder, lesen, speichern) {
      const schleier = element("div", "schleier");
      const dialog = element("div", "dialog");
      dialog.append(element("h3", "dialog-titel", titel), element("div", "dialog-text", text));
      // Drei Spalten je Zeile – Beschriftung, Feld, Einheit –, damit die Felder bündig stehen.
      const raster = element("div", "befund-felder");
      felder.forEach(([beschriftung, feld, einheit]) => {
        const zeile = element("label", "dialog-zahl-zeile");
        zeile.append(element("span", null, beschriftung), feld, element("span", null, einheit));
        raster.appendChild(zeile);
      });
      dialog.appendChild(raster);
      const fehler = element("div", "befund-leise befund-fehler");
      fehler.hidden = true;
      const leiste = element("div", "dialog-leiste");
      const abbrechen = element("button", "dialog-taste", this._t("Abbrechen"));
      const sichern = element("button", "dialog-taste akzent", this._t("Speichern"));
      abbrechen.type = sichern.type = "button";
      leiste.append(abbrechen, sichern);
      dialog.append(fehler, leiste);
      schleier.appendChild(dialog);
      const zu = this._dialogOeffnen(schleier, { fokus: felder[0][1] });
      abbrechen.addEventListener("click", zu);
      sichern.addEventListener("click", async () => {
        const werte = lesen();
        if (werte === null) {
          fehler.textContent = this._t("Die Eingabe ist unvollständig oder ungültig.");
          fehler.hidden = false;
          return;
        }
        sichern.disabled = true;
        try {
          await speichern(werte);
          zu();
          this._befundLaden();
        } catch (err) {
          console.warn("HeatNexus: Eingabe nicht gespeichert", err);
          sichern.disabled = false;
          this._melden(this._t("Die Eingabe konnte nicht gespeichert werden."));
        }
      });
    }
  };
