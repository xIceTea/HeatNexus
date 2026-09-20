"""Formulare und Prüfungen der Einrichtung: Adresse, Zugang, Bedienebenen, Zusatzwerte.

`config_flow.py` führt die Abläufe; was ein Schritt anzeigt und wie seine
Eingabe geprüft wird, steht hier.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

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
    COMFORT_TEMP_STANDARD,
    CONF_COMFORT_DAUER,
    CONF_COMFORT_TEMP,
    CONF_DASHBOARD,
    CONF_ECO_DAUER,
    CONF_ECO_TEMP,
    CONF_ENABLE_ADVANCED,
    CONF_KESSELART,
    CONF_KESSELWERT,
    CONF_LEVELS,
    CONF_LON,
    CONF_LON_GRUNDUMFANG,
    CONF_MARKEN,
    CONF_MARKEN_STATUS,
    CONF_MODULPUMPE,
    CONF_PANEL,
    CONF_UPDATE_INTERVAL,
    CONF_WRITABLE_ADVANCED,
    CONF_ZEITWERTE,
    CONF_ZUSATZGRUPPEN,
    CONF_ZUSATZWERTE,
    DEFAULT_LEVELS,
    DEFAULT_USERNAME,
    ECO_TEMP_STANDARD,
    GRUPPE_INDIVIDUELL,
    KESSELART_AUTO,
    KESSELART_BESCHRIFTUNG,
    KESSELARTEN,
    KESSELWERT_BESCHRIFTUNG,
    KESSELWERT_LEISTUNG,
    KESSELWERTE,
    LEVEL_BESCHRIFTUNG,
    LEVEL_INFO,
    LEVEL_OPERATE,
    MARKEN_MAX_KARTEN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    UEBERSTEUERUNG_DAUER_STANDARD,
    UPDATE_INTERVAL,
    ZUSATZGRUPPEN,
)
from .exceptions import CannotConnect, InvalidAuth


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
        # Schaltzeiten, Urlaubsende, Systemuhr: Einstellwerte, die man einmal
        # anfasst. Ohne Haken werden sie deaktiviert angelegt und kosten keinen
        # Abruf; wer sie alle braucht, setzt ihn hier statt jede Entität
        # einzeln einzuschalten.
        vol.Required(CONF_ZEITWERTE, default=bool(defaults.get(CONF_ZEITWERTE, False))): bool,
        # Der LON-Adressraum. Ab Werk aus: Wo der Kessel viele Datenpunkte
        # meldet, ergänzt der Bus fast nichts (gemessen: PuroWIN 12 Werte
        # ohne Entsprechung, davon die meisten Bus-Verwaltung). Wo er wenige
        # meldet, ist es der einzige Weg zu Gebläsedrehzahl, Lambdasonde
        # und Pelletsvorrat.
        vol.Required(CONF_LON, default=bool(defaults.get(CONF_LON, False))): bool,
        # Der Aufbau der Anlage gehört zum Grundumfang: Ob ein Modul seine
        # Pumpe als Datenpunkt führt, entscheidet die Baureihe, und ohne sie
        # fehlte im Schaubild ein Bauteil, das es gibt.
        vol.Required(
            CONF_LON_GRUNDUMFANG,
            default=bool(defaults.get(CONF_LON_GRUNDUMFANG, True)),
        ): bool,
        # Wirkt nur auf die Zeichnung im Schaubild. Steht trotzdem hier bei
        # der Anlage und nicht in den allgemeinen Einstellungen: Zwei Anlagen
        # in einem Eintrag können verschiedene Wärmeerzeuger haben.
        vol.Required(
            CONF_KESSELART, default=defaults.get(CONF_KESSELART, KESSELART_AUTO)
        ): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=art, label=KESSELART_BESCHRIFTUNG[art])
                    for art in KESSELARTEN
                ],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="kesselart",
            )
        ),
        # Welcher zweite Wert am Kessel steht. Das Glutbett richtet sich
        # weiterhin nach der Leistung; die Wahl betrifft nur die Anzeige.
        vol.Required(
            CONF_KESSELWERT, default=defaults.get(CONF_KESSELWERT, KESSELWERT_LEISTUNG)
        ): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=wert, label=KESSELWERT_BESCHRIFTUNG[wert])
                    for wert in KESSELWERTE
                ],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="kesselwert",
            )
        ),
        # Ein Pumpen-/Relaismodul meldet seine Drehzahl auch dann, wenn keine
        # Pumpe daran hängt. Erst der Haken bringt sie ins Schaubild; das Modul
        # selbst und seine Lampen stehen unabhängig davon im Bild.
        vol.Required(CONF_MODULPUMPE, default=bool(defaults.get(CONF_MODULPUMPE, False))): bool,
    }
    if mit_intervall:
        felder[vol.Required(CONF_DASHBOARD, default=bool(defaults.get(CONF_DASHBOARD, True)))] = (
            bool
        )
        felder[vol.Required(CONF_PANEL, default=bool(defaults.get(CONF_PANEL, False)))] = bool
        # Eco und Comfort: die befristete Übersteuerung, die auch das
        # Bediengerät schreibt. Die Werte gelten für alle Heizkreise – die
        # Anlage kennt je Kreis nur einen Übersteuerungswert, zwei getrennte
        # Vorgaben je Kreis hätten dort nichts, worin sie stehen könnten.
        for schluessel, vorgabe, einheit, kleinst, groesst in (
            (CONF_ECO_TEMP, ECO_TEMP_STANDARD, "°C", 6, 30),
            (CONF_ECO_DAUER, UEBERSTEUERUNG_DAUER_STANDARD, "min", 0, 400),
            (CONF_COMFORT_TEMP, COMFORT_TEMP_STANDARD, "°C", 6, 30),
            (CONF_COMFORT_DAUER, UEBERSTEUERUNG_DAUER_STANDARD, "min", 0, 400),
        ):
            felder[vol.Required(schluessel, default=float(defaults.get(schluessel, vorgabe)))] = (
                NumberSelector(
                    NumberSelectorConfig(
                        min=kleinst,
                        max=groesst,
                        step=0.5 if einheit == "°C" else 5,
                        unit_of_measurement=einheit,
                        mode=NumberSelectorMode.BOX,
                    )
                )
            )
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


def zusatzgruppen_feld(kandidaten: list[dict], gewaehlt: list[str]) -> dict:
    """Auswahl der abgeleiteten Werte, nach Herkunft gruppiert.

    Angeboten wird nur, was diese Anlage hergibt; „Individuell" öffnet den
    zweiten Schritt mit den Einzelwerten.
    """
    vorhanden = [g for g in ZUSATZGRUPPEN if any(k.get("gruppe") == g for k in kandidaten)]
    if not vorhanden:
        return {}
    optionen = [SelectOptionDict(value=g, label=ZUSATZGRUPPEN[g]) for g in vorhanden]
    optionen.append(
        SelectOptionDict(value=GRUPPE_INDIVIDUELL, label="Individuell – weiter zur Einzelauswahl")
    )
    return {
        vol.Optional(CONF_ZUSATZGRUPPEN, default=gewaehlt): SelectSelector(
            SelectSelectorConfig(options=optionen, multiple=True, mode=SelectSelectorMode.LIST)
        )
    }


def zusatzwerte_feld(kandidaten: list[dict], gewaehlt: list[str]) -> dict:
    """Die Einzelwerte zum Ankreuzen – der zweite Schritt hinter „Individuell"."""
    if not kandidaten:
        return {}
    bekannt = {k["id"] for k in kandidaten}
    return {
        vol.Optional(
            CONF_ZUSATZWERTE, default=[k for k in gewaehlt if k in bekannt]
        ): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=k["id"], label=k["name"])
                    for k in sorted(kandidaten, key=lambda k: k["name"])
                ],
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )
    }


