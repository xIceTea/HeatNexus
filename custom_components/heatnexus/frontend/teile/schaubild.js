/**
 * Das Anlagenschaubild in der Übersicht.
 *
 * Die Zeichnung kommt fertig als SVG aus der Integration (`schema.py`); hier
 * werden die Live-Werte daraufgesetzt und die Pumpen in Bewegung gebracht.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import { farbenUmstellen, schaubildAdresse, schriftmass } from "../ordnung.js";

export const SchaubildMixin = (Basis) =>
  class extends Basis {
  // -------------------------------------------------------------------
  // Schaubild
  // -------------------------------------------------------------------
  /**
   * Welcher Farbsatz gezeigt wird.
   *
   * `auto` folgt Home Assistant; ohne dessen Auskunft bleibt es beim dunklen
   * Satz, denn ein falsch geratenes Hell fiele stärker auf.
   */
  _schemaBild(anlage) {
    const farben = anlage.schema_farben || {};
    return schaubildAdresse(farbenUmstellen(anlage.schema_svg, farben[this._farbsatzGilt()]));
  }

  /**
   * Wie groß die Marken im Schaubild stehen. Die Karte überschreibt das.
   * Die Oberfläche zeigt das Bild über die volle Breite, dort tragen die
   * Werte die größere Stufe.
   */
  _schriftmass() {
    return schriftmass("gross");
  }

  /** Ob die Pumpen als Marke im Bild stehen. Die Karte darf sie abwählen. */
  _zeigtPumpen() {
    return true;
  }

  /** Ob der Mischer im Bild steht. Die Karte darf ihn abwählen. */
  _zeigtMischer() {
    return true;
  }

  /** Überschrift über dem Bild. Die Karte setzt eine eigene oder gar keine. */
  _bildtitel() {
    return "Anlagenübersicht";
  }

  /** Der Satz, der gerade gilt – `auto` folgt dem Erscheinungsbild. */
  _farbsatzGilt() {
    const satz = this._farbsatz();
    if (satz && satz !== "auto") return satz;
    const themen = this._hass && this._hass.themes;
    return themen && themen.darkMode === false ? "hell" : "dunkel";
  }

  /**
   * Eine Grundfarbe im gerade geltenden Satz.
   *
   * Die Überlagerungen liegen über dem Bild und erben dessen Farben nicht;
   * sie müssen denselben Austausch mitmachen.
   */
  _farbe(anlage, rolle) {
    const dunkel = (anlage.schema_grundfarben || {})[rolle];
    if (!dunkel) return null;
    const tabelle = (anlage.schema_farben || {})[this._farbsatzGilt()];
    return (tabelle && tabelle[dunkel]) || dunkel;
  }

  /**
   * Ob ein Speicher gerade geladen oder entnommen wird.
   *
   * Die Ladepumpe allein genügt nicht: Sie läuft auch, wenn der Kessel direkt
   * in einen Heizkreis fährt. Wärme geht in den Speicher, solange der Kessel
   * den oberen Bereich hält – gegen Ende der Ladung liegen beide gleichauf.
   */
  _speicherzustand(eintrag) {
    const pumpe = eintrag.laden ? this._foerdert(eintrag.laden) : false;
    const kessel = eintrag.kessel ? this._zahl(eintrag.kessel) : null;
    const oben = eintrag.oben ? this._zahl(eintrag.oben) : null;
    const waermer =
      kessel === null || oben === null ? true : kessel > oben - (Number(eintrag.toleranz) || 0);
    const laedt = pumpe && waermer;
    return { laedt, zieht: (eintrag.entnahme || []).some((e) => this._foerdert(e)) };
  }

  /**
   * Ein Laufrad als eigene Zeichnung statt eines Symbols.
   *
   * Der Kasten liegt symmetrisch um den Nullpunkt, und die drei Schaufeln
   * stehen exakt 120 Grad auseinander – so dreht es sich rund statt zu eiern.
   */
  _laufrad() {
    // Der Kasten aus HTML trägt die Drehung, das SVG nur die Zeichnung.
    const huelle = document.createElement("span");
    huelle.className = "rad";
    const rad = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    rad.setAttribute("viewBox", "-12 -12 24 24");
    rad.innerHTML =
      '<g fill="currentColor">' +
      '<path d="M 0 0 L -1.74 -9.85 A 10 10 0 0 1 7.88 -6.16 Z"/>' +
      '<path d="M 0 0 L 9.40 3.42 A 10 10 0 0 1 1.39 9.90 Z"/>' +
      '<path d="M 0 0 L -7.66 6.43 A 10 10 0 0 1 -9.27 -3.75 Z"/>' +
      '<circle r="2.4"/></g>';
    huelle.appendChild(rad);
    return huelle;
  }

  _schaubild(anlage) {
    if (!anlage.schema_svg) return null;
    const karte = this._karte(this._bildtitel());
    const huelle = document.createElement("div");
    huelle.className = "schaubild";
    // Eine Einheit der Zeichnung, ausgedrückt in der Breite der Karte. Alles
    // Aufgesetzte rechnet damit und wächst mit dem Bild – in der schmalen
    // Vorschau wie im breiten Dashboard.
    if (anlage.schema_breite) {
      huelle.style.setProperty("--hn-einheit", `${(100 / anlage.schema_breite).toFixed(4)}cqw`);
    }
    // Das Schriftmaß der Marken. Die Karte gibt es vor, die Oberfläche bleibt
    // beim Normalmaß.
    huelle.style.setProperty("--hn-schrift", String(this._schriftmass()));
    const bild = document.createElement("img");
    const anfangsbild = this._schemaBild(anlage);
    bild.src = anfangsbild;
    bild.alt = "Anlagenschaubild";
    huelle.appendChild(bild);

    // **Der Farbsatz wird hier gewählt, nicht serverseitig.** Die Zeichnung
    // kommt einmal und wird hier eingefärbt; die Aufteilung entsteht in
    // Python, lange bevor jemand das Erscheinungsbild umschaltet. Die Auswahl
    // hängt deshalb an einer Bindung, die bei jedem Abgleich mitläuft.
    if (anlage.schema_farben) {
      // Gemerkt statt am Bild abgelesen: Ein `<img>` macht aus der Daten-URL
      // beim Zurücklesen nicht zwingend dieselbe Zeichenfolge, und ein
      // vermeintlicher Unterschied setzte die Quelle bei jedem Abgleich neu.
      let gezeigt = anfangsbild;
      this._bindungen.push(() => {
        const gewuenscht = this._schemaBild(anlage);
        if (gewuenscht !== gezeigt) {
          gezeigt = gewuenscht;
          bild.src = gewuenscht;
        }
      });
    }

    // Strömung: zwei Bänder auf Vor- und Rücklauf. Sie laufen, solange
    // irgendeine Pumpe der Anlage fördert – steht alles, steht auch das Bild.
    const leitungen = anlage.schema_leitungen;
    if (leitungen) {
      ["vorlauf", "ruecklauf"].forEach((richtung) => {
        const band = document.createElement("div");
        band.className = `fluss ${richtung}`;
        band.style.left = leitungen.left;
        band.style.width = leitungen.width;
        band.style.top = leitungen[`${richtung}_top`];
        huelle.appendChild(band);
        this._bindungen.push(() => {
          band.classList.toggle("laeuft", this._foerdertEtwas(anlage));
        });
      });
    }

    // Glutbett im Kessel. Die Helligkeit folgt der Leistung: Bei 30 % glimmt
    // es, bei Volllast leuchtet es.
    (anlage.schema_brenner || []).forEach((eintrag) => {
      const glut = document.createElement("div");
      glut.className = "glut";
      glut.style.left = eintrag.left;
      glut.style.top = eintrag.top;
      glut.style.width = eintrag.breite;
      huelle.appendChild(this._klickbar(glut, eintrag.entity || eintrag.ersatz));
      this._bindungen.push(() => {
        // Die Leistung ist der beste Massstab. Meldet die Anlage keine, dient
        // die Brennkammertemperatur als Ersatz: unter 100 Grad glimmt nichts,
        // ab 500 laeuft der Kessel voll, darueber bleibt es bei voll - heisser
        // heisst nicht mehr Leistung.
        const leistung = eintrag.entity ? this._zahl(eintrag.entity) : null;
        let anteil = null;
        let text = "";
        if (leistung !== null) {
          anteil = Math.max(0, Math.min(100, leistung)) / 100;
          text = `${Math.round(leistung)} %`;
        } else if (eintrag.ersatz) {
          const grad = this._zahl(eintrag.ersatz);
          if (grad !== null) {
            const kalt = Number(eintrag.ersatz_min) || 100;
            const heiss = Number(eintrag.ersatz_max) || 500;
            anteil = Math.max(0, Math.min(1, (grad - kalt) / (heiss - kalt)));
            text = `${Math.round(grad)} °C`;
          }
        }
        const brennt = anteil !== null && anteil > 0;
        glut.classList.toggle("brennt", brennt);
        glut.style.opacity = brennt ? String(0.35 + anteil * 0.65) : "0";
        glut.title = `${eintrag.titel} – ${brennt ? text : "aus"}`;
      });
    });

    // Mischerstellung. Bewusst keine Dauerbewegung: Eine Mischerstellung ist
    // ein Zustand, kein Vorgang – ein sich drehendes Ventil läse sich wie eine
    // Pumpe, und die dreht sich daneben schon. Der Anzeiger schwenkt zwischen
    // Rücklauf (0 %) und Vorlauf (100 %), das Stück Leitung darüber färbt sich
    // nach der Beimischung. Bewegt wird nur der Übergang.
    (this._zeigtMischer() ? anlage.schema_mischer || [] : []).forEach((eintrag) => {
      const stutzen = document.createElement("div");
      stutzen.className = "mischer-stutzen";
      stutzen.style.left = eintrag.left;
      stutzen.style.top = eintrag.stutzen_top;
      stutzen.style.height = eintrag.stutzen_hoehe;
      huelle.appendChild(stutzen);

      const marke = document.createElement("div");
      marke.className = "mischer";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      marke.style.width = eintrag.groesse;
      marke.style.height = eintrag.groesse;
      const zeiger = document.createElement("div");
      zeiger.className = "zeiger";
      marke.appendChild(zeiger);
      huelle.appendChild(this._klickbar(marke, eintrag.entity));

      this._bindungen.push(() => {
        const stellwert = this._zahl(eintrag.entity);
        const da = stellwert !== null;
        marke.hidden = !da;
        stutzen.hidden = !da;
        if (!da) return;
        const anteil = Math.max(0, Math.min(100, stellwert)) / 100;
        // −60° steht auf dem Rücklaufschenkel, +60° auf dem Vorlauf.
        zeiger.style.transform = `rotate(${-60 + anteil * 120}deg)`;
        stutzen.style.background = `color-mix(in oklab, ${this._farbe(
          anlage,
          "vorlauf"
        )} ${Math.round(anteil * 100)}%, ${this._farbe(anlage, "ruecklauf")})`;
        marke.title = `${eintrag.titel} – Mischer ${Math.round(stellwert)} %`;
      });
    });

    // Der Heizkörper nimmt die Farbe dessen an, was durch ihn fließt: kalt in
    // der Farbe des Rücklaufs, heiß in der des Vorlaufs – dieselben beiden
    // Farben wie die waagrechten Leitungen. Ab zwei Dritteln der Skala pulsiert
    // er leicht; dann arbeitet der Kreis wirklich.
    (anlage.schema_heizkoerper || []).forEach((eintrag) => {
      const koerper = document.createElement("div");
      koerper.className = "heizkoerper";
      koerper.style.left = eintrag.left;
      koerper.style.top = eintrag.top;
      koerper.style.width = eintrag.breite;
      koerper.style.height = eintrag.hoehe;
      // Ein Element je Glied, gesetzt in **Anteilen der Ebenenbreite**. Die
      // Karte skaliert das Bild auf ihre eigene Breite; feste Bildpunkte
      // säßen danach neben den gezeichneten Gliedern.
      const glieder = [];
      const raster = Number.parseFloat(eintrag.raster);
      for (let i = 0; i < (eintrag.anzahl || 0); i++) {
        const glied = document.createElement("div");
        glied.className = "glied";
        glied.style.left = `${(raster * i).toFixed(4)}%`;
        glied.style.width = eintrag.glied;
        koerper.appendChild(glied);
        glieder.push(glied);
      }
      huelle.appendChild(koerper);

      this._bindungen.push(() => {
        const grad = this._zahl(eintrag.entity);
        koerper.classList.toggle("da", grad !== null);
        if (grad === null) return;
        const spanne = Number(eintrag.heiss) - Number(eintrag.kalt);
        const anteil =
          spanne > 0 ? Math.max(0, Math.min(1, (grad - Number(eintrag.kalt)) / spanne)) : 0;
        // Oben etwas wärmer als unten – so wirkt das Glied rund, wie in der
        // Zeichnung, und der Übergang bleibt an derselben Stelle.
        const teil = Math.round(anteil * 100);
        const vor = this._farbe(anlage, "vorlauf");
        const rueck = this._farbe(anlage, "ruecklauf");
        const warm = `color-mix(in oklab, ${vor} ${teil}%, ${rueck})`;
        const kuehl = `color-mix(in oklab, ${this._farbe(anlage, "warm")} ${teil}%, ${this._farbe(
          anlage,
          "kalt"
        )})`;
        // Zwei Lagen je Glied: links die Glanzkante, die das Glied rund
        // wirken lässt, darunter der Verlauf von warm nach kühl.
        const glanz =
          "linear-gradient(to right, transparent 0 18%, " +
          "rgba(255, 255, 255, 0.18) 18% 46%, transparent 46%)";
        const fuellung = `${glanz}, linear-gradient(to bottom, ${warm}, ${kuehl})`;
        glieder.forEach((glied) => {
          glied.style.background = fuellung;
        });
        koerper.classList.toggle("heiss", anteil > 0.66);
        koerper.title = `${eintrag.titel} – Vorlauf ${this._text(eintrag.entity)}`;
      });
    });

    // Die Schichtung des Puffers. Oben und unten sind zwei echte Fühler
    // (21/65 TPE, 21/66 TPA) – die Grenze dazwischen wandert also mit, statt
    // eine feste Zeichnung zu sein. Durchgeladen heißt: beide gleich warm,
    // also durchgehend eine Farbe.
    (anlage.schema_schichtung || []).forEach((eintrag) => {
      const koerper = document.createElement("div");
      koerper.className = "schichtung";
      koerper.style.left = eintrag.left;
      koerper.style.top = eintrag.top;
      koerper.style.width = eintrag.breite;
      koerper.style.height = eintrag.hoehe;
      koerper.style.borderRadius = eintrag.ecke;
      // Ohne Messwerte derselbe Verlauf, den die Zeichnung sonst selbst
      // gemalt hätte – er kommt vom Server, damit die Farben nicht an zwei
      // Stellen gepflegt werden müssen.
      koerper.style.background = eintrag.grund;
      // **Vor** das Bild, nicht dahinter. Die Zeichnung lässt den
      // Speicherkörper frei, wenn ein Fühlerwert da ist; die Farbe scheint
      // durch das Loch, und Kontur, Dämmnähte, Stutzen und Register bleiben
      // darüber sichtbar. Lag die Farbe oben, deckte sie all das zu und der
      // Speicher sah aus wie ein Klotz.
      huelle.insertBefore(koerper, huelle.firstChild);

      this._bindungen.push(() => {
        const oben = this._zahl(eintrag.oben);
        // Der Boiler meldet nur einen Istwert – dann bleibt `unten` leer und
        // der Inhalt wird gleichmäßig eingefärbt.
        const unten = eintrag.unten ? this._zahl(eintrag.unten) : null;
        const geschichtet = eintrag.unten !== null && eintrag.unten !== undefined;
        const da = oben !== null && (!geschichtet || unten !== null);
        koerper.classList.toggle("da", da);
        if (!da) {
          // Zurück auf den neutralen Verlauf. Ohne das bliebe die letzte
          // Färbung stehen und behauptete Messwerte, die es nicht gibt.
          koerper.style.background = eintrag.grund;
          koerper.title = `${eintrag.titel} – kein Fühlerwert`;
          return;
        }
        const spanne = Number(eintrag.heiss) - Number(eintrag.kalt);
        const farbe = (grad) => {
          const anteil =
            spanne > 0 ? Math.max(0, Math.min(1, (grad - Number(eintrag.kalt)) / spanne)) : 0;
          return `color-mix(in oklab, ${this._farbe(anlage, "warm")} ${Math.round(
            anteil * 100
          )}%, ${this._farbe(anlage, "kalt")})`;
        };
        if (!geschichtet) {
          koerper.style.background = farbe(oben);
          koerper.title = `${eintrag.titel} – ${this._text(eintrag.oben)}`;
          return;
        }
        // Die Haltepunkte liegen auf den gezeichneten Dämmnähten: Der
        // Speicherkörper reicht von y=116 bis y=296, die drei Nähte sitzen
        // bei 168, 206 und 244 – also bei 29 %, 50 % und 71 %. Der obere
        // Fühler beherrscht alles bis zur ersten Naht, der untere alles ab
        // der dritten, dazwischen liegt die Sprungschicht mittig auf der
        // mittleren. Vorher endete der obere Bereich bei 30 % und die
        // Mischfarbe saß bei 62 % – beides zwischen den Nähten, und genau
        // das ließ die Färbung gegenüber der Zeichnung verrutscht aussehen.
        koerper.style.background =
          `linear-gradient(to bottom, ${farbe(oben)} 0%, ${farbe(oben)} 29%, ` +
          `${farbe((oben + unten) / 2)} 50%, ${farbe(unten)} 71%, ${farbe(unten)} 100%)`;
        koerper.title =
          `${eintrag.titel} – oben ${this._text(eintrag.oben)}, ` +
          `unten ${this._text(eintrag.unten)}`;
      });
    });

    // Betriebslampen: am Pumpen-/Relaismodul die Klemmen und die Lampe des
    // Gehäuses, am Wärmeerzeuger der Punkt in seiner Zeichnung. Sie liegen als
    // eigene Ebene über dem Bild – die Zeichnung im <img> kennt keine Zustände.
    (anlage.schema_lampen || []).forEach((eintrag) => {
      const lampe = document.createElement("div");
      lampe.className = ["lampe", eintrag.art, eintrag.zweck].filter(Boolean).join(" ");
      lampe.style.left = eintrag.left;
      lampe.style.top = eintrag.top;
      // Nur die Breite setzen: „groesse" ist ein Anteil der Bild*breite*.
      // Auf die Höhe angewandt ergäbe derselbe Prozentsatz einen anderen
      // Bildpunktwert – die Lampe wurde oval. `aspect-ratio` hält sie rund.
      lampe.style.width = eintrag.groesse;
      huelle.appendChild(lampe);
      this._bindungen.push(() => {
        // Am Modul zählt der Analog-Sollwert, am Erzeuger die Leistung. Fehlt
        // sie, dient die Brennkammertemperatur als Ersatz.
        let wert = eintrag.entity ? this._zahl(eintrag.entity) : null;
        let schwelle = 0;
        if (wert === null && eintrag.ersatz) {
          wert = this._zahl(eintrag.ersatz);
          schwelle = Number(eintrag.ersatz_min) || 0;
        }
        const an = wert !== null && wert > schwelle;
        lampe.classList.toggle("an", an);
        if (eintrag.zweck === "erzeuger") {
          lampe.title = `${eintrag.titel} – ${an ? "in Betrieb" : "aus"}`;
        } else {
          lampe.title = an
            ? `${eintrag.titel} – fordert ${Math.round(wert)} °C`
            : `${eintrag.titel} – keine Anforderung`;
        }
      });
    });

    // Die Übergabe selbst: Solange angefordert wird, glimmt es im Gehäuse,
    // das Laufrad dreht sich langsam und die Wärme geht nach außen ab. Das
    // gezeichnete Rad steht still, deshalb liegt hier ein eigenes darüber.
    (anlage.schema_uebergabe || []).forEach((eintrag) => {
      const feld = document.createElement("div");
      feld.className = "uebergabe";
      feld.style.left = eintrag.left;
      feld.style.top = eintrag.top;
      feld.style.width = eintrag.breite;
      feld.style.height = eintrag.hoehe;
      feld.style.borderRadius = eintrag.ecke;
      feld.innerHTML =
        '<span class="glut"></span><span class="glut zwei"></span>' +
        '<span class="welle"></span><span class="welle"></span><span class="welle"></span>';
      huelle.appendChild(feld);

      const rad = document.createElement("div");
      rad.className = "uebergabe-rad";
      rad.style.left = eintrag.rad_left;
      rad.style.top = eintrag.rad_top;
      rad.style.width = eintrag.rad_groesse;
      rad.appendChild(this._laufrad());
      huelle.appendChild(this._klickbar(rad, eintrag.entity));

      this._bindungen.push(() => {
        const soll = this._zahl(eintrag.entity);
        const an = soll !== null && soll > 0;
        feld.classList.toggle("an", an);
        rad.classList.toggle("an", an);
        rad.title = an
          ? `${eintrag.titel} – gibt Wärme ab, ${Math.round(soll)} °C`
          : `${eintrag.titel} – keine Übergabe`;
      });
    });

    // Wärmeanforderung: Steht der Analog-Sollwert über null, fordert das
    // Modul gerade Wärme an – und mit welcher Temperatur.
    (anlage.schema_anforderung || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "speicher anforderung";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      huelle.appendChild(marke);
      this._bindungen.push(() => {
        const soll = this._zahl(eintrag.entity);
        const an = soll !== null && soll > 0;
        marke.classList.toggle("laedt", an);
        marke.textContent = an ? `fordert ${Math.round(soll)} °C` : "";
        marke.title = `${eintrag.titel} – ${an ? "Wärmeanforderung" : "keine Anforderung"}`;
      });
    });

    // Puffer: lädt, entlädt oder steht. Zwei Temperaturen allein sagen keine
    // Richtung – maßgeblich ist, welche Pumpe fördert.
    (anlage.schema_speicher || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "speicher";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      huelle.appendChild(marke);
      this._bindungen.push(() => {
        const { laedt, zieht } = this._speicherzustand(eintrag);
        marke.classList.toggle("laedt", laedt);
        marke.classList.toggle("entlaedt", !laedt && zieht);
        marke.textContent = laedt ? "lädt" : zieht ? "entlädt" : "";
        marke.title = `${eintrag.titel} – ${marke.textContent || "keine Förderung"}`;
      });
    });

    (anlage.schema_werte || []).forEach((eintrag) => {
      const marke = document.createElement("div");
      marke.className = "marke-wert";
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      huelle.appendChild(this._klickbar(marke, eintrag.entity));
      this._bindungen.push(() => {
        // Ohne Wert keine Marke: Ein „–" mitten im Heizkörper sah aus wie ein
        // Symbol und nicht wie ein fehlender Messwert.
        const da = this._hatWert(eintrag.entity);
        marke.hidden = !da;
        marke.textContent = da ? this._text(eintrag.entity) : "";
      });
    });

    // Pumpen liegen als eigene Marken auf dem Bild: Ein Standbild kann sich
    // nicht drehen, und ohne Bewegung sieht man der Anlage nicht an, ob
    // gerade etwas fließt.
    // Die senkrechten Stichleitungen: Sie strömen nur, solange die Pumpe
    // dieses Anlagenteils fördert. Erst daran sieht man, wohin die Wärme
    // gerade geht – die waagrechten Leitungen allein zeigen nur, dass
    // überhaupt etwas läuft.
    (anlage.schema_pumpen || []).forEach((eintrag) => {
      ["vorlauf", "ruecklauf"].forEach((richtung) => {
        const hoehe = eintrag[`${richtung}_hoehe`];
        if (!hoehe) return;
        const band = document.createElement("div");
        band.className = `fluss senkrecht ${richtung}`;
        band.dataset.teil = eintrag.titel;
        band.style.left = eintrag.left;
        band.style.top = eintrag[`${richtung}_top`];
        band.style.height = hoehe;
        huelle.appendChild(band);
        const speicher = (anlage.schema_speicher || []).find((s) => s.titel === eintrag.titel);
        this._bindungen.push(() => {
          // Am Speicher zählen beide Richtungen: Seine eigene Pumpe lädt ihn,
          // die Pumpen der Verbraucher entnehmen ihm – und dabei steht die
          // Ladepumpe.
          const stroemt =
            this._foerdert(eintrag.entity) ||
            (eintrag.entnahme || []).some((e) => this._foerdert(e));
          band.classList.toggle("laeuft", stroemt);
          // Ein Wärmeerzeuger strömt andersherum als ein Verbraucher: Das kalte
          // Wasser kommt von unten herauf, das heiße verlässt ihn nach oben in
          // den Vorlauf. Beim Speicher hängt es davon ab, ob er gerade lädt.
          const zustand = speicher && this._speicherzustand(speicher);
          const entnimmt = !!zustand && !zustand.laedt && zustand.zieht;
          band.classList.toggle("rueckwaerts", !!eintrag.erzeuger || entnimmt);
        });
      });
    });

    (this._zeigtPumpen() ? anlage.schema_pumpen || [] : []).forEach((eintrag) => {
      // Der Kessel führt die Pufferladepumpe nur für seine Stichleitung. Eine
      // Pumpenmarke gehört dort nicht hin: An der Stelle sitzt keine.
      if (eintrag.nur_strang) return;
      const marke = document.createElement("div");
      marke.className = "pumpe";
      marke.title = `${eintrag.titel} – Pumpe`;
      marke.style.left = eintrag.left;
      marke.style.top = eintrag.top;
      marke.appendChild(this._laufrad());
      huelle.appendChild(this._klickbar(marke, eintrag.entity));
      this._bindungen.push(() => {
        // Manche Pumpen melden keinen Zustand, sondern ihre Drehzahl.
        const zahl = this._zahl(eintrag.entity);
        const laeuft = zahl !== null ? zahl > 0 : this._istAn(eintrag.entity);
        marke.classList.toggle("laeuft", laeuft);
        marke.title = `${eintrag.titel} – Pumpe ${laeuft ? "läuft" : "steht"}`;
      });
    });

    karte.appendChild(huelle);
    return karte;
  }
  };
