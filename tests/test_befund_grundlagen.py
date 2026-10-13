"""Grundlagen des Befunds: gemeinsame Form und Gradtagzahl nach VDI 3807."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def form():
    load_standalone("befund")
    return load_standalone("befund.form")


@pytest.fixture(scope="module")
def gradtage():
    load_standalone("befund")
    return load_standalone("befund.gradtage")


@pytest.mark.parametrize(
    ("anzahl", "erwartet"), [(0, "sammelt"), (3, "sammelt"), (4, "vorlaeufig"), (7, "belastbar")]
)
def test_stufe_folgt_der_anzahl(form, anzahl, erwartet):
    assert form.stufe(anzahl, vorlaeufig=4, belastbar=7) == erwartet


def test_fehlt_traegt_grund(form):
    befund = form.fehlt("raeume", "raeume")
    assert befund.status == form.BRAUCHT_DATEN
    assert befund.grund == "raeume"
    assert befund.wert is None


@pytest.mark.parametrize(
    ("stufe", "auffaellig", "erwartet"),
    [
        ("sammelt", True, "sammelt"),
        ("vorlaeufig", True, "hinweis"),
        ("belastbar", False, "unauffaellig"),
    ],
)
def test_status_erst_nach_dem_sammeln(form, stufe, auffaellig, erwartet):
    assert form.status_aus(stufe, auffaellig) == erwartet


@pytest.mark.parametrize(
    ("land", "grenze"),
    [("DE", 15.0), (None, 15.0), ("AT", 12.0), ("ch", 12.0), ("LI", 12.0), ("NL", 15.0)],
)
def test_rechengrenze_je_land(gradtage, land, grenze):
    assert gradtage.rechengrenze(land) == grenze


def test_gradtag_nur_unter_der_grenze(gradtage):
    assert gradtage.gradtag(12.8, 15.0) == pytest.approx(7.2)
    assert gradtage.gradtag(15.0, 15.0) == 0.0
    assert gradtage.gradtag(16.2, 15.0) == 0.0
