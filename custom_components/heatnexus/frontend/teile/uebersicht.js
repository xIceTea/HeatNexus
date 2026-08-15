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

import {
  ABBRUCH_PAUSE_MS,
  ABBRUCH_VERSUCHE,
  ANNAHME_MS,
  OHNE_WERT,
  RUECKMELDUNG_MS,
  SPERRE_MS,
} from "../ordnung.js";

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
   * In einer gemeinsamen Hülle wären beide in einer Spalte ein einziger
   * Block und könnten nicht getrennt aufrücken.
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
        const aktiv = this._stoerungAktiv(eintrag);
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

    // **Eine einzelne Taste nimmt die ganze Zeile.** Welche Tasten eine Anlage
    // hergibt, entscheidet sie selbst: Am Kessel sind es Reinigung, Wartung
    // und Serviceausbrand, an einem reinen Heizkreis bleibt „Warmwasser laden"
    // allein übrig. Im zweispaltigen Raster stand sie dann als halbe Kachel
    // neben einem leeren Platz.
    const tasten = eintraege.filter((eintrag) => eintrag.entity.split(".")[0] !== "select");
    const alleinstehend = tasten.length === 1;

    eintraege.forEach((eintrag) => {
      if (eintrag.entity.split(".")[0] === "select") {
        const huelle = this._auswahlFeld(eintrag.titel, eintrag.entity, eintrag.hilfe);
        huelle.style.gridColumn = "1 / -1";
        gitter.appendChild(huelle);
        return;
      }
      const taste = this._bedientaste(eintrag, false);
      if (alleinstehend) taste.style.gridColumn = "1 / -1";
      gitter.appendChild(taste);
    });

    karte.appendChild(gitter);
    return karte;
  }

  /** Eine Kachel, die einen Befehl auslöst – mit Rückfrage und Rückmeldung. */
  _bedientaste(eintrag, breit) {
    const bereich = eintrag.entity.split(".")[0];
    // Manche Bedienungen melden ihren Zustand woanders: Die Warmwasserladung
    // steht in der Betriebsart, ihr Auslöser fällt sofort zurück.
    const lautAnlage = () => {
      // **Die Betriebsart hat das letzte Wort.** Sie sagt, was die Anlage
      // gerade tut. Die Ladepumpe ist nur ein Indiz: Sie **läuft nach**
      // (`5/5` „Modus Ladepumpennachlauf") und drehte sich nach einem
      // beendeten Auftrag noch minutenlang weiter. Solange sie hier vorne
      // stand, meldete die Taste erneut „läuft", bot ein zweites Mal
      // Abbrechen an – und der Nutzer brach eine Ladung ab, die es nicht
      // mehr gab.
      if (eintrag.zustand_an) {
        const zustand = this._zustand(eintrag.zustand_an);
        if (zustand && !OHNE_WERT.includes(String(zustand.state).toLowerCase())) {
          return (eintrag.zustand_wenn || []).includes(zustand.state);
        }
      }
      // Erst wenn die Betriebsart nichts hergibt, zählt die Pumpe. An einem
      // Kreis mit nur einem zulässigen Wert (`allowed: [0]`) meldet die
      // Betriebsart den Ladezustand gar nicht.
      if (eintrag.zustand_pumpe && this._istAn(eintrag.zustand_pumpe)) return true;
      return this._istAn(eintrag.entity);
    };
    // Zwischen Druck und Antwort der Anlage liegt ein Abrufabstand. Bis dahin
    // gilt, was gedrückt wurde – sonst sähe es aus, als sei nichts passiert.
    const laeuft = () => {
      const echt = lautAnlage();
      const angenommen = this._ladungAnnahme(eintrag.entity, echt);
      return angenommen === null ? echt : angenommen;
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
      // nichts.** Die Bedingung darf nicht zusätzlich an der Betriebswahl
      // hängen: Fehlt die, fällt der Druck durch bis zum Auslöser und startet
      // die Ladung **noch einmal**. Von außen sieht das aus, als passiere gar
      // nichts – „lädt gerade" steht sofort wieder da.
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
              const bekannt = jetzt && !OHNE_WERT.includes(String(jetzt.state).toLowerCase());
              const aus = new RegExp(eintrag.betriebswahl_aus, "i");
              if (bekannt && aus.test(jetzt.state)) {
                const ww = this._optionWie(eintrag.betriebswahl, eintrag.betriebswahl_ww);
                if (ww) {
                  await this._hass.callService("select", "select_option", {
                    entity_id: eintrag.betriebswahl,
                    option: ww,
                  });
                  // Nur was hier verstellt wurde, wird später zurückgestellt.
                  // Während einer Ladung meldet die Anlage von sich aus
                  // WW-Betrieb und kehrt danach allein zum vorherigen Stand
                  // zurück; das Bediengerät schreibt zum Abbrechen ebenfalls
                  // nur die Freigabe auf Nein.
                  this._wahlVorLadung[eintrag.betriebswahl] = jetzt.state;
                }
              }
            }
            if (bereich === "button") {
              await this._hass.callService("button", "press", { entity_id: eintrag.entity });
            } else {
              await this._hass.callService(
                "homeassistant",
                eintrag.zustand_an ? "turn_on" : "toggle",
                { entity_id: eintrag.entity }
              );
            }
            // Erst hier, nach dem gelungenen Aufruf: Eine abgewiesene
            // Bedienung darf die Taste nicht sperren.
            if (eintrag.zustand_an) this._ladungAnnehmen(eintrag.entity, true);
          },
          // Bestätigt ist der Auftrag, wenn die Anlage anfängt zu laden.
          // **Ohne die eigene Annahme** – die sagt sonst sofort ja, und die
          // Rückmeldung meldete Erfolg, bevor die Anlage etwas getan hat.
          bereich === "button" ? null : () => lautAnlage()
        );
        this._nachfassen(eintrag);
      } finally {
        zeichnen();
      }
    });

    const zeichnen = () => {
      const zustand = this._zustand(eintrag.entity);
      const an = laeuft();
      taste.classList.toggle("an", an);
      // Läuft die Ladung, sagt die Taste, was ein Druck jetzt bewirkt.
      const abbrechbar =
        an && !!eintrag.titel_abbrechen && !!(eintrag.betriebswahl || bereich === "switch");
      beschriftung.textContent = abbrechbar ? eintrag.titel_abbrechen : eintrag.titel;
      taste.classList.toggle("abbrechen", abbrechbar);
      // **Kein zweiter Druck, solange der erste noch unterwegs ist.** Er
      // träfe auf den alten Zustand und kehrte den ersten wieder um.
      // `.taste[disabled]` blendet ab und zeigt den Warte-Zeiger.
      taste.disabled = this._ladungWartet(eintrag.entity);
      // Solange eine Übertragung läuft, gehört die Zeile der Rückmeldung.
      if (rueckmeldung.dataset.belegt === "1") return;
      rueckmeldung.className = "rueckmeldung";
      rueckmeldung.textContent = eintrag.zustand_an
        ? (an ? "läuft" : "bereit")
        : this._tastenZustand(bereich, zustand, an);
    };
    taste._zeichnen = zeichnen;
    this._bindungen.push(zeichnen);
    return taste;
  }

  /**
   * Was die Taste nach einem Druck annimmt, bis die Anlage antwortet.
   *
   * Die Anlage wird alle 30 s abgefragt. Ohne diese Annahme stand nach einem
   * „Warmwasser laden abbrechen" bis zum nächsten Abruf unverändert „läuft"
   * da – es sah aus, als sei der Druck ins Leere gegangen.
   */
  _ladungAnnehmen(entity, laeuft) {
    this._ladungAnnahmen = this._ladungAnnahmen || {};
    this._ladungAnnahmen[entity] = { laeuft, seit: Date.now() };
  }

  /**
   * Ist der letzte Druck noch unterwegs? Dann bleibt die Taste gesperrt.
   *
   * Nicht an die Annahme gekoppelt: Die hält bis zu 45 s und wird erst
   * verbraucht, wenn die Anlage dasselbe meldet. Übernimmt sie den Auftrag
   * nicht, bliebe die Taste die ganze Zeit gesperrt.
   */
  _ladungWartet(entity) {
    const merk = this._ladungAnnahmen && this._ladungAnnahmen[entity];
    return !!merk && Date.now() - merk.seit < SPERRE_MS;
  }

  /**
   * Die Annahme, solange sie gilt – sonst `null`.
   *
   * Verbraucht wird sie, sobald die Anlage dasselbe meldet oder die Zeit um
   * ist. Beides muss sein: Ohne das Erste bliebe die Taste nach einer
   * bestätigten Bedienung unnötig gesperrt, ohne das Zweite für immer, wenn
   * die Anlage den Auftrag gar nicht angenommen hat.
   */
  _ladungAnnahme(entity, echt) {
    const merk = this._ladungAnnahmen && this._ladungAnnahmen[entity];
    if (!merk) return null;
    if (echt === merk.laeuft || Date.now() - merk.seit >= ANNAHME_MS) {
      delete this._ladungAnnahmen[entity];
      return null;
    }
    return merk.laeuft;
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
   * Beendet wird über **beides**: den Auslöser (`2/16`) zurücknehmen und, wenn
   * bekannt, die Betriebswahl auf den Stand von vor der Ladung stellen. Als
   * Anzeige taugt der Auslöser nicht – er fällt zurück, sobald die Anlage den
   * Auftrag angenommen hat –, als Gegenbewegung schon: Er hat die Ladung
   * gestartet.
   *
   * Geht es nicht, sagt die Taste warum. Ein stummes Nichts ist hier das
   * Schlimmste – es sieht aus wie eine kaputte Oberfläche und war es bis
   * 1.5.0 auch: Der Druck landete beim Auslöser und lud erneut.
   */
  async _ladungAbbrechen(eintrag, taste, rueckmeldung) {
    // **Der Auslöser wird immer zurückgenommen.** Er hat die Ladung gestartet;
    // ihn auszuschalten ist die unmittelbare Gegenbewegung und kann nichts
    // verstellen.
    const ausloeser =
      eintrag.entity && eintrag.entity.startsWith("switch.") ? eintrag.entity : null;
    const ziel = eintrag.betriebswahl ? this._rueckkehrWahl(eintrag) : null;
    const steht = eintrag.betriebswahl ? this._zustand(eintrag.betriebswahl) : null;
    // **Denselben Wert noch einmal zu schreiben ändert an der Anlage nichts.**
    // Ist der Zustand von vor der Ladung unbekannt – Seite neu geladen, oder
    // am Gerät gestartet –, fällt `_rueckkehrWahl` auf die *aktuelle*
    // Betriebswahl zurück. Als alleiniger Abbruch wäre das ein Schreibvorgang
    // ohne Wirkung: Die Ladung liefe weiter und „wird ausgeführt …" stünde
    // daneben, bis jemand ein zweites Mal drückt.
    const wahlWirkt = !!ziel && !(steht && steht.state === ziel);

    if (!ausloeser && !eintrag.betriebswahl) {
      this._abgelehnt(taste, rueckmeldung, "keine Betriebswahl gefunden");
      return;
    }
    if (!ausloeser && !wahlWirkt) {
      this._abgelehnt(taste, rueckmeldung, "kein Programm in der Betriebswahl");
      return;
    }
    taste.disabled = true;
    try {
      await this._uebertragen(
        rueckmeldung,
        async () => {
          if (ausloeser) {
            await this._hass.callService("switch", "turn_off", { entity_id: ausloeser });
          }
          if (wahlWirkt) {
            await this._hass.callService("select", "select_option", {
              entity_id: eintrag.betriebswahl,
              option: ziel,
            });
          }
          // Ab jetzt gilt „steht" – bis die Anlage widerspricht oder die
          // Annahme verfällt. Erst hier, damit ein abgewiesener Aufruf die
          // Taste nicht sperrt.
          this._ladungAnnehmen(eintrag.entity, false);
        },
        // **Ohne die Ladepumpe.** Die läuft nach (`5/5` „Modus
        // Ladepumpennachlauf"), und solange sie läuft, gälte die Ladung als
        // aktiv: Die Rückmeldung hinge auf „wird ausgeführt …", obwohl das
        // Umschalten längst durch ist.
        () => !this._laedtLautBetriebsart(eintrag)
      );
      delete this._wahlVorLadung[eintrag.betriebswahl];
      this._nachfassen(eintrag);
      this._abbruchNachsetzen(eintrag, ausloeser);
    } finally {
      // Nicht blind freigeben: Ob die Taste jetzt gesperrt gehört, entscheidet
      // die Annahme, nicht dieser Ablauf.
      if (taste._zeichnen) taste._zeichnen();
      else taste.disabled = false;
    }
  }

  /**
   * Einen Abbruch nachsetzen, den die Anlage überging.
   *
   * Erst lesen, dann schreiben: Meldet die Betriebsart weiter eine Ladung,
   * geht die Freigabe noch einmal auf Nein. Nur die Freigabe – sie ist ein
   * Zustand (`2/16`, Nein/Ja) und gefahrlos wiederholbar, ein zusätzlicher
   * Betriebswahl-Befehl macht den Abbruch dagegen unwirksam.
   *
   * Die Ladepumpe zählt nicht mit: Sie läuft nach und belegt keine Ladung.
   */
  async _abbruchNachsetzen(eintrag, ausloeser) {
    if (!ausloeser) return;
    // Wer inzwischen erneut gedrückt hat, hat das letzte Wort – sonst
    // beendet ein altes Nachsetzen eine frisch gestartete Ladung.
    this._abbruchLauf = this._abbruchLauf || {};
    const marke = (this._abbruchLauf[ausloeser] || 0) + 1;
    this._abbruchLauf[ausloeser] = marke;

    for (let versuch = 0; versuch < ABBRUCH_VERSUCHE; versuch++) {
      await new Promise((weiter) => window.setTimeout(weiter, ABBRUCH_PAUSE_MS));
      if (this._abbruchLauf[ausloeser] !== marke || !this._hass) return;
      if (!this._laedtLautBetriebsart(eintrag)) return;
      try {
        await this._hass.callService("switch", "turn_off", { entity_id: ausloeser });
      } catch (err) {
        console.warn("HeatNexus: Abbruch liess sich nicht wiederholen", err);
        return;
      }
      this._nachfassen(eintrag);
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
    // **Nie ein Programm raten.** Den ersten Eintrag zu nehmen, der wie ein
    // Zeitprogramm aussieht, geht bis zum zweiten Druck gut: Dann ist der
    // gemerkte Zustand verbraucht, die Ladung aber noch als laufend gemeldet –
    // und die Taste stellte die Anlage kommentarlos auf ein Programm, das
    // niemand gewählt hat.
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
