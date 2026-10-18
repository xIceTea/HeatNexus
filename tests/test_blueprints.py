"""Mitgelieferte Automations-Vorlagen.

Die Vorlagen enthalten den Home-Assistant-Tag ``!input`` und lassen sich
darum nicht mit ``yaml.safe_load`` prüfen. Ein eigener Lader bildet den Tag
auf einen Platzhalter ab; damit ist die Datei trotzdem vollständig gegen
Syntaxfehler abgesichert.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

VORLAGEN = (
    Path(__file__).parent.parent
    / "custom_components"
    / "heatnexus"
    / "blueprints"
    / "automation"
    / "heatnexus"
)


class _Lader(yaml.SafeLoader):
    """SafeLoader, der ``!input`` kennt."""


_Lader.add_constructor("!input", lambda loader, node: {"__input__": node.value})


def _dateien() -> list[Path]:
    return sorted(VORLAGEN.glob("*.yaml"))


def test_vorlagen_vorhanden():
    assert _dateien(), "Es wird keine einzige Automations-Vorlage mitgeliefert"


@pytest.mark.parametrize("datei", _dateien(), ids=lambda p: p.name)
def test_vorlage_ist_gueltig(datei: Path):
    inhalt = yaml.load(datei.read_text(encoding="utf-8"), Loader=_Lader)
    blueprint = inhalt["blueprint"]
    assert blueprint["domain"] == "automation"
    assert blueprint["name"].startswith("HeatNexus")
    assert blueprint["description"].strip()
    assert blueprint["input"], "Vorlage ohne Eingabefelder"
    # Ein Auslöser ist Pflicht, sonst löst die Automation nie aus.
    assert inhalt.get("triggers") or inhalt.get("trigger")


@pytest.mark.parametrize("datei", _dateien(), ids=lambda p: p.name)
def test_eingaben_werden_benutzt(datei: Path):
    text = datei.read_text(encoding="utf-8")
    inhalt = yaml.load(text, Loader=_Lader)
    for name in inhalt["blueprint"]["input"]:
        assert f"!input {name}" in text, f"Eingabefeld {name} wird nirgends verwendet"


# ---------------------------------------------------------------------------
# Legionellenschutz
#
# Die einzige Vorlage, die Werte der Anlage *verstellt* statt nur zu melden.
# Was sie stellt, muss sie auch zurückstellen – und zwar auch dann, wenn die
# Zieltemperatur nie erreicht wird. Bliebe die Ladetemperatur auf 60 °C
# stehen, heizte die Anlage ab da jede normale Ladung dorthin.
# ---------------------------------------------------------------------------
LEGIONELLEN = VORLAGEN / "legionellenschutz.yaml"


@pytest.fixture(scope="module")
def legionellen() -> dict:
    return yaml.load(LEGIONELLEN.read_text(encoding="utf-8"), Loader=_Lader)


def _aktionen(schritt) -> list:
    """Alle Aktionsnamen eines Schritts, beliebig tief geschachtelt."""
    gefunden: list[str] = []
    if isinstance(schritt, dict):
        if isinstance(schritt.get("action"), str):
            gefunden.append(schritt["action"])
        for wert in schritt.values():
            gefunden.extend(_aktionen(wert))
    elif isinstance(schritt, list):
        for eintrag in schritt:
            gefunden.extend(_aktionen(eintrag))
    return gefunden


def test_aufraeumen_haengt_an_keiner_bedingung(legionellen):
    """Ladung aus und Ladetemperatur zurück stehen auf oberster Ebene.

    Läge auch nur eines davon in einem `if` oder `choose`, überstünde ein
    abgebrochener Lauf mit erhöhter Ladetemperatur – und die Anlage heizte
    fortan jede normale Ladung dorthin.
    """
    schritte = legionellen["actions"]
    unbedingt = [s for s in schritte if isinstance(s, dict) and "action" in s]
    assert "switch.turn_off" in [s["action"] for s in unbedingt], (
        "Die Ladung wird nicht auf jeden Fall wieder ausgeschaltet"
    )
    # Das Zurückstellen der Temperatur darf eine Bedingung haben – aber nur
    # die, dass der gemerkte Wert überhaupt lesbar war.
    zuruecksetzen = [
        s
        for s in schritte
        if isinstance(s, dict) and "number.set_value" in _aktionen(s.get("then", []))
    ]
    assert zuruecksetzen, "Die Ladetemperatur wird nirgends zurückgestellt"


def test_die_ladung_wird_spaetestens_nach_der_hoechstdauer_beendet(legionellen):
    """Ohne Zeitgrenze liefe die Ladung im Zweifel bis zum nächsten Lauf."""
    warten = [s for s in legionellen["actions"] if isinstance(s, dict) and "wait_template" in s]
    assert warten, "Es wird gar nicht auf die Zieltemperatur gewartet"
    assert warten[0].get("timeout"), "Das Warten hat keine Zeitgrenze"
    assert warten[0].get("continue_on_timeout") is True, (
        "Nach der Zeitgrenze bricht der Ablauf ab, statt aufzuräumen"
    )


@pytest.mark.parametrize(("ist", "erreicht"), [("61.2", True), ("59.6", True), ("45", False)])
def test_ein_schon_warmer_speicher_gilt_sofort_als_erreicht(legionellen, ist, erreicht):
    """Ein Auslöser feuerte nur beim Überschreiten; ein schon warmer Speicher wartete bis zur Grenze."""
    (warten,) = [s for s in legionellen["actions"] if isinstance(s, dict) and "wait_template" in s]
    ergebnis = _rendern(
        warten["wait_template"], states=lambda _e: ist, fuehler="sensor.ww", ziel=60
    )
    assert ergebnis == str(erreicht)
    (merken,) = [s for s in legionellen["actions"] if "erreicht" in s.get("variables", {})]
    assert merken["variables"]["erreicht"] == "{{ wait.completed }}"


def _schreibende(schritt) -> list[dict]:
    """Alle Aktionen, die einen Wert an der Anlage stellen, beliebig tief geschachtelt."""
    gefunden: list[dict] = []
    if isinstance(schritt, dict):
        if str(schritt.get("action", "")).split(".")[0] in {"select", "number", "switch"}:
            gefunden.append(schritt)
        for wert in schritt.values():
            gefunden.extend(_schreibende(wert))
    elif isinstance(schritt, list):
        for eintrag in schritt:
            gefunden.extend(_schreibende(eintrag))
    return gefunden


def test_eine_gescheiterte_aktion_haelt_das_aufraeumen_nicht_auf(legionellen):
    """Sonst bliebe nach einem Schreibfehler die Ladetemperatur auf dem Zielwert stehen."""
    schreibende = _schreibende(legionellen["actions"])
    assert len(schreibende) == 6
    assert all(s.get("continue_on_error") is True for s in schreibende)


def _ww_namen() -> list[str]:
    """Wie „WW-Betrieb" in jeder Sprache heißt: Herstellertabelle und eigene Texte."""
    import json

    paket = VORLAGEN.parent.parent.parent
    datenbank = json.loads((paket / "device_db.json").read_text(encoding="utf-8"))
    namen = [datenbank["enums"]["3/50"]["6"]]
    namen += [t["enums"]["3/50"]["6"] for t in datenbank.get("sprachen", {}).values()]
    for datei in sorted((paket / "sprachen").glob("*.json")):
        namen.append(json.loads(datei.read_text(encoding="utf-8"))["WW-Betrieb"])
    return namen


