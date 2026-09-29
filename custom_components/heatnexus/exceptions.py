"""Exceptions for Windhager integration."""

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN


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


class WindhagerWriteError(WindhagerError):
    """Die Anlage hat einen Schreibvorgang abgelehnt.

    Bewusst ein `HomeAssistantError`: Sonst erscheint der Fehlschlag als
    Stapelauszug von aiohttp statt als Meldung an der bedienten Entität.
    """

    pass


def mit_text[F: HomeAssistantError](klasse: type[F], schluessel: str, **werte: object) -> F:
    """Ein Fehler, dessen Meldung Home Assistant in der Sprache des Nutzers zeigt.

    Die Texte stehen unter `exceptions` in `translations/`.
    """
    return klasse(
        translation_domain=DOMAIN,
        translation_key=schluessel,
        translation_placeholders={name: str(wert) for name, wert in werte.items()},
    )
