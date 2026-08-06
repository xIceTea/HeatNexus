/**
 * Reihenfolge und Sichtbarkeit der Karten.
 *
 * Reine Funktionen ohne Zustand – deshalb eigene Datei und deshalb
 * prüfbar: `tests/test_anordnung.py` lädt genau dieses Modul in Node und
 * vergleicht sein Ergebnis mit der Python-Fassung in `anordnung.py`.
 * Laufen die beiden auseinander, verschiebt der Browser Karten anders als
 * der Server sie speichert.
 */

export const OHNE_WERT = ["unavailable", "unknown", "none", ""];

// Wie lange „übertragen ✓" stehen bleibt, bevor wieder der Zustand erscheint.
//
// **Muss ausgeführt werden.** Beim Schnitt in ES-Module blieben die beiden
// Zeitwerte hier ohne `export` liegen, während die Oberfläche sie weiter
// benutzte. Ergebnis: Beim ersten Aufräumen einer Rückmeldung flog ein
// `ReferenceError`, und „wird ausgeführt …" blieb für immer stehen.
export const RUECKMELDUNG_MS = 4000;

/** Wie lange ein Zahlenfeld nach der letzten Eingabe wartet, bevor es
 *  überträgt. Ohne die Pause ginge jede getippte Ziffer einzeln zur
 *  Anlage - bei "15" erst die 1, dann die 15. */
export const ZAHL_VERZOEGERUNG_MS = 2500;

// Wie lange auf die Bestätigung der Anlage gewartet wird, bevor die
// Rückmeldung aufgibt. Die Anlage wird nur alle 30 s abgefragt – drei
// Minuten reichen also für mehrere Versuche. Länger zu warten hilft nicht:
// Wird der Vorgang inzwischen an der Anlage selbst abgebrochen, bliebe
// „wird ausgeführt …" sonst minutenlang stehen, obwohl nichts mehr läuft.
export const BESTAETIGUNG_MAX_MS = 3 * 60 * 1000;

/**
 * Wie lange eine Bedienung ihrem eigenen Ergebnis glaubt, bevor wieder die
 * Anlage recht bekommt.
 *
 * Die Anlage wird alle 30 s abgefragt, und dazwischen meldet sie noch den
 * alten Stand. Ohne diese Annahme:
 *
 * * „Warmwasser laden abbrechen" liess die Taste unverändert auf „läuft"
 *   stehen – es sah aus, als sei der Druck ins Leere gegangen, also drückte
 *   man noch einmal;
 * * ein Zahlenfeld sprang nach dem Tippen auf den alten Wert zurück und zwei
 *   Sekunden später auf den neuen.
 *
 * Beides zeigt deshalb sofort, was bedient wurde, und hält daran fest, bis
 * die Anlage dasselbe meldet oder diese Zeit um ist. Etwas mehr als ein
 * Abrufabstand, damit ein knapp verpasster Durchlauf noch zählt.
 */
export const ANNAHME_MS = 45 * 1000;

export const REITER = [
  { schluessel: "uebersicht", titel: "Übersicht", symbol: "mdi:view-dashboard-outline" },
  { schluessel: "steuerung", titel: "Steuerung", symbol: "mdi:tune-vertical" },
  { schluessel: "wartung", titel: "Wartung", symbol: "mdi:wrench-outline" },
  { schluessel: "verlauf", titel: "Verlauf", symbol: "mdi:chart-line" },
  { schluessel: "zeitprogramme", titel: "Zeitprogramme", symbol: "mdi:calendar-clock" },
];

// Wochentage, wie die Anlage sie schreibt, mit deutscher Beschriftung. Die
// Reihenfolge ist die der Woche - die Anlage liefert sie unsortiert.
export const WOCHENTAGE = [
  ["Mo", "Mo"],
  ["Tu", "Di"],
  ["We", "Mi"],
  ["Th", "Do"],
  ["Fr", "Fr"],
  ["Sa", "Sa"],
  ["Su", "So"],
];

// Mehr Schaltzeiten nimmt die Anlage je Block nicht an.
export const SCHALTPUNKTE_MAX = 6;

// Wie breit eine Karte höchstens werden darf, in Spalten. Deckt sich mit
// `anordnung.BREITE_MAX` auf der Serverseite – was hier durchgeht, muss dort
// gespeichert werden können.
export const BREITE_MAX = 4;

// Wie lange nach der letzten Änderung gewartet wird, bevor die Anordnung
// gespeichert wird. Beim Ziehen fallen mehrere Änderungen kurz hintereinander
// an; jede einzeln zu schreiben hieße, dieselbe Liste mehrfach abzulegen.
export const SPEICHERN_MS = 500;

/**
 * Zwei Reihenfolgen zusammenführen: `basis` gilt, `rest` füllt auf.
 *
 * Was in `basis` steht, behält seinen Platz. Alles, was nur in `rest` steht,
 * wird dort eingefügt, wo es nach `rest` hingehört – direkt hinter dem
 * nächsten Vorgänger, der bereits einen Platz hat. Hat es keinen, kommt es
 * nach vorn.
 */
export function reihenfolgeMischen(basis, rest) {
  const ergebnis = [...basis];
  (rest || []).forEach((kennung, stelle) => {
    if (ergebnis.includes(kennung)) return;
    let ziel = 0;
    for (let vorher = stelle - 1; vorher >= 0; vorher--) {
      const platz = ergebnis.indexOf(rest[vorher]);
      if (platz >= 0) {
        ziel = platz + 1;
        break;
      }
    }
    ergebnis.splice(ziel, 0, kennung);
  });
  return ergebnis;
}

/**
 * Die gespeicherte Reihenfolge auf die tatsächlich vorhandenen Karten anwenden.
 *
 * **Neue Anlagenteile dürfen die Anordnung nicht zerreißen.** Gespeichert ist
 * nur die Reihenfolge bekannter Kennungen; was neu dazukommt, landet an der
 * Stelle, an der es von Haus aus stünde, und nicht am Ende. Kennungen, die es
 * nicht mehr gibt, fallen still weg. Dieselbe Rechnung steht in
 * `anordnung.ordnung_anwenden` auf der Serverseite.
 */
export function ordnungAnwenden(standard, gespeichert) {
  const vorhanden = new Set(standard);
  return reihenfolgeMischen(
    (gespeichert || []).filter((kennung) => vorhanden.has(kennung)),
    standard
  );
}

