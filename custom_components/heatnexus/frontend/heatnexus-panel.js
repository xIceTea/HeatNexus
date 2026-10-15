/**
 * HeatNexus – eigene Oberfläche für die Heizung.
 *
 * Die Aufteilung kommt fertig aus der Integration (`panel.config.daten`);
 * hier wird sie nur dargestellt und mit den aktuellen Werten aus `hass`
 * gefüllt. Es gibt keine fest verdrahteten Entitäts-IDs.
 *
 * Bewusst ohne Framework und ohne Bauschritt: Die Dateien werden so
 * ausgeliefert, wie sie hier stehen.
 *
 * **Warum Mixins.** Ein Web-Component ist *eine* Klasse; ihre Methoden lassen
 * sich nicht auf mehrere Dateien verteilen, ohne aus jeder Methode eine
 * Funktion mit durchgereichtem `this` zu machen – das hieße, jede der rund
 * neunzig Methoden und jede ihrer Aufrufstellen anzufassen. Stattdessen bringt
 * jede Datei unter `teile/` ihren Abschnitt als Mixin mit: `(Basis) => class
 * extends Basis { … }`. Die Methoden bleiben Methoden derselben Klasse, jede
 * Datei bleibt für sich lesbar, und `this._karte(…)` funktioniert überall
 * weiter. Diese Datei behält, was das Element als Ganzes ausmacht: Lebenszyklus,
 * Werte-Zugriff, Aufbau, Kopf- und Reiterleiste.
 *
 * Reihenfolge der Mixins: erst die Grundlagen (Bedienen, Bausteine, Anordnen),
 * dann die Reiter. Gleiche Namen gäbe es nur bei einem Fehler; die Datei, die
 * später kommt, gewänne.
 */

import { STIL } from "./stil.js";
import { PALETTEN } from "./ordnung.js";
import { REITER } from "./ordnung.js";
import { AnordnenMixin } from "./teile/anordnen.js";
import { AutomatikMixin } from "./teile/automatik.js";
import { BausteineMixin } from "./teile/bausteine.js";
import { BefundMixin } from "./teile/befund.js";
import { EinrichtungMixin } from "./teile/einrichtung.js";
import { KennwerteMixin } from "./teile/kennwerte.js";
import { BedienenMixin } from "./teile/bedienen.js";
import { HilfeMixin } from "./teile/hilfe.js";
import { SchaubildMixin } from "./teile/schaubild.js";
import { SteuerungMixin } from "./teile/steuerung.js";
import { StoerspeicherMixin } from "./teile/stoerspeicher.js";
import { TagesbildMixin } from "./teile/tagesbild.js";
import { UebersichtMixin } from "./teile/uebersicht.js";
import { VerlaufMixin } from "./teile/verlauf.js";
import { WartungMixin } from "./teile/wartung.js";
import { WerteMixin } from "./teile/werte.js";
import { ZeitprogrammeMixin } from "./teile/zeitprogramme.js";
import { DarstellungMixin } from "./teile/darstellung.js";
import { GemeinsamMixin } from "./teile/gemeinsam.js";

/** Das Stylesheet wird je Seitensitzung einmal geparst und von allen Instanzen geteilt. */
const STILBOGEN = { bogen: null };

const Grundlage = GemeinsamMixin(HilfeMixin(
  ZeitprogrammeMixin(
    WartungMixin(
      VerlaufMixin(
        BefundMixin(AutomatikMixin(
          EinrichtungMixin(
            KennwerteMixin(
              TagesbildMixin(
                SteuerungMixin(
                  UebersichtMixin(StoerspeicherMixin(
                    SchaubildMixin(DarstellungMixin(AnordnenMixin(BausteineMixin(BedienenMixin(WerteMixin(HTMLElement))))))
                  ))
                )
              )
            )
          )
        ))
      )
    )
  )
));

