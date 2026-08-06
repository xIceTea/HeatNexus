"""Einen Rundgang durch die Oberfläche aufnehmen.

**Was hier entsteht.** Ein GIF, das durch die Reiter der eigenen Oberfläche
führt: Übersicht mit Heizungsübersicht, Schaubild und Systemstatus, eine
anliegende Störung, die Steuerung, die Wartung mit ihren Restlaufzeiten, das
Wochenraster der Zeitprogramme und der Verlauf. Wer vor der Installation wissen
will, was die Integration eigentlich zeigt, sieht es damit.

**Wie es entsteht.** Nicht nachgebaut: Aufgenommen wird `heatnexus-panel.js`
selbst, mit `stil.js`, in einem kopflosen Browser. Das Panel hängt an genau
einem fremden Element – `ha-icon` – und holt seine Aufteilung über
``panel.config.daten``. Beides lässt sich stellen:

* Die Aufteilung kommt aus ``panel.panel_daten``-Bausteinen, gerechnet über
  dieselbe Beispielanlage wie das Schaubild (`tools/beispielanlage.py`).
* Die Zustandstabelle von Home Assistant wird nachgebildet; je Auftritt lassen
  sich einzelne Zustände überschreiben – so entsteht die Störung.
* ``ha-icon`` wird aus den Symbolpfaden bedient, die das installierte
  Home-Assistant-Frontend mitbringt. Die Symbole sind damit die echten.

    python tools/build_panel_rundgang.py

Voraussetzung ist eine Umgebung mit Home Assistant **und** dessen
Frontend-Paket; ohne die bricht der Lauf mit einem Hinweis ab. Ins Repository
kommt nur das fertige GIF.
"""

from __future__ import annotations

import glob
import http.server
import json
import os
from pathlib import Path
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from beispielanlage import KOMPONENTE, WURZEL, anlage, zustaende

ZIEL = WURZEL / "assets" / "panel_rundgang.gif"

BREITE, HOEHE = 1120, 920
GIF_BREITE = 900
FARBEN = 160

# Die Störung, die im Rundgang auftritt. Text und Kennung stammen aus der
# Störungstabelle des Herstellers (`AL 071`), der Zustand ist erfunden.
STOERUNG = {
    "sensor.meldung_klartext": {
        "state": "Aschelade voll. Aschelade entleeren.",
        "attributes": {"stoerung_aktiv": True},
    }
}

# Der Rundgang. Je Auftritt: Reiter, wie lange er steht, wie weit die Seite
# gerollt ist und was an der Anlage gerade anders ist.
AUFTRITTE = [
    {"reiter": "uebersicht", "dauer": 2600, "rollen": 0, "titel": "Übersicht"},
    {"reiter": "uebersicht", "dauer": 2000, "rollen": 620, "titel": "Schaubild"},
    {
        "reiter": "uebersicht",
        "dauer": 3000,
        "rollen": 0,
        "zustand": STOERUNG,
        "titel": "Störung anliegend",
    },
    {"reiter": "steuerung", "dauer": 3000, "rollen": 0, "titel": "Steuerung"},
    {"reiter": "steuerung", "dauer": 2400, "rollen": 560, "titel": "Warmwasser und Kessel"},
    {"reiter": "wartung", "dauer": 2400, "rollen": 0, "titel": "Wartung"},
    {"reiter": "zeitprogramme", "dauer": 2800, "rollen": 0, "titel": "Zeitprogramme"},
    # Der Reiter „Verlauf" fehlt mit Absicht: Er zeichnet mit der
    # Verlaufskarte von Home Assistant, und die kommt über `loadCardHelpers`
    # aus dem Frontend. Außerhalb einer laufenden Instanz gibt es sie nicht –
    # eine leere Karte im Rundgang wäre eine Falschaussage.
    {"reiter": "uebersicht", "dauer": 2600, "rollen": 1180, "titel": "Systemstatus"},
]


def _mdi_verzeichnis() -> Path:
    """Der Ordner mit den Symbolpfaden im installierten Frontend."""
    try:
        import hass_frontend
    except ImportError as err:  # pragma: no cover - Umgebungsfrage
        raise SystemExit(
            "hass_frontend fehlt – ohne das Frontend-Paket gibt es keine Symbole. "
            "Abhilfe: pip install -r requirements_test.txt"
        ) from err
    return Path(hass_frontend.__file__).parent / "static" / "mdi"


def symbolpfade(namen: set[str]) -> dict[str, str]:
    """Zu jedem Symbolnamen den SVG-Pfad – aus dem Frontend, nicht geraten."""
    gefunden: dict[str, str] = {}
    for datei in glob.glob(str(_mdi_verzeichnis() / "*.json")):
        with open(datei, encoding="utf-8") as f:
            teil = json.load(f)
        for name in namen - gefunden.keys():
            if name in teil:
                gefunden[name] = teil[name]
    return gefunden


