/**
 * Reiter „Automatik“: die Kennwerte als Kacheln mit Skala.
 *
 * Jede Kachel nennt ihre Zahlen mit Beschriftung und zeigt auf einer Skala,
 * wo die Schaltpunkte liegen. Teil der Oberfläche `heatnexus-panel.js`; als Mixin.
 */

import { kelvin, zahl } from "./automatik.js";

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

/** Einordnung der Auskühlzeit für Laien: Altbau mit wenig Masse kühlt unter 30 h, Neubau über 80 h. */
export function traegheit(stunden) {
  if (!vorhanden(stunden)) return null;
  if (Number(stunden) < 30) return "schnell";
  return Number(stunden) <= 80 ? "mittel" : "träge";
}

function knoten(tag, klasse = "", text = null) {
  const element = document.createElement(tag);
  if (klasse) element.className = klasse;
  if (text !== null) element.textContent = text;
  return element;
}

// Vergleichstage, ab denen das Modell frei werden kann; wie `FREIGABE_TAGE` auf dem Server.
const FREIGABE_TAGE = 14;
// Warum noch kein Hausmodell besteht, je Grund aus der Laufzeit.
const LERN_GRUENDE = {
  daten: "Die Aufzeichnung liefert keine Raumwerte, Außentemperatur oder Vorlauf.",
  unpassend: "Die Raumwerte ergeben noch keine plausible Auskühlzeit.",
};

function vorhanden(wert) {
  return wert !== null && wert !== undefined && !Number.isNaN(Number(wert));
}

/** Parameterwert ohne überflüssige Nachkommastelle, negativ mit echtem Minus. */
function parameterwert(wert) {
  return zahl(wert, Number.isInteger(Number(wert)) ? 0 : 1).replace("-", "−");
}

/** ISO-Datum als „14.11.“. */
function tagMonat(datum) {
  const teile = String(datum || "").split("-");
  return teile.length === 3 ? `${teile[2]}.${teile[1]}.` : null;
}

