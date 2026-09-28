/**
 * Reiter „Automatik“.
 *
 * Je Heizkreis eine Karte mit Zustand, Begründung, Kennwerten, Tagesbild
 * und „Erweitert“, daneben das Protokoll. Einladung, Einrichtungsdialog und
 * „Erweitert“ stehen in `einrichtung.js`, das Tagesbild in `tagesbild.js`.
 * Die Daten kommen über `heatnexus/automatik`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

// Höchstens so oft wird nachgeladen, solange der Reiter offen ist.
// Wie auf dem Server: So lange darf ein Raumfühler denselben Wert zeigen, dann gilt er als veraltet.
export const VERALTET_STUNDEN = 12;
export const AUTOMATIK_TAKT_MS = 60 * 1000;

export const FELDER = [
  { name: "grenze_versatz", hilfe: "Die Automatik richtet sich nach der Heizgrenze der Steuerung (TA Heizbetrieb) und verschiebt sie um diesen Wert. Negativ schaltet früher auf nur Warmwasser. Die Ausrichtung setzt ihn; hier lässt er sich fein einstellen.", titel: "Abstand zur Heizgrenze der Steuerung", einheit: "K", schritt: 0.5 },
  { name: "hysterese", hilfe: "Abstand über und unter der Heizgrenze. Er verhindert, dass der Heizkreis bei Werten nahe der Grenze hin- und herschaltet.", titel: "Hysterese Saison", einheit: "K", schritt: 0.1 },
  { name: "tau_h", hilfe: "Wie träge die gedämpfte Außentemperatur dem Fühler folgt. Ein größerer Wert lässt kurze Wärme am Nachmittag weniger zählen. Richtwerte: Heizkörper 5 h, gemischt 15 h, Fußbodenheizung 25 h.", titel: "Zeitkonstante gedämpfte AT", einheit: "h", schritt: 1 },
  { name: "mindestdauer_h", hilfe: "So lange bleibt der Heizkreis mindestens im Programm oder auf nur Warmwasser, bevor die Automatik wieder umschaltet. Ein zu kalter Raum geht immer vor.", titel: "Mindestdauer Saisonwechsel", einheit: "h", schritt: 1 },
  { name: "entscheidung", hilfe: "Zu dieser Uhrzeit prüft die Automatik, ob ein Sonnentag bevorsteht, und setzt dann die Absenkung.", titel: "Entscheidung um", art: "zeit" },
  { name: "nachpruefung", hilfe: "Eine zweite Prüfung am Tag, etwa wenn der Morgen trüb war und die Sonne später kommt. Leer lassen, wenn sie nicht gewünscht ist.", titel: "Nachprüfung um", art: "zeit" },
  { name: "absenkung_k", hilfe: "Um so viel senkt die Automatik den Sollwert an einem Sonnentag. Die Absenkung endet an der Steuerung von selbst, spätestens zwei Stunden vor Sonnenuntergang.", titel: "Absenkung am Sonnentag", einheit: "K", schritt: 0.5 },
  { name: "rueckkehr_k", hilfe: "Fällt der Raum unter Soll minus diesen Wert, beendet die Automatik die Absenkung sofort.", titel: "Rückkehr bei Raum unter Soll minus", einheit: "K", schritt: 0.1 },
  { name: "sonnenquote", hilfe: "Ab diesem Anteil Sonne gilt der Tag als Sonnentag. Die Quote kommt aus der PV-Prognose oder aus der Bewölkung der Wetterprognose.", titel: "Sonnenquote ab", einheit: "%", schritt: 5 },
  { name: "sonnentag", hilfe: "An sonnigen Tagen senkt die Automatik den Sollwert des Heizkreises ab. Mit Thermostaten in den Räumen ist der Sonnentag ab Werk aus: Die Thermostate öffnen bei abgesenktem Sollwert nur weiter.", titel: "Sonnentag absenken", art: "janein" },
  { name: "stark", hilfe: "An sehr sonnigen Tagen ab 80 % Sonnenquote, wenn die Räume schon über ihrem Ziel liegen, schaltet die Automatik den Heizkreis bis Sonnenuntergang auf nur Warmwasser, statt nur den Sollwert abzusenken.", titel: "Sehr sonnig: nur Warmwasser statt Absenkung", art: "janein" },
  { name: "stark_k", hilfe: "So weit müssen die Räume über ihrem Ziel liegen, damit ein sehr sonniger Tag auf nur Warmwasser schaltet.", titel: "Sehr sonnig ab Räumen über Ziel", einheit: "K", schritt: 0.1 },
  { name: "ruhe_h", hilfe: "So lange darf kein Thermostat Wärme angefordert haben, bevor die Automatik auf nur Warmwasser schaltet.", titel: "Räume ruhig seit", einheit: "h", schritt: 0.5 },
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
  einstellung: "Einstellung",
};

export const PROFILE = [
  ["schnell", "Schnell – Heizkörper"],
  ["standard", "Standard – gemischt"],
  ["traege", "Träge – Fußboden- oder Wandheizung"],
];

export const AUSRICHTUNGEN = [
  ["eco", "Eco – früh und kräftig eingreifen"],
  ["ausgewogen", "Ausgewogen"],
  ["komfort", "Komfort – spät und sanft eingreifen"],
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
  if (raum.aus) text += ` · ${t("aus")}`;
  return text;
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
        kopf.parentElement.insertBefore(this._automatikMeta(kreis), kopf.nextSibling);
      }

      karte.appendChild(this._automatikSteuerzeile(kreis, darf));
      const hinweis = this._automatikHinweis(kreis, darf);
      if (hinweis) karte.appendChild(hinweis);

      const warum = document.createElement("div");
      warum.className = "automatik-warum";
      warum.textContent = kreis.begruendung || "";
      karte.appendChild(warum);
      karte.appendChild(this._automatikKennwerte(kreis));
      karte.appendChild(this._automatikGrenzen(kreis, darf));

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

      // Die Ausrichtung ist die Einstellung, die man im Alltag wechselt; sie steht deshalb hier.
      const ausrichtung = document.createElement("div");
      ausrichtung.className = "automatik-segment ausrichtung";
      const gewaehlt = kreis.konfig.ausrichtung || "ausgewogen";
      [
        ["eco", "Eco"],
        ["ausgewogen", "Ausgewogen"],
        ["komfort", "Komfort"],
      ].forEach(([wert, titel]) => {
        const taste = document.createElement("button");
        taste.type = "button";
        taste.textContent = titel;
        taste.title = this._t((AUSRICHTUNGEN.find(([name]) => name === wert) || [])[1] || titel);
        taste.disabled = !darf;
        taste.setAttribute("aria-pressed", String(gewaehlt === wert));
        taste.addEventListener("click", () => {
          if (gewaehlt !== wert) this._automatikEinstellen(kreis, { ausrichtung: wert });
        });
        ausrichtung.appendChild(taste);
      });
      zeile.append(schalter, segment, ausrichtung);
      return zeile;
    }

    /** Unter dem Titel: Heizfläche, Eingriffe als Punkte, nächste Prüfung, Modus seit. */
    _automatikMeta(kreis) {
      const k = kreis.kennwerte || {};
      const meta = document.createElement("div");
      meta.className = "automatik-meta";
      const teil = (text) => {
        const span = document.createElement("span");
        span.textContent = text;
        meta.appendChild(span);
        return span;
      };
      const flaeche = HEIZFLAECHEN.find(([name]) => name === kreis.konfig.heizflaechen);
      const profil = PROFILE.find(([name]) => name === kreis.konfig.profil);
      teil(this._t(flaeche ? flaeche[1] : profil ? profil[1] : kreis.konfig.profil || ""));
      const eingriffe = teil("");
      const budget = document.createElement("span");
      budget.className = "automatik-budget klein";
      for (let i = 0; i < (k.budget || 0); i += 1) {
        const strich = document.createElement("i");
        if (i < (k.eingriffe || 0)) strich.className = "voll";
        budget.appendChild(strich);
      }
      const zaehler = document.createElement("span");
      zaehler.textContent = this._tMit(" {zahl} von {budget} Eingriffen heute", { zahl: k.eingriffe ?? 0, budget: k.budget ?? "–" });
      eingriffe.append(budget, zaehler);
      const uhr = (iso) => new Date(iso).toTimeString().slice(0, 5);
      if (k.naechste_pruefung) teil(this._tMit("nächste Prüfung {zeit}", { zeit: uhr(k.naechste_pruefung) }));
      if (k.modus_seit && kreis.zustand !== "programm" && ZUSTAENDE[kreis.zustand]) {
        teil(this._tMit("{modus} seit {zeit}", { modus: this._t(ZUSTAENDE[kreis.zustand]), zeit: uhr(k.modus_seit) }));
      }
      return meta;
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
