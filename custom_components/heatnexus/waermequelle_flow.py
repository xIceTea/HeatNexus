"""Der Subeintrag für eine Wärmequelle ohne Windhager-Steuerung.

Zwei Schritte: erst Name, Bauart und Bedingungsart, dann nur die Felder der
gewählten Art. Die Regel selbst prüft `bedingung.py`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.selector import (
    EntitySelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from . import bedingung, waermequelle
from .const import CONF_LABEL, CONF_SYSTEMS, QUELLE_SOLAR, QUELLEN_ARTEN, QUELLEN_MAX

# Zustände, die für sich schon an oder aus bedeuten. Alles andere ist
# Klartext: Dort entscheidet die Auswahl, welcher Text als liefernd gilt.
BINAERE_ZUSTAENDE = frozenset({"on", "off", "true", "false"})


# Ersatzzustände von Home Assistant. Als Bedingung gewählt stünde die Quelle
# auf einem Zustand, den sie im Betrieb nie meldet.
OHNE_WAHL = frozenset({"unavailable", "unknown", "none", ""})


def quellen_schema(vorhanden: Mapping[str, Any]) -> vol.Schema:
    """Der erste Schritt: Bauart der Quelle und woran man sie erkennt."""
    regel = dict(vorhanden.get("bedingung") or {})
    return vol.Schema(
        {
            vol.Required("name", default=vorhanden.get("name", "")): str,
            vol.Required("art", default=vorhanden.get("art", QUELLE_SOLAR)): SelectSelector(
                SelectSelectorConfig(
                    options=list(QUELLEN_ARTEN),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="quellenart",
                )
            ),
            vol.Required("pumpe", default=bool(vorhanden.get("pumpe", False))): bool,
            vol.Required(
                "bedingung_art", default=regel.get("art", bedingung.ART_ZUSTAND)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(bedingung.ARTEN),
                    mode=SelectSelectorMode.LIST,
                    translation_key="bedingungsart",
                )
            ),
            vol.Required(
                "quelle", description={"suggested_value": regel.get("quelle")}
            ): EntitySelector(),
        }
    )


def zustandsvorschlaege(hass: Any, entity_id: str | None) -> list[str]:
    """Die Zustände, die eine Entität kennt – als Vorschlag, nicht als Grenze."""
    zustand = hass.states.get(entity_id) if entity_id else None
    if zustand is None:
        return []
    vorschlaege = [
        str(wert)
        for wert in (zustand.attributes.get("options") or [])
        if str(wert).strip().lower() not in OHNE_WAHL
    ]
    jetzt = str(zustand.state)
    if jetzt.strip().lower() not in OHNE_WAHL and jetzt not in vorschlaege:
        vorschlaege.append(jetzt)
    return vorschlaege


def regel_schema(art: str, vorhanden: Mapping[str, Any], vorschlaege: list[str]) -> vol.Schema:
    """Der zweite Schritt: nur die Felder, die zur gewählten Bedingung gehören."""
    regel = dict(vorhanden.get("bedingung") or {})
    if art == bedingung.ART_ZUSTAND:
        gewaehlt = [str(wert) for wert in (regel.get("zustaende") or [])]
        optionen = list(dict.fromkeys([*vorschlaege, *gewaehlt]))
        # Meldet die Entität Klartext, ist die Auswahl Pflicht: Sonst gälte
        # jeder Text als an, auch einer, der „aus" bedeutet.
        klartext = any(wert.lower() not in BINAERE_ZUSTAENDE for wert in optionen)
        feld = vol.Required if klartext else vol.Optional
        return vol.Schema(
            {
                feld(
                    "zustaende", description={"suggested_value": regel.get("zustaende")}
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[SelectOptionDict(value=wert, label=wert) for wert in optionen],
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        custom_value=True,
                    )
                )
            }
        )
    felder: dict[Any, Any] = {}
    if art == bedingung.ART_DIFFERENZ:
        felder[vol.Required("gegen", description={"suggested_value": regel.get("gegen")})] = (
            EntitySelector()
        )
    felder[vol.Required("ein", description={"suggested_value": regel.get("ein")})] = NumberSelector(
        NumberSelectorConfig(mode=NumberSelectorMode.BOX, step="any")
    )
    felder[vol.Optional("aus", description={"suggested_value": regel.get("aus")})] = NumberSelector(
        NumberSelectorConfig(mode=NumberSelectorMode.BOX, step="any")
    )
    return vol.Schema(felder)


def eingabe_als_stand(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Die Eingabe in die Form bringen, die das Formular als Vorgabe liest."""
    return {
        "name": user_input.get("name", ""),
        "art": user_input.get("art", QUELLE_SOLAR),
        "pumpe": bool(user_input.get("pumpe", False)),
        "bedingung": {
            "art": user_input.get("bedingung_art"),
            "quelle": user_input.get("quelle"),
            "gegen": user_input.get("gegen"),
            "ein": user_input.get("ein"),
            "aus": user_input.get("aus"),
            "zustaende": user_input.get("zustaende"),
        },
    }