export const KennwerteMixin = (Basis) =>
  class extends Basis {
    _automatikKennwerte(kreis) {
      const raster = knoten("div", "automatik-werte");
      raster.append(
        ...[
          this._kachelAussen(kreis),
          this._kachelSonne(kreis),
          this._kachelRaeume(kreis),
          this._kachelHaus(kreis),
          this._kachelHinweise(kreis),
        ].filter(Boolean)
      );
      return raster;
    }

    /** Eine Kachel: Titel, große Zahl mit Beisatz, Skala oder Liste, Fußzeilen. */
    _kachel(art, titel, zahl, beisatz, inhalt, fuss = []) {
      const kachel = knoten("div", `automatik-wert ${art}`);
      kachel.appendChild(knoten("div", "titel", this._t(titel)));
      const reihe = knoten("div", "werte");
      reihe.appendChild(knoten("div", "zahl", zahl));
      if (beisatz) reihe.appendChild(knoten("div", "neben", beisatz));
      kachel.appendChild(reihe);
      if (inhalt) kachel.appendChild(inhalt);
      kachel.append(...fuss.filter(Boolean));
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
      achse.forEach((eintrag) => {
        const [text, klasse] = Array.isArray(eintrag) ? eintrag : [eintrag, ""];
        beschriftung.appendChild(knoten("span", klasse, text));
      });
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
          [k.at_gedaempft, "gedaempft", this._t("gedämpft (Automatik)")],
          [k.at, "jetzt", this._t("jetzt")],
        ],
        achse:
          bezug === null
            ? []
            : [
                this._tMit("Heizt unter {ein} °C", { ein: zahl(bezug - hysterese, 0) }),
                this._tMit("Aus über {aus} °C", { aus: zahl(bezug + hysterese, 0) }),
              ],
      });
      const fuss = [];
      if (steuerung === null) fuss.push(knoten("div", "fuss", this._t("Heizgrenze der Steuerung nicht lesbar – es gilt 17 °C.")));
      else if (eigene) {
        fuss.push(knoten("div", "fuss", this._tMit("Automatik: {grenze} °C, {versatz} zur Steuerung", { grenze: zahl(k.heizgrenze), versatz: kelvin(k.versatz) })));
      }
      const kachel = this._kachel(
        "aussentemperatur",
        "Außentemperatur",
        `${zahl(k.at)} °C`,
        this._tMit("gedämpft {wert} °C", { wert: zahl(k.at_gedaempft) }),
        skala,
        fuss
      );
      const hinweis = "Die gedämpfte Außentemperatur entscheidet über nur Warmwasser. Die Steuerung rechnet mit der aktuellen Außentemperatur.";
      kachel.querySelector(".titel").appendChild(this._fragezeichen("Außentemperatur", hinweis));
      this._klickbar(kachel.querySelector(".neben"), (kreis.entitaeten || {}).gedaempft);
      return kachel;
    }

    _kachelSonne(kreis) {
      const k = kreis.kennwerte || {};
      const w = kreis.werte || {};
      const schwelle = vorhanden(k.sonne_schwelle) ? k.sonne_schwelle : w.sonnenquote;
      let vorrang = "";
      if (k.vorrang) {
        vorrang = k.vorrang.laeuft
          ? this._t("Vorrangquelle liefert")
          : this._tMit("Vorrangquellen {stunden} h", { stunden: zahl((k.vorrang.minuten || 0) / 60) });
      }
      const skala = this._skala({
        von: 0,
        bis: 100,
        zonen: vorhanden(k.sonnenquote) ? [[0, k.sonnenquote, "sonne"]] : [],
        marken: [
          [schwelle, "schwelle", this._t("Sonnentag ab")],
          ...(vorhanden(k.stark_quote) ? [[k.stark_quote, "stark", this._tMit("sehr sonnig ab {stark} %", { stark: zahl(k.stark_quote, 0) })]] : []),
        ],
        achse: [this._tMit("Sonnentag ab {ab} %", { ab: zahl(schwelle, 0) }), [vorrang, vorrang ? "vorrang-zeile" : ""]],
      });
      const aus = w.sonnentag === false ? knoten("div", "fuss", this._t("Sonnentag ausgeschaltet")) : null;
      const kachel = this._kachel("sonne", "Sonne heute", `${zahl(k.sonnenquote, 0)} %`, this._t("Sonnenquote"), skala, [aus]);
      this._klickbar(kachel.querySelector(".zahl"), (kreis.entitaeten || {}).sonnenquote);
      const vorrangZeile = kachel.querySelector(".vorrang-zeile");
      if (vorrangZeile && k.vorrang) this._klickbar(vorrangZeile, k.vorrang.entity);
      return kachel;
    }

    /**
     * Skala um das Ziel mit den Zonen aus den Einstellungen; mit mehreren Räumen
     * oder eigenen Zielen darunter eine Zeile je Raum.
     */
    _kachelRaeume(kreis) {
      const k = kreis.kennwerte || {};
      const raeume = k.raeume || [];
      const minimum = k.raum_art === "minimum";
      const beisatz = `${minimum ? this._t("kältester Raum") : "Ø"} ${zahl(k.raum)} °C`;
      const rk = vorhanden(k.rueckkehr_k) ? Number(k.rueckkehr_k) : 1;
      const sonnig = vorhanden(k.sonne_raum_k) ? Number(k.sonne_raum_k) : 0.5;
      const stark = vorhanden(k.stark_k) ? Number(k.stark_k) : null;
      // Außerhalb von ±2 K sitzt der Punkt am Rand; nur dann nennt ein Pfeil den Wert.
      const ab = vorhanden(k.abweichung) ? Number(k.abweichung) : null;
      let wertText = null;
      if (ab !== null && ab < -2) wertText = `‹ ${kelvin(ab)}`;
      if (ab !== null && ab > 2) wertText = `${kelvin(ab)} ›`;
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
          [-sonnig, "schwelle", this._t("Sonnentag möglich ab")],
          ...(stark !== null ? [[stark, "stark", this._t("sehr sonnig ab")]] : []),
        ],
        punkte: [[k.abweichung, "raum", this._t("Räume")]],
        achse: [
          this._tMit("Zurück unter {wert}", { wert: kelvin(-rk) }),
          this._t("Ziel"),
          stark !== null ? this._tMit("Sehr sonnig ab {wert}", { wert: kelvin(stark) }) : "+2 K",
        ],
      });
      const fuss = [];
      if (raeume.length > 1 || k.eigene_ziele) fuss.push(this._raumliste(raeume));
      else fuss.push(knoten("div", "fuss", this._tMit("Bezug: Sollwert des Heizkreises {soll} °C", { soll: zahl(k.soll) })));
      return this._raumKlickbar(kreis, this._kachel("raum", "Räume zum Ziel", kelvin(k.abweichung), beisatz, skala, fuss));
    }

    /**
     * Das gelernte Hausmodell: die Auskühlzeit als Zahl, darunter Treffsicherheit oder Lernstand.
     * Ohne Angabe vom Server fehlt die Kachel.
     */
    _kachelHaus(kreis) {
      const h = (kreis.kennwerte || {}).hausmodell;
      if (!h) return null;
      const fuss = (text) => knoten("div", "fuss", text);
      if (h.status === "lernt") {
        const grund = LERN_GRUENDE[h.grund];
        return this._kachel("haus", "Haus", "–", this._t("lernt noch"), null, [grund ? fuss(this._t(grund)) : null]);
      }
      const genau = { fehler: zahl(h.fehler, 2), bleibt: zahl(h.fehler_bleibt, 2) };
      let stand;
      if (h.status === "aktiv") stand = this._tMit("±{fehler} K, ohne Modell ±{bleibt} K", genau);
      else if ((h.vergleiche || 0) < FREIGABE_TAGE) stand = this._tMit("beobachtet – {tage} von 14 Tagen", { tage: h.vergleiche || 0 });
      else stand = this._tMit("beobachtet – ±{fehler} K, ohne Modell ±{bleibt} K", genau);
      const sonne = this._tMit("Sonne +{wert} K/h", { wert: zahl(h.sonne_k_h, 2) });
      const einordnung = {
        schnell: this._t("Auskühlzeit – schnell"),
        mittel: this._t("Auskühlzeit – mittel"),
        träge: this._t("Auskühlzeit – träge"),
      }[traegheit(h.auskuehlzeit_h)];
      const beisatz = einordnung || this._t("Auskühlzeit");
      return this._kachel("haus", "Haus", `${zahl(h.auskuehlzeit_h, 0)} h`, beisatz, null, [fuss(stand), fuss(sonne)]);
    }

    /**
     * Hinweise zu Heizkurve, Sollwert und Zeitprogramm: je Hinweis Titel, Empfehlung und Grundlage.
     * Ohne Angabe vom Server (Schalter aus) fehlt die Kachel.
     */
    _kachelHinweise(kreis) {
      const h = (kreis.kennwerte || {}).hinweise;
      if (!h) return null;
      const bloecke = (h.eintraege || []).map((eintrag) => this._hinweisBlock(eintrag)).filter(Boolean);
      let kachel;
      if (h.status !== "bereit" || !bloecke.length) {
        const grundlage = this._tMit("Grundlage: {tage} von {noetig} Tagen", { tage: h.tage || 0, noetig: h.noetig || 0 });
        kachel = this._kachel("hinweise", "Hinweise", "–", this._t("sammelt Daten"), null, [knoten("div", "fuss", grundlage)]);
      } else {
        const liste = knoten("div", "vorschlaege");
        liste.append(...bloecke);
        kachel = this._kachel("hinweise", "Hinweise", String(bloecke.length), this._t("Hinweise"), liste);
      }
      const erklaerung = "Hinweise beruhen auf ungestörten Tagen seit der letzten Änderung der Heizkurve. Die Automatik ändert diese Werte nicht.";
      kachel.querySelector(".titel").appendChild(this._fragezeichen("Hinweise", erklaerung));
      return kachel;
    }

    /** Ein Hinweis: Titel und Empfehlung als Marke, darunter Abweichung und Grundlage in einer Zeile. */
    _hinweisBlock(eintrag) {
      const titel = {
        heizkurve_frost: this._t("Heizkurve bei Frost"),
        heizkurve_uebergang: this._t("Heizkurve in der Übergangszeit"),
        heizkurve_parallel: this._t("Heizkurve"),
        sollwert_ausgleich: this._t("Raumsollwert"),
        morgen_spaet: this._t("Morgens zu spät warm"),
        steuerung_passt_an: this._t("Heizkurve"),
      }[eintrag.art];
      if (!titel) return null;
      const block = knoten("div", "vorschlag");
      const kopf = knoten("div", "kopf");
      kopf.appendChild(knoten("span", "name", titel));
      const empfehlung = this._hinweisEmpfehlung(eintrag);
      if (empfehlung) kopf.appendChild(knoten("span", "empfehlung", empfehlung));
      block.append(kopf, knoten("div", "angabe", this._hinweisAngaben(eintrag).join(" · ")));
      return block;
    }

    _hinweisAngaben(eintrag) {
      if (eintrag.art === "steuerung_passt_an") return [this._t("Anpassung durch die Steuerung aktiv")];
      const angaben = [];
      if (eintrag.art === "sollwert_ausgleich") angaben.push(this._tMit("Sollwert {wert} °C", { wert: zahl(eintrag.von) }));
      else if (vorhanden(eintrag.abweichung)) angaben.push(kelvin(eintrag.abweichung));
      if (vorhanden(eintrag.minuten)) angaben.push(this._tMit("Ziel nach {minuten} min", { minuten: eintrag.minuten }));
      const seit = tagMonat(eintrag.seit);
      angaben.push(
        seit
          ? this._tMit("{tage} Tage seit {seit}", { tage: eintrag.tage, seit })
          : this._tMit("{tage} Tage", { tage: eintrag.tage })
      );
      return angaben;
    }

    /** „Fußpunkt 45 → 43 °C“; ohne Zielwert keine Marke. */
    _hinweisEmpfehlung(eintrag) {
      if (eintrag.art === "steuerung_passt_an") return this._t("Keine Empfehlung zur Kurve");
      if (eintrag.art === "sollwert_ausgleich") return this._t("Heizkurve anpassen statt Sollwert");
      if (!vorhanden(eintrag.von) || !vorhanden(eintrag.nach)) return null;
      const parameter = {
        "3/13": this._t("Vorlauf bei Auslegung"),
        "3/1": this._t("Fußpunkt"),
        "3/58": this._t("Behaglichkeit"),
        "3/6": this._t("Vorhaltezeit"),
        "3/51": this._t("Raumsollwert"),
      }[eintrag.parameter] || eintrag.parameter || "";
      const werte = { parameter, von: parameterwert(eintrag.von), nach: parameterwert(eintrag.nach), einheit: eintrag.einheit || "" };
      return this._tMit("{parameter} {von} → {nach} {einheit}", werte).trim();
    }

    /** Eine Zeile je Raum: Name, Ist → Ziel, ob er heizt. */
    _raumliste(raeume) {
      const liste = knoten("div", "raeume");
      raeume.forEach((raum) => {
        const zeile = knoten("div", raum.veraltet ? "raum veraltet" : "raum");
        zeile.appendChild(knoten("span", "name", raum.name));
        const wert = knoten("span", "wert");
        if (raum.veraltet) wert.textContent = this._tMit("{wert} °C – veraltet", { wert: zahl(raum.wert) });
        else {
          const ziel = raum.ziel === null || raum.ziel === undefined ? "" : ` → ${zahl(raum.ziel)}`;
          wert.textContent = `${zahl(raum.wert)}${ziel} °C`;
          if (raum.heizt) wert.appendChild(knoten("span", "heizt", ` · ${this._t("heizt")}`));
          if (raum.aus) wert.appendChild(knoten("span", "aus", ` · ${this._t("aus")}`));
        }
        zeile.appendChild(wert);
        liste.appendChild(zeile);
      });
      return liste;
    }

    /** Die Abweichung öffnet die Entität der Automatik, jeder Raum seine eigene. */
    _raumKlickbar(kreis, kachel) {
      this._klickbar(kachel.querySelector(".zahl"), (kreis.entitaeten || {}).abweichung);
      const raeume = (kreis.kennwerte || {}).raeume || [];
      kachel.querySelectorAll(".raeume .raum").forEach((zeile, i) => this._klickbar(zeile, (raeume[i] || {}).entity_id));
      return kachel;
    }
  };
