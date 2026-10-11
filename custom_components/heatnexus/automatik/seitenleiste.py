"""Benachrichtigungen der Automatik in der Seitenleiste, je Art und Heizkreis eine."""

from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant

from ..const import DOMAIN, PANEL_URL


def kennung(art: str, device_id: str) -> str:
    """Die Kennung der Benachrichtigung einer Art und eines Heizkreises."""
    return f"{DOMAIN}_{art}_{device_id}"


def melden(
    hass: HomeAssistant, art: str, device_id: str, titel: str, text: str, verweis: str
) -> None:
    """Text mit einem Verweis auf das Panel; eine ältere Meldung derselben Art wird ersetzt."""
    persistent_notification.async_create(
        hass,
        f"{text}\n\n[{verweis}](/{PANEL_URL})",
        title=titel,
        notification_id=kennung(art, device_id),
    )


def entfernen(hass: HomeAssistant, art: str, device_id: str) -> None:
    """Die Benachrichtigung einer Art aus der Seitenleiste nehmen."""
    persistent_notification.async_dismiss(hass, kennung(art, device_id))
