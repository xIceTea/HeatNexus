"""Der Ablauf des bewegten Schaubilds.

**Geprüft wird die Rechnung, nicht das Bild.** Ob das GIF byteweise dasselbe
ist, hängt an Browserfassung und Schriftarten des Rechners, der es erzeugt hat
– ein Vergleich darauf wäre in der CI nur eine Fehlalarmquelle. Was sich
prüfen lässt und worauf es ankommt: dass der gezeigte Ablauf die Anlage richtig
erzählt und dass die Ebenen darüber dieselben Zustandsklassen setzen wie die
Oberfläche.

Der Anlass: Die Marke am Puffer unterscheidet „lädt" von „entlädt" an der
Frage, welche Pumpe fördert – nicht an den Temperaturen. Wer den Ablauf ändert,
bekommt das leicht falsch herum, und im GIF fällt es niemandem auf.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "build_schaubild_animation.py"


@pytest.fixture(scope="module")
def animation():
    """Das Werkzeug kommt ohne Home Assistant und ohne Browser aus."""
    spec = importlib.util.spec_from_file_location("schaubild_animation", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def daten(animation):
    return animation.karte()


# ---------------------------------------------------------------------------
# Der Ablauf
# ---------------------------------------------------------------------------
def test_am_anfang_steht_die_anlage_still(animation):
    """Ohne Ruhe am Anfang sieht man dem Bild den Start nicht an."""
    lage = animation.zustand(0)
    assert not any(lage["pumpen"].values())
    assert lage["werte"]["sensor.leistung"] == 0


def test_der_kessel_springt_an_bevor_der_puffer_laedt(animation):
    """Erst Wärme, dann Ladung – andersherum ergäbe es keinen Sinn."""
    an = min(b for b in range(animation.BILDER) if animation.zustand(b)["werte"]["sensor.leistung"])
    laedt = min(
        b
        for b in range(animation.BILDER)
        if animation.zustand(b)["pumpen"]["binary_sensor.pufferladepumpe"]
    )
    assert an < laedt


def test_die_anlage_wird_durchgehend_waermer(animation):
    """Puffer, Vorlauf und Warmwasser dürfen zwischendurch nicht abkühlen."""
    for messwert in ("sensor.puffer_oben", "sensor.puffer_unten", "sensor.warmwasser"):
        verlauf = [animation.zustand(b)["werte"][messwert] for b in range(animation.BILDER)]
        assert verlauf == sorted(verlauf), messwert
        assert verlauf[-1] > verlauf[0], messwert


def test_der_puffer_bleibt_oben_waermer_als_unten(animation):
    """Eine umgekehrte Schichtung gibt es an einer stehenden Anlage nicht."""
    for bild in range(animation.BILDER):
        werte = animation.zustand(bild)["werte"]
        assert werte["sensor.puffer_oben"] >= werte["sensor.puffer_unten"], bild


def test_zum_schluss_entlaedt_der_puffer(animation):
    """Der Ablauf soll beide Zustände zeigen, nicht nur den einen."""
    letzte = animation.zustand(animation.BILDER - 1)["pumpen"]
    assert not letzte["binary_sensor.pufferladepumpe"]
    assert letzte["binary_sensor.heizkreispumpe"]


# ---------------------------------------------------------------------------
# Die Ebenen über dem Bild
# ---------------------------------------------------------------------------
def test_die_marke_am_puffer_folgt_den_pumpen(animation, daten):
    """„lädt" hängt an der Ladepumpe, „entlädt" an einer Entnahme."""
    beim_laden = animation._speicher(daten, animation.zustand(30))
    assert ">lädt<" in beim_laden

    zum_schluss = animation._speicher(daten, animation.zustand(animation.BILDER - 1))
    assert ">entlädt<" in zum_schluss


def test_ohne_foerderung_steht_kein_zustand_am_puffer(animation, daten):
    """Steht alles, behauptet die Marke nichts."""
    ruhe = animation._speicher(daten, animation.zustand(0))
    assert "laedt" not in ruhe and "entlaedt" not in ruhe


def test_die_baender_laufen_nur_wenn_etwas_foerdert(animation, daten):
    """Sonst zeigte das Bild eine Strömung, die es nicht gibt."""
    assert "laeuft" not in animation._fluss(daten, animation.zustand(0))
    assert "laeuft" in animation._fluss(daten, animation.zustand(animation.BILDER - 1))


def test_eine_stichleitung_stroemt_nur_an_ihrem_anlagenteil(animation, daten):
    """Genau daran sieht man, wohin die Wärme gerade geht."""
    lage = animation.zustand(30)  # Puffer lädt, Heizkreis noch aus
    senkrecht = animation._senkrecht(daten, lage)
    # Je Pumpe zwei Bänder; gezählt wird, wie viele davon laufen.
    laufend = senkrecht.count("laeuft")
    assert 0 < laufend < senkrecht.count("fluss senkrecht")


def test_das_glutbett_folgt_der_kesselleistung(animation, daten):
    """Aus heißt unsichtbar, Volllast heißt hell."""
    assert "opacity:0.00" in animation._glut(daten, animation.zustand(0))
    hell = animation._glut(daten, animation.zustand(30))
    assert "brennt" in hell


def test_jede_aufnahme_haelt_die_bewegung_an(animation, daten):
    """Ohne Anhalten stünde in jeder Aufnahme derselbe Bewegungszustand."""
    block = animation.aufnahme(daten, 12, 1.2, "dunkel")
    assert "animation-play-state:paused" in block
    assert "animation-delay:-1.20s" in block


def test_das_stylesheet_kommt_aus_der_oberflaeche(animation):
    """Nachgebaute Regeln liefen irgendwann auseinander."""
    stil = animation._stil()
    assert ".schaubild .pumpe.laeuft" in stil
    assert "@keyframes stroemen" in stil


def test_beide_farbsaetze_werden_erzeugt(animation):
    """Das README zeigt je nach Erscheinungsbild das passende Bild."""
    assert set(animation.ZIELE) == {"dunkel", "hell"}
    for ziel in animation.ZIELE.values():
        assert ziel.exists(), f"{ziel.name} fehlt – python tools/build_schaubild_animation.py"
