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
import { BausteineMixin } from "./teile/bausteine.js";
import { BedienenMixin } from "./teile/bedienen.js";
import { HilfeMixin } from "./teile/hilfe.js";
import { SchaubildMixin } from "./teile/schaubild.js";
import { SteuerungMixin } from "./teile/steuerung.js";
import { UebersichtMixin } from "./teile/uebersicht.js";
import { VerlaufMixin } from "./teile/verlauf.js";
import { WartungMixin } from "./teile/wartung.js";
import { WerteMixin } from "./teile/werte.js";
import { ZeitprogrammeMixin } from "./teile/zeitprogramme.js";

const Grundlage = HilfeMixin(
  ZeitprogrammeMixin(
    WartungMixin(
      VerlaufMixin(
        SteuerungMixin(
          UebersichtMixin(
            SchaubildMixin(AnordnenMixin(BausteineMixin(BedienenMixin(WerteMixin(HTMLElement)))))
          )
        )
      )
    )
  )
);

class HeatNexusPanel extends Grundlage {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._gebaut = false;
    this._daten = null;
    this._bindungen = [];
    this._verlaufskarten = [];
    // „Alle" ist der Standard: Wer zwei Anlagen hat, will beide sehen, nicht
    // die erste. Bei nur einer Anlage gibt es die Wahl gar nicht.
    this._anlageIndex = -1;
    this._reiter = "uebersicht";
    // Laufende Bedienvorgänge: Anzeige -> wann begonnen, wann bestätigt.
    this._wartend = [];
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

  set panel(panel) {
    const daten = panel && panel.config ? panel.config.daten : null;
    if (daten !== this._daten) {
      this._daten = daten;
      this._gebaut = false;
    }
    this._zeichnen();
  }

  set hass(hass) {
    const erster = !this._hass;
    this._hass = hass;
    // Die Aufteilung aus `panel.config` stammt aus dem Augenblick der
    // Einrichtung – da war die Anlage erst zur Hälfte eingelesen. Deshalb
    // wird sie beim Öffnen einmal frisch geholt.
    if (erster) {
      this._datenHolen();
      this._anordnungHolen();
    }
    this._zeichnen();
  }

  async _datenHolen() {
    try {
      const daten = await this._hass.callWS({ type: "heatnexus/panel_daten" });
      if (!daten || !daten.anlagen || !daten.anlagen.length) return;
      this._daten = daten;
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
      this._anordnung = (await this._hass.callWS({ type: "heatnexus/anordnung" })) || {};
      this._gebaut = false;
      this._zeichnen();
    } catch (err) {
      console.warn("HeatNexus: Anordnung konnte nicht geladen werden", err);
      this._melden("Die eigene Anordnung konnte nicht geladen werden.");
    }
  }

