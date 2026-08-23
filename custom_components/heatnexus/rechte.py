"""Wer welche Entität sehen darf.

Die Oberfläche baut ihren Abzug auf dem Server und läse die Zustandstabelle
sonst ungefiltert. Home Assistant führt die Rechte am Benutzer der Verbindung;
hier werden sie angewandt.
"""

from __future__ import annotations

from typing import Any

from homeassistant.auth.permissions.const import POLICY_READ


def darf_lesen(benutzer: Any, entity_id: str) -> bool:
    """Ob dieser Benutzer die Adresse lesen darf.

    Ohne Benutzer gilt keine Einschränkung: Dann kommt der Aufruf nicht von
    einer Verbindung, sondern aus der Integration selbst.
    """
    rechte = getattr(benutzer, "permissions", None)
    if rechte is None:
        return True
    return bool(rechte.check_entity(entity_id, POLICY_READ))