def _symbolnamen(daten: dict) -> set[str]:
    """Alle `mdi:`-Namen aus den Daten und aus der Oberfläche selbst."""
    namen: set[str] = set()

    def sammeln(gegenstand) -> None:
        if isinstance(gegenstand, dict):
            for wert in gegenstand.values():
                sammeln(wert)
        elif isinstance(gegenstand, list):
            for wert in gegenstand:
                sammeln(wert)
        elif isinstance(gegenstand, str) and gegenstand.startswith("mdi:"):
            namen.add(gegenstand[4:])

    sammeln(daten)
    # Die Oberfläche setzt weitere Symbole selbst – sie stehen im Quelltext.
    frontend = KOMPONENTE / "frontend"
    for datei in [frontend / "heatnexus-panel.js", *sorted((frontend / "teile").glob("*.js"))]:
        text = datei.read_text(encoding="utf-8")
        for stelle in range(len(text)):
            if text.startswith("mdi:", stelle):
                ende = stelle + 4
                while ende < len(text) and (text[ende].isalnum() or text[ende] == "-"):
                    ende += 1
                namen.add(text[stelle + 4 : ende])
    return {n for n in namen if n}


def presets() -> dict[str, str]:
    """Die Klartexte der Betriebsarten aus der Übersetzung der Integration.

    Home Assistant setzt sie über `formatEntityAttributeValue` ein; ohne sie
    stünde am Thermostat die nackte Zahl, die die Anlage liefert.
    """
    datei = KOMPONENTE / "translations" / "de.json"
    texte = json.loads(datei.read_text(encoding="utf-8"))
    pfad = texte.get("entity", {}).get("climate", {}).get("heatnexus_climate", {})
    return pfad.get("state_attributes", {}).get("preset_mode", {}).get("state", {})


def panel_daten() -> dict:
    """Die Aufteilung, die die Oberfläche sonst über den Websocket holt."""
    from custom_components.heatnexus.panel import _anlage_daten

    return {
        "anlagen": [_anlage_daten(anlage(), "sensor.aussentemperatur")],
        "uebersteuerung": {},
        "aussentemperatur": "sensor.aussentemperatur",
    }


SEITE = """<!doctype html><meta charset="utf-8">
<style>
  html, body { margin: 0; padding: 0; background: #0e1419; color: #e6edf3;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  /* Die Bewegung wird angehalten: Eine Aufnahme soll denselben Zustand
     zeigen, egal wie lange der Browser bis dahin gebraucht hat. */
  * { animation-play-state: paused !important; transition: none !important; }
</style>
<div id="halter"></div>
<script type="module">
import { DATEN, STATES, MDI, REITER, ROLLEN, PRESETS } from "./auftritt.js";

/** Ersatz für `ha-icon`: dieselben Pfade, die Home Assistant ausliefert. */
class HeatNexusIcon extends HTMLElement {
  static get observedAttributes() { return ["icon"]; }
  connectedCallback() { this._zeichnen(); }
  attributeChangedCallback() { this._zeichnen(); }
  _zeichnen() {
    const name = (this.getAttribute("icon") || "").replace("mdi:", "");
    const pfad = MDI[name];
    this.style.display = "inline-flex";
    this.style.alignItems = "center";
    this.style.justifyContent = "center";
    this.style.width = "var(--mdc-icon-size, 24px)";
    this.style.height = "var(--mdc-icon-size, 24px)";
    this.innerHTML = pfad
      ? '<svg viewBox="0 0 24 24" width="100%" height="100%">'
        + '<path fill="currentColor" d="' + pfad + '"/></svg>'
      : "";
  }
}
customElements.define("ha-icon", HeatNexusIcon);

await import("./frontend/heatnexus-panel.js");

const hass = {
  states: STATES,
  themes: { darkMode: true },
  callWS: async (nachricht) =>
    nachricht.type === "heatnexus/panel_daten" ? DATEN : {},
  callService: async () => {},
  formatEntityState: (zustand) => {
    const einheit = zustand.attributes && zustand.attributes.unit_of_measurement;
    return einheit ? zustand.state + " " + einheit : zustand.state;
  },
  localize: (schluessel) => schluessel,
  // Die Betriebsarten heissen am Gerät "0".."7"; die Klartexte kommen aus der
  // Übersetzung der Integration – genau wie in Home Assistant.
  formatEntityAttributeValue: (zustand, merkmal) =>
    merkmal === "preset_mode"
      ? PRESETS[zustand.attributes.preset_mode] || zustand.attributes.preset_mode
      : zustand.attributes[merkmal],
};

const element = document.createElement("heatnexus-panel");
document.getElementById("halter").appendChild(element);
element.panel = { config: { daten: DATEN } };
element.hass = hass;
// Den Reiter setzen wie ein Klick auf die Leiste – die Oberfläche baut sich
// daraufhin neu auf.
element._reiter = REITER;
element._gebaut = false;
element._zeichnen();
window.scrollTo(0, ROLLEN);
</script>
"""


