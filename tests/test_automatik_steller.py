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
    def __init__(self, fehler: Exception | None = None, ab: int = 0):
        """Merkt sich jeden Aufruf; mit `fehler` lehnt er jeden ab dem `ab`-ten ab."""
        self.aufrufe: list[tuple[str, str]] = []
        self.fehler = fehler
        self.ab = ab

    async def __call__(self, oid: str, wert: str) -> None:
        if self.fehler and len(self.aufrufe) >= self.ab:
            raise self.fehler
        self.aufrufe.append((oid, wert))


def entscheidung(regel, *aktionen, text="Grund."):
    return regel.Entscheidung(regel.Zustand.SONNENTAG, tuple(aktionen), text, regel.Gedaechtnis())


def ausfuehren(steller, e, **kw):
    felder = {
        "jetzt": JETZT,
        "betriebswahl": 2,
        "budget": 4,
        "beobachten": False,
        "erzwingen": False,
    }
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
    absenken = regel.Aktion("absenken", soll=19.5, minuten=60)
    ausfuehren(steller, entscheidung(regel, absenken), budget=1)
    assert ausfuehren(steller, entscheidung(regel, absenken), budget=1) is False
    assert steller.stand.protokoll[0]["art"] == "budget"
    sicher = entscheidung(regel, regel.Aktion("nur_ww", sicherheit=True))
    assert ausfuehren(steller, sicher, budget=1) is True
    assert len(schreiber.aufrufe) == 3


@pytest.mark.parametrize("art", ["zurueck", "absenkung_ende"])
def test_rueckkehr_ins_programm_zaehlt_nicht_gegen_das_budget(s, regel, art):
    """Mehr heizen ist die sichere Richtung; sie darf nie am Budget scheitern."""
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", UML, schreiber)
    assert ausfuehren(steller, entscheidung(regel, regel.Aktion(art)), budget=0) is True
    assert steller.stand.eingriffe == 0


def test_abgelehnter_eingriff_steht_im_protokoll(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber(RuntimeError("HTTP 409")))
    assert ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww"))) is False
    assert steller.stand.protokoll[0]["art"] == "abgelehnt"
    assert "HTTP 409" in steller.stand.protokoll[0]["text"]
    assert steller.stand.eingriffe == 0


def test_nach_ablehnung_wartet_der_steller_immer_laenger(s, regel):
    schreiber = Schreiber(RuntimeError("HTTP 409"))
    steller = s.Steller("/1/15/0", UML, schreiber)
    e = entscheidung(regel, regel.Aktion("zurueck"))
    ausfuehren(steller, e)
    schreiber.fehler = None
    assert ausfuehren(steller, e, jetzt=JETZT + timedelta(minutes=29)) is False
    assert schreiber.aufrufe == []
    assert len(steller.stand.protokoll) == 1  # die Sperre füllt das Protokoll nicht
    schreiber.fehler = RuntimeError("HTTP 409")
    ausfuehren(steller, e, jetzt=JETZT + timedelta(minutes=31))
    schreiber.fehler = None
    assert ausfuehren(steller, e, jetzt=JETZT + timedelta(minutes=31 + 59)) is False
    assert ausfuehren(steller, e, jetzt=JETZT + timedelta(minutes=31 + 61)) is True
    assert steller.stand.ablehnungen == 0


def test_erzwingen_uebergeht_die_sperre(s, regel):
    schreiber = Schreiber(RuntimeError("HTTP 409"))
    steller = s.Steller("/1/15/0", UML, schreiber)
    e = entscheidung(regel, regel.Aktion("zurueck", sicherheit=True))
    ausfuehren(steller, e)
    schreiber.fehler = None
    assert ausfuehren(steller, e, jetzt=JETZT + timedelta(minutes=1), erzwingen=True) is True


def test_sicherheit_schreibt_trotz_sperre(s, regel):
    schreiber = Schreiber(RuntimeError("HTTP 409"))
    steller = s.Steller("/1/15/0", UML, schreiber)
    ausfuehren(steller, entscheidung(regel, regel.Aktion("absenken", soll=19.5, minuten=60)))
    schreiber.fehler = None
    sicher = entscheidung(regel, regel.Aktion("absenkung_ende", sicherheit=True))
    assert ausfuehren(steller, sicher, jetzt=JETZT + timedelta(minutes=1)) is True
    assert schreiber.aufrufe == [("/1/15/0/2/10/0", "0")]


