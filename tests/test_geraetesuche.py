"""Geräte sucht nur `registrierung.py`.

Home Assistant 2026.9 warnt bei der Suche über die Kennung allein; die Weiche
dafür steht an einer Stelle und sonst nirgends.
"""

from __future__ import annotations

from pathlib import Path

PAKET = Path(__file__).parent.parent / "custom_components" / "heatnexus"


def test_nur_registrierung_sucht_geraete_ueber_die_kennung():
    """Jede andere Stelle nimmt `registrierung.geraet_suchen`."""
    fundstellen = [
        f"{datei.relative_to(PAKET)}:{nummer}"
        for datei in PAKET.rglob("*.py")
        if datei.name != "registrierung.py"
        for nummer, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1)
        if "async_get_device(" in zeile
    ]
    assert not fundstellen, fundstellen
