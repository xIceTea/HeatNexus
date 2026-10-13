/**
 * Uhrzeiten und Tage, wie Home Assistant sie dem Nutzer zeigt.
 *
 * Maßgeblich sind die Zeitzone des Servers (oder die lokale, wenn das Profil
 * sie wählt) und das Zeitformat aus dem Profil. Die Zone und Sprache des
 * Browsers gelten nur als Rückfall, wenn `hass` nichts dazu sagt.
 */

/** Die Zone des Servers; in ihr rechnet die Anlage ihre Stunden und Tage. */
export function serverzone(hass) {
  return (hass && hass.config && hass.config.time_zone) || undefined;
}

/** Die Zone für Anzeigen: die des Servers, außer das Profil wählt die lokale. */
export function zeitzone(hass) {
  const locale = (hass && hass.locale) || {};
  return locale.time_zone === "local" ? undefined : serverzone(hass);
}

/** Ein Formatierer; eine unbekannte Zone oder Sprache fällt auf den Browser zurück. */
function formatierer(sprache, optionen, zone) {
  const versuche = [
    [sprache, { ...optionen, timeZone: zone }],
    [sprache, optionen],
    [undefined, optionen],
  ];
  for (const [mitSprache, mitOptionen] of versuche) {
    try {
      return new Intl.DateTimeFormat(mitSprache, mitOptionen);
    } catch {
      /* Nächster Versuch mit weniger Vorgaben. */
    }
  }
  return new Intl.DateTimeFormat();
}

/** Kalendertag, Stunde und Minute eines Zeitpunkts in einer Zone. */
export function zeitTeile(datum, zone) {
  const teile = formatierer(
    "en-GB",
    { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" },
    zone
  ).formatToParts(new Date(datum));
  const wert = (art) => Number((teile.find((eintrag) => eintrag.type === art) || {}).value);
  const jahr = wert("year");
  const monat = wert("month");
  const tag = wert("day");
  return { jahr, monat, tag, stunde: wert("hour") % 24, minute: wert("minute"), kalendertag: `${jahr}-${monat}-${tag}` };
}

/** Ein Schlüssel für den Kalendertag in einer Zone, zum Vergleichen. */
export function kalendertagIn(datum, zone) {
  return zeitTeile(datum, zone).kalendertag;
}

/** „HH:MM" im 24-Stunden-Takt; so stehen Uhrzeiten im Stundenraster der Automatik. */
export function uhr24(datum, zone) {
  const { stunde, minute } = zeitTeile(datum, zone);
  return `${String(stunde).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/** Datum „T.M." in einer Zone. */
export function tagMonatIn(datum, zone) {
  const { tag, monat } = zeitTeile(datum, zone);
  return `${tag}.${monat}.`;
}

/** Eine Uhrzeit in Sprache, Zeitformat (12/24 h) und Zeitzone aus dem Profil von Home Assistant. */
export function uhrzeitText(datum, hass) {
  const locale = (hass && hass.locale) || {};
  const sprache = locale.time_format === "system" ? undefined : locale.language || (hass && hass.language) || "de";
  const optionen = { hour: "2-digit", minute: "2-digit" };
  if (locale.time_format === "12") optionen.hourCycle = "h12";
  else if (locale.time_format === "24") optionen.hourCycle = "h23";
  return formatierer(sprache, optionen, zeitzone(hass)).format(new Date(datum));
}
