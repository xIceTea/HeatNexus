/**
 * Der Editor unter einer Tageszeile: Schaltzeiten eines Blocks, seine Tage, eine Spur zur Kontrolle.
 *
 * Er arbeitet auf einem Modell, das der Aufrufer hält; so übersteht ein offener Editor das Neuzeichnen.
 */

import { SCHALTPUNKTE_MAX } from "./ordnung.js";
import {
  FORMATBEREICH,
  TAGE,
  WERTRASTER,
  ZEITRASTER,
  abschnitte,
  aufWertraster,
  aufZeitraster,
  minuten,
  neueSchaltzeit,
  spaetesterWert,
  tagText,
  uhrzeit,
} from "./zeitprogramm.js";
import { tagesspur } from "./zeitprogrammseite.js";

const OHNE = (text) => text;

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
  const bereich = grenzen.bereich || FORMATBEREICH;
  const feld = document.createElement("input");
  feld.type = "number";
  feld.step = String(WERTRASTER);
  feld.min = String(bereich.min);
  feld.max = String(bereich.max);
  feld.value = String(punkt.wert);
  feld.addEventListener("change", () => {
    const gelesen = feld.value === "" ? NaN : Number(feld.value);
    if (Number.isFinite(gelesen)) {
      const gerastert = aufWertraster(gelesen, bereich);
      feld.value = String(gerastert);
      geaendert(gerastert);
    } else feld.value = String(punkt.wert);
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
  zeit.step = String(ZEITRASTER * 60);
  zeit.value = uhrzeit(punkt.zeit);
  zeit.setAttribute("aria-label", t("Schaltzeit"));
  zeit.dataset.fokus = `zeit:${nummer}`;
  zeit.addEventListener("change", () => {
    const gelesen = minuten(zeit.value);
    if (gelesen === null) {
      zeit.value = uhrzeit(punkt.zeit);
      return;
    }
    punkt.zeit = aufZeitraster(gelesen);
    zeit.value = uhrzeit(punkt.zeit);
    neu(false);
  });
  const wert = wertFeld(punkt, grenzen, t, (gelesen) => {
    punkt.wert = gelesen;
    neu(false);
  });
  wert.classList.add("zp-ze-feld", "zp-wert");
  wert.dataset.fokus = `wert:${nummer}`;
  const einheit = document.createElement("span");
  einheit.className = "zp-einheit";
  einheit.textContent = grenzen.schalt ? "" : "°C";
  const weg = taste("✕", "zp-ze-weg", () => {
    modell.punkte.splice(nummer, 1);
    neu(true);
  });
  weg.title = t("Schaltzeit entfernen");
  weg.setAttribute("aria-label", t("Schaltzeit entfernen"));
  weg.dataset.fokus = `weg:${nummer}`;
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
    knopf.dataset.fokus = `tag:${tag}`;
    knopf.setAttribute("aria-pressed", String(modell.tage.includes(tag)));
    leiste.appendChild(knopf);
  });
  return leiste;
}

/** Der Schlüssel des Bedienelements im Editor, das gerade den Fokus hat. */
function fokusSchluessel(knoten) {
  const wurzel = knoten.getRootNode ? knoten.getRootNode() : document;
  const aktiv = wurzel.activeElement;
  return aktiv && knoten.contains(aktiv) ? aktiv.dataset.fokus || null : null;
}

/** Den Fokus nach dem Neuaufbau zurückgeben; eine entfernte Schaltzeit gibt ihn an die vorige ab. */
function fokusZurueck(knoten, schluessel) {
  if (!schluessel) return;
  const [art, stelle] = schluessel.split(":");
  const kandidaten = [schluessel];
  if (art === "weg") kandidaten.push(`weg:${Number(stelle) - 1}`);
  kandidaten.push("mehr", "zeit:0");
  const ziel = kandidaten
    .map((eintrag) => knoten.querySelector(`[data-fokus="${eintrag}"]`))
    .find((element) => element && !element.disabled);
  if (ziel) ziel.focus({ preventScroll: true });
}

function ueberschrift(text) {
  const kopf = document.createElement("div");
  kopf.className = "zp-ze-kopf";
  kopf.textContent = text;
  return kopf;
}

/**
 * Den Editor bauen. `modell` ({tage, punkte}) ändert er selbst; `speichern` bekommt es sortiert zurück
 * und liefert Fehlertexte oder nichts. `vortag` liefert zum Stand den Wert vor der ersten Schaltzeit.
 * `hinweis` steht beim Öffnen in der Meldungszeile.
 */
export function zeileneditorKnoten(modell, { grenzen, t = OHNE, speichern, abbrechen, vortag = () => null, hinweis = "" }) {
  const knoten = document.createElement("div");
  knoten.className = "zp-zeileneditor";
  const vorschau = document.createElement("div");
  vorschau.className = "zp-ze-vorschau";
  const meldung = document.createElement("div");
  meldung.className = "zp-meldung";
  meldung.setAttribute("role", "status");
  meldung.textContent = hinweis;

  const spurZeichnen = () => {
    const sortiert = [...modell.punkte].sort((a, b) => a.zeit - b.zeit);
    const morgen = vortag({ tage: [...modell.tage], punkte: sortiert });
    vorschau.replaceChildren(tagesspur(abschnitte(sortiert, morgen), grenzen, { t }));
  };
  const zeichnen = () => {
    const fokus = fokusSchluessel(knoten);
    const punkte = document.createElement("div");
    punkte.className = "zp-ze-punkte";
    modell.punkte.forEach((_, nummer) => punkte.appendChild(punktZeile(modell, nummer, { grenzen, t, neu })));
    const mehr = taste(t("+ Schaltzeit"), "zp-ze-mehr", () => {
      const zeit = neueSchaltzeit(modell.punkte);
      if (zeit === null) return;
      const wert = spaetesterWert(modell.punkte);
      modell.punkte.push({ zeit, wert: wert !== null ? wert : grenzen.schalt ? 1 : ERSTER_WERT });
      neu(true);
    });
    mehr.disabled = modell.punkte.length >= SCHALTPUNKTE_MAX || neueSchaltzeit(modell.punkte) === null;
    mehr.dataset.fokus = "mehr";
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
      ueberschrift(t("Schaltzeiten · jeder Wert gilt ab seiner Uhrzeit bis zur nächsten")),
      punkte,
      mehr,
      ueberschrift(t("Gilt für")),
      tagLeiste(modell, t, neu),
      vorschau,
      meldung,
      aktionen
    );
    spurZeichnen();
    fokusZurueck(knoten, fokus);
  };
  // Neue oder entfernte Zeilen bauen den Editor neu; ein geänderter Wert zeichnet nur die Spur.
  function neu(ganz) {
    if (ganz) zeichnen();
    else spurZeichnen();
  }
  knoten.addEventListener("keydown", (ereignis) => {
    if (ereignis.key !== "Escape") return;
    ereignis.preventDefault();
    ereignis.stopPropagation();
    abbrechen();
  });
  zeichnen();
  return knoten;
}
