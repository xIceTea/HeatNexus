/**
 * Reiter „Befund“: gemessene Kennwerte je Anlage, ohne Empfehlung und ohne Bedienung.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin. Die Zahlen rechnet der
 * Server (`befund/`), hier entstehen nur Text und Bild.
 */

const NS = "http://www.w3.org/2000/svg";

function knoten(tag, klasse, text) {
  const el = document.createElement(tag);
  if (klasse) el.className = klasse;
  if (text !== undefined && text !== null) el.textContent = text;
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
  heizgrenze: "Tatsächliche Heizgrenze",
  raeume: "Räume erreichen ihr Ziel",
  naechte: "Übergangszeit nachts",
  vorlauf: "Vorlauf erreicht sein Soll",
  laufzeit: "Starts und Laufzeit",
  energie: "Energie je Heizgradtag",
};

const HILFE = {
  waermespeicher:
    "Gemessen wird, wie schnell die Räume ohne Heizung zur Außentemperatur hin abkühlen. Grundlage ist die Zeitkonstante aus Wärmespeicherfähigkeit und Wärmeverlust, wie in DIN V 18599-2. Eine Einordnung wie leicht oder schwer erscheint erst mit belegter Skala.",
  heizgrenze:
    "Je Tag zählt das Mittel der Außentemperatur und ob der Heizkreis mindestens zwei Stunden geheizt hat. Die Heizgrenze ist die Temperatur, an der Heiztage und heizfreie Tage kippen. Die Rechengrenze nach VDI 3807 ist eine Konvention für Gradtagzahlen, kein Zielwert.",
  raeume:
    "Gezählt werden Heizstunden ohne Eingriff. Thermostate drosseln, sobald ein Raum warm ist; eine zu hohe Heizkurve zeigt sich deshalb kaum. Sonne und Öfen sind nicht herausgerechnet. Laut Windhager-Anleitung hilft bei zu hoher oder zu niedriger Raumtemperatur: Auslegungstemperatur und/oder Fußpunkt korrigieren oder Behaglichkeit.",
  naechte:
    "In Nächten mit 5 bis 15 °C außen zählt der Raum am Ende der Absenkung gegen das Absenkziel. Laut Windhager-Anleitung hilft bei zu hoher oder zu niedriger Raumtemperatur nachts in der Übergangszeit: Heizgrenze Absenkbetrieb verringern bzw. erhöhen.",
  vorlauf:
    "Gezählt werden Heizstunden, in denen der Vorlauf mehr als 3 K unter seinem Soll bleibt. Mögliche Gründe: Puffer leer, Kessel nicht in Betrieb, Mischer am Anschlag, Wärme über eine Fernleitung.",
  laufzeit:
    "Die Zähler der Steuerung für Brennerstarts und Betriebsstunden. Verglichen wird nur mit dem Kessel selbst; für die Laufzeit je Start gibt es weder Norm noch Herstellerangabe.",
  energie:
    "Erzeugte Wärme aus Kesselleistung und Nennleistung, ohne den Sockel an Tagen ohne Heizen. Die Gradtagzahl nach VDI 3807 rechnet das Wetter heraus; so lassen sich Jahre vergleichen. Der Wert gilt für die ganze Anlage.",
};

const ABSCHNITT = { haus: "Haus", heizkreis: "Heizkreis", kessel: "Kessel" };

