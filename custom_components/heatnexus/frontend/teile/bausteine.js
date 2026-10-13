/**
 * Die Bausteine, aus denen jede Karte besteht.
 *
 * Karte, Klappkarte, Symbol, Hinweis und das „?“ mit seinem Erklärfenster.
 * Sie tragen kein Wissen über die Anlage – deshalb stehen sie für sich und
 * nicht zwischen den Karten, die sie benutzen.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

// Diese Methoden laufen immer am Element selbst, auch aus der Sicht einer Anlage heraus:
// Sie zeichnen die ganze Fläche oder wählen die Sprache selbst.
const AM_ELEMENT = new Set(["_zeichnen", "_aufbauen", "_aktualisieren", "_sicht", "_inSprache"]);

export const BausteineMixin = (Basis) =>
  class extends Basis {
  /**
   * Ein Text in der eingestellten Sprache.
   *
   * Der deutsche Text ist der Schlüssel; ohne Eintrag bleibt er stehen. Das
   * Wörterbuch kommt vom Server (`texte.py`), hier wird nichts übersetzt.
   */
  _t(text) {
    return (this._texte && this._texte[text]) || text;
  }

  /** Übersetzen und Platzhalter wie `{von}` einsetzen. */
  _tMit(text, werte) {
    return Object.entries(werte).reduce(
      (satz, [schluessel, wert]) => satz.split(`{${schluessel}}`).join(String(wert)),
      this._t(text)
    );
  }

  /** Ob überhaupt etwas zu übersetzen ist. */
  get _uebersetzt() {
    return Boolean(this._texte && Object.keys(this._texte).length);
  }

  /**
   * Dieselbe Oberfläche mit dem Wörterbuch einer Anlage, die eine eigene Sprache spricht.
   * Was über die Sicht entsteht, hält sie fest: Bindungen, Klicks und Rückfragen übersetzen
   * später mit demselben Wörterbuch. Zustand und eingebaute Methoden bleiben am Element.
   */
  _sicht(anlage) {
    const texte = anlage && anlage.texte;
    if (!texte) return this;
    if (!this._sichten) this._sichten = new WeakMap();
    if (!this._sichten.has(anlage)) {
      const sicht = new Proxy(this, {
        get(ziel, name) {
          if (name === "_texte") return texte;
          const amElement = AM_ELEMENT.has(name) || name in HTMLElement.prototype;
          const wert = Reflect.get(ziel, name, amElement ? ziel : sicht);
          return amElement && typeof wert === "function" ? wert.bind(ziel) : wert;
        },
        set: (ziel, name, wert) => Reflect.set(ziel, name, wert, ziel),
      });
      this._sichten.set(anlage, sicht);
    }
    return this._sichten.get(anlage);
  }

  /** Einen Teil der Anlage in ihrer Sprache bauen; `lang` hält den Rahmen davon fern. */
  _inSprache(anlage, bauen) {
    const sicht = this._sicht(anlage);
    const knoten = bauen(sicht);
    if (sicht !== this && knoten) {
      sicht._uebersetzen(knoten);
      knoten.setAttribute("lang", anlage.sprache || "");
    }
    return knoten;
  }

  /**
   * Den fertigen Baum in die eingestellte Sprache bringen.
   *
   * Fängt, was beim Aufbau entsteht; später gesetzte Texte gehen einzeln
   * durch `_t`. Auf Deutsch kehrt die Methode sofort zurück.
   */
  _uebersetzen(wurzel) {
    if (!wurzel || !this._uebersetzt) return;
    const merkmale = ["title", "aria-label", "placeholder"];
    const gehe = (knoten) => {
      // Das Stylesheet ist ein Textknoten von zigtausend Zeichen und trägt
      // nichts zum Lesen bei.
      if (knoten.tagName === "STYLE" || knoten.tagName === "SCRIPT") return;
      // Namen aus der Anlage (`data-roh`) bleiben, wie sie sind.
      if (knoten.dataset && knoten.dataset.roh !== undefined) return;
      // Ein Teil mit eigener Sprache ist schon übersetzt.
      if (knoten !== wurzel && knoten.getAttribute && knoten.getAttribute("lang")) return;
      if (knoten.getAttribute) {
        merkmale.forEach((merkmal) => {
          const wert = knoten.getAttribute(merkmal);
          const ersatz = wert && this._t(wert);
          if (ersatz && ersatz !== wert) knoten.setAttribute(merkmal, ersatz);
        });
      }
      // Ein Knoten ohne Kinder trägt seinen Text selbst.
      const kinder = knoten.childNodes;
      if (!kinder || !kinder.length) {
        // Geschrieben wird nur bei einem Treffer: Sonst ginge der Abstand
        // um den Text verloren, den `trim` hier abschneidet.
        // Zwei Zeichen sind kein Wort: Wochentagskürzel setzen ihre Erbauer
        // selbst um, ein fremdes „So" oder „Do" bleibt stehen.
        const text = (knoten.textContent || "").trim();
        const ersatz = text.length > 2 && this._t(text);
        if (ersatz && ersatz !== text) knoten.textContent = ersatz;
        return;
      }
      Array.from(kinder).forEach(gehe);
    };
    gehe(wurzel);
  }

  /**
   * Eine Karte zuklappbar machen.
   *
   * Der Kartenkopf wird zur Zusammenfassung, der Rest verschwindet, bis man
   * daraufdrückt. Gebaut wird der Inhalt trotzdem – nur so stimmen die
   * Bindungen, wenn jemand aufklappt, ohne dass die Ansicht neu entsteht.
   */
  _klappbar(karte) {
    if (!karte) return null;
    const kopf = karte.querySelector(".kartenkopf");
    const details = document.createElement("details");
    details.className = "karte klappkarte";
    const zusammenfassung = document.createElement("summary");
    if (kopf) {
      while (kopf.firstChild) zusammenfassung.appendChild(kopf.firstChild);
      kopf.remove();
    }
    zusammenfassung.appendChild(this._symbolKnoten("mdi:chevron-down", "pfeil"));
    details.appendChild(zusammenfassung);
    while (karte.firstChild) details.appendChild(karte.firstChild);
    return details;
  }

  _karte(titel, hilfe) {
    const karte = document.createElement("div");
    karte.className = "karte";
    if (titel) {
      const kopf = document.createElement("div");
      kopf.className = "kartenkopf";
      const ueberschrift = document.createElement("h2");
      ueberschrift.textContent = titel;
      kopf.appendChild(ueberschrift);
      const text = hilfe || (this._hilfe && this._hilfe[titel]);
      if (text) kopf.appendChild(this._fragezeichen(titel, text));
      karte.appendChild(kopf);
    }
    return karte;
  }

  /**
   * Ein „?", das erklärt, was hier eigentlich passiert.
   *
   * Die Anlage bringt zu jeder Einstellung eine Erklärung mit – nur liegt die
   * Anleitung beim Heizen selten daneben. Der Text kommt aus der Integration;
   * abschalten lässt er sich in den Optionen.
   */
  _fragezeichen(titel, text) {
    const taste = document.createElement("button");
    taste.type = "button";
    taste.className = "fragezeichen";
    taste.textContent = this._t("?");
    taste.title = this._t("Erklärung");
    taste.setAttribute("aria-label", this._tMit("Erklärung zu {titel}", { titel: this._t(titel) }));
    taste.addEventListener("click", (ereignis) => {
      ereignis.stopPropagation();
      this._erklaeren(titel, text);
    });
    return taste;
  }

  /** Erklärung als Hinweisfenster – bewusst dieselbe Form wie die Rückfrage. */
  _erklaeren(titel, text) {
    const schleier = document.createElement("div");
    schleier.className = "schleier";
    const dialog = document.createElement("div");
    dialog.className = "dialog erklaerung";

    const ueberschrift = document.createElement("h3");
    ueberschrift.className = "dialog-titel";
    // Das Fenster entsteht nach dem Aufbau; `_uebersetzen` erreicht es nicht mehr.
    ueberschrift.textContent = this._t(titel);
    const inhalt = document.createElement("div");
    inhalt.className = "dialog-text";
    inhalt.textContent = this._t(text);

    const leiste = document.createElement("div");
    leiste.className = "dialog-leiste";
    const schliessen = document.createElement("button");
    schliessen.type = "button";
    schliessen.className = "dialog-taste";
    schliessen.textContent = this._t("Verstanden");
    leiste.appendChild(schliessen);

    dialog.append(ueberschrift, inhalt, leiste);
    schleier.appendChild(dialog);
    const weg = this._dialogOeffnen(schleier, { fokus: schliessen });
    schliessen.addEventListener("click", weg);
  }

  /**
   * Hängt ein fertig gebautes Fenster (Schleier mit `.dialog`) in die Oberfläche.
   *
   * Es sorgt für Rolle und Beschriftung, Escape, Klick daneben, eine Fokusfalle
   * und den Fokus zurück an den Auslöser. Alle Hörer hängen an einem
   * AbortController, den das Schließen und der Abbau der Oberfläche auslösen.
   * Das Ergebnis ist die Funktion zum Schließen; `beiAbbruch` läuft, wenn
   * Escape, ein Klick daneben oder der Abbau das Fenster schließen.
   */
  _dialogOeffnen(schleier, { fokus = null, beiAbbruch = null } = {}) {
    const dialog = schleier.querySelector(".dialog");
    const titel = dialog.querySelector(".dialog-titel");
    if (!dialog.getAttribute("role")) dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    if (titel) {
      this._dialogZaehler = (this._dialogZaehler || 0) + 1;
      titel.id = titel.id || `dialog-titel-${this._dialogZaehler}`;
      dialog.setAttribute("aria-labelledby", titel.id);
    }
    const ausloeser = this.shadowRoot.activeElement || null;
    const abbruch = new AbortController();
    const stapel = this._dialogStapel || (this._dialogStapel = []);
    let offen = true;
    const zu = () => {
      if (!offen) return;
      offen = false;
      abbruch.abort();
      schleier.remove();
      const stelle = stapel.indexOf(abbrechen);
      if (stelle >= 0) stapel.splice(stelle, 1);
      if (ausloeser && this.shadowRoot.contains(ausloeser)) ausloeser.focus();
    };
    const abbrechen = () => {
      if (!offen) return;
      zu();
      if (beiAbbruch) beiAbbruch();
    };
    const beiTaste = (ereignis) => {
      if (stapel[stapel.length - 1] !== abbrechen) return;
      if (ereignis.key === "Escape") abbrechen();
      else if (ereignis.key === "Tab") this._fokusHalten(dialog, ereignis);
    };
    document.addEventListener("keydown", beiTaste, { signal: abbruch.signal });
    schleier.addEventListener(
      "click",
      (ereignis) => {
        if (ereignis.target === schleier) abbrechen();
      },
      { signal: abbruch.signal }
    );
    stapel.push(abbrechen);
    this.shadowRoot.appendChild(schleier);
    if (fokus) fokus.focus();
    return zu;
  }

  /** Tab bleibt im Fenster: vom letzten Bedienelement zurück zum ersten und umgekehrt. */
  _fokusHalten(dialog, ereignis) {
    const ziele = [...dialog.querySelectorAll("button, input, select, textarea, [tabindex]")].filter(
      (knoten) => !knoten.disabled && knoten.getAttribute("tabindex") !== "-1"
    );
    if (!ziele.length) return;
    const aktiv = this.shadowRoot.activeElement;
    const erstes = ziele[0];
    const letztes = ziele[ziele.length - 1];
    if (ereignis.shiftKey && (aktiv === erstes || !dialog.contains(aktiv))) {
      ereignis.preventDefault();
      letztes.focus();
    } else if (!ereignis.shiftKey && (aktiv === letztes || !dialog.contains(aktiv))) {
      ereignis.preventDefault();
      erstes.focus();
    }
  }

  /** Schließt alle offenen Fenster, zuletzt geöffnetes zuerst; der Abbau der Oberfläche ruft es. */
  _dialogeSchliessen() {
    const stapel = this._dialogStapel || [];
    while (stapel.length) stapel[stapel.length - 1]();
  }

  _symbolKnoten(symbol, klasse) {
    const ikone = document.createElement("ha-icon");
    ikone.setAttribute("icon", symbol);
    if (klasse) ikone.className = klasse;
    return ikone;
  }

  /**
   * Eine Meldung in die Leiste von Home Assistant geben.
   *
   * Ohne sie bleibt ein misslungenes Speichern in der Entwicklerkonsole
   * stehen: Die Karte springt zurück, beim nächsten Laden ist sie weg.
   */
  _melden(text) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", {
        detail: { message: text },
        bubbles: true,
        composed: true,
      })
    );
  }

  _hinweisKnoten(text) {
    const hinweis = document.createElement("div");
    hinweis.className = "hinweis";
    hinweis.textContent = text;
    return hinweis;
  }
  };
