/**
 * Zeitprogramme: lesen, zeichnen, bearbeiten.
 *
 * Die Anlage speichert ein Zeitprogramm als **Blöcke**: je Block eine Menge
 * von Wochentagen und bis zu sechs Schaltzeiten. Genau so wird es hier auch
 * bearbeitet – ein Editor, der einzelne Tage aus einem Block herauslöst,
 * müsste Blöcke aufteilen und wieder zusammenführen, und das Ergebnis stünde
 * hinterher anders im Gerät, als der Nutzer es gesehen hat.
 *
 * Die Rechnung steht getrennt vom Zeichnen: `abschnitte`, `pruefen` und
 * `nachDienst` sind reine Funktionen und werden in `tests/test_zeitprogramm.py`
 * in Node geprüft. Der Rest baut daraus Knoten.
 *
 * **Keine Backticks in Kommentaren** – siehe `stil.js`.
 */

import { SCHALTPUNKTE_MAX, WOCHENTAGE } from "./ordnung.js";

/** Minuten eines vollen Tages. */
export const TAG_MINUTEN = 24 * 60;

/** Die Wochentage in der Reihenfolge der Woche, wie die Anlage sie schreibt. */
export const TAGE = WOCHENTAGE.map(([code]) => code);

const TAG_TEXT = new Map(WOCHENTAGE);

// Deutsch wie englisch annehmen: Die Anlage liefert "Tu", der Dienst und die
// Beispiele in der Dokumentation kennen auch "Di".
const TAG_CODE = new Map();
WOCHENTAGE.forEach(([code, text]) => {
  TAG_CODE.set(code.toLowerCase(), code);
  TAG_CODE.set(text.toLowerCase(), code);
});

// Farben der Balken. Dieselben Werte wie im Anlagenschaubild (`schema.py`),
// damit kalt und warm überall dasselbe bedeuten.
const FARBE_KALT = [37, 80, 143];
const FARBE_WARM = [226, 84, 58];
const FARBE_AUS = "rgba(255, 255, 255, 0.06)";

/** Beschriftung eines Wochentags. */
export function tagText(code) {
  return TAG_TEXT.get(code) || code;
}

/** Wochentag auf den Code der Anlage bringen; unbekannt ergibt `null`. */
export function tagCode(tag) {
  return TAG_CODE.get(String(tag).trim().toLowerCase()) || null;
}

/** "06:30" in Minuten seit Mitternacht; ungültig ergibt `null`. */
export function minuten(zeit) {
  const treffer = /^(\d{1,2}):(\d{2})$/.exec(String(zeit).trim());
  if (!treffer) return null;
  const stunde = Number(treffer[1]);
  const minute = Number(treffer[2]);
  if (stunde > 23 || minute > 59) return null;
  return stunde * 60 + minute;
}

/** Minuten seit Mitternacht als "06:30". */
export function uhrzeit(wert) {
  const rund = Math.max(0, Math.min(TAG_MINUTEN - 1, Math.round(Number(wert) || 0)));
  const stunde = String(Math.floor(rund / 60)).padStart(2, "0");
  const minute = String(rund % 60).padStart(2, "0");
  return `${stunde}:${minute}`;
}

/**
 * Die Blöcke der Anlage in die Form bringen, mit der hier gearbeitet wird.
 *
 * Aus `{weekdays, switchPoints:[{time, value}]}` wird `{tage, punkte:[{zeit,
 * wert}]}` – Zeiten als Minuten, damit gerechnet werden kann. Was sich nicht
 * lesen lässt, fällt weg: Ein unlesbarer Schaltpunkt darf nicht dazu führen,
 * dass das ganze Programm leer aussieht.
 */
export function bloeckeLesen(roh) {
  if (!Array.isArray(roh)) return [];
  return roh
    .filter((block) => block && typeof block === "object")
    .map((block) => {
      const tage = [];
      (block.weekdays || []).forEach((tag) => {
        const code = tagCode(tag);
        if (code && !tage.includes(code)) tage.push(code);
      });
      const punkte = (block.switchPoints || [])
        .map((punkt) => ({
          zeit: minuten(punkt && punkt.time),
          wert: Number(punkt && punkt.value),
        }))
        .filter((punkt) => punkt.zeit !== null && Number.isFinite(punkt.wert))
        .sort((a, b) => a.zeit - b.zeit);
      return { tage: TAGE.filter((code) => tage.includes(code)), punkte };
    });
}