def test_abgelehnte_sicherheit_wartet_kurz_und_protokolliert_einmal(s, regel):
    """Dauerhaft abgelehnt: kurze feste Frist statt Schreiben in jedem Takt, ein Protokolleintrag."""
    schreiber = Schreiber(RuntimeError("HTTP 409"))
    steller = s.Steller("/1/15/0", UML, schreiber)
    sicher = entscheidung(regel, regel.Aktion("zurueck", sicherheit=True))
    ausfuehren(steller, sicher)
    schreiber.fehler = None
    assert ausfuehren(steller, sicher, jetzt=JETZT + timedelta(minutes=5)) is False
    assert schreiber.aufrufe == []
    schreiber.fehler = RuntimeError("HTTP 409")
    for minuten in (16, 32, 48):
        assert ausfuehren(steller, sicher, jetzt=JETZT + timedelta(minutes=minuten)) is False
    assert steller.stand.ablehnungen == 4
    assert [e["art"] for e in steller.stand.protokoll].count("abgelehnt") == 1
    schreiber.fehler = None
    assert ausfuehren(steller, sicher, jetzt=JETZT + timedelta(minutes=64)) is True


def test_andere_ablehnung_verdraengt_den_eintrag_nicht(s, regel):
    """Nur dieselbe Ablehnung ersetzt ihren Eintrag; eine andere kommt dazu."""
    schreiber = Schreiber(RuntimeError("HTTP 409"))
    steller = s.Steller("/1/15/0", UML, schreiber)
    ausfuehren(steller, entscheidung(regel, regel.Aktion("zurueck", sicherheit=True)))
    ausfuehren(
        steller,
        entscheidung(regel, regel.Aktion("absenkung_ende", sicherheit=True)),
        jetzt=JETZT + timedelta(minutes=20),
    )
    assert [e["art"] for e in steller.stand.protokoll].count("abgelehnt") == 2


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


@pytest.mark.parametrize(
    ("raumsoll", "erwartet"), [(18.0, "Absenkung von Hand geändert."), (17.2, None), (None, None)]
)
def test_handeingriff_am_raumsoll_der_pause(s, regel, raumsoll, erwartet):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    g = regel.Gedaechtnis(
        absenkung_art=regel.PAUSE,
        absenkung_von=JETZT,
        absenkung_bis=JETZT + timedelta(minutes=400),
        absenkung_soll=17.0,
    )
    spaeter = JETZT + timedelta(hours=1)
    kw = {"jetzt": spaeter, "betriebswahl": 1, "rest_min": 340, "betriebsart": 1}
    assert steller.handeingriff(g, raumsoll=raumsoll, **kw) == erwartet


