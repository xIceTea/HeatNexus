"""Zeitprogramme im Reiter: Fensterprogramme, Kartentitel, Vorschau und der Zeileneditor bei neuem Stand.

Gefahren in Node gegen die DOM-Attrappe (`js/dom-attrappe.mjs`) mit den echten Modulen.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

TESTS = Path(__file__).resolve().parent
KOMPONENTE = TESTS.parent / "custom_components" / "heatnexus"
FRONTEND = KOMPONENTE / "frontend"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

SKRIPT = r"""
import { readFileSync } from "node:fs";
import { browserAttrappe } from "__ATTRAPPE__";
browserAttrappe();
console.warn = () => {};

await import("__FRONTEND__/heatnexus-panel.js");
const zp = await import("__FRONTEND__/zeitprogramm.js");
const { zeileneditorKnoten } = await import("__FRONTEND__/zeileneditor.js");
const [klasse] = [...globalThis.customElements._klassen.values()];
const woerterbuch = (sprache) => JSON.parse(readFileSync(`__SPRACHEN__/${sprache}.json`, "utf-8"));

const text = (knoten) => String((knoten && knoten.textContent) || "").trim();
const WERKTAGE = ["Mo", "Tu", "We", "Th", "Fr"];
const LEER = { start: "00:00", stop: "00:00" };
const FENSTER = [
  { weekdays: WERKTAGE, values: [{ start: "05:00", stop: "08:00" }, { start: "15:00", stop: "22:00" }, LEER] },
  { weekdays: ["Sa", "Su"], values: [{ start: "06:00", stop: "23:00" }, LEER, LEER] },
];
const punkte = (...paare) => paare.map(([time, value]) => ({ time, value }));
const abwarten = async () => {
  for (let runde = 0; runde < 10; runde++) await Promise.resolve();
};

function bauen(programme, zustaende, texte = {}) {
  const flaeche = new klasse();
  const aufrufe = [];
  flaeche._texte = texte;
  flaeche._reiter = "zeitprogramme";
  flaeche._jetzt = () => new Date("2026-11-18T10:00:00Z");
  flaeche.hass = {
    states: zustaende,
    user: { is_admin: true },
    language: "de",
    locale: { language: "de" },
    config: { time_zone: "UTC" },
    callWS: async () => ({}),
    callService: async (bereich, dienst, angaben) => {
      aufrufe.push({ dienst: `${bereich}.${dienst}`, angaben });
      return true;
    },
  };
  flaeche.panel = { config: { daten: { anlagen: [{ id: "a", name: "Versuchsraum", zeitprogramme: programme }] } } };
  flaeche._gebaut = false;
  flaeche._zeichnen();
  flaeche._aktualisieren();
  return { flaeche, aufrufe, wurzel: flaeche.shadowRoot };
}
const zustand = (entity, blocks) => ({ entity_id: entity, state: "", attributes: { blocks } });

const befund = {};
async function abschnitt(name, pruefung) {
  try {
    befund[name] = await pruefung();
  } catch (err) {
    befund[name] = { fehler: String((err && err.stack) || err) };
  }
}

await abschnitt("lesen", () => {
  const bloecke = zp.bloeckeLesen(FENSTER);
  const ende = zp.bloeckeLesen([{ weekdays: ["Mo"], values: [{ start: "22:00", stop: "00:00" }, LEER, LEER] }]);
  const frueh = zp.bloeckeLesen([{ weekdays: ["Mo"], values: [{ start: "00:00", stop: "06:00" }, LEER, LEER] }]);
  const rohe = (b) => b.map((block) => ({ tage: block.tage, punkte: block.punkte }));
  return {
    bloecke: rohe(bloecke),
    abschnitte: zp.abschnitte(bloecke[0].punkte),
    ende: zp.abschnitte(ende[0].punkte),
    frueh: zp.abschnitte(frueh[0].punkte),
    fenster: [zp.istFensterprogramm(bloecke), zp.istFensterprogramm(zp.bloeckeLesen([{ weekdays: ["Mo"], switchPoints: [] }]))],
    skala: zp.skala(bloecke, "wasser").schalt,
  };
});

