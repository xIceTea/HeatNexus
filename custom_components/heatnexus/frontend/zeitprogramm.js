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

/** Höchstlänge der eigenen Bezeichnung; muss zu `bezeichnung.py` passen. */
export const BEZEICHNUNG_MAX = 40;

/** „Heizprogramm 3 – Übergangszeit“; ohne Bezeichnung bleibt der Name allein. */
export function mitBezeichnung(name, bezeichnung) {
  const zusatz = String(bezeichnung || "").trim();
  return zusatz ? `${name} – ${zusatz}` : name;
}

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
const FARBE_EIN = "var(--hn-akzent, rgb(226, 84, 58))";

/** Ohne Wörterbuch bleibt der deutsche Text stehen. */
const OHNE = (text) => text;

/** Beschriftung eines Wochentags, auf Wunsch übersetzt. */
export function tagText(code, t = OHNE) {
  return t(TAG_TEXT.get(code) || code);
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

// Ein Formatter je Zone: Sein Aufbau kostet, und die Oberfläche fragt bei jeder Aktualisierung.
const FORMATTER = new Map();

function formatter(zone) {
  if (!FORMATTER.has(zone)) {
    FORMATTER.set(
      zone,
      new Intl.DateTimeFormat("en-GB", {
        timeZone: zone,
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      })
    );
  }
  return FORMATTER.get(zone);
}

/** Wochentag und Minute in der Zeitzone von Home Assistant; ohne gültige Zone die des Browsers. */
export function ortszeit(datum, zeitzone) {
  let teile;
  try {
    teile = formatter(zeitzone || undefined).formatToParts(datum);
  } catch {
    teile = formatter(undefined).formatToParts(datum);
  }
  const teil = (art) => (teile.find((eintrag) => eintrag.type === art) || {}).value || "";
  return {
    tag: tagCode(teil("weekday").slice(0, 2)),
    minute: Number(teil("hour")) * 60 + Number(teil("minute")),
  };
}

/** Block und Abschnitt, die zu dieser Zeit gelten; 'null', wenn der Tag keinen Block hat. */
export function jetztStelle(bloecke, zeit) {
  if (!zeit || !zeit.tag) return null;
  const block = (bloecke || []).findIndex((eintrag) => eintrag.tage.includes(zeit.tag));
  if (block < 0) return null;
  const stueck = abschnitte(bloecke[block].punkte).find(
    (eintrag) => eintrag.von <= zeit.minute && zeit.minute < eintrag.bis
  );
  return stueck ? { block, von: stueck.von } : null;
}

/** Die Abschnitte des Tages, der zu dieser Zeit gilt; leer, wenn der Tag keinen Block hat. */
export function tagesabschnitte(bloecke, tag) {
  const block = (bloecke || []).find((eintrag) => eintrag.tage.includes(tag));
  return block ? abschnitte(block.punkte) : [];
}

/** Der Wert, der zu dieser Zeit gilt; 'null' ohne Block für den Tag. */
export function wertJetzt(bloecke, zeit) {
  if (!zeit || !zeit.tag) return null;
  const stueck = tagesabschnitte(bloecke, zeit.tag).find(
    (eintrag) => eintrag.von <= zeit.minute && zeit.minute < eintrag.bis
  );
  return stueck ? stueck.wert : null;
}

/**
 * Der nächste Abschnitt mit anderem Wert, höchstens eine Woche voraus.
 *
 * Gleicher Wert nach Mitternacht ist kein Wechsel; ohne Wechsel ergibt sich 'null'.
 */
export function naechsterWechsel(bloecke, zeit) {
  const jetzt = wertJetzt(bloecke, zeit);
  if (jetzt === null) return null;
  const start = TAGE.indexOf(zeit.tag);
  for (let tage = 0; tage <= 7; tage += 1) {
    const tag = TAGE[(start + tage) % TAGE.length];
    const treffer = tagesabschnitte(bloecke, tag).find(
      (stueck) => stueck.wert !== jetzt && (tage > 0 || stueck.von > zeit.minute)
    );
    if (treffer) return { tag, tage, minute: treffer.von, wert: treffer.wert };
  }
  return null;
}

/**
 * Wochentage kurz benennen: „täglich", „Mo–Fr", „Mo–Mi, Sa".
 *
 * Sieben gleiche Zeilen untereinander sagen nichts, was eine Zeile „täglich"
 * nicht auch sagt. Zusammenhängende Tage werden zu einer Spanne, ab drei
 * Tagen mit Gedankenstrich – bei zweien wäre „Sa–So" länger als „Sa, So".
 */
export function tagesbereich(tage, t = OHNE) {
  const gewaehlt = TAGE.filter((tag) => (tage || []).includes(tag));
  if (!gewaehlt.length) return t("kein Tag");
  if (gewaehlt.length === 7) return t("täglich");
  const spannen = [];
  gewaehlt.forEach((tag) => {
    const stelle = TAGE.indexOf(tag);
    const letzte = spannen[spannen.length - 1];
    if (letzte && stelle === letzte.bis + 1) letzte.bis = stelle;
    else spannen.push({ von: stelle, bis: stelle });
  });
  return spannen
    .map(({ von, bis }) => {
      if (von === bis) return tagText(TAGE[von], t);
      if (bis - von === 1) return `${tagText(TAGE[von], t)}, ${tagText(TAGE[bis], t)}`;
      return `${tagText(TAGE[von], t)}–${tagText(TAGE[bis], t)}`;
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
export function blockraster(bloecke, t = OHNE) {
  const zeilen = (bloecke || [])
    .filter((block) => block.tage.length)
    .map((block) => ({
      text: tagesbereich(block.tage, t),
      tage: [...block.tage],
      abschnitte: abschnitte(block.punkte),
      punkte: [...block.punkte].sort((a, b) => a.zeit - b.zeit),
    }));
  const belegt = new Set(zeilen.flatMap((zeile) => zeile.tage));
  const offen = TAGE.filter((tag) => !belegt.has(tag));
  if (offen.length) {
    zeilen.push({ text: tagesbereich(offen, t), tage: offen, abschnitte: [], punkte: [] });
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

/** Feste Farbskalen: gleiche Temperatur, gleiche Farbe, in jedem Programm. */
export const SKALEN = {
  raum: { min: 14, max: 24 },
  wasser: { min: 40, max: 65 },
};

// Ohne Angabe des Servers entscheidet der Wert: eine Raumtemperatur über 30 °C gibt es nicht.
const RAUM_HOECHSTENS = 30;

/** Die Skala eines Programms; Vorlauf ist Wassertemperatur und liegt auf der Wasserskala. */
export function skala(bloecke, art) {
  if (istSchaltprogramm(bloecke)) return { min: 0, max: 1, schalt: true, art: "schalt" };
  let name = art === "vorlauf" ? "wasser" : art;
  if (!SKALEN[name]) {
    const werte = (bloecke || []).flatMap((block) => block.punkte.map((punkt) => punkt.wert));
    name = werte.length && Math.max(...werte) > RAUM_HOECHSTENS ? "wasser" : "raum";
  }
  return { ...SKALEN[name], schalt: false, art: name };
}

/** Farbe eines Abschnitts: kalt nach warm, bzw. Ein und Aus. */
export function farbe(wert, grenzen) {
  if (grenzen.schalt) return wert >= 0.5 ? FARBE_EIN : FARBE_AUS;
  const spanne = grenzen.max - grenzen.min || 1;
  const anteil = Math.max(0, Math.min(1, (wert - grenzen.min) / spanne));
  const kanal = (stelle) =>
    Math.round(FARBE_KALT[stelle] + (FARBE_WARM[stelle] - FARBE_KALT[stelle]) * anteil);
  return `rgb(${kanal(0)}, ${kanal(1)}, ${kanal(2)})`;
}

/** Ein Wert, wie er am Balken und in der Tabelle steht; `t` übersetzt Ein und Aus. */
export function wertText(wert, grenzen, t = OHNE) {
  if (grenzen.schalt) return wert >= 0.5 ? t("Ein") : t("Aus");
  const gerundet = Math.round(wert * 10) / 10;
  return `${gerundet} °C`;
}

/** Platzhalter wie `{nummer}` durch Werte ersetzen. */
export function einsetzen(text, werte) {
  return Object.entries(werte).reduce((s, [k, v]) => s.split(`{${k}}`).join(String(v)), text);
}

/**
 * Was die Anlage nicht annehmen würde.
 *
 * Lieber hier ablehnen als das Gerät kommentarlos kürzen lassen: Über sechs
 * Schaltzeiten je Block schneidet es ab, und ein Wochentag in zwei Blöcken
 * ergibt zwei widersprüchliche Programme für denselben Tag.
 */
export function pruefen(bloecke, t = OHNE) {
  const fehler = [];
  const satz = (text, werte) => einsetzen(t(text), werte);
  if (!bloecke || !bloecke.length) {
    return [t("Mindestens ein Block wird gebraucht.")];
  }
  const vergeben = new Map();
  bloecke.forEach((block, stelle) => {
    const nummer = stelle + 1;
    if (!block.tage.length) fehler.push(satz("Block {nummer}: kein Wochentag gewählt.", { nummer }));
    if (!block.punkte.length) fehler.push(satz("Block {nummer}: keine Schaltzeit angegeben.", { nummer }));
    if (block.punkte.length > SCHALTPUNKTE_MAX) {
      fehler.push(satz("Block {nummer}: höchstens {max} Schaltzeiten.", { nummer, max: SCHALTPUNKTE_MAX }));
    }
    const zeiten = new Set();
    block.punkte.forEach((punkt) => {
      if (punkt.zeit === null || !Number.isFinite(punkt.wert)) {
        fehler.push(satz("Block {nummer}: unvollständige Schaltzeit.", { nummer }));
        return;
      }
      if (zeiten.has(punkt.zeit)) {
        fehler.push(satz("Block {nummer}: {zeit} steht doppelt.", { nummer, zeit: uhrzeit(punkt.zeit) }));
      }
      zeiten.add(punkt.zeit);
    });
    block.tage.forEach((tag) => {
      if (vergeben.has(tag)) {
        fehler.push(
          satz("{tag} steht in Block {erster} und {nummer}.", {
            tag: tagText(tag, t),
            erster: vergeben.get(tag),
            nummer,
          })
        );
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

// Ab dieser Länge in Minuten steht der Wert im Segment; kürzere zeigen ihn im Tooltip.
const WERT_IM_SEGMENT_AB = 120;

/**
 * Eine 24-h-Spur aus Abschnitten, auf Wunsch mit Werten und Jetzt-Linie.
 *
 * Breiten in Prozent: Die Karte ist mal eine Spalte breit und mal vier.
 */
export function spurKnoten(stuecke, grenzen, optionen = {}) {
  const t = optionen.t || OHNE;
  const spur = document.createElement("div");
  spur.className = optionen.duenn ? "spur duenn" : "spur";
  if (!stuecke.length) {
    spur.classList.add("leer");
    spur.title = t("kein Programm");
  }
  stuecke.forEach((stueck) => {
    const balken = document.createElement("div");
    balken.className = "balken";
    balken.style.left = `${(stueck.von / TAG_MINUTEN) * 100}%`;
    balken.style.width = `${((stueck.bis - stueck.von) / TAG_MINUTEN) * 100}%`;
    balken.style.background = farbe(stueck.wert, grenzen);
    const text = wertText(stueck.wert, grenzen, t);
    balken.title = `${uhrzeit(stueck.von)}–${uhrzeit(stueck.bis % TAG_MINUTEN)} · ${text}`;
    // Bei Ein/Aus trägt nur „Ein“ eine Beschriftung; „Aus“ ist die leere Spur.
    const aus = grenzen.schalt && stueck.wert < 0.5;
    if (optionen.werte && !aus && stueck.bis - stueck.von >= WERT_IM_SEGMENT_AB) {
      const wert = document.createElement("span");
      wert.className = "zp-segmentwert";
      wert.textContent = text;
      balken.appendChild(wert);
    }
    spur.appendChild(balken);
  });
  if (Number.isFinite(optionen.jetzt)) {
    const linie = document.createElement("div");
    linie.className = "jetzt-linie";
    linie.style.left = `${(optionen.jetzt / TAG_MINUTEN) * 100}%`;
    spur.appendChild(linie);
  }
  return spur;
}

/** Die Stundenmarken über einer 24-h-Spur. */
export function skalaKnoten() {
  const kopf = document.createElement("div");
  kopf.className = "zeitraster-skala";
  [0, 6, 12, 18, 24].forEach((stunde) => {
    const marke = document.createElement("span");
    marke.textContent = `${stunde}`;
    kopf.appendChild(marke);
  });
  return kopf;
}

function rasterZeile(text, spur, klasse = "") {
  const reihe = document.createElement("div");
  reihe.className = `zeitraster-zeile ${klasse}`.trim();
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = text;
  reihe.append(tag, spur);
  return reihe;
}

/**
 * Das Wochenraster: eine Zeile je Block, die Werte in den Segmenten.
 *
 * Mit jetzt trägt die Zeile des heutigen Tags die Jetzt-Linie; mit vorlauf folgt eine dünne Spur.
 */
export function rasterKnoten(bloecke, optionen = {}) {
  const t = optionen.t || OHNE;
  const grenzen = optionen.grenzen || skala(bloecke, optionen.art);
  const jetzt = optionen.jetzt || null;
  const raster = document.createElement("div");
  raster.className = "zeitraster";
  raster.appendChild(skalaKnoten());

  const zeilen = blockraster(bloecke, t);
  const vorlauf = optionen.vorlauf ? blockraster(optionen.vorlauf, t) : null;
  const vorlaufGrenzen = vorlauf ? skala(optionen.vorlauf, "vorlauf") : null;
  // Nur bei gleicher Tagesaufteilung steht die Vorlaufspur direkt unter der Raumspur.
  const passend =
    vorlauf &&
    vorlauf.length === zeilen.length &&
    vorlauf.every((zeile, n) => zeile.tage.join() === zeilen[n].tage.join());

  zeilen.forEach((zeile, n) => {
    const gruppe = document.createElement("div");
    gruppe.className = "zeitraster-block";
    const heute = jetzt && zeile.tage.includes(jetzt.tag) ? jetzt.minute : null;
    const spur = spurKnoten(zeile.abschnitte, grenzen, { t, werte: true, jetzt: heute });
    gruppe.appendChild(rasterZeile(zeile.text, spur));
    if (passend) {
      const duenn = spurKnoten(vorlauf[n].abschnitte, vorlaufGrenzen, { t, duenn: true });
      gruppe.appendChild(rasterZeile(t("Vorlauf"), duenn, "vorlauf"));
    }
    raster.appendChild(gruppe);
  });

  if (vorlauf && !passend) {
    const titel = document.createElement("div");
    titel.className = "zeitraster-abschnitt";
    titel.textContent = t("Vorlauf");
    raster.appendChild(titel);
    vorlauf.forEach((zeile) => {
      const gruppe = document.createElement("div");
      gruppe.className = "zeitraster-block";
      const duenn = spurKnoten(zeile.abschnitte, vorlaufGrenzen, { t, duenn: true });
      gruppe.appendChild(rasterZeile(zeile.text, duenn, "vorlauf"));
      raster.appendChild(gruppe);
    });
  }

  return raster;
}

/**
 * Die Leseansicht: je Block die Wochentage und die Abschnitte als „von – bis".
 *
 * **So steht es auch im Bediengerät.** Der Editor arbeitet mit Schaltpunkten –
 * ein Punkt gilt, bis der nächste kommt –, und das ist zum Einstellen richtig.
 * Zum Ablesen ist es die falsche Frage: Wer wissen will, wann geheizt wird,
 * will „06:00 – 19:00" lesen und nicht zwei Zeilen im Kopf zusammenrechnen.
 * Der Umlauf über Mitternacht steckt schon in `abschnitte`.
 * Mit jetzt (aus ortszeit) hebt sich die Zeile ab, die gerade gilt.
 */
export function uebersichtKnoten(bloecke, optionen = {}) {
  const t = optionen.t || OHNE;
  const grenzen = optionen.grenzen || skala(bloecke);
  const stelle = optionen.jetzt ? jetztStelle(bloecke, optionen.jetzt) : null;
  const knoten = document.createElement("div");
  knoten.className = "zp-uebersicht";

  (bloecke || []).forEach((block, nummer) => {
    const kasten = document.createElement("div");
    kasten.className = "zp-block";

    const kopf = document.createElement("div");
    kopf.className = "zp-blockkopf";
    kopf.textContent = tagesbereich(block.tage, t);
    kasten.appendChild(kopf);

    const liste = document.createElement("div");
    liste.className = "zp-spannen";
    abschnitte(block.punkte).forEach((stueck) => {
      const zeile = document.createElement("div");
      zeile.className = "zp-spanne";
      const punktfarbe = document.createElement("i");
      punktfarbe.style.background = farbe(stueck.wert, grenzen);
      const zeit = document.createElement("span");
      zeit.className = "zp-spannezeit";
      // `bis` steht auf 1440, wenn der Abschnitt bis Mitternacht läuft; als
      // Uhrzeit ist das 00:00.
      zeit.textContent = `${uhrzeit(stueck.von)} – ${uhrzeit(stueck.bis % TAG_MINUTEN)}`;
      const wert = document.createElement("span");
      wert.className = "zp-spannewert";
      wert.textContent = wertText(stueck.wert, grenzen, t);
      zeile.append(punktfarbe, zeit);
      // Die Marke steht vor dem Wert, damit die Werte untereinander bleiben.
      if (stelle && stelle.block === nummer && stelle.von === stueck.von) {
        zeile.classList.add("jetzt");
        zeile.setAttribute("aria-current", "time");
        const marke = document.createElement("span");
        marke.className = "zp-jetzt";
        marke.textContent = t("jetzt");
        zeile.appendChild(marke);
      }
      zeile.appendChild(wert);
      liste.appendChild(zeile);
    });
    kasten.appendChild(liste);
    knoten.appendChild(kasten);
  });

  return knoten;
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
  const t = optionen.t || OHNE;
  const grenzen = optionen.grenzen || skala(bloecke);
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
    anfuegen.textContent = t("+ Block");
    anfuegen.title = t("Ein eigener Wochenplan für weitere Tage");
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
    kopf.textContent = `${t("Block")} ${stelle + 1} · ${tagesbereich(block.tage, t)}`;
    kasten.appendChild(kopf);

    const tage = document.createElement("div");
    tage.className = "zp-tage";
    TAGE.forEach((tag) => {
      const taste = document.createElement("button");
      taste.type = "button";
      taste.className = "zp-tag";
      taste.textContent = tagText(tag, t);
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

    // **Was hier eingestellt wird, ist der Startpunkt, nicht die Spanne.**
    // Ein Punkt gilt, bis der nächste kommt; das Ende einer Spanne ist der
    // Anfang der nächsten. Ohne diese Überschrift liest man die Zeilen wie
    // die „von – bis" der Leseansicht und stellt das Falsche ein.
    const wozu = document.createElement("div");
    wozu.className = "zp-punktekopf";
    wozu.textContent = t("Startpunkt");
    kasten.appendChild(wozu);

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
    mehr.textContent = t("+ Schaltzeit");
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
    wegText.textContent = t("Block entfernen");
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
    zeit.setAttribute("aria-label", t("Schaltzeit"));
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
    zeitEinheit.textContent = t("Uhr");

    let wert;
    if (grenzen.schalt) {
      wert = document.createElement("select");
      [
        ["1", "Ein"],
        ["0", "Aus"],
      ].forEach(([schluessel, text]) => {
        const eintrag = document.createElement("option");
        eintrag.value = schluessel;
        eintrag.textContent = t(text);
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
    wert.setAttribute("aria-label", t(grenzen.schalt ? "Schaltzustand" : "Solltemperatur"));
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
    weg.title = t("Schaltzeit entfernen");
    weg.setAttribute("aria-label", t("Schaltzeit entfernen"));
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
