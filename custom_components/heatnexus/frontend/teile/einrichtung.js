/**
 * Reiter „Automatik“: Einladung, Einrichtungsdialog und „Erweitert“.
 *
 * Der Dialog holt seine Auswahllisten über `heatnexus/automatik/kandidaten`
 * und schreibt über `heatnexus/automatik/einrichten` bzw. `einstellen`.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin.
 */

import { FELDER, HEIZFLAECHEN, PROFILE, PROFIL_JE_FLAECHE, VERALTET_STUNDEN, zahl } from "./automatik.js";

export const EinrichtungMixin = (Basis) =>
  class extends Basis {
    // --- Erweitert -----------------------------------------------------
    _automatikErweitert(kreis, daten, darf) {
      // Frisch gebaute Felder tragen keine Eingabe; Zuklappen gibt das Nachladen ebenso frei.
      this._automatikBearbeitet = false;
      const bereich = document.createElement("details");
      bereich.className = "automatik-erweitert";
      // Offen bleibt offen, auch wenn Speichern oder Nachladen die Karte neu baut.
      this._automatikOffen = this._automatikOffen || new Set();
      bereich.open = this._automatikOffen.has(kreis.heizkreis);
      bereich.addEventListener("toggle", () => {
        if (bereich.open) this._automatikOffen.add(kreis.heizkreis);
        else {
          this._automatikOffen.delete(kreis.heizkreis);
          this._automatikBearbeitet = false;
        }
      });
      const kopf = document.createElement("summary");
      kopf.textContent = "Erweitert";
      bereich.appendChild(kopf);
      const vorgabe = (daten.profile || {})[kreis.konfig.profil] || {};
      const eingaben = {};
      const raster = document.createElement("div");
      raster.className = "automatik-felder";

      const flaechen = HEIZFLAECHEN.find(([name]) => name === kreis.konfig.heizflaechen);
      const profilFeld = this._automatikFeld(
        "Profil",
        flaechen ? flaechen[1] : "",
        false,
        this._t(
          "Das Profil stellt alle Werte passend zu den Heizflächen ein. Eigene Werte darunter überschreiben einzelne Felder; „Profilwerte wiederherstellen“ nimmt sie zurück."
        )
      );
      profilFeld.classList.add("breit");
      const profilWahl = document.createElement("select");
      profilWahl.disabled = !darf;
      PROFILE.forEach(([name, titel]) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = titel;
        option.selected = name === kreis.konfig.profil;
        profilWahl.appendChild(option);
      });
      profilWahl.addEventListener("change", () =>
        this._automatikEinstellen(kreis, { profil: profilWahl.value, eigene: {} })
      );
      profilFeld.querySelector(".eingabe").appendChild(profilWahl);
      raster.appendChild(profilFeld);

      FELDER.forEach((feld) => {
        const wert = (kreis.werte || {})[feld.name];
        const basis = vorgabe[feld.name];
        const geaendert = wert !== basis;
        const basisText = typeof basis === "number" ? zahl(basis, Number.isInteger(basis) ? 0 : 1) : basis || "–";
        const anzeige = feld.art === "janein" ? (basis ? "Ein" : "Aus") : `${basisText} ${feld.einheit || ""}`.trim();
        const knoten = this._automatikFeld(feld.titel, `Profil: ${anzeige || "–"}`, geaendert, feld.hilfe);
        const eingabe = this._automatikEingabe(feld, wert, darf);
        eingabe.addEventListener("input", () => {
          this._automatikBearbeitet = true;
        });
        eingaben[feld.name] = [feld, eingabe];
        knoten.querySelector(".eingabe").appendChild(eingabe);
        if (feld.einheit) {
          const einheit = document.createElement("span");
          einheit.className = "einheit";
          einheit.textContent = feld.einheit;
          knoten.querySelector(".eingabe").appendChild(einheit);
        }
        raster.appendChild(knoten);
      });
      bereich.appendChild(raster);

      const leiste = document.createElement("div");
      leiste.className = "automatik-leiste";
      const zuruecksetzen = document.createElement("button");
      zuruecksetzen.type = "button";
      zuruecksetzen.className = "automatik-knopf leise";
      zuruecksetzen.textContent = "Profilwerte wiederherstellen";
      zuruecksetzen.disabled = !darf;
      zuruecksetzen.addEventListener("click", () => this._automatikEinstellen(kreis, { eigene: {} }));
      const speichern = document.createElement("button");
      speichern.type = "button";
      speichern.className = "automatik-knopf";
      speichern.textContent = "Speichern";
      speichern.disabled = !darf;
      speichern.addEventListener("click", () => this._automatikEinstellen(kreis, { eigene: this._automatikEigene(eingaben) }));
      const entfernen = document.createElement("button");
      entfernen.type = "button";
      entfernen.className = "automatik-knopf leise warnung";
      entfernen.textContent = "Automatik entfernen";
      entfernen.disabled = !darf;
      entfernen.addEventListener("click", () => this._automatikEntfernen(kreis));
      const links = document.createElement("div");
      links.className = "automatik-leiste-links";
      links.append(entfernen);
      leiste.append(links, zuruecksetzen, speichern);
      bereich.appendChild(leiste);
      return bereich;
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

    _automatikFeld(titel, unter, geaendert = false, hilfe = "") {
      const feld = document.createElement("div");
      feld.className = `automatik-feld${geaendert ? " geaendert" : ""}`;
      const beschriftung = document.createElement("div");
      beschriftung.className = "automatik-feldkopf";
      const text = document.createElement("label");
      text.textContent = titel;
      beschriftung.appendChild(text);
      if (hilfe) beschriftung.appendChild(this._fragezeichen(titel, hilfe));
      const eingabe = document.createElement("div");
      eingabe.className = "eingabe";
      const hinweis = document.createElement("div");
      hinweis.className = "profilwert";
      hinweis.textContent = unter;
      feld.append(beschriftung, eingabe, hinweis);
      return feld;
    }

    _automatikEingabe(feld, wert, darf) {
      if (feld.art === "wahl") {
        const wahl = document.createElement("select");
        feld.optionen.forEach((option) => {
          const eintrag = document.createElement("option");
          eintrag.value = String(option);
          eintrag.textContent = String(option);
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
          option.textContent = titel;
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
      const karte = this._karte(kreis.name, this._hilfe && this._hilfe.Automatik);
      const text = document.createElement("p");
      text.className = "automatik-einladung";
      text.textContent =
        "Die Automatik senkt den Heizkreis an sonnigen Tagen ab und schaltet in der Übergangszeit auf nur Warmwasser. Sie beginnt im Beobachtungsmodus und schreibt dann noch nichts an die Steuerung.";
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "automatik-knopf";
      taste.textContent = "Automatik einrichten";
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
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog automatik-dialog";
      dialog.setAttribute("role", "dialog");
      const titel = document.createElement("h3");
      titel.className = "dialog-titel";
      const k = kreis.eingerichtet ? kreis.konfig : null;
      titel.textContent = k
        ? this._tMit("Einrichtung von {name} ändern", { name: kreis.name })
        : this._tMit("Automatik für {name} einrichten", { name: kreis.name });
      // Kopf und Tasten bleiben stehen, nur die Abschnitte dazwischen scrollen.
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

      const heizflaechen = this._automatikAuswahl(HEIZFLAECHEN, (k && k.heizflaechen) || "gemischt");
      const raeume = this._automatikHaken(kandidaten.temperatur, k ? k.raeume : []);
      const raumArt = this._automatikAuswahl(
        [
          ["mittel", this._t("Mittel der Räume")],
          ["minimum", this._t("Kältester Raum")],
        ],
        (k && k.raum_art) || "mittel"
      );
      const raumZiel = document.createElement("input");
      raumZiel.type = "number";
      raumZiel.step = "0.5";
      raumZiel.min = "10";
      raumZiel.max = "30";
      raumZiel.value = k && k.raum_ziel !== null && k.raum_ziel !== undefined ? String(k.raum_ziel) : "";
      const wetter = this._automatikAuswahl(
        this._automatikMitGewaehlt(kandidaten.wetter.map((e) => [e.entity_id, e.name]), k && k.wetter),
        (k && k.wetter) || ""
      );
      const pv = this._automatikAuswahl(
        this._automatikMitGewaehlt([["", this._t("Keine")], ...kandidaten.pv.map((e) => [e.entity_id, e.name])], k && k.pv),
        (k && k.pv) || ""
      );
      const pvIst = this._automatikAuswahl(
        this._automatikMitGewaehlt([["", this._t("Keine")], ...(kandidaten.pv_ist || []).map((e) => [e.entity_id, e.name])], k && k.pv_ist),
        (k && k.pv_ist) || ""
      );
      const personen = this._automatikHaken(kandidaten.personen, k ? k.personen : []);
      const fenster = this._automatikHaken(kandidaten.fenster, k ? k.fenster : []);
      const erkennung = document.createElement("input");
      erkennung.type = "checkbox";
      erkennung.checked = !!(k && k.fenster_erkennung);

      const abschnitte = [
        [this._t("1 · Heizflächen"), [heizflaechen]],
        [
          this._t("2 · Räume"),
          [
            raeume,
            this._automatikBeschriftet(this._t("Zählt"), raumArt),
            this._automatikBeschriftet(this._t("Wunschtemperatur für Temperaturfühler, °C (leer: Sollwert des Heizkreises)"), raumZiel),
          ],
        ],
        [
          this._t("3 · Wetter und PV-Prognose"),
          [
            this._automatikBeschriftet(this._t("Wetter"), wetter),
            this._automatikBeschriftet(this._t("PV-Prognose, Tagesertrag (optional)"), pv),
            this._automatikBeschriftet(this._t("PV-Ertrag tatsächlich, zum Anpassen (optional)"), pvIst),
          ],
        ],
        [
          this._t("4 · Optional: Anwesenheit und Fenster"),
          [
            this._automatikBeschriftet(this._t("Personen"), personen),
            this._automatikBeschriftet(
              this._t("Fensterkontakte"),
              this._automatikMitText(erkennung, this._t("Fenster aus Temperatursturz erkennen")),
              fenster
            ),
          ],
        ],
      ];
      abschnitte.forEach(([ueberschrift, knoten]) => {
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
      schleier.appendChild(dialog);
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
        const gewaehlt = (liste) => Array.from(liste.querySelectorAll("input:checked")).map((e) => e.value);
        const nachricht = {
          type: k ? "heatnexus/automatik/einstellen" : "heatnexus/automatik/einrichten",
          heizkreis: kreis.heizkreis,
          heizflaechen: heizflaechen.value,
          raeume: gewaehlt(raeume),
          raum_art: raumArt.value,
          raum_ziel: raumZiel.value === "" ? null : Number(raumZiel.value),
          wetter: wetter.value,
          pv: pv.value || null,
          pv_ist: pvIst.value || null,
          personen: gewaehlt(personen),
          fenster: gewaehlt(fenster),
          fenster_erkennung: erkennung.checked,
        };
        // Andere Heizflächen heißen anderes Profil; eigene Werte gehörten zum alten.
        if (k && nachricht.heizflaechen !== k.heizflaechen) {
          nachricht.profil = PROFIL_JE_FLAECHE[nachricht.heizflaechen];
          nachricht.eigene = {};
        }
        if (!nachricht.raeume.length || !nachricht.wetter) {
          this._melden(this._t("Mindestens ein Raum und eine Wetter-Entität sind nötig."));
          return;
        }
        if (await this._automatikAufruf(nachricht)) weg();
      });
      this.shadowRoot.appendChild(schleier);
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
