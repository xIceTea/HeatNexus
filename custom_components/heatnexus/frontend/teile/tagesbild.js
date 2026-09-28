/**
 * Reiter „Automatik“: das Tagesbild je Heizkreis.
 *
 * Tageswahl und Legende, Stundenraster mit Zeile zur gezeigten Stunde, darunter
 * die Tagesleiste als SVG mit Zeiger. Teil der Oberfläche `heatnexus-panel.js`; als Mixin.
 */

import { kelvin, zahl } from "./automatik.js";

const AKTIONEN = { absenkung: "Absenkung", nur_ww: "nur Warmwasser", programm: "Programm" };

/** Die Werte einer Stunde im Tagesbild, als Zeilen für den Zeiger; Fehlendes entfällt. */
export function tagesleisteTipp(tag, stunde, t = (text) => text) {
  const eintrag = ((tag && tag.stunden) || []).find((s) => s.stunde === stunde) || {};
  const kopf = [uhrzeit(stunde), eintrag.aktion ? t(AKTIONEN[eintrag.aktion] || eintrag.aktion) : null];
  const zeilen = [kopf.filter(Boolean).join(" · ")];
  const prognose = eintrag.korrigiert ?? eintrag.roh;
  [
    ["Außen gemessen", eintrag.at],
    ["Außen Prognose", prognose],
    ["gedämpfte AT", eintrag.gedaempft],
    ["Räume", eintrag.raum],
  ].forEach(([titel, wert]) => {
    if (wert !== null && wert !== undefined) zeilen.push(`${t(titel)} ${zahl(wert)} °C`);
  });
  const sonne = ((tag && tag.sonne) || [])[stunde];
  if (sonne) zeilen.push(`${t("Sonne")} ${Math.round(sonne * 100)} %`);
  return zeilen;
}

/** Inhalt des Kastens zu einer Stunde: Modus, heutige Protokolleinträge dieser Stunde, Vorrang, Messwerte. */
export function stundenKasten(tag, stunde, protokoll, t = (text) => text) {
  const eintrag = ((tag && tag.stunden) || []).find((s) => s.stunde === stunde) || {};
  const bis = `${String(stunde + 1).padStart(2, "0")}:00`;
  const zeilen = [`${uhrzeit(stunde)}–${bis} · ${t(AKTIONEN[eintrag.aktion || "programm"])}`];
  const heute = new Date().toDateString();
  (protokoll || [])
    .filter((e) => new Date(e.zeit).getHours() === stunde && new Date(e.zeit).toDateString() === heute)
    .sort((a, b) => new Date(a.zeit) - new Date(b.zeit))
    .forEach((e) => zeilen.push(`${new Date(e.zeit).toTimeString().slice(0, 5)} ${e.text}`));
  if (eintrag.vorrang) zeilen.push(t("Vorrangquelle lieferte"));
  [
    ["Außen gemessen", eintrag.at],
    ["Räume", eintrag.raum],
  ].forEach(([titel, wert]) => {
    if (wert !== null && wert !== undefined) zeilen.push(`${t(titel)} ${zahl(wert)} °C`);
  });
  return zeilen;
}

/** Stunde als Kommazahl in „HH:MM“. */
export function uhrzeit(stunde) {
  const minuten = Math.round(Number(stunde) * 60);
  const h = Math.floor(minuten / 60) % 24;
  return `${String(h).padStart(2, "0")}:${String(minuten % 60).padStart(2, "0")}`;
}

/** Stunden als Punktliste für einen SVG-Pfad; Lücken beginnen neu. */
function linie(werte, x, y) {
  let pfad = "";
  let offen = false;
  werte.forEach(([stunde, wert]) => {
    if (wert === null || wert === undefined || Number.isNaN(Number(wert))) {
      offen = false;
      return;
    }
    pfad += `${offen ? "L" : "M"}${x(stunde)} ${y(wert)} `;
    offen = true;
  });
  return pfad.trim();
}

// Maße des Tagesbilds im SVG; die Beschriftung daneben rechnet mit denselben Zahlen.
export const BILD = { hoehe: 150, band: 8, oben: 8 };

