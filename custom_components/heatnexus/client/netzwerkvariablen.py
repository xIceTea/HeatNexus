"""Netzwerkvariablen des LON-Adressraums als Datenpunkte.

Ein Knoten führt neben seinen Menüs Netzwerkvariablen. Sie werden zu
Deskriptoren, soweit ein Fühler angeschlossen ist und derselbe Begriff nicht
schon als Datenpunkt vorliegt.
"""

from __future__ import annotations

import asyncio
import logging

from ..const import FCT_NV
from ..kanonisch import schluessel as kanonischer_schluessel
from ..lon import im_grundumfang as lon_im_grundumfang
from ..lon import ist_eingang as lon_ist_eingang
from ..lon import kennungsteil as lon_kennungsteil
from ..lon import snvt as lon_snvt
from ..lon import ungueltig as lon_ungueltig
from ..lon import zuordnen as lon_zuordnen

_LOGGER = logging.getLogger(__name__)


class NetzwerkvariablenMixin:
    """Netzwerkvariablen eines Knotens als Deskriptoren."""

    async def _lese_nv(
        self,
        prefix: str,
        ziel_prefix: str | None = None,
        ziel_name: str | None = None,
        ziel_typ: int | None = None,
    ) -> None:
        """Die Netzwerkvariablen eines Knotens als Deskriptoren anlegen.

        Was die Anlage hier führt, hängt nicht an ihrer Baureihe: Die Namen
        kommen aus den Funktionsblöcken des Bus und bedeuten überall dasselbe.
        Für eine Steuerung, für die es keine gepflegte Adresstabelle gibt, ist
        das die einzige Quelle benannter Werte.

        Ab Werk aktiv ist nur, was `lon.py` kennt; alles andere wird angelegt
        und bleibt deaktiviert. Geschrieben wird nichts – die `nvi`-Variablen
        sind Eingänge der Regelung zwischen den Knoten, keine Bedienung.
        """
        ebenen = await self._menue_ebenen(prefix)
        if not ebenen:
            return

        gelesen = await asyncio.gather(
            *(
                self._read_menu(prefix, menu_id, anzahl, None, schluessel="nvIndex")
                for menu_id, anzahl in ebenen.items()
            ),
            return_exceptions=True,
        )
        for menu_id, items in zip(ebenen, gelesen, strict=True):
            if isinstance(items, BaseException):
                self._ebene_ohne_antwort(prefix, menu_id, items)
                continue
            for item in items:
                self._nv_deskriptor(prefix, menu_id, item, ziel_prefix, ziel_name, ziel_typ)

    def _nv_deskriptor(
        self,
        prefix: str,
        menu_id: str,
        item: dict,
        ziel_prefix: str | None = None,
        ziel_name: str | None = None,
        ziel_typ: int | None = None,
    ) -> None:
        """Einen Deskriptor aus einem Eintrag des LON-Adressraums bauen."""
        index = item.get("nvIndex")
        oid = f"{prefix}/{menu_id}/{index}/0"
        if oid in self.oids:
            return
        nv_name = item.get("nvName") or ""
        eintrag = lon_zuordnen(nv_name)
        knoten = prefix.strip("/").split("/")[1]

        # Was der LonMark-Typ über den Wert sagt. Er steht an jedem Eintrag und
        # gilt über Baureihen hinweg – die Namenstabelle entscheidet nur noch
        # über den Begriff, die Größe kommt von hier.
        typ = lon_snvt(item.get("snvtName"))
        # Ohne den Schalter kommt nur, was den Aufbau der Anlage betrifft.
        if not self.lon and not lon_im_grundumfang((eintrag or {}).get("kanonisch")):
            return
        if typ.get("verwaltung"):
            # Dateiverzeichnis und Anforderungs-Eingang sind Innenleben des
            # Bus. Als Entität wären sie eine Zeile, die niemand deuten kann.
            return

        # Die Metadaten stehen schon im Eintrag; ein Einzelabruf entfällt
        # damit. `writeProt` setzt der Client selbst – die Anlage meldet für
        # Netzwerkvariablen keinen Schreibschutz, geschrieben wird trotzdem
        # nicht. Die Einheit aus dem Typ springt nur ein, wo die Anlage keine
        # nennt.
        meta = {**item, "writeProt": True}
        if not meta.get("unit") and typ.get("unit"):
            meta["unit"] = typ["unit"]
        self.menu_meta[oid] = meta

        self.devices.append(
            self._deskriptor(
                id=f"{self._neuron(knoten)}-{lon_kennungsteil(nv_name, menu_id, index)}",
                alt_id=self._alte_kennung(oid),
                oid=oid,
                # Das Kürzel bleibt am Namen, auch beim kuratierten Wert: Wer
                # den Bus einschaltet und danach aufräumen will, filtert in der
                # Entitätsliste nach „LON" und sieht auf einen Blick, was von
                # dort kommt. Es steht auch in der Entitäts-ID.
                name=f"{eintrag['name'] if eintrag else nv_name or f'Netzwerkvariable {index}'} (LON)",
                # Netzwerkvariablen stehen in keiner Bedienebene der Anlage –
                # weder Info noch Service. Sie eine zu nennen, um durch den
                # Umfangsfilter zu kommen, wäre eine falsche Auskunft an alles,
                # was später nach Ebenen unterscheidet; den Filter durchlaufen
                # sie ohnehin nicht. Über ihre Sichtbarkeit entscheidet
                # `enabled_default`. Eine eigene Herkunft statt gar keiner:
                # `None` zählte die Diagnose unter dem Schlüssel `null`.
                level="lon",
                # Ab Werk aktiv ist nur ein benannter **Ausgang**. Der Eingang
                # daneben führt dieselbe Zahl, und Unbenanntes taugt ohne
                # Nachsehen zu nichts.
                enabled_default=bool(eintrag) and not lon_ist_eingang(nv_name),
                state_class=(eintrag or {}).get("state_class") or typ.get("state_class"),
                kanonisch=eintrag.get("kanonisch") if eintrag else None,
                category=None if eintrag and not typ.get("diagnose") else "diagnostic",
                write_prot=True,
                nv_name=nv_name,
                device_id=self._geraetekennung(ziel_prefix or prefix),
                alt_device_id=self._alte_kennung(ziel_prefix or prefix),
                # Ein Knoten ohne brauchbare Funktion trägt keinen Namen, den
                # man anzeigen möchte („NV's"). Dann nennt ihn die Anlage
                # selbst: die Werksbezeichnung des Bausteins, beim Bedienteil
                # „MB6611 LOP". Fehlt auch die, bleibt die Knotennummer – sie
                # ist wenigstens wahr, während „Bedienteil" bei jedem zweiten
                # Busgerät danebenläge.
                device_name=ziel_name or self.werksbezeichnung.get(knoten) or f"Knoten {knoten}",
                fct_type=ziel_typ if ziel_prefix else FCT_NV,
            )
        )
        self.oids.add(oid)

    async def _nv_ohne_fuehler_verwerfen(self) -> None:
        """Netzwerkvariablen ohne angeschlossenen Fühler gar nicht erst anlegen.

        Die Menü-Ebene liefert für sie keinen Wert (`"value": "-"`); erst ein
        Einzelabruf zeigt, ob etwas daranhängt. An der eigenen Anlage standen
        vier von siebzehn dauerhaft auf der Ungültig-Marke – in der Geräteliste
        Zeilen, die für immer „nicht verfügbar" sagen.

        Kostet einmalig eine Anfrage je Netzwerkvariable und läuft im
        Hintergrundabzug, nie in der Einrichtung.
        """
        nv = [d for d in self.devices if d.get("nv_name") and d.get("oid")]
        if not nv:
            return
        werte = await self.fetch_oids([d["oid"] for d in nv])
        ohne_fuehler = {d["oid"] for d in nv if lon_ungueltig(werte.get(d["oid"]))}
        if not ohne_fuehler:
            return
        _LOGGER.debug("%d Netzwerkvariablen ohne Fühler verworfen", len(ohne_fuehler))
        self.devices = [d for d in self.devices if d.get("oid") not in ohne_fuehler]
        self.oids -= ohne_fuehler

    def _nv_doppelte_stilllegen(self) -> None:
        """Netzwerkvariablen abschalten, deren Begriff schon einen Datenpunkt hat.

        Von 95 brauchbaren Werten einer fremden BioWIN hatten 46 eine
        Entsprechung im OID-Raum. Beide anzuzeigen hieße, dieselbe Größe
        zweimal zu führen – und niemand könnte sagen, welche der beiden gilt.

        Entschieden wird über den kanonischen Schlüssel, nicht über einen
        Wertevergleich: Zwei Zahlen sind auch dann gleich, wenn die Anlage
        gerade steht.

        Läuft **nach** den Metadaten, nicht am Ende der Erkennung: Bis dahin
        stehen auch die kuratierten Datenpunkte in der Liste, die diese Anlage
        gar nicht führt. Ein Kessel ohne den Zähler `2/81` verlöre sonst die
        Betriebsstunden aus dem LON-Raum an einen Datenpunkt, den es hier
        nicht gibt.
        """
        belegt = {
            kanonischer_schluessel(d.get("id"))
            for d in self.devices
            if not d.get("nv_name") and d.get("oid")
        }
        belegt.discard(None)
        doppelt = [d for d in self.devices if d.get("nv_name") and d.get("kanonisch") in belegt]
        if self.lon:
            for d in doppelt:
                d["enabled_default"] = False
            return
        # Ohne den Schalter stünde eine abgeschaltete Zeile ohne Zweck da: Der
        # Grundumfang springt nur ein, wo der Datenpunkt fehlt.
        weg = {d["oid"] for d in doppelt if d.get("oid")}
        if weg:
            self.devices = [d for d in self.devices if d.get("oid") not in weg]
            self.oids -= weg
