/**
 * Reiter „Automatik“.
 *
 * Je Heizkreis vier Karten – Kopf, Kennwerte, Tagesverlauf, Einstellungen –
 * und daneben das Protokoll. Einladung, Einrichtungsdialog und Einstellungen
 * stehen in `einrichtung.js`, der Tagesverlauf in `tagesbild.js`.
 * Die Daten kommen über `heatnexus/automatik`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

// Wie auf dem Server: So lange darf ein Raumfühler denselben Wert zeigen, dann gilt er als veraltet.
export const VERALTET_STUNDEN = 12;
// Höchstens so oft wird nachgeladen, solange der Reiter offen ist.
export const AUTOMATIK_TAKT_MS = 60 * 1000;
// So viele Protokolleinträge stehen, bis „Alle anzeigen“ den Rest aufklappt.
const PROTOKOLL_KURZ = 8;

export const FELDER = [
  { name: "grenze_versatz", hilfe: "Die Automatik richtet sich nach der Heizgrenze der Steuerung (TA Heizbetrieb) und verschiebt sie um diesen Wert. Negativ schaltet früher auf nur Warmwasser. Die Ausrichtung setzt ihn; hier lässt er sich fein einstellen.", titel: "Abstand zur Heizgrenze", einheit: "K", schritt: 0.5 },
  { name: "hysterese", hilfe: "Abstand über und unter der Heizgrenze. Er verhindert, dass der Heizkreis bei Werten nahe der Grenze hin- und herschaltet.", titel: "Hysterese Saison", einheit: "K", schritt: 0.1 },
  { name: "tau_h", hilfe: "Wie träge die gedämpfte Außentemperatur dem Fühler folgt. Ein größerer Wert lässt kurze Wärme am Nachmittag weniger zählen. Richtwerte: Heizkörper 5 h, gemischt 15 h, Fußbodenheizung 25 h.", titel: "Zeitkonstante gedämpfte AT", einheit: "h", schritt: 1 },
  { name: "mindestdauer_h", hilfe: "So lange bleibt der Heizkreis mindestens im Programm oder auf nur Warmwasser, bevor die Automatik wieder umschaltet. Ein zu kalter Raum geht immer vor.", titel: "Mindestdauer Saisonwechsel", einheit: "h", schritt: 1 },
  { name: "entscheidung", hilfe: "Zu dieser Uhrzeit prüft die Automatik, ob ein Sonnentag bevorsteht, und setzt dann die Absenkung.", titel: "Entscheidung um", art: "zeit" },
  { name: "nachpruefung", hilfe: "Eine zweite Prüfung am Tag, etwa wenn der Morgen trüb war und die Sonne später kommt. Leer lassen, wenn sie nicht gewünscht ist.", titel: "Nachprüfung um", art: "zeit" },
  { name: "absenkung_k", hilfe: "Um so viel senkt die Automatik den Sollwert an einem Sonnentag. Die Absenkung endet an der Steuerung von selbst, spätestens zwei Stunden vor Sonnenuntergang.", titel: "Absenkung am Sonnentag", einheit: "K", schritt: 0.5 },
  { name: "rueckkehr_k", hilfe: "Fällt der Raum unter Soll minus diesen Wert, beendet die Automatik die Absenkung sofort.", titel: "Rückkehr bei Raum unter Soll minus", einheit: "K", schritt: 0.1 },
  { name: "sonnenquote", hilfe: "Ab diesem Anteil Sonne gilt der Tag als Sonnentag. Die Quote kommt aus der PV-Prognose oder aus der Bewölkung der Wetterprognose.", titel: "Sonnenquote ab", einheit: "%", schritt: 5 },
  { name: "sonnentag", hilfe: "An sonnigen Tagen senkt die Automatik den Sollwert des Heizkreises ab. Mit Thermostaten in den Räumen ist der Sonnentag ab Werk aus: Die Thermostate öffnen bei abgesenktem Sollwert nur weiter.", titel: "Sonnentag absenken", art: "janein" },
  { name: "stark", hilfe: "An sehr sonnigen Tagen ab 80 % Sonnenquote, wenn die Räume schon über ihrem Ziel liegen, schaltet die Automatik den Heizkreis bis Sonnenuntergang auf nur Warmwasser, statt nur den Sollwert abzusenken.", titel: "Sehr sonnig: nur Warmwasser", art: "janein" },
  { name: "stark_k", hilfe: "So weit müssen die Räume über ihrem Ziel liegen, damit ein sehr sonniger Tag auf nur Warmwasser schaltet.", titel: "Sehr sonnig ab Räumen über Ziel", einheit: "K", schritt: 0.1 },
  { name: "ruhe_h", hilfe: "So lange darf kein Thermostat Wärme angefordert haben, bevor die Automatik auf nur Warmwasser schaltet.", titel: "Räume ruhig seit", einheit: "h", schritt: 0.5 },
  { name: "budget", hilfe: "So viele Eingriffe darf die Automatik am Tag an die Steuerung schreiben. Die Rückkehr ins Programm zählt nicht mit und ist immer erlaubt.", titel: "Eingriffe je Tag höchstens", einheit: "", schritt: 1 },
  { name: "fenster_k_je_h", hilfe: "Fällt der Raum schneller als dieser Wert pro Stunde, gilt ein Fenster als offen. Die Automatik setzt ihre Entscheidungen dann 30 Minuten aus.", titel: "Fenster offen ab Sturz von", einheit: "K/h", schritt: 0.5 },
  {
    name: "anpassen",
    hilfe: "Die Automatik vergleicht jeden Tag Prognose und Messung und verschiebt die Prognose um die gelernte Abweichung. Ist der Schalter aus, gelten die rohen Prognosen für Anzeige und Entscheidung; gelernt wird trotzdem weiter.",
    titel: "Prognose an Standort anpassen",
    art: "janein",
  },
  { name: "lernfenster", hilfe: "Über so viele Tage vergleicht die Automatik Prognose und Messung und passt die Prognose daran an. Ein kurzes Fenster reagiert schneller, ein langes schwankt weniger.", titel: "Prognose lernen über", art: "wahl", optionen: [3, 7, 14], einheit: "Tage" },
];

export const ZUSTAENDE = {
  programm: "Heizen nach Programm",
  sonnentag: "Sonnentag",
  nur_ww: "Nur Warmwasser",
  heizpause: "Heizpause",
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
  empfohlen: "empfohlen",
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
  ["ausgewogen", "Ausgewogen – zwischen Eco und Komfort"],
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

/** Ob ein Wert vorliegt; null und undefined zählen nicht. */
export function vorhanden(wert) {
  return wert !== null && wert !== undefined;
}

