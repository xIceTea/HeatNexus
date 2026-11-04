"""Zeilen des Systemstatus, geteilt von den Baureihen und der ganzen Anlage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Statuszeile:
    """Muster, Beschriftung, Symbol, kanonische Schlüssel und wo die Zeile erscheint.

    `panel` ist der Systemstatus im Panel, `karte` die Liste „Zustand“ der Schaubild-Karte.
    Ab zwei Erzeugern setzt `kopf` den Wert mit `vorsatz` in die Kopfzeile des Erzeugers,
    `regelung` zieht die Zeile in den Abschnitt „Regelung“.
    """

    muster: str
    titel: str
    symbol: str
    schluessel: tuple[str, ...] = ()
    panel: bool = False
    karte: bool = False
    kopf: bool = False
    vorsatz: str = ""
    regelung: bool = False

    @property
    def zeile(self) -> tuple[str, str, str, tuple[str, ...]]:
        """Die Zeile als Eintrag einer Mustervorlage."""
        return (self.muster, self.titel, self.symbol, self.schluessel)


# Wie ein Erzeuger gerade läuft. Die Laufzeit entsteht aus dem Zustand: Sie
# zählt, solange das Aggregat läuft, und bleibt danach als Dauer des letzten Laufs.
BETRIEB: tuple[Statuszeile, ...] = (
    Statuszeile(
        r"betriebsphase",
        "Betriebszustand",
        "mdi:state-machine",
        ("operating_phase",),
        panel=True,
        karte=True,
        kopf=True,
    ),
    Statuszeile(
        r"^laufzeit(?: aktuell)?$",
        "Laufzeit",
        "mdi:timer-play-outline",
        ("operating_phase_runtime",),
        panel=True,
    ),
    Statuszeile(
        r"^laufzeit heute$",
        "Laufzeit heute",
        "mdi:timer-outline",
        ("operating_phase_runtime_today",),
        panel=True,
    ),
)

# Was für die ganze Anlage gilt, nicht für einen Erzeuger.
GEMEINSAM: tuple[Statuszeile, ...] = (
    # „Meldung Klartext“ hat keine Adresse: Der Text entsteht aus `FE01msg`
    # und steht in keiner Datenpunkttabelle. Dort bleibt es beim Namen.
    Statuszeile(r"meldung klartext", "Meldung", "mdi:message-alert-outline", karte=True),
    Statuszeile(
        r"au(ß|ss)entemperatur",
        "Außentemperatur",
        "mdi:thermometer",
        ("outdoor_temperature",),
        panel=True,
        karte=True,
    ),
    # Ob der Netzbetreiber gerade sperrt oder zum Einschalten auffordert; nur
    # Anlagen mit SG-Ready-Eingang (Hybridmanager) melden den Zustand.
    Statuszeile(
        r"^sg ready status$", "SG Ready", "mdi:transmission-tower", panel=True, regelung=True
    ),
)

# Ein Kessel: Zustand, Leistung, Verbrennung, Brennstoff, Zähler und Wartung.
KESSEL: tuple[Statuszeile, ...] = (
    *BETRIEB,
    Statuszeile(
        r"kesselleistung",
        "Kesselleistung",
        "mdi:fire",
        ("boiler_power",),
        panel=True,
        karte=True,
        kopf=True,
    ),
    Statuszeile(
        r"brenn(er)?kammertemperatur",
        "Brennkammertemperatur",
        "mdi:fireplace",
        ("combustion_chamber_temperature",),
        panel=True,
    ),
    Statuszeile(
        r"abgastemperatur", "Abgastemperatur", "mdi:smoke", ("flue_gas_temperature",), panel=True
    ),
    Statuszeile(
        r"aktueller brennstoff",
        "Brennstoff",
        "mdi:sack",
        ("fuel_current",),
        panel=True,
        karte=True,
    ),
    Statuszeile(
        r"vorratsbeh",
        "Vorratsbehälter",
        "mdi:battery-70",
        ("fuel_storage_status",),
        panel=True,
        karte=True,
    ),
    # Der Lagerraum steht neben dem Vorratsbehälter; das Schaubild zeigt nur den Behälter am Kessel.
    # Am Anfang verankert: „Schwelle Befüllgrad Lagerraum für Error“ ist eine Einstellung.
    Statuszeile(
        r"^(bef(ü|ue)llgrad lagerraum|vulniveau bunker)",
        "Lagerraum",
        "mdi:warehouse",
        panel=True,
        karte=True,
    ),
    Statuszeile(
        r"^(anzahl der )?brennerstarts$",
        "Brennerstarts",
        "mdi:restart",
        ("burner_starts",),
        panel=True,
    ),
    Statuszeile(
        r"^brennerstarts heute$",
        "Brennerstarts heute",
        "mdi:restart",
        ("burner_starts_today",),
        panel=True,
    ),
    Statuszeile(
        r"^betriebsstunden$",
        "Betriebsstunden",
        "mdi:clock-outline",
        ("operating_hours",),
        panel=True,
    ),
    Statuszeile(
        r"^betriebsstunden heute$",
        "Betriebsstunden heute",
        "mdi:clock-outline",
        ("operating_hours_today",),
        panel=True,
    ),
    Statuszeile(
        r"laufzeit bis ascheentleerung",
        "Bis Ascheentleerung",
        "mdi:delete-clock-outline",
        ("maintenance_ash_hours",),
        panel=True,
    ),
    # Der BioWIN kennt keine Aschetonne, aber eine Reinigung. Die Zeile
    # erscheint nur, wo es den Datenpunkt gibt – am PuroWIN bleibt sie weg.
    Statuszeile(
        r"laufzeit bis reinigung",
        "Bis Reinigung",
        "mdi:broom",
        ("maintenance_cleaning_hours",),
        panel=True,
    ),
)


# Eine Wärmepumpe: Zustand, Leistung und COP, dazu Vorlauf, Starts und Zähler
# für das Heizen. Die Namen sind die der AeroWIN an einer BioWIN Hybrid.
WAERMEPUMPE: tuple[Statuszeile, ...] = (
    *BETRIEB,
    Statuszeile(r"^aktuelle leistung$", "Leistung", "mdi:gauge", panel=True, karte=True, kopf=True),
    Statuszeile(
        r"^cop aktuell$",
        "COP aktuell",
        "mdi:speedometer",
        panel=True,
        karte=True,
        kopf=True,
        vorsatz="COP",
    ),
    Statuszeile(r"cop heizen heute$", "COP heute Heizen", "mdi:speedometer", panel=True),
    Statuszeile(r"cop warmwasser heute$", "COP heute Warmwasser", "mdi:speedometer", panel=True),
    Statuszeile(r"^vorlauftemperatur$", "Vorlauf", "mdi:thermometer", panel=True),
    Statuszeile(r"^anzahl starts$", "Starts", "mdi:restart", panel=True),
    Statuszeile(
        r"^betriebsstunden heizen$", "Betriebsstunden Heizen", "mdi:clock-outline", panel=True
    ),
    Statuszeile(r"^w(ä|ae)rmemenge heizen$", "Wärmemenge Heizen", "mdi:fire", panel=True),
)


# Mit höchstens einem Erzeuger: die Zeilen eines Kessels über die ganze Anlage.
# Erst wie er läuft, dann was für die Anlage gilt, dann seine Werte.
EINZELN: tuple[Statuszeile, ...] = (
    *BETRIEB,
    *GEMEINSAM,
    *(z for z in KESSEL if z not in BETRIEB),
)
