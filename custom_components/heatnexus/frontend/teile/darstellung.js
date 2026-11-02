/**
 * Fenster „Darstellung“ und Anfang der Kopfzeile; Mixin von `heatnexus-panel.js`.
 * Die Einstellungen gelten für alle Reiter und stehen deshalb nicht in „Ansicht bearbeiten“.
 */

import { DARSTELLUNG, DARSTELLUNG_STANDARD, KOPFSTILE, PALETTEN, darstellungSpeicher } from "../ordnung.js";
import { zeichenKnoten } from "../zeichen.js";

export const DarstellungMixin = (Basis) =>
  class extends Basis {
    /**
     * Eine Wahl der Darstellung: gespeichert oder vorab aus dem Browser, damit nichts umspringt.
     * Ein unbekannter Wert fällt auf den Standard zurück, sonst auf den ersten Eintrag der Liste.
     */
    _stilwahl(schluessel) {
      return (this._vorschau && this._vorschau[schluessel]) || this._stilGespeichert(schluessel);
    }

    /** Die gespeicherte Wahl, ohne die Vorschau des offenen Fensters. */
    _stilGespeichert(schluessel) {
      const stile = DARSTELLUNG[schluessel];
      const wert = this._einstellungen()[schluessel] || this._gemerkt(darstellungSpeicher(schluessel));
      if (stile.some((eintrag) => eintrag.schluessel === wert)) return wert;
      return DARSTELLUNG_STANDARD[schluessel] || stile[0].schluessel;
    }

    _gemerkt(speicher) {
      try {
        return window.localStorage.getItem(speicher) || "";
      } catch (err) {
        return "";
      }
    }

    /** Die Darstellung im Browser ablegen; ein gesperrter Speicher darf nichts umwerfen. */
    _einstellungenMerken() {
      const einstellungen = this._einstellungen();
      try {
        for (const schluessel of Object.keys(DARSTELLUNG)) {
          const wert = einstellungen[schluessel];
          if (wert) window.localStorage.setItem(darstellungSpeicher(schluessel), wert);
          else window.localStorage.removeItem(darstellungSpeicher(schluessel));
        }
      } catch (err) {
        /* Ohne Browserspeicher bleibt es beim Flackern, nicht bei einem Fehler. */
      }
    }

    /** Der Farbsatz von Oberfläche und Schaubild. */
    _farbsatz() {
      return this._stilwahl("farbsatz");
    }

    /** Die Marke in der Kopfzeile. */
    _kopfstil() {
      return this._stilwahl("kopf");
    }

    /** Ob das Zeichen selbst die Seitenleiste öffnet oder eine eigene Menütaste davor steht. */
    _menuestil() {
      return this._stilwahl("menue");
    }

    /** Wie „Alle“ mehrere Anlagen zeigt: jede für sich oder gleiche Karten in einem Rahmen. */
    _alleStil() {
      return this._stilwahl("alle");
    }

    /** Was ein Kopfstil zeigt: Name in Farbe, Hersteller darunter. */
    _kopfmerkmale(stil) {
      return KOPFSTILE.find((eintrag) => eintrag.schluessel === stil) || KOPFSTILE[0];
    }

    _darstellungSetzen(teil) {
      this._einstellungSetzen(teil, "Die Darstellung konnte nicht gespeichert werden.");
    }

    /** Menütaste, Zeichen und Wortmarke am Anfang der Kopfzeile. */
    _kopfanfang() {
      const stil = this._kopfstil();
      const { farbig, unterzeile } = this._kopfmerkmale(stil);
      const block = document.createElement("div");
      block.className = ["markenblock", farbig && "farbig", !unterzeile && "kurz"].filter(Boolean).join(" ");
      block.dataset.roh = "";
      const knoten = [block];
      if (this._menuestil() === "taste") {
        const taste = this._seitenleisteTaste("seitenleiste-taste");
        taste.appendChild(this._symbolKnoten("mdi:menu"));
        knoten.unshift(taste);
        block.appendChild(zeichenKnoten());
      } else {
        const taste = this._seitenleisteTaste("zeichen-taste");
        taste.appendChild(zeichenKnoten());
        block.appendChild(taste);
      }
      block.appendChild(this._wortmarke(stil));
      return knoten;
    }

    /**
     * Klappt die Seitenleiste von Home Assistant ein und aus, mit dem Ereignis der
     * eigenen Ansichten von Home Assistant; `composed` lässt es aus dem Schattenbaum.
     */
    _seitenleisteTaste(klasse) {
      const taste = document.createElement("button");
      taste.className = `menue-taste ${klasse}`;
      taste.type = "button";
      taste.title = this._t("Seitenleiste anzeigen (Karten, Energie, Einstellungen)");
      taste.setAttribute("aria-label", this._t("Seitenleiste anzeigen"));
      taste.addEventListener("click", () => {
        this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
      });
      return taste;
    }

    /** „HeatNexus“ je nach Kopfstil: einfarbig oder im Verlauf des Zeichens, mit oder ohne Hersteller darunter. */
    _wortmarke(stil) {
      const { farbig, unterzeile } = this._kopfmerkmale(stil);
      const schrift = document.createElement("div");
      schrift.className = farbig ? "wortmarke farbig" : "wortmarke";
      const marke = document.createElement("div");
      marke.className = "marke";
      if (farbig) {
        for (const [klasse, text] of [["heat", "Heat"], ["nexus", "Nexus"]]) {
          const teil = document.createElement("span");
          teil.className = klasse;
          teil.textContent = text;
          marke.appendChild(teil);
        }
      } else {
        marke.textContent = "HeatNexus";
      }
      schrift.appendChild(marke);
      if (unterzeile) {
        const hersteller = document.createElement("div");
        hersteller.className = "unterzeile";
        hersteller.textContent = "Windhager";
        schrift.appendChild(hersteller);
      }
      return schrift;
    }

    /** Die Oberfläche zeigt den Entwurf als Vorschau; `null` beendet sie. Gespeichert wird nichts. */
    _vorschauZeigen(entwurf) {
      if (!entwurf && !this._vorschau) return;
      this._vorschau = entwurf ? { ...entwurf } : null;
      this._gebaut = false;
      if (!this._abgebaut) this._zeichnen();
    }

    /** Das Fenster „Darstellung“: Ein Klick zeigt die Wahl sofort, „Übernehmen“ speichert, „Verwerfen“ stellt zurück. */
    _darstellungOeffnen() {
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog darstellung";

      const ueberschrift = document.createElement("h3");
      ueberschrift.className = "dialog-titel";
      ueberschrift.textContent = this._t("Darstellung");
      const hinweis = document.createElement("p");
      hinweis.className = "dialog-text";
      hinweis.textContent = this._t("Gilt für alle Reiter und das Schaubild, nur für dich.");
      dialog.append(ueberschrift, hinweis);

      const entwurf = {};
      const wert = (schluessel) => (schluessel in entwurf ? entwurf[schluessel] : this._stilGespeichert(schluessel));
      const geaendert = () => Object.keys(entwurf).filter((schluessel) => entwurf[schluessel] !== this._stilGespeichert(schluessel));

      const leiste = document.createElement("div");
      leiste.className = "dialog-leiste";
      const schliessen = document.createElement("button");
      schliessen.type = "button";
      schliessen.className = "dialog-taste";
      const uebernehmen = document.createElement("button");
      uebernehmen.type = "button";
      uebernehmen.className = "dialog-taste akzent";
      uebernehmen.textContent = this._t("Übernehmen");
      leiste.append(schliessen, uebernehmen);
      const leisteStellen = () => {
        const offen = geaendert().length > 0;
        uebernehmen.hidden = !offen;
        schliessen.textContent = this._t(offen ? "Verwerfen" : "Schließen");
        schliessen.classList.toggle("betont", offen);
      };
      leisteStellen();

      const nachWahl = [leisteStellen, () => this._vorschauZeigen(entwurf)];
      const wahl = (name, art, schluessel) => {
        const waehlen = (stil) => {
          entwurf[schluessel] = stil;
          nachWahl.forEach((stellen) => stellen());
        };
        return this._darstellungGruppe(name, art, DARSTELLUNG[schluessel], () => wert(schluessel), waehlen);
      };
      const groesse = this._darstellungUnterwahl(
        this._t("Nur bei „Umbrechen“"),
        wahl(this._t("Größe je Anlagenteil"), "strang_groesse", "strang_groesse")
      );
      const groesseStellen = () => this._unterwahlStellen(groesse, wert("strang") === "umbrechen");
      nachWahl.push(groesseStellen);
      groesseStellen();

      const zeilen = [
        [this._t("Farbsatz"), this._t("Gilt für Oberfläche und Schaubild."), wahl(this._t("Farbsatz"), "farben", "farbsatz")],
        [this._t("Kopfzeile"), this._t("Legt Zeichen und Namen oben links fest."), wahl(this._t("Kopfzeile"), "kopf", "kopf")],
        [this._t("Seitenleiste"), this._t("Legt fest, wie sich die Seitenleiste öffnet."), wahl(this._t("Seitenleiste"), "menue", "menue")],
        [
          this._t("Schaubild"),
          this._t("Legt fest, wie die Anlagenteile bei wenig Platz stehen."),
          wahl(this._t("Schaubild"), "strang", "strang"),
          groesse,
        ],
      ];
      if (this._anlagen().length > 1) {
        zeilen.push([this._t("Alle Anlagen"), this._t("Gilt für den Reiter „Alle“."), wahl(this._t("Alle Anlagen"), "alle", "alle")]);
      }
      zeilen.forEach(([name, text, ...inhalt]) => dialog.appendChild(this._darstellungZeile(name, text, inhalt)));
      dialog.appendChild(leiste);

      schleier.appendChild(dialog);
      const verwerfen = () => this._vorschauZeigen(null);
      const weg = this._dialogOeffnen(schleier, { fokus: schliessen, beiAbbruch: verwerfen });
      schliessen.addEventListener("click", () => {
        weg();
        verwerfen();
      });
      uebernehmen.addEventListener("click", () => {
        const teil = Object.fromEntries(geaendert().map((schluessel) => [schluessel, entwurf[schluessel]]));
        weg();
        this._vorschau = null;
        this._darstellungSetzen(teil);
      });
    }

    /** Eine Zeile im Fenster: Name und Erklärung links, die Wahl rechts; schmal untereinander. */
    _darstellungZeile(name, text, inhalt) {
      const zeile = document.createElement("section");
      zeile.className = "darstellung-zeile";
      const kopf = document.createElement("div");
      const titel = document.createElement("h4");
      titel.className = "darstellung-name";
      titel.textContent = name;
      const erklaerung = document.createElement("p");
      erklaerung.className = "darstellung-erklaerung";
      erklaerung.textContent = text;
      kopf.append(titel, erklaerung);
      const rechts = document.createElement("div");
      rechts.className = "darstellung-inhalt";
      rechts.append(...inhalt);
      zeile.append(kopf, rechts);
      return zeile;
    }

    /** Eine Wahl, die nur bei einer anderen gilt: mit eigenem Namen und dem Hinweis, wann sie wirkt. */
    _darstellungUnterwahl(bedingung, wahl) {
      const block = document.createElement("div");
      block.className = "darstellung-unter";
      const kopf = document.createElement("div");
      kopf.className = "unter-name";
      const name = document.createElement("span");
      name.textContent = wahl.getAttribute("aria-label");
      const hinweis = document.createElement("span");
      hinweis.className = "unter-bedingung";
      hinweis.textContent = bedingung;
      kopf.append(name, hinweis);
      block.append(kopf, wahl);
      return block;
    }

    /** Gilt die Wahl gerade nicht, wird sie blass und nimmt keinen Klick an; der Hinweis sagt warum. */
    _unterwahlStellen(block, gilt) {
      block.classList.toggle("aus", !gilt);
      block.querySelector(".unter-bedingung").hidden = gilt;
      block.querySelectorAll("button").forEach((taste) => {
        taste.disabled = !gilt;
      });
    }

    /** Vorschaukacheln für eine Einstellung; die gewählte ist markiert. */
    _darstellungGruppe(name, art, eintraege, gewaehlt, setzen) {
      const wahl = document.createElement("div");
      wahl.className = `darstellung-wahl ${art}`;
      wahl.setAttribute("role", "group");
      wahl.setAttribute("aria-label", name);
      const markieren = () => {
        [...wahl.children].forEach((kachel) => kachel.setAttribute("aria-pressed", String(kachel.dataset.wert === gewaehlt())));
      };
      eintraege.forEach((eintrag) => {
        const kachel = document.createElement("button");
        kachel.type = "button";
        kachel.className = "darstellung-muster";
        kachel.dataset.wert = eintrag.schluessel;
        kachel.title = this._t(eintrag.hinweis);
        const beschriftung = document.createElement("span");
        beschriftung.className = "muster-name";
        beschriftung.textContent = this._t(eintrag.titel);
        if (art !== "strang_groesse") kachel.appendChild(this._darstellungVorschau(art, eintrag.schluessel));
        kachel.appendChild(beschriftung);
        kachel.addEventListener("click", () => {
          setzen(eintrag.schluessel);
          markieren();
        });
        wahl.appendChild(kachel);
      });
      markieren();
      return wahl;
    }

    /** Zwei Anlagen in zwei Farben: je Anlage eine Reihe oder je Kartenart ein Paar. */
    _alleVorschau(bild, zusammen) {
      bild.className = zusammen ? "alle-vorschau zusammen" : "alle-vorschau";
      const gruppen = zusammen ? [["a", "b"], ["a", "b"], ["a", "b"]] : [["a", "a", "a"], ["b", "b", "b"]];
      gruppen.forEach((gruppe) => {
        const reihe = document.createElement("span");
        reihe.className = "gruppe";
        gruppe.forEach((anlage) => {
          const feld = document.createElement("i");
          feld.className = anlage;
          reihe.appendChild(feld);
        });
        bild.appendChild(reihe);
      });
      return bild;
    }

    /** Ein kleiner Strang aus Kärtchen an einer Leitung: zwei Reihen beim Umbrechen, eine kleinere beim Verkleinern. */
    _strangVorschau(bild, schluessel) {
      bild.className = `strang-vorschau ${schluessel}`;
      const strang = document.createElement("span");
      strang.className = "strang";
      (schluessel === "umbrechen" ? [3, 2] : [5]).forEach((anzahl) => {
        const reihe = document.createElement("span");
        reihe.className = "gruppe";
        for (let nr = 0; nr < anzahl; nr += 1) reihe.appendChild(document.createElement("i"));
        strang.appendChild(reihe);
      });
      bild.appendChild(strang);
      return bild;
    }

    /** Das kleine Bild auf einer Kachel: ein Ausschnitt der Oberfläche, wie ihn die Wahl zeigt. */
    _darstellungVorschau(art, schluessel) {
      const bild = document.createElement("div");
      bild.dataset.roh = "";
      if (art === "farben") {
        bild.className = "farb-vorschau";
        const satz = PALETTEN[schluessel];
        if (satz) {
          bild.style.background = satz["--hn-grund"];
          for (const [klasse, farbe] of [["balken", satz["--hn-akzent"]], ["flaeche", satz["--hn-karte"]]]) {
            const teil = document.createElement("i");
            teil.className = klasse;
            teil.style.background = farbe;
            bild.appendChild(teil);
          }
        } else {
          const dunkel = PALETTEN.dunkel["--hn-grund"];
          const hell = PALETTEN.hell["--hn-grund"];
          bild.style.background = `linear-gradient(135deg, ${dunkel} 50%, ${hell} 50%)`;
        }
        return bild;
      }
      if (art === "alle") return this._alleVorschau(bild, schluessel === "zusammen");
      if (art === "strang") return this._strangVorschau(bild, schluessel);
      bild.className = "kopf-vorschau";
      if (art === "menue" && schluessel === "taste") bild.appendChild(this._symbolKnoten("mdi:menu"));
      bild.appendChild(zeichenKnoten());
      if (art === "menue" && schluessel === "zeichen") bild.appendChild(this._symbolKnoten("mdi:cursor-default-click-outline"));
      if (art === "kopf") bild.appendChild(this._wortmarke(schluessel));
      if (art === "menue") bild.appendChild(document.createElement("i"));
      return bild;
    }
  };
