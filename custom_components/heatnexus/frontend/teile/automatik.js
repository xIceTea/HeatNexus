/**
 * Reiter „Automatik“.
 *
 * Je Heizkreis eine Karte mit Zustand, Begründung, Kennwerten, Tagesleiste
 * und „Erweitert“, daneben das Protokoll. Einladung, Einrichtungsdialog und
 * „Erweitert“ stehen in `einrichtung.js`. Die Daten kommen über `heatnexus/automatik`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

// Höchstens so oft wird nachgeladen, solange der Reiter offen ist.
// Wie auf dem Server: So lange darf ein Raumfühler denselben Wert zeigen, dann gilt er als veraltet.
export const VERALTET_STUNDEN = 12;
export const AUTOMATIK_TAKT_MS = 60 * 1000;

export const FELDER = [
  { name: "heizgrenze", hilfe: "Liegt die gedämpfte Außentemperatur um die Hysterese darüber, schaltet die Automatik den Heizkreis auf nur Warmwasser. Liegt sie um die Hysterese darunter und ist der Raum kühler als Soll minus 0,5 K, geht er zurück ins Programm.", titel: "Heizgrenze", einheit: "°C", schritt: 0.5 },
  { name: "hysterese", hilfe: "Abstand über und unter der Heizgrenze. Er verhindert, dass der Heizkreis bei Werten nahe der Grenze hin- und herschaltet.", titel: "Hysterese Saison", einheit: "K", schritt: 0.1 },
  { name: "tau_h", hilfe: "Wie träge die gedämpfte Außentemperatur dem Fühler folgt. Ein größerer Wert lässt kurze Wärme am Nachmittag weniger zählen. Richtwerte: Heizkörper 5 h, gemischt 15 h, Fußbodenheizung 25 h.", titel: "Zeitkonstante gedämpfte AT", einheit: "h", schritt: 1 },
  { name: "mindestdauer_h", hilfe: "So lange bleibt der Heizkreis mindestens im Programm oder auf nur Warmwasser, bevor die Automatik wieder umschaltet. Ein zu kalter Raum geht immer vor.", titel: "Mindestdauer Saisonwechsel", einheit: "h", schritt: 1 },
  { name: "entscheidung", hilfe: "Zu dieser Uhrzeit prüft die Automatik, ob ein Sonnentag bevorsteht, und setzt dann die Absenkung.", titel: "Entscheidung um", art: "zeit" },
  { name: "nachpruefung", hilfe: "Eine zweite Prüfung am Tag, etwa wenn der Morgen trüb war und die Sonne später kommt. Leer lassen, wenn sie nicht gewünscht ist.", titel: "Nachprüfung um", art: "zeit" },
  { name: "absenkung_k", hilfe: "Um so viel senkt die Automatik den Sollwert an einem Sonnentag. Die Absenkung endet an der Steuerung von selbst, spätestens zwei Stunden vor Sonnenuntergang.", titel: "Absenkung am Sonnentag", einheit: "K", schritt: 0.5 },
  { name: "rueckkehr_k", hilfe: "Fällt der Raum unter Soll minus diesen Wert, beendet die Automatik die Absenkung sofort.", titel: "Rückkehr bei Raum unter Soll minus", einheit: "K", schritt: 0.1 },
  { name: "sonnenquote", hilfe: "Ab diesem Anteil Sonne gilt der Tag als Sonnentag. Die Quote kommt aus der PV-Prognose oder aus der Bewölkung der Wetterprognose.", titel: "Sonnenquote ab", einheit: "%", schritt: 5 },
  { name: "sonnentag", hilfe: "An sonnigen Tagen senkt die Automatik den Sollwert des Heizkreises ab. Mit Thermostaten in den Räumen ist der Sonnentag ab Werk aus: Die Thermostate öffnen bei abgesenktem Sollwert nur weiter.", titel: "Sonnentag absenken", art: "janein" },
  { name: "stark", hilfe: "An sehr sonnigen Tagen ab 80 % Sonnenquote, wenn der Raum schon 1 K über dem Soll liegt, schaltet die Automatik den Heizkreis bis Sonnenuntergang auf nur Warmwasser, statt nur den Sollwert abzusenken.", titel: "Sehr sonnig: nur Warmwasser statt Absenkung", art: "janein" },
  { name: "budget", hilfe: "So viele Eingriffe darf die Automatik am Tag an die Steuerung schreiben. Die Rückkehr ins Programm zählt nicht mit und ist immer erlaubt.", titel: "Eingriffe je Tag höchstens", einheit: "", schritt: 1 },
  { name: "fenster_k_je_h", hilfe: "Fällt der Raum schneller als dieser Wert pro Stunde, gilt ein Fenster als offen. Die Automatik setzt ihre Entscheidungen dann 30 Minuten aus.", titel: "Fenster offen ab Sturz von", einheit: "K/h", schritt: 0.5 },
  {
    name: "anpassen",
    hilfe: "Die Automatik vergleicht jeden Tag Prognose und Messung und verschiebt die Prognose um die gelernte Abweichung. Ist der Schalter aus, gelten die rohen Prognosen für Anzeige und Entscheidung; gelernt wird trotzdem weiter.",
    titel: "Prognose an den Standort anpassen",
    art: "janein",
  },
  { name: "lernfenster", hilfe: "Über so viele Tage vergleicht die Automatik Prognose und Messung und passt die Prognose daran an. Ein kurzes Fenster reagiert schneller, ein langes schwankt weniger.", titel: "Prognose anpassen über", art: "wahl", optionen: [3, 7, 14], einheit: "Tage" },
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

export const HEIZFLAECHEN = [
  ["heizkoerper", "Heizkörper"],
  ["gemischt", "Gemischt"],
  ["flaeche", "Fußboden- oder Wandheizung"],
];

// Dieselbe Zuordnung wie `profile.HEIZFLAECHEN` auf dem Server.
export const PROFIL_JE_FLAECHE = { heizkoerper: "schnell", gemischt: "standard", flaeche: "traege" };

/** Zahl mit Komma; ohne Wert ein Strich. */
export function zahl(wert, stellen = 1) {
  if (wert === null || wert === undefined || Number.isNaN(Number(wert))) return "–";
  return Number(wert).toFixed(stellen).replace(".", ",");
}

