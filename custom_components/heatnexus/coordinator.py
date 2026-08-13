"""Der zyklische Abruf einer Anlage."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.const import CONF_NAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ABRUF_TIMEOUT,
    AUTH_FEHLER_GRENZE,
    BACKOFF_MAX,
    DOMAIN,
    ERSTABRUF_TIMEOUT,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class WindhagerDataUpdateCoordinator(DataUpdateCoordinator):
    """Fragt eine Anlage zyklisch ab."""

    def __init__(self, hass, client, entry, host, label, update_interval=UPDATE_INTERVAL):
        """Coordinator für genau eine Anlage."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {host}",
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
        self.entry = entry
        self.host = host
        self.label = label
        self.hub_name = entry.data.get(CONF_NAME) or entry.title
        self.consecutive_timeouts = 0
        # Der gewählte Takt. Bei Störungen wird langsamer gefragt, danach
        # wieder genau hierauf zurückgestellt.
        self._takt = update_interval
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
            f"nicht_erreichbar_{self.entry.entry_id}_{self.host}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="nicht_erreichbar",
            translation_placeholders={"anlage": self.label or self.host, "grund": grund},
        )

    def _stoerung_zuruecknehmen(self) -> None:
        ir.async_delete_issue(
            self.hass, DOMAIN, f"nicht_erreichbar_{self.entry.entry_id}_{self.host}"
        )

    async def _async_update_data(self):
        """Werte der Anlage holen."""
        # Mehrere abgewiesene Anfragen hintereinander heißen: Das Passwort
        # stimmt nicht mehr. Home Assistant fragt dann von sich aus danach,
        # statt die Anlage still als „nicht verfügbar" stehen zu lassen.
        if getattr(self.client, "auth_errors", 0) >= AUTH_FEHLER_GRENZE:
            raise ConfigEntryAuthFailed(f"Anlage {self.host} weist die Anmeldung ab")
        erster = bool(getattr(self.client, "erster_abruf", False))
        try:
            async with asyncio.timeout(ERSTABRUF_TIMEOUT if erster else ABRUF_TIMEOUT):
                data = await self.client.fetch_all()
                self.consecutive_timeouts = 0
                self._wieder_normal_fragen()
                self._rueckkehr_protokollieren()
                self._stoerung_zuruecknehmen()
                return data
        except TimeoutError as err:
            self.consecutive_timeouts += 1
            self._langsamer_fragen()
            self._ausfall_protokollieren(
                "Zeitüberschreitung beim Abruf von %s (Versuch %d)",
                self.host,
                self.consecutive_timeouts,
            )
            if self.consecutive_timeouts >= 3:
                self._stoerung_melden("Sie antwortet nicht mehr.")
                raise UpdateFailed(f"Anlage {self.host} antwortet wiederholt nicht: {err}") from err
            # Ein verpasster Abruf lässt die zuletzt gelesenen Werte stehen.
            # Gibt es noch keine, ist nichts zu halten – dann muss der
            # Fehlschlag auch als Fehlschlag gelten. Ein leeres Ergebnis als
            # *Erfolg* abzulegen hieß, dass jeder Leser der Koordinatordaten
            # eine Anlage ohne Datenpunkte sah; daran hing in 1.5.0-beta.9 die
            # Stilllegung sämtlicher Entitäten.
            if not self.data:
                raise UpdateFailed(
                    f"Anlage {self.host} hat noch keine Werte geliefert: {err}"
                ) from err
            return self.data
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            self._langsamer_fragen()
            self._ausfall_protokollieren("Fehler beim Abruf von %s: %s", self.host, err)
            if self._fehlschlaege >= 3:
                self._stoerung_melden(str(err))
            raise UpdateFailed(f"Fehler bei der Abfrage von {self.host}: {err}") from err
