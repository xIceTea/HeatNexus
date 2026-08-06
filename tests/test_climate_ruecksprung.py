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

    def __init__(
        self,
        climate,
        *,
        restzeit: int | None,
        betriebswahl: int | None,
        gemerkt: int | None,
        gesehen: bool = True,
    ):
        self._restzeit = restzeit
        self._betriebswahl = betriebswahl
        self._modus_davor = gemerkt
        # Ob die Vorgabe schon einmal als laufend gelesen wurde. Ohne das darf
        # eine Restzeit von 0 nicht als „abgelaufen" gelten – sie kann auch
        # heißen, dass der Wert noch gar nicht nachgezogen ist.
        self._vorgabe_gesehen = gesehen
        self.geschrieben: list[int] = []
        self.optimistisch: list[int] = []
        self._pruefen = climate.WindhagerBaseThermostat._ruecksprung_pruefen.__get__(self)

    # --- was die echte Entität liefert -------------------------------------
    def raw_custom_temp_remaining_time(self) -> int:
        return self._restzeit or 0

    def get_oid_value(self, oid: str):
        if oid == "/2/10/0":
            return self._restzeit
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


def test_frisch_gesetzte_vorgabe_wird_nicht_sofort_zurueckgenommen(climate):
    """Die halb frischen Daten unmittelbar nach dem Setzen.

    Wer eine Vorgabe setzt, löst ein gezieltes Nachlesen der Betriebswahl aus.
    Eine Sekunde später steht `3/50` bereits auf dem Heizprogramm, `2/10` aber
    noch auf dem alten Stand – hier 0, weil vorher keine Vorgabe lief. Beides
    zusammen las sich wie „umgeschaltet und schon abgelaufen": Der Rücksprung
    schrieb die eigene Bedienung sofort wieder zurück, und an der Anlage blieb
    alles beim Alten.
    """
    a = _Anlage(
        climate,
        restzeit=0,
        betriebswahl=climate.HEIZPROGRAMM,
        gemerkt=6,
        gesehen=False,
    )
    a.pruefen()
    assert a.geschrieben == [], "die eigene Vorgabe darf nicht zurückgenommen werden"
    assert a._modus_davor == 6, "der Merker wird noch gebraucht"


def test_laufende_vorgabe_macht_den_ruecksprung_scharf(climate):
    """Einmal laufend gelesen – danach zählt eine Restzeit von 0."""
    a = _Anlage(
        climate,
        restzeit=42,
        betriebswahl=climate.HEIZPROGRAMM,
        gemerkt=6,
        gesehen=False,
    )
    a.pruefen()
    assert a._vorgabe_gesehen is True
    a._restzeit = 0
    a.pruefen()
    assert a.geschrieben == [6]


def test_unbekannte_restzeit_gilt_nicht_als_abgelaufen(climate):
    """Ohne gelesenen Wert wird nicht geschrieben.

    Fehlt `2/10`, ist nicht bekannt, ob eine Vorgabe läuft. Eine 0 daraus zu
    machen hieße: zurückschalten, obwohl die Anlage nichts gesagt hat.
    """
    a = _Anlage(climate, restzeit=None, betriebswahl=climate.HEIZPROGRAMM, gemerkt=6)
    a.pruefen()
    assert a.geschrieben == []
    assert a._modus_davor == 6


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


# ---------------------------------------------------------------------------
# Ablauf der optimistischen Anzeige – seit `always_update=False`
# ---------------------------------------------------------------------------
class _Optimistisch:
    """Nur die Zeitprüfung, ohne Home Assistant darunter."""

    def __init__(self, climate):
        """Die geprüfte Methode an ein nacktes Objekt binden."""
        self._gueltig = climate.WindhagerBaseThermostat._optimistisch_gueltig.__get__(self)


def test_optimistische_anzeige_laeuft_nach_zeit_ab(climate):
    """Der Ablauf darf nicht am Takt des Coordinators hängen.

    Bis 1.5.0 wurde er nur in `_handle_coordinator_update` geprüft. Seit der
    Coordinator unveränderte Daten stillschweigend verwirft
    (`always_update=False`), gibt es diesen Takt nicht mehr zwangsläufig:
    Nimmt die Anlage einen Schreibvorgang **nicht** an, ändert sich nichts, es
    feuert nichts – und der optimistisch angezeigte Sollwert bliebe für immer
    stehen. Also genau der Fall, den die Zeitgrenze abfangen soll.
    """
    import time

    entity = _Optimistisch(climate)
    jetzt = time.monotonic()

    assert entity._gueltig(jetzt) is True, "frisch gesetzt muss gelten"
    assert entity._gueltig(jetzt - climate.OPTIMISTIC_MAX_AGE_S + 1) is True
    assert entity._gueltig(jetzt - climate.OPTIMISTIC_MAX_AGE_S - 1) is False, (
        "nach der Zeitgrenze darf die optimistische Anzeige nicht mehr gelten"
    )


def test_zeitgrenze_ist_kuerzer_als_der_nachlade_burst_lang(climate):
    """Der Burst muss innerhalb der Gültigkeit fertig sein.

    Sonst verfiele die Anzeige, während die Anlage noch nachzieht – und der
    Regler spränge genau in dem Moment zurück, in dem der Nutzer hinsieht.
    """
    burst = climate.FAST_REFRESH_COUNT * climate.FAST_REFRESH_INTERVAL
    assert burst < climate.OPTIMISTIC_MAX_AGE_S
