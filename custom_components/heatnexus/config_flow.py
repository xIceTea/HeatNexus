"""Einrichtung der Integration über die Oberfläche.

Ein Konfigurationseintrag bündelt eine Heizungsanlage, die aus mehreren
Steuerungen bestehen kann (z.B. Heizhaus und Wohnhaus mit je eigener
Adresse). In Home Assistant erscheint das als ein Gerät mit Untergeräten.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .client import WindhagerHttpClient
from .const import (
    ALL_LEVELS,
    BEKANNTE_BENUTZER,
    CONF_COUNT,
    CONF_DASHBOARD,
    CONF_ENABLE_ADVANCED,
    CONF_LABEL,
    CONF_LEVELS,
    CONF_MELDUNG_EINLESEN,
    CONF_PANEL,
    CONF_SYSTEMS,
    CONF_UPDATE_INTERVAL,
    CONF_WRITABLE_ADVANCED,
    DEFAULT_LEVELS,
    DEFAULT_USERNAME,
    DOMAIN,
    LEVEL_BESCHRIFTUNG,
    LEVEL_INFO,
    LEVEL_OPERATE,
    MAX_SYSTEMS,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)
from .exceptions import CannotConnect, InvalidAuth

_LOGGER = logging.getLogger(__name__)


def clean_host(raw: str) -> str:
    """Aus einer Eingabe die reine Adresse gewinnen (URL, Port, Pfad entfernen)."""
    host = raw.strip().rstrip("/")
    if "://" in host:
        parsed = urlparse(host)
        host = parsed.netloc or parsed.path
    host = host.split("/")[0]
    if ":" in host:
        host = host.split(":")[0]
    return host.strip("/")


def benutzer_auswahl() -> SelectSelector:
    """Auswahlfeld für den Zugang; ein eigener Name bleibt möglich."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=b, label=b) for b in BEKANNTE_BENUTZER],
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


async def validate_connection(host: str, password: str, username: str = DEFAULT_USERNAME) -> list:
    """Prüfen, ob die Anlage antwortet, und ihre Struktur zurückgeben."""
    client = WindhagerHttpClient(host=host, password=password, username=username)
    try:
        data, status = await client.probe()
    finally:
        await client.close()

    if status in (401, 403):
        raise InvalidAuth
    if status != 200 or not isinstance(data, list):
        raise CannotConnect
    return data


def anlagenkennung(struktur: list) -> str:
    """Dauerhafte Kennung einer Steuerung aus ihren Seriennummern.

    Jeder Knoten meldet eine ``neuronId``; die kleinste davon kennzeichnet die
    Steuerung. Anders als die IP-Adresse bleibt sie gleich, wenn die Anlage im
    Netz umzieht – erst dadurch erkennt Home Assistant eine bereits
    eingerichtete Anlage unter neuer Adresse wieder.
    """
    neuronen = sorted(str(k["neuronId"]) for k in struktur if k.get("neuronId"))
    return neuronen[0] if neuronen else ""


def beschreibe(struktur: list) -> str:
    """Kurzfassung dessen, was die Anlage meldet."""
    namen = []
    for knoten in struktur:
        for funktion in knoten.get("functions", []):
            if not funktion.get("lock") and funktion.get("fctType", -1) >= 0:
                namen.append(str(funktion.get("name", "")).strip())
    return ", ".join(dict.fromkeys(n for n in namen if n)) or "keine Funktionen gemeldet"