def stand_zusammenfuehren(
    vorhanden: Mapping[str, Any], user_input: Mapping[str, Any]
) -> dict[str, Any]:
    """Die Eingabe über den bisherigen Stand legen, ohne ihn zu leeren.

    Der erste Schritt fragt die Grenzen nicht ab; beim Ändern stünden sie
    sonst leer im zweiten.
    """
    stand = {**vorhanden, **eingabe_als_stand(user_input)}
    stand["bedingung"] = {
        **dict(vorhanden.get("bedingung") or {}),
        **{name: wert for name, wert in stand["bedingung"].items() if wert is not None},
    }
    return stand


def stand_als_eingabe(stand: Mapping[str, Any]) -> dict[str, Any]:
    """Der gemerkte Stand in der flachen Form des Formulars."""
    regel = dict(stand.get("bedingung") or {})
    return {
        "name": stand.get("name", ""),
        "art": stand.get("art", QUELLE_SOLAR),
        "pumpe": bool(stand.get("pumpe", False)),
        "bedingung_art": regel.get("art"),
        "quelle": regel.get("quelle"),
        "gegen": regel.get("gegen"),
        "ein": regel.get("ein"),
        "aus": regel.get("aus"),
        "zustaende": regel.get("zustaende"),
    }


def quelle_aus_eingabe(
    user_input: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Die Eingabe zu einer Wärmequelle machen, oder die Fehler nennen."""
    regel = {
        "art": user_input.get("bedingung_art"),
        "quelle": user_input.get("quelle"),
        "gegen": user_input.get("gegen"),
        "ein": user_input.get("ein"),
        "aus": user_input.get("aus"),
        "zustaende": user_input.get("zustaende"),
    }
    if not bedingung.vollstaendig(regel):
        return None, {"base": "bedingung_unvollstaendig"}
    art = user_input.get("art", QUELLE_SOLAR)
    return {
        # Ein leerer Name ließe den Subeintrag ohne Titel in der Übersicht
        # stehen. Die Bauart benennt die Quelle dann für ihn.
        "name": (user_input.get("name") or "").strip() or QUELLEN_ARTEN.get(art, "Wärmequelle"),
        "art": art,
        "pumpe": bool(user_input.get("pumpe", False)),
        "bedingung": waermequelle.bedingung_pruefen(regel),
    }, {}


class WaermequelleSubentryFlow(ConfigSubentryFlow):
    """Eine Wärmequelle anlegen oder ändern.

    Sie gehört zu einer Anlage; steht nur eine im Eintrag, entfällt die Frage.
    """

    def __init__(self) -> None:
        """Anlage, Richtung des Ablaufs und was der erste Schritt ergab."""
        self._host: str = ""
        self._aendern: bool = False
        self._stand: dict[str, Any] = {}

    def _systeme(self) -> list[dict[str, Any]]:
        return self._get_entry().data.get(CONF_SYSTEMS, [])

    def _vorhandene_quellen(self) -> list[dict[str, Any]]:
        """Die schon angelegten Quellen – ihre Kennungen bleiben vergeben."""
        return [dict(sub.data or {}) for sub in waermequelle.subeintraege(self._get_entry())]

    def _quellen_der_anlage(self) -> list[dict[str, Any]]:
        """Die Quellen dieser Anlage – mehr fasst ihr Schaubild nicht."""
        return [q for q in self._vorhandene_quellen() if q.get(CONF_HOST) == self._host]

    def _bezeichnung(self, host: str) -> str:
        system = next((s for s in self._systeme() if s[CONF_HOST] == host), {})
        return system.get(CONF_LABEL) or host

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Zu welcher Anlage die neue Quelle gehört."""
        systeme = self._systeme()
        if len(systeme) == 1:
            self._host = systeme[0][CONF_HOST]
            return await self.async_step_quelle()
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            return await self.async_step_quelle()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=system[CONF_HOST],
                                    label=self._bezeichnung(system[CONF_HOST]),
                                )
                                for system in systeme
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Eine vorhandene Quelle ändern."""
        self._aendern = True
        self._host = str(self._get_reconfigure_subentry().data.get(CONF_HOST) or "")
        return await self.async_step_quelle(user_input)

    async def async_step_quelle(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Bauart der Quelle und die Entität, an der man sie erkennt."""
        vorhanden: dict[str, Any] = {}
        if self._aendern:
            sub = self._get_reconfigure_subentry()
            vorhanden = {"name": sub.title, **(sub.data or {})}
        elif len(self._quellen_der_anlage()) >= QUELLEN_MAX:
            return self.async_abort(reason="zu_viele")

        errors: dict[str, str] = {}
        if user_input is not None:
            self._stand = stand_zusammenfuehren(vorhanden, user_input)
            if str(self._stand.get("name") or "").strip():
                return await self.async_step_regel()
            errors = {"name": "name_fehlt"}
            vorhanden = self._stand

        return self.async_show_form(
            step_id="quelle",
            data_schema=quellen_schema(vorhanden),
            errors=errors,
            description_placeholders={"anlage": self._bezeichnung(self._host)},
        )

    async def async_step_regel(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Wann die Quelle liefert. Jede Bedingungsart fragt eigene Felder ab."""
        regel = dict(self._stand.get("bedingung") or {})
        errors: dict[str, str] = {}
        if user_input is not None:
            eingabe = {**stand_als_eingabe(self._stand), **user_input}
            quelle, errors = quelle_aus_eingabe(eingabe)
            if quelle is not None:
                return self._sichern(quelle)
            # Nach einem Fehler steht wieder da, was eingegeben wurde.
            self._stand = stand_zusammenfuehren(self._stand, eingabe)
            regel = dict(self._stand.get("bedingung") or {})

        return self.async_show_form(
            step_id="regel",
            data_schema=regel_schema(
                str(regel.get("art") or ""),
                self._stand,
                zustandsvorschlaege(self.hass, regel.get("quelle")),
            ),
            errors=errors,
            description_placeholders={"quelle": self._quellenname(regel.get("quelle"))},
        )

    def _quellenname(self, entity_id: str | None) -> str:
        """Wie die Entität heißt, die über die Quelle entscheidet."""
        zustand = self.hass.states.get(entity_id) if entity_id else None
        if zustand is None:
            return str(entity_id or "")
        return str(zustand.attributes.get("friendly_name") or entity_id)

    def _sichern(self, quelle: dict[str, Any]) -> SubentryFlowResult:
        """Die fertige Quelle ablegen und die Anlage neu laden.

        Die Plattformen lesen die Subeinträge beim Einrichten. Ohne Neuladen
        entstünde die Entität der Quelle erst beim nächsten Start.
        """
        eintrag = self._get_entry()
        vorhanden = dict(self._get_reconfigure_subentry().data or {}) if self._aendern else {}
        daten = {
            CONF_HOST: self._host,
            "id": vorhanden.get("id") or waermequelle.quelle_id(self._vorhandene_quellen()),
            "art": quelle["art"],
            "pumpe": quelle["pumpe"],
            "bedingung": quelle["bedingung"],
        }
        if self._aendern:
            ergebnis = self.async_update_and_abort(
                eintrag,
                self._get_reconfigure_subentry(),
                title=quelle["name"],
                data=daten,
            )
        else:
            ergebnis = self.async_create_entry(title=quelle["name"], data=daten)
        self.hass.config_entries.async_schedule_reload(eintrag.entry_id)
        return ergebnis
