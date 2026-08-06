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
