/**
 * HeatNexus – Dashboard-Strategie.
 *
 * Baut die Ansichten zur Laufzeit aus den Geräten und Entitäten der
 * Integration. Es gibt keine festen Entitäts-IDs: Was die Anlage liefert,
 * erscheint; was fehlt, entfällt.
 */

const DOMAIN = "heatnexus";

/** Reihenfolge und Zuordnung der Übersichtswerte. */
const WICHTIG = [
  { titel: "Kessel", muster: [
    /betriebsphase/i, /betriebsart/i, /kesseltemperatur ist/i, /kesseltemperatur soll/i,
    /kesselleistung/i, /abgastemperatur/i, /o2/i, /brennerkammer/i,
    /aktueller brennstoff/i, /vorratsbeh/i,
  ]},
  { titel: "Wartung", muster: [
    /laufzeit bis ascheentleerung/i, /laufzeit bis hauptreinigung/i, /laufzeit bis wartung/i,
    /betriebsstunden/i, /brennerstarts/i,
  ]},
  { titel: "Puffer", muster: [
    /puffer oben/i, /puffer unten/i, /puffertemperatur/i,
    /pufferladepumpe drehzahl/i, /r(ü|ue)cklauf temperatur/i,
  ]},
  { titel: "Warmwasser", muster: [
    /warmwasser ist/i, /warmwasser soll/i, /ww-ladepumpe/i,
    /ww einmalladung/i, /ww-zirkulation/i,
  ]},
  { titel: "Heizkreis", muster: [
    /au(ß|ss)entemperatur/i, /vorlauftemperatur ist/i, /vorlauftemperatur soll/i,
    /raumtemperatur ist/i, /raumtemperatur soll/i, /heizkreispumpe/i,
    /mischer stellwert/i, /behaglichkeitskorrektur/i,
  ]},
  { titel: "Meldungen", muster: [/meldung klartext/i, /^meldung$/i, /st(ö|oe)rung/i]},
];

/** Werte, die in der Übersicht als Rundinstrument gut aussehen. */
const RUNDINSTRUMENT = [
  { muster: /kesseltemperatur ist/i, min: 0, max: 95, gruen: 55, gelb: 80, rot: 88 },
  { muster: /kesselleistung/i, min: 0, max: 100 },
  { muster: /puffer oben/i, min: 0, max: 95, gruen: 60, gelb: 80, rot: 90 },
  { muster: /puffer unten/i, min: 0, max: 95, gruen: 40, gelb: 70, rot: 85 },
];

const passt = (name, muster) => muster.some((m) => m.test(name || ""));

/** Entitäten der Integration nach Gerät und Anlage ordnen. */
function sammle(hass) {
  const geraete = new Map();
  const anlagen = new Map();

  for (const geraet of Object.values(hass.devices || {})) {
    if (!(geraet.identifiers || []).some(([bereich]) => bereich === DOMAIN)) continue;
    geraete.set(geraet.id, { geraet, entitaeten: [] });
  }

  for (const eintrag of Object.values(hass.entities || {})) {
    if (eintrag.platform !== DOMAIN) continue;
    if (eintrag.disabled_by || eintrag.hidden_by) continue;
    const ziel = geraete.get(eintrag.device_id);
    if (!ziel) continue;
    const zustand = hass.states[eintrag.entity_id];
    ziel.entitaeten.push({
      entity_id: eintrag.entity_id,
      name: (zustand && zustand.attributes.friendly_name) || eintrag.original_name || eintrag.entity_id,
      kategorie: eintrag.entity_category,
      bereich: (eintrag.entity_id.split(".")[0]),
    });
  }

  // Untergeräte ihren Steuerungen zuordnen (Anlage → Steuerung → Funktion)
  for (const eintrag of geraete.values()) {
    const oben = eintrag.geraet.via_device_id;
    const schluessel = oben || eintrag.geraet.id;
    if (!anlagen.has(schluessel)) anlagen.set(schluessel, []);
    if (oben) anlagen.get(schluessel).push(eintrag);
  }

  return { geraete, anlagen };
}

/** Kurzname ohne Steuerungspräfix. */
const kurz = (name) => (name || "").split(" · ").slice(-1)[0];

