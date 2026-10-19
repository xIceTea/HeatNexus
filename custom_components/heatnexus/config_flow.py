"""Einrichtung der Integration über die Oberfläche.

Ein Konfigurationseintrag bündelt eine Heizungsanlage, die aus mehreren
Steuerungen bestehen kann (z.B. Kesselhaus und Nebengebäude mit je eigener
Adresse). In Home Assistant erscheint das als ein Gerät mit Untergeräten.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    LabelSelector,
    LabelSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.storage import Store
import voluptuous as vol

from . import steuerungen
from .blueprints import verfuegbare as verfuegbare_vorlagen
from .const import (
    BEFUND_UMZUG,
    CONF_AUSSENTEMPERATUR,
    CONF_COUNT,
    CONF_DASHBOARD,
    CONF_HILFE,
    CONF_IDS_ANPASSEN,
    CONF_LABEL,
    CONF_MARKEN,
    CONF_MARKEN_STATUS,
    CONF_MELDUNG_EINLESEN,
    CONF_PANEL,
    CONF_SPRACHE,
    CONF_SPRACHE_ANLAGE,
    CONF_STARTWERTE,
    CONF_STOERUNG_ZURUECKSETZEN,
    CONF_SYSTEMS,
    CONF_UPDATE_INTERVAL,
    CONF_VORLAGEN,
    CONF_ZUSATZGRUPPEN,
    CONF_ZUSATZWERTE,
    DEFAULT_USERNAME,
    DISCOVERY_STORE_VERSION,
    DOMAIN,
    GRUPPE_INDIVIDUELL,
    MAX_SYSTEMS,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    NUR_BUS_JE_FCT,
    SPRACHE_BESCHRIFTUNG,
    SPRACHE_WIE_HEATNEXUS,
    STARTWERTE_VORGABE,
    STARTWERTE_WAHL,
    SUBEINTRAG_QUELLE,
    UPDATE_INTERVAL,
)
from .erkennungsstand import laufzeitdaten, store_key
from .exceptions import CannotConnect, InvalidAuth
from .formulare import (
    anlagenkennung,
    benutzer_auswahl,
    beschreibe,
    clean_host,
    gruppen_ableiten,
    gruppen_aufloesen,
    level_schema,
    normalize_options,
    validate_connection,
    zusatzgruppen_feld,
    zusatzwerte_feld,
)
from .geraetetexte import SPRACHE_AUTO, SPRACHEN
from .migration import entity_ids_umbenennen
from .repairs import adresshinweise_entfernen
from .texte import gemeinsame_wahl, woerterbuch_zu
from .waermequelle_flow import WaermequelleSubentryFlow

_LOGGER = logging.getLogger(__name__)


async def _verbindung_pruefen(host: str, passwort: str, benutzer: str) -> tuple[list | None, str]:
    """Die Struktur der Anlage, sonst der Fehlerschlüssel für das Formular."""
    try:
        return await validate_connection(host, passwort, benutzer), ""
    except InvalidAuth:
        return None, "invalid_auth"
    except CannotConnect:
        return None, "cannot_connect"
    except Exception:
        _LOGGER.exception("Unerwarteter Fehler beim Verbinden mit %s", host)
        return None, "unknown"


def _anzeigename(system: Mapping[str, Any]) -> str:
    """Bezeichnung mit Adresse, wie im Menü."""
    return f"{system.get(CONF_LABEL) or system[CONF_HOST]} ({system[CONF_HOST]})"


def _steuerung_schema(bezeichnung: str) -> vol.Schema:
    """Bezeichnung, Adresse, Zugang und Passwort einer Steuerung."""
    return vol.Schema(
        {
            vol.Required(CONF_LABEL, default=bezeichnung): str,
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): benutzer_auswahl(),
            vol.Required(CONF_PASSWORD): str,
        }
    )


def _anlagenwahl(feld: str, systeme: list[dict[str, Any]]) -> dict:
    """Auswahl der Steuerung eines Eintrags, vorbelegt mit der ersten."""
    return {
        vol.Required(feld, default=systeme[0][CONF_HOST] if systeme else ""): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=s[CONF_HOST], label=_anzeigename(s)) for s in systeme
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
    }


def _zugangsfeld(systeme: list[dict[str, Any]]) -> dict:
    """Der Zugang, vorbelegt mit dem der ersten Steuerung."""
    vorgabe = (systeme[0].get(CONF_USERNAME) if systeme else None) or DEFAULT_USERNAME
    return {vol.Required(CONF_USERNAME, default=vorgabe): benutzer_auswahl()}


def _gleiche_steuerung(entry: ConfigEntry, system: Mapping[str, Any], struktur: list) -> bool:
    """Ob unter der neuen Adresse die Steuerung antwortet, die der Eintrag kennt.

    Verglichen wird die Seriennummer; fehlt sie auf einer Seite, lässt sich nichts prüfen.
    """
    neu = anlagenkennung(struktur)
    bekannt = {system["kennung"]} if system.get("kennung") else set()
    bekannt = bekannt or set(str(entry.unique_id or "").split("-")) - {""}
    if not neu or not bekannt or system.get(CONF_HOST) in bekannt:
        return True
    return neu in bekannt


SPRACHWAHL = (SPRACHE_AUTO, *SPRACHEN)
ANLAGENSPRACHWAHL = (SPRACHE_WIE_HEATNEXUS, *SPRACHEN)


def _sprachauswahl(werte: tuple[str, ...], schluessel: str) -> SelectSelector:
    """Eine Sprachauswahl; die deutsche Beschriftung gilt nur, wo die Übersetzung fehlt."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=w, label=SPRACHE_BESCHRIFTUNG[w]) for w in werte],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=schluessel,
        )
    )


class WindhagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Führt durch Name, Anzahl der Anlagen, deren Adressen und den Umfang."""

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Zwischenstand des Dialogs."""
        self._name: str = "Heizung"
        self._anzahl: int = 1
        self._systeme: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name der Heizungsanlage und Anzahl der Steuerungen."""
        if user_input is not None:
            self._name = user_input[CONF_NAME].strip() or woerterbuch_zu(self)("Heizung")
            self._anzahl = int(user_input[CONF_COUNT])
            self._systeme = []
            return await self.async_step_system()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=woerterbuch_zu(self)("Heizung")): str,
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
                struktur, fehler = await _verbindung_pruefen(
                    host, user_input[CONF_PASSWORD], benutzer
                )
                if fehler:
                    errors["base"] = fehler
                else:
                    self._systeme.append(
                        {
                            CONF_LABEL: user_input[CONF_LABEL].strip() or host,
                            CONF_HOST: host,
                            CONF_USERNAME: benutzer,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            "gefunden": beschreibe(
                                struktur, woerterbuch_zu(self)("keine Funktionen gemeldet")
                            ),
                            "kennung": anlagenkennung(struktur),
                        }
                    )
                    if len(self._systeme) < self._anzahl:
                        return await self.async_step_system()
                    return await self.async_step_scope()

        return self.async_show_form(
            step_id="system",
            data_schema=_steuerung_schema(
                woerterbuch_zu(self)("Anlage {nummer}").replace("{nummer}", str(nummer))
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
                # Mit beiden Sprachfeldern gilt der Eintrag nicht als Altbestand für die Umstellung.
                CONF_SPRACHE: gemeinsame_wahl(self.hass),
                CONF_SPRACHE_ANLAGE: SPRACHE_WIE_HEATNEXUS,
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
            _, fehler = await _verbindung_pruefen(host, user_input[CONF_PASSWORD], benutzer)
            if fehler:
                errors["base"] = fehler
            else:
                neu = [
                    (
                        {**s, CONF_USERNAME: benutzer, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                        if s[CONF_HOST] == host
                        else s
                    )
                    for s in systeme
                ]
                return self._uebernehmen_und_beenden(entry, {**entry.data, CONF_SYSTEMS: neu})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    **_anlagenwahl(CONF_HOST, systeme),
                    **_zugangsfeld(systeme),
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
            # Der Zugang lässt sich hier mitändern. „Service" sieht
            # Datenpunkte, die „USER" gar nicht erst geliefert bekommt.
            benutzer = (
                user_input.get(CONF_USERNAME) or system.get(CONF_USERNAME) or DEFAULT_USERNAME
            ).strip()
            fehler = await self._neue_adresse_pruefen(entry, system, neu_host, benutzer)
            if fehler:
                errors["base"] = fehler
            else:
                return await self._adresse_umstellen(entry, alt, neu_host, benutzer)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    **_anlagenwahl("anlage", systeme),
                    vol.Required(CONF_HOST): str,
                    **_zugangsfeld(systeme),
                }
            ),
            errors=errors,
        )

    async def _neue_adresse_pruefen(
        self, entry: ConfigEntry, system: Mapping[str, Any], neu_host: str, benutzer: str
    ) -> str:
        """Den Fehlerschlüssel für eine neue Adresse; leer, wenn sie passt."""
        alt = system.get(CONF_HOST)
        if neu_host != alt and any(s[CONF_HOST] == neu_host for s in entry.data[CONF_SYSTEMS]):
            return "already_configured"
        struktur, fehler = await _verbindung_pruefen(
            neu_host, system.get(CONF_PASSWORD, ""), benutzer
        )
        if fehler:
            return fehler
        return "" if _gleiche_steuerung(entry, system, struktur or []) else "andere_steuerung"

    async def _adresse_umstellen(
        self, entry: ConfigEntry, alt: str, neu_host: str, benutzer: str
    ) -> ConfigFlowResult:
        """Adresse, Zugang und Optionen umschreiben; was an der alten Adresse hing, entfällt."""
        systeme = entry.data.get(CONF_SYSTEMS, [])
        neu = [
            {**s, CONF_HOST: neu_host, CONF_USERNAME: benutzer} if s[CONF_HOST] == alt else s
            for s in systeme
        ]
        # Die Optionen sind je Adresse abgelegt und ziehen mit um.
        optionen = dict(entry.options)
        if alt in optionen:
            optionen[neu_host] = optionen.pop(alt)
        if neu_host != alt:
            # Der geladene Umfang zieht mit, sonst gilt die alte Adresse als abgewählt.
            umfang = (laufzeitdaten(entry) or {}).get("umfang")
            if isinstance(umfang, dict) and alt in umfang:
                umfang[neu_host] = umfang.pop(alt)
            adresshinweise_entfernen(self.hass, entry.entry_id, alt)
            await Store(self.hass, DISCOVERY_STORE_VERSION, store_key(entry, alt)).async_remove()
            self._quellen_umstellen(entry, alt, neu_host)
            # Das Archiv zieht erst beim Neuladen um, nachdem der alte Sammler gespeichert hat.
            self.hass.data.setdefault(BEFUND_UMZUG, {})[(entry.entry_id, neu_host)] = alt
        return self._uebernehmen_und_beenden(
            entry, {**entry.data, CONF_SYSTEMS: neu}, options=optionen
        )

    def _quellen_umstellen(self, entry: ConfigEntry, alt: str, neu_host: str) -> None:
        """Die Wärmequellen der Anlage an die neue Adresse hängen."""
        for sub in (entry.subentries or {}).values():
            if sub.subentry_type == SUBEINTRAG_QUELLE and (sub.data or {}).get(CONF_HOST) == alt:
                self.hass.config_entries.async_update_subentry(
                    entry, sub, data={**sub.data, CONF_HOST: neu_host}
                )

    def _uebernehmen_und_beenden(
        self, entry: ConfigEntry, daten: Mapping[str, Any], **optionen: Any
    ) -> ConfigFlowResult:
        """Daten und Optionen in einem Schritt schreiben und den Eintrag einmal neu laden.

        Ein geladener Eintrag lädt über seinen Update-Listener neu; nur ohne ihn lädt der Ablauf.
        """
        if not entry.update_listeners:
            return self.async_update_reload_and_abort(entry, data=daten, **optionen)
        if not self.hass.config_entries.async_update_entry(entry, data=daten, **optionen):
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        grund = (
            "reconfigure_successful" if self.source == SOURCE_RECONFIGURE else "reauth_successful"
        )
        return self.async_abort(reason=grund)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> WindhagerOptionsFlow:
        """Optionen dieser Integration."""
        return WindhagerOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Eine Wärmequelle wird als eigenes Gerät hinzugefügt."""
        return {SUBEINTRAG_QUELLE: WaermequelleSubentryFlow}