def _auftritt_schreiben(
    ordner: Path, daten: dict, auftritt: dict, mdi: dict, klartexte: dict
) -> None:
    """Die Datei mit Daten, Zuständen und Reiter für eine Aufnahme."""
    (ordner / "auftritt.js").write_text(
        "export const DATEN = " + json.dumps(daten, ensure_ascii=False) + ";\n"
        "export const STATES = "
        + json.dumps(zustaende(auftritt.get("zustand")), ensure_ascii=False)
        + ";\n"
        "export const MDI = " + json.dumps(mdi, ensure_ascii=False) + ";\n"
        "export const REITER = " + json.dumps(auftritt["reiter"]) + ";\n"
        "export const ROLLEN = " + json.dumps(auftritt.get("rollen", 0)) + ";\n"
        "export const PRESETS = " + json.dumps(klartexte, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )


BROWSER = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
]


def _browser() -> str:
    for pfad in BROWSER:
        if Path(pfad).exists():
            return pfad
    if gefunden := shutil.which("chromium") or shutil.which("google-chrome"):
        return gefunden
    raise SystemExit("Kein kopfloser Browser gefunden (Edge, Chrome oder Chromium).")


class _Stiller(http.server.SimpleHTTPRequestHandler):
    """Ein Webserver ohne Gerede im Protokoll."""

    def log_message(self, *args) -> None:
        pass


def main() -> None:
    from PIL import Image

    daten = panel_daten()
    mdi = symbolpfade(_symbolnamen(daten))
    klartexte = presets()
    print(f"Symbole aus dem Frontend: {len(mdi)}")
    browser = _browser()
    bilder: list[Image.Image] = []
    dauern: list[int] = []

    with tempfile.TemporaryDirectory() as ordnername:
        ordner = Path(ordnername)
        shutil.copytree(KOMPONENTE / "frontend", ordner / "frontend")
        (ordner / "index.html").write_text(SEITE, encoding="utf-8")

        # Der Browser lädt ES-Module nicht über `file:`; ein Server auf der
        # Rückverbindung ist der kürzeste Weg dorthin.
        vorher = os.getcwd()
        os.chdir(ordner)
        try:
            with socketserver.TCPServer(("127.0.0.1", 0), _Stiller) as server:
                tor = server.server_address[1]
                threading.Thread(target=server.serve_forever, daemon=True).start()
                for nummer, auftritt in enumerate(AUFTRITTE):
                    _auftritt_schreiben(ordner, daten, auftritt, mdi, klartexte)
                    aufnahme = ordner / f"auftritt_{nummer}.png"
                    subprocess.run(
                        [
                            browser,
                            "--headless",
                            "--disable-gpu",
                            "--hide-scrollbars",
                            f"--window-size={BREITE},{HOEHE}",
                            "--virtual-time-budget=3000",
                            f"--screenshot={aufnahme}",
                            f"http://127.0.0.1:{tor}/index.html?a={nummer}",
                        ],
                        check=True,
                        capture_output=True,
                    )
                    bild = Image.open(aufnahme).convert("RGB")
                    hoehe = round(HOEHE * GIF_BREITE / BREITE)
                    bilder.append(bild.resize((GIF_BREITE, hoehe), Image.LANCZOS))
                    dauern.append(auftritt["dauer"])
                    print(f"aufgenommen: {auftritt['titel']}")
                server.shutdown()
        finally:
            os.chdir(vorher)

    # Gemeinsame Farbtafel wie beim Schaubild: Sie hält das GIF klein, weil
    # die Farbnummern über die Auftritte hinweg dieselben bleiben.
    auswahl = Image.new("RGB", (bilder[0].width, bilder[0].height * len(bilder)))
    for platz, bild in enumerate(bilder):
        auswahl.paste(bild, (0, platz * bilder[0].height))
    tafel = auswahl.quantize(colors=FARBEN, method=Image.Quantize.MEDIANCUT)
    gemeinsam = [b.quantize(palette=tafel, dither=Image.Dither.NONE) for b in bilder]

    gemeinsam[0].save(
        ZIEL,
        save_all=True,
        append_images=gemeinsam[1:],
        duration=dauern,
        loop=0,
        optimize=True,
    )
    print(f"geschrieben: {ZIEL.relative_to(WURZEL)} ({ZIEL.stat().st_size / 1024:.0f} kB)")


if __name__ == "__main__":
    main()
