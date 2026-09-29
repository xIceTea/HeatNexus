"""Geräte sucht nur `registrierung.py`.

Home Assistant 2026.9 warnt bei der Suche über die Kennung allein; die Weiche
dafür steht an einer Stelle und sonst nirgends.
"""

from __future__ import annotations

from pathlib import Path

from .conftest import requires_ha

PAKET = Path(__file__).parent.parent / "custom_components" / "heatnexus"
TESTS = Path(__file__).parent


def test_nur_registrierung_sucht_geraete_ueber_die_kennung():
    """Jede andere Stelle nimmt `registrierung.geraet_suchen`, auch in den Tests."""
    fundstellen = [
        f"{datei.name}:{nummer}"
        for datei in [*PAKET.rglob("*.py"), *TESTS.rglob("test_*.py")]
        if datei.name not in ("registrierung.py", "test_geraetesuche.py")
        for nummer, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1)
        if "async_get_device(" in zeile
    ]
    assert not fundstellen, fundstellen


class _Register:
    """Merkt sich die Aufrufe; die Schnittstelle legt der Test fest."""

    def __init__(self):
        self.aufrufe = []

    def async_update_device(self, geraet_id, **felder):
        self.aufrufe.append(("update", geraet_id, felder))

    def async_get_or_create(self, **felder):
        self.aufrufe.append(("anlegen", felder["config_subentry_id"]))


@requires_ha()
def test_verschieben_nutzt_das_ziel_wo_es_das_gibt(monkeypatch):
    from types import SimpleNamespace

    from custom_components.heatnexus import registrierung

    geraet = SimpleNamespace(id="g1", identifiers={("heatnexus", "x-automatik")})
    neu, alt = _Register(), _Register()
    monkeypatch.setattr(registrierung, "VERSCHIEBEN_PER_ZIEL", True)
    registrierung.in_untereintrag_verschieben(neu, geraet, "e1", "s1")
    monkeypatch.setattr(registrierung, "VERSCHIEBEN_PER_ZIEL", False)
    registrierung.in_untereintrag_verschieben(alt, geraet, "e1", "s1")

    assert neu.aufrufe == [
        ("update", "g1", {"new_config_entry_id": "e1", "new_config_subentry_id": "s1"})
    ]
    assert alt.aufrufe[0] == ("anlegen", "s1")
    assert alt.aufrufe[1][2]["remove_config_subentry_id"] is None