# Ja/Nein-Einstellungen unter „Allgemein“ mit ihrer Vorgabe, in der Reihenfolge des Dialogs.
ALLGEMEINE_SCHALTER = (
    (CONF_DASHBOARD, True),
    (CONF_PANEL, False),
    (CONF_HILFE, True),
    (CONF_MELDUNG_EINLESEN, False),
    (CONF_STOERUNG_ZURUECKSETZEN, False),
)


class WindhagerOptionsFlow(OptionsFlow):
    """Umfang je Anlage und Abfrageintervall nachträglich ändern."""

    def __init__(self) -> None:
        """Zwischenstand."""
        self._host: str | None = None
        # Anlage, Zugang und schon geprüfte Optionen, während der zweite
        # Schritt für die Einzelwerte offen ist.
        self._offen: tuple[str, str, dict[str, Any]] | None = None
        # Die neue Bezeichnung der Anlage, bis der Dialog abschließt.
        self._bezeichnung: str = ""
        self._ids_anpassen = False

    def _systeme(self) -> list[dict[str, Any]]:
        return self.config_entry.data.get(CONF_SYSTEMS, [])

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Auswahl: allgemeine Einstellungen oder eine bestimmte Anlage."""
        systeme = self._systeme()
        # Das Menü erscheint auch bei einer einzigen Anlage. Sprang der Dialog
        # dort direkt zur Anlage, war der Schritt „Allgemeine Einstellungen"
        # nach der Einrichtung nie wieder erreichbar – und mit ihm Sprache,
        # Dashboard, Panel, Erklärungen, Außentemperatur und Abfrageintervall.
        uebersetzt = woerterbuch_zu(self)
        auswahl = {"allgemein": uebersetzt("Allgemein (Oberfläche, Sprache, Abfrage)")}
        for i, system in enumerate(systeme):
            auswahl[f"anlage_{i}"] = _anzeigename(system)
        auswahl["steuerung_neu"] = uebersetzt("Steuerung hinzufügen")
        # Die letzte Steuerung bleibt; eine ganze Heizung entfernt man mit dem Eintrag.
        if len(systeme) > 1:
            auswahl["steuerung_entfernen"] = uebersetzt("Steuerung entfernen")
        return self.async_show_menu(step_id="init", menu_options=auswahl)

    async def async_step_steuerung_neu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Eine weitere Steuerung an den Eintrag hängen; danach lädt er neu."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = clean_host(user_input[CONF_HOST])
            benutzer = (user_input.get(CONF_USERNAME) or DEFAULT_USERNAME).strip()
            if any(s[CONF_HOST] == host for s in self._systeme()):
                errors["base"] = "already_configured"
            else:
                struktur, fehler = await _verbindung_pruefen(
                    host, user_input[CONF_PASSWORD], benutzer
                )
                if fehler:
                    errors["base"] = fehler
                else:
                    neu = {
                        CONF_LABEL: user_input[CONF_LABEL].strip() or host,
                        CONF_HOST: host,
                        CONF_USERNAME: benutzer,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        "kennung": anlagenkennung(struktur or []),
                    }
                    steuerungen.hinzufuegen(self.hass, self.config_entry, neu)
                    return self.async_abort(reason="steuerung_hinzugefuegt")
        return self.async_show_form(
            step_id="steuerung_neu",
            data_schema=self.add_suggested_values_to_schema(
                _steuerung_schema(""), user_input or {}
            ),
            errors=errors,
        )

    async def async_step_steuerung_entfernen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Die Steuerung wählen, die mit allem, was an ihr hängt, entfernt wird."""
        systeme = self._systeme()
        if len(systeme) < 2:
            return self.async_abort(reason="letzte_steuerung")
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            return await self.async_step_steuerung_entfernen_bestaetigen()
        return self.async_show_form(
            step_id="steuerung_entfernen",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=s[CONF_HOST], label=_anzeigename(s))
                                for s in systeme
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_steuerung_entfernen_bestaetigen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Aufzählen, was mitgeht; erst der Haken entfernt die Steuerung."""
        host = self._host or ""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get("verstanden"):
                await steuerungen.entfernen(self.hass, self.config_entry, host)
                return self.async_abort(reason="steuerung_entfernt")
            errors["base"] = "bestaetigung_fehlt"
        folgen = steuerungen.folgen(self.hass, self.config_entry, host)
        keine = woerterbuch_zu(self)("keine")
        system = next((s for s in self._systeme() if s[CONF_HOST] == host), {CONF_HOST: host})
        return self.async_show_form(
            step_id="steuerung_entfernen_bestaetigen",
            data_schema=vol.Schema({vol.Required("verstanden", default=False): bool}),
            errors=errors,
            description_placeholders={
                "anlage": _anzeigename(system),
                "geraete": str(folgen.geraete),
                "automatiken": ", ".join(folgen.automatiken) or keine,
                "quellen": ", ".join(folgen.quellen) or keine,
            },
        )

    def _sprachfelder(self, options: Mapping[str, Any]) -> dict:
        """Gemeinsame Sprache und Sprache dieser Anlage, vorbelegt mit der gespeicherten Wahl."""
        eigene = options.get(CONF_SPRACHE_ANLAGE)
        return {
            vol.Required(CONF_SPRACHE, default=gemeinsame_wahl(self.hass)): _sprachauswahl(
                SPRACHWAHL, "sprache"
            ),
            vol.Required(
                CONF_SPRACHE_ANLAGE,
                default=eigene if eigene in ANLAGENSPRACHWAHL else SPRACHE_WIE_HEATNEXUS,
            ): _sprachauswahl(ANLAGENSPRACHWAHL, "sprache_anlage"),
        }

    def _sprache_uebernehmen(self, options: dict[str, Any], user_input: Mapping[str, Any]) -> None:
        """Die eigene Wahl gilt nur hier; die gemeinsame geht an jeden anderen Eintrag."""
        wahl = user_input.get(CONF_SPRACHE, SPRACHE_AUTO)
        options[CONF_SPRACHE] = wahl
        options[CONF_SPRACHE_ANLAGE] = user_input.get(CONF_SPRACHE_ANLAGE, SPRACHE_WIE_HEATNEXUS)
        for eintrag in self.hass.config_entries.async_entries(DOMAIN):
            if eintrag.entry_id == self.config_entry.entry_id:
                continue
            if (eintrag.options or {}).get(CONF_SPRACHE) != wahl:
                self.hass.config_entries.async_update_entry(
                    eintrag, options={**eintrag.options, CONF_SPRACHE: wahl}
                )

    async def async_step_allgemein(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abfrageintervall für alle Anlagen."""
        options = dict(self.config_entry.options)
        # Die Vorlagen liegen als Dateien; gelesen wird außerhalb der Ereignisschleife.
        vorlagen = await self.hass.async_add_executor_job(verfuegbare_vorlagen)
        if user_input is not None:
            options[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL])
            options[CONF_STARTWERTE] = int(user_input.get(CONF_STARTWERTE, STARTWERTE_VORGABE))
            # .get statt [] – ein fehlendes Feld darf den Dialog nicht mit
            # „Unknown error occurred“ abbrechen lassen.
            for schluessel, vorgabe in ALLGEMEINE_SCHALTER:
                options[schluessel] = bool(user_input.get(schluessel, vorgabe))
            self._sprache_uebernehmen(options, user_input)
            options[CONF_VORLAGEN] = [v for v in user_input.get(CONF_VORLAGEN, []) if v in vorlagen]
            gewaehlt = (user_input.get(CONF_AUSSENTEMPERATUR) or "").strip()
            if gewaehlt:
                options[CONF_AUSSENTEMPERATUR] = gewaehlt
            else:
                options.pop(CONF_AUSSENTEMPERATUR, None)
            return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="allgemein",
            data_schema=vol.Schema(
                {
                    **{
                        vol.Required(
                            schluessel, default=bool(options.get(schluessel, vorgabe))
                        ): bool
                        for schluessel, vorgabe in ALLGEMEINE_SCHALTER
                    },
                    # Vorlagen erscheinen unter Einstellungen → Automationen.
                    # Ohne gespeicherte Auswahl gelten alle als gewählt, damit
                    # eine Aktualisierung keine wegnimmt.
                    vol.Optional(
                        CONF_VORLAGEN,
                        default=list(options.get(CONF_VORLAGEN, vorlagen)),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=kennung, label=woerterbuch_zu(self)(name))
                                for kennung, name in vorlagen.items()
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Optional(
                        CONF_AUSSENTEMPERATUR,
                        description={"suggested_value": options.get(CONF_AUSSENTEMPERATUR, "")},
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                    **self._sprachfelder(options),
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
                    # Startwerte aus dem Lesespeicher der Anlage: wie alt ein
                    # Wert höchstens sein darf, um beim Start zu gelten.
                    vol.Required(
                        CONF_STARTWERTE,
                        default=str(options.get(CONF_STARTWERTE, STARTWERTE_VORGABE)),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=list(STARTWERTE_WAHL),
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="startwerte",
                        )
                    ),
                }
            ),
        )

    async def async_step_system(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bedienebenen und Zugang einer Anlage.

        Der Zugang steht hier, weil man ihn hier sucht: Er bestimmt zusammen
        mit den Bedienebenen, welche Datenpunkte die Anlage überhaupt
        herausgibt. Über *Neu konfigurieren* ist er ebenfalls erreichbar –
        dort zusammen mit der Adresse.
        """
        options = dict(self.config_entry.options)
        host = self._host or ""
        je_anlage = options.get(host) or {}
        systeme = self._systeme()
        system = next((s for s in systeme if s[CONF_HOST] == host), {})

        if user_input is not None:
            benutzer = (user_input.pop(CONF_USERNAME, None) or DEFAULT_USERNAME).strip()
            self._bezeichnung = (user_input.pop(CONF_LABEL, None) or "").strip()
            self._ids_anpassen = bool(user_input.pop(CONF_IDS_ANPASSEN, False))
            gruppen = user_input.pop(CONF_ZUSATZGRUPPEN, [])
            kandidaten = self._zusatzkandidaten(host)
            # Ohne Kandidaten stand das Feld nicht im Formular. Die gespeicherte
            # Auswahl bleibt dann stehen, statt beim Bestätigen wegzufallen.
            if kandidaten:
                user_input[CONF_ZUSATZWERTE] = gruppen_aufloesen(kandidaten, gruppen)
            else:
                user_input[CONF_ZUSATZWERTE] = list(je_anlage.get(CONF_ZUSATZWERTE, []))
            if GRUPPE_INDIVIDUELL in gruppen:
                # Der zweite Schritt zeigt die Einzelwerte, vorbelegt mit dem,
                # was die Gruppen ergeben.
                self._offen = (host, benutzer, normalize_options(user_input))
                return await self.async_step_zusatzwerte()
            options[host] = normalize_options(user_input)
            self._zugang_uebernehmen(host, benutzer, options)
            return self.async_create_entry(data=options)

        label = system.get(CONF_LABEL) or host
        # Die Bezeichnung steht vor jedem Gerätenamen der Anlage; sie lässt sich hier ändern.
        schema = vol.Schema(
            {
                vol.Required(CONF_LABEL, default=label): str,
                vol.Optional(CONF_IDS_ANPASSEN, default=False): bool,
            }
        ).extend(level_schema(je_anlage, mit_intervall=False).schema)
        schema = schema.extend(
            {
                vol.Required(
                    CONF_USERNAME, default=system.get(CONF_USERNAME) or DEFAULT_USERNAME
                ): benutzer_auswahl()
            }
        )
        schema = schema.extend(
            {
                # Fremde Werte gehören nicht in die selbstgebauten Karten. Je
                # Label entsteht eine eigene, abwählbar wie jede andere; wer
                # sie lieber im Systemstatus hat, wählt sie unten dazu.
                vol.Optional(
                    CONF_MARKEN, default=list(je_anlage.get(CONF_MARKEN, []))
                ): LabelSelector(LabelSelectorConfig(multiple=True)),
                vol.Optional(
                    CONF_MARKEN_STATUS, default=list(je_anlage.get(CONF_MARKEN_STATUS, []))
                ): LabelSelector(LabelSelectorConfig(multiple=True)),
            }
        )
        kandidaten = self._zusatzkandidaten(host)
        schema = schema.extend(
            zusatzgruppen_feld(
                kandidaten, gruppen_ableiten(kandidaten, list(je_anlage.get(CONF_ZUSATZWERTE, [])))
            )
        )
        return self.async_show_form(
            step_id="system",
            data_schema=schema,
            description_placeholders={
                "anlage": f"{label} ({host})".strip(),
                "bus_hinweis": self._bus_hinweis(host),
            },
        )

    def _bus_hinweis(self, host: str) -> str:
        """Was die Baureihen dieser Anlage nur über den LON-Bus hergeben.

        Ohne die Aufzählung bliebe im Dialog eine Sammelaussage stehen, die an
        der einen Anlage zutrifft und an der nächsten nicht.
        """
        daten = getattr(self.config_entry, "runtime_data", None) or {}
        coordinator = (daten.get("coordinators") or {}).get(host)
        beschreibungen = getattr(getattr(coordinator, "client", None), "devices", []) or []
        typen = {d.get("fct_type") for d in beschreibungen}
        begriffe: list[str] = []
        for fct_type in sorted(t for t in typen if isinstance(t, int)):
            begriffe.extend(NUR_BUS_JE_FCT.get(fct_type, ()))
        einmalig = list(dict.fromkeys(begriffe))
        if not einmalig:
            return ""
        uebersetzt = woerterbuch_zu(self)
        begriffe_text = ", ".join(uebersetzt(b) for b in einmalig)
        return uebersetzt("Diese Anlage liefert nur über den Bus: {begriffe}.").replace(
            "{begriffe}", begriffe_text
        )

    def _zugang_uebernehmen(self, host: str, benutzer: str, options: dict[str, Any]) -> None:
        """Zugang und Bezeichnung in die Anlagendaten schreiben.

        Sie gehören zur Anmeldung, nicht zu den Optionen. Ein anderer Zugang
        ändert den Umfang und lässt die Anlage neu einlesen.
        """
        systeme = self._systeme()
        vorher = next((s for s in systeme if s[CONF_HOST] == host), {})
        neu = dict(vorher)
        if benutzer != (vorher.get(CONF_USERNAME) or DEFAULT_USERNAME):
            neu[CONF_USERNAME] = benutzer
        if self._bezeichnung:
            neu[CONF_LABEL] = self._bezeichnung
        if self._ids_anpassen and self._bezeichnung:
            alt = vorher.get(CONF_LABEL) or host
            umbenannt = entity_ids_umbenennen(self.hass, self.config_entry, alt, self._bezeichnung)
            # Die gewählte Außentemperatur zieht mit, sonst zeigt sie ins Leere.
            if (aussen := options.get(CONF_AUSSENTEMPERATUR)) in umbenannt:
                options[CONF_AUSSENTEMPERATUR] = umbenannt[aussen]
        if neu == vorher:
            return
        neue = [neu if s[CONF_HOST] == host else s for s in systeme]
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, CONF_SYSTEMS: neue}
        )

    async def async_step_zusatzwerte(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einzelne abgeleitete Werte ankreuzen."""
        host, benutzer, vorgemerkt = self._offen
        kandidaten = self._zusatzkandidaten(host)
        if user_input is not None:
            options = dict(self.config_entry.options)
            options[host] = {
                **vorgemerkt,
                CONF_ZUSATZWERTE: [
                    k
                    for k in user_input.get(CONF_ZUSATZWERTE, [])
                    if k in {c["id"] for c in kandidaten}
                ],
            }
            self._zugang_uebernehmen(host, benutzer, options)
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="zusatzwerte",
            data_schema=vol.Schema(
                zusatzwerte_feld(kandidaten, list(vorgemerkt.get(CONF_ZUSATZWERTE, [])))
            ),
        )

    def _zusatzkandidaten(self, host: str) -> list[dict]:
        """Was diese Anlage an abgeleiteten Werten hergibt.

        Vor dem ersten vollständigen Einlesen ist die Liste leer; das Feld
        entfällt dann, statt eine leere Auswahl zu zeigen.
        """
        daten = getattr(self.config_entry, "runtime_data", None) or {}
        coordinator = (daten.get("coordinators") or {}).get(host)
        return list(getattr(getattr(coordinator, "client", None), "zusatzkandidaten", []) or [])

    def __getattr__(self, name: str):
        """Nummerierte Schritte des Menüs bereitstellen.

        Das Menü führt eine Zeile je Anlage; feste Methoden würden deren Zahl
        begrenzen und bei einer mehr mit „unbekannter Schritt" abbrechen.
        """
        for praefix, ziel in (("async_step_anlage_", self._anlage),):
            if not name.startswith(praefix):
                continue
            rest = name.removeprefix(praefix)
            if not rest.isdigit():
                break

            async def schritt(user_input=None, _ziel=ziel, _index=int(rest)) -> ConfigFlowResult:
                return await _ziel(_index, user_input)

            return schritt
        raise AttributeError(name)

    async def _anlage(self, index: int, user_input) -> ConfigFlowResult:
        """Menüauswahl auf den gemeinsamen Schritt lenken."""
        systeme = self._systeme()
        if index < len(systeme):
            self._host = systeme[index][CONF_HOST]
        return await self.async_step_system(user_input)
