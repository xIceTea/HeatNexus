"""Exceptions for Windhager integration."""

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


class WindhagerError(HomeAssistantError):
    """Base exception for Windhager integration."""

    pass


class CannotConnect(WindhagerError):
    """Error to indicate we cannot connect."""

    pass


class InvalidAuth(WindhagerError):
    """Error to indicate there is invalid auth."""

    pass


class WindhagerValueError(ServiceValidationError):
    """Eine Eingabe, die so nicht an die Anlage gehen kann.

    Bewusst `ServiceValidationError` und nicht `HomeAssistantError`: Ein
    falscher Wochentag oder eine Uhrzeit ohne Doppelpunkt ist keine Störung der
    Integration. Home Assistant zeigt die Meldung dann als Hinweis am Dienst,
    statt einen Stapelauszug ins Protokoll zu schreiben.
    """

    pass
