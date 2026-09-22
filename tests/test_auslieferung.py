"""Die Auslieferung der Frontend-Dateien.

Die Karte steht in einer Seite, die der Browser über eine Aktualisierung
hinweg behält. Ihr Modulpfad trägt die Fassung, also fragt eine offene Seite
nach der Fassung von gestern.
"""

from __future__ import annotations

import pytest

from .conftest import requires_frontend, requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def auslieferung():
    from custom_components.heatnexus import auslieferung

    return auslieferung


def test_nur_dateien_aus_dem_frontend_ordner(auslieferung):
    """Ein Pfad nach oben führt nirgendwohin."""
    assert auslieferung.datei_im_ordner("heatnexus-schaubild-karte.js") is not None
    assert auslieferung.datei_im_ordner("teile/schaubild.js") is not None
    assert auslieferung.datei_im_ordner("../const.py") is None
    assert auslieferung.datei_im_ordner("gibtsnicht.js") is None


async def test_ein_alter_fassungspfad_bleibt_erreichbar(hass, auslieferung):
    """Sonst fehlt der offenen Seite das Modul und die Karte meldet einen Fehler."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "http", {})

    await auslieferung.async_dateien_ausliefern(hass, "1.11.0")

    pfade = [r.canonical for r in hass.http.app.router.resources()]
    assert "/heatnexus-karte-{fassung}" in " ".join(pfade)


@requires_frontend()
async def test_das_kartenmodul_steht_vor_jeder_anlage_bereit(hass, enable_custom_integrations):
    """Ohne eingerichtete Anlage ist das Kartenmodul schon angemeldet."""
    from homeassistant.components import frontend
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "heatnexus", {})
    await hass.async_block_till_done()

    adressen = hass.data[frontend.DATA_EXTRA_MODULE_URL].urls
    assert any(a.endswith("/heatnexus-schaubild-karte.js") for a in adressen)
