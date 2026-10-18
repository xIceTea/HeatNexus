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

import { BETRIEBSARTEN } from "../ordnung.js";
import { kalendertagIn, tagMonatIn, uhrzeitText, zeitzone } from "./zeit.js";

// Wie auf dem Server: So lange darf ein Raumfühler denselben Wert zeigen, dann gilt er als veraltet.
export const VERALTET_STUNDEN = 12;
// Höchstens so oft wird nachgeladen, solange der Reiter offen ist.
export const AUTOMATIK_TAKT_MS = 60 * 1000;
// So viele Protokolleinträge stehen, bis „Alle anzeigen“ den Rest aufklappt.
const PROTOKOLL_KURZ = 8;
// Nach diesen Zuständen kehrt die Steuerung von selbst zum Programm zurück, wenn ihre Dauer abläuft.
const MIT_ABLAUF = new Set(["sonnentag", "heizpause"]);

export const FELDER = [
  { name: "grenze_versatz", hilfe: "Die Automatik richtet sich nach der Heizgrenze der Steuerung (TA Heizbetrieb) und verschiebt sie um diesen Wert. Negativ schaltet früher auf nur Warmwasser. Die Ausrichtung setzt ihn; hier lässt er sich fein einstellen.", titel: "Abstand zur Heizgrenze", einheit: "K", schritt: 0.5 },
  { name: "hysterese", hilfe: "Abstand über und unter der Heizgrenze. Er verhindert, dass der Heizkreis bei Werten nahe der Grenze hin- und herschaltet.", titel: "Hysterese Saison", einheit: "K", schritt: 0.1 },
  { name: "tau_h", hilfe: "Wie träge die gedämpfte Außentemperatur dem Fühler folgt. Ein größerer Wert lässt kurze Wärme am Nachmittag weniger zählen. Richtwerte: Heizkörper 5 h, gemischt 15 h, Fußbodenheizung 25 h.", titel: "Zeitkonstante gedämpfte AT", einheit: "h", schritt: 1 },
  { name: "mindestdauer_h", hilfe: "So lange bleibt der Heizkreis mindestens im Programm oder auf nur Warmwasser, bevor die Automatik wieder umschaltet. Ein zu kalter Raum geht immer vor.", titel: "Mindestdauer Saisonwechsel", einheit: "h", schritt: 1 },
  { name: "beginn_art", art: "auswahl", optionen: [["aufgang", "Sonnenaufgang"], ["uhrzeit", "Feste Uhrzeit"], ["aus", "Ohne Sperre"]], titel: "Frühester Beginn", hilfe: "Ab hier darf die Sonne einen Eingriff auslösen. Andere Anlässe, etwa eine milde Außentemperatur, gelten zu jeder Zeit." },
  { name: "beginn_uhrzeit", art: "zeit", titel: "Feste Uhrzeit", hilfe: "Gilt, wenn als frühester Beginn eine feste Uhrzeit gewählt ist." },
  { name: "beginn_laeufe", titel: "Beginn nach gleichen Prüfungen", einheit: "", schritt: 1, hilfe: "So viele Prüfungen in Folge, alle fünf Minuten eine, muss ein Eingriff gleich bleiben, bevor er beginnt." },
  { name: "ende_laeufe", titel: "Ende nach gleichen Prüfungen", einheit: "", schritt: 1, hilfe: "So viele Prüfungen in Folge muss das Ende eines Eingriffs gleich bleiben. Kalte Räume und Sicherheit beenden ihn sofort." },
  { name: "halten_min", titel: "Nach einem Wechsel halten", einheit: "min", schritt: 15, hilfe: "So lange bleibt ein neuer Zustand mindestens bestehen. Kalte Räume und Sicherheit gehen vor." },
  { name: "absenkung_k", hilfe: "Um so viel senkt die Automatik den Sollwert an einem Sonnentag. Die Absenkung endet an der Steuerung von selbst, spätestens zwei Stunden vor Sonnenuntergang.", titel: "Absenkung am Sonnentag", einheit: "K", schritt: 0.5 },
  { name: "rueckkehr_k", hilfe: "Fällt der Raum unter Soll minus diesen Wert, beendet die Automatik die Absenkung sofort.", titel: "Rückkehr bei Raum unter Soll minus", einheit: "K", schritt: 0.1 },
  { name: "sonne_frost_at", hilfe: "Unter dieser gedämpften Außentemperatur senkt die Automatik an einem Sonnentag nur ab, wenn das Hausmodell freigegeben ist. Bei Frost deckt die Sonne den Wärmeverlust selten.", titel: "Sonnentag ohne Hausmodell ab", einheit: "°C", schritt: 1 },
  { name: "sonne_voll_at", hilfe: "Ab dieser gedämpften Außentemperatur senkt die Automatik an einem Sonnentag um den vollen Wert ab. Darunter wird die Absenkung mit sinkender Temperatur kleiner, bis auf 0,5 K an der Frostgrenze. Bei Kälte deckt die Sonne weniger vom Wärmeverlust.", titel: "Volle Absenkung am Sonnentag ab", einheit: "°C", schritt: 1 },
  { name: "raum_fehlt_min", hilfe: "Liefert weniger als die Hälfte der Räume einen Wert, trifft die Automatik keine neue Entscheidung. Nach dieser Zeit beendet sie auch eine laufende Absenkung. 0 beendet sie sofort.", titel: "Ohne Raumwerte Absenkung beenden nach", einheit: "min", schritt: 5 },
  { name: "spielraum_k", hilfe: "So weit darf die Vorhersage die Räume bis zum Horizont unter das Ziel sinken lassen. Eco erlaubt mehr, Komfort nichts.", titel: "Spielraum unter Ziel", einheit: "K", schritt: 0.1 },
  { name: "sonnenquote", hilfe: "Ab diesem Anteil Sonne gilt der Tag als Sonnentag. Die Quote kommt aus der PV-Prognose oder aus der Bewölkung der Wetterprognose.", titel: "Sonnenquote ab", einheit: "%", schritt: 5 },
  { name: "sonnentag", hilfe: "An sonnigen Tagen senkt die Automatik den Sollwert des Heizkreises ab. Mit Thermostaten in den Räumen ist der Sonnentag ab Werk aus: Die Thermostate öffnen bei abgesenktem Sollwert nur weiter.", titel: "Sonnentag absenken", art: "janein" },
  { name: "stark", hilfe: "An sehr sonnigen Tagen ab 80 % Sonnenquote, wenn die Räume schon über ihrem Ziel liegen, schaltet die Automatik den Heizkreis bis Sonnenuntergang auf nur Warmwasser, statt nur den Sollwert abzusenken.", titel: "Sehr sonnig: nur Warmwasser", art: "janein" },
  { name: "stark_k", hilfe: "So weit müssen die Räume über ihrem Ziel liegen, damit ein sehr sonniger Tag auf nur Warmwasser schaltet.", titel: "Sehr sonnig: Räume über Ziel ab", einheit: "K", schritt: 0.1 },
  { name: "ruhe_h", hilfe: "So lange darf kein Thermostat Wärme angefordert haben, bevor die Automatik auf nur Warmwasser schaltet.", titel: "Räume ruhig seit", einheit: "h", schritt: 0.5 },
  { name: "budget", hilfe: "So viele Eingriffe darf die Automatik am Tag an die Steuerung schreiben. Die Rückkehr ins Programm zählt nicht mit und ist immer erlaubt.", titel: "Eingriffe je Tag höchstens", einheit: "", schritt: 1 },
  { name: "fenster_k_je_h", hilfe: "Fällt der Raum schneller als dieser Wert pro Stunde, gilt ein Fenster als offen. Die Automatik setzt ihre Entscheidungen dann 30 Minuten aus.", titel: "Fenster offen ab Sturz von", einheit: "K/h", schritt: 0.5 },
  {
    name: "anpassen",
    hilfe: "Die Automatik vergleicht jeden Tag Prognose und Messung und verschiebt die Prognose um die gelernte Abweichung. Ist der Schalter aus, gelten die rohen Prognosen für Anzeige und Entscheidung; gelernt wird trotzdem weiter.",
    titel: "Prognose an Standort anpassen",
    art: "janein",
  },
  { name: "melden", hilfe: "Im Modus „Manuell mit Empfehlung“ erscheint jede Empfehlung als Benachrichtigung in der Seitenleiste von Home Assistant. Sie verschwindet, sobald die Empfehlung übernommen, verworfen oder abgelaufen ist.", titel: "Empfehlung in der Seitenleiste melden", unter: "Gilt im Modus „Manuell mit Empfehlung“", art: "janein" },
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
  verworfen: "verworfen",
  abgelehnt: "abgelehnt",
  budget: "Budget erreicht",
  geprueft: "geprüft",
  eingriff: "Handeingriff",
  einstellung: "Einstellung",
};

