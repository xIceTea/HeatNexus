/**
 * Reiter „Automatik“: die Kennwerte als Skalen und die Heizgrenzen der Steuerung.
 *
 * Jede Kachel nennt ihre Zahlen mit Beschriftung und zeigt auf einer Skala,
 * wo die Schaltpunkte liegen. Teil der Oberfläche `heatnexus-panel.js`; als Mixin.
 */

import { kelvin, raumzeile, zahl } from "./automatik.js";

// So lange steht „übernommen ✓“ im Kasten der Heizgrenzen.
const GRENZEN_GESPEICHERT_MS = 4000;

/** Lage eines Werts auf einer Skala in Prozent, an den Rändern begrenzt. */
export function skalaProzent(wert, von, bis) {
  if (wert === null || wert === undefined || Number.isNaN(Number(wert)) || bis <= von) return null;
  const anteil = ((Number(wert) - von) / (bis - von)) * 100;
  return Math.round(Math.max(0, Math.min(100, anteil)) * 10) / 10;
}

/** Bereich der Außentemperatur-Skala: um die Heizgrenze der Steuerung, sonst 5 bis 25 °C. */
export function aussenBereich(grenze) {
  if (grenze === null || grenze === undefined || Number.isNaN(Number(grenze))) return [5, 25];
  return [Number(grenze) - 12, Number(grenze) + 8];
}

function knoten(tag, klasse = "", text = null) {
  const element = document.createElement(tag);
  if (klasse) element.className = klasse;
  if (text !== null) element.textContent = text;
  return element;
}

function vorhanden(wert) {
  return wert !== null && wert !== undefined && !Number.isNaN(Number(wert));
}

