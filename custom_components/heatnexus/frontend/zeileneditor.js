/**
 * Der Editor unter einer Tageszeile: Schaltzeiten eines Blocks, seine Tage, eine Spur zur Kontrolle.
 *
 * Er arbeitet auf einem Modell, das der Aufrufer hält; so übersteht ein offener Editor das Neuzeichnen.
 */

import { SCHALTPUNKTE_MAX } from "./ordnung.js";
import { TAGE, TAG_MINUTEN, abschnitte, minuten, tagText, uhrzeit } from "./zeitprogramm.js";
import { tagesspur } from "./zeitprogrammseite.js";

const OHNE = (text) => text;

// Eine neue Schaltzeit liegt eine Stunde nach der letzten.
const ABSTAND_MINUTEN = 60;
const ERSTER_START = 6 * 60;
const ERSTER_WERT = 20;

function taste(text, klasse, aktion) {
  const knopf = document.createElement("button");
  knopf.type = "button";
  knopf.className = klasse;
  knopf.textContent = text;
  knopf.addEventListener("click", aktion);
  return knopf;
}

function wertFeld(punkt, grenzen, t, geaendert) {
  if (grenzen.schalt) {
    const auswahl = document.createElement("select");
    [
      ["1", "Ein"],
      ["0", "Aus"],
    ].forEach(([schluessel, text]) => {
      const eintrag = document.createElement("option");
      eintrag.value = schluessel;
      eintrag.textContent = t(text);
      auswahl.appendChild(eintrag);
    });
    auswahl.value = punkt.wert >= 0.5 ? "1" : "0";
    auswahl.addEventListener("change", () => geaendert(Number(auswahl.value)));
    auswahl.setAttribute("aria-label", t("Schaltzustand"));
    return auswahl;
  }
  const feld = document.createElement("input");
  feld.type = "number";
  feld.step = "0.5";
  feld.value = String(punkt.wert);
  feld.addEventListener("change", () => {
    const gelesen = Number(feld.value);
    if (Number.isFinite(gelesen)) geaendert(gelesen);
    else feld.value = String(punkt.wert);
  });
  feld.setAttribute("aria-label", t("Solltemperatur"));
  return feld;
}

function punktZeile(modell, nummer, { grenzen, t, neu }) {
  const punkt = modell.punkte[nummer];
  const zeile = document.createElement("div");
  zeile.className = "zp-ze-punkt";
  const ab = document.createElement("span");
  ab.className = "zp-ze-ab";
  ab.textContent = t("ab");
  const zeit = document.createElement("input");
  zeit.type = "time";
  zeit.className = "zp-ze-feld";
  zeit.value = uhrzeit(punkt.zeit);
  zeit.setAttribute("aria-label", t("Schaltzeit"));
  zeit.addEventListener("change", () => {
    const gelesen = minuten(zeit.value);
    if (gelesen === null) {
      zeit.value = uhrzeit(punkt.zeit);
      return;
    }
    punkt.zeit = gelesen;
    neu(false);
  });
  const wert = wertFeld(punkt, grenzen, t, (gelesen) => {
    punkt.wert = gelesen;
    neu(false);
  });
  wert.classList.add("zp-ze-feld", "zp-wert");
  const einheit = document.createElement("span");
  einheit.className = "zp-einheit";
  einheit.textContent = grenzen.schalt ? "" : "°C";
  const weg = taste("✕", "zp-ze-weg", () => {
    modell.punkte.splice(nummer, 1);
    neu(true);
  });
  weg.title = t("Schaltzeit entfernen");
  weg.setAttribute("aria-label", t("Schaltzeit entfernen"));
  zeile.append(ab, zeit, wert, einheit, weg);
  return zeile;
}

function tagLeiste(modell, t, neu) {
  const leiste = document.createElement("div");
  leiste.className = "zp-ze-tage";
  TAGE.forEach((tag) => {
    const knopf = taste(tagText(tag, t), "zp-tagwahl", () => {
      modell.tage = modell.tage.includes(tag)
        ? modell.tage.filter((eintrag) => eintrag !== tag)
        : TAGE.filter((code) => code === tag || modell.tage.includes(code));
      neu(true);
    });
    knopf.dataset.tag = tag;
    knopf.setAttribute("aria-pressed", String(modell.tage.includes(tag)));
    leiste.appendChild(knopf);
  });
  return leiste;
}

function ueberschrift(text) {
  const kopf = document.createElement("div");
  kopf.className = "zp-ze-kopf";
  kopf.textContent = text;
  return kopf;
}

/**
 * Den Editor bauen. `modell` ({tage, punkte}) ändert er selbst; `speichern` bekommt es sortiert zurück
 * und liefert Fehlertexte oder nichts.
 */
export function zeileneditorKnoten(modell, { grenzen, t = OHNE, speichern, abbrechen }) {
  const knoten = document.createElement("div");
  knoten.className = "zp-zeileneditor";
  const vorschau = document.createElement("div");
  vorschau.className = "zp-ze-vorschau";
  const meldung = document.createElement("div");
  meldung.className = "zp-meldung";
  meldung.setAttribute("role", "status");

  const spurZeichnen = () => {
    const sortiert = [...modell.punkte].sort((a, b) => a.zeit - b.zeit);
    vorschau.replaceChildren(tagesspur(abschnitte(sortiert), grenzen, { t }));
  };
  const zeichnen = () => {
    const punkte = document.createElement("div");
    punkte.className = "zp-ze-punkte";
    modell.punkte.forEach((_, nummer) => punkte.appendChild(punktZeile(modell, nummer, { grenzen, t, neu })));
    const mehr = taste(t("+ Schaltzeit"), "zp-ze-mehr", () => {
      const letzte = modell.punkte[modell.punkte.length - 1];
      const zeit = letzte ? Math.min(TAG_MINUTEN - ABSTAND_MINUTEN, letzte.zeit + ABSTAND_MINUTEN) : ERSTER_START;
      modell.punkte.push({ zeit, wert: letzte ? letzte.wert : grenzen.schalt ? 1 : ERSTER_WERT });
      neu(true);
    });
    mehr.disabled = modell.punkte.length >= SCHALTPUNKTE_MAX;
    const aktionen = document.createElement("div");
    aktionen.className = "zp-ze-aktionen";
    aktionen.append(
      taste(t("Abbrechen"), "zp-taste zp-abbrechen", abbrechen),
      taste(t("Speichern"), "zp-taste betont zp-speichern", () => {
        const fehler = speichern({
          tage: [...modell.tage],
          punkte: [...modell.punkte].sort((a, b) => a.zeit - b.zeit),
        });
        meldung.className = fehler && fehler.length ? "zp-meldung fehler" : "zp-meldung";
        meldung.textContent = fehler && fehler.length ? fehler.join(" ") : "";
      })
    );
    knoten.replaceChildren(
      ueberschrift(t("Schaltzeiten · ab der Uhrzeit gilt der Wert bis zur nächsten")),
      punkte,
      mehr,
      ueberschrift(t("Gilt für")),
      tagLeiste(modell, t, neu),
      vorschau,
      meldung,
      aktionen
    );
    spurZeichnen();
  };
  // Neue oder entfernte Zeilen bauen den Editor neu; ein geänderter Wert zeichnet nur die Spur.
  function neu(ganz) {
    if (ganz) zeichnen();
    else spurZeichnen();
  }
  zeichnen();
  return knoten;
}
