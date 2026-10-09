/**
 * Reiter „Automatik“: Einladung, Einrichtungsdialog und Einstellungen.
 *
 * Der Dialog holt seine Auswahllisten über `heatnexus/automatik/kandidaten`
 * und schreibt über `heatnexus/automatik/einrichten` bzw. `einstellen`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

import { AUSRICHTUNGEN, FELDER, HEIZFLAECHEN, PROFILE, PROFIL_JE_FLAECHE, VERALTET_STUNDEN, zahl } from "./automatik.js";

// So lange steht „übernommen ✓“ neben den Tasten.
const GESPEICHERT_MS = 4000;

// Die Einstellungen in Gruppen; „heizbetrieb“ und „absenkbetrieb“ sind die Heizgrenzen der Steuerung.
export const EINSTELLUNGSGRUPPEN = [
  ["Heizgrenze", ["profil", "heizbetrieb", "absenkbetrieb", "grenze_versatz", "hysterese", "tau_h"]],
  ["Sonnentag", ["sonnenquote", "sonnentag", "absenkung_k", "stark", "stark_k"]],
  ["Zeitplan", ["entscheidung", "nachpruefung", "mindestdauer_h", "budget"]],
  ["Schutz und Prognose", ["rueckkehr_k", "spielraum_k", "ruhe_h", "fenster_k_je_h", "anpassen", "lernfenster"]],
  ["Manuell mit Empfehlung", ["melden"]],
];

export const EinrichtungMixin = (Basis) =>
  class extends Basis {
    // --- Einstellungen -------------------------------------------------
    /**
     * Karte „Einstellungen“ in vier Gruppen. Speichern ist erst aktiv, wenn ein
     * Feld vom gespeicherten Wert abweicht; die Heizgrenzen gehen an die Steuerung.
     */
    _automatikErweitert(kreis, daten, darf) {
      const bereich = document.createElement("details");
      bereich.className = "karte automatik-erweitert";
      // Offen bleibt offen, auch wenn Speichern oder Nachladen die Karte neu baut.
      this._automatikOffen = this._automatikOffen || new Set();
      bereich.open = this._automatikOffen.has(kreis.heizkreis);
      bereich.addEventListener("toggle", () => {
        if (bereich.open) this._automatikOffen.add(kreis.heizkreis);
        else {
          // Zuklappen verwirft, was nicht gespeichert ist, und gibt das Nachladen frei.
          this._automatikOffen.delete(kreis.heizkreis);
          this._automatikEntwurfVerwerfen(kreis.heizkreis);
        }
      });
      const felder = this._automatikEinstellungsfelder(kreis, daten, darf);
      const { eingaben, grenzen, anfang } = felder;

      const tasten = document.createElement("div");
      tasten.className = "automatik-einstellungstasten";
      const zuruecksetzen = this._automatikTaste("Profilwerte wiederherstellen", "automatik-knopf leise");
      zuruecksetzen.disabled = !darf || !felder.abweichend;
      zuruecksetzen.addEventListener("click", () => this._automatikSpeichern(kreis, { eigene: {} }));
      const speichern = this._automatikTaste("Speichern", "automatik-knopf speichern");
      speichern.addEventListener("click", () => this._automatikAllesSpeichern(kreis, eingaben, grenzen, anfang));
      // Das Hinweiszeichen nach dem Neuaufbau sagt, dass das Speichern geklappt hat.
      if (this._automatikGespeichert === kreis.heizkreis) {
        this._automatikGespeichert = null;
        const hinweis = document.createElement("span");
        hinweis.className = "automatik-gespeichert";
        hinweis.textContent = this._t("übernommen ✓");
        tasten.append(hinweis);
        setTimeout(() => hinweis.remove(), GESPEICHERT_MS);
      }
      tasten.append(zuruecksetzen, speichern);
      bereich.append(this._automatikEinstellungskopf(kreis, felder.abweichend), tasten);

      // Ein Entwurf überdauert jeden Neuaufbau, bis gespeichert oder zugeklappt wird.
      const entwurf = this._automatikEntwurf(kreis.heizkreis);
      const namen = new Map([...Object.entries(eingaben).map(([n, [, e]]) => [e, n]), ...Object.entries(grenzen).map(([n, e]) => [e, n])]);
      const pruefen = () => {
        namen.forEach((name, eingabe) => {
          if (eingabe.value === anfang.get(eingabe)) delete entwurf[name];
          else entwurf[name] = eingabe.value;
        });
        speichern.disabled = !darf || !Object.keys(entwurf).length;
        this._automatikBearbeitet = this._automatikHatEntwurf();
      };
      namen.forEach((name, eingabe) => {
        if (name in entwurf) eingabe.value = entwurf[name];
        eingabe.addEventListener("input", pruefen);
        eingabe.addEventListener("change", pruefen);
      });
      pruefen();

      const gruppen = document.createElement("div");
      gruppen.className = "automatik-gruppen";
      EINSTELLUNGSGRUPPEN.forEach(([ueberschrift, gruppenNamen]) => {
        const gruppe = document.createElement("section");
        gruppe.className = "automatik-einstellungsgruppe";
        const kopfzeile = document.createElement("h4");
        kopfzeile.textContent = this._t(ueberschrift);
        gruppe.appendChild(kopfzeile);
        gruppenNamen.forEach((name) => felder.zeilen[name] && gruppe.appendChild(felder.zeilen[name]));
        gruppen.appendChild(gruppe);
      });
      bereich.appendChild(gruppen);

      const leiste = document.createElement("div");
      leiste.className = "automatik-leiste";
      const entfernen = this._automatikTaste("Automatik entfernen", "automatik-knopf leise warnung");
      entfernen.disabled = !darf;
      entfernen.addEventListener("click", () => this._automatikEntfernen(kreis));
      const neuLernen = this._automatikTaste("Hausmodell neu lernen", "automatik-knopf leise");
      neuLernen.disabled = !darf;
      neuLernen.addEventListener("click", () => this._automatikHausmodellNeu(kreis));
      leiste.append(neuLernen, entfernen);
      bereich.appendChild(leiste);
      return bereich;
    }

    /** Die Zeilen der Einstellungen mit ihren Eingaben und dem gespeicherten Stand. */
    _automatikEinstellungsfelder(kreis, daten, darf) {
      const vorgabe = kreis.vorgabe || (daten.profile || {})[kreis.konfig.profil] || {};
      const k = kreis.kennwerte || {};
      const eingaben = {};
      const grenzen = {};
      const zeilen = { profil: this._automatikProfilZeile(kreis, darf) };
      zeilen.heizbetrieb = this._automatikGrenzZeile("Heizbetrieb bis", k.grenze_steuerung, 0, 30, darf, grenzen, "heizbetrieb");
      zeilen.absenkbetrieb = this._automatikGrenzZeile("Absenkbetrieb bis", k.grenze_absenk, -10, 20, darf, grenzen, "absenkbetrieb");
      let abweichend = 0;
      FELDER.forEach((feld) => {
        const wert = (kreis.werte || {})[feld.name];
        const basis = vorgabe[feld.name];
        const geaendert = wert !== basis;
        if (geaendert) abweichend += 1;
        const basisText = typeof basis === "number" ? zahl(basis, Number.isInteger(basis) ? 0 : 1) : basis || "–";
        const anzeige = feld.art === "janein" ? this._t(basis ? "Ein" : "Aus") : `${basisText} ${feld.einheit ? this._t(feld.einheit) : ""}`.trim();
        const zeile = this._automatikFeld(feld.titel, geaendert ? this._tMit("Profil: {wert}", { wert: anzeige || "–" }) : "", geaendert, feld.hilfe);
        const eingabe = this._automatikEingabe(feld, wert, darf);
        eingabe.setAttribute("aria-label", this._t(feld.titel));
        eingaben[feld.name] = [feld, eingabe];
        zeile.querySelector(".eingabe").appendChild(eingabe);
        if (feld.einheit && feld.art !== "wahl") {
          const einheit = document.createElement("span");
          einheit.className = "einheit";
          einheit.textContent = this._t(feld.einheit);
          zeile.querySelector(".eingabe").appendChild(einheit);
        }
        zeilen[feld.name] = zeile;
      });
      const anfang = new Map(
        [...Object.values(eingaben).map(([, e]) => e), ...Object.values(grenzen)].map((e) => [e, e.value])
      );
      return { zeilen, eingaben, grenzen, anfang, abweichend };
    }

    /** Kopf der Karte: Pfeil, Titel und das Profil mit der Zahl eigener Werte. */
    _automatikEinstellungskopf(kreis, abweichend) {
      const kopf = document.createElement("summary");
      kopf.className = "automatik-einstellungskopf";
      const titelblock = document.createElement("div");
      titelblock.className = "titelblock";
      const titel = document.createElement("h3");
      titel.textContent = this._t("Einstellungen");
      const unter = document.createElement("div");
      unter.className = "unter";
      const profil = PROFILE.find(([name]) => name === kreis.konfig.profil);
      const profilText = this._tMit("Profil „{profil}“", { profil: this._t(profil ? profil[1] : kreis.konfig.profil || "–") });
      unter.textContent = abweichend
        ? `${profilText} · ${this._tMit(abweichend === 1 ? "{zahl} Wert weicht ab" : "{zahl} Werte weichen ab", { zahl: abweichend })}`
        : profilText;
      titelblock.append(titel, unter);
      kopf.append(this._symbolKnoten("mdi:chevron-down", "pfeil"), titelblock);
      return kopf;
    }

    /** Der nicht gespeicherte Stand eines Kreises, Feldname → Eingabe. */
    _automatikEntwurf(heizkreis) {
      this._automatikEntwuerfe = this._automatikEntwuerfe || {};
      this._automatikEntwuerfe[heizkreis] = this._automatikEntwuerfe[heizkreis] || {};
      return this._automatikEntwuerfe[heizkreis];
    }

    _automatikHatEntwurf() {
      return Object.values(this._automatikEntwuerfe || {}).some((entwurf) => Object.keys(entwurf).length);
    }

    _automatikEntwurfVerwerfen(heizkreis) {
      if (this._automatikEntwuerfe) delete this._automatikEntwuerfe[heizkreis];
      this._automatikBearbeitet = this._automatikHatEntwurf();
    }

    _automatikTaste(text, klasse) {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = klasse;
      taste.textContent = this._t(text);
      return taste;
    }

    _automatikProfilZeile(kreis, darf) {
      const zeile = this._automatikFeld(
        "Profil",
        "",
        false,
        "Das Profil stellt alle Werte passend zu den Heizflächen ein. Eigene Werte darunter überschreiben einzelne Felder; „Profilwerte wiederherstellen“ nimmt sie zurück."
      );
      zeile.classList.add("breit");
      const wahl = document.createElement("select");
      wahl.disabled = !darf;
      wahl.setAttribute("aria-label", this._t("Profil"));
      PROFILE.forEach(([name, titel]) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = this._t(titel);
        option.selected = name === kreis.konfig.profil;
        wahl.appendChild(option);
      });
      wahl.addEventListener("change", async () => {
        // Ein neues Profil ersetzt alle eigenen Werte; offene Eingaben gingen dabei verloren.
        const offen = Object.keys(this._automatikEntwurf(kreis.heizkreis)).length;
        const ja =
          !offen ||
          (await this._bestaetigen(
            this._t("Profil wechseln?"),
            this._t("Nicht gespeicherte Änderungen gehen dabei verloren."),
            null,
            { ja: this._t("Wechseln") }
          ));
        if (!ja) {
          wahl.value = kreis.konfig.profil;
          return;
        }
        this._automatikEntwurfVerwerfen(kreis.heizkreis);
        this._automatikEinstellen(kreis, { profil: wahl.value, eigene: {} });
      });
      zeile.querySelector(".eingabe").appendChild(wahl);
      return zeile;
    }

    /** Heizgrenze der Steuerung als Zeile; gespeichert wird sie an der Steuerung, nicht in der Automatik. */
    _automatikGrenzZeile(titel, wert, min, max, darf, grenzen, name) {
      const zeile = this._automatikFeld(
        titel,
        "",
        false,
        "Die Steuerung schaltet 1 K darüber ab und 1 K darunter wieder ein, nach der aktuellen Außentemperatur. Die Automatik richtet sich nach der Grenze für den Heizbetrieb."
      );
      zeile.classList.add("grenze");
      const eingabe = document.createElement("input");
      eingabe.type = "number";
      eingabe.step = "0.5";
      eingabe.min = String(min);
      eingabe.max = String(max);
      eingabe.value = wert === null || wert === undefined ? "" : String(wert);
      eingabe.disabled = !darf;
      eingabe.setAttribute("aria-label", this._t(titel));
      const einheit = document.createElement("span");
      einheit.className = "einheit";
      einheit.textContent = "°C";
      zeile.querySelector(".eingabe").append(eingabe, einheit);
      grenzen[name] = eingabe;
      return zeile;
    }

    /**
     * Erst die Heizgrenzen an die Steuerung, dann die eigenen Werte, danach einmal
     * nachladen. Scheitert ein Schritt, bleibt der Entwurf mit den Eingaben stehen.
     */
    async _automatikAllesSpeichern(kreis, eingaben, grenzen, anfang) {
      const geaendert = (eingabe) => eingabe.value !== anfang.get(eingabe);
      try {
        if (Object.values(grenzen).some(geaendert)) {
          const nachricht = { type: "heatnexus/automatik/heizgrenzen", heizkreis: kreis.heizkreis };
          Object.entries(grenzen).forEach(([name, eingabe]) => {
            if (eingabe.value !== "") nachricht[name] = Number(eingabe.value);
          });
          await this._hass.callWS(nachricht);
        }
        if (Object.values(eingaben).some(([, eingabe]) => geaendert(eingabe))) {
          await this._hass.callWS({
            type: "heatnexus/automatik/einstellen",
            heizkreis: kreis.heizkreis,
            eigene: this._automatikEigene(eingaben),
          });
        }
      } catch (err) {
        this._melden((err && err.message) || this._t("Die Automatik hat die Änderung nicht übernommen."));
        return;
      }
      this._automatikEntwurfVerwerfen(kreis.heizkreis);
      await this._automatikHolen(true, kreis.heizkreis);
    }

    /** Speichern der eigenen Werte; nach dem Neuaufbau steht dort „übernommen ✓“. */
    async _automatikSpeichern(kreis, aenderung) {
      this._automatikEntwurfVerwerfen(kreis.heizkreis);
      await this._automatikEinstellen(kreis, aenderung, kreis.heizkreis);
    }

    async _automatikHausmodellNeu(kreis) {
      const ja = await this._bestaetigen(
        this._t("Hausmodell neu lernen?"),
        this._t("Die Automatik verwirft die gelernten Hauswerte und rechnet sie aus der Aufzeichnung neu. Das lohnt sich nach geänderten Räumen oder Umbauten."),
        null,
        { ja: this._t("Neu lernen") }
      );
      if (!ja) return;
      await this._automatikAufruf({ type: "heatnexus/automatik/hausmodell_neu", heizkreis: kreis.heizkreis });
    }

    async _automatikEntfernen(kreis) {
      const ja = await this._bestaetigen(
        this._tMit("Automatik für {name} entfernen?", { name: kreis.name }),
        this._t("Eigene Eingriffe an der Steuerung werden zurückgenommen. Einstellungen und Protokoll gehen verloren."),
        null,
        { ja: this._t("Entfernen") }
      );
      if (!ja) return;
      await this._automatikAufruf({ type: "heatnexus/automatik/entfernen", heizkreis: kreis.heizkreis });
    }

    /** Eine Zeile: Titel links (ein Klick erklärt ihn), darunter der Profilwert, rechts die Eingabe. */
    _automatikFeld(titel, unter, geaendert = false, hilfe = "") {
      const feld = document.createElement("div");
      feld.className = `automatik-feld${geaendert ? " geaendert" : ""}`;
      const text = document.createElement("div");
      text.className = "automatik-feldtext";
      const beschriftung = document.createElement(hilfe ? "button" : "span");
      beschriftung.className = "automatik-feldtitel";
      beschriftung.textContent = this._t(titel);
      if (hilfe) {
        beschriftung.type = "button";
        beschriftung.title = this._t(hilfe);
        beschriftung.addEventListener("click", () => this._erklaeren(titel, hilfe));
      }
      text.appendChild(beschriftung);
      if (unter) {
        const hinweis = document.createElement("div");
        hinweis.className = "profilwert";
        hinweis.textContent = unter;
        text.appendChild(hinweis);
      }
      const eingabe = document.createElement("div");
      eingabe.className = "eingabe";
      feld.append(text, eingabe);
      return feld;
    }

    _automatikEingabe(feld, wert, darf) {
      if (feld.art === "wahl") {
        const wahl = document.createElement("select");
        feld.optionen.forEach((option) => {
          const eintrag = document.createElement("option");
          eintrag.value = String(option);
          eintrag.textContent = feld.einheit ? `${option} ${this._t(feld.einheit)}` : String(option);
          eintrag.selected = Number(wert) === option;
          wahl.appendChild(eintrag);
        });
        wahl.disabled = !darf;
        return wahl;
      }
      if (feld.art === "janein") {
        const wahl = document.createElement("select");
        [
          ["false", "Aus"],
          ["true", "Ein"],
        ].forEach(([schluessel, titel]) => {
          const option = document.createElement("option");
          option.value = schluessel;
          option.textContent = this._t(titel);
          option.selected = String(!!wert) === schluessel;
          wahl.appendChild(option);
        });
        wahl.disabled = !darf;
        return wahl;
      }
      const eingabe = document.createElement("input");
      eingabe.disabled = !darf;
      if (feld.art === "zeit") {
        eingabe.type = "time";
        eingabe.value = wert || "";
      } else {
        eingabe.type = "number";
        eingabe.step = String(feld.schritt);
        eingabe.value = wert ?? "";
      }
      return eingabe;
    }

    _automatikEigene(eingaben) {
      const eigene = {};
      Object.entries(eingaben).forEach(([name, [feld, eingabe]]) => {
        if (feld.art === "janein") eigene[name] = eingabe.value === "true";
        else if (feld.art === "wahl") eigene[name] = Number(eingabe.value);
        else if (feld.art === "zeit") eigene[name] = eingabe.value || "";
        else if (eingabe.value !== "") eigene[name] = Number(eingabe.value);
      });
      return eigene;
    }

    // --- Einrichten ----------------------------------------------------
    _automatikEinladung(kreis, daten) {
      const karte = this._karte(kreis.name);
      karte.classList.add("automatik-einladungskarte");
      const kopf = karte.querySelector(".kartenkopf");
      if (kopf) {
        const stand = document.createElement("span");
        stand.className = "automatik-stand";
        stand.textContent = this._t("Nicht eingerichtet");
        kopf.appendChild(stand);
      }
      const text = document.createElement("p");
      text.className = "automatik-einladung";
      text.textContent = this._t(
        "Senkt an sonnigen Tagen ab und schaltet in der Übergangszeit auf nur Warmwasser. Startet im Beobachtungsmodus."
      );
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "automatik-knopf umriss";
      taste.textContent = this._t("Automatik einrichten");
      taste.disabled = !daten.darf_aendern;
      taste.addEventListener("click", () => this._automatikDialog(kreis));
      karte.append(text, taste);
      return karte;
    }

    async _automatikDialog(kreis) {
      let kandidaten;
      try {
        kandidaten = await this._hass.callWS({ type: "heatnexus/automatik/kandidaten" });
      } catch (err) {
        this._melden(this._t("Die Auswahllisten konnten nicht geladen werden."));
        return;
      }
      const k = kreis.eingerichtet ? kreis.konfig : null;
      const { schleier, dialog, inhalt, kreuz } = this._automatikDialogRahmen(
        k
          ? this._tMit("Einrichtung von {name} ändern", { name: kreis.name })
          : this._tMit("Automatik für {name} einrichten", { name: kreis.name })
      );
      const felder = this._automatikDialogFelder(kandidaten, k);
      this._automatikDialogAbschnitte(felder).forEach(([ueberschrift, knoten]) => {
        const abschnitt = document.createElement("section");
        const kopf = document.createElement("h4");
        kopf.textContent = ueberschrift;
        abschnitt.append(kopf, ...knoten);
        inhalt.appendChild(abschnitt);
      });

      const leiste = document.createElement("div");
      leiste.className = "dialog-leiste";
      const abbrechen = document.createElement("button");
      abbrechen.type = "button";
      abbrechen.className = "dialog-taste";
      abbrechen.textContent = this._t("Abbrechen");
      const einrichten = document.createElement("button");
      einrichten.type = "button";
      einrichten.className = "dialog-taste bestaetigen";
      einrichten.textContent = k ? this._t("Übernehmen") : this._t("Einrichten");
      leiste.append(abbrechen, einrichten);
      dialog.appendChild(leiste);
      const beiTaste = (ereignis) => {
        if (ereignis.key === "Escape") weg();
      };
      const weg = () => {
        document.removeEventListener("keydown", beiTaste);
        schleier.remove();
      };
      document.addEventListener("keydown", beiTaste);
      abbrechen.addEventListener("click", weg);
      kreuz.addEventListener("click", weg);
      einrichten.addEventListener("click", async () => {
        const nachricht = this._automatikDialogNachricht(kreis, k, felder);
        if (!nachricht.raeume.length || !nachricht.wetter) {
          this._melden(this._t("Mindestens ein Raum und eine Wetter-Entität sind nötig."));
          return;
        }
        if (await this._automatikAufruf(nachricht)) weg();
      });
      this.shadowRoot.appendChild(schleier);
    }

    /** Schleier, Dialog und fester Kopf; nur der Inhalt dazwischen scrollt. */
    _automatikDialogRahmen(titelText) {
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog automatik-dialog";
      dialog.setAttribute("role", "dialog");
      const titel = document.createElement("h3");
      titel.className = "dialog-titel";
      titel.textContent = titelText;
      const kopfzeile = document.createElement("div");
      kopfzeile.className = "dialog-kopf";
      const kreuz = document.createElement("button");
      kreuz.type = "button";
      kreuz.className = "dialog-schliessen";
      kreuz.textContent = "×";
      kreuz.setAttribute("aria-label", this._t("Schließen"));
      kreuz.title = this._t("Schließen");
      kopfzeile.append(titel, kreuz);
      const inhalt = document.createElement("div");
      inhalt.className = "automatik-dialog-inhalt";
      dialog.append(kopfzeile, inhalt);
      schleier.appendChild(dialog);
      return { schleier, dialog, inhalt, kreuz };
    }

    /** Die Eingaben des Dialogs, vorbelegt mit der bestehenden Einrichtung `k`. */
    _automatikDialogFelder(kandidaten, k) {
      const mitKeine = (liste, gewaehlt) =>
        this._automatikMitGewaehlt([["", this._t("Keine")], ...(liste || []).map((e) => [e.entity_id, e.name])], gewaehlt);
      const raumZiel = this._automatikEingabe({ schritt: 0.5 }, k ? k.raum_ziel : null, true);
      raumZiel.min = "10";
      raumZiel.max = "30";
      const erkennung = document.createElement("input");
      erkennung.type = "checkbox";
      erkennung.checked = !!(k && k.fenster_erkennung);
      return {
        heizflaechen: this._automatikAuswahl(HEIZFLAECHEN, (k && k.heizflaechen) || "gemischt"),
        ausrichtung: this._automatikAuswahl(AUSRICHTUNGEN, (k && k.ausrichtung) || "ausgewogen"),
        raeume: this._automatikHaken(kandidaten.temperatur, k ? k.raeume : []),
        raumArt: this._automatikAuswahl(
          [
            ["mittel", this._t("Mittel der Räume")],
            ["minimum", this._t("Kältester Raum")],
          ],
          (k && k.raum_art) || "mittel"
        ),
        raumZiel,
        wetter: this._automatikAuswahl(
          this._automatikMitGewaehlt(kandidaten.wetter.map((e) => [e.entity_id, e.name]), k && k.wetter),
          (k && k.wetter) || ""
        ),
        pv: this._automatikAuswahl(mitKeine(kandidaten.pv, k && k.pv), (k && k.pv) || ""),
        pvIst: this._automatikAuswahl(mitKeine(kandidaten.pv_ist, k && k.pv_ist), (k && k.pv_ist) || ""),
        personen: this._automatikHaken(kandidaten.personen, k ? k.personen : []),
        fenster: this._automatikHaken(kandidaten.fenster, k ? k.fenster : []),
        vorrang: this._automatikHaken(kandidaten.vorrang || [], k ? k.vorrang || [] : []),
        erkennung,
      };
    }

    /** Die fünf Abschnitte des Dialogs als Überschrift und Knoten. */
    _automatikDialogAbschnitte(f) {
      const b = (text, ...knoten) => this._automatikBeschriftet(this._t(text), ...knoten);
      return [
        [
          this._t("1 · Heizflächen und Ausrichtung"),
          [f.heizflaechen, b("Eco greift früher und kräftiger ein, Komfort später und sanfter. Ausgewogen nimmt die Werte der Heizflächen unverändert.", f.ausrichtung)],
        ],
        [
          this._t("2 · Räume"),
          [
            b("Räume wählen, die dieser Heizkreis versorgt und die für das Haus typisch sind. Keller, Bad oder Wintergarten verfälschen das Mittel und das Hausmodell.", f.raeume),
            b("Zählt", f.raumArt),
            b("Wunschtemperatur für Temperaturfühler, °C (leer: Sollwert des Heizkreises)", f.raumZiel),
          ],
        ],
        [
          this._t("3 · Wetter und PV-Prognose"),
          [b("Wetter", f.wetter), b("PV-Prognose, Tagesertrag (optional)", f.pv), b("PV-Ertrag tatsächlich, zum Anpassen (optional)", f.pvIst)],
        ],
        [
          this._t("4 · Optional: Anwesenheit und Fenster"),
          [
            b("Personen", f.personen),
            b("Fensterkontakte", this._automatikMitText(f.erkennung, this._t("Fenster aus Temperatursturz erkennen")), f.fenster),
          ],
        ],
        [
          this._t("5 · Optional: Wärmequellen mit Vorrang vor dem Kessel"),
          [b("Liefert eine dieser Quellen, soll ihre Wärme den Heizkreis decken statt der Kessel.", f.vorrang)],
        ],
      ];
    }

    /** Die Nachricht an den Server aus den Eingaben des Dialogs. */
    _automatikDialogNachricht(kreis, k, f) {
      const gewaehlt = (liste) => Array.from(liste.querySelectorAll("input:checked")).map((e) => e.value);
      const nachricht = {
        type: k ? "heatnexus/automatik/einstellen" : "heatnexus/automatik/einrichten",
        heizkreis: kreis.heizkreis,
        heizflaechen: f.heizflaechen.value,
        ausrichtung: f.ausrichtung.value,
        raeume: gewaehlt(f.raeume),
        raum_art: f.raumArt.value,
        raum_ziel: f.raumZiel.value === "" ? null : Number(f.raumZiel.value),
        wetter: f.wetter.value,
        pv: f.pv.value || null,
        pv_ist: f.pvIst.value || null,
        personen: gewaehlt(f.personen),
        fenster: gewaehlt(f.fenster),
        vorrang: gewaehlt(f.vorrang),
        fenster_erkennung: f.erkennung.checked,
      };
      // Andere Heizflächen heißen anderes Profil; eigene Werte gehörten zum alten.
      if (k && nachricht.heizflaechen !== k.heizflaechen) {
        nachricht.profil = PROFIL_JE_FLAECHE[nachricht.heizflaechen];
        nachricht.eigene = {};
      }
      return nachricht;
    }

    _automatikAuswahl(eintraege, vorgabe) {
      const wahl = document.createElement("select");
      eintraege.forEach(([wert, titel]) => {
        const option = document.createElement("option");
        option.value = wert;
        option.textContent = this._t(titel);
        option.selected = wert === vorgabe;
        wahl.appendChild(option);
      });
      return wahl;
    }

    _automatikHaken(eintraege, gewaehlt = []) {
      const liste = document.createElement("div");
      liste.className = "automatik-haken";
      const bekannt = new Set(eintraege.map((e) => e.entity_id));
      const alle = [...gewaehlt.filter((id) => !bekannt.has(id)).map((id) => ({ entity_id: id, name: id, bereich: "" })), ...eintraege];
      if (!alle.length) liste.appendChild(this._hinweisKnoten(this._t("Keine passenden Entitäten gefunden.")));
      alle.forEach((eintrag) => {
        const haken = document.createElement("input");
        haken.type = "checkbox";
        haken.value = eintrag.entity_id;
        haken.checked = gewaehlt.includes(eintrag.entity_id);
        const teile = [eintrag.name, eintrag.bereich, eintrag.art === "thermostat" ? this._t("Thermostat") : "", eintrag.wert].filter(Boolean);
        const alter = eintrag.seit ? (Date.now() - Date.parse(eintrag.seit)) / 3600000 : 0;
        if (alter > VERALTET_STUNDEN) {
          teile.push(
            alter >= 48
              ? this._tMit("seit {tage} Tagen unverändert", { tage: Math.floor(alter / 24) })
              : this._tMit("seit {stunden} h unverändert", { stunden: Math.floor(alter) })
          );
        }
        const zeile = this._automatikMitText(haken, teile.join(" · "));
        if (alter > VERALTET_STUNDEN) zeile.classList.add("veraltet");
        liste.appendChild(zeile);
      });
      return liste;
    }

    _automatikBeschriftet(text, ...knoten) {
      const rahmen = document.createElement("div");
      rahmen.className = "automatik-beschriftet";
      const titel = document.createElement("div");
      titel.className = "automatik-unter";
      titel.textContent = text;
      rahmen.append(titel, ...knoten);
      return rahmen;
    }

    _automatikMitGewaehlt(eintraege, gewaehlt) {
      if (!gewaehlt || eintraege.some(([wert]) => wert === gewaehlt)) return eintraege;
      return [...eintraege, [gewaehlt, gewaehlt]];
    }

    _automatikMitText(eingabe, text) {
      const zeile = document.createElement("label");
      zeile.className = "automatik-haken-zeile";
      const titel = document.createElement("span");
      titel.textContent = text;
      zeile.append(eingabe, titel);
      return zeile;
    }
  };
