"""Panel, Schaubild und Dashboard jeder Testanlage gegen einen gespeicherten Stand.

Ein Werkzeug für Umbauten ohne Verhaltensänderung, kein Teil der Suite: Es läuft
nur mit `SCHNAPPSCHUSS_ORDNER`. Der erste Lauf schreibt den Stand, jeder weitere vergleicht.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

import pytest

from .anlagenkatalog import anlagen
from .conftest import requires_frontend, requires_ha, requires_moderne_ha
from .test_anlagenkatalog_ha import _abbauen, _einrichten

ORDNER = os.environ.get("SCHNAPPSCHUSS_ORDNER")

pytestmark = [
    requires_ha(),
    requires_frontend(),
    requires_moderne_ha(),
    pytest.mark.skipif(not ORDNER, reason="nur mit SCHNAPPSCHUSS_ORDNER"),
]


@pytest.fixture(autouse=True)
def _eigene_integration(enable_custom_integrations):
    """Die Testumgebung lädt eigene Integrationen nur auf ausdrücklichen Wunsch."""
    return enable_custom_integrations


def _kennungen_ersetzen(hass, eintrag, text: str) -> str:
    """Zufällige Kennungen von Registry und Eintrag durch feste Namen ersetzen."""
    from homeassistant.helpers import device_registry as dr

    geraete = dr.async_entries_for_config_entry(dr.async_get(hass), eintrag.entry_id)
    for geraet in geraete:
        fest = "-".join(sorted(w for _, w in geraet.identifiers))
        text = text.replace(geraet.id, f"geraet:{fest}")
    text = text.replace(eintrag.entry_id, "eintrag")
    # Ansichtspfade tragen einen Streuwert der Gerätekennung; sie werden durchnummeriert.
    pfade: dict[str, str] = {}

    def _pfad(treffer: re.Match) -> str:
        return pfade.setdefault(treffer.group(0), f"{treffer.group(1)}-{len(pfade)}")

    return re.sub(r"\b(anlage|teil)-[0-9a-f]{8}\b", _pfad, text)


def _ausgabe(hass) -> dict:
    from custom_components.heatnexus.dashboard import dashboard_konfiguration
    from custom_components.heatnexus.karte import kartendaten
    from custom_components.heatnexus.panel import panel_daten

    return {
        "panel": panel_daten(hass),
        "karte": kartendaten(hass),
        "dashboard_bild": dashboard_konfiguration(hass, als_karte=False),
        "dashboard_karte": dashboard_konfiguration(hass, als_karte=True),
    }


@pytest.mark.parametrize("anlage", anlagen())
async def test_die_ausgabe_bleibt_gleich(hass, anlage):
    eintrag = await _einrichten(hass, anlage, "alles")
    try:
        roh = json.dumps(_ausgabe(hass), ensure_ascii=False, indent=1, sort_keys=True)
        text = _kennungen_ersetzen(hass, eintrag, roh)
    finally:
        await _abbauen(hass, eintrag)
    datei = Path(ORDNER) / f"{anlage}.json"
    if not datei.exists():
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(text + "\n", encoding="utf-8", newline="\n")
        pytest.skip("Schnappschuss neu geschrieben")
    gespeichert = datei.read_text(encoding="utf-8").rstrip("\n")
    if text != gespeichert:
        datei.with_suffix(".abweichung").write_text(text + "\n", encoding="utf-8", newline="\n")
    assert text == gespeichert, f"Ausgabe von {anlage} weicht vom Schnappschuss ab"
