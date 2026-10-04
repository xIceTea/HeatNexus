"""Jede bekannte Anlage durch Erkennung, Metadaten und ersten Abruf.

Die Testanlagen in `daten/anlagen/` stammen von PuroWIN, UML, BioWIN älterer
und neuerer Firmware, InfoWIN Touch v2 und DuoWIN. Geprüft werden Regeln, die
an jeder Anlage gelten müssen – nicht einzelne Werte.
"""

from __future__ import annotations

import json
import re

import pytest

from .anlagenkatalog import HOST, Nachspiel, anlagen
from .conftest import requires_ha

pytestmark = requires_ha()

UMFAENGE = {
    "betreiber": {"levels": ["info", "operate"]},
    "alles": {
        "levels": ["info", "operate", "service", "oem"],
        "enable_advanced": True,
        "writable_advanced": True,
    },
}
FAELLE = [(a, u) for a in anlagen() for u in UMFAENGE]
_ERGEBNISSE: dict[tuple[str, str], dict] = {}


async def _lauf(anlage: str, umfang: str) -> dict:
    """Einmal je Anlage und Umfang: Erkennung, Vollabzug, erster Abruf."""
    if (anlage, umfang) in _ERGEBNISSE:
        return _ERGEBNISSE[(anlage, umfang)]
    from custom_components.heatnexus.client import WindhagerHttpClient

    client = WindhagerHttpClient(HOST, "x", **UMFAENGE[umfang])
    spiel = Nachspiel(anlage)
    spiel.einsetzen(client)
    await client.async_init_basic()
    await client.async_init()
    daten = await client.fetch_all()
    ergebnis = {
        "devices": json.loads(json.dumps(client.devices, default=str)),
        "daten": daten,
        "spiel": spiel,
        "poll": set(client.poll_oids),
    }
    _ERGEBNISSE[(anlage, umfang)] = ergebnis
    return ergebnis


def _zulaessig(meta: dict | None) -> list[int]:
    roh = (meta or {}).get("enum")
    if isinstance(roh, str):
        try:
            roh = json.loads(roh)
        except ValueError:
            return []
    return [int(w) for w in roh] if isinstance(roh, list) else []


def _mit_oid(devices):
    return [d for d in devices if d.get("oid")]


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_die_anlage_wird_erkannt(anlage, umfang):
    erg = await _lauf(anlage, umfang)
    assert erg["devices"], "keine einzige Beschreibung"
    freigegeben = {
        f"/1/{k['nodeId']}/{f['fctId']}"
        for k in erg["spiel"].daten["struktur"]
        for f in k.get("functions") or []
        if not f.get("lock")
        and f.get("fctType", -1) >= 0
        and erg["spiel"].funktionen.get(f"/1/{k['nodeId']}/{f['fctId']}", {}).get("datapoints")
    }
    mit_beschreibung = {d.get("prefix") for d in erg["devices"]} | {
        "/".join(d["oid"].split("/")[:4]) for d in _mit_oid(erg["devices"])
    }
    assert freigegeben <= mit_beschreibung, sorted(freigegeben - mit_beschreibung)


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_kennungen_sind_eindeutig_und_haengen_an_der_seriennummer(anlage, umfang):
    erg = await _lauf(anlage, umfang)
    kennungen = [d["id"] for d in erg["devices"]]
    doppelt = sorted({k for k in kennungen if kennungen.count(k) > 1})
    assert not doppelt, doppelt
    assert all(re.match(r"^KAT\d\dN\d{3}-", k) for k in kennungen), [
        k for k in kennungen if not re.match(r"^KAT\d\dN\d{3}-", k)
    ][:5]


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_jeder_gemeldete_auswahlwert_hat_einen_text(anlage, umfang):
    from custom_components.heatnexus.helpers import enum_texte

    erg = await _lauf(anlage, umfang)
    fehlend = []
    for d in erg["devices"]:
        if d.get("type") not in ("select", "enum_sensor") or not d.get("allowed"):
            continue
        texte = enum_texte(d)
        if not texte:
            continue
        # Eine Anzeige meldet oft einen Wertebereich; über dem höchsten Eintrag liegt Reserve.
        grenze = max(texte) if d["type"] == "enum_sensor" else max(d["allowed"])
        fehlend += [
            f"{d['oid']} {d['name']}: {w}" for w in d["allowed"] if w not in texte and w <= grenze
        ]
    assert not fehlend, fehlend


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_auswahltexte_sind_eindeutig(anlage, umfang):
    from custom_components.heatnexus.helpers import enum_texte

    erg = await _lauf(anlage, umfang)
    doppelt = []
    for d in erg["devices"]:
        if d.get("type") != "select":
            continue
        texte = enum_texte(d)
        werte = d.get("allowed") or sorted(texte)
        namen = [texte.get(w) for w in werte if w in texte]
        doppelt += [f"{d['oid']} {d['name']}: {n}" for n in set(namen) if namen.count(n) > 1]
    assert not doppelt, doppelt


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_geschriebene_werte_bietet_das_geraet_an(anlage, umfang):
    erg = await _lauf(anlage, umfang)
    falsch = []
    for d in _mit_oid(erg["devices"]):
        erlaubt = _zulaessig(erg["spiel"].metadaten(d["oid"]))
        if not erlaubt:
            continue
        if d.get("type") == "switch":
            werte = [d.get("ein_wert") or "1", d.get("aus_wert") or "0"]
        elif d.get("type") == "button" and d.get("press_value") is not None:
            werte = [d["press_value"]]
        else:
            continue
        falsch += [f"{d['oid']} {d['name']}: {w}" for w in werte if int(w) not in erlaubt]
    assert not falsch, falsch


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_zahlenfelder_haben_gueltige_grenzen(anlage, umfang):
    erg = await _lauf(anlage, umfang)
    falsch = []
    for d in erg["devices"]:
        if d.get("type") != "number":
            continue
        lo, hi, step = d.get("min"), d.get("max"), d.get("step")
        if lo is not None and hi is not None and float(lo) >= float(hi):
            falsch.append(f"{d['oid']} {d['name']}: {lo}..{hi}")
        if step is not None and float(step) <= 0:
            falsch.append(f"{d['oid']} {d['name']}: Schritt {step}")
    assert not falsch, falsch


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_keine_beschreibung_fuer_fehlende_datenpunkte(anlage, umfang):
    erg = await _lauf(anlage, umfang)
    spiel = erg["spiel"]
    fehlend = [
        f"{d['oid']} {d['name']}"
        for d in _mit_oid(erg["devices"])
        if d.get("type") != "time_program"
        and spiel.metadaten(d["oid"]) is None
        and d["oid"] not in spiel.daten["objekte"]
    ]
    assert not fehlend, fehlend


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_der_abruf_fragt_nur_bekannte_adressen(anlage, umfang):
    erg = await _lauf(anlage, umfang)
    bekannt = {d["oid"] for d in _mit_oid(erg["devices"])}
    fremd = sorted(o for o in erg["poll"] if o not in bekannt and "/0/" not in o[-4:])
    assert erg["daten"]["devices"]
    assert isinstance(erg["daten"]["oids"], dict)
    assert not [o for o in fremd if erg["spiel"].metadaten(o) is None], fremd[:10]