/** Abweichung in Kelvin mit Vorzeichen; ohne Wert ein Strich. */
export function kelvin(wert) {
  if (wert === null || wert === undefined || Number.isNaN(Number(wert))) return "–";
  const v = Math.round(Number(wert) * 10) / 10;
  return `${v > 0 ? "+" : v < 0 ? "−" : "±"}${zahl(Math.abs(v))} K`;
}

/** Ein Raum mit Ist, eigenem Ziel und Wärmeanforderung. */
export function raumzeile(raum, t = (text) => text) {
  let text = `${raum.name} ${zahl(raum.wert)} °C`;
  if (raum.ziel !== null && raum.ziel !== undefined) text += ` → ${zahl(raum.ziel)} °C`;
  if (raum.heizt) text += ` · ${t("heizt")}`;
  return text;
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
      // Eingerichtete zuerst: Ein unbenutzter Kreis soll den benutzten nicht nach unten schieben.
      const kreise = [...(this._anlagen().length > 1 ? eigene : alle)].sort(
        (a, b) => Number(!!b.eingerichtet) - Number(!!a.eingerichtet)
      );
      // Im gemeinsamen Raster aller Anlagen sagt erst die Anlage, welcher Kreis gemeint ist.
      const mitAnlage = !anlage && this._anlagen().length > 1;
      return kreise.flatMap((roh) => {
        const kreis = mitAnlage && roh.anlage ? { ...roh, name: `${roh.anlage} · ${roh.name}` } : roh;
        const titel = kreis.name;
        if (!kreis.eingerichtet) {
          return [{ id: `automatik:${kreis.heizkreis}`, titel, knoten: this._automatikEinladung(kreis, daten) }];
        }
        return [
          { id: `automatik:${kreis.heizkreis}`, titel, knoten: this._automatikKarte(kreis, daten), breite: 2 },
          { id: `automatik-protokoll:${kreis.heizkreis}`, titel: "Protokoll", knoten: this._automatikProtokoll(kreis) },
        ];
      });
    }

    /** Alle Anlagen in einem Raster: Die Automatik arbeitet je Heizkreis, nicht je Anlage. */
    _automatikAlle() {
      this._hilfe = (this._anlagen()[0] || {}).hilfe || {};
      return this._raster({ id: "alle" }, this._automatikReiter(null), "Keine Heizkreise gefunden.");
    }

    async _automatikHolen(erzwingen = false) {
      if (this._automatikLaedt) return;
      if (!erzwingen && this._automatikZeit && Date.now() - this._automatikZeit < AUTOMATIK_TAKT_MS) return;
      this._automatikLaedt = true;
      try {
        this._automatik = await this._hass.callWS({ type: "heatnexus/automatik" });
        this._automatikZeit = Date.now();
        // Der Neuaufbau ersetzt den ganzen Baum; ein offener Dialog ginge mit.
        const dialogOffen = Boolean(this.shadowRoot.querySelector(".schleier"));
        if (this._reiter === "automatik" && !this._automatikBearbeitet && !dialogOffen) {
          // Der Neuaufbau leert die Seite kurz; ohne Merken spränge sie nach oben.
          const lagen = this._automatikScrollLagen();
          this._gebaut = false;
          this._zeichnen();
          lagen.forEach(([element, oben]) => {
            element.scrollTop = oben;
          });
        }
      } catch (err) {
        this._automatikZeit = Date.now();
        console.warn("HeatNexus: Automatik konnte nicht geladen werden", err);
      } finally {
        this._automatikLaedt = false;
      }
    }

    /** Alle gescrollten Vorfahren, auch über Shadow-Grenzen, mit ihrer Lage. */
    _automatikScrollLagen() {
      const lagen = [];
      let element = this;
      while (element) {
        if (element.scrollTop > 0) lagen.push([element, element.scrollTop]);
        element = element.parentElement || (element.getRootNode && element.getRootNode().host) || null;
      }
      const seite = typeof document !== "undefined" ? document.scrollingElement : null;
      if (seite && seite.scrollTop > 0 && !lagen.some(([e]) => e === seite)) lagen.push([seite, seite.scrollTop]);
      return lagen;
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
      // Zustand neben dem Namen, die Einrichtung rechts oben: Die Zeile darunter bleibt für die Bedienung.
      const punkt = document.createElement("span");
      punkt.className = "automatik-punkt";
      punkt.textContent = "·";
      const bearbeiten = document.createElement("button");
      bearbeiten.type = "button";
      bearbeiten.className = "automatik-knopf leise klein";
      bearbeiten.textContent = "Einrichtung bearbeiten";
      bearbeiten.disabled = !darf;
      bearbeiten.addEventListener("click", () => this._automatikDialog(kreis));
      if (kopf) {
        const titel = kopf.querySelector("h2");
        kopf.insertBefore(bearbeiten, kopf.querySelector(".fragezeichen"));
        kopf.insertBefore(marke, titel ? titel.nextSibling : kopf.firstChild);
        kopf.insertBefore(punkt, marke);
      }

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
      zeile.append(schalter, segment, profil);
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
        k.eigene_ziele
          ? ["raum", kelvin(k.abweichung), k.raum_art === "minimum" ? "Räume zum Ziel, kältester" : "Räume zum Ziel, Mittel", `Raum ${zahl(k.raum)} °C`]
          : ["raum", `${zahl(k.raum)} °C`, k.raum_art === "minimum" ? "Raum, kältester" : "Raum, Mittel", `Soll ${zahl(k.soll)} °C`],
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
        if (art === "sonne" && k.vorrang) {
          const zeile = document.createElement("div");
          zeile.className = "vorrang-zeile";
          zeile.textContent = k.vorrang.laeuft
            ? this._t("Vorrangquelle liefert")
            : this._tMit("Vorrangquellen heute {stunden} h", { stunden: zahl((k.vorrang.minuten || 0) / 60) });
          kachel.appendChild(zeile);
        }
        if (art === "raum" && ((k.raeume || []).length > 1 || k.eigene_ziele)) {
          const liste = document.createElement("div");
          liste.className = "raeume";
          k.raeume.forEach((raum) => {
            const zeile = document.createElement("div");
            zeile.textContent = raum.veraltet
              ? this._tMit("{name} {wert} °C – veraltet, zählt nicht", { name: raum.name, wert: zahl(raum.wert) })
              : raumzeile(raum, (text) => this._t(text));
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
      const jetzt = Math.floor(Number((kreis.tag || {}).jetzt));
      const grenze = (kreis.werte || {}).heizgrenze;
      // Mit Thermostaten hat jeder Raum sein eigenes Ziel; dann gibt es keinen gemeinsamen Bezug.
      const bezug = (kreis.kennwerte || {}).raum_bezug;
      stunden.forEach((eintrag) => {
        const zelle = document.createElement("div");
        zelle.className = `automatik-stunde${eintrag.stunde === jetzt ? " jetzt" : ""}${eintrag.stunde > 14 ? " spaet" : ""}${eintrag.vorrang ? " vorrang" : ""}`;
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
        if (eintrag.raum !== null && eintrag.raum !== undefined) {
          if (bezug !== null && bezug !== undefined) raum.classList.add(eintrag.raum >= bezug ? "ueber" : "unter");
          raum.textContent = zahl(eintrag.raum);
        } else {
          raum.textContent = "–";
        }
        zelle.appendChild(raum);
        raster.appendChild(zelle);
      });
      return raster;
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
  };