function reihen(tag) {
  const stunden = (tag && tag.stunden) || [];
  const jetzt = tag && tag.jetzt !== undefined && tag.jetzt !== null ? Number(tag.jetzt) : null;
  return {
    stunden,
    jetzt,
    gemessen: stunden.map((s) => [s.stunde, jetzt !== null && s.stunde > jetzt ? null : s.at]),
    prognose: stunden.map((s) => [s.stunde, jetzt !== null && s.stunde < Math.floor(jetzt) ? null : s.korrigiert ?? s.roh]),
    gedaempft: stunden.map((s) => [s.stunde, jetzt !== null && s.stunde > jetzt ? null : s.gedaempft]),
  };
}

/** Temperaturbereich des Tagesbilds und die Lage einer Temperatur darin, in Prozent von oben. */
export function tagesleisteBereich(tag, heizgrenze = null) {
  const { gemessen, prognose, gedaempft } = reihen(tag);
  const alle = [...gemessen, ...prognose, ...gedaempft].map(([, w]) => w).filter((w) => w !== null && w !== undefined);
  if (heizgrenze !== null && heizgrenze !== undefined) alle.push(Number(heizgrenze));
  if (!alle.length) return null;
  const min = Math.min(...alle) - 1;
  const max = Math.max(...alle) + 1;
  const unten = BILD.hoehe - BILD.band - 2 - 8;
  const y = (wert) => unten - ((Number(wert) - min) / (max - min)) * (unten - BILD.oben);
  return { min, max, y, prozent: (wert) => (y(wert) / BILD.hoehe) * 100 };
}

/**
 * Das Tagesbild als SVG-Text: Sonne als Fläche, Außen gemessen und
 * angepasste Prognose, Heizgrenze, der Modus je Stunde als Band und „jetzt“.
 */
export function tagesleisteSvg(tag, breite = 1000, heizgrenze = null) {
  const { hoehe, band, oben } = BILD;
  const bandY = hoehe - band - 2;
  const unten = bandY - 8;
  const x = (stunde) => ((Math.max(0, Math.min(24, Number(stunde))) / 24) * breite).toFixed(1);
  const teile = [
    `<svg viewBox="0 0 ${breite} ${hoehe}" preserveAspectRatio="none" role="img" aria-label="Tagesverlauf">`,
  ];
  const sonne = (tag && tag.sonne) || [];
  if (sonne.length) {
    const punkte = sonne.map((wert, stunde) => `${x(stunde)},${(unten - Number(wert) * (unten - oben)).toFixed(1)}`);
    teile.push(`<polygon class="al-sonne" points="0,${unten} ${punkte.join(" ")} ${breite},${unten}"/>`);
  }
  const { stunden, jetzt, gemessen, prognose, gedaempft } = reihen(tag);
  const bereich = tagesleisteBereich(tag, heizgrenze);
  if (bereich) {
    const y = (wert) => bereich.y(wert).toFixed(1);
    if (heizgrenze !== null && heizgrenze !== undefined) {
      teile.push(`<line class="al-grenze" x1="0" x2="${breite}" y1="${y(heizgrenze)}" y2="${y(heizgrenze)}"/>`);
    }
    const pfadGemessen = linie(gemessen, x, y);
    if (pfadGemessen) teile.push(`<path class="al-aussen" d="${pfadGemessen}"/>`);
    const pfadPrognose = linie(prognose, x, y);
    if (pfadPrognose) teile.push(`<path class="al-prognose" d="${pfadPrognose}"/>`);
    const pfadGedaempft = linie(gedaempft, x, y);
    if (pfadGedaempft) teile.push(`<path class="al-gedaempft" d="${pfadGedaempft}"/>`);
  }
  teile.push(`<rect class="al-grund" x="0" y="${bandY}" width="${breite}" height="${band}" rx="4"/>`);
  // Gleiche Modi hintereinander bilden einen Abschnitt; künftige Stunden sind blass.
  let abschnitt = null;
  const abschliessen = () => {
    if (!abschnitt) return;
    const [von, bis, modus, plan] = abschnitt;
    teile.push(
      `<rect class="al-m-${modus}${plan ? " al-plan" : ""}" x="${x(von)}" y="${bandY}" width="${(x(bis) - x(von)).toFixed(1)}" height="${band}"/>`
    );
  };
  stunden.forEach((s) => {
    const modus = ["absenkung", "nur_ww"].includes(s.aktion) ? s.aktion : "programm";
    const plan = jetzt !== null && s.stunde > Math.floor(jetzt);
    if (abschnitt && abschnitt[2] === modus && abschnitt[3] === plan && abschnitt[1] === s.stunde) {
      abschnitt[1] = s.stunde + 1;
      return;
    }
    abschliessen();
    abschnitt = [s.stunde, s.stunde + 1, modus, plan];
  });
  abschliessen();
  const von = tag && tag.absenkung_von;
  const bis = tag && tag.absenkung_bis;
  const ziel = tag && tag.absenkung_ziel;
  if (von !== null && von !== undefined && bis !== null && bis !== undefined) {
    const ende = Math.min(Number(bis), ziel ?? Number(bis));
    teile.push(`<rect class="al-absenkung" x="${x(von)}" y="${bandY}" width="${(x(ende) - x(von)).toFixed(1)}" height="${band}"/>`);
    if (ziel !== null && ziel !== undefined && Number(ziel) > Number(bis)) {
      teile.push(
        `<rect class="al-verlaengerung" x="${x(bis)}" y="${bandY}" width="${(x(ziel) - x(bis)).toFixed(1)}" height="${band}"/>`
      );
    }
  }
  if (jetzt !== null) {
    teile.push(`<line class="al-jetzt" x1="${x(jetzt)}" x2="${x(jetzt)}" y1="0" y2="${bandY}"/>`);
  }
  teile.push("</svg>");
  return teile.join("");
}