class HeatNexusPanel extends Grundlage {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._gebaut = false;
    this._daten = null;
    // Ob die Aufteilung schon selbst geholt wurde. Danach gilt sie und nicht
    // mehr der Abzug aus der Panel-Anmeldung.
    this._eigeneDaten = false;
    this._zeitgeberListe = new Map();
    this._gelesen = new Set();
    this._bindungen = [];
    this._verlaufskarten = [];
    // „Alle" ist der Standard: Wer zwei Anlagen hat, will beide sehen, nicht
    // die erste. Bei nur einer Anlage gibt es die Wahl gar nicht.
    this._anlageIndex = -1;
    this._reiter = "uebersicht";
    // Laufende Bedienvorgänge: Anzeige -> wann begonnen, wann bestätigt.
    this._wartend = [];
    // Sollwerte, die nach einer Betriebswahl noch nachgerechnet werden.
    this._sollwertWartet = {};
    // Selbst gewählte Anordnung je Reiter; leer heißt: Standard.
    this._anordnung = {};
    this._anordnen = false;
    this._speicherAuftrag = null;
    // Welche Karte gerade gezogen wird; null, solange niemand zieht.
    this._gezogen = null;
    // Betriebswahl je Kreis, wie sie **vor** einer Warmwasserladung stand.
    // Beim Abbrechen wird genau die wiederhergestellt.
    this._wahlVorLadung = {};
    // Zuletzt gezeichnetes Zeitprogramm je Entität. Ohne den Vergleich würde
    // das Wochenraster bei jedem Abruf neu entstehen – auch dann, wenn sich
    // nichts geändert hat.
    this._zeitprogrammStand = new Map();
  }

  /**
   * Die Aufteilung aus der Panel-Anmeldung.
   *
   * Sie ist ein Abzug aus dem Augenblick der Anmeldung und wird auch nach
   * einem Verbindungsabriss wieder zugestellt. Selbst geholte Daten sind
   * jünger und dürfen davon nicht überschrieben werden.
   */
  set panel(panel) {
    const daten = panel && panel.config ? panel.config.daten : null;
    if (this._eigeneDaten) {
      this._datenHolen();
      return;
    }
    if (daten !== this._daten) {
      this._daten = daten;
      this._gebaut = false;
    }
    this._zeichnen();
  }

  connectedCallback() {
    if (!this._abgebaut) return;
    // Nach dem Abbau sind Hörer und Zeitgeber weg; die Oberfläche entsteht neu.
    this._abgebaut = false;
    this._gebaut = false;
    this._zeichnen();
  }

  disconnectedCallback() {
    this._abgebaut = true;
    this._anordnungSchreiben();
    this._dialogeSchliessen();
    this._zeitgeberListe.forEach((auftrag) => auftrag.loesen());
    this._zeitgeberListe.clear();
    if (this._bildGeplant) cancelAnimationFrame(this._bildGeplant);
    this._bildGeplant = 0;
    if (this._aufbauAbbruch) this._aufbauAbbruch.abort();
  }

  /** Eine einmalige Verzögerung, die der Abbau der Oberfläche beendet. */
  _zeitgeber(ruf, ms) {
    const kennung = setTimeout(() => {
      this._zeitgeberListe.delete(kennung);
      ruf();
    }, ms);
    this._zeitgeberListe.set(kennung, { loesen: () => clearTimeout(kennung) });
    return kennung;
  }

  /** Ein wiederkehrender Takt, den der Abbau der Oberfläche beendet. */
  _takt(ruf, ms) {
    const kennung = setInterval(ruf, ms);
    this._zeitgeberListe.set(kennung, { loesen: () => clearInterval(kennung) });
    return kennung;
  }

  _zeitgeberLoesen(kennung) {
    const auftrag = this._zeitgeberListe.get(kennung);
    if (auftrag) auftrag.loesen();
    this._zeitgeberListe.delete(kennung);
  }

  set hass(hass) {
    const vorher = this._hass;
    const erster = !vorher;
    this._hass = hass;
    // Die Aufteilung aus `panel.config` stammt aus dem Augenblick der
    // Einrichtung – da war die Anlage erst zur Hälfte eingelesen. Deshalb
    // wird sie beim Öffnen einmal frisch geholt.
    if (erster) {
      this._datenHolen();
      this._anordnungHolen();
      this._linienHolen();
    }
    if (!erster && this._gebaut && !this._hassGeaendert(vorher, hass)) return;
    this._zeichnenPlanen();
  }

  /** Ob sich etwas geändert hat, das die Anzeige liest: gelesene Entitäten oder Umgebung. */
  _hassGeaendert(alt, neu) {
    const umgebung = ["entities", "devices", "language", "locale", "config", "user", "themes"];
    if (umgebung.some((schluessel) => alt[schluessel] !== neu[schluessel])) return true;
    if (alt.states === neu.states) return false;
    const gelesen = this._gelesen || new Set();
    for (const entitaet of gelesen) {
      if ((alt.states || {})[entitaet] !== (neu.states || {})[entitaet]) return true;
    }
    return false;
  }

  /** Mehrere Zustandsmeldungen kurz hintereinander ergeben einen Durchlauf je Bild. */
  _zeichnenPlanen() {
    if (!this._gebaut) {
      this._zeichnen();
      return;
    }
    if (this._bildGeplant) return;
    this._bildGeplant = requestAnimationFrame(() => {
      this._bildGeplant = 0;
      this._zeichnen();
    });
  }

  /** Gleicher Inhalt, auch bei neuem Objekt: Nur Änderungen lösen einen Neuaufbau aus. */
  _inhaltGleich(a, b) {
    try {
      return JSON.stringify(a) === JSON.stringify(b);
    } catch (err) {
      return false;
    }
  }

  async _datenHolen() {
    try {
      const daten = await this._hass.callWS({ type: "heatnexus/panel_daten" });
      if (!daten || !daten.anlagen || !daten.anlagen.length) return;
      const geaendert = !this._inhaltGleich(daten, this._daten);
      this._eigeneDaten = true;
      this._daten = daten;
      this._texte = daten.texte || {};
      if (!geaendert && this._gebaut) return;
      this._gebaut = false;
      this._zeichnen();
    } catch (err) {
      // Ohne frische Daten bleibt der Stand aus der Panel-Konfiguration.
      console.warn("HeatNexus: Aufteilung konnte nicht geladen werden", err);
      this._melden("Die Anlagendaten konnten nicht geladen werden.");
    }
  }

  /** Die eigene Anordnung holen; ohne sie gilt die Standardanordnung. */
  async _anordnungHolen() {
    try {
      const neu = (await this._hass.callWS({ type: "heatnexus/anordnung" })) || {};
      const geaendert = !this._inhaltGleich(neu, this._anordnung);
      this._anordnung = neu;
      this._einstellungenMerken();
      if (!geaendert && this._gebaut) return;
      this._gebaut = false;
      this._zeichnen();
    } catch (err) {
      console.warn("HeatNexus: Anordnung konnte nicht geladen werden", err);
      this._melden("Die eigene Anordnung konnte nicht geladen werden.");
    }
  }

  set narrow(_narrow) {
    /* Die Aufteilung regelt CSS; die Menütaste steht immer da. */
  }

  // -------------------------------------------------------------------
  // Werte
  // -------------------------------------------------------------------
  // Ob eine Störung ansteht, sagt der Ja/Nein-Sensor. Das Attribut des
  // Klartextsensors bleibt als Rückfall, bis ein alter Erkennungsstand den
  // neuen Sensor nachgezogen hat.
  _stoerungAktiv(eintrag) {
    const melder = eintrag.melder && this._zustand(eintrag.melder);
    if (melder) return melder.state === "on";
    const zustand = this._zustand(eintrag.entity);
    return !!zustand && zustand.attributes.stoerung_aktiv === true;
  }

  /** Ob jede Meldung dieser Gerätezeile als anliegender Eintrag im Störspeicher steht. */
  _stoerungImSpeicher(eintrag, anlage) {
    const codes = new Set(
      this._stoerspeicherEintraege(anlage.stoerspeicher).filter((e) => e.aktiv).map((e) => String(e.code))
    );
    const zustand = this._zustand(eintrag.entity);
    const meldungen = (zustand && zustand.attributes.meldungen) || [];
    return meldungen.length > 0 && meldungen.every((m) => codes.has(String(m.code)));
  }

  /**
   * „ok“, „info“, „fehler“ oder „alarm“: die schwerste anliegende Meldungsart. Im Störspeicher
   * zählt der Kennbuchstabe; eine Gerätemeldung ohne Eintrag zählt als Fehler, ein Alarm als Alarm.
   */
  _stoerungsstufe(anlage) {
    const arten = this._stoerspeicherEintraege(anlage.stoerspeicher)
      .filter((e) => e.aktiv)
      .map((e) => ({ A: "alarm", I: "info" })[e.symbol] || "fehler");
    for (const s of anlage.stoerungen || []) {
      if (!this._stoerungAktiv(s) || this._stoerungImSpeicher(s, anlage)) continue;
      const zustand = this._zustand(s.entity);
      const meldungen = (zustand && zustand.attributes.meldungen) || [];
      arten.push(meldungen.some((m) => m.kind === "Alarm") ? "alarm" : "fehler");
    }
    return ["alarm", "fehler", "info"].find((art) => arten.includes(art)) || "ok";
  }

  _stoerung(anlage) {
    return this._stoerungsstufe(anlage) !== "ok";
  }

  // -------------------------------------------------------------------
  // Aufbau
  // -------------------------------------------------------------------
  _zeichnen() {
    if (!this._hass || !this._daten) return;
    if (!this._gebaut) {
      this._aufbauen();
      this._uebersetzen(this.shadowRoot);
      this._gebaut = true;
    }
    this._aktualisieren();
  }

  _anlagen() {
    return (this._daten && this._daten.anlagen) || [];
  }

  _alleAnlagen() {
    return this._anlageIndex < 0 && this._anlagen().length > 1;
  }

  _aktuelleAnlage() {
    const anlagen = this._anlagen();
    if (this._anlageIndex < 0) return anlagen[0];
    return anlagen[Math.min(this._anlageIndex, anlagen.length - 1)];
  }

  /** Den gewählten Farbsatz am Wirtselement setzen; `auto` räumt ihn ab. */
  _paletteAnwenden() {
    const palette = PALETTEN[this._farbsatz()] || null;
    // Alle Farbsätze zusammen nennen die Eigenschaften, die wieder zu entfernen sind.
    const bekannt = new Set(Object.values(PALETTEN).flatMap((satz) => Object.keys(satz)));
    bekannt.forEach((name) => {
      if (palette) this.style.setProperty(name, palette[name]);
      else this.style.removeProperty(name);
    });
  }

  /**
   * Das Stylesheet geteilt einsetzen; die Liste enthält Knoten, die vor den Inhalt gehören.
   * Ohne `adoptedStyleSheets` bleibt der Rückfall auf ein `<style>`-Element.
   */
  _stilEinsetzen() {
    const wurzel = this.shadowRoot;
    if (typeof CSSStyleSheet === "function" && "adoptedStyleSheets" in wurzel) {
      try {
        if (!STILBOGEN.bogen) {
          STILBOGEN.bogen = new CSSStyleSheet();
          STILBOGEN.bogen.replaceSync(STIL);
        }
        wurzel.adoptedStyleSheets = [STILBOGEN.bogen];
        return [];
      } catch (err) {
        console.warn("HeatNexus: Geteiltes Stylesheet nicht möglich", err);
      }
    }
    const stil = document.createElement("style");
    stil.textContent = STIL;
    return [stil];
  }

  /** Ersetzt die Oberfläche, lässt aber offene Fenster stehen: Wer gerade eines ausfüllt, verliert es nicht. */
  _flaecheErsetzen(...knoten) {
    const wurzel = this.shadowRoot;
    [...wurzel.children]
      .filter((kind) => !(kind.classList && kind.classList.contains("schleier")))
      .forEach((kind) => kind.remove());
    const fenster = wurzel.children[0];
    knoten.forEach((kind) => wurzel.insertBefore(kind, fenster || null));
  }

  _aufbauen() {
    // Hörer an Knoten, die den Neuaufbau überleben, hängen an diesem Signal.
    if (this._aufbauAbbruch) this._aufbauAbbruch.abort();
    this._aufbauAbbruch = new AbortController();
    this._gelesen = new Set();
    this._bindungen = [];
    this._verlaufskarten = [];
    this._wartend = [];
    this._zeitprogrammStand = new Map();
    const anlage = this._aktuelleAnlage();
    const stil = this._stilEinsetzen();
    this._paletteAnwenden();
    if (!anlage) {
      this._flaecheErsetzen(...stil);
      return;
    }

    const inhalt = document.createElement("div");
    // Marke, Anlagenwahl und Reiter zusammen in einen klebenden Kasten: Wer
    // in der Wartung nach unten blättert, kommt sonst nur über den Weg nach
    // oben zurück in die Übersicht.
    const leiste = document.createElement("div");
    leiste.className = "leiste";
    leiste.append(this._kopfleiste(anlage), this._reiterleiste());
    // Beim Anordnen steht die Leiste mit im Kasten, damit Spalten und „Fertig“ beim Blättern erreichbar bleiben.
    if (this._anordnen) leiste.appendChild(this._anordnenLeiste());
    inhalt.appendChild(leiste);
    const flaechen = [];
    const gemeinsam = this._alleAnlagen() && this._gemeinsameFlaeche();
    if (gemeinsam) {
      flaechen.push(gemeinsam);
      inhalt.appendChild(gemeinsam);
    } else if (this._alleAnlagen()) {
      if (this._reiter === "zeitprogramme") inhalt.appendChild(this._zeitprogrammeHeute());
      this._anlagen().forEach((eintrag) => {
        const ueberschrift = document.createElement("div");
        ueberschrift.className = "anlagen-trenner";
        ueberschrift.textContent = eintrag.name || "Anlage";
        ueberschrift.dataset.roh = "";
        const flaeche = this._anlagenInhalt(eintrag);
        flaechen.push(flaeche);
        inhalt.append(ueberschrift, flaeche);
      });
    } else {
      flaechen.push(this._anlagenInhalt(anlage));
      inhalt.appendChild(flaechen[0]);
    }
    this._reiterFlaechen(inhalt, flaechen);
    const alteLeiste = this.shadowRoot.querySelector(".reiter");
    const vorher = (alteLeiste && alteLeiste.scrollLeft) || 0;
    this._flaecheErsetzen(...stil, inhalt);
    this._reiterZeigen(inhalt, vorher);
    if (this._tastaturFokus) {
      const taste = inhalt.querySelector(this._tastaturFokus);
      this._tastaturFokus = null;
      if (taste) taste.focus();
    }
    this._verlaufKarteLaden();
  }

  /** Kopfleiste mit Menütaste, Marke und Anlagenwahl. */
  _kopfleiste(anlage) {
    const leiste = document.createElement("div");
    leiste.className = "kopfleiste";

    // Auf schmalen Bildschirmen verdeckt das Panel die Seitenleiste; über
    // das Zeichen oder die Menütaste davor kommt sie zurück.
    leiste.append(...this._kopfanfang());

    const abstand = document.createElement("div");
    abstand.className = "abstand";
    leiste.appendChild(abstand);

    // Die Außentemperatur gilt für die ganze Anlage – an der Anlage selbst
    // steht sie deshalb in der Kopfzeile und nicht bei einem Anlagenteil.
    //
    // Unter „Alle" gibt es keine einzelne Anlage, deren Fühler gälte; dort
    // zählt die in den Optionen gewählte Entität. Steht keine da, nimmt die
    // Kopfzeile den Wert der ersten Anlage.
    if (this._alleAnlagen() && this._daten && this._daten.aussentemperatur) {
      anlage = { ...anlage, aussentemperatur: this._daten.aussentemperatur };
    }
    if (anlage.aussentemperatur) {
      const aussen = document.createElement("div");
      aussen.className = "aussen";
      aussen.appendChild(this._symbolKnoten("mdi:thermometer"));
      const wert = document.createElement("span");
      aussen.appendChild(wert);
      leiste.appendChild(this._klickbar(aussen, anlage.aussentemperatur));
      this._bindungen.push(() => {
        wert.textContent = this._text(anlage.aussentemperatur);
      });
    }

    const anlagen = this._anlagen();
    if (anlagen.length > 1) {
      const waehler = document.createElement("div");
      waehler.className = "waehler";
      waehler.setAttribute("role", "tablist");
      // "Alle" stellt die Anlagen untereinander - mit Ueberschrift je Anlage,
      // damit man beim Scrollen sieht, wo die naechste anfaengt.
      const eintraege = [{ name: "Alle", index: -1 }].concat(
        anlagen.map((a, index) => ({ name: a.name || `Anlage ${index + 1}`, index }))
      );
      eintraege.forEach(({ name, index }) => {
        const taste = document.createElement("button");
        taste.type = "button";
        taste.setAttribute("role", "tab");
        taste.setAttribute("aria-selected", String(index === this._anlageIndex));
        taste.dataset.anlage = String(index);
        taste.textContent = name;
        if (index >= 0) taste.dataset.roh = "";
        taste.addEventListener("click", (ereignis) => {
          this._tastaturFokus = ereignis.detail === 0 ? `[data-anlage="${index}"]` : null;
          this._anlageIndex = index;
          this._gebaut = false;
          this._zeichnen();
        });
        waehler.appendChild(taste);
      });
      this._reiterTastatur(waehler);
      leiste.appendChild(waehler);
    }

    // Die Werkzeuge stehen ganz außen: Sie gehören nicht zum Ablesen, sondern
    // zum Einrichten. Zwischen Außentemperatur und Anlagenwahl stünden sie
    // mitten in den Angaben, die man ständig liest.
    leiste.appendChild(this._werkzeugmenue());

    return leiste;
  }

  /**
   * Die Werkzeuge der Oberfläche hinter einem Knopf.
   *
   * Einzelne Symbole nebeneinander wachsen mit jedem weiteren Werkzeug in die
   * Kopfzeile hinein; ein Menü bleibt gleich breit.
   */
  _werkzeugmenue() {
    const huelle = document.createElement("div");
    huelle.className = "werkzeuge";

    const taste = document.createElement("button");
    taste.className = "menue-taste";
    taste.type = "button";
    taste.title = "Werkzeuge";
    taste.setAttribute("aria-label", "Werkzeuge");
    taste.setAttribute("aria-haspopup", "menu");
    taste.setAttribute("aria-expanded", "false");
    taste.appendChild(this._symbolKnoten("mdi:dots-vertical"));

    const liste = document.createElement("div");
    liste.className = "werkzeugliste";
    liste.setAttribute("role", "menu");
    liste.hidden = true;

    const zu = () => {
      liste.hidden = true;
      taste.setAttribute("aria-expanded", "false");
    };
    const eintrag = (titel, symbol, ruf) => {
      const punkt = document.createElement("button");
      punkt.type = "button";
      punkt.setAttribute("role", "menuitem");
      punkt.setAttribute("tabindex", "-1");
      punkt.appendChild(this._symbolKnoten(symbol));
      const text = document.createElement("span");
      text.textContent = this._t(titel);
      punkt.appendChild(text);
      punkt.addEventListener("click", () => {
        zu();
        ruf();
      });
      liste.appendChild(punkt);
    };

    eintrag(
      this._anordnen ? "Bearbeiten beenden" : "Ansicht bearbeiten",
      this._anordnen ? "mdi:check" : "mdi:view-dashboard-edit-outline",
      () => this._anordnenUmschalten()
    );
    eintrag("Darstellung", "mdi:palette-outline", () => this._darstellungOeffnen());
    // Die Vorlage taugt nur dem, der Dashboards anlegen darf.
    if (this._hass && this._hass.user && this._hass.user.is_admin) {
      eintrag("Dashboard-Vorlage", "mdi:code-braces", () => this._dashboardVorlageOeffnen());
    }

    const punkte = () => [...liste.children];
    const auf = (fokusPunkt) => {
      liste.hidden = false;
      taste.setAttribute("aria-expanded", "true");
      if (fokusPunkt) {
        const alle = punkte();
        (fokusPunkt === "letzter" ? alle[alle.length - 1] : alle[0]).focus();
      }
    };
    taste.addEventListener("click", (ereignis) => {
      ereignis.stopPropagation();
      if (liste.hidden) auf(ereignis.detail === 0 ? "erster" : null);
      else zu();
    });
    huelle.addEventListener("keydown", (ereignis) => {
      const alle = punkte();
      const stelle = alle.indexOf(ereignis.target);
      if (ereignis.key === "Escape" && !liste.hidden) {
        ereignis.preventDefault();
        zu();
        taste.focus();
      } else if (ereignis.target === taste && ["ArrowDown", "ArrowUp"].includes(ereignis.key)) {
        ereignis.preventDefault();
        auf(ereignis.key === "ArrowUp" ? "letzter" : "erster");
      } else if (stelle >= 0) {
        if (ereignis.key === "Tab") {
          zu();
          return;
        }
        const ziel = this._pfeilZiel(alle, stelle, ereignis.key, false);
        if (!ziel) return;
        ereignis.preventDefault();
        ziel.focus();
      }
    });
    // Ein Klick daneben schließt. Gehorcht wird dem Schattenbaum, nicht dem
    // Dokument: Von dort aus zeigt jedes Ereignis auf das Wirtselement.
    this.shadowRoot.addEventListener(
      "click",
      (ereignis) => {
        const pfad = ereignis.composedPath ? ereignis.composedPath() : [];
        if (!liste.hidden && !pfad.includes(huelle)) zu();
      },
      { signal: this._aufbauAbbruch.signal }
    );

    huelle.append(taste, liste);
    return huelle;
  }

  _reiterleiste() {
    const leiste = document.createElement("div");
    leiste.className = "reiter";
    leiste.setAttribute("role", "tablist");
    const versteckt = this._reiterVersteckt();
    const folge = this._reiterFolge();
    const sichtbar = folge.filter((reiter) => !versteckt.has(reiter.schluessel));
    // Ein ausgeblendeter Reiter bleibt nur beim Bearbeiten erreichbar.
    if (!this._anordnen && !sichtbar.some((reiter) => reiter.schluessel === this._reiter) && sichtbar.length) {
      this._reiter = sichtbar[0].schluessel;
    }
    (this._anordnen ? folge : sichtbar).forEach((reiter) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.dataset.reiter = reiter.schluessel;
      if (versteckt.has(reiter.schluessel)) taste.classList.add("versteckt");
      taste.setAttribute("role", "tab");
      taste.id = `reiter-${reiter.schluessel}`;
      taste.setAttribute("aria-selected", String(reiter.schluessel === this._reiter));
      taste.appendChild(this._symbolKnoten(reiter.symbol));
      const beschriftung = document.createElement("span");
      beschriftung.textContent = reiter.titel;
      taste.appendChild(beschriftung);
      if (reiter.schluessel === "automatik") this._reiterPunkt(taste);
      taste.addEventListener("click", (ereignis) => {
        this._tastaturFokus = ereignis.detail === 0 ? `[data-reiter="${reiter.schluessel}"]` : null;
        this._reiter = reiter.schluessel;
        if (reiter.schluessel === "befund") this._befund = undefined;
        this._gebaut = false;
        this._zeichnen();
      });
      leiste.appendChild(taste);
      if (this._anordnen) leiste.appendChild(this._reiterGriffe(reiter, versteckt.has(reiter.schluessel)));
    });
    this._reiterTastatur(leiste);
    return leiste;
  }

  /**
   * Am Telefon passen nicht alle Reiter in die Leiste. Der Neuaufbau behält ihre Position;
   * nur ein verdeckter gewählter Reiter rückt so weit nach, dass er ganz zu sehen ist.
   */
  _reiterZeigen(inhalt, vorher) {
    const leiste = inhalt.querySelector(".reiter");
    if (!leiste) return;
    leiste.scrollLeft = vorher;
    const taste = leiste.querySelector('[aria-selected="true"]');
    if (!taste || !(leiste.scrollWidth > leiste.clientWidth) || !taste.getBoundingClientRect) return;
    const rand = leiste.getBoundingClientRect();
    const knopf = taste.getBoundingClientRect();
    if (knopf.left < rand.left) leiste.scrollLeft -= rand.left - knopf.left;
    else if (knopf.right > rand.right) leiste.scrollLeft += knopf.right - rand.right;
  }

  /**
   * Tastaturmuster für Reiter: nur der gewählte Reiter ist Tabulatorziel,
   * Pfeile, Pos1 und Ende bewegen den Fokus, Eingabe wählt.
   */
  _reiterTastatur(leiste) {
    const reiter = [...leiste.children].filter((kind) => kind.getAttribute("role") === "tab");
    reiter.forEach((taste) => {
      taste.setAttribute("tabindex", taste.getAttribute("aria-selected") === "true" ? "0" : "-1");
    });
    leiste.addEventListener("keydown", (ereignis) => {
      const stelle = reiter.indexOf(ereignis.target);
      if (stelle < 0) return;
      const ziel = this._pfeilZiel(reiter, stelle, ereignis.key, true);
      if (!ziel) return;
      ereignis.preventDefault();
      ziel.focus();
    });
  }

  /** Das Ziel einer Pfeiltaste in einer Reihe von Bedienelementen; null bei anderen Tasten. */
  _pfeilZiel(elemente, stelle, taste, waagerecht) {
    const zurueck = waagerecht ? "ArrowLeft" : "ArrowUp";
    const vor = waagerecht ? "ArrowRight" : "ArrowDown";
    if (taste === "Home") return elemente[0];
    if (taste === "End") return elemente[elemente.length - 1];
    if (taste === vor) return elemente[(stelle + 1) % elemente.length];
    if (taste === zurueck) return elemente[(stelle - 1 + elemente.length) % elemente.length];
    return null;
  }

  /** Verbindet die Reiter mit den Flächen, die sie zeigen (`tabpanel`). */
  _reiterFlaechen(inhalt, flaechen) {
    const ids = flaechen.map((flaeche, nr) => {
      flaeche.id = `reiterflaeche-${nr}`;
      flaeche.setAttribute("role", "tabpanel");
      flaeche.setAttribute("aria-labelledby", `reiter-${this._reiter}`);
      return flaeche.id;
    });
    inhalt.querySelectorAll('[role="tab"]').forEach((taste) => taste.setAttribute("aria-controls", ids.join(" ")));
  }

  /** Beim Bearbeiten: Reiter nach links, nach rechts, aus- oder einblenden. */
  _reiterGriffe(reiter, verborgen) {
    const griffe = document.createElement("div");
    griffe.className = "reiter-griffe";
    [
      ["mdi:chevron-left", "Nach links", () => this._reiterVerschieben(reiter.schluessel, -1)],
      ["mdi:chevron-right", "Nach rechts", () => this._reiterVerschieben(reiter.schluessel, 1)],
      [verborgen ? "mdi:eye-off-outline" : "mdi:eye-outline", verborgen ? "Einblenden" : "Ausblenden", () => this._reiterAusblenden(reiter.schluessel)],
    ].forEach(([symbol, titel, aktion]) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.title = this._t(titel);
      taste.setAttribute("aria-label", `${this._t(titel)}: ${reiter.titel}`);
      taste.appendChild(this._symbolKnoten(symbol));
      taste.addEventListener("click", aktion);
      griffe.appendChild(taste);
    });
    return griffe;
  }

  /** Der Inhalt einer Anlage in ihrer Sprache; die Automatik spricht die gemeinsame. */
  _anlagenInhalt(anlage) {
    if (this._reiter === "automatik") return this._inhalt(anlage);
    return this._inSprache(anlage, (sicht) => sicht._inhalt(anlage));
  }

  _inhalt(anlage) {
    const { karten, leer } = this._reiterKarten(anlage);
    return this._raster(anlage, karten, leer);
  }

  /** Die Karten des offenen Reiters für eine Anlage, dazu der Text, falls keine da ist. */
  _reiterKarten(anlage) {
    // Die Karten holen ihre Erklärung über den Titel.
    this._hilfe = anlage.hilfe || {};
    const reiter = {
      steuerung: [() => this._steuerung(anlage), "Keine bedienbaren Werte gefunden."],
      automatik: [() => this._automatikReiter(anlage), "Keine Heizkreise gefunden."],
      befund: [() => this._befundReiter(anlage), "Für diese Anlage liegt noch keine Auswertung vor."],
      wartung: [() => this._wartung(anlage), "Keine Wartungswerte gefunden."],
      verlauf: [() => this._verlaufReiter(anlage), "Keine Werte für einen Verlauf gefunden."],
      zeitprogramme: [() => this._zeitprogrammeReiter(anlage), "Diese Anlage meldet keine Zeitprogramme."],
      hilfe: [() => this._hilfeReiter(anlage), "Keine Erklärungen gefunden."],
    }[this._reiter] || [() => this._uebersicht(anlage), "Keine Werte gefunden."];
    return { karten: reiter[0](), leer: reiter[1] };
  }

  // -------------------------------------------------------------------
  /** Ob eine Automatik eine Empfehlung offen hat; gelesen am Sensor „Empfehlung“, nicht an der Automatik. */
  _empfehlungOffen() {
    const hass = this._hass;
    if (!hass || !hass.entities) return false;
    if (this._empfehlungQuelle !== hass.entities) {
      this._empfehlungQuelle = hass.entities;
      this._empfehlungSensoren = Object.values(hass.entities)
        .filter((e) => e.platform === "heatnexus" && e.translation_key === "automatik_empfehlung")
        .map((e) => e.entity_id);
    }
    return this._empfehlungSensoren.some((id) => {
      const zustand = (this._zustand(id) || {}).state;
      return Boolean(zustand) && !["keine", "unknown", "unavailable"].includes(zustand);
    });
  }

  /** Der Punkt am Reiter „Automatik“, solange eine Empfehlung auf Antwort wartet. */
  _reiterPunkt(taste) {
    const offen = this._empfehlungOffen();
    taste.classList.toggle("punkt", offen);
    if (offen) taste.title = this._t("Empfehlung offen");
    else taste.removeAttribute("title");
  }

  _aktualisieren() {
    const leiste = this.shadowRoot.querySelector(".reiter");
    const automatik = leiste && [...leiste.querySelectorAll("button")].find((b) => b.dataset.reiter === "automatik");
    if (automatik) this._reiterPunkt(automatik);
    this._bindungen.forEach((binden) => binden());
    this._pruefeWartende();
    (this._verlaufskarten || []).forEach((karte) => {
      karte.hass = this._hass;
    });
  }
}

