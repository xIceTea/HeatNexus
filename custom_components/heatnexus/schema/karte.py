"""Die `picture-elements`-Karte und die Nutzdaten des Schaubilds je Anlage."""

from __future__ import annotations

from typing import Any

from .bauteile import bauteilnamen, kessellampe, lampenpunkt, waermeflaeche
from .farben import FARBABBILDUNGEN, FARBEN, THEMA_HELL, farben_umstellen
from .werte import (
    ANALOG_SOLLWERT,
    BRENNKAMMER_HEISS,
    BRENNKAMMER_KALT,
    ERZEUGER_ARTEN,
    finde,
    kesselart_erkennen,
    waehlbare_werte,
    zeichenbare_module,
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
    MISCHER_MARKE,
    MISCHER_Y,
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
    beschriftungen,
    datenadresse,
    schaubild_svg,
    speicherfuehler,
)


def anlagenschema(
    teile: list[dict[str, Any]],
    kesselart: str | None = None,
    kesselwert: str | None = None,
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
    zeichnungen: dict[str, str] | None = None,
    mischer: bool = True,
    modulpumpe: bool = False,
) -> dict[str, Any] | None:
    """Eine `picture-elements`-Karte für eine Anlage – oder nichts.

    Erwartet die Anlagenteile in der Form, die `dashboard.anlagen_lesen` liefert.
    ``kesselart`` wählt die Kesselzeichnung; ohne Angabe wird sie aus den
    Anlagenteilen abgeleitet.

    **Beide Farbsätze werden mitgeliefert**, nicht einer nach Vorgabe: Das Bild
    steckt als `data:`-Adresse in einem `<img>` und erbt dort kein CSS, die
    Karte wird aber serverseitig gebaut – zu diesem Zeitpunkt ist das
    Erscheinungsbild des Betrachters nicht bekannt, und bei einem Umschalten
    gäbe es niemanden, der neu zeichnet. ``image`` trägt den hellen Satz,
    ``dark_mode_image`` den dunklen; genau so erwartet es die
    `picture-elements`-Karte. Die eigene Oberfläche wählt mit derselben Angabe
    (`panel/daten.py`).
    """
    module = zeichenbare_module(teile, kesselwert, auswahl, teile_aus, zeichnungen, modulpumpe)
    # Ein Bild aus lauter leeren Kästen hilft niemandem: Mindestens ein
    # Anlagenteil muss etwas messen.
    if not any(m["werte"] for m in module):
        return None

    if kesselart is None:
        kesselart = kesselart_erkennen(teile)
    svg, breite = schaubild_svg(module, kesselart, mischer)

    elemente: list[dict[str, Any]] = []
    pumpen: list[dict[str, Any]] = []
    brenner: list[dict[str, Any]] = []
    mischer: list[dict[str, Any]] = []
    heizkoerper: list[dict[str, Any]] = []
    schichtung: list[dict[str, Any]] = []
    speicher: list[dict[str, Any]] = []
    lampen: list[dict[str, Any]] = []
    waerme: list[dict[str, Any]] = []
    uebergabe: list[dict[str, Any]] = []
    # Wer dem Speicher Wärme entnimmt: alle Pumpen der Verbraucher. Wird
    # gleich zweimal gebraucht – für die Marke am Speicher und für seine
    # Stichleitung.
    entnahme = [m["pumpe"] for m in module if m.get("pumpe") and m["art"] in ENTNAHME_ARTEN]
    # Wer dem Speicher Wärme zuführt, ohne an der Steuerung zu hängen. Eine
    # liefernde Quelle lädt ihn, auch wenn die Ladepumpe steht.
    lieferungen = [m["lieferung"] for m in module if m.get("lieferung")]

    for platz, modul in enumerate(module):
        x = RAND + platz * MODUL_BREITE
        elemente += beschriftungen(x, modul, breite)
        if modul.get("pumpe"):
            # Die Pumpe sitzt im Rücklauf, unterhalb ihres Anlagenteils.
            mitte = x + MODUL_BREITE // 2
            oben, unten = KANTEN_JE_ART.get(modul["art"], KANTEN_STANDARD)
            pumpen.append(
                {
                    "entity": modul["pumpe"],
                    "left": f"{mitte / breite * 100:.2f}%",
                    "top": f"{RUECKLAUF_Y / HOEHE * 100:.2f}%",
                    "titel": modul["titel"],
                    # Die beiden senkrechten Stichleitungen dieses Anlagenteils.
                    # Sie strömen nur, solange **seine** Pumpe fördert – daran
                    # sieht man, wohin die Wärme gerade geht. Die waagrechten
                    # Leitungen strömen dagegen immer, sobald irgendwo etwas
                    # läuft: Dort steht das Wasser ja auch nicht still.
                    "vorlauf_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
                    "vorlauf_hoehe": f"{(oben - VORLAUF_Y) / HOEHE * 100:.2f}%",
                    "ruecklauf_top": f"{unten / HOEHE * 100:.2f}%",
                    "ruecklauf_hoehe": f"{(RUECKLAUF_Y - unten) / HOEHE * 100:.2f}%",
                    # Ein Speicher strömt in beide Richtungen: Seine eigene
                    # Pumpe lädt ihn, entnommen wird ihm von den Pumpen der
                    # Verbraucher – und dabei dreht die Ladepumpe nicht.
                    "entnahme": entnahme if modul["art"] == "puffer" else [],
                    # Eine Quelle lädt den Speicher, ohne dass seine Ladepumpe
                    # fördert. Ohne sie stünde die Stichleitung still, während
                    # der Speicher „lädt" anzeigt.
                    "quellen": lieferungen if modul["art"] == "puffer" else [],
                    "erzeuger": modul["art"] in ERZEUGER_ARTEN,
                }
            )
        # Eine Wärmequelle führt keinen Pumpendatenpunkt, speist aber ein.
        # Stichleitung, Lampe und Laufrad hängen deshalb an ihrer Wärmelieferung.
        if modul.get("lieferung"):
            mitte = x + MODUL_BREITE // 2
            oben, unten = KANTEN_JE_ART.get(modul["art"], KANTEN_STANDARD)
            pumpen.append(
                {
                    "entity": modul["lieferung"],
                    "left": f"{mitte / breite * 100:.2f}%",
                    "top": f"{RUECKLAUF_Y / HOEHE * 100:.2f}%",
                    "titel": modul["titel"],
                    "nur_strang": not modul.get("quellenpumpe"),
                    "erzeuger": True,
                    "vorlauf_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
                    "vorlauf_hoehe": f"{(oben - VORLAUF_Y) / HOEHE * 100:.2f}%",
                    "ruecklauf_top": f"{unten / HOEHE * 100:.2f}%",
                    "ruecklauf_hoehe": f"{(RUECKLAUF_Y - unten) / HOEHE * 100:.2f}%",
                }
            )
            # Die Wärme im Bauteil selbst, wie am Pumpen-/Relaismodul: Sie sagt,
            # dass die Quelle arbeitet, ohne eine Temperatur zu behaupten.
            if (flaeche := waermeflaeche(modul["art"], modul.get("zeichnung"))) is not None:
                waerme.append(
                    {
                        "entity": modul["lieferung"],
                        "left": f"{(x + flaeche['x']) / breite * 100:.2f}%",
                        "top": f"{flaeche['y'] / HOEHE * 100:.2f}%",
                        "breite": f"{flaeche['breite'] / breite * 100:.2f}%",
                        "hoehe": f"{flaeche['hoehe'] / HOEHE * 100:.2f}%",
                        "ecke": (
                            f"{flaeche['ecke'] / flaeche['breite'] * 100:.2f}% /"
                            f" {flaeche['ecke'] / flaeche['hoehe'] * 100:.2f}%"
                        ),
                        "dreh": flaeche["dreh"],
                        "titel": modul["titel"],
                    }
                )
            stelle = lampenpunkt(modul["art"], zeichnung=modul.get("zeichnung"))
            if stelle is not None:
                lx, ly, lr = stelle
                lampen.append(
                    {
                        "entity": modul["lieferung"],
                        "left": f"{(x + lx) / breite * 100:.2f}%",
                        "top": f"{ly / HOEHE * 100:.2f}%",
                        "groesse": f"{(2 * lr) / breite * 100:.2f}%",
                        "art": "betrieb",
                        "zweck": "quelle",
                        "titel": modul["titel"],
                    }
                )
        # Der Mischer zeigt seine Stellung, nicht Bewegung: Ein dauernd
        # drehendes Ventil läse sich wie eine Pumpe, und die dreht sich im
        # Bild schon. Der Anzeiger schwenkt, das Stück Vorlauf darüber färbt
        # sich nach der Beimischung.
        if modul.get("mischer"):
            mitte = x + MODUL_BREITE // 2
            oben, _unten = KANTEN_JE_ART["heizkreis"]
            mischer.append(
                {
                    "entity": modul["mischer"],
                    "left": f"{mitte / breite * 100:.2f}%",
                    "top": f"{MISCHER_Y / HOEHE * 100:.2f}%",
                    "groesse": f"{MISCHER_MARKE / breite * 100:.2f}%",
                    # Das Stück Vorlauf zwischen Leitung und Ventil.
                    "stutzen_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
                    "stutzen_hoehe": f"{(oben - VORLAUF_Y) / HOEHE * 100:.2f}%",
                    "titel": modul["titel"],
                }
            )
        # Der Heizkörper färbt sich nach dem, was durch ihn fließt: kalt in der
        # Farbe des Rücklaufs, heiß in der des Vorlaufs. Ohne gemessene
        # Vorlauftemperatur bleibt es bei der Zeichnung.
        if modul["art"] == "heizkreis" and modul.get("vorlauf"):
            heizkoerper.append(
                {
                    "entity": modul["vorlauf"],
                    "left": f"{(x + HEIZKOERPER_X) / breite * 100:.2f}%",
                    "top": f"{HEIZKOERPER_Y / HOEHE * 100:.2f}%",
                    "breite": f"{HEIZKOERPER_BREITE / breite * 100:.2f}%",
                    "hoehe": f"{HEIZKOERPER_HOEHE / HOEHE * 100:.2f}%",
                    # Anteile der Ebenenbreite, nicht Bildpunkte – siehe
                    # HEIZKOERPER_GLIED.
                    "glied": f"{HEIZKOERPER_GLIED / HEIZKOERPER_BREITE * 100:.4f}%",
                    "raster": f"{HEIZKOERPER_RASTER / HEIZKOERPER_BREITE * 100:.4f}%",
                    "glanz_von": f"{HEIZKOERPER_GLANZ_VON / HEIZKOERPER_BREITE * 100:.4f}%",
                    "glanz_bis": f"{HEIZKOERPER_GLANZ_BIS / HEIZKOERPER_BREITE * 100:.4f}%",
                    "anzahl": HEIZKOERPER_ANZAHL,
                    "kalt": HEIZKOERPER_KALT,
                    "heiss": HEIZKOERPER_HEISS,
                    "titel": modul["titel"],
                }
            )

        # Der Wärmeerzeuger bekommt ein Glutbett, das mitgeht, solange er
        # Leistung bringt. Maßgeblich ist die Kesselleistung: Die Betriebsphase
        # heißt auf jeder Baureihe anders, eine Zahl über null nicht.
        if modul["art"] == "kessel":
            # Erste Wahl bleibt die Leistung, unabhängig davon, welcher Wert
            # angezeigt wird. Fehlt sie, dient die Brennkammertemperatur als
            # Ersatzskala – dort heißt kalt 100 °C und voll 500 °C.
            leistung = modul.get("leistung")
            ersatz = modul.get("brennkammer")
            if leistung or ersatz:
                mitte = x + MODUL_BREITE // 2
                brenner.append(
                    {
                        "entity": leistung,
                        "ersatz": ersatz,
                        "ersatz_min": BRENNKAMMER_KALT,
                        "ersatz_max": BRENNKAMMER_HEISS,
                        "left": f"{mitte / breite * 100:.2f}%",
                        "top": f"{GLUTBETT_Y / HOEHE * 100:.2f}%",
                        "breite": f"{GLUTBETT_BREITE / breite * 100:.2f}%",
                        "titel": modul["titel"],
                    }
                )
                # Die Betriebslampe über dem gezeichneten roten Punkt. Sie
                # leuchtet grün, solange der Erzeuger läuft, und deckt das Rot
                # dabei ab.
                if (stelle := kessellampe(kesselart, modul.get("zeichnung"))) is not None:
                    lx, ly, lr = stelle
                    lampen.append(
                        {
                            "entity": leistung,
                            "ersatz": ersatz,
                            "ersatz_min": BRENNKAMMER_KALT,
                            "left": f"{(x + lx) / breite * 100:.2f}%",
                            "top": f"{ly / HOEHE * 100:.2f}%",
                            "groesse": f"{(2 * lr) / breite * 100:.2f}%",
                            "art": "betrieb",
                            "zweck": "erzeuger",
                            "titel": modul["titel"],
                        }
                    )

    # Der Wärmeerzeuger meldet keine eigene Pumpe – sein Wasser bewegt die
    # Pufferladepumpe. Nur die Leitung, keine Pumpenmarke: An dieser Stelle
    # sitzt keine Pumpe.
    ladepumpe = next((m["pumpe"] for m in module if m["art"] == "puffer" and m.get("pumpe")), None)
    if ladepumpe:
        for platz, modul in enumerate(module):
            if modul["art"] != "kessel" or modul.get("pumpe"):
                continue
            mitte = RAND + platz * MODUL_BREITE + MODUL_BREITE // 2
            oben, unten = KANTEN_JE_ART.get("kessel", KANTEN_STANDARD)
            pumpen.append(
                {
                    "entity": ladepumpe,
                    "left": f"{mitte / breite * 100:.2f}%",
                    "top": f"{RUECKLAUF_Y / HOEHE * 100:.2f}%",
                    "titel": modul["titel"],
                    "nur_strang": True,
                    "erzeuger": True,
                    "vorlauf_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
                    "vorlauf_hoehe": f"{(oben - VORLAUF_Y) / HOEHE * 100:.2f}%",
                    "ruecklauf_top": f"{unten / HOEHE * 100:.2f}%",
                    "ruecklauf_hoehe": f"{(RUECKLAUF_Y - unten) / HOEHE * 100:.2f}%",
                }
            )

    # Die Lampen des Pumpen-/Relaismoduls. Sie hängen am Analog-Sollwert: über
    # null fordert das Modul Wärme an.
    for platz, modul in enumerate(module):
        if modul["art"] != "pumpenmodul":
            continue
        soll = finde(modul.get("entitaeten") or [], ANALOG_SOLLWERT, "analog_setpoint")
        if soll is None:
            continue
        x = RAND + platz * MODUL_BREITE
        for lx, ly, r in (*ZSP_KLEMMEN, ZSP_BETRIEBSLAMPE):
            lampen.append(
                {
                    "entity": soll["entity_id"],
                    "left": f"{(x + lx) / breite * 100:.2f}%",
                    "top": f"{ly / HOEHE * 100:.2f}%",
                    "groesse": f"{(2 * r) / breite * 100:.2f}%",
                    "art": "betrieb" if (lx, ly, r) == ZSP_BETRIEBSLAMPE else "klemme",
                    "zweck": "anforderung",
                    "titel": modul["titel"],
                }
            )
        gx, gy, gb, gh = ZSP_GEHAEUSE
        px, py, pr = ZSP_PUMPE
        uebergabe.append(
            {
                "entity": soll["entity_id"],
                "left": f"{(x + gx) / breite * 100:.2f}%",
                "top": f"{gy / HOEHE * 100:.2f}%",
                "breite": f"{gb / breite * 100:.2f}%",
                "hoehe": f"{gh / HOEHE * 100:.2f}%",
                "ecke": f"{12 / gb * 100:.2f}% / {12 / gh * 100:.2f}%",
                # Das gezeichnete Laufrad steht still. Darüber liegt ein eigenes,
                # das sich dreht, solange angefordert wird.
                "rad_left": f"{(x + px) / breite * 100:.2f}%",
                "rad_top": f"{py / HOEHE * 100:.2f}%",
                "rad_groesse": f"{(2 * pr) / breite * 100:.2f}%",
                "titel": modul["titel"],
            }
        )

    # Die Kesseltemperatur des ersten Wärmeerzeugers. Ohne sie liesse sich
    # nicht sagen, ob die laufende Ladepumpe wirklich Wärme in den Puffer
    # bringt oder nur umwälzt.
    kessel_ist = next(
        (
            w["entity_id"]
            for m in module
            if m["art"] == "kessel"
            for w in m["werte"]
            if w.get("beschriftung") == "Kessel"
        ),
        None,
    )
    # Der eingefärbte Inhalt von Puffer und Boiler. Beide laufen über dieselbe
    # Ebene: Der Puffer hat zwei Fühler und zeigt damit eine Schichtung, der
    # Boiler einen und wird gleichmäßig eingefärbt.
    for platz, modul in enumerate(module):
        masse = SPEICHER_ARTEN.get(modul["art"])
        if masse is None:
            continue
        oben, unten = speicherfuehler(modul)
        if oben is None:
            continue
        x = RAND + platz * MODUL_BREITE
        schichtung.append(
            {
                "oben": oben,
                "unten": unten,
                "left": f"{(x + masse['x']) / breite * 100:.2f}%",
                "top": f"{masse['y'] / HOEHE * 100:.2f}%",
                "breite": f"{masse['breite'] / breite * 100:.2f}%",
                "hoehe": f"{masse['hoehe'] / HOEHE * 100:.2f}%",
                # Der Eckradius als Anteil je Achse – sonst verzieht er sich,
                # sobald die Karte das Bild skaliert.
                "ecke": (
                    f"{masse['ecke'] / masse['breite'] * 100:.2f}%"
                    f" / {masse['ecke'] / masse['hoehe'] * 100:.2f}%"
                ),
                "kalt": masse["kalt"],
                "heiss": masse["heiss"],
                # Ohne Messwerte trägt die Fläche denselben Verlauf, den die
                # Zeichnung sonst selbst gemalt hätte.
                "grund": masse["grund"],
                "titel": modul["titel"],
            }
        )

    for platz, modul in enumerate(module):
        if modul["art"] != "puffer":
            continue
        mitte = RAND + platz * MODUL_BREITE + MODUL_BREITE // 2
        oben = next(
            (w["entity_id"] for w in modul["werte"] if w.get("beschriftung") == "oben"),
            None,
        )
        unten = next(
            (w["entity_id"] for w in modul["werte"] if w.get("beschriftung") == "unten"),
            None,
        )
        speicher.append(
            {
                # „lädt" heißt: Die Ladepumpe fördert **und** der Kessel ist
                # wärmer als der obere Pufferbereich. Die Pumpe allein genügt
                # nicht – sie läuft auch, wenn der Kessel gerade direkt in
                # einen Heizkreis fährt und dem Puffer nichts zugeht.
                #
                # „entlädt": Ein Verbraucher zieht, ohne dass geladen wird.
                # Läuft beides, bleibt es bei „lädt"; welche Richtung netto
                # überwiegt, hängt vom Massenstrom ab, und den misst die
                # Anlage nicht.
                "laden": modul.get("pumpe"),
                "quellen": lieferungen,
                "kessel": kessel_ist,
                "oben": oben,
                "unten": unten,
                "toleranz": LADE_TOLERANZ,
                "entnahme": entnahme,
                "left": f"{mitte / breite * 100:.2f}%",
                "top": f"{SPEICHER_Y / HOEHE * 100:.2f}%",
                "titel": modul["titel"],
            }
        )

    # Lage der beiden Leitungen in Prozent des Bildes. Die Oberfläche legt
    # darüber eine bewegte Ebene: Ein Bild als Daten-URL kennt keine Zustände
    # aus Home Assistant, es kann also nicht selbst anzeigen, ob etwas fließt.
    leitungen = {
        "left": f"{RAND / breite * 100:.2f}%",
        "width": f"{(breite - 2 * RAND) / breite * 100:.2f}%",
        "vorlauf_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
        "ruecklauf_top": f"{RUECKLAUF_Y / HOEHE * 100:.2f}%",
    }

    return {
        "type": "picture-elements",
        "image": datenadresse(farben_umstellen(svg, THEMA_HELL)),
        "dark_mode_image": datenadresse(svg),
        # Die `picture-elements`-Karte kennt nur hell und dunkel. Wer mehr
        # Farbsätze braucht, stellt die Zeichnung selbst um.
        "svg": svg,
        # Die Breite der Zeichnung. Damit rechnet die Oberfläche ihre
        # Überlagerungen auf denselben Maßstab wie das Bild.
        "breite": breite,
        "elements": elemente,
        # Welche Anlagenteile gezeichnet sind – für die Wahl der Zeichnung.
        "zeichenbar": [
            {"id": m.get("kennung") or m["titel"], "titel": m["titel"], "art": m["art"]}
            for m in module
        ],
        "leitungen": leitungen,
        # Die Pumpen liegen nicht im Bild: Ein Standbild kann sich nicht
        # drehen. Sie werden als eigene Marken darübergelegt.
        "pumpen": pumpen,
        # Ebenso das Glutbett der Wärmeerzeuger und die Mischerstellung.
        "brenner": brenner,
        "mischer": mischer,
        # Der Heizkörper, eingefärbt nach seiner Vorlauftemperatur.
        "heizkoerper": heizkoerper,
        # Die Schichtung des Puffers aus seinen beiden Fühlern.
        "schichtung": schichtung,
        # Ob der Puffer gerade beladen oder entleert wird.
        "speicher": speicher,
        # Die Lampen des Pumpen-/Relaismoduls, siehe ZSP_KLEMMEN.
        "lampen": lampen,
        # Wärme im Gehäuse, drehendes Laufrad und Abgabe nach außen, solange
        # das Modul Wärme anfordert.
        "uebergabe": uebergabe,
        # Wärme im Bauteil einer Quelle, solange sie liefert.
        "waerme": waerme,
    }


