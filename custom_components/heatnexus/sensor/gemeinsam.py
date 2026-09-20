"""Was mehrere Sensormodule brauchen: Klassenzuordnung und der gespeicherte Zustand."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

STATE_CLASS_MAP = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total": SensorStateClass.TOTAL,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}

# Geräteklassen, die aus der Einheitentabelle kommen können. Was Home Assistant
# nicht kennt, bleibt lieber ohne Klasse als mit einer falschen.
DEVICE_CLASSES = {klasse.value for klasse in SensorDeviceClass}


def zahl_aus_zustand(zustand: str | None) -> float | None:
    """Einen gespeicherten Zustand als Zahl lesen (oder gar nicht)."""
    if zustand is None:
        return None
    try:
        return float(zustand)
    except (TypeError, ValueError):
        return None