def level_schema(defaults: Mapping[str, Any], mit_intervall: bool = True) -> vol.Schema:
    """Auswahl der Bedienebenen (und des Abfrageintervalls)."""
    felder: dict = {
        vol.Required(
            CONF_LEVELS, default=list(defaults.get(CONF_LEVELS, DEFAULT_LEVELS))
        ): SelectSelector(
            SelectSelectorConfig(
                # Beschriftung *und* Übersetzungsschlüssel: Findet die
                # Oberfläche die Übersetzung, gewinnt sie; findet sie keine,
                # steht hier der deutsche Text statt der rohen Schlüssel
                # „info", „operate", „service", „oem". Im Einrichtungsdialog
                # lädt Home Assistant die Übersetzungen der Auswahlfelder
                # einer eigenen Integration nicht zuverlässig mit – ohne
                # Beschriftung blieben die Schlüssel stehen.
                options=[
                    SelectOptionDict(value=lvl, label=LEVEL_BESCHRIFTUNG[lvl]) for lvl in ALL_LEVELS
                ],
                multiple=True,
                mode=SelectSelectorMode.LIST,
                translation_key="levels",
            )
        ),
        vol.Required(
            CONF_ENABLE_ADVANCED, default=bool(defaults.get(CONF_ENABLE_ADVANCED, False))
        ): bool,
        vol.Required(
            CONF_WRITABLE_ADVANCED, default=bool(defaults.get(CONF_WRITABLE_ADVANCED, False))
        ): bool,
    }
    if mit_intervall:
        felder[vol.Required(CONF_DASHBOARD, default=bool(defaults.get(CONF_DASHBOARD, True)))] = (
            bool
        )
        felder[vol.Required(CONF_PANEL, default=bool(defaults.get(CONF_PANEL, False)))] = bool
        felder[
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=int(defaults.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=MIN_UPDATE_INTERVAL,
                max=MAX_UPDATE_INTERVAL,
                step=5,
                unit_of_measurement="s",
                mode=NumberSelectorMode.BOX,
            )
        )
    return vol.Schema(felder)


