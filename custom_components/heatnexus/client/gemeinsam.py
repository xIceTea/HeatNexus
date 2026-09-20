"""Was mehrere Teile des Client-Pakets brauchen."""

from __future__ import annotations

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
