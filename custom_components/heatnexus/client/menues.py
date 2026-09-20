"""Sammel-Lesezugriff über die Menü-Ebenen einer Funktion.

`GET /1/<node>/<fct>` nennt die Ebenen samt Anzahl, `GET .../<menuId>` liefert
die Datenpunkte seitenweise. So entsteht, was die kuratierten Tabellen nicht
führen – und welche Funktionen ein Knoten hat, ohne sie zu melden.
"""

from __future__ import annotations

import asyncio
import logging

from ..const import (
    EXTRA_OIDS_BY_FCT,
    FCT_ENTITY_MAP,
    FCT_IDS_UNGEMELDET,
    FCT_MODELL,
    FINGERABDRUCK_MIN_TREFFER,
    MENU_PAGE_SIZE,
)
from ..device_db import get_layers

_LOGGER = logging.getLogger(__name__)


class MenuesMixin:
    """Datenpunkte über die Menü-Ebenen einer Funktion einlesen."""

    async def _read_menu(
        self, prefix: str, menu_id: str, expected: int, gewuenscht, schluessel: str = "OID"
    ) -> list:
        """Eine Menü-Ebene lesen, soweit sie gebrauchte Datenpunkte enthält.

        Ein Abruf liefert höchstens MENU_PAGE_SIZE Datenpunkte; weitere holt
        das Gerät über ?offset=<n>. Jeder Eintrag enthält bereits Wert und
        Metadaten, ein zusätzlicher Einzelabruf entfällt damit.

        Enthält die erste Seite keinen einzigen Datenpunkt der gewählten
        Bedienebenen, werden die restlichen Seiten übersprungen. Die großen
        Werksebenen-Menüs des Kessels umfassen bis zu 95 Datenpunkte – das
        spart bei abgewählter Werksebene den Großteil der Anfragen.

        `schluessel` sagt, woran ein Eintrag zu erkennen ist. Im LON-Adressraum
        führen die Einträge keine `OID`, sondern einen `nvIndex`; das
        Seitenprotokoll ist dasselbe und steht deshalb nur hier.
        """
        base = f"http://{self.host}/api/1.0/lookup{prefix}/{menu_id}"
        items: list = []
        seen: set = set()
        offset = 0

        def brauchbar(eintrag) -> bool:
            return isinstance(eintrag, dict) and eintrag.get(schluessel) is not None

        # Das Bedienteil der Anlage fordert mit count=-1 alle Einträge einer
        # Ebene auf einmal an. Es gibt Steuerungen, die darauf mit einer leeren
        # Liste antworten; dort wird nach dem ersten Versuch geblättert.
        if expected > MENU_PAGE_SIZE and self._sammelseite is not False:
            data, status = await self._get(f"{base}?count=-1&offset=0")
            if status == 200 and isinstance(data, list):
                # Eine Antwort zählt, ein Fehler nicht: Sonst schaltete eine
                # einzelne Störung das Sammeln dauerhaft ab.
                self._sammelseite = len(data) > MENU_PAGE_SIZE
                if self._sammelseite:
                    return [i for i in data if brauchbar(i)]

        while True:
            url = base if offset == 0 else f"{base}?offset={offset}"
            data, status = await self._get(url)
            if status != 200 or not isinstance(data, list) or not data:
                break
            fresh = [i for i in data if brauchbar(i) and i[schluessel] not in seen]
            if not fresh:
                break
            items.extend(fresh)
            seen.update(i[schluessel] for i in fresh)
            if len(items) >= expected or len(data) < MENU_PAGE_SIZE:
                break
            if (
                offset == 0
                and gewuenscht is not None
                and not any(gewuenscht(self._gnmn(prefix, i[schluessel])) for i in fresh)
            ):
                _LOGGER.debug(
                    "Menü %s/%s übersprungen: keine Datenpunkte der gewählten Ebenen",
                    prefix,
                    menu_id,
                )
                break
            offset += MENU_PAGE_SIZE

        if expected and len(items) < expected:
            _LOGGER.debug(
                "Menü %s/%s: %d von %d Datenpunkten gelesen", prefix, menu_id, len(items), expected
            )
        return items

    @staticmethod
    def _ebene_ohne_antwort(prefix: str, menu_id: str, fehler: BaseException) -> None:
        """Eine Menü-Ebene ohne Antwort: übergehen oder den Lauf abbrechen.

        Eine Zeitüberschreitung kostet nur ihre Ebene. Alles andere ist ein
        Fehler der Verbindung; ihn zu verschlucken hieße, einen halben
        Erkennungsstand als vollständig zu speichern.
        """
        if not isinstance(fehler, TimeoutError):
            raise fehler
        _LOGGER.warning("Menü %s/%s antwortet nicht und wird übergangen", prefix, menu_id)

    def _typ_aus_datenpunkten(self, prefix: str, menu_data: dict) -> int | None:
        """Den Funktionstyp aus den gefundenen Adressen erschließen.

        Für eine Funktion, die `GET /1` nicht meldet, gibt es keinen `fctType`
        – und ohne ihn greift weder die kuratierte Tabelle noch die
        Ebenenzuordnung. Die Datenpunkte selbst sind aber kennzeichnend genug:
        Verglichen wird, welcher Anteil einer kuratierten Tabelle sich
        wiederfindet.

        Entschieden wird nach Anteil, nicht nach Trefferzahl, und erst ab
        `FINGERABDRUCK_MIN_TREFFER` Treffern – die Begründung für beides steht
        an der Konstanten.
        """
        vorhanden = {self._gnmn(prefix, oid) for oid in menu_data}
        if not vorhanden:
            return None

        bester: tuple[float, int, int] | None = None
        for fct_type, eintraege in FCT_ENTITY_MAP.items():
            tabelle = {d["oid"].strip("/").rsplit("/", 1)[0] for d in eintraege}
            treffer = len(tabelle & vorhanden)
            if treffer < FINGERABDRUCK_MIN_TREFFER:
                continue
            wertung = (treffer / len(tabelle), treffer, fct_type)
            if bester is None or wertung > bester:
                bester = wertung
        if bester is None:
            return None

        anteil, treffer, fct_type = bester
        _LOGGER.info(
            "%s ist in der Struktur nicht gemeldet, nach seinen Datenpunkten "
            "aber Funktionstyp %s (%s von %s Adressen, %.0f %%)",
            prefix,
            fct_type,
            treffer,
            len(FCT_ENTITY_MAP[fct_type]),
            anteil * 100,
        )
        return fct_type

    async def _ungemeldete_funktionen(self, device_id: str, gemeldet: list[dict]) -> list[dict]:
        """Funktionen suchen, die der Knoten hat, aber nicht meldet.

        **Ein Knoten kann antworten, ohne sich anzukündigen.** Es gibt Anlagen,
        deren Kessel in `GET /1` ausschließlich seinen LON-Adressraum führt und
        keine Funktion mit `fctType`. Die Datenpunkte darunter antworten
        trotzdem – vollständig, mit Metadaten und Werten. Wer nur die
        gemeldeten Funktionen liest, hält so einen Kessel für nicht vorhanden
        und legt für ihn keine einzige Entität an.

        Geprüft wird nur, wenn der Knoten gar keine brauchbare Funktion meldet;
        an einem Knoten mit gemeldeter Funktion wäre es geraten.
        """
        vergeben = {f.get("fctId") for f in gemeldet}
        gefunden = []
        for fct_id in FCT_IDS_UNGEMELDET:
            if fct_id in vergeben:
                continue
            prefix = f"{device_id}/{fct_id}"
            menu_data = await self._read_function_menus(prefix, None)
            if not menu_data:
                continue
            fct_type = self._typ_aus_datenpunkten(prefix, menu_data)
            if fct_type is None:
                _LOGGER.debug("%s antwortet, passt aber zu keiner bekannten Bauart", prefix)
                continue
            gefunden.append(
                {
                    "fctId": fct_id,
                    "fctType": fct_type,
                    "name": FCT_MODELL.get(fct_type, f"Funktion {fct_type}"),
                    "_menus": menu_data,
                }
            )
        return gefunden

    async def _menue_ebenen(self, prefix: str) -> dict[str, int] | None:
        """Die Menü-Ebenen einer Funktion und ihre angekündigte Länge.

        ``None``, wenn die Funktion keine Menüliste liefert – ältere Firmware
        kennt sie nicht, dann greifen Einzelabfragen.
        """
        # Ein Knoten, der die Verbindung annimmt und dann schweigt, gilt als
        # ohne Menüliste. Der Rest der Anlage wird deswegen nicht aufgegeben.
        try:
            root, status = await self._get(f"http://{self.host}/api/1.0/lookup{prefix}")
        except TimeoutError:
            _LOGGER.warning("%s antwortet nicht und wird übergangen", prefix)
            return None
        if status != 200 or not isinstance(root, list) or not root:
            return None
        if not isinstance(root[0], dict) or "id" not in root[0]:
            return None
        return {str(m.get("id")): int(m.get("count") or 0) for m in root}

    async def _read_function_menus(self, prefix: str, fct_type: int | None) -> dict:
        """Alle Datenpunkte einer Funktion über ihre Menü-Ebenen einlesen."""
        menus = await self._menue_ebenen(prefix)
        if menus is None:
            return {}

        layers = get_layers(fct_type) or {}
        interessant = {g for lvl in self.levels for g in layers.get(lvl, [])}
        # Kuratierte Datenpunkte und bekannte Ausnahmen zählen immer dazu.
        interessant.update(
            d["oid"].strip("/").rsplit("/", 1)[0] for d in FCT_ENTITY_MAP.get(fct_type, [])
        )
        interessant.update(EXTRA_OIDS_BY_FCT.get(fct_type, ()))
        pruefer = interessant.__contains__ if interessant else None

        results = await asyncio.gather(
            *(self._read_menu(prefix, menu_id, count, pruefer) for menu_id, count in menus.items()),
            return_exceptions=True,
        )
        datapoints: dict = {}
        for menu_id, items in zip(menus, results, strict=True):
            if isinstance(items, BaseException):
                self._ebene_ohne_antwort(prefix, menu_id, items)
                continue
            for item in items:
                oid = item.get("OID")
                if oid:
                    datapoints[oid] = item
        _LOGGER.debug("%s: %d Datenpunkte aus %d Menü-Ebenen", prefix, len(datapoints), len(menus))
        return datapoints
