/**
 * Bedienen: nachfragen, übertragen, zurückmelden.
 *
 * Alles, was zwischen einem Tastendruck und der Antwort der Anlage liegt:
 * die Rückfrage vor teuren Eingriffen, der Dienstaufruf selbst und die
 * dreistufige Rückmeldung, die auf die Bestätigung der Anlage wartet.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import { BESTAETIGUNG_MAX_MS, RUECKMELDUNG_MS } from "../ordnung.js";

export const BedienenMixin = (Basis) =>
  class extends Basis {
  /**
   * Die beteiligten Entitäten sofort neu abfragen.
   *
   * Die Anlage wird nur alle 30 s abgerufen. Nach einem Eingriff stünde die
   * Anzeige bis dahin auf dem alten Stand – gerade beim Abbrechen, wo die
   * Betriebswahl den Ausschlag gibt, wirkte die Taste dadurch wirkungslos.
   */
  _nachfassen(eintrag) {
    const entitaeten = [
      eintrag.betriebswahl,
      eintrag.zustand_an,
      eintrag.zustand_pumpe,
      eintrag.entity,
    ].filter(Boolean);
    if (!entitaeten.length) return;
    this._hass
      .callService("homeassistant", "update_entity", { entity_id: entitaeten })
      .catch((err) => console.warn("HeatNexus: Nachfassen fehlgeschlagen", err));
  }

  /**
   * Die erste Auswahlmöglichkeit einer Entität, die zu einem Muster passt.
   *
   * Welche Einträge eine Betriebswahl anbietet, meldet die Anlage selbst –
   * eine feste Liste im Quelltext ginge bei der nächsten Baureihe daneben.
   */
  _optionWie(entity, muster) {
    const zustand = this._zustand(entity);
    const optionen = (zustand && zustand.attributes.options) || [];
    const regex = new RegExp(muster, "i");
    return optionen.find((option) => regex.test(option)) || null;
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
   * nichts passiert. Deshalb drei Stufen: „wird übertragen" während des
   * Aufrufs, danach „wird ausgeführt …", solange die Anlage den neuen Zustand
   * noch nicht zurückmeldet, und erst dann „übernommen ✓".
   *
   * Ohne `bestaetigt` bleibt es bei den ersten beiden Stufen – bei einer
   * Taste ohne Zustand gibt es nichts, worauf man warten könnte.
   */
  async _uebertragen(anzeige, aufruf, bestaetigt, kennung) {
    // Ein neuer Auftrag löst den alten ab – sonst hinge die Anzeige an einer
    // Bestätigung, auf die niemand mehr wartet. Das gilt **auch über Tasten
    // hinweg**, wenn beide dieselbe Entität stellen: Wer den Sollwert
    // verschiebt und dann Eco drückt, hat den ersten Auftrag selbst
    // überstimmt. Der wartete bis dahin drei Minuten auf eine Temperatur, die
    // nie mehr kommt, und „wird ausgeführt …" blieb daneben stehen.
    this._wartend = this._wartend.filter((vorgang) => {
      const abgeloest =
        vorgang.anzeige === anzeige || (!!kennung && vorgang.kennung === kennung);
      if (abgeloest && vorgang.anzeige !== anzeige) this._loeschen(vorgang.anzeige);
      return !abgeloest;
    });
    anzeige.dataset.belegt = "1";
    anzeige.className = "rueckmeldung laeuft";
    anzeige.textContent = "wird übertragen …";
    try {
      await aufruf();
    } catch (err) {
      anzeige.className = "rueckmeldung fehler";
      anzeige.textContent = "nicht übernommen";
      console.warn("HeatNexus: Befehl abgelehnt", err);
      this._freigeben(anzeige, RUECKMELDUNG_MS);
      return;
    }

    if (!bestaetigt) {
      anzeige.className = "rueckmeldung erfolg";
      anzeige.textContent = "übertragen ✓";
      this._freigeben(anzeige, RUECKMELDUNG_MS);
      return;
    }

    anzeige.className = "rueckmeldung wartet";
    anzeige.textContent = "wird ausgeführt …";
    this._wartend.push({ anzeige, bestaetigt, seit: Date.now() });
    this._pruefeWartende();
  }

  /** Eine Rückmeldung sofort räumen – ohne Text, ohne Wartezeit. */
  _loeschen(anzeige) {
    delete anzeige.dataset.belegt;
    anzeige.className = "rueckmeldung";
    anzeige.textContent = "";
  }

  /**
   * Die Anzeige nach kurzer Zeit wieder dem Zustand überlassen.
   *
   * Der Text wird hier gelöscht, nicht von den Bindungen. Nur die wenigsten
   * schreiben die Zeile ohnehin neu – bei den übrigen blieb „übernommen ✓"
   * für immer stehen, zuletzt beim Abbrechen einer Vorgabe. Wer die Zeile
   * besitzt, füllt sie im gleich folgenden `_aktualisieren` wieder.
   */
  _freigeben(anzeige, verzoegerung) {
    window.setTimeout(() => {
      delete anzeige.dataset.belegt;
      anzeige.className = "rueckmeldung";
      anzeige.textContent = "";
      this._aktualisieren();
    }, verzoegerung);
  }

  /**
   * Laufende Vorgänge prüfen.
   *
   * Läuft bei jedem Zustandswechsel mit – die Anlage meldet ihren neuen
   * Zustand mit dem nächsten Abruf, und genau darauf wird gewartet.
   */
  _pruefeWartende() {
    if (!this._wartend.length) return;
    const offen = [];
    this._wartend.forEach((vorgang) => {
      let fertig = false;
      try {
        fertig = vorgang.bestaetigt();
      } catch (err) {
        console.warn("HeatNexus: Zustand nicht prüfbar", err);
        fertig = true;
      }
      if (fertig) {
        vorgang.anzeige.className = "rueckmeldung erfolg";
        vorgang.anzeige.textContent = "übernommen ✓";
        this._freigeben(vorgang.anzeige, RUECKMELDUNG_MS);
        return;
      }
      if (Date.now() - vorgang.seit > BESTAETIGUNG_MAX_MS) {
        vorgang.anzeige.className = "rueckmeldung";
        vorgang.anzeige.textContent = "keine Rückmeldung";
        this._freigeben(vorgang.anzeige, RUECKMELDUNG_MS);
        return;
      }
      offen.push(vorgang);
    });
    this._wartend = offen;
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
  };
