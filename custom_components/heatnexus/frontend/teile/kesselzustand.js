/**
 * Der Kesselzustand für den Kopf der Übersicht.
 *
 * Die Regeln baut der Server (`dashboard/kesselzustand.py`) in der Reihenfolge ihres Vorrangs;
 * hier gilt die erste, deren Zustandstexte passen.
 */
export function kesselzustand(beschreibung, zustand) {
  if (!beschreibung) return null;
  const wert = (kennung) => {
    const z = kennung ? zustand(kennung) : undefined;
    return z ? String(z.state) : null;
  };
  if (wert(beschreibung.bezug) === "unavailable") {
    return { ...beschreibung.offline, uebersetzen: true };
  }
  const art = wert(beschreibung.betriebsart);
  const service = (beschreibung.serviceausbrand || []).includes(wert(beschreibung.betriebswahl));
  for (const regel of beschreibung.regeln || []) {
    const ist = regel.quelle === "phase" ? wert(beschreibung.phase) : art;
    if (!regel.wenn.includes(ist)) continue;
    if (regel.serviceausbrand === true && !service) continue;
    if (regel.serviceausbrand === false && service) continue;
    return regel.text
      ? { text: regel.text, symbol: regel.symbol, uebersetzen: true }
      : { text: ist, symbol: regel.symbol, uebersetzen: false };
  }
  return null;
}
