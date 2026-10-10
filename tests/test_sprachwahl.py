"""Gemeinsame Sprache und Sprache je Anlage.

Die gemeinsame Wahl gilt für alle Einträge, eine eigene Wahl nur für ihren.
Die Umstellung alter Einträge darf keine Anlage umbenennen.
"""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def texte():
    """Das Modul kommt ohne Home Assistant aus."""
    return load_standalone("texte")


class _Eintrag:
    """Ein Konfigurationseintrag, so weit die Sprachwahl ihn braucht."""

    def __init__(self, optionen, entry_id="eintrag"):
        self.options = optionen
        self.entry_id = entry_id


class _Hass:
    """Home Assistant, so weit die Sprachwahl es braucht."""

    def __init__(self, sprache, eintraege):
        self.config = type("Konfig", (), {"language": sprache})()

        def holen(kennung):
            return next((e for e in eintraege if e.entry_id == kennung), None)

        self.config_entries = type(
            "Eintraege",
            (),
            {
                "async_entries": staticmethod(lambda _domain: eintraege),
                "async_get_entry": staticmethod(holen),
            },
        )()


@pytest.mark.parametrize(
    ("gemeinsam", "eigene", "ha", "erwartet"),
    [
        ("de", None, "en", "de"),
        ("de", "wie_heatnexus", "en", "de"),
        ("de", "nl", "en", "nl"),
        ("en", None, "de", "en"),
        ("nl", "en", "de", "en"),
        ("auto", None, "nl", "nl"),
        ("auto", "wie_heatnexus", "en-GB", "en"),
        ("auto", "de", "nl", "de"),
        ("auto", None, "de-CH", "de"),
        # Was HeatNexus nicht führt, erscheint englisch.
        ("auto", None, "fr", "en"),
        ("auto", None, None, "de"),
        ("it", None, "de", "en"),
    ],
)
def test_wirksame_sprache_eines_eintrags(texte, gemeinsam, eigene, ha, erwartet):
    """Die eigene Wahl sticht die gemeinsame; „Automatisch“ folgt Home Assistant."""
    optionen = {"sprache": gemeinsam}
    if eigene is not None:
        optionen["sprache_anlage"] = eigene
    eintrag = _Eintrag(optionen, "b")
    hass = _Hass(ha, [_Eintrag({"sprache": gemeinsam}, "a"), eintrag])

    assert texte.sprache_des_eintrags(hass, eintrag) == erwartet
    assert texte.woerterbuch_des_eintrags(hass, eintrag).sprache == erwartet
    assert texte.woerterbuch_des_eintrags(hass, "b").sprache == erwartet


def test_eine_eigene_sprache_aendert_die_gemeinsame_nicht(texte):
    """Rahmen und Ansicht „Alle“ bleiben in der gemeinsamen Sprache."""
    hass = _Hass(
        "en",
        [
            _Eintrag({"sprache": "de", "sprache_anlage": "nl"}, "a"),
            _Eintrag({"sprache": "de"}, "b"),
        ],
    )

    assert texte.gemeinsame_sprache(hass) == "de"
    assert texte.sprache_der_oberflaeche(hass) == "de"
    assert texte.woerterbuch(hass).sprache == "de"


def test_ein_unbekannter_eintrag_spricht_die_gemeinsame_sprache(texte):
    hass = _Hass("en", [_Eintrag({"sprache": "nl"}, "a")])

    assert texte.woerterbuch_des_eintrags(hass, "weg").sprache == "nl"
    assert texte.woerterbuch_des_eintrags(hass, None).sprache == "nl"


def test_ein_neuer_eintrag_ohne_wahl_folgt_der_gemeinsamen(texte):
    """Die gemeinsame Wahl steht im ersten Eintrag, der eine trägt."""
    neu = _Eintrag({}, "b")
    hass = _Hass("en", [_Eintrag({"sprache": "nl"}, "a"), neu])

    assert texte.sprache_des_eintrags(hass, neu) == "nl"


def test_attrappe_statt_home_assistant_bleibt_deutsch(texte):
    """Nur echte Zeichenketten zählen als Wahl; eine Attrappe ergibt keine fremde Sprache."""
    from unittest.mock import MagicMock

    assert texte.sprache_des_eintrags(MagicMock(), MagicMock()) == "de"


# ---------------------------------------------------------------------------
# Umstellung bestehender Einträge
# ---------------------------------------------------------------------------
def _angewandt(alt, neu):
    """Die Optionen nach der Umstellung; `None` heißt unverändert."""
    return [n if n is not None else dict(a) for a, n in zip(alt, neu, strict=True)]


def test_umstellung_macht_die_erste_wahl_gemeinsam(texte):
    alt = [
        {"sprache": "de", "intervall": 30},
        {"sprache": "nl", "intervall": 60},
        {"sprache": "en"},
    ]

    neu = texte.sprachwahl_umstellen(alt)

    assert neu[0] is None
    assert neu[1] == {"sprache": "de", "sprache_anlage": "nl", "intervall": 60}
    assert neu[2] == {"sprache": "de", "sprache_anlage": "en"}
    assert alt[1] == {"sprache": "nl", "intervall": 60}


def test_umstellung_benennt_keine_anlage_um(texte):
    """Jeder Eintrag spricht danach dieselbe Sprache wie vorher."""
    alt = [{"sprache": "de"}, {"sprache": "nl"}, {"sprache": "en"}]
    neu = _angewandt(alt, texte.sprachwahl_umstellen(alt))
    eintraege = [_Eintrag(o, f"e{i}") for i, o in enumerate(neu)]
    hass = _Hass("fr", eintraege)

    assert [texte.sprache_des_eintrags(hass, e) for e in eintraege] == ["de", "nl", "en"]
    assert texte.gemeinsame_sprache(hass) == "de"


