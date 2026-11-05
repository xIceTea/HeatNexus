"""Jede Testanlage auf Englisch und Niederländisch: kein Name, kein Zustand ohne Übersetzung.

Erkannt wird mit allen Ebenen, ohne Textwerk der Steuerung. So zeigt sich, was
eine Anlage ohne eigene Textdateien anzeigt; dort greifen nur die Tabellen.
"""

from __future__ import annotations

import json

import pytest

from .anlagenkatalog import HOST, Nachspiel, anlagen
from .conftest import requires_ha

pytestmark = requires_ha()

SPRACHEN = ("en", "nl")
ALLES = {
    "levels": ["info", "operate", "service", "oem"],
    "enable_advanced": True,
    "writable_advanced": True,
}
_ERGEBNISSE: dict[tuple[str, str], list[dict]] = {}


async def _beschreibungen(anlage: str, sprache: str) -> list[dict]:
    """Einmal je Anlage und Sprache erkennen."""
    if (anlage, sprache) not in _ERGEBNISSE:
        from custom_components.heatnexus.client import WindhagerHttpClient

        client = WindhagerHttpClient(HOST, "x", sprache=sprache, **ALLES)
        Nachspiel(anlage).einsetzen(client)
        await client.async_init_basic()
        await client.async_init()
        _ERGEBNISSE[(anlage, sprache)] = json.loads(json.dumps(client.devices, default=str))
    return _ERGEBNISSE[(anlage, sprache)]


def _datenpunkte(beschreibungen: list[dict]):
    """Beschreibungen mit Datenpunktadresse, dazu `gn/mn`."""
    for d in beschreibungen:
        oid = d.get("oid") or ""
        if oid.startswith("/1/"):
            yield "/".join(oid.split("/")[4:6]), d


@pytest.mark.parametrize("sprache", SPRACHEN)
@pytest.mark.parametrize("anlage", anlagen())
async def test_jeder_angezeigte_name_hat_eine_fassung_in_der_sprache(anlage, sprache):
    from custom_components.heatnexus import texte
    from custom_components.heatnexus.device_db import get_name

    def rueckfall(gnmn: str, d: dict) -> bool:
        """Deutsch geblieben oder auf Englisch zurückgefallen, ohne Eintrag der Sprache."""
        if get_name(gnmn, sprache) or texte.eigene_fassung(sprache, d.get("name_de") or ""):
            return False
        return d["name"] in (d.get("name_de"), get_name(gnmn, "en"))

    fehlt = sorted(
        {
            f"{gnmn} {d.get('name_de')}"
            for gnmn, d in _datenpunkte(await _beschreibungen(anlage, sprache))
            if rueckfall(gnmn, d)
        }
    )
    assert fehlt == [], (
        "Übersetzung in tools/datenpunktnamen.json ergänzen, Generator laufen lassen"
    )


@pytest.mark.parametrize("sprache", SPRACHEN)
@pytest.mark.parametrize("anlage", anlagen())
async def test_jeder_angezeigte_zustand_hat_einen_text_in_der_sprache(anlage, sprache):
    from custom_components.heatnexus.const import ENUMS
    from custom_components.heatnexus.device_db import get_enum

    fehlt = []
    for gnmn, d in _datenpunkte(await _beschreibungen(anlage, sprache)):
        if not (schluessel := d.get("enum")):
            continue
        deutsch = ENUMS.get(schluessel) or get_enum(schluessel) or {}
        fremd = {int(w) for w in d.get("enum_texte") or {}}
        fehlt += [f"{gnmn}={wert}" for wert in sorted(set(deutsch) - fremd)]
    assert fehlt == []
