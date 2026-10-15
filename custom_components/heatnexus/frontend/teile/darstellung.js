/**
 * Fenster „Darstellung“ und Anfang der Kopfzeile; Mixin von `heatnexus-panel.js`.
 * Die Einstellungen gelten für alle Reiter und stehen deshalb nicht in „Ansicht bearbeiten“.
 */

import { DARSTELLUNG, KOPFSTILE, PALETTEN, darstellungSpeicher } from "../ordnung.js";
import { zeichenKnoten } from "../zeichen.js";

export const DarstellungMixin = (Basis) =>
  class extends Basis {
    /**
     * Eine Wahl der Darstellung: gespeichert oder vorab aus dem Browser, damit nichts umspringt.
     * Ein unbekannter Wert fällt auf den ersten Eintrag der Liste zurück.
     */
    _stilwahl(schluessel) {
      const stile = DARSTELLUNG[schluessel];
      const wert = this._einstellungen()[schluessel] || this._gemerkt(darstellungSpeicher(schluessel));
      return stile.some((eintrag) => eintrag.schluessel === wert) ? wert : stile[0].schluessel;
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

    /** Das Fenster „Darstellung“: Gewählt wird im Entwurf, „Übernehmen“ speichert, „Verwerfen“ lässt alles stehen. */
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
      const wert = (schluessel) => (schluessel in entwurf ? entwurf[schluessel] : this._stilwahl(schluessel));
      const geaendert = () => Object.keys(entwurf).filter((schluessel) => entwurf[schluessel] !== this._stilwahl(schluessel));

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

      const gruppen = [
        ["Farbsatz", "farben", "farbsatz"],
        ["Kopfzeile", "kopf", "kopf"],
        ["Seitenleiste", "menue", "menue"],
      ];
      if (this._anlagen().length > 1) gruppen.push(["Alle Anlagen", "alle", "alle"]);
      gruppen.forEach(([name, art, schluessel]) => {
        const waehlen = (stil) => {
          entwurf[schluessel] = stil;
          leisteStellen();
        };
        dialog.appendChild(this._darstellungGruppe(name, art, DARSTELLUNG[schluessel], () => wert(schluessel), waehlen));
      });
      dialog.appendChild(leiste);

      schleier.appendChild(dialog);
      const weg = this._dialogOeffnen(schleier, { fokus: schliessen });
      schliessen.addEventListener("click", weg);
      uebernehmen.addEventListener("click", () => {
        const teil = Object.fromEntries(geaendert().map((schluessel) => [schluessel, entwurf[schluessel]]));
        weg();
        this._darstellungSetzen(teil);
      });
    }

    /** Eine Reihe Vorschaukacheln für eine Einstellung; die gewählte ist markiert. */
    _darstellungGruppe(name, art, eintraege, gewaehlt, setzen) {
      const gruppe = document.createElement("section");
      const titel = document.createElement("h4");
      titel.className = "darstellung-name";
      titel.textContent = this._t(name);
      const wahl = document.createElement("div");
      wahl.className = `darstellung-wahl ${art}`;
      wahl.setAttribute("role", "group");
      wahl.setAttribute("aria-label", this._t(name));
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
        kachel.append(this._darstellungVorschau(art, eintrag.schluessel), beschriftung);
        kachel.addEventListener("click", () => {
          setzen(eintrag.schluessel);
          markieren();
        });
        wahl.appendChild(kachel);
      });
      markieren();
      gruppe.append(titel, wahl);
      return gruppe;
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

    /** Das kleine Bild auf einer Kachel: Farben, Wortmarke oder Menütaste. */
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
      bild.className = "kopf-vorschau";
      if (art === "menue" && schluessel === "taste") bild.appendChild(this._symbolKnoten("mdi:menu"));
      bild.appendChild(zeichenKnoten());
      if (art === "menue" && schluessel === "zeichen") bild.appendChild(this._symbolKnoten("mdi:cursor-default-click-outline"));
      if (art === "kopf") bild.appendChild(this._wortmarke(schluessel));
      return bild;
    }
  };
