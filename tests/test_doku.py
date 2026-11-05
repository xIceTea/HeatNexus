"""Die öffentliche Doku folgt dem Aufbau des Codes."""

from __future__ import annotations

from pathlib import Path
import re

WURZEL = Path(__file__).resolve().parents[1]
DASHBOARD = WURZEL / "custom_components" / "heatnexus" / "dashboard"


def test_die_architektur_nennt_jedes_dashboardmodul():
    zeile = next(
        z
        for z in (WURZEL / "docs" / "_includes" / "ARCHITECTURE.md")
        .read_text(encoding="utf-8")
        .splitlines()
        if z.startswith("| `dashboard/` |")
    )
    module = {p.stem for p in DASHBOARD.glob("*.py") if p.stem != "__init__"}
    genannt = set(re.findall(r"`(\w+)`", zeile))
    assert module <= genannt, f"fehlt: {sorted(module - genannt)}"
    assert genannt - {"dashboard", "__init__"} <= module, "nennt ein Modul, das es nicht gibt"


def test_die_anleitung_nennt_jeden_dienst():
    """Ein neuer Dienst in `services.yaml` erscheint auch in der Tabelle der Anleitung."""
    dienste = re.findall(
        r"(?m)^([a-z_]+):\s*$",
        (WURZEL / "custom_components" / "heatnexus" / "services.yaml").read_text(encoding="utf-8"),
    )
    vorlagen = (WURZEL / "docs" / "_includes" / "VORLAGEN.md").read_text(encoding="utf-8")
    tabelle = vorlagen.split("## Dienste", 1)[-1]
    fehlen = [d for d in dienste if f"| `{d}` |" not in tabelle]
    assert dienste and not fehlen, f"fehlt in VORLAGEN.md: {fehlen}"


def test_beide_readmes_fuehren_dieselben_geraete():
    """Deutsch und Englisch nennen dieselben Geräte in der Tabelle."""
    namen = [
        re.findall(r"(?m)^\| \S+ \| \*\*([^*]+)\*\*", (WURZEL / datei).read_text(encoding="utf-8"))
        for datei in ("README.md", "README.en.md")
    ]
    assert namen[0] and namen[0] == namen[1]


def test_die_vorlagen_nennen_die_adresse_der_kopie():
    text = (WURZEL / "docs" / "_includes" / "VORLAGEN.md").read_text(encoding="utf-8")
    treffer = re.search(r"(?ms)^### Dashboard ausgeben\s*$(.*?)(?=^#|\Z)", text)
    assert treffer and "`/heatnexus/`" in treffer.group(1)