export const KennwerteMixin = (Basis) =>
  class extends Basis {
    _automatikKennwerte(kreis) {
      const raster = knoten("div", "automatik-werte");
      raster.append(this._kachelAussen(kreis), this._kachelSonne(kreis), this._kachelRaeume(kreis));
      return raster;
    }

    /** Eine Kachel: Titel, Zahlen mit Beschriftung, Skala und Fußzeilen. */
    _kachel(art, titel, zahlen, skala, fuss) {
      const kachel = knoten("div", `automatik-wert ${art}`);
      kachel.appendChild(knoten("div", "titel", this._t(titel)));
      const reihe = knoten("div", "werte");
      zahlen.forEach(([wert, beschriftung], stelle) => {
        const block = knoten("div", stelle ? "neben" : "haupt");
        block.append(knoten("div", "zahl", wert), knoten("div", "bez", this._t(beschriftung)));
        reihe.appendChild(block);
      });
      kachel.append(reihe, skala, ...fuss.filter(Boolean));
      return kachel;
    }

    /** Zonen als Flächen, Marken als Linien, Werte als Punkt oder Strich. */
    _skala({ von, bis, zonen = [], marken = [], punkte = [], achse = [], wertText = null }) {
      const rahmen = knoten("div", "automatik-skala");
      const bahn = knoten("div", "bahn");
      zonen.forEach(([anfang, ende, klasse]) => {
        const links = skalaProzent(anfang, von, bis);
        const rechts = skalaProzent(ende, von, bis);
        if (links === null || rechts === null || rechts <= links) return;
        const zone = knoten("div", `zone ${klasse}`);
        zone.style.left = `${links}%`;
        zone.style.width = `${rechts - links}%`;
        bahn.appendChild(zone);
      });
      [...marken.map((m) => [...m, "marke"]), ...punkte.map((p) => [...p, "punkt"])].forEach(
        ([wert, klasse, titel, form]) => {
          const lage = skalaProzent(wert, von, bis);
          if (lage === null) return;
          const zeichen = knoten("div", `${form} ${klasse}`);
          zeichen.style.left = `${lage}%`;
          if (titel) zeichen.title = titel;
          bahn.appendChild(zeichen);
          if (form === "punkt" && wertText) {
            const text = knoten("div", "punkt-wert", wertText);
            text.style.left = `${lage}%`;
            bahn.appendChild(text);
          }
        }
      );
      const beschriftung = knoten("div", "achse");
      achse.forEach((text) => beschriftung.appendChild(knoten("span", "", text)));
      rahmen.append(bahn, beschriftung);
      return rahmen;
    }

    _kachelAussen(kreis) {
      const k = kreis.kennwerte || {};
      const steuerung = vorhanden(k.grenze_steuerung) ? Number(k.grenze_steuerung) : null;
      const bezug = steuerung ?? (vorhanden(k.heizgrenze) ? Number(k.heizgrenze) : null);
      const hysterese = vorhanden(k.hysterese) ? Number(k.hysterese) : 1;
      const [von, bis] = aussenBereich(bezug);
      const eigene = vorhanden(k.heizgrenze) && steuerung !== null && Math.abs(k.heizgrenze - steuerung) >= 0.05;
      const skala = this._skala({
        von,
        bis,
        zonen:
          bezug === null
            ? []
            : [
                [von, bezug - hysterese, "heizt"],
                [bezug - hysterese, bezug + hysterese, "hysterese"],
                [bezug + hysterese, bis, "aus"],
              ],
        marken: eigene ? [[k.heizgrenze, "automatik", this._t("Grenze der Automatik")]] : [],
        punkte: [
          [k.at_gedaempft, "gedaempft", this._t("gedämpft")],
          [k.at, "jetzt", this._t("jetzt")],
        ],
        achse: [
          `${zahl(von, 0)} °C`,
          bezug === null ? "" : this._tMit("heizt unter {ein} · aus über {aus} °C", { ein: zahl(bezug - hysterese), aus: zahl(bezug + hysterese) }),
          `${zahl(bis, 0)} °C`,
        ],
      });
      let hinweis;
      if (steuerung === null) hinweis = this._t("Heizgrenze der Steuerung nicht lesbar – es gilt 17 °C.");
      else if (eigene) hinweis = this._tMit("Automatik: {grenze} °C, {versatz} zur Steuerung", { grenze: zahl(k.heizgrenze), versatz: kelvin(k.versatz) });
      else hinweis = this._t("Automatik: Heizgrenze der Steuerung");
      return this._kachel(
        "aussentemperatur",
        "Außentemperatur",
        [
          [`${zahl(k.at)} °C`, "jetzt"],
          [`${zahl(k.at_gedaempft)} °C`, "gedämpft (Automatik)"],
        ],
        skala,
        [knoten("div", "fuss", hinweis), knoten("div", "fuss", this._t("Die Steuerung rechnet mit der aktuellen Außentemperatur."))]
      );
    }

    _kachelSonne(kreis) {
      const k = kreis.kennwerte || {};
      const w = kreis.werte || {};
      const schwelle = vorhanden(k.sonne_schwelle) ? k.sonne_schwelle : w.sonnenquote;
      const skala = this._skala({
        von: 0,
        bis: 100,
        zonen: vorhanden(k.sonnenquote) ? [[0, k.sonnenquote, "sonne"]] : [],
        marken: [
          [schwelle, "schwelle", this._t("Sonnentag ab")],
          ...(vorhanden(k.stark_quote) ? [[k.stark_quote, "stark", this._t("sehr sonnig")]] : []),
        ],
        achse: [
          "0",
          vorhanden(k.stark_quote)
            ? this._tMit("Sonnentag ab {ab} · sehr sonnig {stark} %", { ab: zahl(schwelle, 0), stark: zahl(k.stark_quote, 0) })
            : this._tMit("Sonnentag ab {ab} %", { ab: zahl(schwelle, 0) }),
          "100 %",
        ],
      });
      let vorrang = null;
      if (k.vorrang) {
        vorrang = knoten(
          "div",
          "vorrang-zeile",
          k.vorrang.laeuft
            ? this._t("Vorrangquelle liefert")
            : this._tMit("Vorrangquellen heute {stunden} h", { stunden: zahl((k.vorrang.minuten || 0) / 60) })
        );
      }
      const aus = w.sonnentag === false ? knoten("div", "fuss", this._t("Sonnentag ausgeschaltet")) : null;
      return this._kachel("sonne", "Sonne heute", [[`${zahl(k.sonnenquote, 0)} %`, "Sonnenquote"]], skala, [vorrang, aus]);
    }

    _kachelRaeume(kreis) {
      const k = kreis.kennwerte || {};
      const rk = vorhanden(k.rueckkehr_k) ? Number(k.rueckkehr_k) : 1;
      const sonnig = vorhanden(k.sonne_raum_k) ? Number(k.sonne_raum_k) : 0.5;
      // Außerhalb von ±2 K sitzt der Punkt am Rand; ein Pfeil zeigt, dass der Wert weiter liegt.
      const ab = vorhanden(k.abweichung) ? Number(k.abweichung) : null;
      let wertText = ab === null ? null : kelvin(ab);
      if (ab !== null && ab < -2) wertText = `‹ ${wertText}`;
      if (ab !== null && ab > 2) wertText = `${wertText} ›`;
      const skala = this._skala({
        von: -2,
        bis: 2,
        zonen: [
          [-2, -rk, "kalt"],
          [-rk, -sonnig, "neutral"],
          [-sonnig, 0, "moeglich"],
          [0, 2, "ueber"],
        ],
        wertText,
        marken: [
          [0, "ziel", this._t("Ziel")],
          ...(vorhanden(k.sonne_raum_k) ? [[-k.sonne_raum_k, "schwelle", this._t("Sonnentag möglich ab")]] : []),
          ...(vorhanden(k.stark_k) ? [[k.stark_k, "stark", this._t("sehr sonnig ab")]] : []),
        ],
        punkte: [[k.abweichung, "raum", this._t("Räume")]],
        achse: ["−2 K", this._t("Ziel"), "+2 K"],
      });
      const fuss = [];
      if (!k.eigene_ziele) fuss.push(knoten("div", "fuss", this._tMit("Bezug: Sollwert des Heizkreises {soll} °C", { soll: zahl(k.soll) })));
      if ((k.raeume || []).length > 1 || k.eigene_ziele) {
        const liste = knoten("div", "raeume");
        (k.raeume || []).forEach((raum) => {
          const zeile = knoten(
            "div",
            raum.veraltet ? "veraltet" : "",
            raum.veraltet
              ? this._tMit("{name} {wert} °C – veraltet, zählt nicht", { name: raum.name, wert: zahl(raum.wert) })
              : raumzeile(raum, (text) => this._t(text))
          );
          liste.appendChild(zeile);
        });
        fuss.push(liste);
      }
      return this._kachel(
        "raum",
        "Räume zum Ziel",
        [
          [kelvin(k.abweichung), k.raum_art === "minimum" ? "kältester Raum" : "Mittel"],
          [`${zahl(k.raum)} °C`, k.raum_art === "minimum" ? "kältester Raum" : "Ø Räume"],
        ],
        skala,
        fuss
      );
    }

    /** Heizgrenzen der Steuerung lesen und von Hand setzen; die Automatik richtet sich danach. */
    _automatikGrenzen(kreis, darf) {
      const k = kreis.kennwerte || {};
      const kasten = knoten("div", "automatik-grenzen");
      kasten.appendChild(knoten("div", "titel", this._t("Heizgrenzen der Steuerung")));
      const feld = (titel, wert, min, max) => {
        const eingabe = knoten("input");
        eingabe.type = "number";
        eingabe.step = "0.5";
        eingabe.min = String(min);
        eingabe.max = String(max);
        eingabe.value = vorhanden(wert) ? String(wert) : "";
        eingabe.disabled = !darf;
        const beschriftung = knoten("label", "feld");
        beschriftung.append(knoten("span", "", this._t(titel)), eingabe, knoten("span", "", "°C"));
        kasten.appendChild(beschriftung);
        return eingabe;
      };
      const heiz = feld("Heizbetrieb", k.grenze_steuerung, 0, 30);
      const absenk = feld("Absenkbetrieb", k.grenze_absenk, -10, 20);
      const taste = knoten("button", "automatik-knopf leise klein", this._t("Übernehmen"));
      taste.type = "button";
      taste.disabled = !darf;
      taste.addEventListener("click", async () => {
        const nachricht = { type: "heatnexus/automatik/heizgrenzen", heizkreis: kreis.heizkreis };
        if (heiz.value !== "") nachricht.heizbetrieb = Number(heiz.value);
        if (absenk.value !== "") nachricht.absenkbetrieb = Number(absenk.value);
        this._automatikGespeichert = `${kreis.heizkreis}:grenzen`;
        if (!(await this._automatikAufruf(nachricht))) this._automatikGespeichert = null;
      });
      kasten.appendChild(taste);
      if (this._automatikGespeichert === `${kreis.heizkreis}:grenzen`) {
        this._automatikGespeichert = null;
        const hinweis = knoten("span", "automatik-gespeichert", this._t("übernommen ✓"));
        kasten.appendChild(hinweis);
        setTimeout(() => hinweis.remove(), GRENZEN_GESPEICHERT_MS);
      }
      kasten.appendChild(
        knoten(
          "div",
          "fuss",
          vorhanden(k.grenze_steuerung)
            ? this._t("Die Steuerung schaltet 1 K darüber ab und 1 K darunter wieder ein, nach der aktuellen Außentemperatur.")
            : this._t("Die Steuerung liefert ihre Heizgrenze nicht; die Automatik rechnet mit 17 °C.")
        )
      );
      return kasten;
    }
  };
