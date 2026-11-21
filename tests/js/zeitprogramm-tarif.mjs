/**
 * Das Stromtarifprogramm im Reiter „Zeitprogramme“: Tageszeilen ohne Editor.
 *
 * Aufruf: `node zeitprogramm-tarif.mjs <panel.js>`
 *
 * Ausgegeben wird je Programmart: Rolle der Zeilen, ob ein Tipp oder die
 * Eingabetaste den Editor öffnet, und der Klartext der Zeile.
 */

import { pathToFileURL } from "node:url";

import { browserAttrappe } from "./dom-attrappe.mjs";

const [pfadPanel] = process.argv.slice(2);
browserAttrappe();

await import(pathToFileURL(pfadPanel).href);
const [klasse] = [...globalThis.customElements._klassen.values()];
if (!klasse) throw new Error("Die Oberfläche hat kein Element angemeldet");

const WOCHE = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

function durchlauf(art, werte) {
  const element = new klasse();
  const entity = `sensor.programm_${art}`;
  element._hass = {
    states: {
      [entity]: {
        entity_id: entity,
        state: "",
        attributes: {
          blocks: [
            {
              weekdays: WOCHE,
              switchPoints: [
                { time: "06:00", value: werte[0] },
                { time: "22:00", value: werte[1] },
              ],
            },
          ],
        },
      },
    },
    callService: async () => {
      throw new Error("Kein Dienst erwartet");
    },
  };
  element._aktualisieren = () => {};
  const programm = { entity, titel: art, art };
  const rueckmeldung = document.createElement("div");
  const liste = element._tageszeilen(programm, { tag: "Mo", minute: 600 }, rueckmeldung, "de");
  const zeilen = liste.querySelectorAll(".zp-zeile");
  zeilen[0].ausloesen("click");
  const getippt = !!element._zpOffen;
  element._zpOffen = null;
  zeilen[0].ausloesen("keydown", { key: "Enter", preventDefault() {} });
  return {
    zeilen: zeilen.length,
    rollen: zeilen.map((zeile) => zeile.getAttribute("role")),
    getippt,
    taste: !!element._zpOffen,
    text: zeilen.map((zeile) => String(zeile.textContent || "")),
  };
}

console.log(JSON.stringify({ tarif: durchlauf("tarif", [0, 4]), raum: durchlauf("raum", [21, 17]) }));
