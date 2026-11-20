"""Befundwissen je Baureihe steht im Gerätemodul; der Befund liest es von dort."""

from __future__ import annotations

import re

import pytest

from .conftest import COMPONENT_DIR, load_standalone


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
    assert [z.ohne_leistung for z in abgasziele.ziele(beschreibungen, {"70": "1409"})] == [True]


def test_waermepumpenadressen_stehen_im_geraetemodul(geraete):
    tag, gesamt = geraete.BEFUND[7]["waermepumpe"], geraete.BEFUND[27]["waermepumpe"]
    assert tag["tageszaehler"] == {"q": "/52/60/0", "cop": "/52/87/0", "bh": "/52/51/0"}
    assert tag["ww_heute"] == "/52/62/0"
    assert gesamt["waerme"] == ("/60/18/0", "/52/59/0")
    assert gesamt["eheizung"] == "/56/5/0"
    assert {w["luft"] for w in (tag, gesamt)} == {"/52/12/0"}


def test_waermepumpenlauf_nennt_keine_eigenen_adressen():
    lauf = load_standalone("befund.waermepumpelauf")
    quelle = (COMPONENT_DIR / "befund" / "waermepumpelauf.py").read_text(encoding="utf-8")
    assert not re.search(r'"/\d+/\d+/\d+"', quelle)
    assert lauf.LUFT == {7: "/52/12/0", 27: "/52/12/0"}
    assert lauf.LEISTUNG == {7: "/50/26/0", 27: "/50/26/0"}
    assert (lauf.EHEIZUNG, lauf.WW_HEUTE, lauf.BH_27) == ("/56/5/0", "/52/62/0", "/52/50/0")
    assert lauf.TAGESZAEHLER == {"q": "/52/60/0", "cop": "/52/87/0", "bh": "/52/51/0"}
    assert lauf.WAERME_27 == ("/60/18/0", "/52/59/0")
    assert lauf.STROM_27 == ("/52/81/0", "/52/120/0")
    assert lauf.KUEHLEN_27 == ("/60/19/0", "/52/63/0")


def test_jede_waermepumpe_nennt_luft_und_leistung(geraete):
    """Der Befund baut seine Tabellen beim Import; eine Lücke fiele erst beim Laden auf."""
    funktionen = load_standalone("befund.waermepumpe").FUNKTIONSTYPEN
    assert {7, 27} <= set(funktionen)
    for fct in funktionen:
        assert {"luft", "leistung"} <= set(geraete.BEFUND[fct]["waermepumpe"])