/** Wettersymbol einer Stunde aus Bewölkung und Tageslicht. */
export function wetterSymbol(wolken, hell) {
  if (!hell) return "☾";
  if (wolken === null || wolken === undefined) return "·";
  if (wolken < 25) return "☀";
  if (wolken < 70) return "⛅";
  return "☁";
}

/** Text der Korrekturmarke: angepasst, lernend oder ohne Messung. */
export function korrekturText(art, eintrag, noetig) {
  if (art === "sonne" && !eintrag.aktiv) return "Sonne unkorrigiert";
  const name = art === "sonne" ? "Sonne" : "Außen";
  if (art === "temperatur" && eintrag.versatz !== null && eintrag.versatz !== undefined) {
    return `${name} angepasst ${kelvin(eintrag.versatz)}`;
  }
  if (art === "sonne" && eintrag.faktor !== null && eintrag.faktor !== undefined) {
    const prozent = Math.round((Number(eintrag.faktor) - 1) * 100);
    return `${name} angepasst ${prozent > 0 ? "+" : prozent < 0 ? "−" : "±"}${Math.abs(prozent)} %`;
  }
  return `${name}: lernt noch ${eintrag.tage || 0}/${noetig}`;
}

/** Stand der Prognoseanpassung in einer Zeile: angepasst, lernend oder roh. */
export function korrekturZeile(k, t = (text) => text) {
  if (!k) return "";
  if (!k.an) return t("Rohe Prognose");
  const teile = [t("Prognose angepasst")];
  const temperatur = k.temperatur || {};
  if (temperatur.versatz !== null && temperatur.versatz !== undefined) teile.push(`${t("Außen")} ${kelvin(temperatur.versatz)}`);
  else teile.push(`${t("Außen lernt noch")} ${temperatur.tage || 0}/${k.noetig}`);
  const sonne = k.sonne || {};
  if (sonne.aktiv && sonne.faktor !== null && sonne.faktor !== undefined) {
    const prozent = Math.round((Number(sonne.faktor) - 1) * 100);
    teile.push(`${t("Sonne")} ${prozent > 0 ? "+" : prozent < 0 ? "−" : "±"}${Math.abs(prozent)} %`);
  } else if (sonne.aktiv) teile.push(`${t("Sonne")} ${sonne.tage || 0}/${k.noetig}`);
  return teile.join(" · ");
}

