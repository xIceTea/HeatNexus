"""Antwortzeiten der Abrufe: das Bewertungsfenster als Ring und die Dauern der laufenden Stunde."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from contextvars import ContextVar
import time

from ..verbindung import FENSTER_S

# Der Ring hält nur das Bewertungsfenster; die Stundenmediane kommen aus `stunde_abholen`.

# Gesetzt vom Koordinator während des Abrufs; Teilaufgaben erben ihn, Nachfassen und Schreiben nicht.
IM_ABRUF: ContextVar[bool] = ContextVar("heatnexus_im_abruf", default=False)


class Messreihe:
    """Dauer in ms je Antwort, `None` je Fehlantwort, nur während eines Abrufs."""

    def __init__(self, uhr: Callable[[], float] = time.monotonic) -> None:
        self._uhr = uhr
        self._ring: deque[tuple[float, float | None]] = deque()
        self._stunde: list[float] = []
        self._abruf: list[float] = []

    def antwort(self, dauer_s: float) -> None:
        self._eintragen(dauer_s * 1000)

    def fehler(self) -> None:
        self._eintragen(None)

    def _eintragen(self, dauer_ms: float | None) -> None:
        if not IM_ABRUF.get():
            return
        jetzt = self._uhr()
        self._ring.append((jetzt, dauer_ms))
        if dauer_ms is not None:
            self._stunde.append(dauer_ms)
            self._abruf.append(dauer_ms)
        while self._ring and self._ring[0][0] < jetzt - FENSTER_S:
            self._ring.popleft()

    def eintraege(self) -> tuple[tuple[float, float | None], ...]:
        return tuple(self._ring)

    def jetzt(self) -> float:
        return self._uhr()

    def stunde_abholen(self) -> list[float]:
        """Die Dauern seit dem letzten Abholen; danach beginnt die Liste neu."""
        dauern, self._stunde = self._stunde, []
        return dauern

    def abruf_abholen(self) -> list[float]:
        """Die Dauern seit dem letzten Abruf; danach beginnt die Liste neu."""
        dauern, self._abruf = self._abruf, []
        return dauern
