"""Rücksprung nach einer befristeten Vorgabe (Eco/Comfort).

Steht ein Heizkreis auf Standby oder WW-Betrieb, ist er aus: Die Anlage
übernimmt dort keinen Sollwert, sie setzt nur den Timer. Für eine Vorgabe wird
deshalb kurz in ein Heizprogramm geschaltet – und danach muss zuverlässig
zurückgesprungen werden.

Diese Automatik schreibt **von selbst** in eine laufende Heizung. Genau deshalb
steht sie hier unter Test: Sie darf nur dann zurückschalten, wenn die Vorgabe
wirklich abgelaufen ist und niemand die Betriebswahl inzwischen selbst
verstellt hat.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def climate():
    from custom_components.heatnexus import climate as modul

    return modul


class _Anlage:
    """Ein Thermostat, reduziert auf das, was der Rücksprung anfasst."""

    def __init__(self, climate, *, restzeit: int, betriebswahl: int | None, gemerkt: int | None):
        self._restzeit = restzeit
        self._betriebswahl = betriebswahl
        self._modus_davor = gemerkt
        self.geschrieben: list[int] = []
        self.optimistisch: list[int] = []
        self._pruefen = climate.WindhagerBaseThermostat._ruecksprung_pruefen.__get__(self)

    # --- was die echte Entität liefert -------------------------------------
    def raw_custom_temp_remaining_time(self) -> int:
        return self._restzeit

    def get_oid_value(self, oid: str):
        assert oid == "/3/50/0"
        return self._betriebswahl

    def _set_optimistic_mode(self, modus: int) -> None:
        self.optimistisch.append(modus)

    class _Hass:
        def __init__(self, ziel):
            self._ziel = ziel

        def async_create_task(self, coro):
            coro.close()  # nicht ausführen, nur den Aufruf festhalten
            self._ziel.geschrieben.append(self._ziel.optimistisch[-1])

    @property
    def hass(self):
        return self._Hass(self)

    def _modus_schreiben(self, modus):  # wird von async_create_task erwartet
        async def _leer():
            return None

        return _leer()

    def pruefen(self) -> None:
        self._pruefen()


def test_ruecksprung_erst_wenn_die_vorgabe_abgelaufen_ist(climate):
    """Solange die Vorgabe läuft, wird nichts geschrieben."""
    a = _Anlage(climate, restzeit=42, betriebswahl=climate.HEIZPROGRAMM, gemerkt=6)
    a.pruefen()
    assert a.geschrieben == []
    assert a._modus_davor == 6, "der Merker darf nicht verfallen"


def test_ruecksprung_setzt_den_alten_modus(climate):
    """Abgelaufen und noch im gesetzten Programm: zurück auf WW-Betrieb."""
    a = _Anlage(climate, restzeit=0, betriebswahl=climate.HEIZPROGRAMM, gemerkt=6)
    a.pruefen()
    assert a.geschrieben == [6]
    assert a._modus_davor is None, "der Merker gehört danach geleert"


def test_eigene_umstellung_wird_nicht_ueberschrieben(climate):
    """Hat jemand die Betriebswahl selbst verstellt, bleibt sie stehen.

    Sonst risse die Automatik einem den Heizbetrieb wieder weg, den man
    während der Vorgabe bewusst gewählt hat.
    """
    a = _Anlage(climate, restzeit=0, betriebswahl=4, gemerkt=6)  # 4 = Heizbetrieb
    a.pruefen()
    assert a.geschrieben == []
    assert a._modus_davor is None, "der Merker verfällt, ohne zu schreiben"


def test_ohne_merker_passiert_nichts(climate):
    """Wer die Vorgabe aus einem Heizmodus heraus setzt, bekommt keinen Sprung."""
    a = _Anlage(climate, restzeit=0, betriebswahl=climate.HEIZPROGRAMM, gemerkt=None)
    a.pruefen()
    assert a.geschrieben == []


def test_standby_und_ww_betrieb_gelten_als_aus(climate):
    """Nur aus diesen beiden Modi heraus wird überhaupt umgeschaltet.

    0 ist Standby, 6 der WW-Betrieb – in beiden ist der Heizkreis aus.
    """
    assert sorted(climate.WindhagerBaseThermostat.OFF_MODES) == [0, 6]
