/**
 * Selbst gewählte Anordnung der Karten.
 *
 * Raster, Ziehen, Breite, Spaltenzahl, Verstecktes und das Sichern der Wahl.
 * Der größte zusammenhängende Block der Oberfläche und der einzige, der die
 * Karten nur verwaltet, statt welche zu bauen.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import { BREITE_MAX, REITER, SPEICHERN_MS, ordnungAnwenden, reihenfolgeMischen } from "../ordnung.js";

export const AnordnenMixin = (Basis) =>
  class extends Basis {
  // -------------------------------------------------------------------
  // Anordnung: Reihenfolge, Breite, Spaltenzahl, Verstecktes
  // -------------------------------------------------------------------
  /** Die gespeicherte Anordnung des aktuellen Reiters. */
  _reiterAnordnung() {
    return (this._anordnung && this._anordnung[this._reiter]) || {};
  }

  /**
   * Aus Kartenbeschreibungen das Raster bauen.
   *
   * Karten ohne Knoten gibt es an dieser Anlage nicht; sie fallen weg, bevor
   * die Reihenfolge gebildet wird. Damit verschiebt eine Anlage ohne
   * Warmwasser nichts, und die gespeicherte Reihenfolge bleibt für beide
   * Anlagen dieselbe.
   */
  _raster(anlage, karten, leerText) {
    const raster = document.createElement("div");
    raster.className = "raster";

    // Die Kennung trägt die Anlage vorneweg. Ohne sie teilten sich Heizhaus
    // und Wohnhaus dieselbe „schnellzugriff"-Karte: Wer im Heizhaus schob,
    // schob im Wohnhaus mit.
    const vorwahl = `${(anlage && anlage.id) || anlage.name || ""}|`;
    const vorhanden = (karten || [])
      .filter((karte) => karte && karte.knoten)
      .map((karte) => ({ ...karte, id: vorwahl + karte.id }));
    const anordnung = this._reiterAnordnung();
    const spalten = Number(anordnung.spalten) || 0;
    if (spalten > 0) {
      raster.style.setProperty("--raster-spalten", `repeat(${spalten}, minmax(0, 1fr))`);
    }
    const versteckt = new Set(anordnung.versteckt || []);
    const breiten = anordnung.breite || {};

    const reihenfolge = ordnungAnwenden(
      vorhanden.map((karte) => karte.id),
      anordnung.ordnung || []
    );
    const jeKennung = new Map(vorhanden.map((karte) => [karte.id, karte]));

    reihenfolge.forEach((kennung) => {
      const karte = jeKennung.get(kennung);
      if (!karte) return;
      const istVersteckt = versteckt.has(kennung);
      if (istVersteckt && !this._anordnen) return;
      const breite = Math.max(1, Math.min(BREITE_MAX, breiten[kennung] || karte.breite || 1));
      const knoten = this._anordnen
        ? this._anordner(karte, breite, istVersteckt, reihenfolge)
        : karte.knoten;
      knoten.style.setProperty("--breite", String(breite));
      raster.appendChild(knoten);
    });

    if (!raster.childElementCount) {
      const leer = this._karte("HeatNexus");
      leer.appendChild(this._hinweisKnoten(leerText));
      raster.appendChild(leer);
    }
    return raster;
  }

  /**
   * Eine Karte im Anordnen-Modus: Griffleiste oben, Karte darunter.
   *
   * Gezogen wird mit der Maus, verschoben auch mit den Pfeiltasten – am
   * Tablet vor dem Kessel ist Ziehen unzuverlässig, und ohne Tasten käme man
   * mit der Tastatur gar nicht weiter.
   */
  _anordner(karte, breite, istVersteckt, reihenfolge) {
    const huelle = document.createElement("div");
    huelle.className = istVersteckt ? "anordner versteckt" : "anordner";
    huelle.dataset.kennung = karte.id;

    const griff = document.createElement("div");
    griff.className = "anordner-griff";
    griff.appendChild(this._symbolKnoten("mdi:drag"));

    const name = document.createElement("div");
    name.className = "name";
    name.textContent = karte.titel || karte.id;
    griff.appendChild(name);

    const platz = reihenfolge.indexOf(karte.id);
    griff.appendChild(
      this._griffTaste("mdi:chevron-left", "Nach vorn", platz <= 0, () =>
        this._verschieben(karte.id, -1)
      )
    );
    griff.appendChild(
      this._griffTaste(
        "mdi:chevron-right",
        "Nach hinten",
        platz < 0 || platz >= reihenfolge.length - 1,
        () => this._verschieben(karte.id, 1)
      )
    );

    // Breite: schmaler, Anzeige, breiter. Vorher lief eine einzige Taste im
    // Kreis – wer einmal zu weit klickte, musste bis 4× durch und wieder von
    // vorn.
    const grenze = Math.min(Number(this._reiterAnordnung().spalten) || BREITE_MAX, BREITE_MAX);
    griff.appendChild(
      this._griffTaste("mdi:minus", "Schmaler", breite <= 1, () =>
        this._breiteAendern(karte.id, breite - 1)
      )
    );
    const breitenwert = document.createElement("div");
    breitenwert.className = "breite";
    breitenwert.textContent = `${breite}×`;
    breitenwert.title = "Breite in Spalten";
    griff.appendChild(breitenwert);
    griff.appendChild(
      this._griffTaste("mdi:plus", "Breiter", breite >= grenze, () =>
        this._breiteAendern(karte.id, breite + 1)
      )
    );

    griff.appendChild(
      this._griffTaste(
        istVersteckt ? "mdi:eye-off-outline" : "mdi:eye-outline",
        istVersteckt ? "Wieder einblenden" : "Ausblenden",
        false,
        () => this._sichtbarkeitUmschalten(karte.id)
      )
    );

    huelle.append(griff, karte.knoten);
    this._ziehenVerdrahten(huelle, griff, karte.id);
    return huelle;
  }

  _griffTaste(symbol, beschriftung, gesperrt, beiKlick) {
    const taste = document.createElement("button");
    taste.type = "button";
    taste.title = beschriftung;
    taste.setAttribute("aria-label", beschriftung);
    taste.disabled = !!gesperrt;
    taste.appendChild(this._symbolKnoten(symbol));
    taste.addEventListener("click", beiKlick);
    return taste;
  }

  /** Ziehen und Ablegen: der schnelle Weg für die Maus. */
  _ziehenVerdrahten(huelle, griff, kennung) {
    huelle.draggable = true;
    // Nur am Griff anfassen: Sonst startete jeder Klick in der Karte – etwa
    // auf ein Auswahlfeld – einen Ziehvorgang.
    huelle.addEventListener("dragstart", (ereignis) => {
      if (!griff.contains(ereignis.target) && ereignis.target !== huelle) {
        ereignis.preventDefault();
        return;
      }
      this._gezogen = kennung;
      huelle.classList.add("gezogen");
      ereignis.dataTransfer.effectAllowed = "move";
      // Firefox startet ohne gesetzte Nutzlast gar nicht erst.
      ereignis.dataTransfer.setData("text/plain", kennung);
    });
    huelle.addEventListener("dragend", () => {
      this._gezogen = null;
      huelle.classList.remove("gezogen");
    });
    huelle.addEventListener("dragover", (ereignis) => {
      if (!this._gezogen || this._gezogen === kennung) return;
      ereignis.preventDefault();
      ereignis.dataTransfer.dropEffect = "move";
      const feld = huelle.getBoundingClientRect();
      const davor = ereignis.clientX < feld.left + feld.width / 2;
      huelle.classList.toggle("ziel-vor", davor);
      huelle.classList.toggle("ziel-nach", !davor);
    });
    huelle.addEventListener("dragleave", () => {
      huelle.classList.remove("ziel-vor", "ziel-nach");
    });
    huelle.addEventListener("drop", (ereignis) => {
      ereignis.preventDefault();
      const davor = huelle.classList.contains("ziel-vor");
      huelle.classList.remove("ziel-vor", "ziel-nach");
      const gezogen = this._gezogen;
      this._gezogen = null;
      if (gezogen && gezogen !== kennung) this._ablegen(gezogen, kennung, davor);
    });
  }

  /** Eine Karte vor oder hinter eine andere setzen. */
  _ablegen(kennung, ziel, davor) {
    this._ordnungAendern((reihenfolge) => {
      const ohne = reihenfolge.filter((eintrag) => eintrag !== kennung);
      const stelle = ohne.indexOf(ziel);
      if (stelle < 0) return reihenfolge;
      ohne.splice(davor ? stelle : stelle + 1, 0, kennung);
      return ohne;
    });
  }

  /** Eine Karte um einen Platz verschieben. */
  _verschieben(kennung, richtung) {
    this._ordnungAendern((reihenfolge) => {
      const stelle = reihenfolge.indexOf(kennung);
      const ziel = stelle + richtung;
      if (stelle < 0 || ziel < 0 || ziel >= reihenfolge.length) return reihenfolge;
      const neu = [...reihenfolge];
      neu.splice(ziel, 0, neu.splice(stelle, 1)[0]);
      return neu;
    });
  }

  /**
   * Die Reihenfolge ändern.
   *
   * Die sichtbaren Karten bestimmen die neue Reihenfolge, aber sie sind nicht
   * alles: Unter „Alle" zeigt der Reiter nur die Karten *einer* Anlage, und
   * die Kennungen der anderen dürfen dabei nicht aus dem Speicher fallen. Was
   * gerade nicht auf dem Bildschirm steht, wird deshalb wieder eingefügt –
   * dort, wo es vorher stand.
   */
  _ordnungAendern(aenderung) {
    const anordnung = this._reiterAnordnung();
    const sichtbar = this._sichtbareKennungen();
    const alt = anordnung.ordnung || [];
    const neu = aenderung(ordnungAnwenden(sichtbar, alt));
    this._anordnungSetzen({ ...anordnung, ordnung: reihenfolgeMischen(neu, alt) });
  }

  /**
   * Die Kennungen der Karten, die dieser Reiter gerade zeigt.
   *
   * Unter „Alle" steht jede Kartenart einmal je Anlage auf dem Bildschirm –
   * „Kessel" also zweimal. Die Reihenfolge gilt aber für alle Anlagen
   * gemeinsam, deshalb zählt jede Kennung nur einmal.
   */
  _sichtbareKennungen() {
    const kennungen = [];
    this.shadowRoot.querySelectorAll(".anordner[data-kennung]").forEach((knoten) => {
      if (!kennungen.includes(knoten.dataset.kennung)) kennungen.push(knoten.dataset.kennung);
    });
    return kennungen;
  }

  _breiteAendern(kennung, breite) {
    const anordnung = this._reiterAnordnung();
    const grenze = Math.min(Number(anordnung.spalten) || BREITE_MAX, BREITE_MAX);
    const neu = Math.max(1, Math.min(grenze, breite));
    this._anordnungSetzen({
      ...anordnung,
      breite: { ...(anordnung.breite || {}), [kennung]: neu },
    });
  }

  _sichtbarkeitUmschalten(kennung) {
    const anordnung = this._reiterAnordnung();
    const versteckt = new Set(anordnung.versteckt || []);
    if (versteckt.has(kennung)) versteckt.delete(kennung);
    else versteckt.add(kennung);
    this._anordnungSetzen({ ...anordnung, versteckt: [...versteckt] });
  }

  _spaltenSetzen(spalten) {
    this._anordnungSetzen({ ...this._reiterAnordnung(), spalten });
  }

  /** Eine geänderte Anordnung übernehmen, anzeigen und sichern. */
  _anordnungSetzen(anordnung) {
    const reiter = this._reiter;
    this._anordnung = { ...this._anordnung, [reiter]: anordnung };
    this._gebaut = false;
    this._zeichnen();
    this._anordnungSichern(reiter, anordnung);
  }

  /**
   * Die Anordnung speichern – gesammelt, nicht bei jedem Klick.
   *
   * Beim Ziehen entstehen mehrere Änderungen kurz hintereinander; jede
   * einzeln zu schreiben hieße, die Platte für dieselbe Liste mehrfach
   * anzufassen.
   */
  _anordnungSichern(reiter, anordnung) {
    if (this._speicherAuftrag) clearTimeout(this._speicherAuftrag);
    this._speicherAuftrag = setTimeout(async () => {
      this._speicherAuftrag = null;
      try {
        await this._hass.callWS({
          type: "heatnexus/anordnung/setzen",
          reiter,
          anordnung,
        });
      } catch (err) {
        console.warn("HeatNexus: Anordnung konnte nicht gespeichert werden", err);
      }
    }, SPEICHERN_MS);
  }

  _anordnenUmschalten() {
    this._anordnen = !this._anordnen;
    this._gebaut = false;
    this._zeichnen();
  }

  /** Die Leiste, die im Anordnen-Modus über dem Raster steht. */
  _anordnenLeiste() {
    const leiste = document.createElement("div");
    leiste.className = "anordnen-leiste";

    const titel = document.createElement("div");
    titel.className = "titel";
    titel.textContent = "Anordnen";
    leiste.appendChild(titel);

    const hinweis = document.createElement("div");
    hinweis.className = "hinweis";
    hinweis.textContent =
      "Karten am Griff ziehen oder mit den Pfeilen verschieben. Die Anordnung gilt " +
      "nur für dich und nur für diesen Reiter.";
    leiste.appendChild(hinweis);

    const wahl = document.createElement("div");
    wahl.className = "spaltenwahl";
    wahl.setAttribute("role", "group");
    wahl.setAttribute("aria-label", "Spaltenzahl");
    const jetzt = Number(this._reiterAnordnung().spalten) || 0;
    [
      { wert: 0, name: "Auto" },
      { wert: 1, name: "1" },
      { wert: 2, name: "2" },
      { wert: 3, name: "3" },
      { wert: 4, name: "4" },
    ].forEach(({ wert, name }) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.textContent = name;
      taste.title = wert === 0 ? "So viele Spalten, wie nebeneinander passen" : `${name} Spalten`;
      taste.setAttribute("aria-pressed", String(wert === jetzt));
      taste.addEventListener("click", () => this._spaltenSetzen(wert));
      wahl.appendChild(taste);
    });
    leiste.appendChild(wahl);

    const fertig = document.createElement("button");
    fertig.type = "button";
    fertig.className = "anordnen-taste fertig";
    fertig.appendChild(this._symbolKnoten("mdi:check"));
    const fertigText = document.createElement("span");
    fertigText.textContent = "Fertig";
    fertig.appendChild(fertigText);
    fertig.addEventListener("click", () => this._anordnenUmschalten());
    leiste.appendChild(fertig);

    // Das Zurücksetzen steckt hinter dem Menü und hinter einer Rückfrage.
    // Als Taste in der Leiste läge es neben „Fertig" – und ein Fehlgriff
    // dort wirft eine ganze Anordnung weg, die niemand wiederherstellen kann.
    const mehr = document.createElement("button");
    mehr.type = "button";
    mehr.className = "anordnen-taste";
    mehr.title = "Weitere Möglichkeiten";
    mehr.setAttribute("aria-label", "Weitere Möglichkeiten");
    mehr.appendChild(this._symbolKnoten("mdi:dots-vertical"));
    mehr.addEventListener("click", () => this._anordnenMenue());
    leiste.appendChild(mehr);

    return leiste;
  }

  /** Das Menü hinter „⋮": nur das Zurücksetzen, jeweils mit Rückfrage. */
  _anordnenMenue() {
    const reiterName = (REITER.find((r) => r.schluessel === this._reiter) || {}).titel || "Reiter";
    this._menueDialog("Anordnung zurücksetzen", [
      {
        titel: `Nur „${reiterName}" zurücksetzen`,
        symbol: "mdi:restore",
        frage: `Die eigene Anordnung des Reiters „${reiterName}" verwerfen und zur Standardanordnung zurückgehen?`,
        tun: () => this._zuruecksetzen(this._reiter),
      },
      {
        titel: "Alle Reiter zurücksetzen",
        symbol: "mdi:restore-alert",
        frage:
          "Die eigene Anordnung aller vier Reiter verwerfen? Reihenfolge, " +
          "Breiten, ausgeblendete Karten und Spaltenzahl gehen dabei verloren.",
        tun: () => this._zuruecksetzen(null),
      },
    ]);
  }

  async _zuruecksetzen(reiter) {
    if (this._speicherAuftrag) {
      clearTimeout(this._speicherAuftrag);
      this._speicherAuftrag = null;
    }
    if (reiter) {
      const rest = { ...this._anordnung };
      delete rest[reiter];
      this._anordnung = rest;
    } else {
      this._anordnung = {};
    }
    this._gebaut = false;
    this._zeichnen();
    try {
      await this._hass.callWS({
        type: "heatnexus/anordnung/zuruecksetzen",
        ...(reiter ? { reiter } : {}),
      });
    } catch (err) {
      console.warn("HeatNexus: Anordnung konnte nicht zurückgesetzt werden", err);
    }
  }

  /**
   * Ein kleines Menüfenster; jeder Eintrag stellt vor der Tat seine Rückfrage.
   *
   * Bewusst dieselben Klassen wie die übrigen Fenster – und bewusst nicht
   * `window.confirm`: Der blockiert den Browser und sieht in Home Assistant
   * wie ein Fremdkörper aus.
   */
  _menueDialog(titel, eintraege) {
    const schleier = document.createElement("div");
    schleier.className = "schleier";
    const dialog = document.createElement("div");
    dialog.className = "dialog";

    const ueberschrift = document.createElement("h3");
    ueberschrift.className = "dialog-titel";
    ueberschrift.textContent = titel;
    dialog.appendChild(ueberschrift);

    const weg = () => {
      schleier.remove();
      document.removeEventListener("keydown", beiTaste);
    };
    const beiTaste = (ereignis) => {
      if (ereignis.key === "Escape") weg();
    };

    eintraege.forEach((eintrag) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "anordnen-taste";
      taste.style.width = "100%";
      taste.style.marginTop = "10px";
      taste.appendChild(this._symbolKnoten(eintrag.symbol));
      const text = document.createElement("span");
      text.textContent = eintrag.titel;
      taste.appendChild(text);
      taste.addEventListener("click", async () => {
        // Zweiter Schritt: erst die Rückfrage, dann die Tat.
        if (!(await this._bestaetigen(eintrag.titel, eintrag.frage))) return;
        weg();
        eintrag.tun();
      });
      dialog.appendChild(taste);
    });

    const leiste = document.createElement("div");
    leiste.className = "dialog-leiste";
    const schliessen = document.createElement("button");
    schliessen.type = "button";
    schliessen.className = "dialog-taste";
    schliessen.textContent = "Schließen";
    schliessen.addEventListener("click", weg);
    leiste.appendChild(schliessen);
    dialog.appendChild(leiste);

    schleier.appendChild(dialog);
    schleier.addEventListener("click", (ereignis) => {
      if (ereignis.target === schleier) weg();
    });
    document.addEventListener("keydown", beiTaste);
    this.shadowRoot.appendChild(schleier);
  }
  };
