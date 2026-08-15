/**
 * Reiter „Hilfe“.
 *
 * Alle Erklärungen dieser Anlage an einer Stelle, durchsuchbar. Verteilt hinter
 * den Fragezeichen der Karten sind sie schwer zu treffen, und wer nicht weiß,
 * wonach er sucht, findet den Text nicht, der seine Frage beantwortet.
 *
 * Welche Erklärungen überhaupt gelten, entscheidet die Integration; hier wird
 * nur gefiltert und gezeichnet.
 *
 * Teil der Oberfläche `heatnexus-panel.js`; eingebunden als Mixin, damit die
 * Methoden unverändert an derselben Klasse hängen. Siehe dort.
 */

import { BREITE_MAX } from "../ordnung.js";

/**
 * Einträge auf eine Suche eingrenzen.
 *
 * Gesucht wird in Titel **und** Text: Wer einen Begriff sucht, kennt die
 * Überschrift meist nicht.
 */
export function filtern(eintraege, suche) {
  const wort = (suche || "").trim().toLowerCase();
  if (!wort) return eintraege || [];
  return (eintraege || []).filter(
    (e) =>
      (e.titel || "").toLowerCase().includes(wort) ||
      (e.text || "").toLowerCase().includes(wort)
  );
}

export const HilfeMixin = (Basis) =>
  class extends Basis {
    // -------------------------------------------------------------------
    // Reiter „Hilfe"
    // -------------------------------------------------------------------
    /**
     * Das mitgelieferte Dashboard als Text.
     *
     * Es entsteht bei jedem Öffnen neu; Home Assistant sperrt dort Editor und
     * Rohkonfiguration. Wer es abwandeln will, kopiert diesen Text in ein
     * eigenes Dashboard.
     */
    _dashboardVorlage() {
      const karte = this._karte("Dashboard-Vorlage");
      const text = document.createElement("p");
      text.className = "hinweis";
      text.textContent =
        "Das mitgelieferte Dashboard baut sich bei jedem Öffnen neu aus der " +
        "Anlage auf und lässt sich deshalb nicht bearbeiten. Der Text hier ist " +
        "sein heutiger Stand – eingefügt in ein neues Dashboard gehört er dir.";
      karte.appendChild(text);

      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "dialog-taste";
      taste.textContent = "YAML anzeigen";
      taste.addEventListener("click", async () => {
        taste.disabled = true;
        try {
          const antwort = await this._hass.callWS({ type: "heatnexus/dashboard_yaml" });
          this._yamlZeigen(antwort.yaml || "");
        } catch (err) {
          this._erklaeren("Dashboard-Vorlage", `Nicht abrufbar: ${err.message || err}`);
        } finally {
          taste.disabled = false;
        }
      });
      karte.appendChild(taste);
      return karte;
    }

    /** Der Text in einem Fenster, mit Knopf zum Kopieren. */
    _yamlZeigen(text) {
      const schleier = document.createElement("div");
      schleier.className = "schleier";
      const dialog = document.createElement("div");
      dialog.className = "dialog erklaerung";
      dialog.setAttribute("role", "dialog");

      const ueberschrift = document.createElement("h3");
      ueberschrift.className = "dialog-titel";
      ueberschrift.textContent = "Dashboard-Vorlage";

      // Ein Textfeld statt eines Absatzes: So lässt sich der Inhalt auch dort
      // markieren, wo die Zwischenablage gesperrt ist.
      const feld = document.createElement("textarea");
      feld.className = "yaml-feld";
      feld.readOnly = true;
      feld.value = text;

      const leiste = document.createElement("div");
      leiste.className = "dialog-leiste";
      const kopieren = document.createElement("button");
      kopieren.type = "button";
      kopieren.className = "dialog-taste";
      kopieren.textContent = "Kopieren";
      const schliessen = document.createElement("button");
      schliessen.type = "button";
      schliessen.className = "dialog-taste";
      schliessen.textContent = "Schließen";
      leiste.append(kopieren, schliessen);

      dialog.append(ueberschrift, feld, leiste);
      schleier.appendChild(dialog);

      const weg = () => {
        schleier.remove();
        document.removeEventListener("keydown", beiTaste);
      };
      const beiTaste = (ereignis) => {
        if (ereignis.key === "Escape") weg();
      };
      kopieren.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(text);
          kopieren.textContent = "Kopiert ✓";
        } catch {
          feld.select();
          kopieren.textContent = "Markiert – bitte selbst kopieren";
        }
      });
      schliessen.addEventListener("click", weg);
      schleier.addEventListener("click", (e) => {
        if (e.target === schleier) weg();
      });
      document.addEventListener("keydown", beiTaste);
      this.shadowRoot.appendChild(schleier);
      schliessen.focus();
    }

    _hilfeReiter(anlage) {
      const eintraege = anlage.hilfe_liste || [];
      const vorlage = { id: "dashboard-vorlage", titel: "Dashboard-Vorlage", knoten: null };
      if (this._hass && this._hass.user && this._hass.user.is_admin) {
        vorlage.knoten = this._dashboardVorlage();
      }
      if (!eintraege.length) return [{ id: "hilfe", titel: "Hilfe", knoten: null }, vorlage];

      const karte = this._karte("Hilfe");

      const suchfeld = document.createElement("input");
      suchfeld.type = "search";
      suchfeld.className = "hilfe-suche";
      suchfeld.placeholder = "Suchen …";
      suchfeld.setAttribute("aria-label", "Erklärungen durchsuchen");
      karte.appendChild(suchfeld);

      const liste = document.createElement("div");
      liste.className = "hilfe-liste";
      karte.appendChild(liste);

      const zeichnen = () => {
        liste.textContent = "";
        const treffer = filtern(eintraege, suchfeld.value);
        if (!treffer.length) {
          const leer = document.createElement("p");
          leer.className = "hilfe-leer";
          leer.textContent = "Kein Eintrag passt zu dieser Suche.";
          liste.appendChild(leer);
          return;
        }
        treffer.forEach((eintrag) => {
          const block = document.createElement("details");
          block.className = "hilfe-eintrag";
          const kopf = document.createElement("summary");
          kopf.textContent = eintrag.titel;
          block.appendChild(kopf);
          const text = document.createElement("p");
          // `textContent`, nicht `innerHTML`: Die Texte tragen Aufzählungen und
          // Absätze, aber kein Markup.
          text.textContent = eintrag.text;
          block.appendChild(text);
          liste.appendChild(block);
        });
      };

      suchfeld.addEventListener("input", zeichnen);
      zeichnen();

      // Fließtext über die volle Breite. Auf einer Spalte stünde die Karte
      // schmal neben leerer Fläche.
      return [{ id: "hilfe", titel: "Hilfe", knoten: karte, breite: BREITE_MAX }, vorlage];
    }
  };