await abschnitt("reiter", () => {
  const programm = { entity: "sensor.evo_heizen", titel: "Zeitprogramm Heizen", anlagenteil: "HK", teil: "hk", art: "wasser" };
  const { flaeche, wurzel } = bauen([programm], { "sensor.evo_heizen": zustand("sensor.evo_heizen", FENSTER) });
  const karte = wurzel.querySelector(".zp-karte");
  const zeilen = karte.querySelectorAll(".zp-zeile");
  zeilen[0].ausloesen("click");
  const offen = !!karte.querySelector(".zp-zeileneditor");
  const rueckmeldung = document.createElement("div");
  flaeche._zeitprogrammBearbeiten(programm, rueckmeldung);
  const dialog = wurzel.querySelector(".zp-dialog");
  const bearbeiten = dialog && dialog.querySelectorAll(".dialog-taste").find((t) => t.classList.contains("betont"));
  return {
    leer: !!karte.querySelector(".zp-leer"),
    tage: karte.querySelectorAll(".zp-tagname").map(text),
    zeiten: karte.querySelectorAll(".zp-tzeit").map(text),
    werte: karte.querySelectorAll(".zp-twert").map(text),
    knopf: zeilen.map((zeile) => zeile.getAttribute("role")),
    offen,
    bearbeiten: bearbeiten ? !!bearbeiten.hidden : null,
  };
});

await abschnitt("titel", () => {
  const programm = (entity, teil, geraet) => ({
    entity, titel: "Zeitprogramm Silentmode", anlagenteil: "AeroWIN", teil, art: "schalt", ...(geraet ? { geraet } : {}),
  });
  const plan = [{ weekdays: [...WERKTAGE, "Sa", "Su"], switchPoints: punkte(["00:00", 0]) }];
  const programme = [
    programm("sensor.a", "g1", "AeroWIN EVO Wärmepumpe"),
    programm("sensor.b", "g2", "AeroWIN Wärmepumpe"),
    programm("sensor.c", "g3"),
  ];
  const zustaende = Object.fromEntries(programme.map((p) => [p.entity, zustand(p.entity, plan)]));
  const titel = (texte) =>
    bauen(programme, zustaende, texte).wurzel.querySelectorAll(".zp-karte").map((karte) => text(karte.querySelector("h2")));
  const { flaeche } = bauen(programme, zustaende);
  const pumpe = (id) => text(flaeche._karte(flaeche._waermepumpeTitel({ id, titel: "AeroWIN" })).querySelector("h2"));
  return { de: titel({}), en: titel(woerterbuch("en")), pumpen: ["g1", "g3"].map(pumpe) };
});

await abschnitt("vorschau", () => {
  const grenzen = zp.skala([], "schalt");
  const modell = { tage: ["Mo"], punkte: [{ zeit: 360, wert: 0 }, { zeit: 1080, wert: 0 }] };
  const editor = zeileneditorKnoten(modell, { grenzen, t: (s) => s, speichern: () => [], abbrechen: () => {} });
  return editor.querySelector(".zp-ze-vorschau").querySelectorAll(".zp-stueck").map(text);
});

await abschnitt("mehr", () => {
  const grenzen = zp.skala([], "raum");
  const modell = { tage: ["Mo"], punkte: [{ zeit: 1380, wert: 18 }, { zeit: 360, wert: 21 }] };
  const editor = zeileneditorKnoten(modell, { grenzen, speichern: () => [], abbrechen: () => {} });
  editor.querySelector(".zp-ze-mehr").ausloesen("click");
  editor.querySelector(".zp-ze-mehr").ausloesen("click");
  const dialog = zp.editorKnoten([{ tage: ["Mo"], punkte: [{ zeit: 1380, wert: 18 }, { zeit: 360, wert: 21 }] }], { grenzen });
  const mehr = dialog.knoten.querySelectorAll("button").find((t) => text(t) === "+ Schaltzeit");
  mehr.ausloesen("click");
  return { zeile: modell.punkte.slice(2), dialog: dialog.lesen()[0].punkte };
});

