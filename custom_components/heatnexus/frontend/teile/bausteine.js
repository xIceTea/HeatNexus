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

  /**
   * Den fertigen Baum in die eingestellte Sprache bringen.
   *
   * Ein Durchlauf statt eines Aufrufs an jeder Beschriftung. Auf Deutsch ist
   * das Wörterbuch leer und die Methode kehrt sofort zurück.
   */
  _uebersetzen(wurzel) {
    if (!wurzel || !this._texte || !Object.keys(this._texte).length) return;
    const merkmale = ["title", "aria-label", "placeholder"];
    const gehe = (knoten) => {
      if (knoten.getAttribute) {
        merkmale.forEach((merkmal) => {
          const wert = knoten.getAttribute(merkmal);
          if (wert && this._texte[wert]) knoten.setAttribute(merkmal, this._texte[wert]);
        });
      }
      // Der Browser führt Textknoten in `childNodes`, die Attrappe der Tests
      // in `children`. Ein Knoten ohne Kinder trägt seinen Text selbst.
      const kinder = knoten.childNodes || knoten.children;
      if (!kinder || !kinder.length) {
        const text = (knoten.textContent || "").trim();
        if (text && this._texte[text]) knoten.textContent = this._texte[text];
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
    taste.textContent = "?";
    taste.title = "Erklärung";
    taste.setAttribute("aria-label", `Erklärung zu ${titel}`);
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
    dialog.setAttribute("role", "dialog");

    const ueberschrift = document.createElement("h3");
    ueberschrift.className = "dialog-titel";
    ueberschrift.textContent = titel;
    const inhalt = document.createElement("div");
    inhalt.className = "dialog-text";
    inhalt.textContent = text;

    const leiste = document.createElement("div");
    leiste.className = "dialog-leiste";
    const schliessen = document.createElement("button");
    schliessen.type = "button";
    schliessen.className = "dialog-taste";
    schliessen.textContent = "Verstanden";
    leiste.appendChild(schliessen);

    dialog.append(ueberschrift, inhalt, leiste);
    schleier.appendChild(dialog);
    const weg = () => {
      schleier.remove();
      document.removeEventListener("keydown", beiTaste);
    };
    const beiTaste = (ereignis) => {
      if (ereignis.key === "Escape") weg();
    };
    schliessen.addEventListener("click", weg);
    schleier.addEventListener("click", (e) => {
      if (e.target === schleier) weg();
    });
    document.addEventListener("keydown", beiTaste);
    this.shadowRoot.appendChild(schleier);
    schliessen.focus();
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
