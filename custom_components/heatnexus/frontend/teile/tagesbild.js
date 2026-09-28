/**
 * Reiter „Automatik“: das Tagesbild je Heizkreis.
 *
 * Tageswahl, Korrekturmarken, Stundenraster mit Legende und Kasten, darunter
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

/**
 * Das Tagesbild als SVG-Text: Sonne als Fläche, Außen gemessen und
 * angepasste Prognose, Heizgrenze, Absenkung und „jetzt“. Nur Zahlen gehen in den Text.
 */
export function tagesleisteSvg(tag, breite = 1000, heizgrenze = null) {
  const hoehe = 150;
  const band = 10;
  const bandY = hoehe - band - 2;
  const oben = 8;
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
  const stunden = (tag && tag.stunden) || [];
  const jetzt = tag && tag.jetzt !== undefined && tag.jetzt !== null ? Number(tag.jetzt) : null;
  const gemessen = stunden.map((s) => [s.stunde, jetzt !== null && s.stunde > jetzt ? null : s.at]);
  const prognose = stunden.map((s) => [s.stunde, jetzt !== null && s.stunde < Math.floor(jetzt) ? null : s.korrigiert ?? s.roh]);
  const gedaempft = stunden.map((s) => [s.stunde, jetzt !== null && s.stunde > jetzt ? null : s.gedaempft]);
  const alle = [...gemessen, ...prognose, ...gedaempft].map(([, w]) => w).filter((w) => w !== null && w !== undefined);
  if (heizgrenze !== null && heizgrenze !== undefined) alle.push(Number(heizgrenze));
  if (alle.length) {
    const min = Math.min(...alle) - 1;
    const max = Math.max(...alle) + 1;
    const y = (wert) => (unten - ((Number(wert) - min) / (max - min)) * (unten - oben)).toFixed(1);
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
  teile.push(`<rect class="al-grund" x="0" y="${bandY}" width="${breite}" height="${band}" rx="5"/>`);
  const von = tag && tag.absenkung_von;
  const bis = tag && tag.absenkung_bis;
  const ziel = tag && tag.absenkung_ziel;
  if (von !== null && von !== undefined && bis !== null && bis !== undefined) {
    const ende = Math.min(Number(bis), ziel ?? Number(bis));
    teile.push(
      `<rect class="al-absenkung" x="${x(von)}" y="${bandY}" width="${(x(ende) - x(von)).toFixed(1)}" height="${band}" rx="4"/>`
    );
    if (ziel !== null && ziel !== undefined && Number(ziel) > Number(bis)) {
      teile.push(
        `<rect class="al-verlaengerung" x="${x(bis)}" y="${bandY}" width="${(x(ziel) - x(bis)).toFixed(1)}" height="${band}" rx="4"/>`
      );
    }
  }
  ((tag && tag.entscheidungen) || []).forEach((stunde) => {
    teile.push(`<rect class="al-punkt" x="${x(stunde)}" y="${bandY - 4}" width="3" height="${band + 8}"/>`);
  });
  if (jetzt !== null) {
    teile.push(`<line class="al-jetzt" x1="${x(jetzt)}" x2="${x(jetzt)}" y1="0" y2="${hoehe}"/>`);
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

    _automatikTag(kreis) {
      const rahmen = document.createElement("div");
      rahmen.className = "automatik-tag";
      this._automatikTagWahl = this._automatikTagWahl || {};
      const tage = [{ titel: "Heute", tag: kreis.tag }, ...(kreis.vorschau || [])];
      const wahl = Math.min(this._automatikTagWahl[kreis.heizkreis] || 0, tage.length - 1);
      const gewaehlt = tage[wahl];
      const tag = gewaehlt.tag || {};
      rahmen.appendChild(this._automatikTagWahlLeiste(kreis, tage, wahl));
      rahmen.appendChild(this._automatikKorrekturMarken(kreis));
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
      const bild = document.createElement("div");
      bild.className = "automatik-tag-bild";
      bild.innerHTML = tagesleisteSvg(tag, 1000, (kreis.kennwerte || {}).heizgrenze);
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
        ["al-sonne", "Sonne laut Prognose"],
        ["al-aussen", "Außen gemessen"],
        ["al-prognose", "Außen Prognose, angepasst"],
        ["al-gedaempft", "gedämpfte AT"],
        ["al-grenze", "Heizgrenze"],
        ["al-absenkung", "Absenkung"],
      ].forEach(([klasse, titel]) => {
        const eintrag = document.createElement("span");
        const farbe = document.createElement("i");
        farbe.className = klasse;
        const text = document.createElement("span");
        text.textContent = titel;
        eintrag.append(farbe, text);
        legende.appendChild(eintrag);
      });
      rahmen.append(bild, achse, legende);
      return rahmen;
    }

    _automatikTagWahlLeiste(kreis, tage, wahl) {
      const leiste = document.createElement("div");
      leiste.className = "automatik-tagwahl";
      tage.forEach((eintrag, index) => {
        const taste = document.createElement("button");
        taste.type = "button";
        taste.textContent = eintrag.titel;
        taste.setAttribute("aria-pressed", String(index === wahl));
        taste.addEventListener("click", () => {
          this._automatikTagWahl[kreis.heizkreis] = index;
          this._gebaut = false;
          this._zeichnen();
        });
        leiste.appendChild(taste);
      });
      return leiste;
    }

    _automatikKorrekturMarken(kreis) {
      const leiste = document.createElement("div");
      leiste.className = "automatik-korrektur";
      const k = kreis.korrektur;
      if (!k) return leiste;
      const schalter = document.createElement("button");
      schalter.type = "button";
      schalter.className = `automatik-schalter klein${k.an ? " an" : ""}`;
      schalter.setAttribute("role", "switch");
      schalter.setAttribute("aria-checked", String(!!k.an));
      schalter.disabled = !(this._automatik && this._automatik.darf_aendern);
      const knopf = document.createElement("i");
      const text = document.createElement("span");
      text.textContent = "Prognose anpassen";
      schalter.append(knopf, text);
      schalter.addEventListener("click", () =>
        this._automatikEinstellen(kreis, { eigene: { ...(kreis.konfig.eigene || {}), anpassen: !k.an } })
      );
      leiste.appendChild(schalter);
      if (!k.an) {
        const aus = document.createElement("span");
        aus.className = "automatik-korrekturmarke";
        aus.textContent = "rohe Prognose";
        leiste.appendChild(aus);
        return leiste;
      }
      ["temperatur", "sonne"].forEach((art) => {
        const marke = document.createElement("span");
        const eintrag = k[art] || {};
        const wirkt = art === "temperatur" ? eintrag.versatz !== null && eintrag.versatz !== undefined : eintrag.faktor !== null && eintrag.faktor !== undefined;
        marke.className = `automatik-korrekturmarke${wirkt ? " wirkt" : ""}`;
        marke.textContent = korrekturText(art, eintrag, k.noetig);
        leiste.appendChild(marke);
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
      // Mit Thermostaten hat jeder Raum sein eigenes Ziel; dann gibt es keinen gemeinsamen Bezug.
      const bezug = (kreis.kennwerte || {}).raum_bezug;
      stunden.forEach((eintrag) => {
        const zelle = document.createElement("div");
        const plan = !heute || eintrag.stunde > jetzt;
        zelle.className = [
          "automatik-stunde",
          `m-${eintrag.aktion || "programm"}`,
          eintrag.stunde === jetzt ? "jetzt" : "",
          eintrag.stunde > 14 ? "spaet" : "",
          plan ? "plan" : "",
          eintrag.stunde === this._automatikStundeOffen ? "offen" : "",
        ]
          .filter(Boolean)
          .join(" ");
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
        if (eintrag.raum !== null && eintrag.raum !== undefined) {
          if (bezug !== null && bezug !== undefined) raum.classList.add(eintrag.raum >= bezug ? "ueber" : "unter");
          raum.textContent = `${zahl(eintrag.raum)}°`;
        } else {
          raum.textContent = "–";
        }
        zelle.appendChild(raum);
        raster.appendChild(zelle);
      });
      const huelle = document.createElement("div");
      huelle.appendChild(raster);
      huelle.appendChild(this._automatikStundenlegende());
      const offen = this._automatikStundeOffen;
      if (stunden.some((s) => s.stunde === offen)) {
        const kasten = document.createElement("div");
        kasten.className = "automatik-stundenkasten";
        stundenKasten(kreis.tag, offen, heute ? kreis.protokoll : [], (text) => this._t(text)).forEach((text, i) => {
          const zeile = document.createElement("div");
          if (i === 0) zeile.className = "kopf";
          zeile.textContent = text;
          kasten.appendChild(zeile);
        });
        huelle.appendChild(kasten);
      }
      return huelle;
    }

    /** Farben der Modi unter dem Stundenraster. */
    _automatikStundenlegende() {
      const legende = document.createElement("div");
      legende.className = "automatik-stundenlegende";
      [
        ["m-absenkung", "Sonnentag"],
        ["m-nur_ww", "nur Warmwasser"],
        ["m-programm", "Programm"],
      ].forEach(([klasse, titel]) => {
        const eintrag = document.createElement("span");
        const farbe = document.createElement("i");
        farbe.className = klasse;
        eintrag.append(farbe, this._t(titel));
        legende.appendChild(eintrag);
      });
      const hinweis = document.createElement("span");
      hinweis.textContent = this._t("Rand oben: was galt · blass: geplant · Klick zeigt die Stunde");
      legende.appendChild(hinweis);
      return legende;
    }
  };