/**
 * Aus Schaltpunkten die Abschnitte eines Tages.
 *
 * Ein Schaltpunkt gilt, bis der nächste kommt. **Vor dem ersten gilt der
 * letzte des Tages weiter** – die Anlage schaltet um Mitternacht nicht ab,
 * sondern behält den Wert. Ohne diesen Umlauf stünde jeder Tag bis zur ersten
 * Schaltzeit leer da, obwohl geheizt wird.
 */
export function abschnitte(punkte) {
  if (!punkte || !punkte.length) return [];
  const sortiert = [...punkte].sort((a, b) => a.zeit - b.zeit);
  const stuecke = [];
  const letzter = sortiert[sortiert.length - 1];
  if (sortiert[0].zeit > 0) {
    stuecke.push({ von: 0, bis: sortiert[0].zeit, wert: letzter.wert });
  }
  sortiert.forEach((punkt, stelle) => {
    const bis = stelle + 1 < sortiert.length ? sortiert[stelle + 1].zeit : TAG_MINUTEN;
    if (bis > punkt.zeit) stuecke.push({ von: punkt.zeit, bis, wert: punkt.wert });
  });
  return stuecke;
}

/** Zu jedem Wochentag seine Abschnitte – auch zu Tagen ohne Block. */
export function wochenraster(bloecke) {
  return TAGE.map((tag) => {
    const block = (bloecke || []).find((eintrag) => eintrag.tage.includes(tag));
    return { tag, text: tagText(tag), abschnitte: block ? abschnitte(block.punkte) : [] };
  });
}

/**
 * Wochentage kurz benennen: „täglich", „Mo–Fr", „Mo–Mi, Sa".
 *
 * Sieben gleiche Zeilen untereinander sagen nichts, was eine Zeile „täglich"
 * nicht auch sagt. Zusammenhängende Tage werden zu einer Spanne, ab drei
 * Tagen mit Gedankenstrich – bei zweien wäre „Sa–So" länger als „Sa, So".
 */
export function tagesbereich(tage) {
  const gewaehlt = TAGE.filter((tag) => (tage || []).includes(tag));
  if (!gewaehlt.length) return "kein Tag";
  if (gewaehlt.length === 7) return "täglich";
  const spannen = [];
  gewaehlt.forEach((tag) => {
    const stelle = TAGE.indexOf(tag);
    const letzte = spannen[spannen.length - 1];
    if (letzte && stelle === letzte.bis + 1) letzte.bis = stelle;
    else spannen.push({ von: stelle, bis: stelle });
  });
  return spannen
    .map(({ von, bis }) => {
      if (von === bis) return tagText(TAGE[von]);
      if (bis - von === 1) return `${tagText(TAGE[von])}, ${tagText(TAGE[bis])}`;
      return `${tagText(TAGE[von])}–${tagText(TAGE[bis])}`;
    })
    .join(", ");
}

/**
 * Das Raster nach **Blöcken** statt nach Tagen.
 *
 * So führt die Anlage es, und so ist es zu lesen: Ein Programm mit einem
 * einzigen Block für die ganze Woche steht in einer Zeile „täglich" statt in
 * sieben gleichen. Tage ohne Block bekommen eine eigene, leere Zeile – sonst
 * fiele nicht auf, dass Samstag nirgends vorkommt.
 */
export function blockraster(bloecke) {
  const zeilen = (bloecke || [])
    .filter((block) => block.tage.length)
    .map((block) => ({
      text: tagesbereich(block.tage),
      tage: [...block.tage],
      abschnitte: abschnitte(block.punkte),
      punkte: [...block.punkte].sort((a, b) => a.zeit - b.zeit),
    }));
  const belegt = new Set(zeilen.flatMap((zeile) => zeile.tage));
  const offen = TAGE.filter((tag) => !belegt.has(tag));
  if (offen.length) {
    zeilen.push({ text: tagesbereich(offen), tage: offen, abschnitte: [], punkte: [] });
  }
  return zeilen;
}