@pytest.mark.parametrize("name", _ww_namen())
def test_der_ww_betrieb_wird_in_jeder_sprache_gefunden(legionellen, name):
    (umstellen,) = [s for s in legionellen["actions"] if isinstance(s, dict) and "repeat" in s][:1]
    vorlage = umstellen["repeat"]["sequence"][0]["variables"]["ww_eintrag"]
    optionen = ["Standby", "Programm 1", name]
    ergebnis = _rendern(
        vorlage, state_attr=lambda _e, _a: optionen, repeat={"item": "select.betriebswahl"}
    )
    assert ergebnis == name


def test_ein_gescheiterter_lauf_bleibt_nicht_still(legionellen):
    """Darauf verlässt man sich – ein stiller Fehlschlag ist der schlimmste."""
    text = LEGIONELLEN.read_text(encoding="utf-8")
    assert "!input aktion_misslungen" in text


def test_die_verbruehungsgefahr_steht_in_der_beschreibung(legionellen):
    """60 °C verbrühen in Sekunden. Wer das einrichtet, muss es gelesen haben."""
    beschreibung = legionellen["blueprint"]["description"]
    assert "Verbrühungsgefahr" in beschreibung
    assert "Mischventil" in beschreibung


def test_nur_ein_lauf_gleichzeitig(legionellen):
    """Zwei Läufe stellten einander die Ladetemperatur unter den Händen weg."""
    assert legionellen["mode"] == "single"


