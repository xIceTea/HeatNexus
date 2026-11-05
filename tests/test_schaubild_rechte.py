"""Das Schaubild liest mit den Rechten des fragenden Benutzers."""

from __future__ import annotations

from types import SimpleNamespace

from .conftest import requires_ha

pytestmark = requires_ha()


def test_das_schaubild_liest_mit_den_rechten_des_benutzers(monkeypatch):
    from custom_components.heatnexus import karte

    gelesen: list = []

    def lesen(hass, benutzer=None):
        gelesen.append(benutzer)
        return []

    monkeypatch.setattr(karte, "anlagen_lesen", lesen)
    monkeypatch.setattr(karte, "woerterbuch", lambda hass: None)
    verbindung = SimpleNamespace(user="benutzer", send_result=lambda *_a: None)

    karte._ws_schaubild(None, verbindung, {"id": 1})

    assert gelesen == ["benutzer"]
