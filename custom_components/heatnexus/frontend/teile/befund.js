/**
 * Reiter „Befund“: gemessene Kennwerte je Anlage, ohne Empfehlung und ohne Bedienung.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin. Die Zahlen rechnet der
 * Server (`befund/`), hier entstehen nur Text und Bild.
 */

import { zahl } from "./automatik.js";

const NS = "http://www.w3.org/2000/svg";
// So alt darf der Stand werden, solange der Reiter offen ist; danach lädt er neu.
const BEFUND_TAKT_MS = 5 * 60 * 1000;

function knoten(tag, klasse, text) {
  const el = document.createElement(tag);
  if (klasse) el.className = klasse;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}

/** „2026-10-01“ wird „01.10.“ */
function kurzdatum(datum) {
  return `${datum.slice(8, 10)}.${datum.slice(5, 7)}.`;
}

/** Pfad eines Kreisbogens von `von` bis `bis` Grad, im Uhrzeigersinn ab zwölf Uhr. */
function bogen(cx, cy, r, von, bis) {
  const punkt = (grad) => {
    const w = ((grad - 90) * Math.PI) / 180;
    return `${(cx + r * Math.cos(w)).toFixed(2)} ${(cy + r * Math.sin(w)).toFixed(2)}`;
  };
  return `M${punkt(von)} A${r} ${r} 0 ${bis - von > 180 ? 1 : 0} 1 ${punkt(bis)}`;
}

function ikone(symbol) {
  const el = document.createElement("ha-icon");
  el.setAttribute("icon", symbol);
  return el;
}

function svg(tag, attribute = {}, text) {
  const el = document.createElementNS(NS, tag);
  Object.entries(attribute).forEach(([name, wert]) => el.setAttribute(name, String(wert)));
  if (text !== undefined) el.textContent = text;
  return el;
}

const TITEL = {
  waermespeicher: "Wärmespeicher des Hauses",
  heizgrenze: "Heizgrenze im Betrieb",
  raeume: "Räume erreichen ihr Ziel",
  naechte: "Übergangszeit nachts",
  vorlauf: "Vorlauf erreicht sein Soll",
  laufzeit: "Starts und Laufzeit",
  energie: "Energie je Heizgradtag",
};

const HILFE = {
  waermespeicher:
    "Die Zahl ist die Zeitkonstante des Hauses nach DIN V 18599-2. In dieser Zeit verliert ein Raum ohne Heizung knapp zwei Drittel seines Abstands zur Außentemperatur. Je größer sie ist, desto länger hält das Haus die Wärme. Eine Einordnung wie leicht oder schwer erscheint erst mit belegter Skala.",
  heizgrenze:
    "Geprüft wird, ob der Heizkreis bei der eingestellten Heizgrenze (TA Heizbetrieb) heizt. Je Tag zählen das Mittel der Außentemperatur und ob der Heizkreis mindestens zwei Stunden geheizt hat. Weicht die gemessene Grenze um mehr als 2 K ab, begrenzt etwas anderes das Heizen, etwa Thermostate, ein leerer Puffer oder fremde Wärme.",
  raeume:
    "Gezählt werden Heizstunden ohne Eingriff. Thermostate drosseln, sobald ein Raum warm ist; eine zu hohe Heizkurve zeigt sich deshalb kaum. Sonne und Öfen sind nicht herausgerechnet. Laut Windhager-Anleitung hilft bei zu hoher oder zu niedriger Raumtemperatur: Auslegungstemperatur und/oder Fußpunkt korrigieren oder Behaglichkeit.",
  naechte:
    "In Nächten mit 5 bis 15 °C außen zählt der Raum am Ende der Absenkung gegen das Absenkziel. Laut Windhager-Anleitung hilft bei zu hoher oder zu niedriger Raumtemperatur nachts in der Übergangszeit: Heizgrenze Absenkbetrieb verringern bzw. erhöhen.",
  vorlauf:
    "Gezählt werden Heizstunden, in denen der Vorlauf mehr als 3 K unter seinem Soll bleibt. Mögliche Gründe: Puffer leer, Kessel nicht in Betrieb, Mischer am Anschlag, Wärme über eine Fernleitung.",
  laufzeit:
    "Die Zähler der Steuerung für Brennerstarts und Betriebsstunden. Verglichen wird nur mit dem Kessel selbst; für die Laufzeit je Start gibt es weder Norm noch Herstellerangabe.",
  energie:
    "Erzeugte Wärme aus Kesselleistung und Nennleistung, ohne den Sockel an Tagen ohne Heizen. Die Gradtagzahl nach VDI 3807 rechnet das Wetter heraus; so lassen sich Jahre vergleichen. Sie zählt jeden Tag, dessen Mittel außen unter der Heizgrenze der Norm liegt, mit 20 °C minus Tagesmittel. Diese Grenze ist ein fester Rechenwert, in Deutschland 15 °C, in Österreich und der Schweiz 12 °C, und keine Einstellung der Anlage. Der Wert gilt für die ganze Anlage. Als Heiztag zählt auch ein Tag, an dem eine mitversorgte Anlage ohne eigenen Kessel geheizt hat.",
};

