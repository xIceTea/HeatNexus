/**
 * Reiter „Zeitprogramme“: oben der Heute-Streifen, darunter eine Karte je Anlagenteil.
 *
 * Gerechnet wird in ../zeitprogramm.js und ../zeitprogrammseite.js; eingebunden als Mixin in heatnexus-panel.js.
 */

import { BREITE_MAX } from "../ordnung.js";
import {
  BEZEICHNUNG_MAX,
  bloeckeLesen,
  editorKnoten,
  gleich,
  mitBezeichnung,
  nachDienst,
  ortszeit,
  pruefen,
  rasterKnoten,
  skala,
  spurKnoten,
  tagesabschnitte,
  uebersichtKnoten,
} from "../zeitprogramm.js";
import { HEUTE_GRUPPEN, heuteText, legendeKnoten, nachTeilen } from "../zeitprogrammseite.js";

// Fußtexte der Gruppen, deren Programme einander ablösen; die übrigen nehmen den Hinweis ihres Programms.
const FUSS = {
  heizen: "Es wirkt nur das Programm, auf dem die Betriebswahl steht.",
  zirkulation: "Es wirkt nur das Programm der Steuerungsart, auf der die Zirkulationspumpe steht.",
};

/** Ein Programm ohne Schaltzeit braucht nur eine Zeile. */
const istLeer = (bloecke) => bloecke.every((block) => !block.punkte.length);