def normalize_options(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Eingaben zu den Bedienebenen prüfen und vereinheitlichen."""
    levels = [lvl for lvl in raw.get(CONF_LEVELS, DEFAULT_LEVELS) if lvl in ALL_LEVELS]
    # Ohne Info- und Betreiberebene bliebe die Anlage stumm bzw. unbedienbar.
    for pflicht in (LEVEL_INFO, LEVEL_OPERATE):
        if pflicht not in levels:
            levels.append(pflicht)
    ergebnis: dict[str, Any] = {
        CONF_LEVELS: [lvl for lvl in ALL_LEVELS if lvl in levels],
        CONF_ENABLE_ADVANCED: bool(raw.get(CONF_ENABLE_ADVANCED, False)),
        CONF_WRITABLE_ADVANCED: bool(raw.get(CONF_WRITABLE_ADVANCED, False)),
    }
    if CONF_UPDATE_INTERVAL in raw:
        ergebnis[CONF_UPDATE_INTERVAL] = int(raw[CONF_UPDATE_INTERVAL])
    if CONF_DASHBOARD in raw:
        ergebnis[CONF_DASHBOARD] = bool(raw[CONF_DASHBOARD])
    if CONF_PANEL in raw:
        ergebnis[CONF_PANEL] = bool(raw[CONF_PANEL])
    return ergebnis


class WindhagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Führt durch Name, Anzahl der Anlagen, deren Adressen und den Umfang."""

    VERSION = 2

    def __init__(self) -> None:
        """Zwischenstand des Dialogs."""
        self._name: str = "Heizung"
        self._anzahl: int = 1
        self._systeme: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name der Heizungsanlage und Anzahl der Steuerungen."""
        if user_input is not None:
            self._name = user_input[CONF_NAME].strip() or "Heizung"
            self._anzahl = int(user_input[CONF_COUNT])
            self._systeme = []
            return await self.async_step_system()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="Heizung"): str,
                    vol.Required(CONF_COUNT, default=1): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=MAX_SYSTEMS, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )

    async def async_step_system(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bezeichnung, Adresse und Passwort je Steuerung."""
        nummer = len(self._systeme) + 1
        errors: dict[str, str] = {}

        if user_input is not None:
            host = clean_host(user_input[CONF_HOST])
            if any(s[CONF_HOST] == host for s in self._systeme):
                errors["base"] = "already_configured"
            else:
                benutzer = (user_input.get(CONF_USERNAME) or DEFAULT_USERNAME).strip()
                try:
                    struktur = await validate_connection(host, user_input[CONF_PASSWORD], benutzer)
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unerwarteter Fehler beim Verbinden mit %s", host)
                    errors["base"] = "unknown"
                else:
                    self._systeme.append(
                        {
                            CONF_LABEL: user_input[CONF_LABEL].strip() or host,
                            CONF_HOST: host,
                            CONF_USERNAME: benutzer,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            "gefunden": beschreibe(struktur),
                            "kennung": anlagenkennung(struktur),
                        }
                    )
                    if len(self._systeme) < self._anzahl:
                        return await self.async_step_system()
                    return await self.async_step_scope()

        return self.async_show_form(
            step_id="system",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LABEL, default=f"Anlage {nummer}"): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): benutzer_auswahl(),
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"nummer": str(nummer), "anzahl": str(self._anzahl)},
        )

    async def async_step_scope(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bedienebenen und Abfrageintervall festlegen."""
        if user_input is not None:
            gemeinsam = normalize_options(user_input)
            intervall = gemeinsam.pop(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)
            dashboard = gemeinsam.pop(CONF_DASHBOARD, True)
            oberflaeche = gemeinsam.pop(CONF_PANEL, False)
            options: dict[str, Any] = {
                CONF_UPDATE_INTERVAL: intervall,
                CONF_DASHBOARD: dashboard,
                CONF_PANEL: oberflaeche,
            }
            # Die Auswahl gilt zunächst für alle Anlagen; sie lässt sich
            # später je Anlage getrennt ändern.
            for system in self._systeme:
                options[system[CONF_HOST]] = dict(gemeinsam)

            # Kennung aus den Seriennummern; nur wenn eine Anlage keine
            # meldet, bleibt ihre Adresse als Rückfall.
            kennungen = sorted(s.get("kennung") or s[CONF_HOST] for s in self._systeme)
            await self.async_set_unique_id("-".join(kennungen))
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_NAME: self._name,
                    CONF_SYSTEMS: [
                        {
                            CONF_LABEL: s[CONF_LABEL],
                            CONF_HOST: s[CONF_HOST],
                            CONF_USERNAME: s[CONF_USERNAME],
                            CONF_PASSWORD: s[CONF_PASSWORD],
                        }
                        for s in self._systeme
                    ],
                },
                options=options,
            )

        uebersicht = "\n".join(
            f"- **{s[CONF_LABEL]}** ({s[CONF_HOST]}): {s['gefunden']}" for s in self._systeme
        )
        return self.async_show_form(
            step_id="scope",
            data_schema=level_schema({}),
            description_placeholders={"gefunden": uebersicht},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Nach abgelehnter Anmeldung ein neues Passwort erfragen."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passwort einer Anlage erneuern."""
        entry = self._get_reauth_entry()
        systeme = entry.data.get(CONF_SYSTEMS, [])
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            benutzer = (user_input.get(CONF_USERNAME) or DEFAULT_USERNAME).strip()
            try:
                await validate_connection(host, user_input[CONF_PASSWORD], benutzer)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                neu = [
                    (
                        {**s, CONF_USERNAME: benutzer, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                        if s[CONF_HOST] == host
                        else s
                    )
                    for s in systeme
                ]
                return self.async_update_reload_and_abort(entry, data_updates={CONF_SYSTEMS: neu})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=systeme[0][CONF_HOST] if systeme else ""
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=s[CONF_HOST],
                                    label=f"{s[CONF_LABEL]} ({s[CONF_HOST]})",
                                )
                                for s in systeme
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_USERNAME,
                        default=(systeme[0].get(CONF_USERNAME) if systeme else DEFAULT_USERNAME)
                        or DEFAULT_USERNAME,
                    ): benutzer_auswahl(),
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Adresse einer Anlage ändern.

        Nötig, wenn die Anlage im Netz umzieht. Geräte und Entitäten bleiben
        dabei erhalten – ihre Kennungen hängen an den Seriennummern, nicht an
        der Adresse.
        """
        entry = self._get_reconfigure_entry()
        systeme = entry.data.get(CONF_SYSTEMS, [])
        errors: dict[str, str] = {}

        if user_input is not None:
            alt = user_input["anlage"]
            neu_host = clean_host(user_input[CONF_HOST])
            system = next((s for s in systeme if s[CONF_HOST] == alt), {})
            passwort = system.get(CONF_PASSWORD, "")
            benutzer = system.get(CONF_USERNAME) or DEFAULT_USERNAME
            try:
                await validate_connection(neu_host, passwort, benutzer)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                neu = [{**s, CONF_HOST: neu_host} if s[CONF_HOST] == alt else s for s in systeme]
                # Die Optionen sind je Adresse abgelegt und ziehen mit um.
                optionen = dict(entry.options)
                if alt in optionen:
                    optionen[neu_host] = optionen.pop(alt)
                self.hass.config_entries.async_update_entry(entry, options=optionen)
                return self.async_update_reload_and_abort(entry, data_updates={CONF_SYSTEMS: neu})

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "anlage", default=systeme[0][CONF_HOST] if systeme else ""
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=s[CONF_HOST],
                                    label=f"{s[CONF_LABEL]} ({s[CONF_HOST]})",
                                )
                                for s in systeme
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> WindhagerOptionsFlow:
        """Optionen dieser Integration."""
        return WindhagerOptionsFlow()


class WindhagerOptionsFlow(OptionsFlow):
    """Umfang je Anlage und Abfrageintervall nachträglich ändern."""

    def __init__(self) -> None:
        """Zwischenstand."""
        self._host: str | None = None

    def _systeme(self) -> list[dict[str, Any]]:
        return self.config_entry.data.get(CONF_SYSTEMS, [])

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Auswahl: allgemeine Einstellungen oder eine bestimmte Anlage."""
        systeme = self._systeme()
        if len(systeme) <= 1:
            self._host = systeme[0][CONF_HOST] if systeme else ""
            return await self.async_step_system()

        auswahl = {"allgemein": "Allgemein (Abfrageintervall)"}
        for i, system in enumerate(systeme):
            auswahl[f"anlage_{i}"] = f"{system[CONF_LABEL]} ({system[CONF_HOST]})"
        return self.async_show_menu(step_id="init", menu_options=auswahl)

    async def async_step_allgemein(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abfrageintervall für alle Anlagen."""
        options = dict(self.config_entry.options)
        if user_input is not None:
            options[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL])
            options[CONF_DASHBOARD] = bool(user_input[CONF_DASHBOARD])
            options[CONF_PANEL] = bool(user_input[CONF_PANEL])
            options[CONF_MELDUNG_EINLESEN] = bool(user_input[CONF_MELDUNG_EINLESEN])
            return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="allgemein",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DASHBOARD, default=bool(options.get(CONF_DASHBOARD, True))
                    ): bool,
                    vol.Required(CONF_PANEL, default=bool(options.get(CONF_PANEL, False))): bool,
                    vol.Required(
                        CONF_MELDUNG_EINLESEN,
                        default=bool(options.get(CONF_MELDUNG_EINLESEN, False)),
                    ): bool,
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=int(options.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                            step=5,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_system(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bedienebenen einer Anlage."""
        options = dict(self.config_entry.options)
        host = self._host or ""
        if user_input is not None:
            options[host] = normalize_options(user_input)
            return self.async_create_entry(data=options)

        label = next((s[CONF_LABEL] for s in self._systeme() if s[CONF_HOST] == host), host)
        return self.async_show_form(
            step_id="system",
            data_schema=level_schema(options.get(host, {}), mit_intervall=False),
            description_placeholders={"anlage": f"{label} ({host})".strip()},
        )

    def __getattr__(self, name: str):
        """Schritt ``anlage_<n>`` zu jeder eingerichteten Anlage bereitstellen.

        Das Menü führt eine Zeile je Anlage; feste Methoden würden die Zahl
        der Anlagen künstlich begrenzen und bei einer mehr mit „unbekannter
        Schritt" abbrechen.
        """
        if not name.startswith("async_step_anlage_"):
            raise AttributeError(name)
        rest = name.removeprefix("async_step_anlage_")
        if not rest.isdigit():
            raise AttributeError(name)

        async def schritt(user_input=None) -> ConfigFlowResult:
            return await self._anlage(int(rest), user_input)

        return schritt

    async def _anlage(self, index: int, user_input) -> ConfigFlowResult:
        """Menüauswahl auf den gemeinsamen Schritt lenken."""
        systeme = self._systeme()
        if index < len(systeme):
            self._host = systeme[index][CONF_HOST]
        return await self.async_step_system(user_input)
