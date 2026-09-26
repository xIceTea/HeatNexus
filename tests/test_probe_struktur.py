"""Das Probe-Werkzeug beim ersten Kontakt mit der Anlage.

Die Sonde muss dieselbe Steuerung erreichen wie die Integration und klar
sagen, wenn unter der Adresse etwas anderes antwortet.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import urllib.request

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_sonde_umgeht_den_proxy_des_systems(probe_modul, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("http_proxy", "http://proxy.invalid:3128")
    probe = probe_modul.Probe("192.0.2.10", "geheim", 1)

    proxies = [
        h.proxies for h in probe.opener.handlers if isinstance(h, urllib.request.ProxyHandler)
    ]

    assert not any(proxies)


def test_falsches_passwort_nennt_das_passwort(probe_modul):
    assert "Passwort" in probe_modul.struktur_hinweis(401, {"raw": ""})


def test_404_nennt_fremden_webserver(probe_modul):
    seite = "<html><head><title>FRITZ!Box</title></head><body>…</body></html>"

    hinweis = probe_modul.struktur_hinweis(404, {"raw": seite})

    assert "keine Windhager-Steuerung" in hinweis
    assert "FRITZ!Box" in hinweis


def test_404_ohne_seitentitel_zeigt_textanfang(probe_modul):
    hinweis = probe_modul.struktur_hinweis(404, {"raw": "<h1>Not Found</h1><p>nginx</p>"})

    assert "Not Found nginx" in hinweis


def test_fremde_antwort_ohne_json_nennt_fremden_webserver(probe_modul):
    assert "keine Windhager-Steuerung" in probe_modul.struktur_hinweis(400, {"raw": ""})


def test_fremde_json_antwort_zeigt_ihren_text(probe_modul):
    antwort = {"errors": [{"message": "unknown endpoint"}]}

    hinweis = probe_modul.struktur_hinweis(400, antwort)

    assert "keine Windhager-Steuerung" in hinweis
    assert "unknown endpoint" in hinweis


def test_verbindungsfehler_nennt_die_ursache(probe_modul):
    assert "timed out" in probe_modul.struktur_hinweis(0, {"error": "timed out"})