/**
 * Ein Schaltprogramm kennt nur Ein und Aus.
 *
 * Zirkulation und Freigabezeiten schreiben 0/1, Heizprogramme Temperaturen.
 * Die Anlage sagt es nicht dazu; sie steht in beiden Fällen unter derselben
 * Typkennung. Am Wertebereich ist es aber eindeutig – eine Solltemperatur von
 * 1 °C gibt es nicht.
 */
export function istSchaltprogramm(bloecke) {
  const werte = (bloecke || []).flatMap((block) => block.punkte.map((punkt) => punkt.wert));
  return werte.length > 0 && werte.every((wert) => wert === 0 || wert === 1);
}

/** Wertebereich für die Färbung. */
export function bereich(bloecke) {
  if (istSchaltprogramm(bloecke)) return { min: 0, max: 1, schalt: true };
  const werte = (bloecke || []).flatMap((block) => block.punkte.map((punkt) => punkt.wert));
  if (!werte.length) return { min: 10, max: 25, schalt: false };
  const min = Math.min(...werte);
  const max = Math.max(...werte);
  // Bei nur einem Wert gäbe es keine Spanne; dann ist alles gleich warm.
  return { min, max: max > min ? max : min + 1, schalt: false };
}

/** Farbe eines Abschnitts: kalt nach warm, bzw. Ein und Aus. */
export function farbe(wert, grenzen) {
  if (grenzen.schalt) return wert >= 0.5 ? "rgb(226, 84, 58)" : FARBE_AUS;
  const spanne = grenzen.max - grenzen.min || 1;
  const anteil = Math.max(0, Math.min(1, (wert - grenzen.min) / spanne));
  const kanal = (stelle) =>
    Math.round(FARBE_KALT[stelle] + (FARBE_WARM[stelle] - FARBE_KALT[stelle]) * anteil);
  return `rgb(${kanal(0)}, ${kanal(1)}, ${kanal(2)})`;
}

/** Ein Wert, wie er am Balken und in der Tabelle steht. */
export function wertText(wert, grenzen) {
  if (grenzen.schalt) return wert >= 0.5 ? "Ein" : "Aus";
  const gerundet = Math.round(wert * 10) / 10;
  return `${gerundet} °C`;
}

/**
 * Was die Anlage nicht annehmen würde.
 *
 * Lieber hier ablehnen als das Gerät kommentarlos kürzen lassen: Über sechs
 * Schaltzeiten je Block schneidet es ab, und ein Wochentag in zwei Blöcken
 * ergibt zwei widersprüchliche Programme für denselben Tag.
 */
export function pruefen(bloecke) {
  const fehler = [];
  if (!bloecke || !bloecke.length) {
    return ["Mindestens ein Block wird gebraucht."];
  }
  const vergeben = new Map();
  bloecke.forEach((block, stelle) => {
    const nummer = stelle + 1;
    if (!block.tage.length) fehler.push(`Block ${nummer}: kein Wochentag gewählt.`);
    if (!block.punkte.length) fehler.push(`Block ${nummer}: keine Schaltzeit angegeben.`);
    if (block.punkte.length > SCHALTPUNKTE_MAX) {
      fehler.push(`Block ${nummer}: höchstens ${SCHALTPUNKTE_MAX} Schaltzeiten.`);
    }
    const zeiten = new Set();
    block.punkte.forEach((punkt) => {
      if (punkt.zeit === null || !Number.isFinite(punkt.wert)) {
        fehler.push(`Block ${nummer}: unvollständige Schaltzeit.`);
        return;
      }
      if (zeiten.has(punkt.zeit)) {
        fehler.push(`Block ${nummer}: ${uhrzeit(punkt.zeit)} steht doppelt.`);
      }
      zeiten.add(punkt.zeit);
    });
    block.tage.forEach((tag) => {
      if (vergeben.has(tag)) {
        fehler.push(`${tagText(tag)} steht in Block ${vergeben.get(tag)} und ${nummer}.`);
      } else {
        vergeben.set(tag, nummer);
      }
    });
  });
  return [...new Set(fehler)];
}

