/**
 * Reiter „Automatik“.
 *
 * Je Heizkreis eine Karte mit Zustand, Begründung, Kennwerten, Tagesleiste
 * und „Erweitert“, daneben das Protokoll. Ohne Automatik lädt eine Karte zum
 * Einrichten ein. Die Daten kommen über `heatnexus/automatik`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

// Höchstens so oft wird nachgeladen, solange der Reiter offen ist.
// Wie auf dem Server: So lange darf ein Raumfühler denselben Wert zeigen, dann gilt er als veraltet.
export const VERALTET_STUNDEN = 12;
export const AUTOMATIK_TAKT_MS = 60 * 1000;

export const FELDER = [
  { name: "heizgrenze", titel: "Heizgrenze", einheit: "°C", schritt: 0.5 },
  { name: "hysterese", titel: "Hysterese Saison", einheit: "K", schritt: 0.1 },
  { name: "tau_h", titel: "Zeitkonstante gedämpfte AT", einheit: "h", schritt: 1 },
  { name: "mindestdauer_h", titel: "Mindestdauer Saisonwechsel", einheit: "h", schritt: 1 },
  { name: "entscheidung", titel: "Entscheidung um", art: "zeit" },
  { name: "nachpruefung", titel: "Nachprüfung um", art: "zeit" },
  { name: "absenkung_k", titel: "Absenkung am Sonnentag", einheit: "K", schritt: 0.5 },
  { name: "rueckkehr_k", titel: "Rückkehr bei Raum unter Soll minus", einheit: "K", schritt: 0.1 },
  { name: "sonnenquote", titel: "Sonnenquote ab", einheit: "%", schritt: 5 },
  { name: "stark", titel: "Starke Stufe: nur Warmwasser", art: "janein" },
  { name: "budget", titel: "Eingriffe je Tag höchstens", einheit: "", schritt: 1 },
  { name: "fenster_k_je_h", titel: "Fenster offen ab Sturz von", einheit: "K/h", schritt: 0.5 },
  { name: "lernfenster", titel: "Prognose anpassen über", art: "wahl", optionen: [3, 7, 14], einheit: "Tage" },
];

export const ZUSTAENDE = {
  programm: "Heizen nach Programm",
  sonnentag: "Sonnentag",
  nur_ww: "Nur Warmwasser",
  abwesend: "Abwesend",
  pausiert: "Pausiert",
  fenster: "Fenster offen",
  keine_daten: "Keine Daten",
  sicherheit: "Sicherheit",
  aus: "Aus",
};

export const PROTOKOLL_ARTEN = {
  geschrieben: "geschrieben",
  haette: "hätte geschrieben",
  abgelehnt: "abgelehnt",
  budget: "Budget erreicht",
  geprueft: "geprüft",
  eingriff: "Handeingriff",
};

export const PROFILE = [
  ["schnell", "Schnell – Heizkörper"],
  ["standard", "Standard – gemischt"],
  ["traege", "Träge – Fußboden- oder Wandheizung"],
];

const HEIZFLAECHEN = [
  ["heizkoerper", "Heizkörper"],
  ["gemischt", "Gemischt"],
  ["flaeche", "Fußboden- oder Wandheizung"],
];

// Dieselbe Zuordnung wie `profile.HEIZFLAECHEN` auf dem Server.
const PROFIL_JE_FLAECHE = { heizkoerper: "schnell", gemischt: "standard", flaeche: "traege" };

/** Zahl mit Komma; ohne Wert ein Strich. */
export function zahl(wert, stellen = 1) {
  if (wert === null || wert === undefined || Number.isNaN(Number(wert))) return "–";
  return Number(wert).toFixed(stellen).replace(".", ",");
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
    const v = Number(eintrag.versatz);
    return `${name} angepasst ${v > 0 ? "+" : v < 0 ? "−" : "±"}${zahl(Math.abs(v))} K`;
  }
  if (art === "sonne" && eintrag.faktor !== null && eintrag.faktor !== undefined) {
    const prozent = Math.round((Number(eintrag.faktor) - 1) * 100);
    return `${name} angepasst ${prozent > 0 ? "+" : prozent < 0 ? "−" : "±"}${Math.abs(prozent)} %`;
  }
  return `${name}: lernt noch ${eintrag.tage || 0}/${noetig}`;
}

