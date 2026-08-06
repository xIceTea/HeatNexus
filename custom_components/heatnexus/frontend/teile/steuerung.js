/**
 * Reiter „Steuerung“ – die Anlage bedienen.
 *
 * Heizkreis mit Sollwertregler, Eco und Comfort, Warmwasser, Lagerraum und
 * Kessel. Jede Karte hier schreibt an die Anlage; das Muster dafür steht in
 * `bedienen.js`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import { OHNE_WERT } from "../ordnung.js";

export const SteuerungMixin = (Basis) =>
  class extends Basis {
  // -------------------------------------------------------------------
  // Reiter „Steuerung"
  // -------------------------------------------------------------------
  _steuerung(anlage) {
    const steuerung = anlage.steuerung || {};
    // Je Heizkreis eine Karte – die Kennung hängt an der Gerätekennung, nicht
    // an der Position: Kommt ein Kreis dazu, behalten die anderen ihren Platz.
    const karten = (steuerung.heizkreise || []).map((kreis) => ({
      id: `heizkreis:${kreis.id || kreis.entity}`,
      titel: kreis.titel,
      knoten: this._heizkreisKarte(kreis),
    }));
    karten.push(
      {
        id: "warmwasser",
        titel: "Warmwasser",
        knoten: steuerung.warmwasser ? this._warmwasserKarte(steuerung.warmwasser) : null,
      },
      {
        id: "kessel",
        titel: "Kessel",
        knoten: (steuerung.kessel || []).length ? this._kesselKarte(steuerung.kessel) : null,
      },
      {
        id: "lagerraum",
        titel: "Lagerraum befüllen",
        knoten: steuerung.lagerraum ? this._lagerraumKarte(steuerung.lagerraum) : null,
      }
    );
    return karten;
  }

  /**
   * Eine Taste für Eco bzw. Comfort.
   *
   * Geschrieben wird dieselbe befristete Übersteuerung, die das Bediengerät
   * setzt: Temperatur (3/4) und Dauer (2/10). Die Vorgaben stehen in den
   * Optionen der Integration und gelten für alle Kreise.
   *
   * Der Weg führt bewusst über den Dienst `heatnexus.set_vorgabe` und nicht
   * mehr über die beiden Zahlen-Entitäten. Direkt geschrieben fehlte die
   * Umschaltung aus Standby und WW-Betrieb: Dort ist der Heizkreis aus, die
   * Anlage übernahm nur den Timer, und die Taste wartete auf eine Bestätigung,
   * die nicht kommen konnte.
   */
  _uebersteuerungsTaste(kreis, schluessel, beschriftungText, symbol) {
    const werte = ((this._daten && this._daten.uebersteuerung) || {})[schluessel] || {};
    const taste = document.createElement("button");
    taste.className = "taste";
    taste.type = "button";
    taste.appendChild(this._symbolKnoten(symbol));
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = beschriftungText;
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    taste.append(beschriftung, rueckmeldung);

    taste.addEventListener("click", async () => {
      if (taste.disabled) return;
      const temperatur = Number(werte.temperatur);
      const dauer = Number(werte.dauer);
      if (!Number.isFinite(temperatur) || !Number.isFinite(dauer)) return;
      taste.disabled = true;
      try {
        await this._uebertragen(
          rueckmeldung,
          () =>
            this._hass.callService("heatnexus", "set_vorgabe", {
              entity_id: kreis.entity,
              temperature: temperatur,
              duration: dauer,
            }),
          () => {
            const jetzt = this._zustand(kreis.entity);
            return !!jetzt && Math.abs(Number(jetzt.attributes.temperature) - temperatur) < 0.3;
          },
          kreis.entity
        );
        // Betriebswahl und Restzeit ziehen erst mit dem nächsten Abruf nach –
        // ohne Nachfassen stünde die Karte 30 s lang auf dem alten Stand.
        this._nachfassen({ entity: kreis.entity, betriebswahl: kreis.betriebswahl });
      } finally {
        taste.disabled = false;
      }
    });

    this._bindungen.push(() => {
      if (rueckmeldung.dataset.belegt === "1") return;
      const zustand = this._zustand(kreis.entity);
      const soll = zustand ? Number(zustand.attributes.temperature) : NaN;
      const aktiv =
        !!zustand &&
        zustand.attributes.override_aktiv === true &&
        Math.abs(soll - Number(werte.temperatur)) < 0.3;
      taste.classList.toggle("an", aktiv);
      rueckmeldung.className = "rueckmeldung";
      const grad = Number(werte.temperatur);
      rueckmeldung.textContent = Number.isFinite(grad)
        ? `${grad} °C · ${Math.round(Number(werte.dauer) || 0)} min`
        : "";
    });
    return taste;
  }

  /** Heizkreis mit Sollwertregler, Betriebswahl und Zeitprogramm. */
  _heizkreisKarte(kreis) {
    const karte = this._karte(kreis.titel);

    // Die Anlage stellt in ihrer Detailansicht die Betriebsart als Klartext
    // ueber den Wert - dort sucht man sie.
    const betriebsart = document.createElement("div");
    betriebsart.className = "betriebsart";
    karte.appendChild(betriebsart);
    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      betriebsart.textContent =
        zustand && zustand.attributes.preset_mode ? this._presetName(zustand) : "";
    });

    const gross = document.createElement("div");
    gross.className = "gross";
    const zahl = document.createElement("div");
    zahl.className = "zahl";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = "Raumtemperatur";
    gross.append(zahl, beschriftung);
    karte.appendChild(this._klickbar(gross, kreis.entity));

    const laufzeit = document.createElement("div");
    laufzeit.className = "laufzeit";
    laufzeit.appendChild(this._symbolKnoten("mdi:timer-sand"));
    const laufzeitText = document.createElement("span");
    laufzeit.appendChild(laufzeitText);
    // Eine laufende Vorgabe muss sich beenden lassen, ohne dass man den
    // Sollwert zurückdreht. Die Dauer (2/10) auf null zu setzen ist derselbe
    // Weg, den die Anlage beim Wechsel der Betriebswahl selbst geht – danach
    // gilt wieder das Zeitprogramm.
    const abbruch = document.createElement("button");
    abbruch.type = "button";
    abbruch.className = "laufzeit-abbruch";
    abbruch.textContent = "abbrechen";
    abbruch.title = "Vorgabe beenden und zum Programm zurückkehren";
    if (kreis.uebersteuerung_dauer) laufzeit.appendChild(abbruch);
    karte.appendChild(laufzeit);

    // Sollwertregler
    const regler = document.createElement("div");
    regler.className = "regler";
    const runter = document.createElement("button");
    runter.type = "button";
    runter.textContent = "−";
    runter.setAttribute("aria-label", "Sollwert senken");
    const mitte = document.createElement("div");
    mitte.className = "sollwert";
    const sollZahl = document.createElement("div");
    sollZahl.className = "zahl";
    const sollText = document.createElement("div");
    sollText.className = "beschriftung";
    sollText.textContent = "Sollwert";
    mitte.append(sollZahl, sollText);
    const hoch = document.createElement("button");
    hoch.type = "button";
    hoch.textContent = "+";
    hoch.setAttribute("aria-label", "Sollwert anheben");
    regler.append(runter, mitte, hoch);
    karte.appendChild(regler);

    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    karte.appendChild(rueckmeldung);

    const stellen = async (richtung) => {
      const zustand = this._zustand(kreis.entity);
      if (!zustand) return;
      const schritt = Number(zustand.attributes.target_temp_step) || 0.5;
      const soll = Number(zustand.attributes.temperature);
      if (Number.isNaN(soll)) return;
      const neu = Math.round((soll + richtung * schritt) * 10) / 10;
      await this._uebertragen(
        rueckmeldung,
        () =>
          this._hass.callService("climate", "set_temperature", {
            entity_id: kreis.entity,
            temperature: neu,
          }),
        // Bestätigt ist die Vorgabe erst, wenn die Anlage sie zurückmeldet.
        () => {
          const jetzt = this._zustand(kreis.entity);
          return !!jetzt && Math.abs(Number(jetzt.attributes.temperature) - neu) < 0.3;
        },
        kreis.entity
      );
    };
    runter.addEventListener("click", () => stellen(-1));
    hoch.addEventListener("click", () => stellen(1));

    abbruch.addEventListener("click", async () => {
      if (abbruch.disabled || !kreis.uebersteuerung_dauer) return;
      abbruch.disabled = true;
      try {
        await this._uebertragen(
          rueckmeldung,
          () =>
            this._hass.callService("number", "set_value", {
              entity_id: kreis.uebersteuerung_dauer,
              value: 0,
            }),
          () => {
            const jetzt = this._zustand(kreis.entity);
            return !!jetzt && jetzt.attributes.override_aktiv !== true;
          },
          kreis.entity
        );
        this._nachfassen({
          entity: kreis.uebersteuerung_dauer,
          betriebswahl: kreis.betriebswahl,
        });
      } finally {
        abbruch.disabled = false;
      }
    });

    // Eco und Comfort: dieselbe befristete Übersteuerung, die auch das
    // Bediengerät schreibt. Die Anlage kennt je Kreis nur *einen*
    // Übersteuerungswert – ob er Eco oder Comfort heißt, entscheidet sie
    // daran, ob er unter oder über dem Programmsollwert liegt.
    if (kreis.uebersteuerung_temperatur && kreis.uebersteuerung_dauer) {
      const paar = document.createElement("div");
      paar.className = "gitter";
      paar.style.marginTop = "12px";
      [
        ["eco", "Eco", "mdi:leaf"],
        ["comfort", "Comfort", "mdi:sofa"],
      ].forEach(([schluessel, beschriftung, symbol]) => {
        paar.appendChild(this._uebersteuerungsTaste(kreis, schluessel, beschriftung, symbol));
      });
      karte.appendChild(paar);
    }

    if (kreis.betriebswahl) {
      karte.appendChild(
        this._auswahlFeld("Betriebswahl", kreis.betriebswahl, kreis.betriebswahl_hilfe)
      );
    }
    if (kreis.programm) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.append(trenner, this._statuszeile(kreis.programm, "Zeitprogramm"));
    }
    if (kreis.vorlauf) {
      karte.appendChild(this._statuszeile(kreis.vorlauf, "Vorlauf"));
    }

    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      const ist = zustand && zustand.attributes.current_temperature;
      zahl.textContent = ist !== undefined && ist !== null ? `${ist} °C` : "–";
      const soll = zustand && zustand.attributes.temperature;
      sollZahl.textContent = soll !== undefined && soll !== null ? `${soll} °C` : "–";
      const rest = this._restzeit(zustand);
      laufzeit.style.display = rest ? "inline-flex" : "none";
      laufzeitText.textContent = rest ? `Vorgabe ${rest}` : "";
      // Ohne laufende Vorgabe gibt es nichts zu beenden.
      laufzeit.hidden = !rest;
    });
    return karte;
  }

  /**
   * Warmwasser mit Ist, Soll und Einmalladung.
   *
   * Die Einmalladung läuft minutenlang. Die Taste bleibt deshalb markiert,
   * solange die Anlage sie als aktiv meldet, und springt von selbst zurück,
   * wenn die Ladung fertig ist – so wie in der Windhager-App.
   */
  _warmwasserKarte(wasser) {
    const karte = this._karte("Warmwasser");

    // Wie bei der Anlage: die Betriebsart im Klartext über dem Wert.
    if (wasser.betriebsart) {
      const betriebsart = document.createElement("div");
      betriebsart.className = "betriebsart";
      karte.appendChild(betriebsart);
      this._bindungen.push(() => {
        betriebsart.textContent = this._text(wasser.betriebsart);
      });
    }

    const gross = document.createElement("div");
    gross.className = "gross";
    const zahl = document.createElement("div");
    zahl.className = "zahl";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = "Isttemperatur";
    gross.append(zahl, beschriftung);
    karte.appendChild(wasser.ist ? this._klickbar(gross, wasser.ist) : gross);
    this._bindungen.push(() => {
      zahl.textContent = wasser.ist ? this._text(wasser.ist) : "–";
    });

    if (wasser.soll) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.append(trenner, this._statuszeile(wasser.soll, "Sollwert"));
    }
    if (wasser.programm) {
      karte.appendChild(this._statuszeile(wasser.programm, "Programm"));
    }

    if (wasser.taste) {
      const trenner = document.createElement("div");
      trenner.className = "trenner";
      karte.appendChild(trenner);
      // Die Anlage kennt zur Einmalladung beides: die Temperatur, auf die
      // geladen wird, und das Ausloesen.
      if (wasser.laden_temperatur) {
        karte.appendChild(this._statuszeile(wasser.laden_temperatur, "Ladetemperatur"));
      }
      // **Dieselbe Taste wie im Schnellzugriff der Übersicht.** Vorher stand
      // hier eine eigene, die weder die Ladeschwelle kannte noch abbrechen
      // konnte: In der Übersicht ließ sich eine Ladung beenden, in der
      // Steuerung nicht.
      karte.appendChild(this._bedientaste(wasser.taste, true));
    }
    return karte;
  }


  _istAn(entity) {
    const zustand = this._zustand(entity);
    return !!zustand && zustand.state === "on";
  }

  _auswahlFeld(titel, entity, hilfe) {
    const feld = document.createElement("div");
    feld.className = "feld";
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    const wort = document.createElement("span");
    wort.textContent = titel;
    beschriftung.appendChild(wort);
    // Gerade der Brennstoff braucht die Erklärung: Welche der vier
    // Einstellungen richtig ist, sieht man der Auswahlliste nicht an.
    const text = hilfe || (this._hilfe && this._hilfe[titel]);
    if (text) beschriftung.appendChild(this._fragezeichen(titel, text));
    const auswahl = document.createElement("select");
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    feld.append(beschriftung, auswahl, rueckmeldung);

    auswahl.addEventListener("change", async () => {
      const gewaehlt = auswahl.value;
      await this._uebertragen(
        rueckmeldung,
        () =>
          this._hass.callService("select", "select_option", {
            entity_id: entity,
            option: gewaehlt,
          }),
        () => {
          const zustand = this._zustand(entity);
          return !!zustand && zustand.state === gewaehlt;
        },
        entity
      );
    });

    this._bindungen.push(() => {
      const zustand = this._zustand(entity);
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
      if (rueckmeldung.dataset.belegt === "1") return;
      // Die Rückmeldung gehört ausdrücklich zurückgesetzt. Ohne das blieb
      // „übernommen ✓" für immer stehen: `_freigeben` löscht nur die Sperre
      // und stößt die Bindungen an – den Text löscht niemand.
      rueckmeldung.textContent = "";
      rueckmeldung.className = "rueckmeldung";
      if (zustand) auswahl.value = zustand.state;
    });
    return feld;
  }

  /**
   * Lagerraumbefüllung, aufgebaut wie die Seite am Bediengerät.
   *
   * Erst anfordern, dann ablesen: Die Anlage gibt das Befüllen nur frei, wenn
   * ihr Zustand es zulässt – bei pneumatischer Zuführung etwa erst bei leerem
   * Vorratsbehälter. Erst wenn dort „freigegeben" steht, darf weiterbefüllt
   * werden; das ist keine Anzeigefrage, sondern steht so in der Anleitung des
   * Kessels (Beschädigung des Rührwerks).
   */
  _lagerraumKarte(lagerraum) {
    const karte = this._karte("Lagerraum befüllen");

    (lagerraum.zeilen || []).forEach((zeile) => {
      karte.appendChild(this._statuszeile(zeile.entity, zeile.titel));
    });

    const trenner = document.createElement("div");
    trenner.className = "trenner";
    karte.appendChild(trenner);
    karte.appendChild(
      this._bedientaste(
        {
          entity: lagerraum.anfordern,
          titel: "Befüllung anfordern",
          symbol: "mdi:warehouse",
          frage: lagerraum.frage,
        },
        true
      )
    );
    return karte;
  }

  /**
   * Kesselbedienung: Auswahlfelder oben, Tasten darunter im Raster.
   *
   * Untereinander gestapelt wuchs die Karte mit jeder Reinigungstaste weiter
   * in die Länge; nebeneinander bleibt sie überschaubar und sieht aus wie der
   * Schnellzugriff.
   */
  _kesselKarte(eintraege) {
    const karte = this._karte("Kessel");
    const gitter = document.createElement("div");
    gitter.className = "gitter";
    gitter.style.marginTop = "10px";

    eintraege.forEach((eintrag) => {
      const bereich = eintrag.entity.split(".")[0];
      if (bereich === "select") {
        karte.appendChild(this._auswahlFeld(eintrag.titel, eintrag.entity, eintrag.hilfe));
        return;
      }
      gitter.appendChild(this._bedientaste(eintrag, false));
    });

    if (gitter.childElementCount) karte.appendChild(gitter);
    return karte;
  }
  };