/** Uhrzeit „HH:MM“ aus einem ISO-Zeitpunkt, in der Zeitzone des Browsers. */
export function uhrAus(iso) {
  return new Date(iso).toTimeString().slice(0, 5);
}

/** Datum „T.M.“ aus einem Zeitpunkt. */
export function tagMonat(datum) {
  const d = new Date(datum);
  return `${d.getDate()}.${d.getMonth() + 1}.`;
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
          { id: `automatik:${kreis.heizkreis}`, titel, knoten: this._automatikBereich(kreis, daten), breite: 2 },
          { id: `automatik-protokoll:${kreis.heizkreis}`, titel: "Protokoll", knoten: this._automatikProtokoll(kreis) },
        ];
      });
    }

    /** Alle Anlagen in einem Raster: Die Automatik arbeitet je Heizkreis, nicht je Anlage. */
    _automatikAlle() {
      this._hilfe = (this._anlagen()[0] || {}).hilfe || {};
      return this._raster({ id: "alle" }, this._automatikReiter(null), "Keine Heizkreise gefunden.");
    }

    /**
     * Stand vom Server holen. Ein erzwungener Abruf wartet einen laufenden ab, dessen Stand
     * älter sein kann als die gerade geschriebene Änderung; `gespeichert` meldet sie danach.
     */
    async _automatikHolen(erzwingen = false, gespeichert = null) {
      if (this._automatikLaeuft) {
        if (!erzwingen) return;
        await this._automatikLaeuft;
      }
      if (!erzwingen && this._automatikZeit && Date.now() - this._automatikZeit < AUTOMATIK_TAKT_MS) return;
      if (gespeichert) this._automatikGespeichert = gespeichert;
      this._automatikLaeuft = this._automatikLaden();
      try {
        await this._automatikLaeuft;
      } finally {
        this._automatikLaeuft = null;
      }
    }

    async _automatikLaden() {
      try {
        this._automatik = await this._hass.callWS({ type: "heatnexus/automatik" });
        this._automatikZeit = Date.now();
        // Der Neuaufbau ersetzt den ganzen Baum; ein offener Dialog ginge mit.
        const dialogOffen = Boolean(this.shadowRoot.querySelector(".schleier"));
        if (this._reiter === "automatik" && !this._automatikBearbeitet && !dialogOffen) this._automatikNeuZeichnen();
        else this._automatikGespeichert = null;
      } catch (err) {
        this._automatikZeit = Date.now();
        console.warn("HeatNexus: Automatik konnte nicht geladen werden", err);
      }
    }

    /** Neu aufbauen; der Neuaufbau leert die Seite kurz, ohne Merken spränge sie nach oben. */
    _automatikNeuZeichnen() {
      const lagen = this._automatikScrollLagen();
      this._gebaut = false;
      this._zeichnen();
      lagen.forEach(([element, oben]) => {
        element.scrollTop = oben;
      });
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

    async _automatikAufruf(nachricht, gespeichert = null) {
      try {
        await this._hass.callWS(nachricht);
        this._automatikBearbeitet = this._automatikHatEntwurf();
        await this._automatikHolen(true, gespeichert);
        return true;
      } catch (err) {
        this._melden((err && err.message) || this._t("Die Automatik hat die Änderung nicht übernommen."));
        return false;
      }
    }

    _automatikEinstellen(kreis, aenderung, gespeichert = null) {
      return this._automatikAufruf(
        { type: "heatnexus/automatik/einstellen", heizkreis: kreis.heizkreis, ...aenderung },
        gespeichert
      );
    }

    /** Ein Schalter mit Text; `klein` für die Leiste im Tagesverlauf. */
    _automatikSchalter(text, an, darf, klick, klein = false) {
      const schalter = document.createElement("button");
      schalter.type = "button";
      schalter.className = `automatik-schalter${klein ? " klein" : ""}${an ? " an" : ""}`;
      schalter.setAttribute("role", "switch");
      schalter.setAttribute("aria-checked", String(!!an));
      schalter.disabled = !darf;
      const knopf = document.createElement("i");
      const beschriftung = document.createElement("span");
      beschriftung.textContent = this._t(text);
      schalter.append(knopf, beschriftung);
      schalter.addEventListener("click", klick);
      return schalter;
    }

    // --- Karte ---------------------------------------------------------
    /** Kopfkarte, drei Kennwerte, Tagesverlauf und Einstellungen untereinander. */
    _automatikBereich(kreis, daten) {
      const bereich = document.createElement("div");
      bereich.className = "automatik-bereich";
      const darf = !!daten.darf_aendern;
      bereich.append(
        this._automatikKarte(kreis, daten),
        this._automatikKennwerte(kreis),
        this._automatikTag(kreis),
        this._automatikErweitert(kreis, daten, darf)
      );
      return bereich;
    }

    _automatikKarte(kreis, daten) {
      const karte = this._karte(kreis.name, this._hilfe && this._hilfe.Automatik);
      karte.classList.add("automatik");
      const darf = !!daten.darf_aendern;
      const kopf = karte.querySelector(".kartenkopf");
      const marke = document.createElement("span");
      marke.className = `automatik-marke z-${kreis.zustand}`;
      marke.textContent = this._t(ZUSTAENDE[kreis.zustand] || kreis.zustand);
      if (kreis.konfig.modus === "beobachten" && kreis.konfig.aktiv) {
        marke.textContent += ` · ${this._t("beobachtet")}`;
      }
      const bearbeiten = document.createElement("button");
      bearbeiten.type = "button";
      bearbeiten.className = "automatik-knopf leise klein";
      bearbeiten.textContent = this._t("Einrichtung bearbeiten");
      bearbeiten.disabled = !darf;
      bearbeiten.addEventListener("click", () => this._automatikDialog(kreis));
      this._klickbar(marke, (kreis.entitaeten || {}).zustand);
      if (kopf) {
        const titel = kopf.querySelector("h2");
        kopf.insertBefore(bearbeiten, kopf.querySelector(".fragezeichen"));
        kopf.insertBefore(marke, titel ? titel.nextSibling : kopf.firstChild);
        kopf.parentElement.insertBefore(this._automatikMeta(kreis), kopf.nextSibling);
      }

      const warum = document.createElement("div");
      warum.className = "automatik-warum";
      warum.textContent = kreis.begruendung || "";
      karte.appendChild(warum);
      karte.appendChild(this._automatikSteuerzeile(kreis, darf));
      const hinweis = this._automatikHinweis(kreis, darf);
      if (hinweis) karte.appendChild(hinweis);
      return karte;
    }

    /** Ein Segment aus Tasten; die gewählte ist hervorgehoben. */
    _automatikSegment(titel, klasse, eintraege, gewaehlt, darf, waehlen) {
      const gruppe = document.createElement("div");
      gruppe.className = "automatik-gruppe";
      const beschriftung = document.createElement("span");
      beschriftung.className = "automatik-gruppentitel";
      beschriftung.textContent = this._t(titel);
      const segment = document.createElement("div");
      segment.className = `automatik-segment${klasse ? ` ${klasse}` : ""}`;
      eintraege.forEach(([wert, text, tipp]) => {
        const taste = document.createElement("button");
        taste.type = "button";
        taste.textContent = this._t(text);
        if (tipp) taste.title = this._t(tipp);
        taste.disabled = !darf;
        taste.setAttribute("aria-pressed", String(gewaehlt === wert));
        taste.addEventListener("click", () => {
          if (gewaehlt !== wert) waehlen(wert);
        });
        segment.appendChild(taste);
      });
      // Am Handy erscheint kein `title`; das „?“ zeigt dieselben Tipps.
      const tipps = eintraege.filter(([, , tipp]) => tipp).map(([, , tipp]) => this._t(tipp));
      if (tipps.length) beschriftung.appendChild(this._fragezeichen(titel, tipps.join(". ") + "."));
      gruppe.append(beschriftung, segment);
      return gruppe;
    }

    _automatikSteuerzeile(kreis, darf) {
      const zeile = document.createElement("div");
      zeile.className = "automatik-zeile";
      const schalter = this._automatikSchalter("Automatik aktiv", kreis.konfig.aktiv, darf, () =>
        this._automatikEinstellen(kreis, { aktiv: !kreis.konfig.aktiv })
      );

      const modus = this._automatikSegment(
        "Modus",
        "",
        [
          ["beobachten", "Beobachten"],
          ["empfehlen", "Manuell mit Empfehlung"],
          ["schalten", "Automatisch"],
        ],
        kreis.konfig.modus,
        darf,
        (wert) => this._automatikEinstellen(kreis, { modus: wert })
      );
      // Die Ausrichtung ist die Einstellung, die man im Alltag wechselt; sie steht deshalb hier.
      const stil = this._automatikSegment(
        "Stil",
        "ausrichtung",
        [
          ["eco", "Eco", AUSRICHTUNGEN[0][1]],
          ["ausgewogen", "Ausgewogen", AUSRICHTUNGEN[1][1]],
          ["komfort", "Komfort", AUSRICHTUNGEN[2][1]],
        ],
        kreis.konfig.ausrichtung || "ausgewogen",
        darf,
        (wert) => this._automatikEinstellen(kreis, { ausrichtung: wert })
      );
      zeile.append(schalter, modus, stil);
      return zeile;
    }

    /** Unter dem Titel: Heizfläche, Eingriffe, nächste Prüfung, Modus seit. */
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
      const entitaeten = kreis.entitaeten || {};
      this._klickbar(teil(this._tMit("{zahl} von {budget} Eingriffen heute", { zahl: k.eingriffe ?? 0, budget: k.budget ?? "–" })), entitaeten.eingriffe);
      if (k.naechste_pruefung) {
        this._klickbar(teil(this._tMit("Nächste Prüfung {zeit}", { zeit: uhrAus(k.naechste_pruefung) })), entitaeten.naechste_entscheidung);
      }
      if (k.modus_seit && kreis.zustand !== "programm" && ZUSTAENDE[kreis.zustand]) {
        teil(this._tMit("{modus} seit {zeit}", { modus: this._t(ZUSTAENDE[kreis.zustand]), zeit: uhrAus(k.modus_seit) }));
      }
      return meta;
    }

    /** Eine offene Empfehlung: Begründung und Knopf zum Übernehmen. */
    _automatikEmpfehlung(kreis, darf) {
      const empfehlung = kreis.empfehlung;
      if (!empfehlung || !kreis.konfig.aktiv || kreis.konfig.modus !== "empfehlen") return null;
      const hinweis = document.createElement("div");
      hinweis.className = "automatik-hinweis";
      const text = document.createElement("div");
      text.className = "text";
      text.textContent = empfehlung.begruendung || "";
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "automatik-knopf";
      taste.disabled = !darf;
      taste.textContent = this._t("Übernehmen");
      taste.addEventListener("click", () =>
        this._automatikAufruf({ type: "heatnexus/automatik/empfehlung_uebernehmen", heizkreis: kreis.heizkreis })
      );
      hinweis.append(text, taste);
      return hinweis;
    }

    _automatikHinweis(kreis, darf) {
      const empfohlen = this._automatikEmpfehlung(kreis, darf);
      if (empfohlen) return empfohlen;
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
        const datum = tagMonat(kreis.beobachtet_seit);
        text.textContent = this._tMit("Beobachtungsmodus seit dem {datum} – vorgemerkte Eingriffe: {anzahl}. Nichts davon ging an die Steuerung.", { datum, anzahl: haette });
        taste.className = tage >= 7 ? "automatik-knopf" : "automatik-knopf leise";
        taste.textContent = this._t("Jetzt scharf schalten");
        taste.addEventListener("click", () => this._automatikEinstellen(kreis, { modus: "schalten" }));
      }
      hinweis.append(text, taste);
      return hinweis;
    }

    // --- Protokoll -----------------------------------------------------
    /** Einträge nach Tagen: Heute, Gestern, dann das Datum; lange Listen zeigen erst die jüngsten. */
    _automatikProtokoll(kreis) {
      const karte = this._karte("Protokoll");
      karte.classList.add("automatik-protokollkarte");
      const eintraege = kreis.protokoll || [];
      this._automatikProtokollAlle = this._automatikProtokollAlle || new Set();
      const alle = this._automatikProtokollAlle.has(kreis.heizkreis);
      const kopf = karte.querySelector(".kartenkopf");
      if (kopf && eintraege.length > PROTOKOLL_KURZ) {
        const umschalten = document.createElement("button");
        umschalten.type = "button";
        umschalten.className = "automatik-verweis";
        umschalten.textContent = this._t(alle ? "Weniger anzeigen" : "Alle anzeigen");
        umschalten.setAttribute("aria-expanded", String(alle));
        umschalten.addEventListener("click", () => {
          if (alle) this._automatikProtokollAlle.delete(kreis.heizkreis);
          else this._automatikProtokollAlle.add(kreis.heizkreis);
          this._automatikNeuZeichnen();
        });
        kopf.appendChild(umschalten);
      }
      if (!eintraege.length) karte.appendChild(this._hinweisKnoten("Noch keine Entscheidung."));
      const heute = new Date();
      const gestern = new Date(heute.getTime() - 86400000);
      let liste = null;
      let letzterTag = null;
      (alle ? eintraege : eintraege.slice(0, PROTOKOLL_KURZ)).forEach((eintrag) => {
        const datum = new Date(eintrag.zeit);
        const tag = datum.toDateString();
        if (tag !== letzterTag) {
          letzterTag = tag;
          const ueberschrift = document.createElement("h4");
          ueberschrift.className = "automatik-protokolltag";
          if (tag === heute.toDateString()) ueberschrift.textContent = this._t("Heute");
          else if (tag === gestern.toDateString()) ueberschrift.textContent = this._t("Gestern");
          else ueberschrift.textContent = tagMonat(datum);
          liste = document.createElement("ul");
          liste.className = "automatik-protokoll";
          karte.append(ueberschrift, liste);
        }
        const zeile = document.createElement("li");
        const zeit = document.createElement("span");
        zeit.className = "zeit";
        zeit.textContent = uhrAus(datum);
        const inhalt = document.createElement("div");
        inhalt.className = "inhalt";
        const text = document.createElement("div");
        text.textContent = eintrag.text;
        const art = document.createElement("span");
        art.className = `art ${eintrag.art}`;
        art.textContent = this._t(PROTOKOLL_ARTEN[eintrag.art] || eintrag.art);
        inhalt.append(text, art);
        zeile.append(zeit, inhalt);
        liste.appendChild(zeile);
      });
      return karte;
    }
  };