export const ZeitprogrammeMixin = (Basis) =>
  class extends Basis {
  /**
   * Eine Karte je Anlagenteil, in der Einzelansicht mit dem Heute-Streifen davor.
   *
   * Unter „Alle“ setzt das Panel einen gemeinsamen Streifen über alle Anlagen.
   */
  _zeitprogrammeReiter(anlage) {
    const karten = nachTeilen(anlage.zeitprogramme).map((teil) => ({
      id: `zeitprogramme:${teil.teil}`,
      titel: teil.anlagenteil,
      knoten: this._teilKarte(teil),
      breite: 2,
    }));
    if (this._alleAnlagen()) return karten;
    const heute = { id: "zeitprogramme:heute", titel: this._t("Heute"), breite: BREITE_MAX };
    return [{ ...heute, knoten: this._heuteKarte([anlage]) }, ...karten];
  }

  /** Der gemeinsame Heute-Streifen unter „Alle“, je Anlage eine Zwischenzeile. */
  _zeitprogrammeHeute() {
    const knoten = this._heuteKarte(this._anlagen());
    if (!knoten) return document.createElement("div");
    const karte = { id: "zeitprogramme:heute", titel: this._t("Heute"), knoten, breite: BREITE_MAX };
    return this._raster({ id: "alle" }, [karte], "");
  }

  /** Die Blöcke eines Programms; 'null', wenn die Entität keine führt. */
  _bloecke(entity) {
    const zustand = this._zustand(entity);
    const roh = zustand && zustand.attributes && zustand.attributes.blocks;
    return Array.isArray(roh) ? bloeckeLesen(roh) : null;
  }

  _ortszeit() {
    const zone = this._hass && this._hass.config && this._hass.config.time_zone;
    return ortszeit(this._jetzt(), zone);
  }

  /** Ob ein Programm gilt: das Heizprogramm bei einer Betriebswahl, das WW-Programm bei allen außer einer. */
  _gilt(programm) {
    const wirkung = programm.wirkung;
    if (!wirkung) return true;
    const zustand = this._zustand(wirkung.entity);
    const text = zustand ? String(zustand.state).toLowerCase() : "";
    return wirkung.muster_nicht ? !text.includes(wirkung.muster_nicht) : text.includes(wirkung.muster);
  }

  /** Sichtbare Programme der Gruppe, das geltende und das, das groß steht. */
  _gruppenStand(gruppe) {
    // Auch das Programm, das gerade nicht gilt, bleibt sichtbar: klein, mit „Aktivieren“.
    const sichtbar = gruppe.eintraege.filter(({ programm }) => this._bloecke(programm.entity) !== null);
    const aktiv = sichtbar.find(({ programm }) => this._gilt(programm)) || null;
    // Ein einzelnes Programm steht immer groß, auch wenn es gerade nicht wirkt.
    const gross = gruppe.eintraege.length === 1 ? sichtbar[0] || null : aktiv;
    return { sichtbar, aktiv, gross };
  }

  /** Der Stand der Auswahl, an der die Gruppe hängt: „Betriebswahl: Heizbetrieb“. */
  _wahlText(gruppe) {
    const mit = gruppe.eintraege.find(({ programm }) => programm.wirkung);
    const zustand = mit && this._zustand(mit.programm.wirkung.entity);
    if (!zustand) return "";
    const { entity, wahl_name: wahlName } = mit.programm.wirkung;
    const option = this._optionBeschriftung(entity, zustand.state);
    return wahlName ? `${wahlName}: ${option}` : option;
  }

  /** Arten der Farbskala, die auf der Seite vorkommen, für die Legende. */
  _skalenDerSeite(anlagen) {
    const arten = new Set();
    anlagen.forEach((anlage) =>
      (anlage.zeitprogramme || []).forEach((programm) => {
        const bloecke = this._bloecke(programm.entity);
        if (bloecke && !istLeer(bloecke)) arten.add(skala(bloecke, programm.art).art);
      })
    );
    return arten;
  }

  // -------------------------------------------------------------------
  // Heute-Streifen
  // -------------------------------------------------------------------
  _heuteKarte(anlagen) {
    const mitProgramm = anlagen.filter((anlage) => (anlage.zeitprogramme || []).length);
    if (!mitProgramm.length) return null;
    const karte = this._karte(this._t("Heute"));
    karte.classList.add("zp-heute");
    const kopf = document.createElement("div");
    kopf.className = "zp-heute-zeile zp-heute-kopf";
    const marken = document.createElement("div");
    marken.className = "zeitraster-skala";
    [0, 6, 12, 18, 24].forEach((stunde) => {
      const marke = document.createElement("span");
      marke.textContent = `${stunde}`;
      marken.appendChild(marke);
    });
    kopf.append(document.createElement("span"), marken, document.createElement("span"));
    karte.appendChild(kopf);
    mitProgramm.forEach((anlage) => {
      karte.appendChild(this._inSprache(anlage, (sicht) => sicht._heuteAnlage(anlage, anlagen.length > 1)));
    });
    karte.appendChild(legendeKnoten(this._skalenDerSeite(mitProgramm), this._t.bind(this)));
    return karte;
  }

  _heuteAnlage(anlage, mitName) {
    const gruppe = document.createElement("div");
    gruppe.className = "zp-heute-anlage";
    if (mitName) {
      const name = document.createElement("div");
      name.className = "zp-heute-anlagenname";
      name.textContent = anlage.name || "Anlage";
      name.dataset.roh = "";
      gruppe.appendChild(name);
    }
    nachTeilen(anlage.zeitprogramme).forEach((teil) => {
      teil.gruppen
        .filter((eintrag) => HEUTE_GRUPPEN.has(eintrag.gruppe))
        .forEach((eintrag) => gruppe.appendChild(this._heuteZeile(teil, eintrag)));
    });
    return gruppe;
  }

  /** Eine Zeile: Anlagenteil, der heutige Tag des geltenden Programms, rechts jetzt und der nächste Wechsel. */
  _heuteZeile(teil, gruppe) {
    const zeile = document.createElement("div");
    zeile.className = "zp-heute-zeile";
    zeile.dataset.gruppe = gruppe.gruppe;
    const name = document.createElement("div");
    name.className = "zp-heute-name";
    const erstes = gruppe.eintraege[0].programm;
    if (erstes.symbol) name.appendChild(this._symbolKnoten(erstes.symbol));
    const titel = document.createElement("span");
    titel.className = "zp-heute-titel";
    titel.textContent = gruppe.gruppe === "warmwasser" ? this._t("Warmwasser") : teil.anlagenteil;
    if (gruppe.gruppe !== "warmwasser") titel.dataset.roh = "";
    const programm = document.createElement("span");
    programm.className = "zp-heute-programm";
    programm.dataset.roh = "";
    name.append(titel, programm);
    const spur = document.createElement("div");
    spur.className = "zeitraster zp-heute-spur";
    const text = document.createElement("div");
    text.className = "zp-heute-text";
    zeile.append(name, spur, text);
    const teile = { programm, spur, text, anlagenteil: teil.anlagenteil };
    let stand = null;
    this._bindungen.push(() => {
      const kennung = this._gruppenKennung(gruppe);
      if (kennung === stand) return;
      stand = kennung;
      this._heuteZeichnen(gruppe, teile);
    });
    return zeile;
  }

  _heuteZeichnen(gruppe, teile) {
    const t = this._t.bind(this);
    const { aktiv, gross } = this._gruppenStand(gruppe);
    const zeit = this._ortszeit();
    const zusatz = gruppe.gruppe === "warmwasser" ? ` · ${teile.anlagenteil}` : "";
    const bloecke = aktiv ? this._bloecke(aktiv.programm.entity) || [] : [];
    const grenzen = skala(bloecke, aktiv && aktiv.programm.art);
    const zeigt = aktiv || gross;
    teile.programm.textContent = zeigt ? this._programmTitel(zeigt.programm) + zusatz : "";
    const heute = aktiv ? tagesabschnitte(bloecke, zeit.tag) : [];
    teile.spur.replaceChildren(spurKnoten(heute, grenzen, { t, jetzt: zeit.minute }));
    if (aktiv) {
      teile.text.textContent = heuteText(bloecke, zeit, grenzen, t);
      return;
    }
    const lage = t(gross ? "wirkt nicht" : "kein Programm");
    teile.text.textContent = [lage, this._wahlText(gruppe)].filter(Boolean).join(" · ");
  }

  /** Was sich an einer Gruppe ändern kann: Uhrzeit, Auswahl, Blöcke, geltendes Programm. */
  _gruppenKennung(gruppe) {
    const zeit = this._ortszeit();
    const programme = gruppe.eintraege.flatMap(({ programm, vorlauf }) => [programm, vorlauf].filter(Boolean));
    const teile = programme.map((programm) => {
      const zustand = this._zustand(programm.entity);
      const bloecke = zustand && zustand.attributes ? JSON.stringify(zustand.attributes.blocks) : "";
      return [programm.entity, bloecke, this._gilt(programm)].join("~");
    });
    return [zeit.tag, zeit.minute, this._wahlText(gruppe), ...teile].join("|");
  }

  // -------------------------------------------------------------------
  // Karte je Anlagenteil
  // -------------------------------------------------------------------
  /** Ohne Attribut blocks ist es kein Zeitprogramm; ein Anlagenteil ohne echtes Programm bekommt keine Karte. */
  _teilKarte(teil) {
    if (!teil.programme.some((programm) => this._bloecke(programm.entity) !== null)) return null;
    const hilfe = (teil.programme.find((programm) => programm.hilfe) || {}).hilfe;
    const karte = this._karte(teil.anlagenteil, hilfe);
    karte.classList.add("zp-karte");
    const ueberschrift = karte.querySelector("h2");
    if (ueberschrift) ueberschrift.dataset.roh = "";
    // Das Symbol des Anlagenteils; Warmwasser und Zirkulation tragen ihr eigenes.
    const leit = teil.programme.find((p) => !["warmwasser", "zirkulation"].includes(p.gruppe)) || teil.programme[0];
    const kopf = karte.querySelector(".kartenkopf");
    if (kopf && leit.symbol) kopf.insertBefore(this._symbolKnoten(leit.symbol, "zp-kartensymbol"), kopf.firstChild);
    teil.gruppen.forEach((gruppe) => karte.appendChild(this._gruppeKnoten(gruppe)));
    const fuss = this._kartenfuss(teil.gruppen);
    if (fuss) karte.appendChild(fuss);
    return karte;
  }

  _gruppeKnoten(gruppe) {
    const knoten = document.createElement("div");
    knoten.className = "zp-gruppe";
    knoten.dataset.gruppe = gruppe.gruppe || "";
    // Tasten und Rückmeldung überdauern das Neuzeichnen; sonst verlöre ein laufendes Umstellen seine Anzeige.
    const teile = new Map(gruppe.eintraege.map((eintrag) => [eintrag.programm.entity, this._programmTeile(eintrag)]));
    let stand = null;
    this._bindungen.push(() => {
      const kennung = this._gruppenKennung(gruppe);
      if (kennung !== stand) {
        stand = kennung;
        this._gruppeZeichnen(knoten, gruppe, teile);
      }
      this._tastenSetzen(gruppe, teile);
    });
    return knoten;
  }

  _programmTeile({ programm, vorlauf }) {
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    rueckmeldung.dataset.programm = programm.entity;
    // „Öffnen“, nicht „Bearbeiten“: Der Dialog zeigt zuerst die Zeiten als „von – bis“.
    const oeffnen = this._zpTaste("Öffnen", "zp-taste betont", () =>
      this._zeitprogrammBearbeiten(programm, rueckmeldung)
    );
    const vorlaufTaste = vorlauf
      ? this._zpTaste("Vorlauf", "zp-taste", () => this._zeitprogrammBearbeiten(vorlauf, rueckmeldung))
      : null;
    return { rueckmeldung, oeffnen, vorlaufTaste, aktivieren: this._aktivierenTaste(programm, rueckmeldung) };
  }

  _zpTaste(text, klasse, aktion) {
    const taste = document.createElement("button");
    taste.type = "button";
    taste.className = klasse;
    taste.textContent = this._t(text);
    taste.addEventListener("click", aktion);
    return taste;
  }

  _tastenSetzen(gruppe, teile) {
    gruppe.eintraege.forEach(({ programm }) => {
      const { aktivieren } = teile.get(programm.entity);
      if (!aktivieren) return;
      const { entity, ziel } = programm.wirkung;
      const laufend = this._wartend.some((vorgang) => vorgang.kennung === entity);
      const leer = istLeer(this._bloecke(programm.entity) || []);
      aktivieren.hidden = this._gilt(programm) || laufend || !this._bietet(entity, ziel) || leer;
    });
  }

  /** Groß das geltende Programm, darunter die übrigen als Minibalken; gilt keines, sagt eine Zeile warum. */
  _gruppeZeichnen(knoten, gruppe, teile) {
    const { sichtbar, gross } = this._gruppenStand(gruppe);
    const zeit = this._ortszeit();
    const inhalt = [];
    if (!gross && sichtbar.length) {
      const zustand = document.createElement("div");
      zustand.className = "zp-zustand";
      zustand.textContent = [this._t("kein Programm"), this._wahlText(gruppe)].filter(Boolean).join(" · ");
      inhalt.push(zustand);
    }
    if (gross) inhalt.push(this._programmGross(gross, teile.get(gross.programm.entity), zeit));
    sichtbar
      .filter((eintrag) => eintrag !== gross)
      .forEach((eintrag) => inhalt.push(this._programmMini(eintrag, teile.get(eintrag.programm.entity), zeit)));
    knoten.replaceChildren(...inhalt);
    knoten.hidden = !inhalt.length;
  }

  _programmName(programm, klasse) {
    const name = document.createElement("span");
    name.className = klasse;
    name.textContent = this._programmTitel(programm);
    name.dataset.roh = "";
    return name;
  }

  _leerZeile(programm) {
    const zeile = document.createElement("div");
    zeile.className = "zp-mini leer";
    const leer = document.createElement("span");
    leer.className = "zp-leer";
    leer.textContent = this._t("leer");
    zeile.append(this._programmName(programm, "zp-mininame"), leer);
    return zeile;
  }

  _programmGross({ programm, vorlauf }, teile, zeit) {
    const bloecke = this._bloecke(programm.entity) || [];
    if (istLeer(bloecke)) return this._leerZeile(programm);
    const knoten = document.createElement("div");
    knoten.className = "zp-programm";
    const kopf = document.createElement("div");
    kopf.className = "zp-programmkopf";
    kopf.appendChild(this._programmName(programm, "zp-programmname"));
    // Zum Rahmen eine Textmarke: Farbe allein trägt keine Aussage.
    if (programm.wirkung && this._gilt(programm)) {
      const marke = document.createElement("span");
      marke.className = "zp-aktiv";
      marke.textContent = `· ${this._t("aktiv")}`;
      kopf.appendChild(marke);
      knoten.classList.add("aktiv");
    }
    const raster = rasterKnoten(bloecke, {
      t: this._t.bind(this),
      art: programm.art,
      jetzt: zeit,
      vorlauf: vorlauf ? this._bloecke(vorlauf.entity) : null,
    });
    const leiste = document.createElement("div");
    leiste.className = "zp-karteleiste";
    leiste.append(...[teile.oeffnen, teile.vorlaufTaste, teile.aktivieren, teile.rueckmeldung].filter(Boolean));
    knoten.append(kopf, raster, leiste);
    return knoten;
  }

  /** Eine Zeile mit dem heutigen Tag des Programms, vergleichbar mit dem geltenden darüber. */
  _programmMini({ programm, vorlauf }, teile, zeit) {
    const bloecke = this._bloecke(programm.entity) || [];
    if (istLeer(bloecke)) return this._leerZeile(programm);
    const t = this._t.bind(this);
    const zeile = document.createElement("div");
    zeile.className = "zp-mini";
    const name = document.createElement("button");
    name.type = "button";
    name.className = "zp-mininame";
    name.textContent = this._programmTitel(programm);
    name.dataset.roh = "";
    name.title = t("Öffnen");
    name.addEventListener("click", () => this._zeitprogrammBearbeiten(programm, teile.rueckmeldung));
    const spuren = document.createElement("div");
    spuren.className = "zeitraster zp-minispuren";
    const heute = tagesabschnitte(bloecke, zeit.tag);
    spuren.appendChild(spurKnoten(heute, skala(bloecke, programm.art), { t, jetzt: zeit.minute }));
    const vorlaufBloecke = vorlauf ? this._bloecke(vorlauf.entity) : null;
    if (vorlaufBloecke) {
      const duenn = tagesabschnitte(vorlaufBloecke, zeit.tag);
      spuren.appendChild(spurKnoten(duenn, skala(vorlaufBloecke, "vorlauf"), { t, duenn: true }));
    }
    zeile.append(name, spuren, ...[teile.aktivieren, teile.rueckmeldung].filter(Boolean));
    return zeile;
  }

  /** Die Hinweise einmal je Karte, eine Zeile je Gruppe: Sie erklären die Regel, nicht den Zustand. */
  _kartenfuss(gruppen) {
    const texte = gruppen
      .map((gruppe) => {
        const mit = gruppe.eintraege.find(({ programm }) => programm.wirkung);
        return mit ? FUSS[gruppe.gruppe] || mit.programm.wirkung.hinweis : null;
      })
      .filter(Boolean);
    if (!texte.length) return null;
    const fuss = document.createElement("div");
    fuss.className = "zp-fuss";
    [...new Set(texte)].forEach((text) => {
      const zeile = document.createElement("div");
      zeile.textContent = this._t(text);
      fuss.appendChild(zeile);
    });
    return fuss;
  }

  _programmTitel(programm) {
    return mitBezeichnung(programm.titel, programm.bezeichnung);
  }

  /** Eine Option mit der Bezeichnung des Programms, auf das sie schaltet. */
  _optionBeschriftung(entity, option) {
    const programm = ((this._daten && this._daten.anlagen) || [])
      .flatMap((anlage) => anlage.zeitprogramme || [])
      .find((p) => p.wirkung && p.wirkung.entity === entity && p.wirkung.ziel === option);
    return mitBezeichnung(option, programm && programm.bezeichnung);
  }

  /** Ob die Auswahl diese Option gerade anbietet. */
  _bietet(entity, option) {
    const zustand = this._zustand(entity);
    // Eine nicht verfügbare Auswahl behält ihre Optionen, nimmt aber nichts an.
    if (!zustand || ["unavailable", "unknown"].includes(zustand.state)) return false;
    const optionen = (zustand && zustand.attributes && zustand.attributes.options) || [];
    return optionen.includes(option);
  }

  _aktivierenTaste(programm, rueckmeldung) {
    if (!programm.wirkung || !programm.wirkung.ziel) return null;
    const taste = document.createElement("button");
    taste.type = "button";
    taste.className = "zp-taste zp-aktivieren";
    taste.textContent = this._t("Aktivieren");
    taste.hidden = true;
    taste.addEventListener("click", () => this._zeitprogrammAktivieren(programm, rueckmeldung));
    return taste;
  }

  /** Rückfrage, dann die Auswahl auf dieses Programm stellen. */
  async _zeitprogrammAktivieren(programm, rueckmeldung) {
    const { entity, ziel, wahl_name: wahlName } = programm.wirkung;
    const zustand = this._zustand(entity);
    const frage = this._tMit("{wahl} von „{von}“ auf „{nach}“ umstellen?", {
      wahl: wahlName,
      von: zustand ? this._optionBeschriftung(entity, zustand.state) : "–",
      nach: this._optionBeschriftung(entity, ziel),
    });
    const ja = await this._bestaetigen(this._programmTitel(programm), frage, null, {
      ja: this._t("Aktivieren"),
      zurueck: this._t("Abbrechen"),
    });
    if (!ja) return;
    const angenommen = await this._uebertragen(
      rueckmeldung,
      () => this._hass.callService("select", "select_option", { entity_id: entity, option: ziel }),
      () => {
        const jetzt = this._zustand(entity);
        return !!jetzt && jetzt.state === ziel;
      },
      entity
    );
    // Endet, sobald die Auswahl den neuen Stand meldet.
    if (angenommen) this._nachfassen({ betriebswahl: entity });
  }

  /** Das Feld für die eigene Bezeichnung; der Name der Anlage bleibt davor stehen. */
  _bezeichnungFeld(programm) {
    const feld = document.createElement("input");
    feld.type = "text";
    feld.className = "zp-bezeichnung";
    feld.maxLength = BEZEICHNUNG_MAX;
    feld.placeholder = this._t("z. B. Übergangszeit");
    feld.value = programm.bezeichnung || "";
    const zeile = document.createElement("label");
    zeile.className = "zp-bezeichnung-zeile";
    zeile.append(this._t("Bezeichnung (optional)"), feld);
    return { zeile, feld };
  }

  /** Die aktuelle Zeit; eine eigene Methode, damit der Durchlauf sie festlegen kann. */
  _jetzt() {
    return new Date();
  }

  /**
   * Das Programm als Dialog – dieselbe Form wie Rückfrage und Erklärung.
   *
   * **Zwei Zustände.** Zuerst nur lesen: die Zeiten als „von – bis", so wie
   * das Bediengerät sie zeigt. Erst ein Druck auf *Bearbeiten* holt den
   * Editor, und der arbeitet mit Startpunkten – ein Punkt gilt, bis der
   * nächste kommt. Beides in einer Ansicht zu mischen war die Ursache dafür,
   * dass man beim Verstellen einer Zeit die falsche erwischte.
   *
   * Geschrieben wird erst beim Übernehmen, und dann das **ganze** Programm:
   * Die Anlage kennt keinen Weg, einen einzelnen Schaltpunkt zu ändern.
   * `heatnexus.set_time_program` liest das Objekt vorher und tauscht nur den
   * Wert aus, damit der Umschlag des Geräts erhalten bleibt.
   */
  _zeitprogrammBearbeiten(programm, rueckmeldung) {
    const zustand = this._zustand(programm.entity);
    const bloecke = bloeckeLesen(zustand && zustand.attributes && zustand.attributes.blocks);
    if (!bloecke.length) return;
    const grenzen = skala(bloecke, programm.art);

    const schleier = document.createElement("div");
    schleier.className = "schleier";
    const dialog = document.createElement("div");
    dialog.className = "dialog zp-dialog";

    const ueberschrift = document.createElement("h3");
    ueberschrift.className = "dialog-titel";
    ueberschrift.textContent = this._programmTitel(programm);

    const platz = document.createElement("div");
    const zone = this._hass && this._hass.config && this._hass.config.time_zone;
    const jetzt = ortszeit(this._jetzt(), zone);
    platz.appendChild(uebersichtKnoten(bloecke, { grenzen, jetzt, t: this._t.bind(this) }));

    const meldung = document.createElement("div");
    meldung.className = "zp-meldung";

    const leiste = document.createElement("div");
    leiste.className = "dialog-leiste";
    const abbrechen = document.createElement("button");
    abbrechen.type = "button";
    abbrechen.className = "dialog-taste";
    abbrechen.textContent = this._t("Schließen");
    const speichern = document.createElement("button");
    speichern.type = "button";
    speichern.className = "dialog-taste betont";
    speichern.textContent = this._t("Bearbeiten");
    leiste.append(abbrechen, speichern);

    dialog.append(ueberschrift, platz, meldung, leiste);
    schleier.appendChild(dialog);

    const weg = this._dialogOeffnen(schleier, { fokus: speichern });
    abbrechen.addEventListener("click", weg);

    // Im Lesezustand liegt hier nichts; erst *Bearbeiten* legt den Editor an.
    let editor = null;
    let bezeichnungFeld = null;
    dialog._bearbeiten = () => {
      editor = editorKnoten(bloecke, { grenzen, t: this._t.bind(this) });
      bezeichnungFeld = this._bezeichnungFeld(programm);
      platz.replaceChildren(bezeichnungFeld.zeile, editor.knoten);
      meldung.textContent = "";
      abbrechen.textContent = this._t("Verwerfen");
      speichern.textContent = this._t("Übernehmen");
      speichern.focus();
    };

    speichern.addEventListener("click", async () => {
      if (!editor) {
        dialog._bearbeiten();
        return;
      }
      const neu = editor.lesen();
      const fehler = pruefen(neu, this._t.bind(this));
      if (fehler.length) {
        meldung.className = "zp-meldung fehler";
        meldung.textContent = fehler.join(" ");
        return;
      }
      const bezeichnung = bezeichnungFeld.feld.value.trim();
      const neueBezeichnung = bezeichnung !== (programm.bezeichnung || "");
      // Ein zweiter Druck während des Speicherns schriebe alles doppelt.
      speichern.disabled = true;
      if (neueBezeichnung) {
        try {
          await this._hass.callWS({
            type: "heatnexus/bezeichnung",
            entity_id: programm.entity,
            bezeichnung,
          });
        } catch (err) {
          console.warn("HeatNexus: Bezeichnung nicht gespeichert", err);
          meldung.className = "zp-meldung fehler";
          meldung.textContent = this._t("Die Bezeichnung konnte nicht gespeichert werden.");
          speichern.disabled = false;
          return;
        }
      }
      meldung.textContent = "";
      weg();
      // Titel, Rückfrage und Betriebswahl lesen die Bezeichnung aus den Paneldaten.
      // Der Neuaufbau ersetzt die Karte; die Rückmeldung gehört an die neue.
      if (neueBezeichnung) await this._datenHolen();
      if (gleich(neu, bloecke)) return;
      const anzeige =
        [...this.shadowRoot.querySelectorAll(".rueckmeldung")].find(
          (knoten) => knoten.dataset.programm === programm.entity
        ) || rueckmeldung;
      await this._uebertragen(
        anzeige,
        () =>
          this._hass.callService("heatnexus", "set_time_program", {
            entity_id: programm.entity,
            blocks: nachDienst(neu),
          }),
        // Übernommen ist es erst, wenn die Anlage dasselbe zurückmeldet.
        () => {
          const jetzt = this._zustand(programm.entity);
          const gemeldet = bloeckeLesen(jetzt && jetzt.attributes && jetzt.attributes.blocks);
          return gleich(gemeldet, neu);
        },
        programm.entity
      );
      this._nachfassen({ entity: programm.entity });
    });

  }
  };
