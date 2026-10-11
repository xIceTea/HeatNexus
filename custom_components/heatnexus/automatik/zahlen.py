"""Zahlen und Abweichungen als Text, wie Panel, Begründung und Benachrichtigung sie schreiben."""

from __future__ import annotations

MINUS = "\u2212"


def zahl(wert: float, punkt: bool = False, stellen: int | None = None) -> str:
    """Ohne `stellen` ganze Zahlen ohne Nachkommastelle, sonst eine; negativ mit echtem Minus."""
    if stellen is None:
        stellen = 0 if float(wert).is_integer() else 1
    text = f"{wert:.{stellen}f}"
    return (text if punkt else text.replace(".", ",")).replace("-", MINUS)


def kelvin(wert: float | None, punkt: bool = False) -> str:
    """Eine Abweichung mit Vorzeichen und einer Nachkommastelle; um null „±“."""
    if wert is None:
        return "–"
    v = round(wert, 1)
    zeichen = "+" if v > 0 else MINUS if v < 0 else "±"
    return f"{zeichen}{zahl(abs(v), punkt, 1)} K"