function uebersichtsAbschnitte(geraete) {
  const abschnitte = [];

  for (const { titel, muster } of WICHTIG) {
    const karten = [];
    for (const { geraet, entitaeten } of geraete.values()) {
      const treffer = entitaeten.filter((e) => passt(e.name, muster) && !e.kategorie);
      if (!treffer.length) continue;

      for (const e of treffer) {
        const rund = RUNDINSTRUMENT.find((r) => r.muster.test(e.name));
        if (rund && titel !== "Meldungen") {
          karten.push({
            type: "gauge",
            entity: e.entity_id,
            name: kurz(e.name),
            min: rund.min,
            max: rund.max,
            needle: true,
            ...(rund.gruen !== undefined
              ? { severity: { green: rund.gruen, yellow: rund.gelb, red: rund.rot } }
              : {}),
          });
        } else if (e.bereich === "climate") {
          karten.push({ type: "thermostat", entity: e.entity_id });
        } else {
          karten.push({
            type: "tile",
            entity: e.entity_id,
            name: kurz(e.name),
            ...(geraete.size > 1 ? { hide_state: false } : {}),
          });
        }
      }
    }
    if (karten.length) {
      abschnitte.push({
        type: "grid",
        cards: [{ type: "heading", heading: titel, heading_style: "title" }, ...karten],
      });
    }
  }
  return abschnitte;
}

function geraeteAnsicht(eintrag) {
  const { geraet, entitaeten } = eintrag;
  const bedienbar = entitaeten.filter(
    (e) => ["climate", "select", "number", "switch", "button", "time", "date"].includes(e.bereich)
  );
  const messwerte = entitaeten.filter((e) => !bedienbar.includes(e) && !e.kategorie);
  const diagnose = entitaeten.filter((e) => e.kategorie === "diagnostic");
  const einstellungen = entitaeten.filter((e) => e.kategorie === "config" && !bedienbar.includes(e));

  const abschnitt = (titel, liste, kartentyp = "tile") =>
    liste.length
      ? [{
          type: "grid",
          cards: [
            { type: "heading", heading: titel, heading_style: "title" },
            ...liste.map((e) =>
              e.bereich === "climate"
                ? { type: "thermostat", entity: e.entity_id }
                : { type: kartentyp, entity: e.entity_id, name: kurz(e.name) }
            ),
          ],
        }]
      : [];

  return {
    title: kurz(geraet.name_by_user || geraet.name),
    path: `geraet-${geraet.id.slice(0, 8)}`,
    type: "sections",
    max_columns: 3,
    sections: [
      ...abschnitt("Bedienung", bedienbar),
      ...abschnitt("Messwerte", messwerte),
      ...abschnitt("Einstellungen", einstellungen),
      ...abschnitt("Diagnose", diagnose),
    ],
  };
}

class HeatNexusDashboardStrategy {
  static async generate(config, hass) {
    const { geraete } = sammle(hass);

    if (!geraete.size) {
      return {
        title: "HeatNexus",
        views: [{
          title: "HeatNexus",
          cards: [{
            type: "markdown",
            content:
              "### Keine Anlage gefunden\n\n" +
              "Richte die Integration **HeatNexus** unter Einstellungen → Geräte & Dienste ein.",
          }],
        }],
      };
    }

    // Steuerungen und Anlagen tragen selbst keine Werte – sie strukturieren nur.
    const mitWerten = [...geraete.values()].filter((e) => e.entitaeten.length);

    const views = [
      {
        title: "Übersicht",
        path: "uebersicht",
        icon: "mdi:fire",
        type: "sections",
        max_columns: 3,
        sections: uebersichtsAbschnitte(geraete),
      },
      ...mitWerten
        .sort((a, b) => (a.geraet.name || "").localeCompare(b.geraet.name || ""))
        .map(geraeteAnsicht),
    ];

    return { title: "Heizung", views };
  }
}

customElements.define("ll-strategy-dashboard-heatnexus", HeatNexusDashboardStrategy);
customElements.define("ll-strategy-heatnexus", HeatNexusDashboardStrategy);