def schaubild_daten(
    anlagen: list[dict[str, Any]],
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
    zeichnungen: dict[str, str] | None = None,
    mischer: bool = True,
) -> list[dict[str, Any]]:
    """Schaubild je Anlage, wie die Lovelace-Karte es bekommt.

    Die Kennung entscheidet, welche Anlage eine Karte zeigt – nicht die Reihenfolge.
    """
    return [
        {
            "id": anlage.get("id") or anlage["name"],
            "name": anlage["name"],
            **schaubild_nutzdaten(anlage, auswahl, teile_aus, zeichnungen, mischer),
        }
        for anlage in anlagen
    ]


def schaubild_nutzdaten(
    anlage: dict[str, Any],
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
    zeichnungen: dict[str, str] | None = None,
    mischer: bool = True,
) -> dict[str, Any]:
    """Die Schaubild-Felder einer Anlage – Bilder, Lagen, Bewegung.

    Oberfläche und Karte lesen dieselben Felder; zwei Aufbauwege wären zwei Quellen.
    """
    bild = anlagenschema(
        anlage["teile"],
        anlage.get("kesselart"),
        anlage.get("kesselwert"),
        auswahl,
        teile_aus,
        zeichnungen,
        mischer,
        anlage.get("modulpumpe", False),
    )
    return {
        # Die Zeichnung geht **einmal** hinaus, dazu die Farbtabellen. Welcher
        # Satz gilt, weiß erst der Browser; er tauscht die Werte selbst.
        "schema_svg": bild["svg"] if bild else None,
        # Maßstab der Überlagerungen: Sie sollen mit dem Bild wachsen und
        # schrumpfen, nicht in Bildpunkten stehenbleiben.
        "schema_breite": bild.get("breite") if bild else None,
        # Was sich einstellen lässt: je Anlagenteil die Werte dieser Anlage.
        "schema_teile": waehlbare_werte(anlage["teile"], anlage.get("kesselwert")),
        # Die gezeichneten Anlagenteile und die Zeichnungen, die zur Wahl stehen.
        "schema_zeichenbar": bild.get("zeichenbar") if bild else [],
        "schema_bauteile": bauteilnamen(),
        # Die Grundfarben für die Überlagerungen – Mischer, Heizkörper,
        # Schichtung. Sie liegen über dem Bild und erben dessen Farben nicht.
        "schema_grundfarben": {
            rolle: FARBEN[rolle] for rolle in ("vorlauf", "ruecklauf", "warm", "kalt")
        },
        # Je Thema eine eigene Kopie: Eine flache reichte die Tabellen selbst
        # heraus, und wer sie änderte, änderte den Modulzustand mit.
        "schema_farben": (
            {thema: dict(werte) for thema, werte in FARBABBILDUNGEN.items()} if bild else {}
        ),
        "schema_werte": (
            [
                {
                    "entity": el["entity"],
                    "left": el["style"]["left"],
                    "top": el["style"]["top"],
                }
                for el in bild["elements"]
            ]
            if bild
            else []
        ),
        "schema_pumpen": bild.get("pumpen", []) if bild else [],
        # Bewegung im Schaubild: die Leitungen strömen, solange eine Pumpe
        # läuft, das Glutbett glimmt, solange der Kessel Leistung bringt.
        "schema_leitungen": bild.get("leitungen") if bild else None,
        "schema_brenner": bild.get("brenner", []) if bild else [],
        "schema_anforderung": bild.get("anforderung", []) if bild else [],
        "schema_mischer": bild.get("mischer", []) if bild else [],
        # Der Heizkörper färbt sich nach seiner Vorlauftemperatur.
        "schema_heizkoerper": bild.get("heizkoerper", []) if bild else [],
        # Die Schichtung des Puffers – oben und unten je nach Messwert.
        "schema_schichtung": bild.get("schichtung", []) if bild else [],
        "schema_lampen": bild.get("lampen", []) if bild else [],
        "schema_uebergabe": bild.get("uebergabe", []) if bild else [],
        "schema_waerme": bild.get("waerme", []) if bild else [],
        "schema_speicher": bild.get("speicher", []) if bild else [],
    }