export const AutomatikMixin = (Basis) =>
  class extends Basis {
    // -------------------------------------------------------------------
    // Reiter „Automatik“
    // -------------------------------------------------------------------
    _automatikReiter(anlage) {
      this._automatikHolen();
      this._automatikUhrStellen();
      const daten = this._automatik;
      if (!daten) {
        return [{ id: "automatik", titel: "Automatik", knoten: this._hinweisKnoten("Die Automatik lädt …") }];
      }
      const alle = daten.heizkreise || [];
      const eigene = alle.filter((kreis) => !anlage || !anlage.id || kreis.anlage_id === anlage.id);
      const kreise = this._anlagen().length > 1 ? eigene : alle;
      return kreise.flatMap((kreis) => {
        if (!kreis.eingerichtet) {
          return [{ id: `automatik:${kreis.heizkreis}`, titel: kreis.name, knoten: this._automatikEinladung(kreis, daten) }];
        }
        return [
          { id: `automatik:${kreis.heizkreis}`, titel: kreis.name, knoten: this._automatikKarte(kreis, daten), breite: 2 },
          { id: `automatik-protokoll:${kreis.heizkreis}`, titel: "Protokoll", knoten: this._automatikProtokoll(kreis) },
        ];
      });
    }

    async _automatikHolen(erzwingen = false) {
      if (this._automatikLaedt) return;
      if (!erzwingen && this._automatikZeit && Date.now() - this._automatikZeit < AUTOMATIK_TAKT_MS) return;
      this._automatikLaedt = true;
      try {
        this._automatik = await this._hass.callWS({ type: "heatnexus/automatik" });
        this._automatikZeit = Date.now();
        if (this._reiter === "automatik" && !this._automatikBearbeitet) {
          this._gebaut = false;
          this._zeichnen();
        }
      } catch (err) {
        this._automatikZeit = Date.now();
        console.warn("HeatNexus: Automatik konnte nicht geladen werden", err);
      } finally {
        this._automatikLaedt = false;
      }
    }

    _automatikUhrStellen() {
      if (this._automatikUhr) return;
      this._automatikUhr = setInterval(() => {
        if (!this.isConnected || this._reiter !== "automatik") {
          clearInterval(this._automatikUhr);
          this._automatikUhr = null;
          return;
        }
        this._automatikHolen();
      }, AUTOMATIK_TAKT_MS);
    }

    async _automatikAufruf(nachricht) {
      try {
        await this._hass.callWS(nachricht);
        this._automatikBearbeitet = false;
        await this._automatikHolen(true);
        return true;
      } catch (err) {
        this._melden((err && err.message) || this._t("Die Automatik hat die Änderung nicht übernommen."));
        return false;
      }
    }

    _automatikEinstellen(kreis, aenderung) {
      return this._automatikAufruf({ type: "heatnexus/automatik/einstellen", heizkreis: kreis.heizkreis, ...aenderung });
    }

    // --- Karte ---------------------------------------------------------
    _automatikKarte(kreis, daten) {
      const karte = this._karte(kreis.name, this._hilfe && this._hilfe.Automatik);
      karte.classList.add("automatik");
      const darf = !!daten.darf_aendern;
      const kopf = karte.querySelector(".kartenkopf");
      const marke = document.createElement("span");
      marke.className = `automatik-marke z-${kreis.zustand}`;
      marke.textContent = ZUSTAENDE[kreis.zustand] || kreis.zustand;
      if (kreis.konfig.modus === "beobachten" && kreis.konfig.aktiv) {
        marke.textContent += ` · ${this._t("beobachtet")}`;
      }
      if (kopf) kopf.insertBefore(marke, kopf.querySelector(".fragezeichen"));

      karte.appendChild(this._automatikSteuerzeile(kreis, darf));
      const hinweis = this._automatikHinweis(kreis, darf);
      if (hinweis) karte.appendChild(hinweis);

      const warum = document.createElement("div");
      warum.className = "automatik-warum";
      warum.textContent = kreis.begruendung || "";
      karte.appendChild(warum);
      karte.appendChild(this._automatikKennwerte(kreis));

      const ueberschrift = document.createElement("h3");
      ueberschrift.textContent = "Heute";
      karte.appendChild(ueberschrift);
      karte.appendChild(this._automatikTag(kreis));
      karte.appendChild(this._automatikErweitert(kreis, daten, darf));
      return karte;
    }

    _automatikSteuerzeile(kreis, darf) {
      const zeile = document.createElement("div");
      zeile.className = "automatik-zeile";
      const schalter = document.createElement("button");
      schalter.type = "button";
      schalter.className = `automatik-schalter${kreis.konfig.aktiv ? " an" : ""}`;
      schalter.setAttribute("role", "switch");
      schalter.setAttribute("aria-checked", String(!!kreis.konfig.aktiv));
      schalter.disabled = !darf;
      const knopf = document.createElement("i");
      const text = document.createElement("span");
      text.textContent = "Automatik";
      schalter.append(knopf, text);
      schalter.addEventListener("click", () => this._automatikEinstellen(kreis, { aktiv: !kreis.konfig.aktiv }));

      const segment = document.createElement("div");
      segment.className = "automatik-segment";
      [
        ["beobachten", "Beobachten"],
        ["schalten", "Schalten"],
      ].forEach(([modus, titel]) => {
        const taste = document.createElement("button");
        taste.type = "button";
        taste.textContent = titel;
        taste.disabled = !darf;
        taste.setAttribute("aria-pressed", String(kreis.konfig.modus === modus));
        taste.addEventListener("click", () => {
          if (kreis.konfig.modus !== modus) this._automatikEinstellen(kreis, { modus });
        });
        segment.appendChild(taste);
      });

      const profil = document.createElement("span");
      profil.className = "automatik-profil";
      const eintrag = PROFILE.find(([name]) => name === kreis.konfig.profil);
      profil.textContent = eintrag ? eintrag[1] : kreis.konfig.profil;
      const bearbeiten = document.createElement("button");
      bearbeiten.type = "button";
      bearbeiten.className = "automatik-knopf leise klein";
      bearbeiten.textContent = "Einrichtung bearbeiten";
      bearbeiten.disabled = !darf;
      bearbeiten.addEventListener("click", () => this._automatikDialog(kreis));
      zeile.append(schalter, segment, profil, bearbeiten);
      return zeile;
    }

    _automatikHinweis(kreis, darf) {
      const pausiert = kreis.zustand === "pausiert";
      const beobachtet = kreis.konfig.modus === "beobachten" && kreis.konfig.aktiv;
      if (!pausiert && !beobachtet) return null;
      const hinweis = document.createElement("div");
      hinweis.className = "automatik-hinweis";
      const text = document.createElement("div");
      text.className = "text";
      const taste = document.createElement("button");
      taste.type = "button";
      taste.disabled = !darf;
      if (pausiert) {
        text.textContent = kreis.begruendung || "";
        taste.className = "automatik-knopf";
        taste.textContent = this._t("Wieder übernehmen");
        taste.addEventListener("click", () =>
          this._automatikAufruf({ type: "heatnexus/automatik/uebernehmen", heizkreis: kreis.heizkreis })
        );
      } else {
        const tage = Math.max(0, Math.floor((Date.now() - Date.parse(kreis.beobachtet_seit)) / 86400000));
        const haette = (kreis.protokoll || []).filter((e) => e.art === "haette").length;
        const seit = new Date(kreis.beobachtet_seit);
        const datum = `${seit.getDate()}.${seit.getMonth() + 1}.`;
        text.textContent = this._tMit("Beobachtungsmodus seit dem {datum} – vorgemerkte Eingriffe: {anzahl}. Nichts davon ging an die Steuerung.", { datum, anzahl: haette });
        taste.className = tage >= 7 ? "automatik-knopf" : "automatik-knopf leise";
        taste.textContent = this._t("Jetzt scharf schalten");
        taste.addEventListener("click", () => this._automatikEinstellen(kreis, { modus: "schalten" }));
      }
      hinweis.append(text, taste);
      return hinweis;
    }

    _automatikKennwerte(kreis) {
      const k = kreis.kennwerte || {};
      const w = kreis.werte || {};
      const raster = document.createElement("div");
      raster.className = "automatik-werte";
      const kacheln = [
        ["sonne", `${zahl(k.sonnenquote, 0)} %`, "Sonnenquote heute", `ab ${zahl(w.sonnenquote, 0)} %`],
        ["", `${zahl(k.raum)} °C`, k.raum_art === "minimum" ? "Raum, kältester" : "Raum, Mittel", `Soll ${zahl(k.soll)} °C`],
        ["", `${zahl(k.at)} · ${zahl(k.at_gedaempft)} °C`, "Außen · gedämpft", `Heizgrenze ${zahl(k.heizgrenze)} °C`],
        ["", `${k.eingriffe ?? 0} / ${k.budget ?? "–"}`, "Eingriffe heute", "Budget"],
      ];
      kacheln.forEach(([art, wert, bezeichnung, schwelle]) => {
        const kachel = document.createElement("div");
        kachel.className = `automatik-wert ${art}`;
        const zeilen = [
          ["zahl", wert],
          ["bez", bezeichnung],
          ["schw", schwelle],
        ];
        zeilen.forEach(([klasse, inhalt]) => {
          const teil = document.createElement("div");
          teil.className = klasse;
          teil.textContent = inhalt;
          kachel.appendChild(teil);
        });
        if (bezeichnung.startsWith("Raum") && (k.raeume || []).length > 1) {
          const liste = document.createElement("div");
          liste.className = "raeume";
          k.raeume.forEach((raum) => {
            const zeile = document.createElement("div");
            zeile.textContent = raum.veraltet
              ? this._tMit("{name} {wert} °C – veraltet, zählt nicht", { name: raum.name, wert: zahl(raum.wert) })
              : `${raum.name} ${zahl(raum.wert)} °C`;
            if (raum.veraltet) zeile.className = "veraltet";
            liste.appendChild(zeile);
          });
          kachel.appendChild(liste);
        }
        raster.appendChild(kachel);
      });
      return raster;
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
      bild.innerHTML = tagesleisteSvg(tag, 1000, (kreis.werte || {}).heizgrenze);
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
      const jetzt = Math.floor(Number((kreis.tag || {}).jetzt));
      const grenze = (kreis.werte || {}).heizgrenze;
      const soll = (kreis.kennwerte || {}).soll;
      stunden.forEach((eintrag) => {
        const zelle = document.createElement("div");
        zelle.className = `automatik-stunde${eintrag.stunde === jetzt ? " jetzt" : ""}${eintrag.stunde > 14 ? " spaet" : ""}`;
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
        if (eintrag.raum !== null && eintrag.raum !== undefined && soll !== null && soll !== undefined) {
          raum.classList.add(eintrag.raum >= soll ? "ueber" : "unter");
          raum.textContent = zahl(eintrag.raum);
        } else {
          raum.textContent = "–";
        }
        zelle.appendChild(raum);
        raster.appendChild(zelle);
      });
      return raster;
    }

    // --- Erweitert -----------------------------------------------------
    _automatikErweitert(kreis, daten, darf) {
      const bereich = document.createElement("details");
      bereich.className = "automatik-erweitert";
      const kopf = document.createElement("summary");
      kopf.textContent = "Erweitert";
      bereich.appendChild(kopf);
      const vorgabe = (daten.profile || {})[kreis.konfig.profil] || {};
      const eingaben = {};
      const raster = document.createElement("div");
      raster.className = "automatik-felder";

      const flaechen = HEIZFLAECHEN.find(([name]) => name === kreis.konfig.heizflaechen);
      const profilFeld = this._automatikFeld("Profil", flaechen ? flaechen[1] : "");
      profilFeld.classList.add("breit");
      const profilWahl = document.createElement("select");
      profilWahl.disabled = !darf;
      PROFILE.forEach(([name, titel]) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = titel;
        option.selected = name === kreis.konfig.profil;
        profilWahl.appendChild(option);
      });
      profilWahl.addEventListener("change", () =>
        this._automatikEinstellen(kreis, { profil: profilWahl.value, eigene: {} })
      );
      profilFeld.querySelector(".eingabe").appendChild(profilWahl);
      raster.appendChild(profilFeld);

      FELDER.forEach((feld) => {
        const wert = (kreis.werte || {})[feld.name];
        const basis = vorgabe[feld.name];
        const geaendert = wert !== basis;
        const basisText = typeof basis === "number" ? zahl(basis, Number.isInteger(basis) ? 0 : 1) : basis || "–";
        const anzeige = feld.art === "janein" ? (basis ? "Ein" : "Aus") : `${basisText} ${feld.einheit || ""}`.trim();
        const knoten = this._automatikFeld(feld.titel, `Profil: ${anzeige || "–"}`, geaendert);
        const eingabe = this._automatikEingabe(feld, wert, darf);
        eingabe.addEventListener("input", () => {
          this._automatikBearbeitet = true;
        });
        eingaben[feld.name] = [feld, eingabe];
        knoten.querySelector(".eingabe").appendChild(eingabe);
        if (feld.einheit) {
          const einheit = document.createElement("span");
          einheit.className = "einheit";
          einheit.textContent = feld.einheit;
          knoten.querySelector(".eingabe").appendChild(einheit);
        }
        raster.appendChild(knoten);
      });
      bereich.appendChild(raster);

      const leiste = document.createElement("div");
      leiste.className = "automatik-leiste";
      const zuruecksetzen = document.createElement("button");
      zuruecksetzen.type = "button";
      zuruecksetzen.className = "automatik-knopf leise";
      zuruecksetzen.textContent = "Profilwerte wiederherstellen";
      zuruecksetzen.disabled = !darf;
      zuruecksetzen.addEventListener("click", () => this._automatikEinstellen(kreis, { eigene: {} }));
      const speichern = document.createElement("button");
      speichern.type = "button";
      speichern.className = "automatik-knopf";
      speichern.textContent = "Speichern";
      speichern.disabled = !darf;
      speichern.addEventListener("click", () => this._automatikEinstellen(kreis, { eigene: this._automatikEigene(eingaben) }));
      const entfernen = document.createElement("button");
      entfernen.type = "button";
      entfernen.className = "automatik-knopf leise warnung";
      entfernen.textContent = "Automatik entfernen";
      entfernen.disabled = !darf;
      entfernen.addEventListener("click", () => this._automatikEntfernen(kreis));
      const links = document.createElement("div");
      links.className = "automatik-leiste-links";
      links.append(entfernen);
      leiste.append(links, zuruecksetzen, speichern);
      bereich.appendChild(leiste);
      return bereich;
    }

    async _automatikEntfernen(kreis) {
      const ja = await this._bestaetigen(
        this._tMit("Automatik für {name} entfernen?", { name: kreis.name }),
        this._t("Eigene Eingriffe an der Steuerung werden zurückgenommen. Einstellungen und Protokoll gehen verloren."),
        null,
        { ja: this._t("Entfernen") }
      );
      if (!ja) return;
      await this._automatikAufruf({ type: "heatnexus/automatik/entfernen", heizkreis: kreis.heizkreis });
    }

    _automatikFeld(titel, unter, geaendert = false) {
      const feld = document.createElement("div");
      feld.className = `automatik-feld${geaendert ? " geaendert" : ""}`;
      const beschriftung = document.createElement("label");
      beschriftung.textContent = titel;
      const eingabe = document.createElement("div");
      eingabe.className = "eingabe";
      const hinweis = document.createElement("div");
      hinweis.className = "profilwert";
      hinweis.textContent = unter;
      feld.append(beschriftung, eingabe, hinweis);
      return feld;
    }

    _automatikEingabe(feld, wert, darf) {
      if (feld.art === "wahl") {
        const wahl = document.createElement("select");
        feld.optionen.forEach((option) => {
          const eintrag = document.createElement("option");
          eintrag.value = String(option);
          eintrag.textContent = String(option);
          eintrag.selected = Number(wert) === option;
          wahl.appendChild(eintrag);
        });
        wahl.disabled = !darf;
        return wahl;
      }
      if (feld.art === "janein") {
        const wahl = document.createElement("select");
        [
          ["false", "Aus"],
          ["true", "Ein"],
        ].forEach(([schluessel, titel]) => {
          const option = document.createElement("option");
          option.value = schluessel;
          option.textContent = titel;
          option.selected = String(!!wert) === schluessel;
          wahl.appendChild(option);
        });
        wahl.disabled = !darf;
        return wahl;
      }
      const eingabe = document.createElement("input");
      eingabe.disabled = !darf;
      if (feld.art === "zeit") {
        eingabe.type = "time";
        eingabe.value = wert || "";
      } else {
        eingabe.type = "number";
        eingabe.step = String(feld.schritt);
        eingabe.value = wert ?? "";
      }
      return eingabe;
    }

    _automatikEigene(eingaben) {
      const eigene = {};
      Object.entries(eingaben).forEach(([name, [feld, eingabe]]) => {
        if (feld.art === "janein") eigene[name] = eingabe.value === "true";
        else if (feld.art === "wahl") eigene[name] = Number(eingabe.value);
        else if (feld.art === "zeit") eigene[name] = eingabe.value || "";
        else if (eingabe.value !== "") eigene[name] = Number(eingabe.value);
      });
      return eigene;
    }

    // --- Protokoll -----------------------------------------------------
    _automatikProtokoll(kreis) {
      const karte = this._karte("Protokoll");
      const k = kreis.kennwerte || {};
      const budget = document.createElement("div");
      budget.className = "automatik-budget";
      for (let i = 0; i < (k.budget || 0); i += 1) {
        const strich = document.createElement("i");
        if (i < (k.eingriffe || 0)) strich.className = "voll";
        budget.appendChild(strich);
      }
      karte.appendChild(budget);
      const liste = document.createElement("ul");
      liste.className = "automatik-protokoll";
      const eintraege = kreis.protokoll || [];
      if (!eintraege.length) karte.appendChild(this._hinweisKnoten("Noch keine Entscheidung."));
      eintraege.forEach((eintrag) => {
        const zeile = document.createElement("li");
        const zeit = document.createElement("span");
        zeit.className = "zeit";
        const datum = new Date(eintrag.zeit);
        const heute = new Date().toDateString() === datum.toDateString();
        zeit.textContent = heute
          ? datum.toTimeString().slice(0, 5)
          : `${datum.getDate()}.${datum.getMonth() + 1}. ${datum.toTimeString().slice(0, 5)}`;
        const text = document.createElement("span");
        text.textContent = eintrag.text;
        const art = document.createElement("span");
        art.className = `art ${eintrag.art}`;
        art.textContent = PROTOKOLL_ARTEN[eintrag.art] || eintrag.art;
        zeile.append(zeit, text, art);
        liste.appendChild(zeile);
      });
      karte.appendChild(liste);
      return karte;
    }

    // --- Einrichten ----------------------------------------------------
    _automatikEinladung(kreis, daten) {
      const karte = this._karte(kreis.name, this._hilfe && this._hilfe.Automatik);
      const text = document.createElement("p");
      text.className = "automatik-einladung";
      text.textContent =
        "Die Automatik senkt den Heizkreis an sonnigen Tagen ab und schaltet in der Übergangszeit auf nur Warmwasser. Sie beginnt im Beobachtungsmodus und schreibt dann noch nichts an die Steuerung.";
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "automatik-knopf";
      taste.textContent = "Automatik einrichten";
      taste.disabled = !daten.darf_aendern;
      taste.addEventListener("click", () => this._automatikDialog(kreis));
      karte.append(text, taste);
      return karte;
    }

    async _automatikDialog(kreis) {
      let kandidaten;
      try {
        kandidaten = await this._hass.callWS({ type: "heatnexus/automatik/kandidaten" });
      } catch (err) {
        this._melden(this._t("Die Auswahllisten konnten nicht geladen werden."));
        return;
      }
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog automatik-dialog";
      dialog.setAttribute("role", "dialog");
      const titel = document.createElement("h3");
      titel.className = "dialog-titel";
      const k = kreis.eingerichtet ? kreis.konfig : null;
      titel.textContent = k
        ? this._tMit("Einrichtung von {name} ändern", { name: kreis.name })
        : this._tMit("Automatik für {name} einrichten", { name: kreis.name });
      dialog.appendChild(titel);

      const heizflaechen = this._automatikAuswahl(HEIZFLAECHEN, (k && k.heizflaechen) || "gemischt");
      const raeume = this._automatikHaken(kandidaten.temperatur, k ? k.raeume : []);
      const raumArt = this._automatikAuswahl(
        [
          ["mittel", this._t("Mittel der Räume")],
          ["minimum", this._t("Kältester Raum")],
        ],
        (k && k.raum_art) || "mittel"
      );
      const wetter = this._automatikAuswahl(
        this._automatikMitGewaehlt(kandidaten.wetter.map((e) => [e.entity_id, e.name]), k && k.wetter),
        (k && k.wetter) || ""
      );
      const pv = this._automatikAuswahl(
        this._automatikMitGewaehlt([["", this._t("Keine")], ...kandidaten.pv.map((e) => [e.entity_id, e.name])], k && k.pv),
        (k && k.pv) || ""
      );
      const pvIst = this._automatikAuswahl(
        this._automatikMitGewaehlt([["", this._t("Keine")], ...(kandidaten.pv_ist || []).map((e) => [e.entity_id, e.name])], k && k.pv_ist),
        (k && k.pv_ist) || ""
      );
      const personen = this._automatikHaken(kandidaten.personen, k ? k.personen : []);
      const fenster = this._automatikHaken(kandidaten.fenster, k ? k.fenster : []);
      const erkennung = document.createElement("input");
      erkennung.type = "checkbox";
      erkennung.checked = !!(k && k.fenster_erkennung);

      const abschnitte = [
        [this._t("1 · Heizflächen"), [heizflaechen]],
        [this._t("2 · Räume"), [raeume, this._automatikBeschriftet(this._t("Zählt"), raumArt)]],
        [
          this._t("3 · Wetter und PV-Prognose"),
          [
            this._automatikBeschriftet(this._t("Wetter"), wetter),
            this._automatikBeschriftet(this._t("PV-Prognose, Tagesertrag (optional)"), pv),
            this._automatikBeschriftet(this._t("PV-Ertrag tatsächlich, zum Anpassen (optional)"), pvIst),
          ],
        ],
        [
          this._t("4 · Optional: Anwesenheit und Fenster"),
          [
            this._automatikBeschriftet(this._t("Personen"), personen),
            this._automatikBeschriftet(this._t("Fensterkontakte"), fenster),
            this._automatikMitText(erkennung, this._t("Fenster aus Temperatursturz erkennen")),
          ],
        ],
      ];
      abschnitte.forEach(([ueberschrift, knoten]) => {
        const abschnitt = document.createElement("section");
        const kopf = document.createElement("h4");
        kopf.textContent = ueberschrift;
        abschnitt.append(kopf, ...knoten);
        dialog.appendChild(abschnitt);
      });

      const leiste = document.createElement("div");
      leiste.className = "dialog-leiste";
      const abbrechen = document.createElement("button");
      abbrechen.type = "button";
      abbrechen.className = "dialog-taste";
      abbrechen.textContent = this._t("Abbrechen");
      const einrichten = document.createElement("button");
      einrichten.type = "button";
      einrichten.className = "dialog-taste bestaetigen";
      einrichten.textContent = k ? this._t("Übernehmen") : this._t("Einrichten");
      leiste.append(abbrechen, einrichten);
      dialog.appendChild(leiste);
      schleier.appendChild(dialog);
      const weg = () => schleier.remove();
      abbrechen.addEventListener("click", weg);
      einrichten.addEventListener("click", async () => {
        const gewaehlt = (liste) => Array.from(liste.querySelectorAll("input:checked")).map((e) => e.value);
        const nachricht = {
          type: k ? "heatnexus/automatik/einstellen" : "heatnexus/automatik/einrichten",
          heizkreis: kreis.heizkreis,
          heizflaechen: heizflaechen.value,
          raeume: gewaehlt(raeume),
          raum_art: raumArt.value,
          wetter: wetter.value,
          pv: pv.value || null,
          pv_ist: pvIst.value || null,
          personen: gewaehlt(personen),
          fenster: gewaehlt(fenster),
          fenster_erkennung: erkennung.checked,
        };
        // Andere Heizflächen heißen anderes Profil; eigene Werte gehörten zum alten.
        if (k && nachricht.heizflaechen !== k.heizflaechen) {
          nachricht.profil = PROFIL_JE_FLAECHE[nachricht.heizflaechen];
          nachricht.eigene = {};
        }
        if (!nachricht.raeume.length || !nachricht.wetter) {
          this._melden(this._t("Mindestens ein Raum und eine Wetter-Entität sind nötig."));
          return;
        }
        if (await this._automatikAufruf(nachricht)) weg();
      });
      this.shadowRoot.appendChild(schleier);
    }

    _automatikAuswahl(eintraege, vorgabe) {
      const wahl = document.createElement("select");
      eintraege.forEach(([wert, titel]) => {
        const option = document.createElement("option");
        option.value = wert;
        option.textContent = this._t(titel);
        option.selected = wert === vorgabe;
        wahl.appendChild(option);
      });
      return wahl;
    }

    _automatikHaken(eintraege, gewaehlt = []) {
      const liste = document.createElement("div");
      liste.className = "automatik-haken";
      const bekannt = new Set(eintraege.map((e) => e.entity_id));
      const alle = [...gewaehlt.filter((id) => !bekannt.has(id)).map((id) => ({ entity_id: id, name: id, bereich: "" })), ...eintraege];
      if (!alle.length) liste.appendChild(this._hinweisKnoten(this._t("Keine passenden Entitäten gefunden.")));
      alle.forEach((eintrag) => {
        const haken = document.createElement("input");
        haken.type = "checkbox";
        haken.value = eintrag.entity_id;
        haken.checked = gewaehlt.includes(eintrag.entity_id);
        const teile = [eintrag.name, eintrag.bereich, eintrag.wert].filter(Boolean);
        const alter = eintrag.seit ? (Date.now() - Date.parse(eintrag.seit)) / 3600000 : 0;
        if (alter > VERALTET_STUNDEN) teile.push(this._tMit("seit {stunden} h unverändert", { stunden: Math.floor(alter) }));
        const zeile = this._automatikMitText(haken, teile.join(" · "));
        if (alter > VERALTET_STUNDEN) zeile.classList.add("veraltet");
        liste.appendChild(zeile);
      });
      return liste;
    }

    _automatikBeschriftet(text, knoten) {
      const rahmen = document.createElement("div");
      rahmen.className = "automatik-beschriftet";
      const titel = document.createElement("div");
      titel.className = "automatik-unter";
      titel.textContent = text;
      rahmen.append(titel, knoten);
      return rahmen;
    }

    _automatikMitGewaehlt(eintraege, gewaehlt) {
      if (!gewaehlt || eintraege.some(([wert]) => wert === gewaehlt)) return eintraege;
      return [...eintraege, [gewaehlt, gewaehlt]];
    }

    _automatikMitText(eingabe, text) {
      const zeile = document.createElement("label");
      zeile.className = "automatik-haken-zeile";
      const titel = document.createElement("span");
      titel.textContent = text;
      zeile.append(eingabe, titel);
      return zeile;
    }
  };
