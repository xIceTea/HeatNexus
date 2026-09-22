"""Dauerhafte Kennungen aus `neuronId` und Adresse – das Schema ist eingefroren.

Die `neuronId` ist die Seriennummer des Bausteins und übersteht einen
Adresswechsel der Anlage; meldet ein Knoten keine, bleibt die Adresse als
Notnagel. Eine Schemaänderung verwaiste die Entitäten jeder Installation.
"""

from __future__ import annotations

from .gemeinsam import gnmn_aus_oid


class KennungenMixin:
    """Dauerhafte Kennungen aus `neuronId` und Adresse."""

    @staticmethod
    def slugify(identifier_str):
        return identifier_str.replace(".", "-").replace("/", "-")

    def _neuron(self, node_id: str) -> str:
        return self.neuron_by_node.get(str(node_id)) or self.slugify(self.host)

    def _kennung(self, oid: str) -> str:
        """Dauerhafte Kennung eines Datenpunkts aus seiner OID.

        `/1/60/0/0/7/0` wird zu `<neuronId>-0-0-7-0`: Knoten- und
        Anlagenadresse fallen weg, der Rest bleibt wie er ist.
        """
        teile = oid.strip("/").split("/")
        if len(teile) < 3:
            return self.slugify(f"{self.host}{oid}")
        return "-".join([self._neuron(teile[1]), *teile[2:]])

    def _geraetekennung(self, prefix: str) -> str:
        """Dauerhafte Kennung einer Funktion (`/1/<node>/<fct>`)."""
        return self._kennung(prefix)

    def _alte_kennung(self, teil: str) -> str:
        """Die frühere, adressgebundene Kennung – nur noch für die Umstellung."""
        return self.slugify(f"{self.host}{teil}")

    def steuerung_kennung(self) -> str | None:
        """Dauerhafte Kennung der Steuerung (eine Adresse, mehrere Knoten).

        Die Steuerung selbst meldet keine eigene Seriennummer; genommen wird
        deshalb die kleinste ihrer Knoten-Seriennummern. Sie ändert sich nur,
        wenn genau dieser Baustein getauscht wird.
        """
        if not self.neuron_by_node:
            return None
        return f"steuerung-{min(self.neuron_by_node.values())}"

    @staticmethod
    def _gnmn(prefix: str, oid: str) -> str:
        """Datenpunktadresse 'gn/mn' relativ zum Funktionspräfix."""
        rest = oid[len(prefix) :].strip("/").split("/")
        return f"{rest[0]}/{rest[1]}" if len(rest) >= 2 else oid

    @staticmethod
    def _kennung_aus_oid(oid: str | None) -> str:
        """`gn/mn` aus einer vollständigen Adresse, ohne Präfix."""
        return gnmn_aus_oid(oid) or ""

    @staticmethod
    def _praefix_aus_oid(oid: str | None) -> str:
        """Knoten und Funktion aus einer Adresse, also `/1/16/1`.

        Der Deskriptor selbst führt kein Präfix — nur der Heizkreis-Thermostat
        hat eines.
        """
        teile = str(oid or "").strip("/").split("/")
        return "/" + "/".join(teile[:3]) if len(teile) >= 6 else ""