// Der Zeileneditor einer Zeile bleibt offen, während sich das Programm der Anlage ändert.
const HEIZEN = { entity: "sensor.heizen", titel: "Heizprogramm 1", anlagenteil: "HK", teil: "hk", art: "raum" };
const ARBEIT = punkte(["06:00", 21], ["22:00", 16]);
const SAMSTAG = punkte(["07:30", 21], ["23:00", 16]);
const SONNTAG = punkte(["08:00", 20], ["22:00", 16]);
async function zeileAendern(vorher, nachher, tagname, neuZeichnen = true) {
  const { flaeche, aufrufe, wurzel } = bauen([HEIZEN], { "sensor.heizen": zustand("sensor.heizen", vorher) });
  wurzel.querySelectorAll(".zp-zeile").find((zeile) => text(zeile.querySelector(".zp-tagname")) === tagname).ausloesen("click");
  const feld = wurzel.querySelector(".zp-zeileneditor").querySelector(".zp-wert");
  feld.value = "19";
  feld.ausloesen("change");
  flaeche.hass = { ...flaeche._hass, states: { "sensor.heizen": zustand("sensor.heizen", nachher) } };
  if (neuZeichnen) flaeche._aktualisieren();
  await abwarten();
  const meldung = () => {
    const editor = wurzel.querySelector(".zp-zeileneditor");
    return editor ? text(editor.querySelector(".zp-meldung")) : "";
  };
  const zuerst = meldung();
  wurzel.querySelector(".zp-zeileneditor").querySelector(".zp-speichern").ausloesen("click");
  await abwarten();
  const geschrieben = aufrufe.filter((a) => a.dienst === "heatnexus.set_time_program").map((a) => a.angaben.blocks);
  return { meldungen: [zuerst, meldung()], geschrieben };
}

await abschnitt("veraltet", async () => {
  const vorher = [
    { weekdays: WERKTAGE, switchPoints: ARBEIT },
    { weekdays: ["Sa"], switchPoints: SAMSTAG },
    { weekdays: ["Su"], switchPoints: SONNTAG },
  ];
  const nachher = [
    { weekdays: WERKTAGE, switchPoints: ARBEIT },
    { weekdays: ["Sa", "Su"], switchPoints: SAMSTAG },
  ];
  return { gezeichnet: await zeileAendern(vorher, nachher, "So"), sofort: await zeileAendern(vorher, nachher, "So", false) };
});

await abschnitt("umgestellt", async () => {
  const vorher = [
    { weekdays: WERKTAGE, switchPoints: ARBEIT },
    { weekdays: ["Sa", "Su"], switchPoints: SAMSTAG },
  ];
  const neu = [...vorher].reverse();
  return { gezeichnet: await zeileAendern(vorher, neu, "Sa, So"), sofort: await zeileAendern(vorher, neu, "Sa, So", false) };
});