def test_umstellung_laeuft_nur_einmal(texte):
    alt = [{"sprache": "de"}, {"sprache": "nl"}]
    neu = _angewandt(alt, texte.sprachwahl_umstellen(alt))

    assert texte.sprachwahl_umstellen(neu) is None
    assert texte.sprachwahl_umstellen([]) is None


def test_gleiche_wahl_bleibt_unberuehrt(texte):
    """Wo die gemeinsame Sprache dasselbe bedeutet, bekommt nur der erste Eintrag die Marke."""
    assert texte.sprachwahl_umstellen([{"sprache": "de"}, {"sprache": "de"}, {}]) == [
        {"sprache": "de", "sprache_anlage": "wie_heatnexus"},
        None,
        None,
    ]


def test_umstellung_ohne_wahl_bleibt_automatisch(texte):
    """Ein Eintrag ohne Wahl folgt danach der gemeinsamen Sprache."""
    alt = [{}, {"sprache": "de"}, {"sprache": "auto"}]

    neu = texte.sprachwahl_umstellen(alt)

    assert neu == [None, {"sprache": "auto", "sprache_anlage": "de"}, None]
    eintraege = [_Eintrag(o, f"e{i}") for i, o in enumerate(_angewandt(alt, neu))]
    hass = _Hass("nl", eintraege)
    assert [texte.sprache_des_eintrags(hass, e) for e in eintraege] == ["nl", "de", "nl"]


def test_umstellung_einer_entfallenen_sprache(texte):
    """Französisch und Italienisch lasen die Steuerung schon bisher englisch."""
    alt = [{"sprache": "fr"}, {"sprache": "it"}, {"sprache": "de"}]

    neu = texte.sprachwahl_umstellen(alt)

    assert neu == [None, None, {"sprache": "en", "sprache_anlage": "de"}]
    eintraege = [_Eintrag(o, f"e{i}") for i, o in enumerate(_angewandt(alt, neu))]
    hass = _Hass("de", eintraege)
    assert [texte.sprache_des_eintrags(hass, e) for e in eintraege] == ["en", "en", "de"]


@pytest.mark.parametrize(
    ("ha", "alt", "erwartet"),
    [
        ("en", [{}], [{"sprache": "auto", "sprache_anlage": "de"}]),
        ("en", [{"sprache": "auto"}], [{"sprache": "auto", "sprache_anlage": "de"}]),
        (
            "en-GB",
            [{}, {"sprache": "en"}],
            [
                {"sprache": "auto", "sprache_anlage": "de"},
                {"sprache": "auto", "sprache_anlage": "en"},
            ],
        ),
        ("de", [{}], [{"sprache": "auto", "sprache_anlage": "wie_heatnexus"}]),
        (
            "de",
            [{}, {"sprache": "auto"}],
            [{"sprache": "auto", "sprache_anlage": "wie_heatnexus"}, None],
        ),
        (
            "nl",
            [{"sprache": "nl"}, {"sprache": "auto"}],
            [None, {"sprache": "nl", "sprache_anlage": "de"}],
        ),
        ("nl", [{"sprache": "nl"}, {}], [None, {"sprache": "nl", "sprache_anlage": "de"}]),
        (None, [{"sprache": "en"}, {}], [None, {"sprache": "en", "sprache_anlage": "de"}]),
    ],
)
def test_umstellung_haelt_deutsch_ohne_wahl(texte, ha, alt, erwartet):
    """Ohne Wahl waren die Namen deutsch, unabhängig von der Sprache von Home Assistant."""
    assert texte.sprachwahl_umstellen(alt, ha) == erwartet


@pytest.mark.parametrize("ha", ["de", "en", "nl", "fr", None])
@pytest.mark.parametrize(
    "alt",
    [
        [{}, {"sprache": "auto"}, {"sprache": "de"}],
        [{"sprache": "auto"}, {"sprache": "nl"}, {}],
        [{"sprache": "en"}, {}, {"sprache": "fr"}, {"sprache": "nl"}],
        [{"sprache": "it"}, {"sprache": "auto"}, {"sprache": "de"}],
    ],
)
def test_umstellung_haelt_jede_wirksame_sprache(texte, ha, alt):
    """Jeder Eintrag spricht nach der Umstellung wie vorher, gleich welche Sprache Home Assistant hat."""
    vorher = [
        {"de": "de", "en": "en", "nl": "nl", "fr": "en", "it": "en"}.get(o.get("sprache"), "de")
        for o in alt
    ]
    neu = texte.sprachwahl_umstellen(alt, ha)
    eintraege = [_Eintrag(o, f"e{i}") for i, o in enumerate(_angewandt(alt, neu))]
    hass = _Hass(ha, eintraege)

    assert [texte.sprache_des_eintrags(hass, e) for e in eintraege] == vorher
    assert texte.sprachwahl_umstellen(_angewandt(alt, neu), ha) is None


def test_umstellung_mit_ha_sprache_laeuft_nur_einmal(texte):
    umgestellt = [{"sprache": "auto", "sprache_anlage": "de"}, {}]

    assert texte.sprachwahl_umstellen(umgestellt, "en") is None


def test_umstellung_ohne_aenderung_laeuft_trotzdem_nur_einmal(texte):
    """Ein späterer Wechsel der Sprache von Home Assistant hält „Automatisch“ nicht auf Deutsch fest."""
    alt = [{}, {}]

    neu = texte.sprachwahl_umstellen(alt, "de")

    assert neu == [{"sprache": "auto", "sprache_anlage": "wie_heatnexus"}, None]
    assert texte.sprachwahl_umstellen(_angewandt(alt, neu), "en") is None