def gruppen_aufloesen(kandidaten: list[dict], gruppen: list[str]) -> list[str]:
    """Welche Einzelwerte die angekreuzten Gruppen ergeben."""
    return [k["id"] for k in kandidaten if k.get("gruppe") in gruppen]


def gruppen_ableiten(kandidaten: list[dict], gewaehlt: list[str]) -> list[str]:
    """Welche Gruppen zu einer gespeicherten Auswahl passen.

    Eine Gruppe erscheint, sobald **einer** ihrer Werte gewählt ist. Nur die
    vollständig gewählten sind damit erledigt; bleibt etwas übrig, steht
    zusätzlich „Individuell".
    """
    aktiv = set(gewaehlt)
    gruppen = []
    abgedeckt: set[str] = set()
    for gruppe in ZUSATZGRUPPEN:
        kennungen = {k["id"] for k in kandidaten if k.get("gruppe") == gruppe}
        if not kennungen or not kennungen & aktiv:
            continue
        # Auch bei einer Teilauswahl vorangekreuzt: Bliebe die Gruppe leer,
        # schriebe das nächste Bestätigen ihren Inhalt weg.
        gruppen.append(gruppe)
        if kennungen <= aktiv:
            abgedeckt |= kennungen
    if aktiv - abgedeckt:
        gruppen.append(GRUPPE_INDIVIDUELL)
    return gruppen