# ---------------------------------------------------------------------------
# Empfehlung der Automatik
# ---------------------------------------------------------------------------
EMPFEHLUNG = VORLAGEN / "automatik_empfehlung.yaml"


@pytest.fixture(scope="module")
def empfehlung() -> dict:
    return yaml.load(EMPFEHLUNG.read_text(encoding="utf-8"), Loader=_Lader)


def test_empfehlung_antwort_gehoert_zur_eigenen_mitteilung(empfehlung):
    """Mitteilung und Warten teilen sich die Aktionskennung; ohne Antwort endet der Lauf."""
    assert empfehlung["triggers"][0]["event_type"] == "heatnexus_automatik_empfehlung"
    aktionen = empfehlung["actions"]
    (melden,) = (a for a in aktionen if "data" in a and "actions" in a["data"])
    (warten,) = (a for a in aktionen if "wait_for_trigger" in a)
    kennungen = [a["action"] for a in melden["data"]["actions"]]
    assert kennungen[0] == melden["data"]["tag"]
    assert [w["event_data"]["action"] for w in warten["wait_for_trigger"]] == kennungen
    assert warten["continue_on_timeout"] is False
    assert any(a.get("action") == "button.press" for a in aktionen)


@pytest.mark.parametrize(
    ("antwort", "taste"), [("ID", "button.ja"), ("ID_VERWERFEN", "button.nein")]
)
def test_empfehlung_drueckt_die_taste_zur_antwort(empfehlung, antwort, taste):
    from jinja2 import Environment

    (druecken,) = (a for a in empfehlung["actions"] if a.get("action") == "button.press")
    vorlage = druecken["target"]["entity_id"]
    wait = {"trigger": {"event": {"data": {"action": antwort}}}}
    werte = {"aktion_id": "ID", "taste": "button.ja", "verwerfen": "button.nein", "wait": wait}
    assert Environment().from_string(vorlage).render(**werte).strip() == taste


@pytest.mark.parametrize(
    ("taste", "meldet"), [(None, False), ("None", False), ("", False), ("button.x", True)]
)
def test_empfehlung_meldet_nur_mit_taste(empfehlung, taste, meldet):
    from jinja2 import Environment

    vorlage = empfehlung["conditions"][0]["value_template"]
    assert Environment().from_string(vorlage).render(taste=taste) == str(meldet)


