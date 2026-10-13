/**
 * Das Aussehen der Oberfläche.
 *
 * Steht als eigene Datei, weil es der größte zusammenhängende Block ist und
 * mit der Logik nichts zu tun hat. Der Stil liegt in einem Template-Literal:
 * Ein Backtick im Kommentar beendet es, und die ganze Datei ist kein gültiges
 * JavaScript mehr. In einer Datei, die nur Stil enthält, fällt das auf.
 *
 * **Keine Backticks in Kommentaren.** Der Test `test_browser_rechnet_genauso`
 * lädt die Module in Node und fängt es ab.
 */


import { GRUND } from "./stil/grund.js";
import { KOPFLEISTE } from "./stil/kopfleiste.js";
import { RASTER } from "./stil/raster.js";
import { ANORDNEN } from "./stil/anordnen.js";
import { KARTEN } from "./stil/karten.js";
import { ZEILEN } from "./stil/zeilen.js";
import { SCHAUBILD } from "./stil/schaubild.js";
import { TASTEN } from "./stil/tasten.js";
import { STEUERUNG } from "./stil/steuerung.js";
import { DIALOG } from "./stil/dialog.js";
import { ZEITPROGRAMME } from "./stil/zeitprogramme.js";
import { ALLGEMEIN } from "./stil/allgemein.js";
import { HILFE } from "./stil/hilfe.js";
import { AUTOMATIK } from "./stil/automatik.js";
import { BEFUND } from "./stil/befund.js";

// Die Reihenfolge ist die Kaskade: Ein späterer Teil schlägt einen früheren.
export const STIL = [
  GRUND,
  KOPFLEISTE,
  RASTER,
  ANORDNEN,
  KARTEN,
  ZEILEN,
  SCHAUBILD,
  TASTEN,
  STEUERUNG,
  DIALOG,
  ZEITPROGRAMME,
  ALLGEMEIN,
  HILFE,
  AUTOMATIK,
  BEFUND,
].join("");
