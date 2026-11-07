"""Pflegeziele: welche Pflege an welchem Gerät entsteht."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def z():
    load_standalone("befund")
    return load_standalone("befund.pflegeziele")


def d(prefix, gnmn, fct, device="dev", **mehr):
    beschreibung = {"prefix": prefix, "oid": f"{prefix}/{gnmn}/0", "fct_type": fct}
    return beschreibung | {"device_id": device} | mehr


def test_purowin_drei_zaehler_mit_max(z):
    b = [
        d("/1/60/0", "39/91", 25),
        d("/1/60/0", "39/92", 25),
        d("/1/60/0", "39/93", 25, max=65534),
    ]
    ergebnis = z.ziele(b, {})
    assert [x.pflege.art for x in ergebnis] == ["asche", "hauptreinigung", "wartung"]
    assert ergebnis[2].max_feld == 65534
    assert {x.prefix for x in ergebnis} == {"/1/60/0"}


def test_biowin_nur_was_gemeldet_ist(z):
    assert [x.pflege.art for x in z.ziele([d("/1/60/0", "20/61", 9)], {})] == ["reinigung"]


def test_gas_seit_service(z):
    ergebnis = z.ziele([d("/1/70/0", "60/29", 6, device="gas")], {})
    assert ergebnis[0].pflege.weise == "seit_service"
    assert ergebnis[0].device_id == "gas"


def test_logwin_nach_geraeteklasse(z):
    b = [d("/1/65/0", "2/81", 10, device="log"), d("/1/65/0", "0/11", 10, device="log")]
    assert [x.pflege.art for x in z.ziele(b, {"65": "2009"})] == ["asche", "jahresreinigung"]
    assert z.ziele(b, {"65": "1415"}) == []


def test_fremder_funktionstyp_ergibt_nichts(z):
    assert z.ziele([d("/1/60/0", "39/92", 9)], {}) == []


def test_ohne_geraet_ergibt_nichts(z):
    assert z.ziele([d("/1/60/0", "39/92", 25, device=None)], {}) == []