const ABSCHNITT = { haus: "Haus", heizkreis: "Heizkreis", kessel: "Kessel" };

// Kurzname je Befund für Aufzählungen in der Kopfkarte.
const KURZ = {
  waermespeicher: "Wärmespeicher",
  heizgrenze: "Heizgrenze",
  raeume: "Räume",
  naechte: "Nächte",
  vorlauf: "Vorlauf",
  laufzeit: "Laufzeit",
  energie: "Energie",
};

const SYMBOL = { unauffaellig: "mdi:check", hinweis: "mdi:exclamation" };

const MARKE = { unauffaellig: "unauffällig", hinweis: "Hinweis", sammelt: "sammelt", braucht_daten: "nicht eingerichtet" };

export const BefundMixin = (Basis) =>
  class extends Basis {
    _befundLaden() {
      if (this._befundLaeuft) return;
      this._befundLaeuft = this._hass
        .callWS({ type: "heatnexus/befund" })
        .then((daten) => {
          this._befund = (daten && daten.anlagen) || {};
          this._befundZeit = Date.now();
        })
        .catch((err) => {
          console.warn("HeatNexus: Befund konnte nicht geladen werden", err);
          this._befund = {};
        })
        .finally(() => {
          this._befundLaeuft = null;
          if (this._reiter === "befund") {
            this._gebaut = false;
            this._zeichnen();
          } else if (this._reiter === "automatik" && !this._automatikBearbeitet && !this.shadowRoot.querySelector(".schleier")) {
            this._automatikNeuZeichnen();
          }
        });
    }

    /** Ganze Zahlen ohne Nachkommastelle, sonst wie in der Automatik. */
    _befundZahl(wert, stellen = 1) {
      return Number.isInteger(Number(wert)) ? zahl(wert, 0) : zahl(wert, stellen);
    }

    /** Karten für das Raster: zuerst die Lage, dann je Abschnitt die Befunde. */
    _befundReiter(anlage) {
      if (this._befund === undefined) {
        this._befundLaden();
        return [{ id: "befund", titel: "Befund", knoten: this._befundHinweis("Der Befund lädt …") }];
      }
      if (Date.now() - (this._befundZeit || 0) > BEFUND_TAKT_MS) this._befundLaden();
      const stand = this._befund[anlage && anlage.id];
      if (!stand) return [];
      const karten = [{ id: "befund-lage", titel: "Befund", knoten: this._befundLage(stand), breite: 2 }];
      const offen = [];
      stand.abschnitte.forEach((abschnitt) => {
        if (abschnitt.art === "waermeerzeuger") {
          karten.push({ id: "befund-waermeerzeuger", titel: "Wärmeerzeuger", knoten: this._befundVerweis() });
          return;
        }
        abschnitt.befunde.forEach((befund) => {
          if (befund.wert === null || befund.wert === undefined) {
            offen.push({ abschnitt, b: befund });
            return;
          }
          karten.push({
            id: `befund:${abschnitt.kennung}:${befund.art}`,
            titel: this._t(TITEL[befund.art] || befund.art),
            knoten: this._befundKarte(abschnitt, befund),
          });
        });
      });
      if (offen.length) karten.push({ id: "befund-offen", titel: "Noch ohne Ergebnis", knoten: this._befundOffen(offen), breite: 2 });
      return karten;
    }

    /** Befunde ohne Wert stehen gesammelt in einer Kachel, je Zeile mit dem Grund. */
    _befundOffen(offen) {
      const karte = this._karte(this._t("Noch ohne Ergebnis"));
      const liste = knoten("div", "befund-offen");
      offen.forEach(({ abschnitt, b }) => {
        const zeile = knoten("div");
        zeile.append(
          knoten("span", null, `${this._t(TITEL[b.art] || b.art)} · ${abschnitt.titel}`),
          knoten("span", "befund-leise", this._befundGrund(b))
        );
        liste.appendChild(zeile);
      });
      karte.appendChild(liste);
      if (offen.some(({ b }) => b.grund === "raeume" || b.grund === "automatik")) karte.appendChild(this._befundZurAutomatik());
      return karte;
    }

    _befundHinweis(text) {
      const karte = this._karte(this._t("Befund"));
      karte.appendChild(this._hinweisKnoten(this._t(text)));
      return karte;
    }

    /** Kopfkarte: Ring mit einem Teil je Befund, daneben die Zahl je Stand mit den Namen. */
    _befundLage(stand) {
      const l = stand.lage;
      const karte = this._karte(this._t("Befund"));
      const seit = l.seit ? l.seit.split("-").reverse().join(".") : null;
      const kopf = karte.querySelector(".kartenkopf");
      const datum = knoten("span", "befund-seit", seit ? this._tMit("Daten seit {datum}", { datum: seit }) : this._t("Sammelt seit dem Start"));
      if (kopf) kopf.appendChild(datum);
      else karte.appendChild(datum);
      const alle = stand.abschnitte.flatMap((a) => a.befunde);
      const namen = (stati) => [...new Set(alle.filter((b) => stati.includes(b.status)).map((b) => this._t(KURZ[b.art] || b.art)))].join(" · ");
      const gruppen = [
        ["gut", l.unauffaellig, "unauffällig", namen(["unauffaellig"]), "Nichts gemessen"],
        ["hinweis", l.hinweise, "Hinweise", namen(["hinweis"]), "Nichts Auffälliges gemessen"],
        ["offen", l.sammelt + l.braucht_daten, "noch ohne Ergebnis", namen(["sammelt", "braucht_daten"]), "Alle Befunde haben einen Wert"],
      ];
      const inhalt = knoten("div", "befund-lage");
      inhalt.appendChild(this._befundRing(alle, l.befunde));
      const liste = knoten("div", "befund-gruppen");
      gruppen.forEach(([klasse, anzahl, titel, text, leer]) => {
        const zeile = knoten("div", `befund-gruppe ${anzahl ? klasse : "null"}`);
        const rechts = knoten("div");
        rechts.append(knoten("div", "befund-gruppentitel", this._t(titel)), knoten("div", "befund-leise", text || this._t(leer)));
        zeile.append(knoten("span", "befund-anzahl", String(anzahl)), rechts);
        liste.appendChild(zeile);
      });
      inhalt.appendChild(liste);
      karte.appendChild(inhalt);
      const fuss = knoten("div", "befund-schutz");
      fuss.append(ikone("mdi:shield-check-outline"), knoten("span", null, this._t("Nur Beobachtung: gemessene Werte, keine Empfehlung. Der Befund ändert nichts an der Anlage.")));
      karte.appendChild(fuss);
      return karte;
    }

    /** Ein Ring aus je einem Bogen pro Befund, in der Farbe seines Stands. */
    _befundRing(befunde, anzahl) {
      const s = svg("svg", { viewBox: "0 0 120 120", class: "befund-ring" });
      const n = Math.max(1, befunde.length);
      const luecke = n > 1 ? 4 : 0;
      befunde.forEach((b, i) => {
        const von = (i * 360) / n + luecke / 2;
        const bis = ((i + 1) * 360) / n - luecke / 2;
        s.appendChild(svg("path", { d: bogen(60, 60, 48, von, bis), class: `bogen ${b.status}` }));
      });
      s.append(
        svg("text", { x: 60, y: 62, "text-anchor": "middle", class: "ring-zahl" }, String(anzahl)),
        svg("text", { x: 60, y: 82, "text-anchor": "middle", class: "ring-text" }, this._t("Befunde"))
      );
      return s;
    }

    /**
     * Die Befunde eines Heizkreises im Reiter Automatik: links Zahl und Stand je Befund,
     * rechts die Liste. Eine Zeile öffnet den Verlauf ihres Sensors.
     */
    _befundKompakt(kreis) {
      if (this._befund === undefined || Date.now() - (this._befundZeit || 0) > BEFUND_TAKT_MS) this._befundLaden();
      const stand = (this._befund || {})[kreis.anlage_id];
      if (!stand) return null;
      const befunde = stand.abschnitte.filter((a) => a.kennung === kreis.heizkreis).flatMap((a) => a.befunde);
      if (!befunde.length) return null;
      const kachel = knoten("div", "automatik-wert breit befund-kompakt");
      const kopf = knoten("div", "befund-kompakt-kopf");
      const seit = stand.lage.seit ? this._tMit("Daten seit {datum}", { datum: stand.lage.seit.split("-").reverse().join(".") }) : "";
      const alle = knoten("button", "befund-sprung", this._t("Alle Befunde"));
      alle.type = "button";
      alle.addEventListener("click", () => this._befundOeffnen());
      kopf.append(knoten("div", "titel", this._t("Befund")), knoten("span", "befund-leise", seit), alle);
      const inhalt = knoten("div", "befund-kompakt-inhalt");
      const liste = knoten("div", "befund-liste");
      befunde.forEach((b) => liste.appendChild(this._befundZeile(b)));
      inhalt.append(this._befundUebersicht(befunde), liste);
      kachel.append(kopf, inhalt, this._befundMerkmale());
      return kachel;
    }

    /** Große Zahl, ein Kästchen je Befund und die Zählung nach Stand. */
    _befundUebersicht(befunde) {
      const links = knoten("div", "befund-uebersicht");
      const gross = knoten("div", "befund-gross");
      gross.append(knoten("span", "zahl", String(befunde.length)), knoten("span", "befund-leise", this._t("Befunde")));
      const kaesten = knoten("div", "befund-kaesten");
      befunde.forEach((b) => {
        const kasten = knoten("span", `befund-kasten ${b.status}`);
        kasten.title = this._t(TITEL[b.art] || b.art);
        kasten.appendChild(ikone(SYMBOL[b.status] || "mdi:clock-outline"));
        kaesten.appendChild(kasten);
      });
      const anzahl = (stati) => befunde.filter((b) => stati.includes(b.status)).length;
      const zaehlung = knoten("div", "befund-zaehlung");
      [
        ["gut", "unauffällig", anzahl(["unauffaellig"])],
        ["hinweis", "Hinweise", anzahl(["hinweis"])],
        ["offen", "noch ohne Ergebnis", anzahl(["sammelt", "braucht_daten"])],
      ].forEach(([klasse, text, n]) => zaehlung.append(knoten("span", null, this._t(text)), knoten("span", `anzahl ${n ? klasse : "null"}`, String(n))));
      links.append(gross, kaesten, zaehlung);
      return links;
    }

    _befundZeile(b) {
      const zeile = knoten("button", `befund-zeile ${b.status}`);
      zeile.type = "button";
      const wert = b.wert === null || b.wert === undefined ? "–" : `${this._befundZahl(b.wert)} ${b.einheit}`.trim();
      zeile.append(
        knoten("i", "punkt"),
        knoten("span", "name", this._t(TITEL[b.art] || b.art)),
        knoten("span", "wert", wert),
        knoten("span", `befund-marke ${b.status}`, this._t(MARKE[b.status] || b.status))
      );
      if (b.entity) this._klickbar(zeile, b.entity);
      else zeile.addEventListener("click", () => this._befundOeffnen());
      return zeile;
    }

    /** Drei Merkmale des Befunds als Leiste. */
    _befundMerkmale() {
      const leiste = knoten("div", "befund-merkmale");
      [
        ["mdi:chart-bar", "Gemessene Werte"],
        ["mdi:cancel", "Keine Empfehlung"],
        ["mdi:lock-outline", "Ändert nichts an der Anlage"],
      ].forEach(([symbol, text]) => {
        const merkmal = knoten("span", "befund-merkmal");
        merkmal.append(ikone(symbol), knoten("span", null, this._t(text)));
        leiste.appendChild(merkmal);
      });
      return leiste;
    }

    _befundOeffnen() {
      this._reiter = "befund";
      this._gebaut = false;
      this._zeichnen();
    }

    _befundVerweis() {
      const karte = this._karte(this._t("Wärmeerzeuger"));
      karte.appendChild(
        this._hinweisKnoten(this._t("Diese Anlage hat keinen eigenen Kessel. Kessel und Energie stehen bei der Anlage, die die Wärme liefert."))
      );
      return karte;
    }

    _befundKarte(abschnitt, b) {
      const karte = this._karte(this._t(TITEL[b.art] || b.art), this._t(HILFE[b.art] || ""));
      karte.classList.add("befund-karte", `befund-${b.status}`);
      const kopf = knoten("div", "befund-kopf");
      kopf.appendChild(knoten("span", "befund-abschnitt", `${this._t(ABSCHNITT[abschnitt.art] || "")} · ${abschnitt.titel}`));
      const marke = { unauffaellig: "unauffällig", hinweis: "Hinweis", sammelt: "sammelt" }[b.status];
      if (marke) kopf.appendChild(knoten("span", `befund-marke ${b.status}`, this._t(marke)));
      karte.appendChild(kopf);
      if (b.art === "heizgrenze") return this._befundPruefung(karte, b);
      const wert = knoten("div", "befund-wert");
      const zahlUndEinheit = knoten("span", "befund-zahl");
      zahlUndEinheit.append(knoten("span", "zahl", this._befundZahl(b.wert)), knoten("span", "einheit", b.einheit));
      wert.append(this._klickbar(zahlUndEinheit, b.entity), knoten("span", "neben", this._befundBeisatz(b)));
      karte.appendChild(wert);
      const bild = this._befundBild(b);
      if (bild) karte.appendChild(bild);
      const vergleich = this._befundVergleich(b);
      if (vergleich) karte.appendChild(vergleich);
      karte.appendChild(knoten("div", "befund-fuss", this._tMit("Verlässlichkeit: {stufe}", { stufe: this._befundStufe(b.stufe) })));
      return karte;
    }

    /** Die Heizgrenze als Prüfung: eingestellt gegen gemessen, ohne große Zahl. */
    _befundPruefung(karte, b) {
      const v = b.vergleich || {};
      const ab = (b.angaben || {}).abweichung;
      const zeile = knoten("div", "befund-pruefung");
      const gemessen = knoten("span", null, this._tMit("geheizt ab {wert} °C im Tagesmittel", { wert: this._befundZahl(b.wert) }));
      zeile.append(
        knoten("span", null, this._tMit("Eingestellt {wert} °C", { wert: this._befundZahl(v.eingestellt) })),
        this._klickbar(gemessen, b.entity)
      );
      karte.appendChild(zeile);
      let urteil = this._t("Ohne eingestellte Heizgrenze kein Vergleich.");
      if (ab !== undefined && ab !== null) {
        const k = this._befundZahl(Math.abs(ab));
        if (b.status === "hinweis") urteil = this._tMit(ab < 0 ? "{k} K unter der Einstellung" : "{k} K über der Einstellung", { k });
        else urteil = this._t("passt zur Einstellung");
      }
      karte.appendChild(knoten("div", "befund-leise", urteil));
      return karte;
    }

    _befundStufe(stufe) {
      return this._t({ sammelt: "sammelt", vorlaeufig: "vorläufig", belastbar: "belastbar" }[stufe] || stufe);
    }

    /** Räume und Hausmodell entstehen in der Automatik; der Knopf führt dorthin. */
    _befundZurAutomatik() {
      const taste = knoten("button", "befund-sprung", this._t("Zur Automatik"));
      taste.type = "button";
      taste.addEventListener("click", () => {
        this._reiter = "automatik";
        this._gebaut = false;
        this._zeichnen();
      });
      return taste;
    }

    _befundGrund(b) {
      if (b.grund === "raeume") return this._t("Braucht Räume. Die Räume werden in der Automatik gewählt.");
      if (b.grund === "automatik") return this._t("Das Hausmodell entsteht, sobald für diesen Heizkreis die Automatik eingerichtet ist. Der Modus „Beobachten“ genügt; geschrieben wird dann nichts.");
      if (b.grund === "kessel") return this._t("Braucht die Zähler des Kessels.");
      if (b.grund === "energie") return this._t("Braucht Kesselleistung und Nennleistung.");
      return this._t("Sammelt noch Tage.");
    }

    _befundBeisatz(b) {
      const a = b.angaben || {};
      if (b.art === "laufzeit" && a.starts_tag !== null && a.starts_tag !== undefined) {
        return this._tMit("je Start · {n} Starts am Tag", { n: this._befundZahl(a.starts_tag) });
      }
      return this._t(
        {
          waermespeicher: "Zeitkonstante",
          raeume: "der Heizstunden am Ziel oder darüber",
          naechte: "am Morgen über dem Absenkziel",
          vorlauf: "der Heizstunden mehr als 3 K unter Soll",
          laufzeit: "je Start",
          energie: "je Heizgradtag",
        }[b.art] || ""
      );
    }

    _befundVergleich(b) {
      const v = b.vergleich || {};
      const a = b.angaben || {};
      const grad = (wert) => `${this._befundZahl(wert)} °C`;
      const zeilen = [
        [v.eingestellt, "Eingestellt an der Steuerung (TA Heizbetrieb)", grad],
        [v.rechengrenze, "Heizgrenze der Gradtagzahl (VDI 3807, fester Rechenwert)", grad],
        [v.ta_absenk, "Heizgrenze Absenkbetrieb (TA Absenkbetrieb)", grad],
        [a.sonne, "Sonne wärmt bei vollem Sonnenschein", (w) => this._tMit("+{k} K je Stunde", { k: this._befundZahl(w) })],
        [a.gesamt_h_je_start, "Seit Inbetriebnahme", (w) => this._tMit("{h} h je Start", { h: this._befundZahl(w) })],
        [a.sockel, "Sockel ohne Heizen", (w) => this._tMit("{kwh} kWh am Tag", { kwh: this._befundZahl(w) })],
        [a.gerade, "Mehr Wärme je Kelvin kälter", (w) => `${this._befundZahl(w)} kWh`],
        [a.ohne_gradtag || null, "Heiztage ohne Gradtag nach VDI 3807", (w) => String(w)],
      ].filter(([wert]) => wert !== null && wert !== undefined);
      if (!zeilen.length) return null;
      const liste = knoten("div", "befund-vergleich");
      zeilen.forEach(([wert, text, format]) => liste.append(knoten("span", null, this._t(text)), knoten("span", null, format(wert))));
      return liste;
    }

    _befundBild(b) {
      const a = b.angaben || {};
      if (b.art === "waermespeicher" && a.nacht) return this._bildNacht(b.wert, a.nacht);
      if (b.art === "raeume" && a.je_raum) return this._bildRaeume(a.je_raum);
      if (b.art === "naechte" && (a.naechte || []).length) return this._bildPunkte(a.naechte);
      if (b.art === "vorlauf" && (a.je_tag || []).length) {
        return this._bildBalken(a.je_tag, "Stunden unter Soll je Heiztag", "warn", b.quelle, (d, n) => this._tMit("{datum}: {h} h unter Soll", { datum: kurzdatum(d), h: n }));
      }
      if (b.art === "laufzeit" && (a.je_tag || []).length) {
        return this._bildBalken(a.je_tag, "Betriebsstunden je Tag", "an", b.quelle, (d, h) => this._tMit("{datum}: {h} Betriebsstunden", { datum: kurzdatum(d), h: this._befundZahl(h) }));
      }
      if (b.art === "energie" && (a.punkte || []).length) return this._bildSignatur(a.punkte, b.quelle);
      return null;
    }

    /** Ein Feld für ein Bild; mit `quelle` öffnet die Beschriftung den Verlauf des Sensors dahinter. */
    _befundFeld(beschriftung, quelle = null) {
      const feld = knoten("div", "befund-feld");
      if (beschriftung) {
        const kopf = knoten("div", "befund-leise befund-feldkopf", this._t(beschriftung));
        if (quelle) kopf.prepend(ikone("mdi:chart-line"));
        feld.appendChild(this._klickbar(kopf, quelle));
      }
      feld.anzeige = knoten("div", "befund-ablesen befund-leise", this._t("Antippen zeigt den Wert."));
      return feld;
    }

    /** Antippen oder Überfahren schreibt den Wert eines Bildteils unter das Bild. */
    _befundAblesbar(feld, element, text) {
      element.classList.add("ablesbar");
      const zeigen = () => {
        feld.anzeige.textContent = text;
        feld.querySelectorAll(".gewaehlt").forEach((e) => e.classList.remove("gewaehlt"));
        element.classList.add("gewaehlt");
      };
      element.addEventListener("click", zeigen);
      element.addEventListener("mouseenter", zeigen);
    }

    /** Ein Punkt mit größerer, unsichtbarer Trefferfläche für den Finger. */
    _befundPunkt(feld, cx, cy, klasse, text, r = 4.5) {
      const g = svg("g");
      g.append(svg("circle", { cx, cy, r: 11, class: "treffer" }), svg("circle", { cx, cy, r, class: klasse }));
      this._befundAblesbar(feld, g, text);
      return g;
    }

    _befundFertig(feld, bild) {
      feld.append(bild, feld.anzeige);
      return feld;
    }

    _bildNacht(tau, nacht) {
      const feld = this._befundFeld();
      const kuehler = this._befundZahl(nacht.von - nacht.nach);
      feld.appendChild(
        knoten("div", "befund-leise", this._tMit("Ohne Heizung ab jetzt: nach {h} h {k} K kühler ({von} → {nach} °C), bei {aussen} °C außen", {
          h: nacht.stunden,
          k: kuehler,
          von: this._befundZahl(nacht.von),
          nach: this._befundZahl(nacht.nach),
          aussen: this._befundZahl(nacht.aussen),
        }))
      );
      const f = (t) => nacht.aussen + (nacht.von - nacht.aussen) * Math.exp(-t / tau);
      const unten = f(24) - 0.5;
      const oben = nacht.von + 0.5;
      const x = (t) => 20 + (t / 24) * 420;
      const y = (v) => 10 + ((oben - v) / (oben - unten)) * 80;
      const s = svg("svg", { viewBox: "0 0 460 110" });
      let pfad = "";
      for (let t = 0; t <= 24; t += 0.5) pfad += `${t ? "L" : "M"}${x(t)} ${y(f(t))}`;
      s.append(
        svg("path", { d: pfad, class: "linie" }),
        svg("circle", { cx: x(8), cy: y(f(8)), r: 5, class: "punkt" }),
        svg("text", { x: x(8) + 10, y: y(f(8)) - 8 }, `${this._befundZahl(f(8))} °C`),
        svg("text", { x: 20, y: 106 }, this._t("jetzt")),
        svg("text", { x: x(8), y: 106, "text-anchor": "middle" }, "+8 h"),
        svg("text", { x: 440, y: 106, "text-anchor": "end" }, "+24 h")
      );
      for (let t = 0; t <= 24; t += 2) {
        const zeit = t ? `+${t} h` : this._t("jetzt");
        s.appendChild(this._befundPunkt(feld, x(t), y(f(t)), "stelle", this._tMit("{zeit}: {wert} °C", { zeit, wert: this._befundZahl(f(t)) }), 3));
      }
      return this._befundFertig(feld, s);
    }

    _bildRaeume(jeRaum) {
      const feld = this._befundFeld();
      const klassen = { unter: "unter Ziel", am: "am Ziel ±0,5 K", leicht: "0,5–1 K darüber", ueber: "über 1 K darüber" };
      Object.entries(jeRaum).forEach(([kennung, w]) => {
        const zustand = this._hass.states[kennung];
        const name = (zustand && zustand.attributes.friendly_name) || kennung;
        const zeile = knoten("div", "befund-raum");
        const stapel = knoten("div", "befund-stapel");
        ["unter", "am", "leicht", "ueber"].forEach((klasse) => {
          if (!w[klasse]) return;
          const teil = knoten("span", klasse);
          teil.style.width = `${w[klasse]}%`;
          this._befundAblesbar(feld, teil, this._tMit("{raum}: {p} % {klasse}", { raum: name, p: w[klasse], klasse: this._t(klassen[klasse]) }));
          stapel.appendChild(teil);
        });
        zeile.append(knoten("span", null, name), stapel, knoten("span", "befund-leise", `${w.stunden} h`));
        feld.appendChild(zeile);
      });
      const legende = knoten("div", "befund-legende");
      Object.entries(klassen).forEach(([klasse, text]) => {
        const eintrag = knoten("span", null, this._t(text));
        eintrag.prepend(knoten("i", klasse));
        legende.appendChild(eintrag);
      });
      return this._befundFertig(feld, legende);
    }

    _bildPunkte(naechte) {
      const feld = this._befundFeld("Raum am Morgen minus Absenkziel, je Nacht");
      const s = svg("svg", { viewBox: "0 0 460 100" });
      const x = (i) => 40 + (i * 400) / Math.max(1, naechte.length - 1);
      const y = (v) => 50 - Math.max(-2.5, Math.min(2.5, v)) * 16;
      s.append(
        svg("rect", { x: 30, y: y(0.5), width: 420, height: y(-0.5) - y(0.5), class: "zone" }),
        svg("line", { x1: 30, x2: 450, y1: y(0), y2: y(0), class: "marke" }),
        svg("text", { x: 26, y: y(0) + 4, "text-anchor": "end" }, this._t("Ziel"))
      );
      naechte.forEach(([datum, wert], i) => {
        const text = this._tMit("{datum}: {wert} K", { datum: kurzdatum(datum), wert: (wert > 0 ? "+" : "") + this._befundZahl(wert) });
        s.appendChild(this._befundPunkt(feld, x(i), y(wert), Math.abs(wert) <= 0.5 ? "punkt an" : "punkt", text));
      });
      return this._befundFertig(feld, s);
    }

    /** Balken je Tag; `eintraege` sind [Datum, Wert], `text` beschreibt einen Balken. */
    _bildBalken(eintraege, beschriftung, klasse, quelle, text) {
      const feld = this._befundFeld(beschriftung, quelle);
      const s = svg("svg", { viewBox: "0 0 460 80" });
      const werte = eintraege.map(([, wert]) => wert || 0);
      const hoch = Math.max(1, ...werte);
      const breite = 420 / werte.length;
      werte.forEach((wert, i) => {
        const h = (wert / hoch) * 60;
        const g = svg("g");
        g.append(
          svg("rect", { x: 30 + i * breite, y: 4, width: breite, height: 64, class: "treffer" }),
          svg("rect", { x: 30 + i * breite + 0.5, y: 68 - h, width: Math.max(1, breite - 1), height: Math.max(wert ? 1.5 : 0, h), rx: 1.5, class: `balken ${klasse}` })
        );
        this._befundAblesbar(feld, g, text(eintraege[i][0], wert));
        s.appendChild(g);
      });
      s.append(svg("line", { x1: 30, x2: 450, y1: 68, y2: 68, class: "achse" }), svg("text", { x: 26, y: 14, "text-anchor": "end" }, this._befundZahl(hoch, 0)));
      return this._befundFertig(feld, s);
    }

    _bildSignatur(punkte, quelle) {
      const feld = this._befundFeld("Wärme je Tag gegen Außentemperatur · Wochenmittel", quelle);
      const s = svg("svg", { viewBox: "0 0 460 150" });
      const ats = punkte.map(([at]) => at);
      const lo = Math.floor(Math.min(...ats));
      const hi = Math.ceil(Math.max(...ats)) || lo + 1;
      const kwhMax = Math.max(1, ...punkte.map(([, k]) => k));
      const x = (v) => 40 + ((v - lo) / Math.max(1, hi - lo)) * 400;
      const y = (v) => 128 - (v / kwhMax) * 112;
      s.appendChild(svg("line", { x1: 40, x2: 440, y1: 128, y2: 128, class: "achse" }));
      punkte.forEach(([at, kwh]) => {
        const text = `${this._befundZahl(at)} °C: ${this._tMit("{kwh} kWh am Tag", { kwh: this._befundZahl(kwh) })}`;
        s.appendChild(this._befundPunkt(feld, x(at), y(kwh), "punkt an", text, 4));
      });
      s.append(
        svg("text", { x: 40, y: 144 }, `${lo} °C`),
        svg("text", { x: 440, y: 144, "text-anchor": "end" }, `${hi} °C`),
        svg("text", { x: 34, y: 16, "text-anchor": "end" }, `${this._befundZahl(kwhMax, 0)} kWh`)
      );
      return this._befundFertig(feld, s);
    }
  };