export const BefundMixin = (Basis) =>
  class extends Basis {
    _befundLaden() {
      if (this._befundLaeuft) return;
      this._befundLaeuft = this._hass
        .callWS({ type: "heatnexus/befund" })
        .then((daten) => {
          this._befund = (daten && daten.anlagen) || {};
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
          }
        });
    }

    _befundZahl(wert, stellen = 1) {
      if (wert === null || wert === undefined) return "–";
      return Number(wert).toLocaleString(this._sprache || "de", { maximumFractionDigits: stellen });
    }

    /** Karten für das Raster: zuerst die Lage, dann je Abschnitt die Befunde. */
    _befundReiter(anlage) {
      if (this._befund === undefined) {
        this._befundLaden();
        return [{ id: "befund", titel: "Befund", knoten: this._befundHinweis("Der Befund lädt …") }];
      }
      const stand = this._befund[anlage && anlage.id];
      if (!stand) return [];
      const karten = [{ id: "befund-lage", titel: "Befund", knoten: this._befundLage(stand), breite: 2 }];
      stand.abschnitte.forEach((abschnitt) => {
        if (abschnitt.art === "waermeerzeuger") {
          karten.push({ id: "befund-waermeerzeuger", titel: "Wärmeerzeuger", knoten: this._befundVerweis(), breite: 2 });
          return;
        }
        abschnitt.befunde.forEach((befund) => {
          karten.push({
            id: `befund:${abschnitt.kennung}:${befund.art}`,
            titel: this._t(TITEL[befund.art] || befund.art),
            knoten: this._befundKarte(abschnitt, befund),
          });
        });
      });
      return karten;
    }

    _befundHinweis(text) {
      const karte = this._karte(this._t("Befund"));
      karte.appendChild(this._hinweisKnoten(this._t(text)));
      return karte;
    }

    _befundLage(stand) {
      const l = stand.lage;
      const karte = this._karte(this._t("Befund"));
      const zeile = knoten("div", "befund-lage");
      zeile.appendChild(
        knoten(
          "span",
          null,
          this._tMit("{n} Befunde · {u} unauffällig · {h} Hinweise · {s} sammeln", {
            n: l.befunde,
            u: l.unauffaellig,
            h: l.hinweise,
            s: l.sammelt + l.braucht_daten,
          })
        )
      );
      const seit = l.seit ? new Date(l.seit).toLocaleDateString(this._sprache || "de") : null;
      zeile.appendChild(knoten("span", null, seit ? this._tMit("Daten seit {datum}", { datum: seit }) : this._t("Sammelt seit dem Start")));
      karte.appendChild(zeile);
      karte.appendChild(knoten("div", "befund-leise", this._t("Gemessene Werte, keine Empfehlung. Der Befund ändert nichts an der Anlage.")));
      return karte;
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
      karte.classList.add("befund-karte", b.status);
      const kopf = knoten("div", "befund-kopf");
      kopf.appendChild(knoten("span", "befund-abschnitt", `${this._t(ABSCHNITT[abschnitt.art] || "")} · ${abschnitt.titel}`));
      const marke = { unauffaellig: "unauffällig", hinweis: "Hinweis", sammelt: "sammelt" }[b.status];
      if (marke) kopf.appendChild(knoten("span", `befund-marke ${b.status}`, this._t(marke)));
      karte.appendChild(kopf);
      if (b.status === "braucht_daten" || b.wert === null || b.wert === undefined) {
        karte.appendChild(this._hinweisKnoten(this._befundGrund(b)));
        return karte;
      }
      const wert = knoten("div", "befund-wert");
      wert.append(knoten("span", "zahl", this._befundZahl(b.wert)), knoten("span", "einheit", b.einheit), knoten("span", "neben", this._befundBeisatz(b)));
      karte.appendChild(wert);
      const bild = this._befundBild(b);
      if (bild) karte.appendChild(bild);
      const vergleich = this._befundVergleich(b);
      if (vergleich) karte.appendChild(vergleich);
      karte.appendChild(knoten("div", "befund-fuss", this._tMit("Verlässlichkeit: {stufe}", { stufe: this._befundStufe(b.stufe) })));
      return karte;
    }

    _befundStufe(stufe) {
      return this._t({ sammelt: "sammelt", vorlaeufig: "vorläufig", belastbar: "belastbar" }[stufe] || stufe);
    }

    _befundGrund(b) {
      if (b.grund === "raeume") return this._t("Braucht Räume. Die Räume werden in der Automatik gewählt.");
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
          waermespeicher: "hält die Wärme",
          heizgrenze: "Tagesmittel",
          raeume: "der Heizstunden am Ziel oder darüber",
          naechte: "am Morgen über dem Absenkziel",
          vorlauf: "der Heizstunden unter Soll",
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
        [v.rechengrenze, "Rechengrenze nach VDI 3807", grad],
        [v.heizstunden_je_gt, "Heizstunden je Heizgradtag", (w) => `${this._befundZahl(w)} h`],
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
      if (b.art === "heizgrenze" && (a.klassen || []).length) return this._bildKlassen(a.klassen, b.wert);
      if (b.art === "raeume" && a.je_raum) return this._bildRaeume(a.je_raum);
      if (b.art === "naechte" && (a.naechte || []).length) return this._bildPunkte(a.naechte);
      if (b.art === "vorlauf" && (a.je_tag || []).length) return this._bildBalken(a.je_tag.map(([, n]) => n), "Stunden unter Soll je Heiztag", "warn");
      if (b.art === "laufzeit" && (a.je_tag || []).length) return this._bildBalken(a.je_tag.map(([, h]) => h || 0), "Betriebsstunden je Tag", "an");
      if (b.art === "energie" && (a.punkte || []).length) return this._bildSignatur(a.punkte);
      return null;
    }

    _befundFeld(beschriftung) {
      const feld = knoten("div", "befund-feld");
      if (beschriftung) feld.appendChild(knoten("div", "befund-leise", this._t(beschriftung)));
      return feld;
    }

    _bildNacht(tau, nacht) {
      const feld = this._befundFeld();
      const kuehler = this._befundZahl(nacht.von - nacht.nach);
      feld.appendChild(
        knoten("div", "befund-leise", this._tMit("Ohne Heizung heute Nacht: nach {h} h {k} K kühler ({von} → {nach} °C)", {
          h: nacht.stunden,
          k: kuehler,
          von: this._befundZahl(nacht.von),
          nach: this._befundZahl(nacht.nach),
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
      feld.appendChild(s);
      return feld;
    }

    _bildKlassen(klassen, grenze) {
      const feld = this._befundFeld("Anteil der Heiztage je Außentemperatur");
      const s = svg("svg", { viewBox: "0 0 460 130" });
      const lo = 10;
      const hi = 25;
      const x = (v) => 30 + ((v - lo) / (hi - lo)) * 410;
      const y = (p) => 110 - p * 90;
      klassen
        .filter(([k]) => k >= lo && k < hi)
        .forEach(([k, n, h]) => {
          const p = n ? h / n : 0;
          s.appendChild(svg("rect", { x: x(k) + 2, y: y(p), width: 410 / (hi - lo) - 4, height: Math.max(1.5, 110 - y(p)), rx: 3, class: p > 0.5 ? "balken an" : "balken" }));
        });
      if (grenze !== null && grenze !== undefined) s.appendChild(svg("line", { x1: x(grenze), x2: x(grenze), y1: 8, y2: 110, class: "marke" }));
      [10, 15, 20, 25].forEach((v) => s.appendChild(svg("text", { x: x(v), y: 126, "text-anchor": "middle" }, `${v} °C`)));
      feld.appendChild(s);
      return feld;
    }

    _bildRaeume(jeRaum) {
      const feld = this._befundFeld();
      Object.entries(jeRaum).forEach(([kennung, w]) => {
        const zustand = this._hass.states[kennung];
        const name = (zustand && zustand.attributes.friendly_name) || kennung;
        const zeile = knoten("div", "befund-raum");
        const stapel = knoten("div", "befund-stapel");
        ["unter", "am", "leicht", "ueber"].forEach((klasse) => {
          if (!w[klasse]) return;
          const teil = knoten("span", klasse);
          teil.style.width = `${w[klasse]}%`;
          teil.title = `${w[klasse]} %`;
          stapel.appendChild(teil);
        });
        zeile.append(knoten("span", null, name), stapel, knoten("span", "befund-leise", `${w.stunden} h`));
        feld.appendChild(zeile);
      });
      const legende = knoten("div", "befund-legende");
      [
        ["unter", "unter Ziel"],
        ["am", "am Ziel ±0,5 K"],
        ["leicht", "0,5–1 K darüber"],
        ["ueber", "über 1 K darüber"],
      ].forEach(([klasse, text]) => {
        const eintrag = knoten("span", null, this._t(text));
        eintrag.prepend(knoten("i", klasse));
        legende.appendChild(eintrag);
      });
      feld.appendChild(legende);
      return feld;
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
      naechte.forEach(([, wert], i) => s.appendChild(svg("circle", { cx: x(i), cy: y(wert), r: 4.5, class: Math.abs(wert) <= 0.5 ? "punkt an" : "punkt" })));
      feld.appendChild(s);
      return feld;
    }

    _bildBalken(werte, beschriftung, klasse) {
      const feld = this._befundFeld(beschriftung);
      const s = svg("svg", { viewBox: "0 0 460 80" });
      const hoch = Math.max(1, ...werte);
      const breite = 420 / werte.length;
      werte.forEach((wert, i) => {
        const h = (wert / hoch) * 60;
        s.appendChild(svg("rect", { x: 30 + i * breite + 0.5, y: 68 - h, width: Math.max(1, breite - 1), height: Math.max(wert ? 1.5 : 0, h), rx: 1.5, class: `balken ${klasse}` }));
      });
      s.append(svg("line", { x1: 30, x2: 450, y1: 68, y2: 68, class: "achse" }), svg("text", { x: 26, y: 14, "text-anchor": "end" }, this._befundZahl(hoch, 0)));
      feld.appendChild(s);
      return feld;
    }

    _bildSignatur(punkte) {
      const feld = this._befundFeld("Wärme je Tag gegen Außentemperatur · Wochenmittel");
      const s = svg("svg", { viewBox: "0 0 460 150" });
      const ats = punkte.map(([at]) => at);
      const lo = Math.floor(Math.min(...ats));
      const hi = Math.ceil(Math.max(...ats)) || lo + 1;
      const kwhMax = Math.max(1, ...punkte.map(([, k]) => k));
      const x = (v) => 40 + ((v - lo) / Math.max(1, hi - lo)) * 400;
      const y = (v) => 128 - (v / kwhMax) * 112;
      s.appendChild(svg("line", { x1: 40, x2: 440, y1: 128, y2: 128, class: "achse" }));
      punkte.forEach(([at, kwh]) => s.appendChild(svg("circle", { cx: x(at), cy: y(kwh), r: 4, class: "punkt an" })));
      s.append(
        svg("text", { x: 40, y: 144 }, `${lo} °C`),
        svg("text", { x: 440, y: 144, "text-anchor": "end" }, `${hi} °C`),
        svg("text", { x: 34, y: 16, "text-anchor": "end" }, `${this._befundZahl(kwhMax, 0)} kWh`)
      );
      feld.appendChild(s);
      return feld;
    }
  };
