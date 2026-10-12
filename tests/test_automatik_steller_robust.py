"""Steller der Automatik: halb geschriebene Eingriffe und unlesbare Zeiten aus dem Store."""

from __future__ import annotations

import asyncio

import pytest

from .conftest import load_standalone
from .test_automatik_steller import JETZT, UML

PREFIX = "/1/15/0"
TEMPERATUR = f"{PREFIX}/3/4/0"
DAUER = f"{PREFIX}/2/10/0"


@pytest.fixture(scope="module")
def regel():
    load_standalone("automatik")
    load_standalone("automatik.profile")
    return load_standalone("automatik.regel")


@pytest.fixture(scope="module")
def s(regel):
    return load_standalone("automatik.steller")


class Steuerung:
    def __init__(self, *ablehnen: str) -> None:
        """Nimmt alles an außer den Adressen in `ablehnen`."""
        self.ablehnen = set(ablehnen)
        self.aufrufe: list[tuple[str, str]] = []

    async def __call__(self, oid: str, wert: str) -> None:
        if oid in self.ablehnen:
            raise RuntimeError("abgelehnt")
        self.aufrufe.append((oid, wert))


def _pause(regel, soll: float = 17.5):
    aktion = regel.Aktion("pause", soll=soll, minuten=400, erneuern=True)
    return regel.Entscheidung(regel.Zustand.HEIZPAUSE, (aktion,), "Grund.", regel.Gedaechtnis())


def _ausfuehren(steller, e, **kw):
    felder = {"jetzt": JETZT, "betriebswahl": 1, "budget": 4, "beobachten": False}
    return asyncio.run(steller.ausfuehren(e, **(felder | kw)))


def test_zeiten_ohne_zone_aus_dem_store_entfallen(s, regel):
    """Ein naiver Zeitpunkt ließe jeden Vergleich mit `jetzt` scheitern."""
    stand = s.Stand.aus_dict(
        {
            "zuletzt": "2026-09-27T06:58:00",
            "gesperrt_bis": "2026-09-27T08:00:00",
            "protokoll": [
                {"zeit": "2026-09-27T06:50:00", "art": "abgelehnt", "sicherheit": True},
                {"zeit": JETZT.isoformat(), "art": "geschrieben", "text": ""},
                {"art": "geprueft"},
            ],
        }
    )

    assert stand.zuletzt is None
    assert stand.gesperrt_bis is None
    assert [e["art"] for e in stand.protokoll] == ["geschrieben"]
    steller = s.Steller(PREFIX, UML, Steuerung(), stand)
    aktion = regel.Aktion("absenkung_ende", sicherheit=True)
    e = regel.Entscheidung(regel.Zustand.SICHERHEIT, (aktion,), "", regel.Gedaechtnis())
    assert _ausfuehren(steller, e) is True
    assert (
        steller.handeingriff(
            regel.Gedaechtnis(), jetzt=JETZT, betriebswahl=1, rest_min=0, betriebsart=1
        )
        is None
    )