def normalize_options(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Eingaben zu den Bedienebenen prüfen und vereinheitlichen."""
    levels = [lvl for lvl in raw.get(CONF_LEVELS, DEFAULT_LEVELS) if lvl in ALL_LEVELS]
    # Ohne Info- und Betreiberebene bliebe die Anlage stumm bzw. unbedienbar.
    for pflicht in (LEVEL_INFO, LEVEL_OPERATE):
        if pflicht not in levels:
            levels.append(pflicht)
    kesselart = raw.get(CONF_KESSELART, KESSELART_AUTO)
    kesselwert = raw.get(CONF_KESSELWERT, KESSELWERT_LEISTUNG)
    # Labels gelten je Anlage; in den Systemstatus kommt nur, was die
    # Kartenauswahl auch zeigt.
    marken = [str(k) for k in raw.get(CONF_MARKEN, [])][:MARKEN_MAX_KARTEN]
    im_status = {str(k) for k in raw.get(CONF_MARKEN_STATUS, [])}
    ergebnis: dict[str, Any] = {
        CONF_LEVELS: [lvl for lvl in ALL_LEVELS if lvl in levels],
        CONF_ENABLE_ADVANCED: bool(raw.get(CONF_ENABLE_ADVANCED, False)),
        CONF_WRITABLE_ADVANCED: bool(raw.get(CONF_WRITABLE_ADVANCED, False)),
        CONF_ZEITWERTE: bool(raw.get(CONF_ZEITWERTE, False)),
        CONF_LON: bool(raw.get(CONF_LON, False)),
        CONF_LON_GRUNDUMFANG: bool(raw.get(CONF_LON_GRUNDUMFANG, True)),
        # Kennungen der abgeleiteten Werte, die eingeschaltet sein sollen.
        CONF_ZUSATZWERTE: [str(k) for k in raw.get(CONF_ZUSATZWERTE, [])][:200],
        CONF_KESSELART: kesselart if kesselart in KESSELARTEN else KESSELART_AUTO,
        CONF_KESSELWERT: (kesselwert if kesselwert in KESSELWERTE else KESSELWERT_LEISTUNG),
        CONF_MODULPUMPE: bool(raw.get(CONF_MODULPUMPE, False)),
        CONF_MARKEN: marken,
        CONF_MARKEN_STATUS: [k for k in marken if k in im_status],
    }
    if CONF_UPDATE_INTERVAL in raw:
        ergebnis[CONF_UPDATE_INTERVAL] = int(raw[CONF_UPDATE_INTERVAL])
    if CONF_DASHBOARD in raw:
        ergebnis[CONF_DASHBOARD] = bool(raw[CONF_DASHBOARD])
    if CONF_PANEL in raw:
        ergebnis[CONF_PANEL] = bool(raw[CONF_PANEL])
    for schluessel in (CONF_ECO_TEMP, CONF_ECO_DAUER, CONF_COMFORT_TEMP, CONF_COMFORT_DAUER):
        if schluessel in raw:
            ergebnis[schluessel] = float(raw[schluessel])
    return ergebnis