/*
 * Der Name des Anzeigeelements trägt die Fassungsnummer.
 *
 * Ein Element lässt sich im Browser nur einmal je Seitensitzung anmelden. Mit
 * festem Namen übersprang eine neu geladene Fassung die Anmeldung, und die
 * alte Klasse zeichnete weiter – sichtbar wurde die Änderung erst nach
 * Strg+Umschalt+R. Die Fassung steht schon im Pfad dieser Datei
 * (`/heatnexus-frontend/<fassung>/heatnexus-panel.js`), von dort kommt sie.
 *
 * Passt der Pfad nicht zum Muster, bleibt es beim bisherigen Namen; dann ist
 * das Verhalten wie vorher, aber nichts kaputt. Die Integration bildet
 * denselben Namen in `const.panel_element`.
 */
const FASSUNG = (import.meta.url.match(/\/heatnexus-frontend\/([^/]+)\//) || [])[1];
const ELEMENT = FASSUNG ? `heatnexus-panel-${FASSUNG}` : "heatnexus-panel";
if (!customElements.get(ELEMENT)) {
  customElements.define(ELEMENT, HeatNexusPanel);
}

// Eine Seite von vor der Einrichtung kennt das Kartenmodul nicht; Lovelace lädt es dort nie nach.
// Ist es hier definiert, baut das Dashboard seine Fehlerkarten über `whenDefined` selbst neu.
if (!customElements.get("heatnexus-schaubild")) {
  import("./heatnexus-schaubild-karte.js").catch((err) =>
    console.warn("HeatNexus: Kartenmodul konnte nicht geladen werden", err)
  );
}
