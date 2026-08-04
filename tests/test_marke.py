"""Die Bildmaße der Integration.

Seit Home Assistant 2026.3 liefert die Anlage ihr Symbol nicht mehr über das
Repository *home-assistant/brands*, sondern aus ``brand/`` in der Integration
selbst; brands nimmt für Zusatzintegrationen keine Beiträge mehr an. Die
Maßvorgaben sind dieselben geblieben:

============  ==============================================
Datei         kürzeste Seite
============  ==============================================
icon.png      genau 256
icon@2x.png   genau 512
logo.png      mindestens 128, höchstens 256
logo@2x.png   mindestens 256, höchstens 512
============  ==============================================

Das war schon einmal falsch und schon einmal „behoben": In 1.2.0 fehlte
``logo@2x.png`` ganz, danach waren ``logo.png`` 512×127 und ``logo@2x.png``
1024×254 – jeweils ein bzw. zwei Bildpunkte unter dem Mindestmaß. Auffallen
kann so etwas nur einem Test; von Hand sieht man den Unterschied nicht.

Gelesen wird der PNG-Kopf von Hand, damit die Prüfung ohne Pillow läuft.
"""

from __future__ import annotations

from pathlib import Path
import struct

import pytest

MARKE = Path(__file__).resolve().parent.parent / "custom_components" / "heatnexus" / "brand"

# Datei -> (kleinste erlaubte kürzeste Seite, größte erlaubte kürzeste Seite)
MASSE = {
    "icon.png": (256, 256),
    "icon@2x.png": (512, 512),
    "logo.png": (128, 256),
    "logo@2x.png": (256, 512),
}


def _groesse(pfad: Path) -> tuple[int, int]:
    """Breite und Höhe aus dem IHDR-Block eines PNG."""
    kopf = pfad.read_bytes()[:24]
    assert kopf[:8] == b"\x89PNG\r\n\x1a\n", f"{pfad.name} ist kein PNG"
    return struct.unpack(">II", kopf[16:24])


@pytest.mark.parametrize("datei", sorted(MASSE))
def test_markenbild_haelt_die_masse(datei):
    """Jedes der vier Bilder liegt im vorgeschriebenen Bereich."""
    pfad = MARKE / datei
    assert pfad.is_file(), f"{datei} fehlt – ohne sie zeigt Home Assistant kein Symbol"

    breite, hoehe = _groesse(pfad)
    kuerzeste = min(breite, hoehe)
    klein, gross = MASSE[datei]
    assert klein <= kuerzeste <= gross, (
        f"{datei} ist {breite}×{hoehe}; die kürzeste Seite muss zwischen {klein} und {gross} liegen"
    )


def test_symbole_sind_quadratisch():
    """Ein Symbol ist quadratisch, ein Schriftzug ist es nie."""
    for datei in ("icon.png", "icon@2x.png"):
        breite, hoehe = _groesse(MARKE / datei)
        assert breite == hoehe, f"{datei} ist {breite}×{hoehe}, gefordert ist ein Quadrat"