def test_raumsoll_innerhalb_der_schonfrist_ist_kein_handeingriff(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    ausfuehren(steller, entscheidung(regel, regel.Aktion("pause", soll=17.0, minuten=400)))
    g = regel.Gedaechtnis(
        absenkung_art=regel.PAUSE,
        absenkung_von=JETZT,
        absenkung_bis=JETZT + timedelta(minutes=400),
        absenkung_soll=17.0,
    )
    kurz = JETZT + timedelta(minutes=1)
    kw = {"jetzt": kurz, "betriebswahl": 2, "rest_min": 399, "betriebsart": 1}
    assert steller.handeingriff(g, raumsoll=21.0, **kw) is None


def test_neuer_tag_setzt_das_budget_zurueck(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    absenken = regel.Aktion("absenken", soll=19.5, minuten=60)
    ausfuehren(steller, entscheidung(regel, absenken))
    morgen = JETZT + timedelta(days=1)
    ausfuehren(steller, entscheidung(regel, absenken), jetzt=morgen)
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


def test_unlesbare_zeiten_im_store_werden_verworfen(s):
    stand = s.Stand.aus_dict({"gesperrt_bis": "kaputt", "zuletzt": "auch kaputt"})
    assert stand.gesperrt_bis is None
    assert stand.zuletzt is None


def test_teilweise_angenommen_gilt_nicht_als_handeingriff(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww")))
    steller._schreiben = Schreiber(RuntimeError("abgelehnt"), ab=1)
    rueckkehr = entscheidung(
        regel,
        regel.Aktion("zurueck", sicherheit=True),
        regel.Aktion("absenkung_ende", sicherheit=True),
    )

    assert ausfuehren(steller, rueckkehr, betriebswahl=6) is False
    assert [a.art for a in steller.erledigt] == ["zurueck"]
    assert steller.stand.erwartet is None
    g = regel.nach_teilerfolg(regel.Gedaechtnis(saison=regel.NUR_WW), steller.erledigt, JETZT)
    assert g.saison == regel.HEIZEN
    spaeter = JETZT + timedelta(minutes=10)
    assert (
        steller.handeingriff(g, jetzt=spaeter, betriebswahl=1, rest_min=None, betriebsart=1) is None
    )


def test_beendete_absenkung_bleibt_beendet_wenn_nur_ww_scheitert(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber(RuntimeError("abgelehnt"), ab=1))
    g = regel.Gedaechtnis(absenkung_art=regel.SONNE, absenkung_bis=JETZT + timedelta(hours=3))
    wechsel = entscheidung(regel, regel.Aktion("absenkung_ende"), regel.Aktion("nur_ww"))

    assert ausfuehren(steller, wechsel) is False
    neu = regel.nach_teilerfolg(g, steller.erledigt, JETZT)
    assert not regel.absenkung_laeuft(neu, JETZT)
    assert neu.saison == regel.HEIZEN


def test_beobachten_vergisst_den_letzten_teilerfolg(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber(RuntimeError("abgelehnt"), ab=1))
    ausfuehren(steller, entscheidung(regel, regel.Aktion("absenkung_ende"), regel.Aktion("nur_ww")))
    ausfuehren(steller, entscheidung(regel, regel.Aktion("nur_ww")), beobachten=True)
    assert steller.erledigt == ()


def test_pause_schreibt_wie_eine_absenkung(s, regel):
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", UML, schreiber)
    assert ausfuehren(steller, entscheidung(regel, regel.Aktion("pause", soll=16.0, minuten=400)))
    assert schreiber.aufrufe == [("/1/15/0/3/4/0", "16.0"), ("/1/15/0/2/10/0", "400")]
    assert steller.stand.eingriffe == 1
    assert steller.stand.protokoll[0]["aktionen"] == ["pause"]


def test_erneuern_zaehlt_nicht_gegen_das_budget(s, regel):
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", UML, schreiber)
    erneuern = regel.Aktion("pause", soll=16.0, minuten=400, erneuern=True)
    assert ausfuehren(steller, entscheidung(regel, erneuern), budget=0)
    assert steller.stand.eingriffe == 0
    assert len(schreiber.aufrufe) == 2


def test_zurueck_und_pause_erwarten_die_wahl_nach_der_rueckkehr(s, regel):
    schreiber = Schreiber()
    stand = s.Stand(betriebswahl_vorher=1, erwartet=6)
    steller = s.Steller("/1/15/0", UML, schreiber, stand)
    wechsel = entscheidung(
        regel, regel.Aktion("zurueck"), regel.Aktion("pause", soll=16.0, minuten=400)
    )
    assert ausfuehren(steller, wechsel, betriebswahl=6)
    assert schreiber.aufrufe == [
        ("/1/15/0/3/50/0", "1"),
        ("/1/15/0/3/4/0", "16.0"),
        ("/1/15/0/2/10/0", "400"),
    ]
    assert steller.stand.erwartet == 1


@pytest.mark.parametrize("mit_zurueck", [False, True])
def test_empfehlen_schreibt_eine_absenkung_nicht(s, regel, mit_zurueck):
    schreiber = Schreiber()
    stand = s.Stand(betriebswahl_vorher=1, erwartet=6) if mit_zurueck else s.Stand()
    steller = s.Steller("/1/15/0", UML, schreiber, stand)
    aktionen = [regel.Aktion("zurueck")] if mit_zurueck else []
    e = entscheidung(regel, *aktionen, regel.Aktion("pause", soll=16.0, minuten=400))
    assert ausfuehren(steller, e, empfehlen=True, betriebswahl=6 if mit_zurueck else 2) is False
    assert schreiber.aufrufe == []
    assert steller.empfohlen is True
    assert steller.stand.protokoll[0]["art"] == "empfohlen"
    assert steller.stand.eingriffe == 0


def test_empfehlen_vermerkt_dieselbe_empfehlung_nur_einmal(s, regel):
    steller = s.Steller("/1/15/0", UML, Schreiber())
    e = entscheidung(regel, regel.Aktion("nur_ww"))
    ausfuehren(steller, e, empfehlen=True)
    ausfuehren(steller, e, empfehlen=True)
    assert [x["art"] for x in steller.stand.protokoll].count("empfohlen") == 1


@pytest.mark.parametrize(
    "aktion",
    [
        ("zurueck", {}),
        ("absenkung_ende", {}),
        ("pause", {"soll": 16.0, "minuten": 400, "erneuern": True}),
        ("nur_ww", {"sicherheit": True}),
    ],
)
def test_empfehlen_schreibt_rueckkehr_erneuern_und_sicherheit(s, regel, aktion):
    art, felder = aktion
    schreiber = Schreiber()
    steller = s.Steller("/1/15/0", UML, schreiber, s.Stand(betriebswahl_vorher=1))
    assert ausfuehren(steller, entscheidung(regel, regel.Aktion(art, **felder)), empfehlen=True)
    assert schreiber.aufrufe
    assert steller.empfohlen is False