export const TagesbildMixin = (Basis) =>
  class extends Basis {
    /** Zeiger über dem Tagesbild: senkrechte Linie und die Werte der Stunde darunter. */
    _automatikZeiger(bild, tag) {
      const linie = document.createElement("div");
      linie.className = "automatik-zeiger";
      const tipp = document.createElement("div");
      tipp.className = "automatik-tipp";
      linie.hidden = true;
      tipp.hidden = true;
      bild.append(linie, tipp);
      const zeigen = (ereignis) => {
        const rahmen = bild.getBoundingClientRect();
        if (!rahmen.width) return;
        const anteil = Math.max(0, Math.min(1, (ereignis.clientX - rahmen.left) / rahmen.width));
        const stunde = Math.min(23, Math.floor(anteil * 24));
        linie.style.left = `${((stunde + 0.5) / 24) * 100}%`;
        tipp.replaceChildren(
          ...tagesleisteTipp(tag, stunde, (text) => this._t(text)).map((text) => {
            const zeile = document.createElement("div");
            zeile.textContent = text;
            return zeile;
          })
        );
        // Rechts der Mitte steht die Box links vom Zeiger, damit sie im Bild bleibt.
        tipp.style.left = anteil > 0.5 ? "auto" : `calc(${((stunde + 0.5) / 24) * 100}% + 8px)`;
        tipp.style.right = anteil > 0.5 ? `calc(${100 - ((stunde + 0.5) / 24) * 100}% + 8px)` : "auto";
        linie.hidden = false;
        tipp.hidden = false;
      };
      bild.addEventListener("pointermove", zeigen);
      bild.addEventListener("pointerdown", zeigen);
      bild.addEventListener("pointerleave", () => {
        linie.hidden = true;
        tipp.hidden = true;
      });
    }

    /** Karte „Tagesverlauf“: Tageswahl und Legende, Stundenraster, Stundenzeile, Tagesbild. */
    _automatikTag(kreis) {
      const karte = document.createElement("div");
      karte.className = "karte automatik-verlauf";
      const rahmen = document.createElement("div");
      rahmen.className = "automatik-tag";
      this._automatikTagWahl = this._automatikTagWahl || {};
      const tage = [{ titel: "Heute", tag: kreis.tag }, ...(kreis.vorschau || [])];
      const wahl = Math.min(this._automatikTagWahl[kreis.heizkreis] || 0, tage.length - 1);
      const gewaehlt = tage[wahl];
      const tag = gewaehlt.tag || {};
      const kopf = document.createElement("div");
      kopf.className = "automatik-verlaufkopf";
      const titel = document.createElement("h3");
      titel.textContent = this._t("Tagesverlauf");
      kopf.append(titel, this._automatikTagWahlLeiste(kreis, tage, wahl), this._automatikStundenlegende());
      rahmen.appendChild(kopf);
      if (wahl > 0) {
        const vorschau = document.createElement("div");
        vorschau.className = "automatik-vorschau";
        vorschau.textContent = this._tMit("{titel}: {text} Angenommen ist ein Raum am Sollwert.", {
          titel: this._t(gewaehlt.titel),
          text: gewaehlt.begruendung || "",
        });
        rahmen.appendChild(vorschau);
      }
      rahmen.appendChild(this._automatikStundenraster({ ...kreis, tag }));
      const grenze = (kreis.kennwerte || {}).heizgrenze;
      const bild = document.createElement("div");
      bild.className = "automatik-tag-bild";
      bild.innerHTML = tagesleisteSvg(tag, 1000, grenze);
      this._automatikBildBeschriften(bild, tag, grenze);
      this._automatikZeiger(bild, tag);
      const achse = document.createElement("div");
      achse.className = "automatik-achse";
      ["00:00", "06:00", "12:00", "18:00", "24:00"].forEach((marke) => {
        const teil = document.createElement("span");
        teil.textContent = marke;
        achse.appendChild(teil);
      });
      const legende = document.createElement("div");
      legende.className = "automatik-legende";
      [
        ["al-aussen", "Außen gemessen"],
        ["al-prognose", "Außen Prognose"],
        ["al-gedaempft", "Gedämpfte AT"],
        ["al-grenze", "Heizgrenze"],
        ["al-sonne", "Sonne laut Prognose"],
      ].forEach(([klasse, text]) => {
        const eintrag = document.createElement("span");
        const farbe = document.createElement("i");
        farbe.className = klasse;
        const beschriftung = document.createElement("span");
        beschriftung.textContent = this._t(text);
        eintrag.append(farbe, beschriftung);
        legende.appendChild(eintrag);
      });
      rahmen.append(bild, achse, legende);
      karte.appendChild(rahmen);
      return karte;
    }

    /** Temperaturmarken am linken Rand und die Heizgrenze am rechten, als Text über dem SVG. */
    _automatikBildBeschriften(bild, tag, grenze) {
      const bereich = tagesleisteBereich(tag, grenze);
      if (!bereich) return;
      const marke = (klasse, text, prozent) => {
        const element = document.createElement("span");
        element.className = `automatik-bildmarke ${klasse}`;
        element.textContent = text;
        element.style.top = `${prozent.toFixed(1)}%`;
        bild.appendChild(element);
      };
      const schritt = bereich.max - bereich.min > 24 ? 10 : 5;
      for (let wert = Math.ceil(bereich.min / schritt) * schritt; wert <= bereich.max; wert += schritt) {
        if (grenze === null || grenze === undefined || Math.abs(wert - grenze) > 1.5) marke("achse", `${wert}°`, bereich.prozent(wert));
      }
      if (grenze !== null && grenze !== undefined) {
        marke("grenze", this._tMit("Heizgrenze {wert}°", { wert: zahl(grenze, 0) }), bereich.prozent(grenze));
      }
    }

    _automatikTagWahlLeiste(kreis, tage, wahl) {
      const leiste = document.createElement("div");
      leiste.className = "automatik-tagwahl";
      tage.forEach((eintrag, index) => {
        const taste = document.createElement("button");
        taste.type = "button";
        taste.textContent = this._t(eintrag.titel);
        taste.setAttribute("aria-pressed", String(index === wahl));
        taste.addEventListener("click", () => {
          this._automatikTagWahl[kreis.heizkreis] = index;
          this._automatikStundeOffen = null;
          this._gebaut = false;
          this._zeichnen();
        });
        leiste.appendChild(taste);
      });
      return leiste;
    }

    _automatikStundenraster(kreis) {
      const raster = document.createElement("div");
      raster.className = "automatik-stunden";
      const stunden = ((kreis.tag || {}).stunden || []).filter((s) => s.stunde >= 6 && s.stunde <= 22);
      const sonne = (kreis.tag || {}).sonne || [];
      const heute = (kreis.tag || {}).jetzt !== null && (kreis.tag || {}).jetzt !== undefined;
      const jetzt = heute ? Math.floor(Number(kreis.tag.jetzt)) : null;
      const grenze = (kreis.kennwerte || {}).heizgrenze;
      // Gezeigt wird die angeklickte Stunde, sonst die laufende, an anderen Tagen die erste.
      const offen = stunden.some((s) => s.stunde === this._automatikStundeOffen) ? this._automatikStundeOffen : null;
      const gezeigt = offen ?? (stunden.some((s) => s.stunde === jetzt) ? jetzt : (stunden[0] || {}).stunde);
      stunden.forEach((eintrag) => {
        const zelle = document.createElement("button");
        zelle.type = "button";
        const plan = !heute || eintrag.stunde > jetzt;
        zelle.className = [
          "automatik-stunde",
          `m-${eintrag.aktion || "programm"}`,
          eintrag.stunde === jetzt ? "jetzt" : "",
          eintrag.stunde > 14 ? "spaet" : "",
          plan ? "plan" : "",
          eintrag.stunde === offen ? "offen" : "",
          eintrag.stunde === gezeigt ? "gezeigt" : "",
        ]
          .filter(Boolean)
          .join(" ");
        zelle.setAttribute("aria-pressed", String(eintrag.stunde === gezeigt));
        zelle.addEventListener("click", () => {
          this._automatikStundeOffen = this._automatikStundeOffen === eintrag.stunde ? null : eintrag.stunde;
          this._gebaut = false;
          this._zeichnen();
        });
        const temperatur = eintrag.korrigiert ?? eintrag.roh;
        const teile = [
          ["uhr", String(eintrag.stunde).padStart(2, "0")],
          ["sym", wetterSymbol(eintrag.wolken, (sonne[eintrag.stunde] || 0) > 0)],
          ["t", temperatur === null || temperatur === undefined ? "–" : `${Math.round(temperatur)}°`],
        ];
        teile.forEach(([klasse, text]) => {
          const teil = document.createElement("div");
          teil.className = klasse;
          if (klasse === "t" && temperatur !== null && temperatur !== undefined && grenze !== undefined) {
            teil.classList.add(temperatur < grenze ? "kalt" : "warm");
          }
          teil.textContent = text;
          zelle.appendChild(teil);
        });
        const streifen = document.createElement("div");
        streifen.className = `streifen ${eintrag.aktion || "programm"}`;
        zelle.appendChild(streifen);
        const raum = document.createElement("div");
        raum.className = "raum";
        raum.title = this._t("Räume im Mittel, gemessen zu Beginn der Stunde");
        raum.textContent = eintrag.raum !== null && eintrag.raum !== undefined ? zahl(eintrag.raum) : "–";
        zelle.appendChild(raum);
        raster.appendChild(zelle);
      });
      const huelle = document.createElement("div");
      huelle.appendChild(raster);
      if (gezeigt !== undefined && gezeigt !== null) {
        huelle.appendChild(this._automatikStundenzeile(kreis, gezeigt, heute));
      }
      return huelle;
    }

    /** Zeile unter dem Raster: Werte und Modus der gezeigten Stunde, rechts der Stand der Prognoseanpassung. */
    _automatikStundenzeile(kreis, stunde, heute) {
      const eintrag = ((kreis.tag || {}).stunden || []).find((s) => s.stunde === stunde) || {};
      const kasten = document.createElement("div");
      kasten.className = "automatik-stundenkasten";
      const zeile = document.createElement("div");
      zeile.className = "automatik-stundenwerte";
      const teil = (klasse, text) => {
        const span = document.createElement("span");
        if (klasse) span.className = klasse;
        span.textContent = text;
        zeile.appendChild(span);
      };
      teil("kopf", this._tMit("{zeit} Uhr", { zeit: uhrzeit(stunde) }));
      const gemessen = heute && eintrag.at !== null && eintrag.at !== undefined;
      const aussen = gemessen ? eintrag.at : eintrag.korrigiert ?? eintrag.roh;
      if (aussen !== null && aussen !== undefined) teil("", `${this._t("Außen")} ${zahl(aussen, 0)} °C`);
      if (eintrag.raum !== null && eintrag.raum !== undefined) teil("", `${this._t("Räume")} ${zahl(eintrag.raum)} °C`);
      const aktion = eintrag.aktion || "programm";
      teil(`modus m-${aktion}`, this._t(AKTIONEN[aktion] || aktion));
      if (eintrag.vorrang) teil("vorrang", this._t("Vorrangquelle lieferte"));
      const korrektur = korrekturZeile(kreis.korrektur, (text) => this._t(text));
      if (korrektur) teil("korrektur", korrektur);
      kasten.appendChild(zeile);
      // Die Protokolleinträge dieser Stunde; Kopf und Messwerte stehen schon in der Zeile.
      stundenKasten(kreis.tag, stunde, heute ? kreis.protokoll : [], (text) => this._t(text))
        .filter((text) => /^\d\d:\d\d /.test(text))
        .forEach((text) => {
          const eintragZeile = document.createElement("div");
          eintragZeile.className = "protokoll";
          eintragZeile.textContent = text;
          kasten.appendChild(eintragZeile);
        });
      return kasten;
    }

    /** Farben der Modi, oben rechts im Tagesverlauf. */
    _automatikStundenlegende() {
      const legende = document.createElement("div");
      legende.className = "automatik-stundenlegende";
      legende.title = this._t(
        "Der Balken unter jeder Stunde zeigt, was galt; blasse Stunden sind geplant. Ein Klick auf eine Stunde zeigt ihre Werte und Einträge."
      );
      [
        ["m-absenkung", "Sonnentag"],
        ["m-nur_ww", "Nur Warmwasser"],
        ["m-programm", "Programm"],
      ].forEach(([klasse, titel]) => {
        const eintrag = document.createElement("span");
        const farbe = document.createElement("i");
        farbe.className = klasse;
        eintrag.append(farbe, this._t(titel));
        legende.appendChild(eintrag);
      });
      return legende;
    }
  };
