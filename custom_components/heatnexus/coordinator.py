"""Der zyklische Abruf einer Anlage."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ABRUF_RESERVE,
    ABRUF_TIMEOUT,
    AUTH_FEHLER_GRENZE,
    BACKOFF_MAX,
    DOMAIN,
    ERSTABRUF_TIMEOUT,
    NACHFASS_ANZAHL,
    NACHFASS_INTERVALL,
    UPDATE_INTERVAL,
)
from .exceptions import mit_text
from .texte import woerterbuch

_LOGGER = logging.getLogger(__name__)


class WindhagerDataUpdateCoordinator(DataUpdateCoordinator):
    """Fragt eine Anlage zyklisch ab."""

    def __init__(self, hass, client, entry, host, label, update_interval=UPDATE_INTERVAL):
        """Coordinator für genau eine Anlage."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {host}",
            config_entry=entry,
            update_interval=timedelta(seconds=update_interval),
            # Unveränderte Daten lösen keinen Durchlauf durch alle Entitäten
            # aus. Eine Anlage im Standby meldet minutenlang dieselben Werte –
            # bei dreistelliger Entitätszahl jedes Mal ein vollständiger
            # Rundlauf ohne Ergebnis.
            #
            # Achtung, das hat eine Nebenwirkung: Was sich nur *mit der Zeit*
            # ändert, darf nicht am Takt des Coordinators hängen. Die
            # optimistische Anzeige des Thermostats prüft ihren Ablauf deshalb
            # seither in der Eigenschaft selbst (`_optimistisch_gueltig`) und
            # nicht mehr nur beim Eintreffen neuer Daten.
            always_update=False,
        )
        self.client = client
        self.host = host
        self.label = label
        # Der gewählte Takt. Bei Störungen wird langsamer gefragt, danach
        # wieder genau hierauf zurückgestellt.
        self._takt = update_interval
        # Fehlschläge in Folge, gleich welcher Art; die erste Antwort setzt sie zurück.
        self._fehlschlaege = 0
        # Ob der Ausfall schon im Protokoll steht. Eine Anlage, die über Nacht
        # weg ist, schriebe sonst je Abruf eine Zeile.
        self._ausfall_gemeldet = False

    def _langsamer_fragen(self) -> None:
        """Nach einem Fehlschlag den Abstand verdoppeln.

        Eine Anlage, die nicht antwortet, antwortet auch dreißig Sekunden
        später nicht – sie bekommt dann aber trotzdem alle dreißig Sekunden
        eine volle Runde Anfragen. Ist die Steuerung nur überlastet, hält der
        gleichbleibende Takt sie genau darin fest.
        """
        self._fehlschlaege += 1
        neu = min(self._takt * 2**self._fehlschlaege, BACKOFF_MAX)
        if self.update_interval != timedelta(seconds=neu):
            _LOGGER.debug("Abruf von %s vorerst alle %d s", self.host, neu)
            self.update_interval = timedelta(seconds=neu)

    def _wieder_normal_fragen(self) -> None:
        """Zurück auf den gewählten Takt, sobald die Anlage wieder antwortet."""
        self._fehlschlaege = 0
        if self.update_interval != timedelta(seconds=self._takt):
            _LOGGER.debug("Abruf von %s wieder alle %d s", self.host, self._takt)
            self.update_interval = timedelta(seconds=self._takt)

    def _ausfall_protokollieren(self, satz: str, *args) -> None:
        """Den Ausfall einmal deutlich melden, jede Wiederholung nur auf Debug."""
        if self._ausfall_gemeldet:
            _LOGGER.debug(satz, *args)
            return
        self._ausfall_gemeldet = True
        _LOGGER.warning(satz, *args)

    def _rueckkehr_protokollieren(self) -> None:
        """Die Gegenzeile zum gemeldeten Ausfall – sonst bleibt er offen."""
        if not self._ausfall_gemeldet:
            return
        self._ausfall_gemeldet = False
        _LOGGER.info("Anlage %s antwortet wieder", self.host)

    def _stoerung_melden(self, grund: str) -> None:
        """Ein Problem in die Reparaturen von Home Assistant eintragen.

        Eine Benachrichtigung verschwindet mit einem Klick und kommt nie
        wieder; ein Reparatureintrag bleibt stehen, bis das Problem weg ist,
        und **löst sich von selbst auf**, sobald die Anlage wieder antwortet.
        """
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"nicht_erreichbar_{self.config_entry.entry_id}_{self.host}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="nicht_erreichbar",
            translation_placeholders={"anlage": self.label or self.host, "grund": grund},
        )

    def _stoerung_zuruecknehmen(self) -> None:
        ir.async_delete_issue(
            self.hass, DOMAIN, f"nicht_erreichbar_{self.config_entry.entry_id}_{self.host}"
        )

    async def _async_update_data(self):
        """Werte der Anlage holen."""
        # Mehrere abgewiesene Anfragen hintereinander heißen: Das Passwort
        # stimmt nicht mehr. Home Assistant fragt dann von sich aus danach,
        # statt die Anlage still als „nicht verfügbar" stehen zu lassen.
        if self.client.auth_errors >= AUTH_FEHLER_GRENZE:
            raise mit_text(ConfigEntryAuthFailed, "anmeldung_abgewiesen", anlage=self.host)
        fenster = ERSTABRUF_TIMEOUT if self.client.erster_abruf else ABRUF_TIMEOUT
        try:
            # Der Abruf bekommt sein Zeitfenster mit und hört von selbst
            # rechtzeitig auf. Die Zeitüberschreitung bleibt der Notnagel für
            # eine Anlage, die gar nicht mehr antwortet.
            async with asyncio.timeout(fenster):
                data = await self.client.fetch_all(budget=fenster - ABRUF_RESERVE)
                self._wieder_normal_fragen()
                self._rueckkehr_protokollieren()
                self._stoerung_zuruecknehmen()
                return data
        except TimeoutError as err:
            self._langsamer_fragen()
            self._ausfall_protokollieren(
                "Zeitüberschreitung beim Abruf von %s (Versuch %d)",
                self.host,
                self._fehlschlaege,
            )
            if self._fehlschlaege >= 3:
                self._stoerung_melden(woerterbuch(self.hass)("Sie antwortet nicht mehr."))
                raise mit_text(
                    UpdateFailed, "antwortet_nicht", anlage=self.host, fehler=err
                ) from err
            # Ein verpasster Abruf lässt die zuletzt gelesenen Werte stehen. Gibt es
            # noch keine, bleibt es ein Fehlschlag: Ein leeres Ergebnis als Erfolg zeigte
            # jedem Leser eine Anlage ohne Datenpunkte, und die Entitäten würden stillgelegt.
            if not self.data:
                raise mit_text(UpdateFailed, "keine_werte", anlage=self.host, fehler=err) from err
            return self.data
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            self._langsamer_fragen()
            self._ausfall_protokollieren("Fehler beim Abruf von %s: %s", self.host, err)
            if self._fehlschlaege >= 3:
                self._stoerung_melden(str(err))
                raise mit_text(
                    UpdateFailed, "abfrage_fehler", anlage=self.host, fehler=err
                ) from err
            # Ein einzelner Fehlschlag lässt die zuletzt gelesenen Werte stehen.
            # Alle Entitäten für einen Takt auf „nicht verfügbar" zu setzen
            # reißt jede Statistik auf. Ohne Werte bleibt es ein Fehlschlag.
            if not self.data:
                raise mit_text(
                    UpdateFailed, "abfrage_fehler", anlage=self.host, fehler=err
                ) from err
            return self.data

    async def werte_nachlesen(self, oids: list[str]) -> dict | None:
        """Einzelne Adressen sofort lesen und in den Bestand legen; None bei Fehlschlag.

        Geweckt werden nur die Zuhörer – kein Durchlauf durch die ganze Anlage.
        """
        try:
            gelesen = await self.client.fetch_oids(oids)
        except Exception as err:
            # Nachlesen ist eine Beschleunigung: Der reguläre Durchlauf holt den Wert ohnehin.
            _LOGGER.debug("Gezieltes Nachlesen von %s fehlgeschlagen: %s", oids, err)
            return None
        if gelesen and self.data is not None:
            self.data.setdefault("oids", {}).update(gelesen)
            self.async_update_listeners()
        return gelesen

    def nachfassen(
        self,
        oids: list[str],
        erwartet: dict[str, str] | None = None,
        anzahl: int = NACHFASS_ANZAHL,
        abstand: float = NACHFASS_INTERVALL,
    ) -> None:
        """Adressen nach einer Bedienung kurz engmaschig nachlesen.

        Als Aufgabe des Eintrags: Beim Entladen bricht Home Assistant sie ab.
        """
        self.config_entry.async_create_background_task(
            self.hass,
            self._nachfass_lauf(list(oids), erwartet, anzahl, abstand),
            name=f"{DOMAIN}_nachfassen_{self.host}",
        )

    async def _nachfass_lauf(
        self, oids: list[str], erwartet: dict[str, str] | None, anzahl: int, abstand: float
    ) -> None:
        for _ in range(anzahl):
            await asyncio.sleep(abstand)
            gelesen = await self.werte_nachlesen(oids)
            if gelesen is None:
                return
            # Meldet die Anlage den erwarteten Wert, ist nichts mehr nachzufassen.
            if erwartet and all(str(gelesen.get(o)) == str(w) for o, w in erwartet.items()):
                return
