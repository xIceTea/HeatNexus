"""Steller der Automatik: was an die Steuerung geht und was nicht."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
JETZT = datetime(2026, 9, 27, 7, 0, tzinfo=TZ)
UML = [0, 1, 2, 3, 4, 5, 6, 7]
INFINITY = [0, 1, 2, 3, 4, 5, 7]


@pytest.fixture(scope="module")
def regel():
    load_standalone("automatik")
    load_standalone("automatik.profile")
    return load_standalone("automatik.regel")


@pytest.fixture(scope="module")
def s(regel):
    return load_standalone("automatik.steller")


class Schreiber:
    def __init__(self, fehler: Exception | None = None):
        """Merkt sich jeden Aufruf; mit `fehler` lehnt er jeden ab."""
        self.aufrufe: list[tuple[str, str]] = []
        self.fehler = fehler

    async def __call__(self, oid: str, wert: str) -> None:
        if self.fehler:
            raise self.fehler
        self.aufrufe.append((oid, wert))


def entscheidung(regel, *aktionen, text="Grund."):
    return regel.Entscheidung(regel.Zustand.SONNENTAG, tuple(aktionen), text, regel.Gedaechtnis())


def ausfuehren(steller, e, **kw):
    felder = {"jetzt": JETZT, "betriebswahl": 2, "budget": 4, "beobachten": False}
    felder.update(kw)
    return asyncio.run(steller.ausfuehren(e, **felder))


def test_nur_ww_je_bauart(s):
    assert s.nur_ww_wert(UML) == 6
    assert s.nur_ww_wert(INFINITY) == 0


def test_absenken_schreibt_temperatur_und_dauer(s, regel):
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", UML, schreiber)
    assert ausfuehren(
        steller, entscheidung(regel, regel.Aktion("absenken", soll=19.5, minuten=400))
    )
    assert schreiber.aufrufe == [("/1/15/0/3/4/0", "19.5"), ("/1/15/0/2/10/0", "400")]
    assert steller.stand.eingriffe == 1
    assert steller.stand.protokoll[0]["art"] == "geschrieben"
    assert steller.stand.protokoll[0]["werte"] == [["/3/4/0", "19.5"], ["/2/10/0", "400"]]


def test_beobachten_schreibt_nichts(s, regel):
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", UML, schreiber)
    e = entscheidung(regel, regel.Aktion("nur_ww"))
    assert ausfuehren(steller, e, beobachten=True) is True
    assert schreiber.aufrufe == []
    assert steller.stand.protokoll[0]["art"] == "haette"
    assert steller.stand.eingriffe == 0


def test_budget_haelt_an_ausser_bei_sicherheit(s, regel):
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", UML, schreiber)
    ausfuehren(steller, entscheidung(regel, regel.Aktion("absenkung_ende")), budget=1)
    assert (
        ausfuehren(steller, entscheidung(regel, regel.Aktion("absenkung_ende")), budget=1) is False
    )
    assert steller.stand.protokoll[0]["art"] == "budget"
    sicher = entscheidung(regel, regel.Aktion("absenkung_ende", sicherheit=True))
    assert ausfuehren(steller, sicher, budget=1) is True
    assert len(schreiber.aufrufe) == 2


def test_abgelehnter_eingriff_steht_im_protokoll(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber(RuntimeError("HTTP 409")))
    assert ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww"))) is False
    assert steller.stand.protokoll[0]["art"] == "abgelehnt"
    assert "HTTP 409" in steller.stand.protokoll[0]["text"]
    assert steller.stand.eingriffe == 0


def test_rueckkehr_stellt_die_vorherige_wahl_her(s, regel):
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", INFINITY, schreiber)
    ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww")), betriebswahl=2)
    assert steller.stand.erwartet == 0
    ausfuehren(steller, entscheidung(regel, regel.Aktion("zurueck")), betriebswahl=0)
    assert schreiber.aufrufe == [("/1/15/0/3/50/0", "0"), ("/1/15/0/3/50/0", "2")]
    assert steller.stand.erwartet is None


def test_rueckkehr_ohne_gemerkte_wahl_nimmt_programm_1(s, regel):
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", UML, schreiber)
    ausfuehren(steller, entscheidung(regel, regel.Aktion("zurueck")), betriebswahl=6)
    assert schreiber.aufrufe == [("/1/15/0/3/50/0", "1")]


def test_handeingriff_an_der_betriebswahl(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww")))
    spaeter = JETZT + timedelta(minutes=10)
    g = regel.Gedaechtnis(saison=regel.NUR_WW)
    kw = {"jetzt": spaeter, "rest_min": None}
    assert steller.handeingriff(g, betriebswahl=1, betriebsart=1, **kw)
    assert steller.handeingriff(g, betriebswahl=6, betriebsart=0, **kw) is None
    assert steller.handeingriff(g, betriebswahl=1, betriebsart=3, **kw) is None


def test_handeingriff_nicht_direkt_nach_eigenem_schreiben(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww")))
    g = regel.Gedaechtnis(saison=regel.NUR_WW)
    kurz = JETZT + timedelta(minutes=1)
    assert steller.handeingriff(g, jetzt=kurz, betriebswahl=2, rest_min=None, betriebsart=0) is None


def test_handeingriff_beendet_die_absenkung(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    g = regel.Gedaechtnis(
        absenkung_art=regel.SONNE,
        absenkung_von=JETZT,
        absenkung_bis=JETZT + timedelta(hours=5),
    )
    spaeter = JETZT + timedelta(hours=1)
    text = steller.handeingriff(g, jetzt=spaeter, betriebswahl=1, rest_min=0, betriebsart=1)
    assert text == "Absenkung von Hand beendet."
    passt = steller.handeingriff(g, jetzt=spaeter, betriebswahl=1, rest_min=240, betriebsart=1)
    assert passt is None


def test_neuer_tag_setzt_das_budget_zurueck(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    ausfuehren(steller, entscheidung(regel, regel.Aktion("absenkung_ende")))
    morgen = JETZT + timedelta(days=1)
    ausfuehren(steller, entscheidung(regel, regel.Aktion("absenkung_ende")), jetzt=morgen)
    assert steller.stand.eingriffe == 1


def test_abgleichen_vergisst_die_erwartung_ohne_eigenen_eingriff(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww")))
    steller.abgleichen(regel.Gedaechtnis(), JETZT)
    assert steller.stand.erwartet is None


def test_protokoll_ist_begrenzt(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    for _ in range(s.PROTOKOLL_MAX + 5):
        steller.vermerken(JETZT, "geprueft", "x")
    assert len(steller.stand.protokoll) == s.PROTOKOLL_MAX


def test_stand_uebersteht_den_store(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww")))
    assert s.Stand.aus_dict(steller.stand.als_dict()) == steller.stand
    assert s.Stand.aus_dict("kaputt") == s.Stand()
