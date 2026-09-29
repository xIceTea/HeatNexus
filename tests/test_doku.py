"""Die öffentliche Doku folgt dem Aufbau des Codes."""

from __future__ import annotations

from pathlib import Path
import re

WURZEL = Path(__file__).resolve().parents[1]
DASHBOARD = WURZEL / "custom_components" / "heatnexus" / "dashboard"


def _abschnitt(datei: str, titel: str) -> str:
    text = (WURZEL / datei).read_text(encoding="utf-8")
    treffer = re.search(rf"(?ms)^## {titel}\s*$(.*?)(?=^## )", text)
    assert treffer, f"{datei}: Abschnitt {titel} fehlt"
    return treffer.group(1)


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


def test_die_readme_nennt_die_grenzen_der_kopie():
    for datei in ("README.md", "README.en.md"):
        assert "`/heatnexus/`" in _abschnitt(datei, "Dashboard"), datei


def test_die_vorlagen_nennen_die_adresse_der_kopie():
    text = (WURZEL / "docs" / "_includes" / "VORLAGEN.md").read_text(encoding="utf-8")
    treffer = re.search(r"(?ms)^### Dashboard ausgeben\s*$(.*?)(?=^#|\Z)", text)
    assert treffer and "`/heatnexus/`" in treffer.group(1)