# ---------------------------------------------------------------------------
# Auswahl der mitgelieferten Vorlagen
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def modul():
    pfad = VORLAGEN.parent.parent.parent / "blueprints.py"
    quelle = pfad.read_text(encoding="utf-8")
    # Ohne Home Assistant laden: Nur die Dateiarbeit wird geprüft.
    quelle = quelle.replace(
        "from homeassistant.core import HomeAssistant", "HomeAssistant = object"
    )
    quelle = quelle.replace("from .const import DOMAIN", "DOMAIN = 'heatnexus'")
    raum: dict = {"__file__": str(pfad), "__name__": "hn_blueprints"}
    exec(compile(quelle, str(pfad), "exec"), raum)
    return type("Modul", (), raum)


def test_jede_vorlage_hat_einen_anzeigenamen(modul):
    namen = modul.verfuegbare()
    assert set(namen) == {p.stem for p in VORLAGEN.glob("*.yaml")}
    assert all(n.startswith("HeatNexus") for n in namen.values())


def test_nur_gewaehlte_vorlagen_werden_abgelegt(modul, tmp_path):
    ziel = tmp_path / "bp"
    geschrieben, entfernt = modul._kopieren(ziel, "1.0.0", {"stoerung_melden"}, tmp_path / "a.yaml")

    assert geschrieben == 1
    assert entfernt == 0
    assert [p.name for p in ziel.glob("*.yaml")] == ["stoerung_melden.yaml"]


def test_eine_abgewaehlte_vorlage_wird_entfernt(modul, tmp_path):
    ziel = tmp_path / "bp"
    modul._kopieren(ziel, "1.0.0", {"stoerung_melden"}, tmp_path / "a.yaml")
    _, entfernt = modul._kopieren(ziel, "1.0.1", set(), tmp_path / "a.yaml")

    assert entfernt == 1
    assert not list(ziel.glob("*.yaml"))


def test_eine_benutzte_vorlage_bleibt_liegen(modul, tmp_path):
    """Sonst stünde die Automation des Nutzers ohne ihren Bauplan da."""
    ziel = tmp_path / "bp"
    automationen = tmp_path / "automations.yaml"
    modul._kopieren(ziel, "1.0.0", {"stoerung_melden"}, automationen)
    automationen.write_text(
        "- use_blueprint:\n    path: heatnexus/stoerung_melden.yaml\n", encoding="utf-8"
    )

    _, entfernt = modul._kopieren(ziel, "1.0.1", set(), automationen)

    assert entfernt == 0
    assert (ziel / "stoerung_melden.yaml").is_file()


def test_ohne_auswahl_liest_der_executor_die_vorlagen(modul, tmp_path):
    """Das Verzeichnis der Vorlagen wird nicht in der Ereignisschleife gelesen."""
    import asyncio
    from types import SimpleNamespace

    im_executor: list = []
    globale = modul._kopieren.__globals__
    original = globale["verfuegbare"]
    gelesen: list[bool] = []

    def verfuegbare():
        gelesen.append(bool(im_executor))
        return original()

    async def executor(funktion, *argumente):
        im_executor.append(funktion)
        return funktion(*argumente)

    hass = SimpleNamespace(
        config=SimpleNamespace(path=lambda *teile: str(tmp_path.joinpath(*teile))),
        async_add_executor_job=executor,
    )
    globale["verfuegbare"] = verfuegbare
    try:
        asyncio.run(modul.async_install_blueprints(hass, "1.0.0"))
    finally:
        globale["verfuegbare"] = original

    assert gelesen == [True]
    assert len(list((tmp_path / "blueprints" / "automation" / "heatnexus").glob("*.yaml"))) == len(
        _dateien()
    )


@pytest.mark.parametrize("datei", _dateien(), ids=lambda p: p.name)
def test_die_quelle_zeigt_auf_die_datei_im_repo(datei: Path):
    inhalt = yaml.load(datei.read_text(encoding="utf-8"), Loader=_Lader)
    assert inhalt["blueprint"]["source_url"].endswith(
        f"/blob/main/custom_components/heatnexus/blueprints/automation/heatnexus/{datei.name}"
    )


