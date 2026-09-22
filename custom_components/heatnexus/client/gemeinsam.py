"""Was mehrere Teile des Client-Pakets brauchen."""

from __future__ import annotations

# Die Ebenenliste in der Reihenfolge, in der eine Adresse ihre Ebene bekommt.
# `overview` ist die Titelseite des Herstellers: Sie hebt eine Adresse aus
# Service- oder Werksebene auf `info`, an info und operate ändert sie nichts.
EBENENFOLGE: tuple[tuple[str, str], ...] = (
    ("info", "info"),
    ("operate", "operate"),
    ("overview", "info"),
    ("service", "service"),
    ("oem", "oem"),
)


def gnmn_aus_oid(oid: str | None) -> str | None:
    """`gn/mn` aus einer vollständigen OID, mit oder ohne Funktionsteil."""
    teile = str(oid or "").strip("/").split("/")
    return "/".join(teile[-3:-1]) if len(teile) >= 3 else None


def gelesene_ebenen(levels) -> list[str]:
    """Die Listen der Datenbank, die zu den gewählten Ebenen gehören."""
    return [*levels, "overview"] if "info" in levels else list(levels)


# Rückgabe eines Abrufs, der die Anlage nicht erreicht hat. Zu unterscheiden
# von ``None``: Das ist die Auskunft der Anlage, dass sie keinen Wert führt.
FEHLGESCHLAGEN = object()

# Was ein Knoten aus seiner Meldung (`FExxmsg`) hergibt: Kennungs-Endung,
# Typ, Name, Symbol. Das Ja/Nein neben dem Klartext macht die Störung für
# Automationen auswählbar – eine Entitätsauswahl filtert nach Geräteklasse.
MELDUNGS_SENSOREN = (
    ("fe01", "device_status", "Meldung", "mdi:message-alert-outline"),
    ("fe01text", "message_text", "Meldung Klartext", "mdi:alert-circle-outline"),
    ("fe01stoerung", "stoerung", "Störung gemeldet", "mdi:alert"),
    ("fe01liste", "message_list", "Meldungsliste", "mdi:format-list-bulleted"),
)