console.log(JSON.stringify(befund));
"""


@pytest.fixture(scope="module")
def befund(tmp_path_factory) -> dict:
    skript = tmp_path_factory.mktemp("fenster") / "fenster.mjs"
    skript.write_text(
        SKRIPT.replace("__ATTRAPPE__", (TESTS / "js" / "dom-attrappe.mjs").as_uri())
        .replace("__FRONTEND__", FRONTEND.as_uri())
        .replace("__SPRACHEN__", str(KOMPONENTE / "sprachen").replace("\\", "/")),
        encoding="utf-8",
    )
    lauf = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    return json.loads(lauf.stdout)


def _abschnitt(befund: dict, name: str):
    teil = befund[name]
    assert not (isinstance(teil, dict) and "fehler" in teil), teil.get("fehler")
    return teil


def test_fenster_werden_zu_ein_und_aus(befund):
    lesen = _abschnitt(befund, "lesen")
    assert lesen["bloecke"][0]["tage"] == ["Mo", "Tu", "We", "Th", "Fr"]
    assert lesen["abschnitte"] == [
        {"von": 0, "bis": 300, "wert": 0},
        {"von": 300, "bis": 480, "wert": 1},
        {"von": 480, "bis": 900, "wert": 0},
        {"von": 900, "bis": 1320, "wert": 1},
        {"von": 1320, "bis": 1440, "wert": 0},
    ]
    assert lesen["fenster"] == [True, False]
    assert lesen["skala"] is True


def test_ein_fenster_bis_null_uhr_endet_um_mitternacht(befund):
    lesen = _abschnitt(befund, "lesen")
    assert lesen["ende"] == [
        {"von": 0, "bis": 1320, "wert": 0},
        {"von": 1320, "bis": 1440, "wert": 1},
    ]
    assert lesen["frueh"] == [
        {"von": 0, "bis": 360, "wert": 1},
        {"von": 360, "bis": 1440, "wert": 0},
    ]


def test_ein_fensterprogramm_zeigt_seine_fenster_nur_lesend(befund):
    reiter = _abschnitt(befund, "reiter")
    assert reiter["leer"] is False
    assert reiter["tage"] == ["Mo–Fr", "Sa, So"]
    assert reiter["zeiten"][:2] == ["05:00 – 08:00", "15:00 – 22:00"]
    assert reiter["werte"][:2] == ["Ein", "Ein"]
    assert reiter["knopf"] == [None, None]
    assert reiter["offen"] is False
    assert reiter["bearbeiten"] is True


def test_gleich_benannte_karten_tragen_das_modell(befund):
    titel = _abschnitt(befund, "titel")
    assert titel["de"] == ["AeroWIN EVO Wärmepumpe", "AeroWIN Wärmepumpe", "AeroWIN"]
    assert titel["en"] == ["AeroWIN EVO heat pump", "AeroWIN heat pump", "AeroWIN"]
    assert titel["pumpen"] == ["AeroWIN EVO Wärmepumpe", "AeroWIN"]


def test_die_vorschau_zeigt_einen_tag_nur_mit_aus(befund):
    assert _abschnitt(befund, "vorschau") == ["Aus"]


def test_eine_neue_schaltzeit_folgt_der_spaetesten_und_ist_frei(befund):
    mehr = _abschnitt(befund, "mehr")
    assert mehr["zeile"] == [{"zeit": 1425, "wert": 18}, {"zeit": 1410, "wert": 18}]
    assert mehr["dialog"][-1] == {"zeit": 1425, "wert": 18}


@pytest.mark.parametrize("fall", ["gezeichnet", "sofort"])
def test_ein_neuer_stand_der_anlage_verhindert_das_speichern(befund, fall):
    """Neu gezeichnet oder noch vor dem nächsten Bild gespeichert: Geschrieben wird nichts."""
    veraltet = _abschnitt(befund, "veraltet")[fall]
    assert veraltet["geschrieben"] == []
    assert any(
        m.startswith("Das Programm hat sich inzwischen geändert.") for m in veraltet["meldungen"]
    )


@pytest.mark.parametrize("fall", ["gezeichnet", "sofort"])
def test_bei_neuer_reihenfolge_trifft_das_speichern_den_richtigen_block(befund, fall):
    umgestellt = _abschnitt(befund, "umgestellt")[fall]
    assert umgestellt["meldungen"] == ["", ""]
    (bloecke,) = umgestellt["geschrieben"]
    tage = {tuple(b["weekdays"]): b["switch_points"][0]["value"] for b in bloecke}
    assert tage == {("Mo", "Tu", "We", "Th", "Fr"): 21, ("Sa", "Su"): 19}
