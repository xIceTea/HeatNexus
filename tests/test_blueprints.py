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
    warten = [s for s in legionellen["actions"] if isinstance(s, dict) and "wait_for_trigger" in s]
    assert warten, "Es wird gar nicht auf die Zieltemperatur gewartet"
    assert warten[0].get("timeout"), "Das Warten hat keine Zeitgrenze"
    assert warten[0].get("continue_on_timeout") is True, (
        "Nach der Zeitgrenze bricht der Ablauf ab, statt aufzuräumen"
    )


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