# ---------------------------------------------------------------------------
# Heizkreis bei Abwesenheit: gemerkt wird nur die Betriebsart, keine Szene
# ---------------------------------------------------------------------------
ABWESEND = VORLAGEN / "heizkreis_abwesend.yaml"


@pytest.fixture(scope="module")
def abwesend() -> dict:
    return yaml.load(ABWESEND.read_text(encoding="utf-8"), Loader=_Lader)


def _rendern(vorlage: str, zustaende: dict | None = None, **werte) -> str:
    """Eine Vorlage rendern; `is_state` liest aus `zustaende`."""
    from jinja2 import Environment

    umgebung = Environment()
    umgebung.tests["is_state"] = lambda entitaet, zustand: (
        (zustaende or {}).get(entitaet) == zustand
    )
    return umgebung.from_string(vorlage).render(**werte).strip()


def test_abwesend_ohne_szene(abwesend):
    """Eine feste Szene teilten sich alle Automationen aus der Vorlage."""
    assert not [a for a in _aktionen(abwesend["actions"]) if a.startswith("scene.")]
    assert set(_aktionen(abwesend["actions"])) == {"climate.set_preset_mode"}


def _attribute(**werte):
    return lambda _entitaet, name: werte.get(name)


def test_abwesend_merkt_die_betriebsart_vor_dem_absenken(abwesend):
    vorher = abwesend["variables"]["vorher"]
    attribute = _attribute(preset_mode="3")
    assert _rendern(vorher, state_attr=attribute, heizkreis="climate.hk") == "3"
    absenken, zurueck = (a for a in abwesend["actions"] if a.get("action"))
    assert absenken["data"]["preset_mode"] == "{{ modus_abwesend }}"
    assert zurueck["data"]["preset_mode"] == "{{ vorher }}"


def test_abwesend_merkt_den_modus_vor_einer_umschaltenden_vorgabe(abwesend):
    """Eine Vorgabe aus Standby schaltet nur befristet ins Heizprogramm."""
    vorher = abwesend["variables"]["vorher"]
    attribute = _attribute(preset_mode="1", modus_vor_vorgabe=0)
    assert _rendern(vorher, state_attr=attribute, heizkreis="climate.hk") == "0"


@pytest.mark.parametrize(
    ("vorher", "modus", "senkt"),
    [("3", "5", True), ("5", "5", False), ("None", "5", False), ("", "5", False)],
)
def test_abwesend_senkt_nur_aus_einer_anderen_betriebsart(abwesend, vorher, modus, senkt):
    (bedingung,) = [b for b in abwesend["conditions"] if "vorher" in b.get("value_template", "")]
    ergebnis = _rendern(bedingung["value_template"], vorher=vorher, modus_abwesend=modus)
    assert ergebnis == str(senkt)


def test_abwesend_wartet_auch_auf_eine_schon_erfolgte_rueckkehr(abwesend):
    """Ein Warten auf den Zustandswechsel verpasste eine Rückkehr während des Absenkens."""
    (warten,) = [a for a in abwesend["actions"] if "wait_template" in a]
    personen = ["person.a", "person.b"]
    da = _rendern(warten["wait_template"], {"person.b": "home"}, anwesende=personen)
    weg = _rendern(warten["wait_template"], {"person.b": "not_home"}, anwesende=personen)
    assert (da, weg) == ("True", "False")


@pytest.mark.parametrize(("jetzt", "stellt_zurueck"), [("5", True), ("4", False), ("0", False)])
def test_abwesend_laesst_eine_handaenderung_stehen(abwesend, jetzt, stellt_zurueck):
    (bedingung,) = [a for a in abwesend["actions"] if a.get("condition") == "template"]
    ergebnis = _rendern(
        bedingung["value_template"],
        state_attr=lambda _e, _a: jetzt,
        heizkreis="climate.hk",
        modus_abwesend="5",
    )
    assert ergebnis == str(stellt_zurueck)