  set narrow(_narrow) {
    /* Die Aufteilung regelt CSS. */
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

  _stoerung(anlage) {
    return (anlage.stoerungen || []).some((s) => this._stoerungAktiv(s));
  }

  // -------------------------------------------------------------------
  // Aufbau
  // -------------------------------------------------------------------
  _zeichnen() {
    if (!this._hass || !this._daten) return;
    if (!this._gebaut) {
      this._aufbauen();
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
    const bekannt = new Set(Object.keys(PALETTEN.dunkel));
    bekannt.forEach((name) => {
      if (palette) this.style.setProperty(name, palette[name]);
      else this.style.removeProperty(name);
    });
  }

  _aufbauen() {
    this._bindungen = [];
    this._verlaufskarten = [];
    this._wartend = [];
    this._zeitprogrammStand = new Map();
    const anlage = this._aktuelleAnlage();
    const stil = document.createElement("style");
    stil.textContent = STIL;
    this._paletteAnwenden();
    if (!anlage) {
      this.shadowRoot.replaceChildren(stil);
      return;
    }

    const inhalt = document.createElement("div");
    // Marke, Anlagenwahl und Reiter zusammen in einen klebenden Kasten: Wer
    // in der Wartung nach unten blättert, kommt sonst nur über den Weg nach
    // oben zurück in die Übersicht.
    const leiste = document.createElement("div");
    leiste.className = "leiste";
    leiste.append(this._kopfleiste(anlage), this._reiterleiste());
    inhalt.appendChild(leiste);
    if (this._anordnen) inhalt.appendChild(this._anordnenLeiste());
    if (this._alleAnlagen()) {
      this._anlagen().forEach((eintrag) => {
        const ueberschrift = document.createElement("div");
        ueberschrift.className = "anlagen-trenner";
        ueberschrift.textContent = eintrag.name || "Anlage";
        inhalt.append(ueberschrift, this._inhalt(eintrag));
      });
    } else {
      inhalt.appendChild(this._inhalt(anlage));
    }
    this.shadowRoot.replaceChildren(stil, inhalt);
    this._verlaufKarteLaden();
  }

  /** Kopfleiste mit Menütaste, Marke und Anlagenwahl. */
  _kopfleiste(anlage) {
    const leiste = document.createElement("div");
    leiste.className = "kopfleiste";

    // Auf schmalen Bildschirmen verdeckt das Panel die Seitenleiste; über
    // diese Taste kommt sie zurück. Das Ereignis ist dasselbe, das die
    // eigenen Ansichten von Home Assistant benutzen – es muss den
    // Schattenbaum verlassen, daher `composed`.
    const menue = document.createElement("button");
    menue.className = "menue-taste";
    menue.type = "button";
    menue.title = "Seitenleiste anzeigen (Karten, Energie, Einstellungen)";
    menue.setAttribute("aria-label", "Seitenleiste anzeigen");
    // Das eigene Symbol statt eines Hamburgers: Es ist zugleich der Weg
    // zurueck in die uebrigen Ansichten von Home Assistant - auf dem Handy
    // sonst nur ueber eine Wischgeste erreichbar.
    menue.appendChild(this._symbolKnoten("mdi:radiator"));
    menue.addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    });
    leiste.appendChild(menue);

    const marke = document.createElement("div");
    marke.className = "marke";
    marke.textContent = "HeatNexus";
    leiste.appendChild(marke);

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
        taste.textContent = name;
        taste.addEventListener("click", () => {
          this._anlageIndex = index;
          this._gebaut = false;
          this._zeichnen();
        });
        waehler.appendChild(taste);
      });
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
      punkt.appendChild(this._symbolKnoten(symbol));
      const text = document.createElement("span");
      text.textContent = titel;
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
    // Die Vorlage taugt nur dem, der Dashboards anlegen darf.
    if (this._hass && this._hass.user && this._hass.user.is_admin) {
      eintrag("Dashboard-Vorlage", "mdi:code-braces", () => this._dashboardVorlageOeffnen());
    }

    taste.addEventListener("click", (ereignis) => {
      ereignis.stopPropagation();
      liste.hidden = !liste.hidden;
      taste.setAttribute("aria-expanded", String(!liste.hidden));
    });
    // Ein Klick daneben schließt. Gehorcht wird dem Schattenbaum, nicht dem
    // Dokument: Von dort aus zeigt jedes Ereignis auf das Wirtselement.
    this.shadowRoot.addEventListener("click", (ereignis) => {
      const pfad = ereignis.composedPath ? ereignis.composedPath() : [];
      if (!liste.hidden && !pfad.includes(huelle)) zu();
    });

    huelle.append(taste, liste);
    return huelle;
  }

  _reiterleiste() {
    const leiste = document.createElement("div");
    leiste.className = "reiter";
    leiste.setAttribute("role", "tablist");
    REITER.forEach((reiter) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.setAttribute("role", "tab");
      taste.setAttribute("aria-selected", String(reiter.schluessel === this._reiter));
      taste.appendChild(this._symbolKnoten(reiter.symbol));
      const beschriftung = document.createElement("span");
      beschriftung.textContent = reiter.titel;
      taste.appendChild(beschriftung);
      taste.addEventListener("click", () => {
        this._reiter = reiter.schluessel;
        this._gebaut = false;
        this._zeichnen();
      });
      leiste.appendChild(taste);
    });
    return leiste;
  }

  _inhalt(anlage) {
    // Die Karten holen ihre Erklärung über den Titel.
    this._hilfe = anlage.hilfe || {};
    if (this._reiter === "steuerung") {
      return this._raster(anlage, this._steuerung(anlage), "Keine bedienbaren Werte gefunden.");
    }
    if (this._reiter === "wartung") {
      return this._raster(anlage, this._wartung(anlage), "Keine Wartungswerte gefunden.");
    }
    if (this._reiter === "verlauf") {
      return this._raster(
        anlage,
        this._verlaufReiter(anlage),
        "Keine Werte für einen Verlauf gefunden."
      );
    }
    if (this._reiter === "zeitprogramme") {
      return this._raster(
        anlage,
        this._zeitprogrammeReiter(anlage),
        "Diese Anlage meldet keine Zeitprogramme."
      );
    }
    if (this._reiter === "hilfe") {
      return this._raster(anlage, this._hilfeReiter(anlage), "Keine Erklärungen gefunden.");
    }
    return this._raster(anlage, this._uebersicht(anlage), "Keine Werte gefunden.");
  }

  // -------------------------------------------------------------------
  _aktualisieren() {
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
