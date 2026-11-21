/**
 * Reiter „Zeitprogramme“: oben der Heute-Streifen, darunter eine Karte je Anlagenteil.
 *
 * Gerechnet wird in ../zeitprogramm.js und ../zeitprogrammseite.js; eingebunden als Mixin in heatnexus-panel.js.
 */

import {
  BEZEICHNUNG_MAX,
  blockraster,
  bloeckeLesen,
  editorKnoten,
  gleich,
  mitBezeichnung,
  nachDienst,
  ortszeit,
  pruefen,
  TAG_MINUTEN,
  schaltetNie,
  skala,
  uebersichtKnoten,
} from "../zeitprogramm.js";
import { zeileneditorKnoten } from "../zeileneditor.js";
import {
  achseKnoten,
  blockEinsetzen,
  ohneFenster,
  tabelle,
  nachTeilen,
  tagesspur,
} from "../zeitprogrammseite.js";

// Zeit- und Impulssteuerung folgen den Schaltzeiten; ohne ein Ein steht die Pumpe.
const OHNE_EIN = "Alle Schaltzeiten der Zeitsteuerung stehen auf Aus. Die Zirkulationspumpe läuft damit nicht.";

/** Ein Programm ohne Schaltzeit braucht nur eine Zeile. */
const istLeer = (bloecke) => bloecke.every((block) => !block.punkte.length);

// Jetzt-Linie und „ab HH:MM“ rücken auch dann vor, wenn sich an der Anlage nichts ändert.
const UHR_TAKT_MS = 60 * 1000;

// Gelesene Blöcke je Attribut: Home Assistant ersetzt das Attribut bei jeder Änderung;
// solange es dasselbe ist, gilt auch das Gelesene. Die Nummer kennzeichnet den Stand.
const GELESEN = new WeakMap();
let lesestand = 0;

