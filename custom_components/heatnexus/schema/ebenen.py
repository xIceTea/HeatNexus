"""Die Überlagerungen des Schaubilds: Lage und Daten je Bauteil in Prozent des Bildes.

Ein Standbild kann sich nicht drehen und kennt keine Zustände aus Home Assistant.
Pumpen, Glutbett, Mischer, Heizkörper, Lampen und Speicher liegen deshalb als eigene
Ebenen über der Zeichnung; jede Funktion hier liefert eine davon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .bauteile import kessellampe, lampenpunkt, waermeflaeche
from .werte import (
    ANALOG_SOLLWERT,
    BRENNKAMMER_HEISS,
    BRENNKAMMER_KALT,
    ERZEUGER_ARTEN,
    finde,
)
from .zeichnung import (
    ENTNAHME_ARTEN,
    GLUTBETT_BREITE,
    GLUTBETT_Y,
    HEIZKOERPER_ANZAHL,
    HEIZKOERPER_BREITE,
    HEIZKOERPER_GLANZ_BIS,
    HEIZKOERPER_GLANZ_VON,
    HEIZKOERPER_GLIED,
    HEIZKOERPER_HEISS,
    HEIZKOERPER_HOEHE,
    HEIZKOERPER_KALT,
    HEIZKOERPER_RASTER,
    HEIZKOERPER_X,
    HEIZKOERPER_Y,
    HOEHE,
    KANTEN_JE_ART,
    KANTEN_STANDARD,
    LADE_TOLERANZ,
    MISCHER_JE_ART,
    MISCHER_MARKE,
    MODUL_BREITE,
    RAND,
    RUECKLAUF_Y,
    SPEICHER_ARTEN,
    SPEICHER_Y,
    VORLAUF_Y,
    ZSP_BETRIEBSLAMPE,
    ZSP_GEHAEUSE,
    ZSP_KLEMMEN,
    ZSP_PUMPE,
    speicherfuehler,
)

Ebene = list[dict[str, Any]]


@dataclass(frozen=True)
class Rahmen:
    """Was mehrere Ebenen gemeinsam brauchen: die Bildbreite und die Wärmewege am Speicher."""

    breite: float
    # Wer dem Speicher Wärme entnimmt: alle Pumpen der Verbraucher.
    entnahme: tuple[str, ...]
    # Wer dem Speicher Wärme zuführt, ohne an der Steuerung zu hängen. Eine
    # liefernde Quelle lädt ihn, auch wenn die Ladepumpe steht.
    lieferungen: tuple[str, ...]

    @classmethod
    def aus_modulen(cls, module: list[dict[str, Any]], breite: float) -> Rahmen:
        """Die gemeinsamen Angaben aus den gezeichneten Anlagenteilen."""
        return cls(
            breite=breite,
            entnahme=tuple(
                m["pumpe"] for m in module if m.get("pumpe") and m["art"] in ENTNAHME_ARTEN
            ),
            lieferungen=tuple(m["lieferung"] for m in module if m.get("lieferung")),
        )


def _pct(wert: float, gesamt: float, stellen: int = 2) -> str:
    """Ein Maß als Anteil am Bild; sonst verzieht es sich, sobald die Karte skaliert."""
    return f"{wert / gesamt * 100:.{stellen}f}%"


def _links(platz: int) -> int:
    return RAND + platz * MODUL_BREITE


def _mitte(platz: int) -> int:
    return _links(platz) + MODUL_BREITE // 2


def _marke(entity: str, mitte: float, y: float, titel: str, rahmen: Rahmen) -> dict[str, Any]:
    """Entität, Lage und Titel einer Marke, die auf der Mitte eines Anlagenteils sitzt."""
    return {
        "entity": entity,
        "left": _pct(mitte, rahmen.breite),
        "top": _pct(y, HOEHE),
        "titel": titel,
    }


def _stichleitungen(art: str) -> dict[str, str]:
    """Die beiden senkrechten Stichleitungen eines Anlagenteils.

    Sie strömen nur, solange **seine** Pumpe fördert – daran sieht man, wohin die
    Wärme gerade geht. Die waagrechten Leitungen strömen dagegen immer, sobald
    irgendwo etwas läuft: Dort steht das Wasser ja auch nicht still.
    """
    oben, unten = KANTEN_JE_ART.get(art, KANTEN_STANDARD)
    return {
        "vorlauf_top": _pct(VORLAUF_Y, HOEHE),
        "vorlauf_hoehe": _pct(oben - VORLAUF_Y, HOEHE),
        "ruecklauf_top": _pct(unten, HOEHE),
        "ruecklauf_hoehe": _pct(RUECKLAUF_Y - unten, HOEHE),
    }


def _stelle(x: float, y: float, rahmen: Rahmen) -> dict[str, str]:
    """Position einer Marke innerhalb eines Anlagenteils."""
    return {"left": _pct(x, rahmen.breite), "top": _pct(y, HOEHE)}


def _pumpe(modul: dict[str, Any], mitte: float, rahmen: Rahmen) -> dict[str, Any]:
    """Die Pumpe sitzt im Rücklauf, unterhalb ihres Anlagenteils."""
    puffer = modul["art"] == "puffer"
    return {
        **_marke(modul["pumpe"], mitte, RUECKLAUF_Y, modul["titel"], rahmen),
        **_stichleitungen(modul["art"]),
        # Ein Speicher strömt in beide Richtungen: Seine eigene Pumpe lädt ihn,
        # entnommen wird ihm von den Pumpen der Verbraucher – und dabei dreht
        # die Ladepumpe nicht.
        "entnahme": list(rahmen.entnahme) if puffer else [],
        # Eine Quelle lädt den Speicher, ohne dass seine Ladepumpe fördert. Ohne
        # sie stünde die Stichleitung still, während der Speicher „lädt" anzeigt.
        "quellen": list(rahmen.lieferungen) if puffer else [],
        "erzeuger": modul["art"] in ERZEUGER_ARTEN,
    }


def _strang(entity: str, modul: dict[str, Any], mitte: float, rahmen: Rahmen, **extra) -> dict:
    """Nur die Leitung eines Erzeugers, ohne drehende Pumpenmarke."""
    return {
        **_marke(entity, mitte, RUECKLAUF_Y, modul["titel"], rahmen),
        **extra,
        "erzeuger": True,
        **_stichleitungen(modul["art"]),
    }


def _kesselstrang(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Die Leitung eines Kessels ohne eigene Pumpe.

    Sein Wasser bewegt die Pufferladepumpe. Nur die Leitung, keine Pumpenmarke:
    An dieser Stelle sitzt keine Pumpe.
    """
    ladepumpe = next((m["pumpe"] for m in module if m["art"] == "puffer" and m.get("pumpe")), None)
    if not ladepumpe:
        return []
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        if modul["art"] != "kessel" or modul.get("pumpe"):
            continue
        ergebnis.append(_strang(ladepumpe, modul, _mitte(platz), rahmen, nur_strang=True))
    return ergebnis


