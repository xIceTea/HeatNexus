"""Befundwissen je Baureihe steht im Gerätemodul; der Befund liest es von dort."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def geraete():
    return load_standalone("geraete")


def test_befundwissen_steht_je_baureihe_im_geraetemodul(geraete):
    assert set(geraete.BEFUND) == {6, 7, 9, 10, 25, 27}
    assert geraete.BEFUND[9]["brennstoff"] == {"zaehler": "/23/103/0", "weise": "zaehler"}
    assert geraete.BEFUND[10]["abgas"]["klassen"] == ("2009",)
    assert geraete.BEFUND[27]["waermepumpe"]["phasen_heizen"] == (4,)


def test_pflege_entsteht_aus_dem_geraetemodul(geraete):
    pflege = load_standalone("befund.pflege")
    assert [x.adresse for x in pflege.PFLEGE[25]] == ["/39/91/0", "/39/92/0", "/39/93/0"]
    assert {x.art for x in pflege.KALENDERPFLEGE[(10, "2009")]} == {"asche", "jahresreinigung"}


def test_eine_weitere_geraeteklasse_bekommt_kalenderpflege_und_abgas(monkeypatch):
    """Eine neue Geräteklasse braucht nur ihren Eintrag; die Logik bleibt unverändert."""
    pflege = load_standalone("befund.pflege")
    ziele = load_standalone("befund.pflegeziele")
    abgasziele = load_standalone("befund.abgasziele")
    monkeypatch.setitem(pflege.KALENDERPFLEGE, (10, "1409"), pflege.KALENDERPFLEGE[(10, "2009")])
    monkeypatch.setitem(
        abgasziele.ABGASWAECHTER, 10, abgasziele.ABGASWAECHTER[10] | {"klassen": ("2009", "1409")}
    )
    beschreibungen = [{"oid": "/1/70/0/0/11/0", "fct_type": 10, "device_id": "alt"}]
    assert {z.pflege.art for z in ziele.ziele(beschreibungen, {"70": "1409"})} == {
        "asche",
        "jahresreinigung",
    }
    assert [z.logwin for z in abgasziele.ziele(beschreibungen, {"70": "1409"})] == [True]