export const ZeitprogrammeMixin = (Basis) =>
  class extends Basis {
  /**
   * Eine Karte je Anlagenteil, in der Einzelansicht mit dem Heute-Streifen davor.
   *
   * Unter „Alle“ setzt das Panel einen gemeinsamen Streifen über alle Anlagen.
   */
  _zeitprogrammeReiter(anlage) {
    this._zeitprogrammUhrStellen();
    const karten = nachTeilen(anlage.zeitprogramme).map((teil) => ({
      id: `zeitprogramme:${teil.teil}`,
      titel: teil.anlagenteil,
      knoten: this._teilKarte({ ...teil, sprache: anlage.sprache }),
      breite: 2,
    }));
    return karten;
  }

  /** Solange der Reiter offen ist, einmal je Minute die Bindungen laufen lassen. */
  _zeitprogrammUhrStellen() {
    if (this._zeitprogrammUhr && this._zeitgeberListe.has(this._zeitprogrammUhr)) return;
    this._zeitprogrammUhr = this._takt(() => {
      if (!this.isConnected || this._reiter !== "zeitprogramme") {
        this._zeitgeberLoesen(this._zeitprogrammUhr);
        this._zeitprogrammUhr = null;
        return;
      }
      this._aktualisieren();
    }, UHR_TAKT_MS);
  }

  /** Die Blöcke eines Programms mit einer Nummer für ihren Stand; 'null', wenn die Entität keine führt. */
  _blockstand(entity) {
    const zustand = this._zustand(entity);
    const roh = zustand && zustand.attributes && zustand.attributes.blocks;
    if (!Array.isArray(roh)) return null;
    if (!GELESEN.has(roh)) GELESEN.set(roh, { bloecke: bloeckeLesen(roh), nummer: (lesestand += 1) });
    return GELESEN.get(roh);
  }

  _bloecke(entity) {
    const stand = this._blockstand(entity);
    return stand ? stand.bloecke : null;
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
    if (wirkung.muster_nicht) return !text.includes(wirkung.muster_nicht);
    return text.includes(wirkung.muster) || (!!wirkung.muster_auch && text.includes(wirkung.muster_auch));
  }

  /** Das Zirkulationsprogramm, nach dem die Pumpe nie läuft. Das Temperaturprogramm schaltet nicht. */
  _laeuftNie(programm) {
    return (
      programm.gruppe === "zirkulation" &&
      programm.art !== "wasser" &&
      schaltetNie(this._bloecke(programm.entity))
    );
  }

  /**
   * Ob ein Programm in seiner Gruppe gilt. Ohne bekannte Auswahl gilt ein einzelnes Programm immer;
   * von mehreren lässt sich dann keines als geltend zeigen.
   */
  _giltInGruppe(gruppe, programm) {
    return programm.wirkung ? this._gilt(programm) : gruppe.eintraege.length === 1;
  }

  /** Sichtbare Programme der Gruppe, das geltende und das, das groß steht. */
  _gruppenStand(gruppe) {
    // Auch das Programm, das gerade nicht gilt, bleibt sichtbar: klein, mit „Aktivieren“.
    const sichtbar = gruppe.eintraege.filter(({ programm }) => this._bloecke(programm.entity) !== null);
    const aktiv = sichtbar.find(({ programm }) => this._giltInGruppe(gruppe, programm)) || null;
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

  /** Was eine Gruppe neu aufbaut: Wochentag, Auswahl, Blöcke, geltendes Programm. Die Minute nicht. */
  _gruppenKennung(gruppe) {
    const programme = gruppe.eintraege.flatMap(({ programm, vorlauf }) => [programm, vorlauf].filter(Boolean));
    const teile = programme.map((programm) => {
      const stand = this._blockstand(programm.entity);
      return [programm.entity, stand ? stand.nummer : "-", this._giltInGruppe(gruppe, programm)].join("~");
    });
    const wahl = this._zpWahl ? this._zpWahl.get(this._gruppenSchluessel(gruppe)) : "";
    const offen = this._zpOffen && programme.some((p) => p.entity === this._zpOffen.entity);
    const editor = offen ? `${this._zpOffen.entity}#${this._zpOffen.stelle}` : "";
    const benennen = programme.some((p) => p.entity === this._zpBenennen) ? this._zpBenennen : "";
    const form = this._stilwahl("zeitprogramme");
    return [this._ortszeit().tag, this._wahlText(gruppe), wahl, editor, benennen, form, ...teile].join("|");
  }

  /** Die Jetzt-Linien eines Knotens auf die aktuelle Minute setzen, ohne ihn neu zu bauen. */
  _jetztLinienSetzen(knoten) {
    const links = `${(this._ortszeit().minute / TAG_MINUTEN) * 100}%`;
    knoten.querySelectorAll(".jetzt-linie").forEach((linie) => {
      linie.style.left = links;
    });
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
    teil.gruppen.forEach((gruppe) => karte.appendChild(this._gruppeKnoten({ ...gruppe, sprache: teil.sprache })));
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
      this._jetztLinienSetzen(knoten);
      this._tastenSetzen(gruppe, teile);
    });
    return knoten;
  }

  _rueckmeldung(programm) {
    const rueckmeldung = document.createElement("div");
    rueckmeldung.className = "rueckmeldung";
    rueckmeldung.dataset.programm = programm.entity;
    return rueckmeldung;
  }

  /** Bedienelemente eines Programms; sie überdauern das Neuzeichnen der Gruppe samt Fokus. */
  _programmTeile({ programm, vorlauf }) {
    const rueckmeldung = this._rueckmeldung(programm);
    const vorlaufRueckmeldung = vorlauf ? this._rueckmeldung(vorlauf) : null;
    const stift = this._zpTaste("", "zp-stift", () => {
      this._zpBenennen = this._zpBenennen === programm.entity ? null : programm.entity;
      this._aktualisieren();
    });
    stift.appendChild(this._symbolKnoten("mdi:pencil-outline"));
    stift.title = this._t("Bezeichnung ändern");
    stift.setAttribute("aria-label", this._t("Bezeichnung ändern"));
    return {
      rueckmeldung,
      vorlaufRueckmeldung,
      stift,
      aktivieren: this._aktivierenTaste(programm, rueckmeldung),
    };
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

  /** Das gewählte Programm der Gruppe, sonst das geltende, sonst das erste. */
  _gezeigt(gruppe, sichtbar, aktiv) {
    const wahl = this._zpWahl && this._zpWahl.get(this._gruppenSchluessel(gruppe));
    return sichtbar.find(({ programm }) => programm.entity === wahl) || aktiv || sichtbar[0] || null;
  }

  /** Gruppen gleichen Namens gibt es in jedem Anlagenteil; das erste Programm macht sie eindeutig. */
  _gruppenSchluessel(gruppe) {
    return gruppe.eintraege.length ? gruppe.eintraege[0].programm.entity : gruppe.schluessel;
  }

  /** Lagezeile, Programmwahl und Tageszeilen des gezeigten Programms; die Warnung davor. */
  _gruppeZeichnen(knoten, gruppe, teile) {
    // Umgehängte Knöpfe verlieren den Fokus; wer per Tastatur dort stand, bleibt dort.
    const fokus = this.shadowRoot.activeElement;
    const { sichtbar, aktiv } = this._gruppenStand(gruppe);
    const gezeigt = this._gezeigt(gruppe, sichtbar, aktiv);
    const inhalt = [];
    if (sichtbar.some(({ programm }) => this._laeuftNie(programm))) {
      const warnung = document.createElement("div");
      warnung.className = "zp-warnung";
      warnung.textContent = this._t(OHNE_EIN);
      inhalt.push(warnung);
    }
    if (gezeigt) inhalt.push(this._programmAnsicht(gruppe, { sichtbar, aktiv, gezeigt }, teile));
    knoten.replaceChildren(...inhalt);
    knoten.hidden = !inhalt.length;
    if (fokus && fokus !== this.shadowRoot.activeElement && knoten.contains(fokus)) {
      fokus.focus({ preventScroll: true });
    }
  }

  _programmAnsicht(gruppe, stand, teile) {
    const { programm, vorlauf } = stand.gezeigt;
    const eigene = teile.get(programm.entity);
    const knoten = document.createElement("div");
    knoten.className = "zp-programm";
    if (programm.wirkung && this._gilt(programm)) knoten.classList.add("aktiv");
    // Mit Reitern nennt die Leiste das Programm; allein steht sein Name. Daneben nur der Stift.
    const kopf = document.createElement("div");
    kopf.className = "zp-kopfzeile";
    if (stand.sichtbar.length > 1) {
      kopf.appendChild(this._programmReiter(gruppe, stand));
    } else {
      const titel = document.createElement("div");
      titel.className = "zp-titel";
      titel.appendChild(this._programmName(programm, "zp-programmname"));
      kopf.appendChild(titel);
    }
    kopf.appendChild(eigene.stift);
    knoten.appendChild(kopf);
    const hinweis = this._lageZeile(gruppe, stand);
    if (hinweis) knoten.appendChild(hinweis);
    if (this._zpBenennen === programm.entity) knoten.appendChild(this._benennenKnoten(programm));
    const zeit = this._ortszeit();
    knoten.appendChild(this._tageszeilen(programm, zeit, eigene.rueckmeldung, gruppe.sprache));
    const vorlaufBloecke = vorlauf ? this._bloecke(vorlauf.entity) : null;
    if (vorlaufBloecke && !istLeer(vorlaufBloecke)) {
      const titel = document.createElement("div");
      titel.className = "zp-abschnitt";
      titel.textContent = this._t("Vorlaufwerte");
      knoten.append(titel, this._tageszeilen(vorlauf, zeit, eigene.vorlaufRueckmeldung, gruppe.sprache));
    }
    const leiste = document.createElement("div");
    leiste.className = "zp-karteleiste";
    const knoepfe = [eigene.aktivieren, eigene.rueckmeldung, eigene.vorlaufRueckmeldung];
    leiste.append(...knoepfe.filter(Boolean));
    knoten.appendChild(leiste);
    return knoten;
  }

  /** Nur wenn kein Programm wirkt, ein Satz dazu: „kein Programm · Betriebswahl: Standby“. Sonst nichts. */
  _lageZeile(gruppe, { sichtbar, aktiv, gezeigt }) {
    if (aktiv) return null;
    const allein = sichtbar.length === 1;
    const stuecke = [this._t(allein && gezeigt.programm.wirkung ? "wirkt nicht" : "kein Programm")];
    const wahl = this._wahlText(gruppe);
    if (wahl) stuecke.push(wahl);
    const zeile = document.createElement("div");
    zeile.className = "zp-lage";
    zeile.textContent = stuecke.join(" · ");
    return zeile;
  }

  /** Eine Reiterleiste statt Minibalken; der Reiter des geltenden Programms ist eingefärbt. */
  _programmReiter(gruppe, { sichtbar, aktiv, gezeigt }) {
    const leiste = document.createElement("div");
    leiste.className = "zp-reiter";
    leiste.setAttribute("role", "tablist");
    sichtbar.forEach((eintrag) => leiste.appendChild(this._programmTab(gruppe, eintrag, { aktiv, gezeigt })));
    return leiste;
  }

  _programmTab(gruppe, eintrag, { aktiv, gezeigt }) {
    const { programm } = eintrag;
    const taste = document.createElement("button");
    taste.type = "button";
    taste.setAttribute("role", "tab");
    taste.setAttribute("aria-selected", String(eintrag === gezeigt));
    if (eintrag === aktiv) {
      taste.classList.add("gilt");
      taste.title = this._t("gilt");
      const punkt = document.createElement("i");
      punkt.className = "zp-punkt-gilt";
      taste.appendChild(punkt);
    }
    const name = this._programmName(programm, eintrag === gezeigt ? "zp-programmname" : "zp-mininame");
    if (istLeer(this._bloecke(programm.entity) || [])) {
      taste.classList.add("leer");
      taste.title = this._t("leer");
    }
    taste.appendChild(name);
    if (eintrag === aktiv) taste.appendChild(this._giltMarke());
    taste.addEventListener("click", () => {
      if (!this._zpWahl) this._zpWahl = new Map();
      this._zpWahl.set(this._gruppenSchluessel(gruppe), programm.entity);
      this._aktualisieren();
    });
    return taste;
  }

  /** Zahlen im Klartext folgen der Sprache der Anlage; fehlt sie, der von Home Assistant. */
  _sprachcode(sprache) {
    const hass = this._hass || {};
    return sprache || (hass.locale && hass.locale.language) || hass.language || "de";
  }

  /** Je Block eine Zeile: Tage, eine Spur in einer Farbe, darunter der Klartext; antippen öffnet das Programm. */
  _tageszeilen(programm, zeit, rueckmeldung, sprache) {
    const t = this._t.bind(this);
    const bloecke = this._bloecke(programm.entity) || [];
    const liste = document.createElement("div");
    liste.className = "zp-zeilen";
    if (istLeer(bloecke)) {
      const leer = document.createElement("div");
      leer.className = "zp-leer";
      leer.textContent = t("Dieses Programm hat keine Schaltzeiten.");
      liste.appendChild(leer);
      return liste;
    }
    const grenzen = skala(bloecke, programm.art);
    blockraster(bloecke, t).forEach((reihe) => {
      const heute = reihe.tage.includes(zeit.tag) ? zeit.minute : null;
      const offen = this._zeileOffen(programm, reihe);
      const zeile = this._tageszeile(reihe, grenzen, { jetzt: heute, sprache }, () => this._zeileUmschalten(programm, reihe));
      zeile.setAttribute("aria-expanded", String(offen));
      if (offen) zeile.classList.add("offen");
      liste.appendChild(zeile);
      if (offen) liste.appendChild(this._zeileneditor(programm, bloecke, grenzen, rueckmeldung));
    });
    return liste;
  }

  _tageszeile(reihe, grenzen, { jetzt, sprache }, oeffnen) {
    const t = this._t.bind(this);
    const zeile = document.createElement("div");
    zeile.className = "zp-zeile";
    zeile.setAttribute("role", "button");
    zeile.tabIndex = 0;
    zeile.title = t("Öffnen");
    const tag = document.createElement("span");
    tag.className = "zp-tagname";
    tag.textContent = reihe.text;
    zeile.appendChild(tag);
    const code = this._sprachcode(sprache);
    const zeilen = tabelle(reihe.abschnitte, grenzen, { t, sprache: code });
    if (ohneFenster(zeilen)) {
      const [{ zeit: ohneText, wert }] = zeilen;
      zeile.appendChild(this._ohneFensterZeile(wert ? t("Kein Zeitfenster") : ohneText, wert));
    } else {
      // Unter „Darstellung“ wählbar: Werte in der Spur oder als Tabelle darunter.
      const inSpur = this._stilwahl("zeitprogramme") === "spur";
      zeile.append(
        tagesspur(reihe.abschnitte, grenzen, { t, jetzt, beschriften: inSpur, tippen: inSpur, sprache: code }),
        achseKnoten()
      );
      if (!inSpur) zeile.appendChild(this._schaltzeitenTabelle(zeilen));
    }
    zeile.addEventListener("click", oeffnen);
    zeile.addEventListener("keydown", (ereignis) => {
      if (ereignis.key !== "Enter" && ereignis.key !== " ") return;
      ereignis.preventDefault();
      oeffnen();
    });
    return zeile;
  }

  /** „Kein Zeitfenster“ mit dem Wert des ganzen Tags, oder „kein Zeitplan“; statt einer Spur in einer Farbe. */
  _ohneFensterZeile(beschriftung, wert) {
    const zeile = document.createElement("div");
    zeile.className = "zp-ohne-fenster";
    const text = document.createElement("span");
    text.textContent = beschriftung;
    const was = document.createElement("b");
    was.textContent = wert;
    zeile.append(text, was);
    return zeile;
  }

  /** Je Fenster Farbfeld, Zeit und Wert; zuletzt „sonst“ gedämpft. */
  _schaltzeitenTabelle(zeilen) {
    const liste = document.createElement("div");
    liste.className = "zp-tabelle";
    zeilen.forEach(({ stufe, farbe, zeit, wert }) => {
      const feld = document.createElement("i");
      feld.className = stufe && farbe ? "zp-feld" : "zp-feld leer";
      if (stufe && farbe) feld.style.background = farbe;
      const wann = document.createElement("span");
      wann.className = stufe ? "zp-tzeit" : "zp-tzeit rest";
      wann.textContent = zeit;
      const was = document.createElement("span");
      was.className = stufe ? "zp-twert" : "zp-twert rest";
      was.textContent = wert;
      liste.append(feld, wann, was);
    });
    return liste;
  }

  /** Für Vorleser; sichtbar sagt es der Punkt. Steht hinter dem Namen, damit dieser vorn bleibt. */
  _giltMarke() {
    const marke = document.createElement("span");
    marke.className = "zp-aktiv";
    marke.textContent = this._t("gilt");
    return marke;
  }

  _programmName(programm, klasse) {
    const name = document.createElement("span");
    name.className = klasse;
    name.textContent = this._programmTitel(programm);
    name.dataset.roh = "";
    return name;
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
    const warnung = this._laeuftNie(programm) ? ` ${this._t(OHNE_EIN)}` : "";
    const ja = await this._bestaetigen(this._programmTitel(programm), frage + warnung, null, {
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
      await this._programmSchreiben(programm, neu, rueckmeldung);
    });
  }

  /** Das ganze Programm schreiben; übernommen ist es erst, wenn die Anlage dasselbe zurückmeldet. */
  async _programmSchreiben(programm, neu, rueckmeldung) {
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
      () => {
        const jetzt = this._zustand(programm.entity);
        const gemeldet = bloeckeLesen(jetzt && jetzt.attributes && jetzt.attributes.blocks);
        return gleich(gemeldet, neu);
      },
      programm.entity
    );
    this._nachfassen({ entity: programm.entity });
  }

  /** Die eigene Bezeichnung unter der Reiterleiste ändern; Titel und Betriebswahl lesen sie aus den Paneldaten. */
  _benennenKnoten(programm) {
    const { zeile, feld } = this._bezeichnungFeld(programm);
    const meldung = document.createElement("div");
    meldung.className = "zp-meldung";
    const schliessen = () => {
      this._zpBenennen = null;
      this._aktualisieren();
    };
    const speichern = this._zpTaste("Speichern", "zp-taste betont zp-speichern", async () => {
      const bezeichnung = feld.value.trim();
      if (bezeichnung === (programm.bezeichnung || "")) {
        schliessen();
        return;
      }
      speichern.disabled = true;
      try {
        await this._hass.callWS({ type: "heatnexus/bezeichnung", entity_id: programm.entity, bezeichnung });
      } catch (err) {
        console.warn("HeatNexus: Bezeichnung nicht gespeichert", err);
        meldung.className = "zp-meldung fehler";
        meldung.textContent = this._t("Die Bezeichnung konnte nicht gespeichert werden.");
        speichern.disabled = false;
        return;
      }
      schliessen();
      await this._datenHolen();
    });
    const aktionen = document.createElement("div");
    aktionen.className = "zp-ze-aktionen";
    aktionen.append(this._zpTaste("Abbrechen", "zp-taste zp-abbrechen", schliessen), speichern);
    const knoten = document.createElement("div");
    knoten.className = "zp-benennen";
    knoten.append(zeile, meldung, aktionen);
    return knoten;
  }

  // -------------------------------------------------------------------
  // Editor unter der Zeile
  // -------------------------------------------------------------------
  _zeileOffen(programm, reihe) {
    const offen = this._zpOffen;
    return !!offen && offen.entity === programm.entity && offen.stelle === reihe.stelle;
  }

  /** Eine Zeile öffnet ihren Editor; dieselbe Zeile schließt ihn, eine andere übernimmt. */
  _zeileUmschalten(programm, reihe) {
    this._zpOffen = this._zeileOffen(programm, reihe)
      ? null
      : {
          entity: programm.entity,
          stelle: reihe.stelle,
          modell: { tage: [...reihe.tage], punkte: reihe.punkte.map((punkt) => ({ ...punkt })) },
        };
    this._aktualisieren();
  }

  _zeileneditor(programm, bloecke, grenzen, rueckmeldung) {
    const t = this._t.bind(this);
    const { stelle, modell } = this._zpOffen;
    const schliessen = () => {
      this._zpOffen = null;
      this._aktualisieren();
    };
    return zeileneditorKnoten(modell, {
      grenzen,
      t,
      abbrechen: schliessen,
      speichern: (block) => {
        const neu = blockEinsetzen(bloecke, stelle, block);
        const fehler = pruefen(neu, t);
        if (fehler.length) return fehler;
        schliessen();
        if (!gleich(neu, bloecke)) this._programmSchreiben(programm, neu, rueckmeldung);
        return [];
      },
    });
  }
  };
