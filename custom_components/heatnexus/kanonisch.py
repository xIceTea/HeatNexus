"""Kanonische Datenpunktschlüssel – sprachunabhängig statt am Namen erkannt.

**Warum es das gibt.** Schaubild, Dashboard und Oberfläche erkennen einen
Datenpunkt bisher an seinem *deutschen Namen*: rund fünfzig Suchmuster in
`panel/muster.py`, `dashboard.py` und `schema.py`. Solange nur Deutsch
ausgeliefert wird, geht das gut. Es ist aber genau der Grund, warum die drei
anderen Sprachen des Herstellers – sie liegen fertig auf der Anlage – nicht
eingeschaltet werden können: Mit englischen Namen liefe kein einziges Muster
mehr an, und Schaubild, Kennwerte und Dashboard stünden still leer da. Keine
Fehlermeldung, nur leere Karten.

Sprachunabhängig ist dagegen die **Adresse** des Datenpunkts. `0/7` ist die
Kesseltemperatur, in jeder Sprache und über die Baureihen hinweg. Sie steckt
in jeder `unique_id` (`<neuronId>-<fctId>-<gn>-<mn>-<idx>`) und lässt sich
dort ohne Umweg über die Anlage wieder herausholen.

**Was hier steht und was nicht.** Die Tabelle ist bewusst flach nach `gn/mn`
geschlüsselt, nicht nach Funktionstyp. Dieselbe Adresse bedeutet an
verschiedenen Anlagenteilen Verschiedenes – `0/7` ist am Kessel die
Kesseltemperatur, am Pumpen-/Relaismodul der Fühler auf der anderen Seite
einer Fernwärmeübergabe. Diese Unterscheidung gehört dorthin, wo der
Funktionstyp bekannt ist (`KENNWERT_JE_FCT`), nicht hierher: Sonst stünde
dieselbe Entscheidung an zwei Stellen und liefe auseinander.

Die Adressen sind gegen `device_db.json` geprüft, nicht abgeschrieben.
"""

from __future__ import annotations

# gn/mn -> kanonischer Schlüssel. Herkunft: `_intern/NAMING-MODEL.md`, Abschnitt 4.
#
# **Was hier bewusst fehlt.** Zu allgemein benannte Adressen bleiben draußen,
# auch wenn ein Muster sie gebrauchen könnte: `2/16` heißt in der
# Geräte-Datenbank „Freigabe starten" und `5/51` schlicht „Temperatur" – beide
# bedeuten an einer anderen Funktion etwas anderes. Ein falsch geratener
# Schlüssel wäre schlimmer als keiner; dort bleibt es beim Namen.
KANONISCH: dict[str, str] = {
    # Kessel
    "0/7": "boiler_temperature",
    "1/7": "boiler_temperature_target",
    "0/8": "return_temperature",
    "0/9": "boiler_power",
    "0/11": "flue_gas_temperature",
    "0/42": "oxygen_level",
    "0/45": "combustion_chamber_temperature",
    "2/1": "operating_phase",
    "2/9": "operating_mode",
    "2/80": "burner_starts",
    "2/81": "operating_hours",
    "38/126": "fuel_selected",
    "38/127": "fuel_current",
    "39/76": "fuel_storage_status",
    # Wartungszähler: Restlaufzeiten bis zur nächsten fälligen Arbeit. Die
    # Baureihen führen sie an verschiedenen Adressen – der PuroWIN unter
    # `39/9x`, der BioWIN unter `20/6x`. Hauptreinigung und Wartung sind
    # dieselbe Arbeit und bekommen denselben Schlüssel; „Asche entleeren"
    # (PuroWIN) und „Reinigung" (BioWIN) sind zwei verschiedene.
    "39/91": "maintenance_ash_hours",
    "39/92": "maintenance_main_cleaning_hours",
    "39/93": "maintenance_service_hours",
    "20/61": "maintenance_cleaning_hours",
    "20/62": "maintenance_main_cleaning_hours",
    "20/63": "maintenance_service_hours",
    "39/94": "cleaning_confirm",
    # Heizkreis
    "0/0": "outdoor_temperature",
    "0/1": "room_temperature",
    "1/1": "room_temperature_target",
    "0/2": "flow_temperature",
    "1/2": "flow_temperature_target",
    "1/20": "circuit_pump",
    "1/21": "mixer_position",
    "3/50": "mode_selection",
    "3/58": "comfort_offset",
    # Warmwasser (hängt am Heizkreis, nicht an einer eigenen Funktion)
    "0/4": "dhw_temperature",
    "1/4": "dhw_temperature_target",
    "1/66": "dhw_charge_pump",
    # Zirkulation: `1/65` meldet, ob die Pumpe läuft, `5/6` wonach sie sich
    # richtet (Aus, Zeit-, Temperatur-, Impulssteuerung, EIN). Zwei Begriffe,
    # zwei Schlüssel – bis 1.5.0-beta.4 trug der Modus den Namen der Pumpe.
    "1/65": "dhw_circulation_pump",
    "5/6": "dhw_circulation_mode",
    # Zwei Zirkulationsprogramme, in der Herstellerdatei **wortgleich**
    # benannt: beide heißen „WW-Zirkulationsprogramm". Auseinanderhalten lassen
    # sie sich nur an der Adresse – `5/65` gilt bei Zeitsteuerung, `5/64` bei
    # Temperatursteuerung (`5/6`). Ohne diese Zuordnung stünden im Reiter
    # Zeitprogramme zwei gleichnamige Karten, und keine sagt, welche wirkt.
    "5/65": "dhw_circulation_program_time",
    "5/64": "dhw_circulation_program_temperature",
    "0/118": "dhw_circulation_temperature",
    # `5/76` „WW-Kreis" – daran hängt, ob eine Anlage überhaupt Warmwasser
    # bereitet. Die übrigen WW-Parameter beweisen das nicht: Sie stehen auch
    # an einem Heizkreis ohne Speicher in der Liste.
    "5/76": "dhw_circuit",
    # Puffer. Zwei Adresspaare für denselben Messwert: Die Baureihen mit
    # eigenem Puffermodul melden ihn unter `21/65`/`21/66` (TPE/TPA), die mit
    # angebautem Fühler unter `0/15`/`0/16`. Es ist derselbe Begriff.
    "21/65": "buffer_top",
    "21/66": "buffer_bottom",
    "0/15": "buffer_top",
    "0/16": "buffer_bottom",
    # Solar
    "0/14": "collector_temperature",
    "0/61": "solar_storage_temperature",
    # Pumpen-/Relaismodul (ZSP). Der Analog-Sollwert ist die Temperatur, mit
    # der gerade Wärme angefordert wird; über null heißt: Es liegt etwas an.
    "0/95": "analog_setpoint",
    "0/22": "pump_speed",
}