// Was die Regel prüft; die Namen kommen vom Server, die Beschriftung von hier.
export const BEWERTUNGEN = {
  daten: "Daten",
  prognose: "Prognose",
  fenster: "Fenster",
  beginn: "Ab",
  sonne: "Sonne",
  vorrang: "Vorrang",
  raeume: "Räume",
  thermostate: "Thermostate",
  at_gedaempft: "Gedämpfte AT",
  tagesmittel: "Tagesmittel",
  at_prognose: "AT-Prognose",
  programmwahl: "Betriebswahl",
  betriebsart: "Betriebsart",
  abwesend: "Abwesend",
  hausmodell: "Hausmodell",
  sperre: "Sperre",
};

export const ERGEBNISSE = {
  schreibt: "schreibt",
  haette: "hätte geschrieben",
  empfohlen: "empfohlen",
  abgelehnt: "abgelehnt",
  zaehlt: "zählt",
  haelt: "hält",
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

/** Temperatur mit Komma und Einheit; ohne Wert ein Strich. */
function grad(wert) {
  return wert === null || wert === undefined ? "–" : `${zahl(wert)} °C`;
}

// Betriebsarten des Heizkreises (`2/9`), die einen Eingriff aufhalten; deckt sich mit `regel.SONDERBETRIEB`.
const HEIZKREIS_BETRIEB = {
  2: "Heizkreis im Absenkbetrieb",
  5: "Heizkreis im Urlaubsprogramm",
  6: "Heizkreis im Estrichprogramm",
  9: "Heizkreis im Handbetrieb",
  10: "Heizkreis im Testbetrieb",
  11: "Heizkreis im Kaminkehrerbetrieb",
};

/** Platzhalter `{name}` füllen, ohne zu übersetzen. */
function fuellen(text, werte = {}) {
  return Object.entries(werte).reduce((satz, [k, v]) => satz.split(`{${k}}`).join(String(v)), text);
}

/** Eine Bewertung als Aussage, etwa „Sonnenfenster bis 16:16“; `t` übersetzt Vorlage und Werte. */
export function markeAussage(b, t = fuellen) {
  const ja = b.erfuellt;
  switch (b.name) {
    case "daten":
      return ja ? t("Daten vollständig") : t("Daten fehlen");
    case "prognose":
      return ja ? t("Prognose liegt vor") : t("Prognose fehlt");
    case "fenster":
      return ja ? t("Fenster zu") : t("Fenster offen");
    case "beginn":
      return beginnAussage(b, t);
    case "sonne":
      if (b.wert === null || b.wert === undefined) return t("Sonnenquote fehlt");
      return t("Sonne {wert} % (ab {schwelle} %)", { wert: zahl(b.wert, 0), schwelle: zahl(b.schwelle, 0) });
    case "vorrang":
      return vorrangAussage(b, t);
    case "raeume":
      return raeumeAussage(b, t);
    case "thermostate":
      return ja ? t("Thermostate ruhig") : t("Thermostate fordern Wärme");
    case "at_gedaempft":
      return t("Gedämpfte AT {wert} (Grenze {schwelle})", { wert: grad(b.wert), schwelle: grad(b.schwelle) });
    case "tagesmittel":
      return t("Tagesmittel {wert} (Grenze {schwelle})", { wert: grad(b.wert), schwelle: grad(b.schwelle) });
    case "at_prognose":
      return t("AT-Prognose {wert} (Grenze {schwelle})", { wert: grad(b.wert), schwelle: grad(b.schwelle) });
    case "programmwahl":
      if (BETRIEBSARTEN[b.wert]) return t("Betriebswahl {wahl}", { wahl: t(BETRIEBSARTEN[b.wert]) });
      return ja ? t("Betriebswahl im Programm") : t("Betriebswahl außerhalb des Programms");
    case "betriebsart":
      if (ja) return t("Heizkreis im Normalbetrieb");
      return t(HEIZKREIS_BETRIEB[b.wert] || "Heizkreis im Sonderbetrieb");
    case "abwesend":
      return ja ? t("Abwesend") : t("Anwesend");
    case "hausmodell":
      return ja ? t("Hausmodell freigegeben") : t("Hausmodell nicht freigegeben");
    case "sperre":
      return ja ? t("Heizpause frei") : t("Heizpause heute gesperrt");
    default:
      return t(BEWERTUNGEN[b.name] || b.name);
  }
}

/** Im Fenster sein Ende, davor sein Beginn, danach „vorbei“; `wert` ist die Uhrzeit des Laufs. */
function beginnAussage(b, t) {
  if (!b.schwelle) return b.erfuellt ? t("Im Sonnenfenster") : t("Außerhalb des Sonnenfensters");
  if (b.erfuellt) return t("Sonnenfenster bis {zeit}", { zeit: b.schwelle });
  if (b.wert && String(b.wert) < String(b.schwelle)) return t("Sonnenfenster ab {zeit}", { zeit: b.schwelle });
  return t("Sonnenfenster vorbei ({zeit})", { zeit: b.schwelle });
}

/** Die Vorrangquelle mit Namen; ohne Namen das Wort „Vorrangquelle“. */
function vorrangAussage(b, t) {
  const quelle = b.quelle || t("Vorrangquelle");
  if (!b.erfuellt) return t("{quelle} liefert nicht", { quelle });
  if (b.wert === null || b.wert === undefined) return t("{quelle} liefert", { quelle });
  return t("{quelle} liefert seit {minuten} min", { quelle, minuten: zahl(b.wert, 0) });
}

/** Abstand der Räume zum Ziel in Worten. */
function raeumeAussage(b, t) {
  if (b.wert === null || b.wert === undefined) return t("Räume ohne Wert");
  const v = Math.round(Number(b.wert) * 10) / 10;
  if (v === 0) return t("Räume am Ziel");
  const abstand = `${zahl(Math.abs(v))} K`;
  return v > 0 ? t("Räume {abstand} über Ziel", { abstand }) : t("Räume {abstand} unter Ziel", { abstand });
}

/**
 * Protokoll und Regellauf in einer Folge, neueste zuerst: Läufe zwischen zwei Einträgen bilden eine Gruppe.
 * `schluessel` ist die Zeit des älteren Eintrags darunter, beim ältesten Abschnitt "anfang".
 */
export function protokollMitLaeufen(protokoll = [], laeufe = []) {
  const folge = [];
  let gruppe = [];
  let j = 0;
  const abschliessen = (schluessel) => {
    if (gruppe.length) folge.push({ art: "laeufe", laeufe: gruppe, schluessel });
    gruppe = [];
  };
  for (const eintrag of protokoll) {
    const grenze = Date.parse(eintrag.zeit);
    while (j < laeufe.length && Date.parse(laeufe[j].zeit) > grenze) gruppe.push(laeufe[j++]);
    abschliessen(eintrag.zeit);
    folge.push({ art: "eintrag", eintrag });
  }
  gruppe.push(...laeufe.slice(j));
  abschliessen("anfang");
  return folge;
}

/** Ein Schalter ohne Text: Spur mit Knopf, eingeschaltet mit Haken. */
export function schalterKnopf(an, darf, klein = false) {
  const schalter = document.createElement("button");
  schalter.type = "button";
  schalter.className = `automatik-schalter${klein ? " klein" : ""}${an ? " an" : ""}`;
  schalter.setAttribute("role", "switch");
  schalter.setAttribute("aria-checked", String(!!an));
  schalter.disabled = !darf;
  schalter.appendChild(document.createElement("i"));
  return schalter;
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

/** Uhrzeit aus einem ISO-Zeitpunkt, in Zone und Zeitformat aus Home Assistant. */
export function uhrAus(iso, hass) {
  return uhrzeitText(iso, hass);
}

/** Datum „T.M.“ aus einem Zeitpunkt; ohne Zone in der des Browsers. */
export function tagMonat(datum, zone) {
  return tagMonatIn(datum, zone);
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
          { id: `automatik:${kreis.heizkreis}`, titel, knoten: this._automatikBereich(kreis, daten), breite: 3 },
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
      this._automatikUhr = this._takt(() => {
        if (!this.isConnected || this._reiter !== "automatik") {
          this._zeitgeberLoesen(this._automatikUhr);
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

    /** Ein Schalter, Text vorn und Schalter dahinter; `klein` für die Leiste im Tagesverlauf. */
    _automatikSchalter(text, an, darf, klick, klein = false) {
      const schalter = schalterKnopf(an, darf, klein);
      const beschriftung = document.createElement("span");
      beschriftung.textContent = this._t(text);
      schalter.prepend(beschriftung);
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
      const kern = this._automatikKern((kreis.kern || {}).bewertungen, (kreis.kern || {}).anstehend);
      if (kern) karte.appendChild(kern);
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
      // „Aus" ist dieselbe Auswahl wie die Modi, wie bei der Entität „Automatik-Modus".
      const modus = this._automatikSegment(
        "Modus",
        "",
        [
          ["aus", "Aus"],
          ["beobachten", "Beobachten"],
          ["empfehlen", "Manuell mit Empfehlung"],
          ["schalten", "Automatisch"],
        ],
        kreis.konfig.aktiv ? kreis.konfig.modus : "aus",
        darf,
        (wert) =>
          this._automatikEinstellen(kreis, wert === "aus" ? { aktiv: false } : { aktiv: true, modus: wert })
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
      zeile.append(modus, stil);
      return zeile;
    }

    /** Unter dem Titel: Heizfläche, Eingriffe, frühester Beginn, Modus seit. */
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
      if (k.fruehester_beginn) {
        this._klickbar(teil(this._tMit("Frühester Beginn {zeit}", { zeit: uhrAus(k.fruehester_beginn, this._hass) })), entitaeten.naechste_entscheidung);
      }
      if (k.modus_seit && kreis.zustand !== "programm" && ZUSTAENDE[kreis.zustand]) {
        teil(this._tMit("{modus} seit {zeit}", { modus: this._t(ZUSTAENDE[kreis.zustand]), zeit: uhrAus(k.modus_seit, this._hass) }));
      }
      return meta;
    }

    /** Eine offene Empfehlung: Begründung, Knöpfe zum Übernehmen und Verwerfen. */
    _automatikEmpfehlung(kreis, darf) {
      const empfehlung = kreis.empfehlung;
      if (!empfehlung || !kreis.konfig.aktiv || kreis.konfig.modus !== "empfehlen") return null;
      const hinweis = document.createElement("div");
      hinweis.className = "automatik-hinweis empfehlung";
      hinweis.setAttribute("role", "status");
      const text = document.createElement("div");
      text.className = "text";
      // Die Überschrift zeigt, dass dieser Kasten auf eine Antwort wartet; wie der Punkt am Reiter.
      const titel = document.createElement("div");
      titel.className = "empfehlung-titel";
      const wort = document.createElement("span");
      wort.textContent = this._t("Empfehlung");
      titel.append(this._symbolKnoten("mdi:lightbulb-on-outline"), wort);
      const grund = document.createElement("div");
      grund.className = "empfehlung-grund";
      grund.textContent = empfehlung.begruendung || "";
      text.append(titel, grund);
      const kern = this._automatikKern((kreis.kern || {}).bewertungen);
      if (kern) text.appendChild(kern);
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "automatik-knopf";
      taste.disabled = !darf;
      taste.textContent = this._t("Übernehmen");
      taste.addEventListener("click", () =>
        this._automatikAufruf({ type: "heatnexus/automatik/empfehlung_uebernehmen", heizkreis: kreis.heizkreis })
      );
      const verwerfen = document.createElement("button");
      verwerfen.type = "button";
      verwerfen.className = "automatik-knopf leise";
      verwerfen.disabled = !darf;
      verwerfen.textContent = this._t("Verwerfen");
      verwerfen.addEventListener("click", () =>
        this._automatikAufruf({ type: "heatnexus/automatik/empfehlung_verwerfen", heizkreis: kreis.heizkreis })
      );
      hinweis.append(text, taste, verwerfen);
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
        const datum = tagMonat(kreis.beobachtet_seit, zeitzone(this._hass));
        text.textContent = this._tMit("Beobachtungsmodus seit dem {datum} – vorgemerkte Eingriffe: {anzahl}. Nichts davon ging an die Steuerung.", { datum, anzahl: haette });
        taste.className = tage >= 7 ? "automatik-knopf" : "automatik-knopf leise";
        taste.textContent = this._t("Jetzt scharf schalten");
        taste.addEventListener("click", () => this._automatikEinstellen(kreis, { modus: "schalten" }));
      }
      hinweis.append(text, taste);
      return hinweis;
    }

    // --- Regellauf und Kernbewertungen ---------------------------------
    /** Eine Bewertung als kleine Marke mit Aussage; unerfüllte heben sich farbig ab. */
    _bewertungMarke(b) {
      const marke = document.createElement("span");
      marke.className = `bewertung ${b.erfuellt ? "ja" : "nein"}${b.entscheidend ? " kern" : ""}`;
      marke.textContent = markeAussage(b, (text, werte = {}) => this._tMit(text, werte));
      return marke;
    }

    /** Unter der Begründung: was gerade entscheidet, davor ein anstehender Wechsel mit Zählerstand. */
    _automatikKern(bewertungen = [], a = null) {
      if (!bewertungen.length && !a) return null;
      const zeile = document.createElement("div");
      zeile.className = "automatik-kern";
      if (a) {
        const text = document.createElement("span");
        text.className = "anstehend";
        text.textContent = a.halten_bis
          ? this._tMit("Hält bis {zeit}", { zeit: uhrAus(a.halten_bis, this._hass) })
          : this._tMit("{zustand} in Sicht – {n} von {noetig}", {
              zustand: this._t(ZUSTAENDE[a.zustand] || a.zustand),
              n: a.zaehler,
              noetig: a.noetig,
            });
        zeile.appendChild(text);
      }
      bewertungen.forEach((b) => zeile.appendChild(this._bewertungMarke(b)));
      return zeile;
    }

    /** Kopfzeile und Pille eines Laufs; ein ruhiger oder geschriebener Lauf braucht keine Pille. */
    _laufKopf(e) {
      const name = (zustand) => this._t(ZUSTAENDE[zustand] || zustand);
      if (e.ergebnis === "schreibt") return { text: this._tMit("{zustand} geschrieben", { zustand: name(e.zustand) }) };
      if (e.ergebnis === "bleibt") {
        return { text: e.zustand === "programm" ? name(e.zustand) : this._tMit("{zustand} läuft", { zustand: name(e.zustand) }) };
      }
      if (e.ergebnis === "wechselt") {
        const zurueck = e.zustand === "programm" && MIT_ABLAUF.has(e.vorher);
        return {
          text: this._tMit("{zustand} endet", { zustand: name(e.vorher) }),
          pille: zurueck
            ? this._t("Steuerung kehrt zum Programm zurück")
            : this._tMit("jetzt {zustand}, ohne Schreiben", { zustand: name(e.zustand) }),
        };
      }
      const zaehler = e.zaehler ? ` ${e.zaehler}/${e.noetig}` : "";
      return { text: `${name(e.kandidat)}${zaehler}`, pille: this._t(ERGEBNISSE[e.ergebnis] || e.ergebnis) };
    }

    /** Ein Lauf der Regel: Zeit, Kopfzeile, Pille und die Marken der Bewertungen. */
    _automatikLaufZeile(e) {
      const zeile = document.createElement("li");
      const zeit = document.createElement("span");
      zeit.className = "zeit";
      zeit.textContent = uhrAus(e.zeit, this._hass);
      const inhalt = document.createElement("div");
      inhalt.className = "inhalt";
      const kopf = this._laufKopf(e);
      const kopfzeile = document.createElement("div");
      kopfzeile.className = `lauf ${e.ergebnis}`;
      kopfzeile.textContent = kopf.text;
      inhalt.appendChild(kopfzeile);
      if (kopf.pille) {
        const art = document.createElement("span");
        art.className = `art ${e.ergebnis}`;
        art.textContent = kopf.pille;
        inhalt.appendChild(art);
      }
      // Der Server liefert je Zeile nur, was entscheidet oder gegenüber dem vorigen Lauf kippte.
      if ((e.bewertungen || []).length) {
        const marken = document.createElement("div");
        marken.className = "automatik-kern";
        e.bewertungen.forEach((b) => marken.appendChild(this._bewertungMarke(b)));
        inhalt.appendChild(marken);
      }
      zeile.append(zeit, inhalt);
      return zeile;
    }

    /** Läufe zwischen zwei Protokolleinträgen als aufklappbare Zeile; offen bleibt offen beim Nachladen. */
    _automatikLaeufe(kreis, gruppe) {
      const zeile = document.createElement("li");
      zeile.className = "automatik-laeufe";
      const bereich = document.createElement("details");
      const schluessel = `${kreis.heizkreis}|${gruppe.schluessel}`;
      this._automatikLaeufeOffen = this._automatikLaeufeOffen || new Set();
      bereich.open = this._automatikLaeufeOffen.has(schluessel);
      bereich.addEventListener("toggle", () => {
        if (bereich.open) this._automatikLaeufeOffen.add(schluessel);
        else this._automatikLaeufeOffen.delete(schluessel);
      });
      const [neuester] = gruppe.laeufe;
      const anzahl = gruppe.laeufe.length;
      const teile = [
        anzahl === 1 ? this._t("1 Prüfung") : this._tMit("{zahl} Prüfungen", { zahl: anzahl }),
        this._tMit("jetzt {zustand}", { zustand: this._t(ZUSTAENDE[neuester.zustand] || neuester.zustand) }),
      ];
      const gezaehlt = gruppe.laeufe.filter((e) => e.zaehler);
      if (gezaehlt.length) {
        const hoechster = gezaehlt.reduce((a, e) => (e.zaehler > a.zaehler ? e : a));
        teile.push(this._tMit("Zähler bis {stand}", { stand: `${hoechster.zaehler}/${hoechster.noetig}` }));
      }
      const kopf = document.createElement("summary");
      const text = document.createElement("span");
      text.textContent = teile.join(" · ");
      kopf.append(this._symbolKnoten("mdi:chevron-down", "pfeil"), text);
      const liste = document.createElement("ul");
      liste.className = "automatik-protokoll automatik-regellauf";
      gruppe.laeufe.forEach((e) => liste.appendChild(this._automatikLaufZeile(e)));
      bereich.append(kopf, liste);
      zeile.appendChild(bereich);
      return zeile;
    }

    /** „Alle anzeigen“ im Kartenkopf einer langen Liste; gibt zurück, ob gerade alle sichtbar sind. */
    _automatikAlleUmschalten(karte, menge, heizkreis, lang) {
      const alle = menge.has(heizkreis);
      const kopf = karte.querySelector(".kartenkopf");
      if (!kopf || !lang) return alle;
      const umschalten = document.createElement("button");
      umschalten.type = "button";
      umschalten.className = "automatik-verweis";
      umschalten.textContent = this._t(alle ? "Weniger anzeigen" : "Alle anzeigen");
      umschalten.setAttribute("aria-expanded", String(alle));
      umschalten.addEventListener("click", () => {
        if (alle) menge.delete(heizkreis);
        else menge.add(heizkreis);
        this._automatikNeuZeichnen();
      });
      kopf.appendChild(umschalten);
      return alle;
    }

    // --- Protokoll -----------------------------------------------------
    /** Einträge nach Tagen: Heute, Gestern, dann das Datum; dazwischen die Läufe der Regel, aufklappbar. */
    _automatikProtokoll(kreis) {
      const karte = this._karte("Protokoll");
      karte.classList.add("automatik-protokollkarte");
      const folge = protokollMitLaeufen(kreis.protokoll || [], kreis.regellauf || []);
      // Gekürzt wird nach Protokolleinträgen; Läufe darüber bleiben sichtbar.
      let ende = 0;
      for (let gezaehlt = 0; ende < folge.length && gezaehlt < PROTOKOLL_KURZ; ende += 1) {
        if (folge[ende].art === "eintrag") gezaehlt += 1;
      }
      this._automatikProtokollAlle = this._automatikProtokollAlle || new Set();
      const alle = this._automatikAlleUmschalten(karte, this._automatikProtokollAlle, kreis.heizkreis, folge.length > ende);
      if (!folge.length) karte.appendChild(this._hinweisKnoten("Noch keine Entscheidung."));
      const zone = zeitzone(this._hass);
      const namen = { [kalendertagIn(Date.now(), zone)]: "Heute", [kalendertagIn(Date.now() - 86400000, zone)]: "Gestern" };
      let liste = null;
      let letzterTag = null;
      (alle ? folge : folge.slice(0, ende)).forEach((teil) => {
        const datum = new Date(teil.art === "eintrag" ? teil.eintrag.zeit : teil.laeufe[0].zeit);
        const tag = kalendertagIn(datum, zone);
        if (tag !== letzterTag) {
          letzterTag = tag;
          const ueberschrift = document.createElement("h4");
          ueberschrift.className = "automatik-protokolltag";
          ueberschrift.textContent = namen[tag] ? this._t(namen[tag]) : tagMonat(datum, zone);
          liste = document.createElement("ul");
          liste.className = "automatik-protokoll";
          karte.append(ueberschrift, liste);
        }
        liste.appendChild(teil.art === "eintrag" ? this._automatikProtokollZeile(teil.eintrag) : this._automatikLaeufe(kreis, teil));
      });
      return karte;
    }

    _automatikProtokollZeile(eintrag) {
      const zeile = document.createElement("li");
      const zeit = document.createElement("span");
      zeit.className = "zeit";
      zeit.textContent = uhrAus(new Date(eintrag.zeit), this._hass);
      const inhalt = document.createElement("div");
      inhalt.className = "inhalt";
      const text = document.createElement("div");
      text.textContent = eintrag.text;
      const art = document.createElement("span");
      art.className = `art ${eintrag.art}`;
      art.textContent = this._t(PROTOKOLL_ARTEN[eintrag.art] || eintrag.art);
      inhalt.append(text, art);
      zeile.append(zeit, inhalt);
      return zeile;
    }
  };
