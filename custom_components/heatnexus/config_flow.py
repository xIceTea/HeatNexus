"""Einrichtung der Integration über die Oberfläche.

Ein Konfigurationseintrag bündelt eine Heizungsanlage, die aus mehreren
Steuerungen bestehen kann (z.B. Heizhaus und Wohnhaus mit je eigener
Adresse). In Home Assistant erscheint das als ein Gerät mit Untergeräten.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
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
import voluptuous as vol

from .blueprints import verfuegbare as verfuegbare_vorlagen
from .const import (
    CONF_AUSSENTEMPERATUR,
    CONF_COUNT,
    CONF_DASHBOARD,
    CONF_HILFE,
    CONF_LABEL,
    CONF_MARKEN,
    CONF_MARKEN_STATUS,
    CONF_MELDUNG_EINLESEN,
    CONF_PANEL,
    CONF_SPRACHE,
    CONF_STARTWERTE,
    CONF_SYSTEMS,
    CONF_UPDATE_INTERVAL,
    CONF_VORLAGEN,
    CONF_ZUSATZGRUPPEN,
    CONF_ZUSATZWERTE,
    DEFAULT_USERNAME,
    DOMAIN,
    GRUPPE_INDIVIDUELL,
    MAX_SYSTEMS,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    NUR_BUS_JE_FCT,
    SPRACHE_BESCHRIFTUNG,
    STARTWERTE_VORGABE,
    STARTWERTE_WAHL,
    SUBEINTRAG_QUELLE,
    UPDATE_INTERVAL,
)
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
from .geraetetexte import SPRACHEN, sprache_aufloesen
from .waermequelle_flow import WaermequelleSubentryFlow

_LOGGER = logging.getLogger(__name__)


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
            # Der Zugang lässt sich hier mitändern. „Service" sieht
            # Datenpunkte, die „USER" gar nicht erst geliefert bekommt –
            # bisher kam man an diese Umstellung nur über eine fehlgeschlagene
            # Anmeldung heran.
            benutzer = (
                user_input.get(CONF_USERNAME) or system.get(CONF_USERNAME) or DEFAULT_USERNAME
            ).strip()
            try:
                await validate_connection(neu_host, passwort, benutzer)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                neu = [
                    {**s, CONF_HOST: neu_host, CONF_USERNAME: benutzer}
                    if s[CONF_HOST] == alt
                    else s
                    for s in systeme
                ]
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
                    vol.Required(
                        CONF_USERNAME,
                        default=(systeme[0].get(CONF_USERNAME) if systeme else DEFAULT_USERNAME)
                        or DEFAULT_USERNAME,
                    ): benutzer_auswahl(),
                }
            ),
            errors=errors,
        )

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


class WindhagerOptionsFlow(OptionsFlow):
    """Umfang je Anlage und Abfrageintervall nachträglich ändern."""

    def __init__(self) -> None:
        """Zwischenstand."""
        self._host: str | None = None
        # Anlage, Zugang und schon geprüfte Optionen, während der zweite
        # Schritt für die Einzelwerte offen ist.
        self._offen: tuple[str, str, dict[str, Any]] | None = None

    def _systeme(self) -> list[dict[str, Any]]:
        return self.config_entry.data.get(CONF_SYSTEMS, [])

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Auswahl: allgemeine Einstellungen oder eine bestimmte Anlage."""
        systeme = self._systeme()
        # Das Menü erscheint auch bei einer einzigen Anlage. Sprang der Dialog
        # dort direkt zur Anlage, war der Schritt „Allgemeine Einstellungen"
        # nach der Einrichtung nie wieder erreichbar – und mit ihm Sprache,
        # Dashboard, Panel, Erklärungen, Außentemperatur und Abfrageintervall.
        auswahl = {"allgemein": "Allgemein (Oberfläche, Sprache, Abfrage)"}
        for i, system in enumerate(systeme):
            bezeichnung = system.get(CONF_LABEL) or system[CONF_HOST]
            auswahl[f"anlage_{i}"] = f"{bezeichnung} ({system[CONF_HOST]})"
        return self.async_show_menu(step_id="init", menu_options=auswahl)

    async def async_step_allgemein(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abfrageintervall für alle Anlagen."""
        options = dict(self.config_entry.options)
        if user_input is not None:
            options[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL])
            options[CONF_STARTWERTE] = int(user_input.get(CONF_STARTWERTE, STARTWERTE_VORGABE))
            options[CONF_DASHBOARD] = bool(user_input[CONF_DASHBOARD])
            options[CONF_PANEL] = bool(user_input[CONF_PANEL])
            # .get statt [] – ein fehlendes Feld darf den Dialog nicht mit
            # „Unknown error occurred“ abbrechen lassen.
            options[CONF_MELDUNG_EINLESEN] = bool(user_input.get(CONF_MELDUNG_EINLESEN, False))
            options[CONF_HILFE] = bool(user_input.get(CONF_HILFE, True))
            options[CONF_SPRACHE] = user_input.get(CONF_SPRACHE, "de")
            options[CONF_VORLAGEN] = [
                v for v in user_input.get(CONF_VORLAGEN, []) if v in verfuegbare_vorlagen()
            ]
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
                    vol.Required(
                        CONF_DASHBOARD, default=bool(options.get(CONF_DASHBOARD, True))
                    ): bool,
                    vol.Required(CONF_PANEL, default=bool(options.get(CONF_PANEL, False))): bool,
                    vol.Required(CONF_HILFE, default=bool(options.get(CONF_HILFE, True))): bool,
                    vol.Required(
                        CONF_MELDUNG_EINLESEN,
                        default=bool(options.get(CONF_MELDUNG_EINLESEN, False)),
                    ): bool,
                    # Vorlagen erscheinen unter Einstellungen → Automationen.
                    # Ohne gespeicherte Auswahl gelten alle als gewählt, damit
                    # eine Aktualisierung keine wegnimmt.
                    vol.Optional(
                        CONF_VORLAGEN,
                        default=list(options.get(CONF_VORLAGEN, verfuegbare_vorlagen())),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=kennung, label=name)
                                for kennung, name in verfuegbare_vorlagen().items()
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Optional(
                        CONF_AUSSENTEMPERATUR,
                        description={"suggested_value": options.get(CONF_AUSSENTEMPERATUR, "")},
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                    # Woher die Bezeichnungen kommen. „Automatisch" steht nicht
                    # zur Wahl, gilt als gespeicherter Wert aber weiter und
                    # bedeutet Deutsch – dafür die Auflösung in der Vorwahl.
                    vol.Required(
                        CONF_SPRACHE,
                        default=sprache_aufloesen(options.get(CONF_SPRACHE), None),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=wahl, label=SPRACHE_BESCHRIFTUNG[wahl])
                                for wahl in SPRACHEN
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="sprache",
                        )
                    ),
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
            self._zugang_uebernehmen(host, benutzer)
            return self.async_create_entry(data=options)

        label = system.get(CONF_LABEL) or host
        schema = level_schema(je_anlage, mit_intervall=False)
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
        return "Diese Anlage liefert nur über den Bus: " + ", ".join(einmalig) + "."

    def _zugang_uebernehmen(self, host: str, benutzer: str) -> None:
        """Einen geänderten Zugang in die Anlagendaten schreiben.

        Er gehört zur Anmeldung, nicht zu den Optionen. Ein Wechsel ändert den
        Umfang und lässt die Anlage neu einlesen.
        """
        systeme = self._systeme()
        vorher = next((s for s in systeme if s[CONF_HOST] == host), {})
        if benutzer == (vorher.get(CONF_USERNAME) or DEFAULT_USERNAME):
            return
        neue = [{**s, CONF_USERNAME: benutzer} if s[CONF_HOST] == host else s for s in systeme]
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
            self._zugang_uebernehmen(host, benutzer)
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
