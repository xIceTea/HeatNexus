/**
 * Reiter „Übersicht“ – und was nur dort steht.
 *
 * Kennwerte, Heizkreise, Warmwasser, Systemstatus, Störungen und der
 * Schnellzugriff. Die Karten dieses Reiters lesen fast nur ab; bedient wird
 * im Reiter „Steuerung“.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import { OHNE_WERT, RUECKMELDUNG_MS } from "../ordnung.js";

export const UebersichtMixin = (Basis) =>
  class extends Basis {
  // -------------------------------------------------------------------
  // Reiter „Übersicht"
  // -------------------------------------------------------------------
  /**
   * Die Karten der Übersicht in ihrer Standardreihenfolge.
   *
   * Zurück kommen **Beschreibungen**, keine fertige Aufteilung: Kennung,
   * Titel, Knoten und die Standardbreite in Spalten. Erst `_raster` bringt
   * sie in die Reihenfolge, die der Nutzer gewählt hat. Die Kennungen sind
   * fest verdrahtet und nicht durchnummeriert – nur so findet eine gespeicherte
   * Anordnung ihre Karten wieder, wenn ein Anlagenteil dazukommt.
   */
  _uebersicht(anlage) {
    const wasser = this._warmwasserkarte(anlage);
    return [
      { id: "seite", titel: "Heizungsübersicht", knoten: this._seite(anlage) },
      { id: "schaubild", titel: "Anlagenübersicht", knoten: this._schaubild(anlage), breite: 2 },
      { id: "status", titel: "Systemstatus", knoten: this._statuskarte(anlage) },
      { id: "heizkreise", titel: "Heizkreise", knoten: this._heizkreiskarte(anlage) },
      {
        id: "schnellzugriff",
        titel: "Schnellzugriff",
        knoten: this._schnellzugriff(anlage),
        // Ohne Warmwasserkreis bleibt in der Zeile ein Platz frei; den nimmt
        // der Schnellzugriff ein, statt ein Loch stehen zu lassen.
        breite: wasser ? 1 : 2,
      },
      { id: "warmwasser", titel: "Warmwasser", knoten: wasser },
      { id: "stoerungen", titel: "Störungen", knoten: this._stoerungskarte(anlage) },
      {
        id: "verlauf24",
        titel: "Verlauf (24 Stunden)",
        knoten: this._klappbar(this._verlauf(anlage, 24)),
        breite: 2,
      },
    ];
  }

  // -------------------------------------------------------------------
  // Linke Spalte: Marke, Zustand, Kennwerte
  // -------------------------------------------------------------------
  _seite(anlage) {
    // Eine Überschrift wie jede andere Karte. Marke und Logo standen hier ein
    // zweites Mal, obwohl beide in der Kopfleiste darüber stehen; der Name der
    // Anlage steht unter „Alle" in der Trennzeile und sonst im gewählten
    // Reiter oben rechts.
    const karte = this._karte("Heizungsübersicht");

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
        this._wertzeile(
          kennwert.entity,
          kennwert.titel,
          kennwert.untertitel,
          kennwert.symbol,
          // Was statt einer Zahl dasteht, solange der Wert nicht über null
          // liegt – bei der Wärmeanforderung des Pumpen-/Relaismoduls ein
          // Strich. Ein „0,0 °C" behauptete dort eine Anforderung mit null
          // Grad.
          kennwert.ersatz_unter_null
        )
      );
    });
    karte.appendChild(liste);
    return karte;
  }

  /**
   * Kennwertzeile wie im Muster: links Anlagenteil, rechts der große Wert und
   * darunter klein, worum es sich handelt („Kesseltemperatur").
   */
  _wertzeile(entity, titel, bezeichnung, symbol, ersatzUnterNull) {
    const zeile = document.createElement("div");
    zeile.className = "zeile";
    if (symbol) zeile.appendChild(this._symbolKnoten(symbol));
    const text = document.createElement("div");
    text.className = "text";
    const oben = document.createElement("div");
    oben.className = "titel";
    oben.textContent = titel;
    text.appendChild(oben);

    const rechts = document.createElement("div");
    rechts.className = "rechts";
    const wert = document.createElement("div");
    wert.className = "wert";
    const unten = document.createElement("div");
    unten.className = "bezeichnung";
    unten.textContent = bezeichnung || "";
    rechts.append(wert, unten);

    zeile.append(text, rechts);
    this._bindungen.push(() => {
      // Werte, die nur über null etwas bedeuten – die Wärmeanforderung des
      // Pumpen-/Relaismoduls. Liegt keine an, steht dort ein Strich statt
      // einer Zahl; das Anlagenteil bleibt sichtbar. Bis 1.5.0-beta.9
      // verschwand die Zeile stattdessen ganz, und mit ihr das Anlagenteil
      // aus der Liste.
      const zahl = ersatzUnterNull ? this._zahl(entity) : null;
      const ohneAnforderung = ersatzUnterNull && !(zahl !== null && zahl > 0);
      wert.textContent = ohneAnforderung ? ersatzUnterNull : this._text(entity);
      unten.textContent = bezeichnung || "";
      // Lange Texte („Betriebsbereit") umbrechen statt zu schrumpfen.
      wert.classList.toggle("lang", wert.textContent.length > 8);
    });
    return this._klickbar(zeile, entity);
  }

  // -------------------------------------------------------------------
  // Heizkreise und Warmwasser
  // -------------------------------------------------------------------
  /**
   * Die Heizkreise, unter der Anlagenübersicht in derselben Spalte.
   *
   * Dort wächst die Karte nach unten, wenn eine Anlage mehr als einen Kreis
   * hat, ohne das Schaubild zu verschieben.
   *
   * Was es nicht gibt, bekommt auch keine Karte – so hält es die Anlage
   * selbst: Was keinen Wert liefert, wird ausgeblendet.
   */
  _heizkreiskarte(anlage) {
    const kreise = anlage.heizkreise || [];
    if (!kreise.length) return null;
    const karte = this._karte("Heizkreise");
    kreise.forEach((kreis) => karte.appendChild(this._heizkreiszeile(kreis)));
    return karte;
  }

  /**
   * Warmwasser, unter dem Schaubild und genauso breit.
   *
   * Eine Anlage ohne Warmwasserbereitung bekommt gar keine Karte – eine leere
   * Karte behauptet, da fehle etwas.
   */
  _warmwasserkarte(anlage) {
    const wasser = anlage.warmwasser || [];
    if (!wasser.length) return null;
    const karte = this._karte("Warmwasser");
    wasser.forEach((eintrag) => {
      karte.appendChild(this._statuszeile(eintrag.entity, eintrag.titel));
    });
    return karte;
  }

  /**
   * Eine Heizkreiszeile nach dem Vorbild der Anlage.
   *
   * Links Symbol, Name und die Betriebsart farbig darunter; rechts der große
   * Ist-Wert mit dem Sollwert klein daneben, dahinter zwei Symbole: die
   * Betriebsart (Sonne, Mond, Standby …) und das Zeitprogramm.
   */
  _heizkreiszeile(kreis) {
    const zeile = document.createElement("div");
    zeile.className = "zeile kreis";
    zeile.appendChild(this._symbolKnoten("mdi:home-outline"));

    const text = document.createElement("div");
    text.className = "text";
    const oben = document.createElement("div");
    oben.className = "titel";
    oben.textContent = kreis.titel;
    const unten = document.createElement("div");
    unten.className = "betriebsart-klein";
    text.append(oben, unten);

    const rechts = document.createElement("div");
    rechts.className = "rechts";
    const wert = document.createElement("div");
    wert.className = "wert";
    const sollzeile = document.createElement("div");
    sollzeile.className = "bezeichnung";
    rechts.append(wert, sollzeile);

    const symbole = document.createElement("div");
    symbole.className = "kreis-symbole";
    const artSymbol = this._symbolKnoten("mdi:white-balance-sunny");
    const uhr = this._symbolKnoten("mdi:clock-outline");
    symbole.append(artSymbol, uhr);

    zeile.append(text, rechts, symbole);
    this._bindungen.push(() => {
      const zustand = this._zustand(kreis.entity);
      if (!zustand) {
        wert.textContent = "–";
        return;
      }
      const ist = zustand.attributes.current_temperature;
      const soll = zustand.attributes.temperature;
      wert.textContent = ist !== undefined && ist !== null ? `${ist} °C` : "–";
      sollzeile.textContent =
        soll !== undefined && soll !== null ? `${soll} °C` : "Raumtemperatur";

      const art = zustand.attributes.preset_mode ? this._presetName(zustand) : "";
      const rest = this._restzeit(zustand);
      unten.textContent = rest ? `${art} · ${rest}` : art;
      // Farbe wie im Muster: Heizen warm, Absenken kühl.
      const heizt = zustand.state === "heat" || zustand.attributes.hvac_action === "heating";
      unten.className = `betriebsart-klein ${heizt ? "heizt" : "abgesenkt"}`;
      artSymbol.setAttribute("icon", heizt ? "mdi:white-balance-sunny" : "mdi:weather-night");
      artSymbol.className = heizt ? "heizt" : "abgesenkt";
      uhr.style.display = kreis.programm ? "" : "none";
    });
    return this._klickbar(zeile, kreis.entity);
  }

  _presetName(zustand) {
    // Die Betriebsarten heißen am Gerät "0".."7"; die Klartexte liefert die
    // Übersetzung der Integration mit.
    if (this._hass.formatEntityAttributeValue) {
      return this._hass.formatEntityAttributeValue(zustand, "preset_mode");
    }
    return zustand.attributes.preset_mode;
  }

  /**
   * Text zur laufenden Sollwert-Vorgabe.
   *
   * Ein am Thermostat gesetzter Wert gilt befristet; die Anlage meldet die
   * Restzeit in Minuten (2/10). Ohne diese Anzeige sieht man dem Heizkreis
   * nicht an, dass gerade eine Vorgabe läuft.
   */
  _restzeit(zustand) {
    if (!zustand || zustand.attributes.override_aktiv !== true) return "";
    const minuten = Number(zustand.attributes.override_restzeit_min) || 0;
    if (minuten <= 0) return "";
    const ende = new Date(Date.now() + minuten * 60000);
    const uhrzeit = ende.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return minuten >= 60
      ? `noch bis ${uhrzeit}`
      : `noch ${minuten} min (bis ${uhrzeit})`;
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
      const text = this._text(entity);
      wert.textContent = text;
      wert.title = text;
      // Farbe nach Art des Wertes: kurze Zustände grün, Leistungen orange,
      // Zahlen blau – so wie im Muster. Ein langer Text bleibt neutral, sonst
      // leuchtet die halbe Karte.
      const zustand = this._zustand(entity);
      const einheit = zustand && zustand.attributes.unit_of_measurement;
      wert.className = "wert";
      if (einheit === "%" || einheit === "kW") wert.classList.add("warm");
      else if (!einheit && this._hatWert(entity) && text.length <= 20) {
        wert.classList.add("zustand");
      }
    });
    return this._klickbar(zeile, entity);
  }

  /**
   * Der Systemstatus – **ohne** die Störungskarte.
   *
   * Beide standen bis 1.2.0-beta.4 in einer gemeinsamen Hülle. In einer Spalte
   * wären sie damit ein einziger Block und könnten nicht getrennt aufrücken.
   *
   * Kein dritter Störungshinweis: Derselbe Zustand steht in der
   * Anlagenübersicht („Anlage in Ordnung") und in der Störungskarte.
   */
  _statuskarte(anlage) {
    const karte = this._karte("Systemstatus");
    (anlage.status || []).forEach((eintrag) => {
      karte.appendChild(this._statuszeile(eintrag.entity, eintrag.titel, eintrag.symbol));
    });
    if (!(anlage.status || []).length) {
      karte.appendChild(this._hinweisKnoten("Keine Statuswerte gefunden."));
    }
    return karte;
  }

  _stoerungskarte(anlage) {
    const karte = this._karte("Störungen");
    const eintraege = anlage.stoerungen || [];

    const mitte = document.createElement("div");
    mitte.className = "mitte";
    const symbol = this._symbolKnoten("mdi:shield-check-outline");
    const haupt = document.createElement("div");
    haupt.className = "haupt";
    const neben = document.createElement("div");
    neben.className = "neben";
    mitte.append(symbol, haupt, neben);
    karte.appendChild(mitte);

    eintraege.forEach((eintrag) => {
      const zeile = document.createElement("div");
      zeile.className = "status-zeile";
      const links = document.createElement("div");
      links.className = "titel";
      const wert = document.createElement("div");
      wert.className = "wert";
      zeile.append(links, wert);
      karte.appendChild(this._klickbar(zeile, eintrag.entity));
      this._bindungen.push(() => {
        links.textContent = this._name(eintrag.entity).replace(" Meldung Klartext", "");
        const zustand = this._zustand(eintrag.entity);
        const aktiv = zustand && zustand.attributes.stoerung_aktiv === true;
        wert.textContent = this._text(eintrag.entity);
        wert.className = `wert ${aktiv ? "schlecht" : "gut"}`;
        // Ohne Störung sagt der Kasten oben schon alles; die Zeilen sind dann
        // nur Wiederholung.
        zeile.style.display = aktiv ? "flex" : "none";
      });
    });

    this._bindungen.push(() => {
      const stoerung = this._stoerung(anlage);
      symbol.setAttribute("icon", stoerung ? "mdi:shield-alert-outline" : "mdi:shield-check-outline");
      symbol.className = stoerung ? "schlecht" : "gut";
      haupt.textContent = stoerung ? "Störung anliegend" : "Keine Störung";
      neben.textContent = stoerung
        ? "Die Anlage meldet mindestens eine aktive Störung."
        : "Alles läuft.";
      mitte.style.display = stoerung ? "none" : "block";
    });
    return karte;
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
      if (eintrag.entity.split(".")[0] === "select") {
        const huelle = this._auswahlFeld(eintrag.titel, eintrag.entity, eintrag.hilfe);
        huelle.style.gridColumn = "1 / -1";
        gitter.appendChild(huelle);
        return;
      }
      gitter.appendChild(this._bedientaste(eintrag, false));
    });

    karte.appendChild(gitter);
    return karte;
  }

  /** Eine Kachel, die einen Befehl auslöst – mit Rückfrage und Rückmeldung. */
  _bedientaste(eintrag, breit) {
    const bereich = eintrag.entity.split(".")[0];
    // Manche Bedienungen melden ihren Zustand woanders: Die Warmwasserladung
    // steht in der Betriebsart, ihr Auslöser fällt sofort zurück.
    const laeuft = () => {
      // Die Ladepumpe ist der handfeste Beleg: Sie läuft, solange geladen
      // wird. Die Betriebsart meldet je nach Baureihe andere Worte und an
      // manchen Kreisen gar nichts.
      if (eintrag.zustand_pumpe && this._istAn(eintrag.zustand_pumpe)) return true;
      if (eintrag.zustand_an) {
        const zustand = this._zustand(eintrag.zustand_an);
        if (zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase())) {
          return (eintrag.zustand_wenn || []).includes(zustand.state);
        }
      }
      return this._istAn(eintrag.entity);
    };
    const taste = document.createElement("button");
    taste.className = "taste";
    taste.type = "button";
    if (breit) taste.style.marginTop = "10px";
    taste.appendChild(this._symbolKnoten(eintrag.symbol || "mdi:gesture-tap-button"));
    const beschriftung = document.createElement("div");
    beschriftung.className = "beschriftung";
    beschriftung.textContent = eintrag.titel;
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    taste.append(beschriftung, rueckmeldung);
    if (eintrag.hilfe) {
      const hinweis = this._fragezeichen(eintrag.titel, eintrag.hilfe);
      hinweis.classList.add("auf-taste");
      taste.appendChild(hinweis);
    }

    taste.addEventListener("click", async () => {
      if (taste.disabled) return;
      // **Läuft die Ladung, bricht dieselbe Taste sie ab – und tut sonst
      // nichts.** Bis 1.5.0 hing diese Bedingung zusätzlich an der
      // Betriebswahl und ihrem Rückkehrmuster. Fehlte eines von beiden, fiel
      // der Druck durch bis zum Auslöser und startete die Ladung **noch
      // einmal**. Von außen sah das aus, als passierte gar nichts: „lädt
      // gerade" stand sofort wieder da, ohne Rückfrage, ohne Meldung. Genau
      // so war es gemeldet worden.
      if (laeuft()) {
        await this._ladungAbbrechen(eintrag, taste, rueckmeldung);
        return;
      }

      // Zu warm für eine Ladung: Die Anlage nimmt den Auftrag gar nicht an,
      // und die Taste stünde minutenlang auf „wird ausgeführt …". Lieber
      // gleich sagen, warum nichts passiert.
      if (eintrag.ist && eintrag.soll) {
        const ist = this._zahl(eintrag.ist);
        const soll = this._zahl(eintrag.soll);
        const abstand = Number(eintrag.abstand) || 0;
        if (ist !== null && soll !== null && ist > soll - abstand) {
          this._abgelehnt(
            taste,
            rueckmeldung,
            `schon ${Math.round(ist)} °C – erst ab ${Math.round(soll - abstand)} °C`
          );
          return;
        }
      }

      if (eintrag.frage && !(await this._bestaetigen(eintrag.titel, eintrag.frage))) return;
      taste.disabled = true;
      try {
        await this._uebertragen(
          rueckmeldung,
          async () => {
            // Auf Standby ist der Kreis abgeschaltet und nimmt den
            // Ladeauftrag nicht an. Nur dann wird vorher umgeschaltet – wer
            // im Heiz- oder Absenkbetrieb lädt, soll den nicht verlieren.
            if (eintrag.betriebswahl && eintrag.betriebswahl_aus && eintrag.betriebswahl_ww) {
              const jetzt = this._zustand(eintrag.betriebswahl);
              // Was jetzt eingestellt ist, gilt als Rückkehrpunkt.
              if (jetzt && !OHNE_WERT.includes(String(jetzt.state).toLowerCase())) {
                this._wahlVorLadung[eintrag.betriebswahl] = jetzt.state;
              }
              const aus = new RegExp(eintrag.betriebswahl_aus, "i");
              if (jetzt && aus.test(jetzt.state)) {
                const ww = this._optionWie(eintrag.betriebswahl, eintrag.betriebswahl_ww);
                if (ww) {
                  await this._hass.callService("select", "select_option", {
                    entity_id: eintrag.betriebswahl,
                    option: ww,
                  });
                }
              }
            }
            return bereich === "button"
              ? this._hass.callService("button", "press", { entity_id: eintrag.entity })
              : this._hass.callService(
                  "homeassistant",
                  eintrag.zustand_an ? "turn_on" : "toggle",
                  { entity_id: eintrag.entity }
                );
          },
          // Bestätigt ist der Auftrag, wenn die Anlage anfängt zu laden. Hier
          // steht sie noch – der Abbruch ist oben schon abgebogen.
          bereich === "button" ? null : () => laeuft()
        );
        this._nachfassen(eintrag);
      } finally {
        taste.disabled = false;
      }
    });

    this._bindungen.push(() => {
      const zustand = this._zustand(eintrag.entity);
      const an = laeuft();
      taste.classList.toggle("an", an);
      // Läuft die Ladung, sagt die Taste, was ein Druck jetzt bewirkt.
      const abbrechbar = an && !!eintrag.titel_abbrechen && !!eintrag.betriebswahl;
      beschriftung.textContent = abbrechbar ? eintrag.titel_abbrechen : eintrag.titel;
      taste.classList.toggle("abbrechen", abbrechbar);
      // Solange eine Übertragung läuft, gehört die Zeile der Rückmeldung.
      if (rueckmeldung.dataset.belegt === "1") return;
      rueckmeldung.className = "rueckmeldung";
      rueckmeldung.textContent = eintrag.zustand_an
        ? (an ? "läuft" : "bereit")
        : this._tastenZustand(bereich, zustand, an);
    });
    return taste;
  }

  /**
   * Ein Eingriff, den die Anlage gar nicht erst annimmt.
   *
   * Zweimal rot aufblitzen und kurz sagen, woran es liegt – danach steht
   * wieder der Zustand da. Ein Dialog wäre für „geht gerade nicht" zu viel,
   * ein stummes Nichts zu wenig.
   */
  /**
   * Eine laufende Warmwasserladung beenden.
   *
   * Beendet wird über die **Betriebswahl**. Der Auslöser (`2/16`) taugt dafür
   * nicht: Er fällt zurück, sobald die Anlage den Auftrag angenommen hat, und
   * hat danach keinen Zustand mehr, den man zurücknehmen könnte.
   *
   * Geht es nicht, sagt die Taste warum. Ein stummes Nichts ist hier das
   * Schlimmste – es sieht aus wie eine kaputte Oberfläche und war es bis
   * 1.5.0 auch: Der Druck landete beim Auslöser und lud erneut.
   */
  async _ladungAbbrechen(eintrag, taste, rueckmeldung) {
    if (!eintrag.betriebswahl) {
      this._abgelehnt(taste, rueckmeldung, "keine Betriebswahl gefunden");
      return;
    }
    const ziel = this._rueckkehrWahl(eintrag);
    if (!ziel) {
      this._abgelehnt(taste, rueckmeldung, "kein Programm in der Betriebswahl");
      return;
    }
    taste.disabled = true;
    try {
      await this._uebertragen(
        rueckmeldung,
        () =>
          this._hass.callService("select", "select_option", {
            entity_id: eintrag.betriebswahl,
            option: ziel,
          }),
        // **Ohne die Ladepumpe.** Die läuft nach (`5/5` „Modus
        // Ladepumpennachlauf"), und solange sie läuft, gälte die Ladung als
        // aktiv: Die Rückmeldung hinge auf „wird ausgeführt …", obwohl das
        // Umschalten längst durch ist.
        () => !this._laedtLautBetriebsart(eintrag)
      );
      delete this._wahlVorLadung[eintrag.betriebswahl];
      this._nachfassen(eintrag);
    } finally {
      taste.disabled = false;
    }
  }

  /**
   * Der Eintrag der Betriebswahl, auf den nach einer Ladung zurückgestellt wird.
   *
   * Erste Wahl ist der Zustand **vor** der Ladung – blind auf ein Programm zu
   * stellen beendete sonst stillschweigend einen laufenden Heiz- oder
   * Absenkbetrieb. Ist er unbekannt (etwa nach einem Neuladen der Seite oder
   * wenn die Ladung am Gerät gestartet wurde), greift das Zeitprogramm.
   */
  _rueckkehrWahl(eintrag) {
    const gemerkt = this._wahlVorLadung[eintrag.betriebswahl];
    if (gemerkt) return gemerkt;
    // **Nie ein Programm raten.** Bis 1.5.0-beta.5 suchte diese Stelle den
    // ersten Eintrag, der wie ein Zeitprogramm aussah. Das ging genau so
    // lange gut, bis jemand ein zweites Mal drückte: Der gemerkte Zustand war
    // schon verbraucht, die Ladung nach dem ersten Druck noch als laufend
    // gemeldet – und die Taste stellte die Anlage kommentarlos auf
    // „Heizprogramm 1", das der Nutzer nie gewählt hatte.
    //
    // Ist der Zustand von vor der Ladung unbekannt, wird stattdessen die
    // **aktuelle** Betriebswahl erneut geschrieben. Sie ist die dauerhafte
    // Wahl; die Ladung liegt nur vorübergehend darüber. Sie erneut zu setzen
    // beendet den vorübergehenden Zustand und kann nichts verstellen – sie
    // steht ja schon so.
    const jetzt = this._zustand(eintrag.betriebswahl);
    if (!jetzt || OHNE_WERT.includes(String(jetzt.state).toLowerCase())) return null;
    return jetzt.state;
  }

  /**
   * Lädt die Anlage laut Betriebsart – ohne die nachlaufende Ladepumpe.
   *
   * Für die Anzeige zählt die Pumpe mit: Sie ist der handfeste Beleg, dass
   * gerade geladen wird. Für die Bestätigung eines Abbruchs zählt sie
   * gerade nicht.
   */
  _laedtLautBetriebsart(eintrag) {
    if (!eintrag.zustand_an) return false;
    const zustand = this._zustand(eintrag.zustand_an);
    if (!zustand || OHNE_WERT.includes(String(zustand.state).toLowerCase())) return false;
    return (eintrag.zustand_wenn || []).includes(zustand.state);
  }

  _abgelehnt(taste, anzeige, grund) {
    anzeige.dataset.belegt = "1";
    anzeige.className = "rueckmeldung fehler";
    anzeige.textContent = grund;
    taste.classList.remove("blinkt");
    // Neustart der Animation erzwingen: Ohne das Auslesen läuft sie beim
    // zweiten Druck nicht noch einmal.
    void taste.offsetWidth;
    taste.classList.add("blinkt");
    window.setTimeout(() => taste.classList.remove("blinkt"), 1200);
    this._freigeben(anzeige, RUECKMELDUNG_MS);
  }
  };
