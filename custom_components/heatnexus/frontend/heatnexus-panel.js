/**
 * HeatNexus – eigene Oberfläche für die Heizung.
 *
 * Die Aufteilung kommt fertig aus der Integration (`panel.config.daten`);
 * hier wird sie nur dargestellt und mit den aktuellen Werten aus `hass`
 * gefüllt. Es gibt keine fest verdrahteten Entitäts-IDs.
 *
 * Bewusst ohne Framework und ohne Bauschritt: Die Datei wird so ausgeliefert,
 * wie sie hier steht.
 */

const OHNE_WERT = ["unavailable", "unknown", "none", ""];

// Wie lange „übertragen ✓" stehen bleibt, bevor wieder der Zustand erscheint.
const RUECKMELDUNG_MS = 4000;

const STIL = `
  :host {
    display: block;
    background: var(--primary-background-color, #0e1419);
    color: var(--primary-text-color, #e6edf3);
    min-height: 100%;
    box-sizing: border-box;
  }
  * { box-sizing: border-box; }
  .rahmen {
    display: grid;
    gap: 16px;
    padding: 16px;
    grid-template-columns: minmax(280px, 340px) minmax(0, 1fr) minmax(280px, 340px);
    grid-template-areas:
      "seite schema status"
      "seite kreise status"
      "verlauf verlauf schnell";
    align-items: start;
  }
  @media (max-width: 1180px) {
    .rahmen {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: "seite" "schema" "kreise" "status" "verlauf" "schnell";
    }
  }
  .karte {
    background: var(--card-background-color, #151d26);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 16px 18px;
  }
  .karte + .karte { margin-top: 16px; }
  h2 {
    margin: 0 0 14px;
    font-size: 17px;
    font-weight: 600;
    letter-spacing: 0.2px;
  }
  h3 {
    margin: 18px 0 10px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    opacity: 0.55;
  }
  .kopf { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
  .kopf .marke { font-size: 24px; font-weight: 700; line-height: 1.15; }
  .kopf .unterzeile { font-size: 13px; opacity: 0.6; }
  .abzeichen {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 14px; border-radius: 999px; font-weight: 600; font-size: 14px;
    background: rgba(67, 160, 71, 0.15); color: #7bd88f;
  }
  .abzeichen.stoerung { background: rgba(229, 57, 53, 0.15); color: #ff8a80; }
  .zeile {
    display: flex; align-items: center; gap: 12px;
    padding: 11px 12px; border-radius: 12px;
    background: rgba(255, 255, 255, 0.03);
  }
  .zeile + .zeile { margin-top: 8px; }
  .zeile .text { flex: 1; min-width: 0; }
  .zeile .titel { font-size: 14px; font-weight: 600; }
  .zeile .unter { font-size: 12px; opacity: 0.55; }
  .zeile .wert { font-size: 18px; font-weight: 600; white-space: nowrap; }
  .zeile .wert.klein { font-size: 15px; }
  .status-zeile {
    display: flex; align-items: center; gap: 12px; padding: 9px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }
  .status-zeile:last-child { border-bottom: none; }
  .status-zeile .titel { flex: 1; font-size: 14px; }
  .status-zeile .wert { font-weight: 600; font-size: 14px; color: #6fb2f5; }
  ha-icon { --mdc-icon-size: 22px; opacity: 0.85; flex: none; }
  .schaubild { width: 100%; position: relative; }
  .schaubild img { width: 100%; display: block; border-radius: 12px; }
  .schaubild .marke-wert {
    position: absolute; transform: translate(-50%, -50%);
    background: rgba(10, 14, 19, 0.72); color: #fff;
    font-size: 15px; font-weight: 600; padding: 3px 9px;
    border-radius: 8px; white-space: nowrap;
  }
  .doppel { display: grid; gap: 16px; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); }
  @media (max-width: 900px) { .doppel { grid-template-columns: minmax(0, 1fr); } }
  .gitter { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }
  .taste {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 16px 10px; border-radius: 14px; cursor: pointer;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: inherit; font: inherit; text-align: center;
  }
  .taste:hover { background: rgba(255, 255, 255, 0.08); }
  .taste .beschriftung { font-size: 13px; font-weight: 600; }
  .taste.an { border-color: rgba(111, 178, 245, 0.5); color: #6fb2f5; }
  select {
    width: 100%; padding: 9px 10px; border-radius: 10px;
    background: rgba(255, 255, 255, 0.05); color: inherit;
    border: 1px solid rgba(255, 255, 255, 0.1); font: inherit;
  }
  .rueckmeldung { font-size: 11px; opacity: 0.5; min-height: 14px; }
  .rueckmeldung.laeuft { opacity: 0.9; color: #6fb2f5; }
  .rueckmeldung.erfolg { opacity: 1; color: #7bd88f; }
  .rueckmeldung.fehler { opacity: 1; color: #ff8a80; }
  .taste[disabled] { opacity: 0.6; cursor: progress; }
  .taste.an .beschriftung { text-shadow: 0 0 12px rgba(111, 178, 245, 0.6); }
  .schleier {
    position: fixed; inset: 0; z-index: 20;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, 0.55); padding: 16px;
  }
  .dialog {
    background: var(--card-background-color, #151d26);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px; padding: 22px 24px; max-width: 420px; width: 100%;
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
  }
  .dialog-titel { margin: 0 0 10px; font-size: 17px; font-weight: 600;
    text-transform: none; letter-spacing: 0; opacity: 1; }
  .dialog-text { font-size: 14px; line-height: 1.5; opacity: 0.8; }
  .dialog-leiste { display: flex; gap: 10px; justify-content: flex-end; margin-top: 22px; }
  .dialog-taste {
    padding: 9px 16px; border-radius: 10px; font: inherit; font-weight: 600;
    cursor: pointer; color: inherit;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }
  .dialog-taste:hover { background: rgba(255, 255, 255, 0.12); }
  .dialog-taste.betont { background: rgba(229, 57, 53, 0.2); border-color: rgba(229, 57, 53, 0.5);
    color: #ff8a80; }
  .klickbar { cursor: pointer; }
  .klickbar:hover { background: rgba(255, 255, 255, 0.07); }
  .status-zeile.klickbar:hover { background: rgba(255, 255, 255, 0.05); border-radius: 8px; }
  .marke-wert.klickbar:hover { background: rgba(10, 14, 19, 0.92); }
  .klickbar:focus-visible { outline: 2px solid #6fb2f5; outline-offset: 2px; }
  .hinweis { opacity: 0.6; font-size: 14px; padding: 6px 0; }
  .gut { color: #7bd88f; }
  .schlecht { color: #ff8a80; }
`;

class HeatNexusPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._gebaut = false;
    this._daten = null;
    this._bindungen = [];
    this._verlaufskarte = null;
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
    if (erster) this._datenHolen();
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
    }
  }

  set narrow(_narrow) {
    /* Die Aufteilung regelt CSS. */
  }

  // -------------------------------------------------------------------
  // Werte
  // -------------------------------------------------------------------
  _zustand(entity) {
    return this._hass && this._hass.states ? this._hass.states[entity] : undefined;
  }

  _text(entity) {
    const zustand = this._zustand(entity);
    if (!zustand || OHNE_WERT.includes(String(zustand.state).toLowerCase())) return "–";
    if (this._hass.formatEntityState) return this._hass.formatEntityState(zustand);
    const einheit = zustand.attributes.unit_of_measurement;
    return einheit ? `${zustand.state} ${einheit}` : zustand.state;
  }

  _name(entity) {
    const zustand = this._zustand(entity);
    return (zustand && zustand.attributes.friendly_name) || entity;
  }

  /**
   * Ein Element zur Entität führen: Klick öffnet die Detailansicht.
   *
   * `hass-more-info` ist das Ereignis, das auch die Lovelace-Karten benutzen.
   * Es muss den Schattenbaum verlassen, sonst hört Home Assistant es nicht –
   * daher `composed`.
   */
  _klickbar(element, entity) {
    if (!entity) return element;
    element.classList.add("klickbar");
    element.setAttribute("role", "button");
    element.setAttribute("tabindex", "0");
    const oeffnen = () => {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId: entity },
          bubbles: true,
          composed: true,
        })
      );
    };
    element.addEventListener("click", oeffnen);
    element.addEventListener("keydown", (ereignis) => {
      if (ereignis.key === "Enter" || ereignis.key === " ") {
        ereignis.preventDefault();
        oeffnen();
      }
    });
    return element;
  }

  _stoerung(anlage) {
    return (anlage.stoerungen || []).some((s) => {
      const zustand = this._zustand(s.entity);
      return zustand && zustand.attributes.stoerung_aktiv === true;
    });
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

  _aufbauen() {
    this._bindungen = [];
    const anlagen = this._daten.anlagen || [];
    const stil = document.createElement("style");
    stil.textContent = STIL;

    const inhalt = document.createElement("div");
    anlagen.forEach((anlage) => inhalt.appendChild(this._anlage(anlage)));

    this.shadowRoot.replaceChildren(stil, inhalt);
    this._verlaufKarteLaden(anlagen);
  }

  _anlage(anlage) {
    const rahmen = document.createElement("div");
    rahmen.className = "rahmen";
    rahmen.append(
      this._bereich("seite", this._seite(anlage)),
      this._bereich("schema", this._schaubild(anlage)),
      this._bereich("kreise", this._kreiseUndWasser(anlage)),
      this._bereich("status", this._status(anlage)),
      this._bereich("verlauf", this._verlauf(anlage)),
      this._bereich("schnell", this._schnellzugriff(anlage))
    );
    return rahmen;
  }

  _bereich(name, knoten) {
    const huelle = document.createElement("div");
    huelle.style.gridArea = name;
    huelle.style.minWidth = "0";
    if (knoten) huelle.appendChild(knoten);
    return huelle;
  }

  _karte(titel) {
    const karte = document.createElement("div");
    karte.className = "karte";
    if (titel) {
      const ueberschrift = document.createElement("h2");
      ueberschrift.textContent = titel;
      karte.appendChild(ueberschrift);
    }
    return karte;
  }

  _symbolKnoten(symbol) {
    const ikone = document.createElement("ha-icon");
    ikone.setAttribute("icon", symbol);
    return ikone;
  }

  // -------------------------------------------------------------------
  // Linke Spalte: Marke, Zustand, Kennwerte
  // -------------------------------------------------------------------
  _seite(anlage) {
    const karte = this._karte(null);

    const kopf = document.createElement("div");
    kopf.className = "kopf";
    kopf.appendChild(this._symbolKnoten("mdi:radiator"));
    const beschriftung = document.createElement("div");
    beschriftung.innerHTML =
      '<div class="marke">HeatNexus</div><div class="unterzeile"></div>';
    beschriftung.querySelector(".unterzeile").textContent = anlage.name
      ? `Heizungsübersicht · ${anlage.name}`
      : "Heizungsübersicht";
    kopf.appendChild(beschriftung);
    karte.appendChild(kopf);

    const abzeichen = document.createElement("div");
    abzeichen.className = "abzeichen";
    abzeichen.appendChild(this._symbolKnoten("mdi:check-circle-outline"));
    const abzeichenText = document.createElement("span");
    abzeichen.appendChild(abzeichenText);
    karte.appendChild(abzeichen);
    this._bindungen.push(() => {
      const stoerung = this._stoerung(anlage);
      abzeichen.classList.toggle("stoerung", stoerung);
      abzeichenText.textContent = stoerung ? "Störung anliegend" : "Anlage in Ordnung";
      abzeichen.firstChild.setAttribute(
        "icon",
        stoerung ? "mdi:alert-circle-outline" : "mdi:check-circle-outline"
      );
    });

    const liste = document.createElement("div");
    liste.style.marginTop = "16px";
    (anlage.kennwerte || []).forEach((kennwert) => {
      liste.appendChild(
        this._wertzeile(kennwert.entity, kennwert.titel, kennwert.untertitel, kennwert.symbol)
      );
    });
    karte.appendChild(liste);
    return karte;
  }

  _wertzeile(entity, titel, unter, symbol) {
    const zeile = document.createElement("div");
    zeile.className = "zeile";
    if (symbol) zeile.appendChild(this._symbolKnoten(symbol));
    const text = document.createElement("div");
    text.className = "text";
    const oben = document.createElement("div");
    oben.className = "titel";
    oben.textContent = titel;
    const unten = document.createElement("div");
    unten.className = "unter";
    unten.textContent = unter || "";
    text.append(oben, unten);
    const wert = document.createElement("div");
    wert.className = "wert";
    zeile.append(text, wert);
    this._bindungen.push(() => {
      wert.textContent = this._text(entity);
      wert.classList.toggle("klein", wert.textContent.length > 8);
    });
    return this._klickbar(zeile, entity);
  }

  // -------------------------------------------------------------------
  // Schaubild
  // -------------------------------------------------------------------
  _schaubild(anlage) {
    if (!anlage.schema) return null;
    const karte = this._karte("Anlagenübersicht");
    const huelle = document.createElement("div");
    huelle.className = "schaubild";
    const bild = document.createElement("img");
    bild.src = anlage.schema;
    bild.alt = "Anlagenschaubild";
    huelle.appendChild(bild);

    (anlage.schema_werte || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "marke-wert";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      huelle.appendChild(this._klickbar(marke, eintrag.entity));
      this._bindungen.push(() => {
        marke.textContent = this._text(eintrag.entity);
      });
    });

    karte.appendChild(huelle);
    return karte;
  }

  // -------------------------------------------------------------------
  // Heizkreise und Warmwasser
  // -------------------------------------------------------------------
  _kreiseUndWasser(anlage) {
    const kreise = anlage.heizkreise || [];
    const wasser = anlage.warmwasser || [];
    if (!kreise.length && !wasser.length) return null;

    const doppel = document.createElement("div");
    doppel.className = "doppel";

    const linkeKarte = this._karte("Heizkreise");
    if (!kreise.length) {
      const hinweis = document.createElement("div");
      hinweis.className = "hinweis";
      hinweis.textContent = "Kein Heizkreis gefunden.";
      linkeKarte.appendChild(hinweis);
    }
    kreise.forEach((kreis) => {
      const zeile = document.createElement("div");
      zeile.className = "zeile";
      zeile.appendChild(this._symbolKnoten("mdi:home-thermometer-outline"));
      const text = document.createElement("div");
      text.className = "text";
      const oben = document.createElement("div");
      oben.className = "titel";
      oben.textContent = kreis.titel;
      const unten = document.createElement("div");
      unten.className = "unter";
      text.append(oben, unten);
      const wert = document.createElement("div");
      wert.className = "wert";
      zeile.append(text, wert);
      this._bindungen.push(() => {
        const zustand = this._zustand(kreis.entity);
        if (!zustand) {
          wert.textContent = "–";
          return;
        }
        const ist = zustand.attributes.current_temperature;
        const soll = zustand.attributes.temperature;
        wert.textContent = ist !== undefined && ist !== null ? `${ist} °C` : "–";
        const teile = [];
        if (zustand.attributes.preset_mode) {
          teile.push(this._presetName(zustand));
        }
        if (soll !== undefined && soll !== null) teile.push(`Soll ${soll} °C`);
        unten.textContent = teile.join(" · ");
      });
      linkeKarte.appendChild(this._klickbar(zeile, kreis.entity));
    });

    const rechteKarte = this._karte("Warmwasser");
    if (!wasser.length) {
      const hinweis = document.createElement("div");
      hinweis.className = "hinweis";
      hinweis.textContent = "Kein Warmwasserkreis gefunden.";
      rechteKarte.appendChild(hinweis);
    }
    wasser.forEach((eintrag) => {
      rechteKarte.appendChild(this._statuszeile(eintrag.entity, eintrag.titel));
    });

    doppel.append(linkeKarte, rechteKarte);
    return doppel;
  }

  _presetName(zustand) {
    // Die Betriebsarten heißen am Gerät "0".."7"; die Klartexte liefert die
    // Übersetzung der Integration mit.
    if (this._hass.formatEntityAttributeValue) {
      return this._hass.formatEntityAttributeValue(zustand, "preset_mode");
    }
    return zustand.attributes.preset_mode;
  }

  // -------------------------------------------------------------------
  // Systemstatus und Störungen
  // -------------------------------------------------------------------
  _statuszeile(entity, titel, symbol) {
    const zeile = document.createElement("div");
    zeile.className = "status-zeile";
    if (symbol) zeile.appendChild(this._symbolKnoten(symbol));
    const links = document.createElement("div");
    links.className = "titel";
    links.textContent = titel;
    const wert = document.createElement("div");
    wert.className = "wert";
    zeile.append(links, wert);
    this._bindungen.push(() => {
      wert.textContent = this._text(entity);
    });
    return this._klickbar(zeile, entity);
  }

  _status(anlage) {
    const huelle = document.createElement("div");

    const karte = this._karte("Systemstatus");
    (anlage.status || []).forEach((eintrag) => {
      karte.appendChild(this._statuszeile(eintrag.entity, eintrag.titel, eintrag.symbol));
    });
    if (!(anlage.status || []).length) {
      const hinweis = document.createElement("div");
      hinweis.className = "hinweis";
      hinweis.textContent = "Keine Statuswerte gefunden.";
      karte.appendChild(hinweis);
    }
    huelle.appendChild(karte);

    const stoerungskarte = this._karte("Störungen");
    const zusammenfassung = document.createElement("div");
    zusammenfassung.className = "hinweis";
    stoerungskarte.appendChild(zusammenfassung);
    (anlage.stoerungen || []).forEach((eintrag) => {
      const zeile = document.createElement("div");
      zeile.className = "status-zeile";
      const links = document.createElement("div");
      links.className = "titel";
      const wert = document.createElement("div");
      wert.className = "wert";
      zeile.append(links, wert);
      stoerungskarte.appendChild(this._klickbar(zeile, eintrag.entity));
      this._bindungen.push(() => {
        links.textContent = this._name(eintrag.entity).replace(" Meldung Klartext", "");
        const zustand = this._zustand(eintrag.entity);
        const aktiv = zustand && zustand.attributes.stoerung_aktiv === true;
        wert.textContent = this._text(eintrag.entity);
        wert.className = `wert ${aktiv ? "schlecht" : "gut"}`;
        zeile.style.display = "flex";
      });
    });
    this._bindungen.push(() => {
      zusammenfassung.textContent = this._stoerung(anlage)
        ? "Es liegt mindestens eine Störung an."
        : "Keine Störung. Alles läuft.";
    });
    huelle.appendChild(stoerungskarte);
    return huelle;
  }

  // -------------------------------------------------------------------
  // Verlauf
  // -------------------------------------------------------------------
  _verlauf(anlage) {
    if (!(anlage.verlauf || []).length) return null;
    const karte = this._karte("Verlauf (24 Stunden)");
    const platz = document.createElement("div");
    platz.dataset.verlauf = "1";
    platz.dataset.entities = JSON.stringify(anlage.verlauf);
    karte.appendChild(platz);
    return karte;
  }

  async _verlaufKarteLaden(anlagen) {
    const plaetze = this.shadowRoot.querySelectorAll("[data-verlauf]");
    if (!plaetze.length || !window.loadCardHelpers) return;
    const helfer = await window.loadCardHelpers();
    this._verlaufskarten = [];
    plaetze.forEach((platz) => {
      const karte = helfer.createCardElement({
        type: "history-graph",
        hours_to_show: 24,
        entities: JSON.parse(platz.dataset.entities),
      });
      karte.hass = this._hass;
      platz.replaceChildren(karte);
      this._verlaufskarten.push(karte);
    });
  }

  // -------------------------------------------------------------------
  // Schnellzugriff
  // -------------------------------------------------------------------
  _schnellzugriff(anlage) {
    const eintraege = anlage.schnellzugriff || [];
    if (!eintraege.length) return null;
    const karte = this._karte("Schnellzugriff");
    const gitter = document.createElement("div");
    gitter.className = "gitter";

    eintraege.forEach((eintrag) => {
      const bereich = eintrag.entity.split(".")[0];
      if (bereich === "select") {
        const huelle = document.createElement("div");
        huelle.style.gridColumn = "1 / -1";
        const beschriftung = document.createElement("div");
        beschriftung.className = "unter";
        beschriftung.textContent = eintrag.titel;
        beschriftung.style.marginBottom = "6px";
        const auswahl = document.createElement("select");
        const rueckmeldung = document.createElement("div");
        rueckmeldung.className = "rueckmeldung";
        auswahl.addEventListener("change", async () => {
          const gewaehlt = auswahl.value;
          if (eintrag.frage && !(await this._bestaetigen(eintrag.titel, eintrag.frage))) {
            const zustand = this._zustand(eintrag.entity);
            if (zustand) auswahl.value = zustand.state;
            return;
          }
          await this._uebertragen(rueckmeldung, () =>
            this._hass.callService("select", "select_option", {
              entity_id: eintrag.entity,
              option: gewaehlt,
            })
          );
        });
        huelle.append(beschriftung, auswahl, rueckmeldung);
        gitter.appendChild(huelle);
        this._bindungen.push(() => {
          const zustand = this._zustand(eintrag.entity);
          const optionen = (zustand && zustand.attributes.options) || [];
          if (auswahl.dataset.optionen !== optionen.join("|")) {
            auswahl.dataset.optionen = optionen.join("|");
            auswahl.replaceChildren(
              ...optionen.map((option) => {
                const knoten = document.createElement("option");
                knoten.value = option;
                knoten.textContent = option;
                return knoten;
              })
            );
          }
          if (zustand) auswahl.value = zustand.state;
        });
        return;
      }

      const taste = document.createElement("button");
      taste.className = "taste";
      taste.type = "button";
      taste.appendChild(this._symbolKnoten(eintrag.symbol));
      const beschriftung = document.createElement("div");
      beschriftung.className = "beschriftung";
      beschriftung.textContent = eintrag.titel;
      const rueckmeldung = document.createElement("div");
      rueckmeldung.className = "rueckmeldung";
      taste.append(beschriftung, rueckmeldung);
      taste.addEventListener("click", async () => {
        if (taste.disabled) return;
        if (eintrag.frage && !(await this._bestaetigen(eintrag.titel, eintrag.frage))) return;
        taste.disabled = true;
        try {
          await this._uebertragen(rueckmeldung, () =>
            bereich === "button"
              ? this._hass.callService("button", "press", { entity_id: eintrag.entity })
              : this._hass.callService("homeassistant", "toggle", { entity_id: eintrag.entity })
          );
        } finally {
          taste.disabled = false;
        }
      });
      gitter.appendChild(taste);
      this._bindungen.push(() => {
        const zustand = this._zustand(eintrag.entity);
        const laeuft = !!zustand && zustand.state === "on";
        taste.classList.toggle("an", laeuft);
        // Solange eine Übertragung läuft, gehört die Zeile der Rückmeldung.
        if (rueckmeldung.dataset.belegt === "1") return;
        rueckmeldung.className = "rueckmeldung";
        rueckmeldung.textContent = this._tastenZustand(bereich, zustand, laeuft);
      });
    });

    karte.appendChild(gitter);
    return karte;
  }

  // -------------------------------------------------------------------
  // Bedienen: nachfragen, übertragen, zurückmelden
  // -------------------------------------------------------------------

  /**
   * Rückfrage vor einem Eingriff, der die Anlage wirklich etwas kostet.
   *
   * Bewusst ein eigener Dialog statt `window.confirm`: Der blockiert den
   * Browser und sieht in Home Assistant wie ein Fremdkörper aus.
   */
  _bestaetigen(titel, frage) {
    return new Promise((antworten) => {
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog";
      dialog.setAttribute("role", "alertdialog");

      const ueberschrift = document.createElement("h3");
      ueberschrift.className = "dialog-titel";
      ueberschrift.textContent = titel;
      const text = document.createElement("div");
      text.className = "dialog-text";
      text.textContent = frage;

      const leiste = document.createElement("div");
      leiste.className = "dialog-leiste";
      const abbrechen = document.createElement("button");
      abbrechen.type = "button";
      abbrechen.className = "dialog-taste";
      abbrechen.textContent = "Abbrechen";
      const ausloesen = document.createElement("button");
      ausloesen.type = "button";
      ausloesen.className = "dialog-taste betont";
      ausloesen.textContent = "Ja, ausführen";
      leiste.append(abbrechen, ausloesen);

      dialog.append(ueberschrift, text, leiste);
      schleier.appendChild(dialog);

      const schliessen = (antwort) => {
        schleier.remove();
        document.removeEventListener("keydown", beiTaste);
        antworten(antwort);
      };
      const beiTaste = (ereignis) => {
        if (ereignis.key === "Escape") schliessen(false);
      };
      abbrechen.addEventListener("click", () => schliessen(false));
      ausloesen.addEventListener("click", () => schliessen(true));
      schleier.addEventListener("click", (ereignis) => {
        if (ereignis.target === schleier) schliessen(false);
      });
      document.addEventListener("keydown", beiTaste);

      this.shadowRoot.appendChild(schleier);
      ausloesen.focus();
    });
  }

  /**
   * Einen Dienstaufruf ausführen und den Verlauf sichtbar machen.
   *
   * Die Anlage wird nur alle 30 s abgefragt; ohne Rückmeldung drückt man und
   * nichts passiert. Deshalb: „wird übertragen" während des Aufrufs, danach
   * kurz „übertragen" oder der Fehlertext.
   */
  async _uebertragen(anzeige, aufruf) {
    anzeige.dataset.belegt = "1";
    anzeige.className = "rueckmeldung laeuft";
    anzeige.textContent = "wird übertragen …";
    try {
      await aufruf();
      anzeige.className = "rueckmeldung erfolg";
      anzeige.textContent = "übertragen ✓";
    } catch (err) {
      anzeige.className = "rueckmeldung fehler";
      anzeige.textContent = "nicht übernommen";
      console.warn("HeatNexus: Befehl abgelehnt", err);
    }
    window.setTimeout(() => {
      delete anzeige.dataset.belegt;
      this._aktualisieren();
    }, RUECKMELDUNG_MS);
  }

  /** Was unter einer Taste steht, wenn gerade nichts übertragen wird. */
  _tastenZustand(bereich, zustand, laeuft) {
    if (!zustand) return "";
    if (bereich === "button") {
      const zeitpunkt = new Date(zustand.state);
      if (Number.isNaN(zeitpunkt.getTime())) return "noch nie ausgelöst";
      return `zuletzt ${zeitpunkt.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      })}`;
    }
    return laeuft ? "läuft" : "aus";
  }

  // -------------------------------------------------------------------
  _aktualisieren() {
    this._bindungen.forEach((binden) => binden());
    (this._verlaufskarten || []).forEach((karte) => {
      karte.hass = this._hass;
    });
  }
}

if (!customElements.get("heatnexus-panel")) {
  customElements.define("heatnexus-panel", HeatNexusPanel);
}
