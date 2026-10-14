"""Quittung der Wartungsarbeiten (`39/94`), gleich an PuroWIN und BioWIN."""

from __future__ import annotations

# „Reinigung bestätigen" (39/94) ist am Gerät eine Auswahlliste aus vier
# Arbeiten. Je Arbeit eine eigene Taste ist eindeutig, eine Liste lädt zum
# Fehlgriff ein.
# Die Restlaufzeiten, die eine Quittung zurücksetzt: PuroWIN `39/91–93`,
# BioWIN `20/61–63`. Gelesen wird nur, was der Kessel führt.
ZAEHLER = ("39/91", "39/92", "39/93", "20/61", "20/62", "20/63")

TASTEN: list[dict] = [
    {
        "oid": "/39/94/0",
        "name": "Reinigung durchgeführt",
        "platform": "button",
        "nachlesen": ZAEHLER,
        "press_value": "1",
        "key_suffix": "reinigung",
        "category": "config",
        "icon": "mdi:broom",
    },
    {
        "oid": "/39/94/0",
        "name": "Hauptreinigung durchgeführt",
        "platform": "button",
        "nachlesen": ZAEHLER,
        "press_value": "2",
        "key_suffix": "hauptreinigung",
        "category": "config",
        "icon": "mdi:broom",
    },
    {
        "oid": "/39/94/0",
        "name": "Wartung durchgeführt",
        "platform": "button",
        "nachlesen": ZAEHLER,
        "press_value": "3",
        "key_suffix": "wartung",
        "category": "config",
        "icon": "mdi:wrench-check-outline",
    },
    {
        "oid": "/39/94/0",
        "name": "Hauptreinigung und Aschetonnen durchgeführt",
        "platform": "button",
        "nachlesen": ZAEHLER,
        "press_value": "4",
        "key_suffix": "hauptreinigung_asche",
        "category": "config",
        "icon": "mdi:delete-empty-outline",
    },
]
