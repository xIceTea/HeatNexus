"""Welche Werte, Pumpen und Mischer ein Anlagenteil im Schaubild zeigt.

Die Zuordnung läuft über kanonische Schlüssel und Namensmuster; je Art gibt
es eine Vorlage, aus der `module` die zeichenbaren Anlagenteile bildet.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

from .. import geraete
from ..const import QUELLEN_ARTEN
from ..symbole import symbol_fuer_wert, symbol_je_fct

# Woran ein Heizkreis (fctType 14) Warmwasser und Zirkulation erkennen lässt.
# Am Gerät gehören beide Datenpunkte zum Heizkreis, im Schaubild werden sie
# eigenständige Teile; eine ZSP-Funktion liefert nicht immer eine Temperatur.
#
# Je zwei Schreibweisen, weil die kuratierten Tabellen anders benennen als die
# Geräte-Datenbank: „Warmwasser Ist-Temperatur" gegen „WW-Temperatur Aktueller
# Wert", „WW-Zirkulation Ist-Temperatur" gegen „WW-Zirkulationstemperatur
# Aktueller Wert". Der Sollwert darf dabei nicht mitgehen.
WARMWASSER_IST = r"\bww[- ]temperatur aktueller|\bwarmwasser ist[- ]?temperatur"


ZIRKULATION_IST = r"\bww-zirkulations?[- ]?(ist[- ])?temperatur(?!.*soll)"


# Der Stellwert des Heizkreismischers. „Laufzeit" muss draußen bleiben: Die
# Mischerlaufzeit ist eine Einstellung in Minuten, keine Stellung in Prozent.
MISCHER_IST = r"^mischer( stellwert)?$"


# Die gemessene Vorlauftemperatur eines Heizkreises – die Wärme, die wirklich
# im Heizkörper ankommt. Der Sollwert darf nicht mitgehen.
VORLAUF_IST = r"^vorlauftemperatur ist$"


# Die Brennkammertemperatur: wahlweise zweiter Wert am Kessel und Ersatzskala
# für das Glutbett, wenn keine Leistung gemeldet wird.
BRENNKAMMER_IST = r"brennerkammertemperatur|brennkammertemperatur"


# Der Analog-Sollwert des Pumpen-/Relaismoduls (0/95): die angeforderte
# Temperatur, über null heißt Anforderung. Er hat Vorrang vor 0/7, denn dessen
# Fühler misst bei einer Fernwärmeübergabe den Speicher der anderen Seite.
ANALOG_SOLLWERT = r"^analog[- ]sollwert$"


KESSELLEISTUNG_IST = r"kesselleistung"


# Eine Wärmequelle meldet keinen Messwert, sondern ob sie gerade liefert.
# Daran hängen ihre Lampe und der Fluss in ihrer Stichleitung.
LIEFERUNG = r"wärmelieferung"


# Unter dieser Temperatur glimmt nichts, darüber wird es voll.
BRENNKAMMER_KALT = 100


BRENNKAMMER_HEISS = 500


# Welcher Wert eines Anlagenteils wo im Schaubild steht.
# (Muster, Beschriftung, kanonische Schlüssel) – die Reihenfolge bestimmt die
# Position von oben. Der Schlüssel steht hinten und gewinnt, wo es ihn gibt;
# ohne ihn bliebe das Schaubild in einer fremden Sprache leer.
Wert = tuple[str, str, tuple[str, ...]]


WERTE_JE_ART: dict[str, tuple[Wert, ...]] = {
    # Der zweite Wert am Kessel ist wählbar (Option „kesselwert"); hier steht
    # die Vorgabe. `_werte_je_art` tauscht ihn gegebenenfalls aus.
    "kessel": (
        (r"kesseltemperatur ist", "Kessel", ("boiler_temperature",)),
        (r"kesselleistung", "Leistung", ("boiler_power",)),
    ),
    # Zwei Schreibweisen: die kuratierte Tabelle nennt sie „Puffer oben
    # Temperatur (TPE)", die Geräte-Datenbank „Puffertemperatur TPE" bzw.
    # „Puffertemperatur oben". Beide müssen treffen.
    "puffer": (
        (r"puffer(temperatur)?[ -]?oben|puffertemperatur tpe", "oben", ("buffer_top",)),
        (r"puffer(temperatur)?[ -]?unten|puffertemperatur tpa", "unten", ("buffer_bottom",)),
    ),
    "heizkreis": (
        (r"vorlauftemperatur ist", "Vorlauf", ("flow_temperature",)),
        (r"raumtemperatur ist", "Raum", ("room_temperature",)),
    ),
    # Das Pumpen-/Relaismodul (ZSP, fctType 20). Es ist keine Zirkulation: Es
    # kann eine Pumpe regeln, eine externe Wärmeanforderung entgegennehmen oder
    # einen Sammelalarm schalten – was davon, sagt `29/0..29/3`.
    # Bewusst leer: siehe `module`. Was das Modul tut, zeigen seine Lampen.
    "pumpenmodul": (),
    # Nur der Istwert. Ein Sollwert an der Stelle, an der beim Puffer die
    # zweite *gemessene* Temperatur steht, liest sich wie ein Messwert und
    # verwirrt mehr, als er nützt.
    "wasser": (
        (r"\bww[- ]temperatur aktueller|\bwarmwasser ist", "Warmwasser", ("dhw_temperature",)),
    ),
    # Die Warmwasser-Zirkulation.
    "zirkulation": ((ZIRKULATION_IST, "Zirkulation", ("dhw_circulation_temperature",)),),
    "solar": (
        (r"kollektortemperatur", "Kollektor", ("collector_temperature",)),
        (
            r"ww[- ]temperatur solar|puffertemperatur tps",
            "Speicher",
            ("solar_storage_temperature",),
        ),
    ),
    # Weiche bzw. Umschaltung: was hereinkommt und was im Speicher steht.
    "umschaltung": (
        (r"kesseltemperatur(?!.*soll)", "Kessel", ("boiler_temperature",)),
        (r"puffertemperatur (oben|tpe)", "Puffer", ("buffer_top",)),
    ),
}


# Die Pumpe eines Anlagenteils; sie dreht sich im Schaubild, solange sie läuft.
# Der Schlüssel trägt auch ohne deutschen Namen, das Muster fängt den Rest.
PUMPE_JE_ART: dict[str, tuple[str, tuple[str, ...]]] = {
    "kessel": (r"kesselpumpe|\bpumpe\b", ("boiler_pump",)),
    "puffer": (r"pufferladepumpe", ("buffer_charge_pump",)),
    "heizkreis": (r"heizkreispumpe", ("circuit_pump",)),
    "wasser": (r"\bww-ladepumpe", ("dhw_charge_pump",)),
    # Das ZSP-Modul meldet keinen Pumpenzustand, sondern seine Drehzahl.
    "pumpenmodul": (r"pumpendrehzahl|zirkulationspumpe(?!.*modus)", ("pump_speed",)),
    "zirkulation": (r"\bww-zirkulationspumpe(?!.*modus)", ("dhw_circulation_pump",)),
    "solar": (r"solarpumpe|pumpensteuerung drehzahl", ("pump_speed",)),
}


# Manche Pumpen melden keinen Zustand, sondern ihre Drehzahl in Prozent – die
# Pufferladepumpe etwa. Sie zählt genauso; „läuft" heißt dann „über null".
PUMPE_BEREICHE = ("binary_sensor", "switch", "sensor")


# Funktionstyp -> Art im Schaubild.
#
# **Diese Zuordnung ist nicht geraten.** Sie stammt aus den offiziellen
# Windhager-Dateien: `parameterLayer.json` führt je Funktionstyp die Liste
# seiner Datenpunkte, `de-parameters.json` deren Namen. Wer sie ändern will,
# lese sie dort nach – aus Namen abgeleitet gerät die Zuordnung falsch.
#
# Kurzform des Belegs je Typ:
#   1  Heizkurve, Kühlgrenzen, Estrich; Zeitprogramme 3/61..3/63 (Heizprogramme)
#   2  0/4 WW-Temperatur, Hygiene-Programm; Zeitprogramme 5/61, 5/62, 5/64
#   4  „Kaskadenmanager" – so nennt die Anlage ihn selbst; Folgeschaltung, ZSK
#   5  58/56 Kollektortemperatur, Kollektor spülen, Hydraulikschema Solar
#  13  „Solar ES" – ebenfalls von der Anlage benannt
#   6  60/30 Ionisationsstrom, 60/27 Anlagendruck, Netzbetriebsstunden
#   7  52/40 COP, Silentmode, Betriebsstunden Heizen/Warmwasser
#   8  56/5 Aktuelle Stufe E-Heizung, Betriebsstunden Stufe 1..3
#   9  Laufzeit bis Reinigung, Brennstoffverbrauch, Sondenumschaltung (BioWIN)
#  10  Startverzögerung Automatikkessel, O2-Signal, Puffertemperaturen
#  14  wie 1, aber ältere Baureihe (1/20 Heizkreispumpe) samt Warmwasser
#  15  Automatikkessel / Festbrennstoff / Pufferspeicher, Umschaltventil
#  16  21/65 TPE, 21/66 TPA, Pufferladepumpe
#  20  Pumpensteuerung, Ext. Wärmeanforderung, Summenstörmeldung
#  21  Puffertemperatur oben/mitte/unten, Beladegrad, Kälte-Puffertemperatur
#  24  58/12 Pumpe Wärmeerzeuger, Schichtladung, Rücklaufhochhaltung
#  25  PuroWIN
#  26  Kosten Strom, PV-Eingang, SG Ready, Bivalenztemperatur (Wärmepumpe)
#  27  50/70 Betriebsphase, Wärmemenge Heizen/Kühlen, E-Heizung (Wärmepumpe)
#
ART_JE_FCT: dict[int, str] = geraete.SCHAUBILD_ARTEN


ART_UNBEKANNT = "modul"


# Alle Arten, für die es eine Bauteilzeichnung geben muss. `zirkulation` steht
# in keinem Funktionstyp: Sie entsteht in `module` aus den Datenpunkten eines
# Heizkreises.
ALLE_ARTEN = set(ART_JE_FCT.values()) | {"zirkulation", ART_UNBEKANNT}


# Wer Wärme erzeugt, strömt andersherum als wer sie abnimmt: Beim Kessel kommt
# das kalte Wasser von unten herauf und das heiße verlässt ihn nach oben in den
# Vorlauf. Der Puffer entscheidet es je Zustand und steht deshalb nicht hier.
ERZEUGER_ARTEN = {"kessel", "solar"} | set(QUELLEN_ARTEN)


def _art(fct_type: Any) -> str:
    try:
        return ART_JE_FCT.get(int(fct_type), ART_UNBEKANNT)
    except (TypeError, ValueError):
        return ART_UNBEKANNT


# ---------------------------------------------------------------------------
# Art des Wärmeerzeugers
# ---------------------------------------------------------------------------
# Erste Quelle: der Funktionstyp, wo er die Art schon festlegt. Eine
# Wärmepumpe verbrennt nichts – bei ihr braucht es keinen Brennstoff und keinen
# Namen, um die Zeichnung zu wählen.
KESSELART_JE_FCT: dict[int, str] = geraete.KESSELARTEN


# Zweite Quelle: der Brennstoff, den die Anlage selbst meldet (`38/126`,
# `38/127`). Er ist eindeutig – ein PuroWIN kann Hackgut *oder* Pellets
# verbrennen, die Baureihe allein verrät es nicht.
BRENNSTOFF_ENTITAET = re.compile(r"(aktueller|gew(ä|ae)hlter) brennstoff", re.IGNORECASE)


BRENNSTOFF_ART: tuple[tuple[str, str], ...] = (
    (r"pellet", "pellets"),
    (r"hackgut|hackschnitzel", "hackgut"),
    (r"scheitholz|st(ü|ue)ckholz|stueckholz", "scheitholz"),
)


# Dritte Quelle: der Name der Funktion. Die Windhager-Baureihen sind sprechend
# genug, und bei fremden Anlagen ist es oft das Einzige, was vorliegt.
NAME_ART: tuple[tuple[str, str], ...] = (
    (r"aerowin|w(ä|ae)rmepumpe|heat\s?pump", "waermepumpe"),
    (r"purowin", "hackgut"),
    (r"biowin|pelletswin|pelletskessel|\bpellet", "pellets"),
    (r"logwin|vario\s?win|scheitholz|st(ü|ue)ckholz|holzvergaser", "scheitholz"),
    (r"duo\s?win|gas|\b(ö|oe)l\b|brennwert|therme", "gas_oel"),
)


def kesselart_erkennen(teile: list[dict[str, Any]]) -> str | None:
    """Art des Wärmeerzeugers aus den Anlagenteilen ableiten.

    Gibt einen Schlüssel aus ``const.KESSELARTEN`` zurück oder ``None``, wenn
    sich nichts sagen lässt. ``None`` heißt „neutral zeichnen" – nicht raten.
    Die Funktion wirkt ausschließlich auf die Zeichnung.
    """
    kessel = [t for t in teile if _art(t.get("fct_type")) == "kessel"]
    for teil in kessel:
        with contextlib.suppress(TypeError, ValueError):
            if art := KESSELART_JE_FCT.get(int(teil.get("fct_type"))):
                return art
    for teil in kessel:
        for eintrag in teil.get("entitaeten", []):
            if not BRENNSTOFF_ENTITAET.search(eintrag.get("name") or ""):
                continue
            text = str(eintrag.get("text") or "")
            for muster, art in BRENNSTOFF_ART:
                if re.search(muster, text, re.IGNORECASE):
                    return art
    for teil in kessel:
        for muster, art in NAME_ART:
            if re.search(muster, teil.get("name") or "", re.IGNORECASE):
                return art
    return None


def passt(name: str, muster: tuple[re.Pattern, ...]) -> bool:
    """Ob einer der Namensausdrücke greift."""
    return any(m.search(name) for m in muster)


def traegt(eintrag: dict, schluessel: tuple[str, ...]) -> bool:
    """Ob der Eintrag einen der gesuchten kanonischen Schlüssel trägt."""
    return bool(schluessel) and eintrag.get("schluessel") in schluessel


def treffer(
    entitaeten: list[dict[str, Any]], muster: tuple[re.Pattern, ...], *schluessel: str
) -> list[dict[str, Any]]:
    """Passende Einträge, die verlässlichsten zuerst.

    Die Adresse eines Datenpunkts ist eindeutig, sein Name nicht: Ein Einsteller
    der Serviceebene kann so heißen wie der Messwert, den er begrenzt. Wer über
    den Schlüssel passt, steht deshalb vorn.
    """
    ueber_schluessel = [e for e in entitaeten if traegt(e, schluessel)]
    ueber_namen = [
        e for e in entitaeten if not traegt(e, schluessel) and passt(e.get("name") or "", muster)
    ]
    return ueber_schluessel + ueber_namen


def finde(entitaeten: list[dict[str, Any]], muster: str, *schluessel: str) -> dict[str, Any] | None:
    """Erste passende Entität; eine mit Wert hat Vorrang.

    Ein Wert ist keine Bedingung: Das Schaubild entsteht, während die Anlage
    noch eingelesen wird, und bliebe sonst leer.
    """
    gefunden = treffer(entitaeten, (re.compile(muster, re.IGNORECASE),), *schluessel)
    if not gefunden:
        return None
    return next((e for e in gefunden if e.get("hat_wert")), gefunden[0])


def _werte_je_art(art: str, kesselwert: str | None) -> tuple[Wert, ...]:
    """Die Wertevorlage einer Art, mit dem gewählten zweiten Kesselwert."""
    vorlage = WERTE_JE_ART.get(art, ())
    if art != "kessel" or kesselwert != "brennkammer":
        return vorlage
    return (vorlage[0], (BRENNKAMMER_IST, "Brennkammer", ("combustion_chamber_temperature",)))


def _werte(
    entitaeten: list[dict[str, Any]], art: str, kesselwert: str | None = None
) -> list[dict[str, Any]]:
    """Die Messwerte eines Anlagenteils in der Reihenfolge des Schaubilds."""
    werte = []
    for muster, beschriftung, schluessel in _werte_je_art(art, kesselwert):
        if (treffer := finde(entitaeten, muster, *schluessel)) is not None:
            werte.append({"entity_id": treffer["entity_id"], "beschriftung": beschriftung})
    return werte


def _pumpe(entitaeten: list[dict[str, Any]], art: str) -> str | None:
    """Die Pumpe eines Anlagenteils, sofern sie als Zustand gemeldet wird."""
    muster, schluessel = PUMPE_JE_ART.get(art, ("", ()))
    if not muster:
        return None
    treffer = finde(
        [e for e in entitaeten if e.get("bereich") in PUMPE_BEREICHE], muster, *schluessel
    )
    return treffer["entity_id"] if treffer else None


def _mischer(entitaeten: list[dict[str, Any]]) -> str | None:
    """Der Stellwert des Heizkreismischers in Prozent, sofern gemeldet.

    Die Anlage nennt den Datenpunkt `1/21` „Mischer"; die kuratierte Tabelle
    „Mischer Stellwert". Beide Schreibweisen zählen.
    """
    treffer = finde(
        [e for e in entitaeten if (e.get("unit") or "") == "%" or e.get("bereich") == "sensor"],
        MISCHER_IST,
        "mixer_position",
    )
    return treffer["entity_id"] if treffer else None


# Woran ein Pumpen-/Relaismodul erkennen lässt, dass es eine Aufgabe hat: ein
# eigener **Messwert** oder eine der Funktionen aus Gruppe 29. Sollwerte zählen
# ausdrücklich nicht – „Solltemperatur ext. Wärmeanforderung" und
# „Digital-Sollwert WWK" meldet auch ein Modul, an dem nichts hängt. Deshalb
# sind alle Muster verankert: unverankert fischte
# `ext. wärmeanforderung` genau diesen Sollwert mit heraus.
MODUL_AUFGABE: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"^kesseltemperatur$", ("boiler_temperature",)),
    (r"^temperatur ist$", ()),
    (r"^ext\.? w(ä|ae)rmeanforderung$", ()),
    (r"^pumpensteuerung$", ()),
    (r"^relaisfunktion$", ()),
)


def modul_in_betrieb(entitaeten: list[dict[str, Any]]) -> bool:
    """Ob ein Pumpen-/Relaismodul an dieser Anlage überhaupt eine Aufgabe hat.

    Der ZSP ist ein Universalmodul: Es kann eine Pumpe regeln, eine externe
    Wärmeanforderung entgegennehmen oder einen Sammelalarm schalten – oder als
    Klemmenkasten dasitzen und nichts davon. Welche Aufgabe verdrahtet ist,
    sagt die Anlage nicht als Wert; sie sagt es dadurch, **welche Datenpunkte
    sie überhaupt beantwortet**. Fehlende beantwortet sie mit 404 bzw. 409, und
    die fliegen schon in `client._apply_metadata` heraus.

    Ein verdrahtetes Modul führt Kesseltemperatur (``0/7``), Pumpendrehzahl
    (``0/22``) oder externe Anforderung (``29/2``); ein unbenutztes meldet
    davon keinen einzigen, sondern nur Sollwerte und den Aktorentest. Ohne
    diese Unterscheidung stünde es im Schaubild als Kasten in der Leitung, durch
    den nichts fließt, mit Lampen, die nie angehen.
    """
    return _pumpe(entitaeten, "pumpenmodul") is not None or any(
        finde(entitaeten, muster, *schluessel) is not None for muster, schluessel in MODUL_AUFGABE
    )


# Bereiche, deren Zustand sich als Beschriftung im Bild lesen lässt.
WERT_BEREICHE = ("sensor", "number", "binary_sensor", "select")


def teil_kennung(teil: dict[str, Any]) -> str:
    """Stabile Kennung eines Anlagenteils für die Auswahl."""
    return str(teil.get("id") or teil.get("name") or "")


def waehlbare_werte(
    teile: list[dict[str, Any]], kesselwert: str | None = None
) -> list[dict[str, Any]]:
    """Je Anlagenteil die Werte, die zur Auswahl stehen, samt Vorgabe.

    Die Liste kommt aus der Erkennung, nicht aus einer gepflegten Tabelle – nur
    so trägt sie auch auf Baureihen, für die es hier kein Namensmuster gibt.
    """
    liste = []
    for teil in teile:
        art = _art(teil.get("fct_type"))
        werte = [
            {
                "entity": e["entity_id"],
                "name": e.get("name") or e["entity_id"],
                "symbol": symbol_fuer_wert(e, teil.get("fct_type")),
            }
            for e in teil["entitaeten"]
            if e.get("bereich") in WERT_BEREICHE and e.get("kategorie") != "config"
        ]
        if not werte:
            continue
        liste.append(
            {
                "id": teil_kennung(teil),
                "titel": teil.get("name") or "",
                "art": art,
                "symbol": symbol_je_fct(teil.get("fct_type")),
                "werte": sorted(werte, key=lambda w: w["name"]),
                "vorgabe": [w["entity_id"] for w in _werte(teil["entitaeten"], art, kesselwert)],
            }
        )
    return liste


def _gewaehlte_werte(
    teil: dict[str, Any], art: str, kesselwert: str | None, gewaehlt: list[str]
) -> list[dict[str, Any]]:
    """Die gewählten Werte in ihrer Reihenfolge, mit bekannter Beschriftung.

    Was das Schaubild ohnehin kennt, behält seine Rolle (`oben`, `unten`); alles
    Übrige bekommt seinen Namen. Ohne die Rolle wüsste der Puffer nicht mehr,
    welcher Fühler oben sitzt.
    """
    bekannt = {w["entity_id"]: w for w in _werte(teil["entitaeten"], art, kesselwert)}
    namen = {e["entity_id"]: e.get("name") or e["entity_id"] for e in teil["entitaeten"]}
    werte = []
    for entity in gewaehlt:
        if entity in bekannt:
            werte.append(bekannt[entity])
        elif entity in namen:
            werte.append({"entity_id": entity, "beschriftung": namen[entity]})
    return werte


def zeichenbare_module(
    teile: list[dict[str, Any]],
    kesselwert: str | None = None,
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
    zeichnungen: dict[str, str] | None = None,
    modulpumpe: bool = False,
) -> list[dict[str, Any]]:
    """Anlagenteile, die sich zeichnen lassen, mit ihren Werten.

    Warmwasser bekommt einen eigenen Kasten, obwohl seine Datenpunkte am
    Heizkreis hängen – auf dem Display der Anlage steht es genauso.
    """
    module: list[dict[str, Any]] = []
    for teil in teile:
        # Eine Wärmequelle bringt ihre Bauart selbst mit; sie hat keinen
        # Funktionstyp, weil sie nicht an der Steuerung hängt.
        eigene_art = teil.get("art")
        art = eigene_art or _art(teil.get("fct_type"))
        # Ein Solarkreis der Steuerung trägt dieselbe Bauart wie eine
        # angelegte Solaranlage. Nur die mitgebrachte Bauart trennt beide.
        ist_quelle = bool(eigene_art)
        kennung = teil_kennung(teil)
        if kennung in set(teile_aus or ()):
            continue
        gewaehlt = (auswahl or {}).get(kennung)
        werte = (
            _gewaehlte_werte(teil, art, kesselwert, gewaehlt)
            if gewaehlt is not None
            else _werte(teil["entitaeten"], art, kesselwert)
        )
        # Das Pumpen-/Relaismodul wird auch ohne Messwert gezeichnet: Seine
        # Kesseltemperatur misst bei einer Fernwärmeübergabe den Speicher auf
        # der anderen Seite – im Schaubild sagt die Zahl nichts. Dass das Modul
        # in der Leitung sitzt, muss man trotzdem sehen; seinen Zustand zeigen
        # die Lampen. Ein Modul ohne Aufgabe bleibt aber draußen, siehe
        # `modul_in_betrieb`.
        if art == "pumpenmodul" and not modul_in_betrieb(teil["entitaeten"]):
            continue
        # Eine Wärmequelle wird auch ohne Messwert gezeichnet: Dass sie in der
        # Anlage steht, ist die Aussage; ob sie liefert, sagt ihre Lampe.
        if werte or art == "pumpenmodul" or ist_quelle:
            module.append(
                {
                    "kennung": kennung,
                    "zeichnung": (zeichnungen or {}).get(kennung),
                    "titel": teil["name"],
                    "art": art,
                    "werte": werte,
                    # Am Pumpen-/Relaismodul ist die Drehzahl nur dann eine
                    # Pumpe, wenn auch eine angeschlossen ist. Das entscheidet
                    # die Option, nicht der Datenpunkt.
                    "pumpe": (
                        _pumpe(teil["entitaeten"], art)
                        if modulpumpe or art != "pumpenmodul"
                        else None
                    ),
                    # Die Wärmelieferung tritt bei einer Quelle an die Stelle der
                    # Pumpe: An ihr hängen Lampe und Fluss.
                    "lieferung": (
                        e["entity_id"]
                        if ist_quelle and (e := finde(teil["entitaeten"], LIEFERUNG))
                        else None
                    ),
                    # Ob die Quelle ein Laufrad bekommt, sagt ihre Einstellung:
                    # Eine Solaranlage hat eine Pumpe, ein Heizstab nicht.
                    "quellenpumpe": ist_quelle and bool(teil.get("quellenpumpe")),
                    "mischer": _mischer(teil["entitaeten"]) if art == "heizkreis" else None,
                    # Die Temperatur, die tatsächlich in den Heizkörper geht.
                    # Nicht der Sollwert: Der steht auch dann auf 45 °C, wenn
                    # der Kreis abgeschaltet ist und der Körper kalt hängt.
                    "vorlauf": (
                        e["entity_id"]
                        if art == "heizkreis"
                        and (e := finde(teil["entitaeten"], VORLAUF_IST, "flow_temperature"))
                        else None
                    ),
                    # Für Auswertungen, die über die angezeigten Werte
                    # hinausgehen – etwa die Lampen des Pumpen-/Relaismoduls.
                    "entitaeten": teil["entitaeten"],
                    # Für das Glutbett, unabhängig davon, welcher Wert im Bild
                    # steht: Leistung zuerst, Brennkammertemperatur als Ersatz.
                    "leistung": (
                        e["entity_id"]
                        if art == "kessel"
                        and (e := finde(teil["entitaeten"], KESSELLEISTUNG_IST, "boiler_power"))
                        else None
                    ),
                    "brennkammer": (
                        e["entity_id"]
                        if art == "kessel"
                        and (
                            e := finde(
                                teil["entitaeten"],
                                BRENNKAMMER_IST,
                                "combustion_chamber_temperature",
                            )
                        )
                        else None
                    ),
                }
            )
        # Hängt an diesem Kreis eine Warmwasserbereitung, wird sie als eigener
        # Anlagenteil dahinter gezeichnet.
        if (
            art == "heizkreis"
            and finde(teil["entitaeten"], WARMWASSER_IST, "dhw_temperature") is not None
        ):
            wasser = _werte(teil["entitaeten"], "wasser")
            if wasser:
                module.append(
                    {
                        "kennung": f"{kennung}-wasser",
                        "zeichnung": (zeichnungen or {}).get(f"{kennung}-wasser"),
                        "titel": "Warmwasser",
                        "art": "wasser",
                        "werte": wasser,
                        "pumpe": _pumpe(teil["entitaeten"], "wasser"),
                    }
                )
        # Auch an einer eigenständigen Warmwasserfunktion (fctType 2) hängt die
        # Zirkulation als Datenpunkt, nicht als eigene Funktion.
        if art in ("heizkreis", "wasser") and finde(
            teil["entitaeten"], ZIRKULATION_IST, "dhw_circulation_temperature"
        ):
            kreis = _werte(teil["entitaeten"], "zirkulation")
            if kreis:
                module.append(
                    {
                        "kennung": f"{kennung}-zirkulation",
                        "zeichnung": (zeichnungen or {}).get(f"{kennung}-zirkulation"),
                        "titel": "Zirkulation",
                        "art": "zirkulation",
                        "werte": kreis,
                        "pumpe": _pumpe(teil["entitaeten"], "zirkulation"),
                    }
                )
    return module