def pumpen(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Die Pumpen und die Stränge der Erzeuger.

    Eine Wärmequelle führt keinen Pumpendatenpunkt, speist aber ein. Stichleitung,
    Lampe und Laufrad hängen deshalb an ihrer Wärmelieferung.
    """
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        mitte = _mitte(platz)
        if modul.get("pumpe"):
            ergebnis.append(_pumpe(modul, mitte, rahmen))
        if modul.get("lieferung"):
            ergebnis.append(
                _strang(
                    modul["lieferung"],
                    modul,
                    mitte,
                    rahmen,
                    nur_strang=not modul.get("quellenpumpe"),
                )
            )
    return ergebnis + _kesselstrang(module, rahmen)


def waerme(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Die Wärme im Bauteil einer Quelle, solange sie liefert.

    Sie sagt, dass die Quelle arbeitet, ohne eine Temperatur zu behaupten.
    """
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        if not modul.get("lieferung"):
            continue
        flaeche = waermeflaeche(modul["art"], modul.get("zeichnung"))
        if flaeche is None:
            continue
        ergebnis.append(
            {
                "entity": modul["lieferung"],
                **_stelle(_links(platz) + flaeche["x"], flaeche["y"], rahmen),
                "breite": _pct(flaeche["breite"], rahmen.breite),
                "hoehe": _pct(flaeche["hoehe"], HOEHE),
                "ecke": f"{_pct(flaeche['ecke'], flaeche['breite'])} / "
                f"{_pct(flaeche['ecke'], flaeche['hoehe'])}",
                "dreh": flaeche["dreh"],
                "titel": modul["titel"],
            }
        )
    return ergebnis


def _lampe(entity: str, punkt: tuple[float, float, float], links: float, rahmen: Rahmen) -> dict:
    """Die gemeinsamen Felder einer Betriebslampe: Lage und Größe."""
    lx, ly, lr = punkt
    return {
        "entity": entity,
        **_stelle(links + lx, ly, rahmen),
        "groesse": _pct(2 * lr, rahmen.breite),
    }


def lampen_der_erzeuger(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Die Betriebslampen der Wärmequellen und der Kessel.

    Die Lampe des Kessels sitzt über dem gezeichneten roten Punkt. Sie leuchtet
    grün, solange der Erzeuger läuft, und deckt das Rot dabei ab.
    """
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        links = _links(platz)
        if modul.get("lieferung"):
            punkt = lampenpunkt(modul["art"], zeichnung=modul.get("zeichnung"))
            if punkt is not None:
                lampe = _lampe(modul["lieferung"], punkt, links, rahmen)
                lampe.update({"art": "betrieb", "zweck": "quelle", "titel": modul["titel"]})
                ergebnis.append(lampe)
        if modul["art"] != "kessel":
            continue
        leistung, ersatz = modul.get("leistung"), modul.get("brennkammer")
        if not (leistung or ersatz):
            continue
        punkt = kessellampe(modul.get("kesselart"), modul.get("zeichnung"))
        if punkt is not None:
            lampe = _lampe(leistung, punkt, links, rahmen)
            ergebnis.append(
                {
                    "entity": leistung,
                    "ersatz": ersatz,
                    "ersatz_min": BRENNKAMMER_KALT,
                    "left": lampe["left"],
                    "top": lampe["top"],
                    "groesse": lampe["groesse"],
                    "art": "betrieb",
                    "zweck": "erzeuger",
                    "titel": modul["titel"],
                }
            )
    return ergebnis


def mischer(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Der Mischer zeigt seine Stellung, nicht Bewegung.

    Ein dauernd drehendes Ventil läse sich wie eine Pumpe, und die dreht sich im
    Bild schon. Der Anzeiger schwenkt, das Stück Vorlauf darüber färbt sich nach
    der Beimischung.
    """
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        if not (modul.get("mischer") and modul["art"] in MISCHER_JE_ART):
            continue
        ventil, oben = MISCHER_JE_ART[modul["art"]]
        ergebnis.append(
            {
                **_marke(modul["mischer"], _mitte(platz), ventil, modul["titel"], rahmen),
                "groesse": _pct(MISCHER_MARKE, rahmen.breite),
                # Das Stück Vorlauf zwischen Leitung und Ventil.
                "stutzen_top": _pct(VORLAUF_Y, HOEHE),
                "stutzen_hoehe": _pct(oben - VORLAUF_Y, HOEHE),
            }
        )
    return ergebnis


def heizkoerper(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Der Heizkörper färbt sich nach dem, was durch ihn fließt.

    Kalt in der Farbe des Rücklaufs, heiß in der des Vorlaufs. Ohne gemessene
    Vorlauftemperatur bleibt es bei der Zeichnung.
    """
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        if not (modul["art"] == "heizkreis" and modul.get("vorlauf")):
            continue
        ergebnis.append(
            {
                "entity": modul["vorlauf"],
                **_stelle(_links(platz) + HEIZKOERPER_X, HEIZKOERPER_Y, rahmen),
                "breite": _pct(HEIZKOERPER_BREITE, rahmen.breite),
                "hoehe": _pct(HEIZKOERPER_HOEHE, HOEHE),
                # Anteile der Ebenenbreite, nicht Bildpunkte – siehe HEIZKOERPER_GLIED.
                "glied": _pct(HEIZKOERPER_GLIED, HEIZKOERPER_BREITE, 4),
                "raster": _pct(HEIZKOERPER_RASTER, HEIZKOERPER_BREITE, 4),
                "glanz_von": _pct(HEIZKOERPER_GLANZ_VON, HEIZKOERPER_BREITE, 4),
                "glanz_bis": _pct(HEIZKOERPER_GLANZ_BIS, HEIZKOERPER_BREITE, 4),
                "anzahl": HEIZKOERPER_ANZAHL,
                "kalt": HEIZKOERPER_KALT,
                "heiss": HEIZKOERPER_HEISS,
                "titel": modul["titel"],
            }
        )
    return ergebnis


def brenner(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Das Glutbett des Wärmeerzeugers, das mitgeht, solange er Leistung bringt.

    Maßgeblich ist die Kesselleistung: Die Betriebsphase heißt auf jeder Baureihe
    anders, eine Zahl über null nicht. Fehlt die Leistung, dient die
    Brennkammertemperatur als Ersatzskala – dort heißt kalt 100 °C und voll 500 °C.
    """
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        if modul["art"] != "kessel":
            continue
        leistung, ersatz = modul.get("leistung"), modul.get("brennkammer")
        if not (leistung or ersatz):
            continue
        ergebnis.append(
            {
                "entity": leistung,
                "ersatz": ersatz,
                "ersatz_min": BRENNKAMMER_KALT,
                "ersatz_max": BRENNKAMMER_HEISS,
                **_stelle(_mitte(platz), GLUTBETT_Y, rahmen),
                "breite": _pct(GLUTBETT_BREITE, rahmen.breite),
                "titel": modul["titel"],
            }
        )
    return ergebnis


def pumpenmodule(module: list[dict[str, Any]], rahmen: Rahmen) -> tuple[Ebene, Ebene]:
    """Lampen und Übergabe des Pumpen-/Relaismoduls, beide am Analog-Sollwert.

    Über null fordert das Modul Wärme an. Das gezeichnete Laufrad steht still;
    darüber liegt ein eigenes, das sich dreht, solange angefordert wird.
    """
    lampen: Ebene = []
    uebergabe: Ebene = []
    for platz, modul in enumerate(module):
        if modul["art"] != "pumpenmodul":
            continue
        soll = finde(modul.get("entitaeten") or [], ANALOG_SOLLWERT, "analog_setpoint")
        if soll is None:
            continue
        x = _links(platz)
        for punkt in (*ZSP_KLEMMEN, ZSP_BETRIEBSLAMPE):
            lampe = _lampe(soll["entity_id"], punkt, x, rahmen)
            lampe.update(
                {
                    "art": "betrieb" if punkt == ZSP_BETRIEBSLAMPE else "klemme",
                    "zweck": "anforderung",
                    "titel": modul["titel"],
                }
            )
            lampen.append(lampe)
        gx, gy, gb, gh = ZSP_GEHAEUSE
        px, py, pr = ZSP_PUMPE
        uebergabe.append(
            {
                "entity": soll["entity_id"],
                **_stelle(x + gx, gy, rahmen),
                "breite": _pct(gb, rahmen.breite),
                "hoehe": _pct(gh, HOEHE),
                "ecke": f"{_pct(12, gb)} / {_pct(12, gh)}",
                "rad_left": _pct(x + px, rahmen.breite),
                "rad_top": _pct(py, HOEHE),
                "rad_groesse": _pct(2 * pr, rahmen.breite),
                "titel": modul["titel"],
            }
        )
    return lampen, uebergabe


def schichtung(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Der eingefärbte Inhalt von Puffer und Boiler.

    Beide laufen über dieselbe Ebene: Der Puffer hat zwei Fühler und zeigt damit
    eine Schichtung, der Boiler einen und wird gleichmäßig eingefärbt.
    """
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        masse = SPEICHER_ARTEN.get(modul["art"])
        if masse is None:
            continue
        oben, unten = speicherfuehler(modul)
        if oben is None:
            continue
        ergebnis.append(
            {
                "oben": oben,
                "unten": unten,
                **_stelle(_links(platz) + masse["x"], masse["y"], rahmen),
                "breite": _pct(masse["breite"], rahmen.breite),
                "hoehe": _pct(masse["hoehe"], HOEHE),
                # Der Eckradius als Anteil je Achse – sonst verzieht er sich,
                # sobald die Karte das Bild skaliert.
                "ecke": f"{_pct(masse['ecke'], masse['breite'])} / "
                f"{_pct(masse['ecke'], masse['hoehe'])}",
                "kalt": masse["kalt"],
                "heiss": masse["heiss"],
                # Ohne Messwerte trägt die Fläche denselben Verlauf, den die
                # Zeichnung sonst selbst gemalt hätte.
                "grund": masse["grund"],
                "titel": modul["titel"],
            }
        )
    return ergebnis


def _kesseltemperatur(module: list[dict[str, Any]]) -> str | None:
    """Die Kesseltemperatur des ersten Wärmeerzeugers.

    Ohne sie ließe sich nicht sagen, ob die laufende Ladepumpe wirklich Wärme in
    den Puffer bringt oder nur umwälzt.
    """
    return next(
        (
            w["entity_id"]
            for m in module
            if m["art"] == "kessel"
            for w in m["werte"]
            if w.get("beschriftung") == "Kessel"
        ),
        None,
    )


def _fuehler(modul: dict[str, Any], beschriftung: str) -> str | None:
    return next(
        (w["entity_id"] for w in modul["werte"] if w.get("beschriftung") == beschriftung),
        None,
    )


def speicher(module: list[dict[str, Any]], rahmen: Rahmen) -> Ebene:
    """Ob der Puffer gerade beladen oder entleert wird.

    „lädt" heißt: Die Ladepumpe fördert **und** der Kessel ist wärmer als der obere
    Pufferbereich. Die Pumpe allein genügt nicht – sie läuft auch, wenn der Kessel
    gerade direkt in einen Heizkreis fährt und dem Puffer nichts zugeht.

    „entlädt": Ein Verbraucher zieht, ohne dass geladen wird. Läuft beides, bleibt
    es bei „lädt"; welche Richtung netto überwiegt, hängt vom Massenstrom ab, und
    den misst die Anlage nicht.
    """
    kessel_ist = _kesseltemperatur(module)
    ergebnis: Ebene = []
    for platz, modul in enumerate(module):
        if modul["art"] != "puffer":
            continue
        ergebnis.append(
            {
                "laden": modul.get("pumpe"),
                "quellen": list(rahmen.lieferungen),
                "kessel": kessel_ist,
                "oben": _fuehler(modul, "oben"),
                "unten": _fuehler(modul, "unten"),
                "toleranz": LADE_TOLERANZ,
                "entnahme": list(rahmen.entnahme),
                **_stelle(_mitte(platz), SPEICHER_Y, rahmen),
                "titel": modul["titel"],
            }
        )
    return ergebnis


def leitungen(rahmen: Rahmen) -> dict[str, str]:
    """Lage der beiden Leitungen in Prozent des Bildes.

    Die Oberfläche legt darüber eine bewegte Ebene: Ein Bild als Daten-URL kennt
    keine Zustände aus Home Assistant, es kann also nicht selbst anzeigen, ob
    etwas fließt.
    """
    return {
        "left": _pct(RAND, rahmen.breite),
        "width": _pct(rahmen.breite - 2 * RAND, rahmen.breite),
        "vorlauf_top": _pct(VORLAUF_Y, HOEHE),
        "ruecklauf_top": _pct(RUECKLAUF_Y, HOEHE),
    }
