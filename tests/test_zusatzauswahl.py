"""Die Auswahl der abgeleiteten Werte, nach Gruppen.

Die Auswahl schreibt die Vereinigung der angekreuzten Gruppen. Wird eine
teilweise gewählte Gruppe nicht vorangekreuzt, verschwindet ihr Inhalt beim
nächsten Bestätigen, ohne dass jemand etwas abgewählt hätte.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def flow():
    from custom_components.heatnexus import config_flow

    return config_flow


def _kandidaten():
    return [
        {"id": "a", "name": "Laufzeit", "gruppe": "laufzeit"},
        {"id": "b", "name": "Laufzeit heute", "gruppe": "laufzeit"},
        {"id": "c", "name": "Brennerstarts heute", "gruppe": "zaehler"},
        {"id": "d", "name": "Abstand bis Ladung", "gruppe": "schaltpunkt"},
    ]


def test_eine_teilweise_gewaehlte_gruppe_bleibt_angekreuzt(flow):
    """Sonst fällt sie beim nächsten Bestätigen still heraus."""
    gruppen = flow.gruppen_ableiten(_kandidaten(), ["a"])

    assert "laufzeit" in gruppen


def test_eine_teilauswahl_nennt_zusaetzlich_die_einzelauswahl(flow):
    """Damit sichtbar bleibt, dass nicht die ganze Gruppe gewählt ist."""
    gruppen = flow.gruppen_ableiten(_kandidaten(), ["a"])

    assert flow.GRUPPE_INDIVIDUELL in gruppen


def test_eine_ganz_gewaehlte_gruppe_braucht_keine_einzelauswahl(flow):
    gruppen = flow.gruppen_ableiten(_kandidaten(), ["a", "b"])

    assert gruppen == ["laufzeit"]


def test_ohne_auswahl_bleibt_alles_leer(flow):
    assert flow.gruppen_ableiten(_kandidaten(), []) == []
