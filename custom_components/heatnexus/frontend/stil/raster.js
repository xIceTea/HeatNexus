/** Stil: Das Kartenraster der Reiter. Zusammengesetzt in `stil.js`. */

export const RASTER = `
  /* --- Kartenraster ---------------------------------------------------- */
  /* Ein Raster für alle vier Reiter. Jede Karte liegt einzeln darin, nicht
     in einem Spaltenstapel: Sonst steckte die Reihenfolge im Stapel statt in
     einer Liste, und umsortieren ginge nicht.

     "align-items: stretch" ist Absicht. Vorher richtete sich jede Karte nach
     ihrem eigenen Inhalt, und in der Steuerung stand die Heizkreiskarte
     deutlich höher als Kessel und Lagerraum daneben – die Zeile sah aus, als
     fehlte etwas. Gleich hohe Karten je Zeile lesen sich ruhiger.

     Spaltenzahl und Kartenbreite kommen als Variablen von der Anordnung; sie
     stehen bewusst nicht als Inline-Stil da, sonst schlüge die eigene
     Einstellung den Umbruch auf schmalen Bildschirmen.

     "auto-fill" statt "auto-fit": Unter „Alle" bekommt jede Anlage ihr eigenes
     Raster. Mit "auto-fit" fallen leere Spalten in sich zusammen, und eine
     Anlage mit zwei Karten machte daraus zwei breite – daneben stand die
     Anlage mit drei Karten in drei schmalen. Gleiches „1×" sah dann
     verschieden groß aus. "auto-fill" lässt die leeren Spalten stehen, also
     ist eine Spalte überall gleich breit. */
  .raster {
    display: grid;
    gap: 16px;
    padding: 16px;
    grid-template-columns: var(--raster-spalten, repeat(auto-fill, minmax(320px, 1fr)));
    align-items: stretch;
  }
  .raster > * { grid-column: span var(--breite, 1); min-width: 0; }
  /* Der Inhalt bleibt oben, auch wenn die Karte für die Zeile mitwächst. */
  .karte { display: flex; flex-direction: column; }
  .raster > .karte + .karte { margin-top: 0; }
  @media (max-width: 1180px) {
    .raster { grid-template-columns: minmax(0, 1fr); }
    .raster > * { grid-column: auto; }
  }
`;