/** Die Blöcke in der Form, die `heatnexus.set_time_program` erwartet. */
export function nachDienst(bloecke) {
  return (bloecke || []).map((block) => ({
    weekdays: [...block.tage],
    switch_points: [...block.punkte]
      .sort((a, b) => a.zeit - b.zeit)
      .map((punkt) => ({ time: uhrzeit(punkt.zeit), value: punkt.wert })),
  }));
}

/**
 * Zwei Programme vergleichen, ohne auf die Schreibweise zu achten.
 *
 * Damit erkennt die Rückmeldung, ob die Anlage das Geschriebene wirklich
 * übernommen hat: Sie meldet dieselben Blöcke zurück, nur in ihrer eigenen
 * Reihenfolge und mit "21" statt "21.0".
 */
export function gleich(einer, anderer) {
  const kennung = (bloecke) =>
    JSON.stringify(
      (bloecke || [])
        .map((block) => ({
          tage: [...block.tage].sort(),
          punkte: [...block.punkte]
            .sort((a, b) => a.zeit - b.zeit)
            .map((punkt) => [punkt.zeit, Math.round(punkt.wert * 10) / 10]),
        }))
        .sort((a, b) => (a.tage[0] || "").localeCompare(b.tage[0] || ""))
    );
  return kennung(einer) === kennung(anderer);
}

// ---------------------------------------------------------------------------
// Zeichnen
// ---------------------------------------------------------------------------

/**
 * Das Wochenraster: sieben Zeilen, darin die Schaltzeiten als Balken.
 *
 * Die Breite kommt in Prozent, nicht in Bildpunkten – die Karte ist mal halb
 * so breit wie der Bildschirm und mal ganz. Dasselbe hat beim Heizkörper im
 * Schaubild einmal ein gestreiftes Ergebnis erzeugt.
 */
export function rasterKnoten(bloecke) {
  const grenzen = bereich(bloecke);
  const raster = document.createElement("div");
  raster.className = "zeitraster";

  const kopf = document.createElement("div");
  kopf.className = "zeitraster-skala";
  [0, 6, 12, 18, 24].forEach((stunde) => {
    const marke = document.createElement("span");
    marke.textContent = `${stunde}`;
    kopf.appendChild(marke);
  });
  raster.appendChild(kopf);

  blockraster(bloecke).forEach((zeile) => {
    const gruppe = document.createElement("div");
    gruppe.className = "zeitraster-block";

    const reihe = document.createElement("div");
    reihe.className = "zeitraster-zeile";

    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = zeile.text;

    const spur = document.createElement("div");
    spur.className = "spur";
    if (!zeile.abschnitte.length) {
      spur.classList.add("leer");
      spur.title = "kein Programm";
    }
    zeile.abschnitte.forEach((stueck) => {
      const balken = document.createElement("div");
      balken.className = "balken";
      balken.style.left = `${(stueck.von / TAG_MINUTEN) * 100}%`;
      balken.style.width = `${((stueck.bis - stueck.von) / TAG_MINUTEN) * 100}%`;
      balken.style.background = farbe(stueck.wert, grenzen);
      balken.title = `${uhrzeit(stueck.von)}–${uhrzeit(stueck.bis % TAG_MINUTEN)} · ${wertText(
        stueck.wert,
        grenzen
      )}`;
      spur.appendChild(balken);
    });

    reihe.append(tag, spur);
    gruppe.appendChild(reihe);

    // Die Schaltzeiten noch einmal als Text. Aus dem Balken allein liest
    // niemand ab, ob um 05:00 oder um 05:30 geschaltet wird.
    if (zeile.punkte.length) {
      const zeiten = document.createElement("div");
      zeiten.className = "zeitraster-zeiten";
      zeile.punkte.forEach((punkt) => {
        const marke = document.createElement("span");
        marke.className = "schaltzeit";
        const punktfarbe = document.createElement("i");
        punktfarbe.style.background = farbe(punkt.wert, grenzen);
        const text = document.createElement("span");
        // Strich zwischen Uhrzeit und Wert. Ohne ihn standen „06:00" und
        // „21,0 °C" nur durch ein Leerzeichen getrennt nebeneinander und
        // lasen sich wie eine einzige Angabe.
        text.textContent = `${uhrzeit(punkt.zeit)} – ${wertText(punkt.wert, grenzen)}`;
        marke.append(punktfarbe, text);
        zeiten.appendChild(marke);
      });
      gruppe.appendChild(zeiten);
    }

    raster.appendChild(gruppe);
  });

  return raster;
}