def gnmn(unique_id: str | None) -> str | None:
    """Die Datenpunktadresse `gn/mn` aus einer Kennung zurückgewinnen.

    Die Kennung lautet `<neuronId>-<fctId>-<gn>-<mn>-<idx>`; manche tragen
    dahinter noch einen Zusatz (`-text`), weil zwei Entitäten auf derselben
    Adresse sitzen. Gesucht werden deshalb die **letzten vier Zahlen**, nicht
    feste Stellen von vorn: Die Seriennummer davor ist nicht durchgehend
    zahlenfrei, und ein fester Abstand von hinten bräche am Zusatz.

    Gibt ``None`` zurück, wenn die Kennung nicht so aufgebaut ist – dann bleibt
    es beim Namen. Ein falsch geratener Schlüssel wäre schlimmer als keiner.
    """
    if not unique_id:
        return None
    teile = str(unique_id).split("-")
    # Von hinten den letzten Block aus mindestens vier Zahlen suchen.
    ende = len(teile)
    while ende > 0 and not teile[ende - 1].isdigit():
        ende -= 1
    zahlen = []
    stelle = ende
    while stelle > 0 and teile[stelle - 1].isdigit():
        stelle -= 1
        zahlen.insert(0, teile[stelle])
    if len(zahlen) < 4:
        return None
    # **Vorn muss etwas stehen, das keine Zahl ist.** Meldet ein Knoten keine
    # `neuronId`, fällt `client._neuron` auf die Adresse zurück; die Kennung
    # beginnt dann selbst mit Zahlen. Zusammen mit einem Wortzusatz hinten
    # (`…-thermostat`, `…-fe01`) verschiebt sich der Zahlenlauf, und aus
    # `10-0-1-20-0-thermostat` würde `1/20` – die Heizkreispumpe, die dort gar
    # nicht gemeint ist. Reicht der Lauf bis an den Anfang **und** wurde hinten
    # etwas abgeschnitten, ist die Zerlegung nicht vertrauenswürdig.
    if stelle == 0 and ende < len(teile):
        return None
    # Die letzten vier sind fctId, gn, mn, idx.
    _fct, gn, mn, _idx = zahlen[-4:]
    return f"{gn}/{mn}"


def schluessel(unique_id: str | None) -> str | None:
    """Kanonischer Schlüssel eines Datenpunkts – oder nichts.

    Datenpunkte ohne kanonische Entsprechung behalten den Herstellernamen; sie
    sind der Grund, warum die Muster nicht ersatzlos verschwinden können.
    """
    adresse = gnmn(unique_id)
    return KANONISCH.get(adresse) if adresse else None