/**
 * Der Editor: je Block die Wochentage und eine Tabelle der Schaltzeiten.
 *
 * Zurück kommt der Knoten und ein `lesen()`, das den aktuellen Stand als
 * Blöcke liefert. Der Zustand liegt in einem eigenen Modell und nicht in den
 * Eingabefeldern: Beim Hinzufügen einer Zeile entstehen die Felder neu, und
 * was nur im DOM stünde, wäre dann weg.
 */
export function editorKnoten(bloecke, optionen = {}) {
  const grenzen = optionen.grenzen || bereich(bloecke);
  // Eine eigene Kopie – solange nicht gespeichert ist, bleibt der Stand der
  // Anlage unangetastet.
  const modell = (bloecke || []).map((block) => ({
    tage: [...block.tage],
    punkte: block.punkte.map((punkt) => ({ ...punkt })),
  }));

  const knoten = document.createElement("div");
  knoten.className = "zp-editor";

  const zeichnen = () => {
    knoten.textContent = "";
    modell.forEach((block, stelle) => knoten.appendChild(blockKnoten(block, stelle)));

    const anfuegen = document.createElement("button");
    anfuegen.type = "button";
    anfuegen.className = "zp-taste";
    anfuegen.textContent = "+ Block";
    anfuegen.title = "Ein eigener Wochenplan für weitere Tage";
    anfuegen.addEventListener("click", () => {
      const belegt = new Set(modell.flatMap((block) => block.tage));
      modell.push({
        tage: TAGE.filter((tag) => !belegt.has(tag)),
        punkte: [{ zeit: 6 * 60, wert: grenzen.schalt ? 1 : 20 }],
      });
      zeichnen();
    });
    knoten.appendChild(anfuegen);
  };

  // Ein Symbol aus dem Vorrat von Home Assistant. Ein „x" sah nach
  // „Fenster schließen" aus; der Mülleimer sagt, was wirklich passiert.
  const symbol = (name) => {
    const ikone = document.createElement("ha-icon");
    ikone.setAttribute("icon", name);
    return ikone;
  };

  const blockKnoten = (block, stelle) => {
    const kasten = document.createElement("div");
    kasten.className = "zp-block";

    const kopf = document.createElement("div");
    kopf.className = "zp-blockkopf";
    kopf.textContent = `Block ${stelle + 1} · ${tagesbereich(block.tage)}`;
    kasten.appendChild(kopf);

    const tage = document.createElement("div");
    tage.className = "zp-tage";
    TAGE.forEach((tag) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "zp-tag";
      taste.textContent = tagText(tag);
      const gewaehlt = block.tage.includes(tag);
      taste.setAttribute("aria-pressed", String(gewaehlt));
      taste.addEventListener("click", () => {
        if (block.tage.includes(tag)) {
          block.tage = block.tage.filter((eintrag) => eintrag !== tag);
        } else {
          // Ein Tag gehört immer nur einem Block; sonst stünden für denselben
          // Tag zwei Programme im Gerät.
          modell.forEach((anderer) => {
            if (anderer !== block) anderer.tage = anderer.tage.filter((e) => e !== tag);
          });
          block.tage = TAGE.filter((code) => code === tag || block.tage.includes(code));
        }
        zeichnen();
      });
      tage.appendChild(taste);
    });
    kasten.appendChild(tage);

    const tabelle = document.createElement("div");
    tabelle.className = "zp-punkte";
    block.punkte.forEach((punkt, nummer) => {
      tabelle.appendChild(punktZeile(block, punkt, nummer));
    });
    kasten.appendChild(tabelle);

    const leiste = document.createElement("div");
    leiste.className = "zp-blockleiste";

    const mehr = document.createElement("button");
    mehr.type = "button";
    mehr.className = "zp-taste";
    mehr.textContent = "+ Schaltzeit";
    mehr.disabled = block.punkte.length >= SCHALTPUNKTE_MAX;
    mehr.addEventListener("click", () => {
      const letzte = block.punkte[block.punkte.length - 1];
      const zeit = letzte ? Math.min(TAG_MINUTEN - 60, letzte.zeit + 60) : 6 * 60;
      block.punkte.push({ zeit, wert: letzte ? letzte.wert : grenzen.schalt ? 1 : 20 });
      zeichnen();
    });

    const weg = document.createElement("button");
    weg.type = "button";
    weg.className = "zp-taste";
    weg.append(symbol("mdi:trash-can-outline"));
    const wegText = document.createElement("span");
    wegText.textContent = "Block entfernen";
    weg.appendChild(wegText);
    weg.disabled = modell.length <= 1;
    weg.addEventListener("click", () => {
      modell.splice(stelle, 1);
      zeichnen();
    });

    leiste.append(mehr, weg);
    kasten.appendChild(leiste);
    return kasten;
  };

  const punktZeile = (block, punkt, nummer) => {
    const zeile = document.createElement("div");
    zeile.className = "zp-punkt";

    const zeit = document.createElement("input");
    zeit.type = "time";
    zeit.value = uhrzeit(punkt.zeit);
    zeit.setAttribute("aria-label", "Schaltzeit");
    zeit.addEventListener("change", () => {
      const gelesen = minuten(zeit.value);
      if (gelesen !== null) punkt.zeit = gelesen;
      else zeit.value = uhrzeit(punkt.zeit);
    });

    // Die Einheit hinter der Uhrzeit. Ohne sie steht im Editor eine nackte
    // Zeit neben einer nackten Zahl, und beim ersten Hinsehen ist nicht klar,
    // welches Feld was ist.
    const zeitEinheit = document.createElement("span");
    zeitEinheit.className = "zp-einheit";
    zeitEinheit.textContent = "Uhr";

    let wert;
    if (grenzen.schalt) {
      wert = document.createElement("select");
      [
        ["1", "Ein"],
        ["0", "Aus"],
      ].forEach(([schluessel, text]) => {
        const eintrag = document.createElement("option");
        eintrag.value = schluessel;
        eintrag.textContent = text;
        wert.appendChild(eintrag);
      });
      wert.value = punkt.wert >= 0.5 ? "1" : "0";
      wert.addEventListener("change", () => {
        punkt.wert = Number(wert.value);
      });
    } else {
      wert = document.createElement("input");
      wert.type = "number";
      wert.step = "0.5";
      wert.min = "5";
      wert.max = "40";
      wert.value = String(punkt.wert);
      wert.addEventListener("change", () => {
        const gelesen = Number(wert.value);
        if (Number.isFinite(gelesen)) punkt.wert = gelesen;
        else wert.value = String(punkt.wert);
      });
    }
    wert.setAttribute("aria-label", grenzen.schalt ? "Schaltzustand" : "Solltemperatur");
    wert.className = "zp-wert";

    // Die Einheit hinter das Feld. Ohne sie steht im Editor eine nackte Zahl,
    // während im Raster darunter „05:30 21 °C" steht – und man rechnet kurz,
    // ob 21 nun Grad oder eine Uhrzeit ist. Beim Schaltzustand („Ein"/„Aus")
    // gibt es nichts zu ergänzen.
    const einheiten = document.createElement("span");
    einheiten.className = "zp-einheit";
    einheiten.textContent = grenzen.schalt ? "" : "°C";

    const weg = document.createElement("button");
    weg.type = "button";
    weg.className = "zp-weg";
    weg.appendChild(symbol("mdi:trash-can-outline"));
    weg.title = "Schaltzeit entfernen";
    weg.setAttribute("aria-label", "Schaltzeit entfernen");
    weg.addEventListener("click", () => {
      block.punkte.splice(nummer, 1);
      zeichnen();
    });

    zeile.append(zeit, zeitEinheit, wert, einheiten, weg);
    return zeile;
  };

  zeichnen();

  return {
    knoten,
    lesen: () =>
      modell.map((block) => ({
        tage: TAGE.filter((tag) => block.tage.includes(tag)),
        punkte: [...block.punkte].sort((a, b) => a.zeit - b.zeit),
      })),
  };
}
