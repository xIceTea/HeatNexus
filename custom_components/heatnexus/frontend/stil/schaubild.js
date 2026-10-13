/** Stil: Das Anlagenschaubild und seine Bewegung (teile/schaubild.js). Zusammengesetzt in `stil.js`. */

export const SCHAUBILD = `
  /* --- Schaubild ------------------------------------------------------- */
  /* Die Isolation macht die Huelle zum Stapelkontext. Ohne sie wuerde
     die Farbflaeche des Speichers mit ihrem negativen z-index nicht nur
     hinter das Bild rutschen, sondern hinter die ganze Karte - und waere
     verschwunden. */
  /* Die Hülle ist der Bezug für Behälterbreiten. Die Oberfläche setzt darauf
     eine Einheit der Zeichnung, in Kartenbreite ausgedrückt; alles Aufgesetzte
     rechnet damit und wächst mit dem Bild statt in Bildpunkten zu verharren. */
  .schaubild {
    width: 100%; position: relative; isolation: isolate;
    container-type: inline-size;
    --hn-einheit: 0.1cqw;
    /* Pumpenmarke und Leitung teilen sich eine Begrenzung, damit ihr
       Größenverhältnis in jeder Breite dasselbe bleibt. Ohne sie steht die
       Marke auf schmalen Anzeigen als Klecks auf einem Haarstrich. */
    --hn-marke: clamp(16px, calc(var(--hn-einheit) * 28), 40px);
    --hn-strang: clamp(3.43px, calc(var(--hn-einheit) * 6), 8.57px);
    /* Farbe der Wärmeübergabe. Dieselbe, in der die Vorlaufbänder strömen.
       Ein Laufrad sind drei Schaufeln um eine Nabe; in Signalgelb liest sich
       diese Form als Warnzeichen für Strahlung. */
    --hn-uebergabe: #ffd9c2;
    /* Schriftmaß der Marken. Die Karte stellt es ein; die Zeichnung selbst
       bleibt davon unberührt. */
    --hn-schrift: 1;
  }
  .schaubild img { width: 100%; display: block; border-radius: 12px; }

  /* --- Bewegung im Schaubild ------------------------------------------- */
  /* Das Bild selbst ist eine Daten-URL in einem <img> und kennt keine
     Zustände aus Home Assistant. Bewegung entsteht deshalb als eigene Ebene
     darüber, genau wie schon bei den Pumpen.

     Bewegt wird ausschließlich die Hintergrundposition – das läuft im
     Compositor und kostet kein Neuzeichnen. */
  .schaubild .fluss {
    position: absolute;
    height: var(--hn-strang);
    transform: translateY(-50%);
    border-radius: 999px; pointer-events: none;
    opacity: 0; transition: opacity 0.4s ease;
    background-repeat: repeat-x;
    background-size: calc(var(--hn-einheit) * 26) 100%;
  }
  .schaubild .fluss.laeuft { opacity: 1; animation: stroemen 1.1s linear infinite; }
  .schaubild .fluss.vorlauf {
    background-image: linear-gradient(
      90deg, rgba(255, 214, 194, 0) 0%, rgba(255, 214, 194, 0.85) 45%,
      rgba(255, 214, 194, 0) 70%);
  }
  .schaubild .fluss.ruecklauf {
    background-image: linear-gradient(
      90deg, rgba(198, 224, 255, 0) 0%, rgba(198, 224, 255, 0.85) 45%,
      rgba(198, 224, 255, 0) 70%);
  }
  /* Der Rücklauf fließt zum Kessel zurück, also andersherum. Das gilt für die
     **waagrechte** Leitung. Die senkrechte Stichleitung führt vom Anlagenteil
     hinunter *in* den Rücklauf – dort ist die Grundrichtung schon richtig, und
     ein zweites Umdrehen ließ sie in das Bauteil hineinfließen. */
  .schaubild .fluss.ruecklauf.laeuft { animation-direction: reverse; }
  .schaubild .fluss.senkrecht.ruecklauf.laeuft { animation-direction: normal; }
  /* Wird dem Speicher entnommen, dreht sich beides um: Oben verlässt die Wärme
     ihn, unten kommt sie zurück. */
  .schaubild .fluss.senkrecht.rueckwaerts.laeuft { animation-direction: reverse; }
  .schaubild .fluss.senkrecht.ruecklauf.rueckwaerts.laeuft { animation-direction: reverse; }
  @keyframes stroemen {
    from { background-position: 0 0; }
    to { background-position: calc(var(--hn-einheit) * 26) 0; }
  }

  /* Die Stichleitung hinunter zum Anlagenteil: dieselben Bänder, gekippt.
     Der Vorlauf läuft hinunter zum Verbraucher, der Rücklauf hinauf. */
  .schaubild .fluss.senkrecht {
    width: var(--hn-strang); height: auto;
    transform: translateX(-50%);
    background-repeat: repeat-y;
    background-size: 100% calc(var(--hn-einheit) * 26);
  }
  .schaubild .fluss.senkrecht.vorlauf {
    background-image: linear-gradient(
      180deg, rgba(255, 214, 194, 0) 0%, rgba(255, 214, 194, 0.85) 45%,
      rgba(255, 214, 194, 0) 70%);
  }
  .schaubild .fluss.senkrecht.ruecklauf {
    background-image: linear-gradient(
      180deg, rgba(198, 224, 255, 0) 0%, rgba(198, 224, 255, 0.85) 45%,
      rgba(198, 224, 255, 0) 70%);
  }
  .schaubild .fluss.senkrecht.laeuft { animation-name: stroemen-senkrecht; }
  @keyframes stroemen-senkrecht {
    from { background-position: 0 0; }
    to { background-position: 0 calc(var(--hn-einheit) * 26); }
  }

  .schaubild .glut {
    position: absolute;
    height: calc(var(--hn-einheit) * 26);
    transform: translate(-50%, -50%);
    border-radius: 999px; pointer-events: auto; cursor: pointer;
    opacity: 0; transition: opacity 0.6s ease;
    background: radial-gradient(
      ellipse at center, #ffb347 0%, #e2543a 45%, rgba(226, 84, 58, 0) 75%);
  }
  .schaubild .glut.brennt { animation: glimmen 2.6s ease-in-out infinite; }

  /* Mischer: Stellung, nicht Bewegung. Der Zeiger schwenkt beim Wechsel des
     Werts an seine neue Stelle und bleibt dort stehen. */
  .schaubild .mischer-stutzen {
    position: absolute;
    width: calc(var(--hn-einheit) * 4);
    transform: translateX(-50%);
    pointer-events: none; border-radius: 999px; opacity: 0.85;
    transition: background 0.8s ease;
  }
  .schaubild .mischer {
    position: absolute; transform: translate(-50%, -50%);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
  }
  .schaubild .mischer .zeiger {
    width: calc(var(--hn-einheit) * 3); height: 62%; border-radius: 999px;
    background: #f2f6fa;
    box-shadow: 0 0 4px rgba(0, 0, 0, 0.6);
    transform-origin: 50% 50%;
    transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .schaubild .mischer:hover .zeiger { background: var(--hn-akzent); }

  /* Der Heizkörper, eingefärbt nach seiner Vorlauftemperatur.

     Die Zeichnung füllt die fünf Glieder mit einem festen Verlauf – ein
     Heizkörper, der auch bei 27 Grad glüht. Darüber liegt deshalb diese Ebene
     und malt sie neu: unten die Farbe des Rücklaufs, oben die des Vorlaufs.

     Die Glieder entstehen als wiederholter Verlauf, nicht als fünf Kästen:
     "repeating-linear-gradient" trifft dieselben Abstände wie die Zeichnung
     (Glied 14 breit, Lücke 8, Raster 22), und die Ebene bleibt ein Element.
     Die weiße Kante links in jedem Glied ist der Glanz aus der Zeichnung. */
  .schaubild .heizkoerper {
    position: absolute; pointer-events: none;
    opacity: 0; transition: opacity 0.6s ease;
  }
  /* Ein Element je Glied statt einer Maske über der ganzen Fläche.
     Eine Maske aus einem Streifenverlauf hat harte Ecken; die gezeichneten
     Glieder sind an den Enden rund – Radius 7 bei Breite 14, also genau ein
     Halbkreis. An den vier Ecken jedes Glieds blieb deshalb ein Rest der
     Zeichnung sichtbar. Ein voller Eckradius ergibt dieselbe Rundung, und
     zwar mitskalierend. */
  .schaubild .heizkoerper .glied {
    position: absolute; top: 0; bottom: 0;
    border-radius: 999px;
    transition: background 1.2s ease;
  }
  .schaubild .heizkoerper.da { opacity: 1; }
  /* Karte: Schaubild und Werteliste nebeneinander, am Handy untereinander. */
  /* Die Karte richtet sich nach ihrer **eigenen** Breite, nicht nach dem
     Fenster: In der Editor-Vorschau steht sie schmal in einem breiten Fenster,
     und feste Schriftgrößen liefen dort ineinander. */
  .karte-zweispaltig { display: grid; gap: 12px; }
  /* **Jede Spalte ist ihr eigener Bezug.** Die Werteliste steht in einem
     Drittel der Kartenbreite; nach der ganzen Karte gemessen blieb sie groß
     und Titel und Wert liefen ineinander. */
  .karte-zweispaltig > * { container-type: inline-size; min-width: 0; }
  /* Gleich hohe Zeilen, auch wo Anlagenteil oder Wert fehlen. Die kompakte
     Ansicht ist durchgehend flacher, nicht einzelne Zeilen darin. */
  .karte-zweispaltig .zeile { min-height: 56px; }
  .karte-zweispaltig .zeile.knapp { min-height: 40px; }
  @container (max-width: 340px) {
    .karte-zweispaltig .zeile .wert { font-size: 16px; }
    .karte-zweispaltig .zeile .wert.lang { font-size: 12px; }
    .karte-zweispaltig .zeile .titel { font-size: 12px; }
    .karte-zweispaltig .zeile .bezeichnung { font-size: 10px; }
    .karte-zweispaltig .zeile { gap: 8px; padding: 8px 10px; min-height: 48px; }
    .karte-zweispaltig .zeile.knapp { min-height: 36px; }
    .karte-zweispaltig .kartenkopf h2 { font-size: 15px; }
  }
  /* Noch schmaler passen Titel und Wert nicht mehr nebeneinander. Dann
     untereinander statt in immer kleinerer Schrift. */
  @container (max-width: 230px) {
    .karte-zweispaltig .zeile {
      flex-direction: column; align-items: flex-start; gap: 2px; min-height: 0;
    }
    .karte-zweispaltig .zeile.knapp { min-height: 0; }
    .karte-zweispaltig .zeile .rechts { text-align: left; }
    .karte-zweispaltig .zeile .wert { font-size: 15px; }
    .karte-zweispaltig .zeile .wert.lang { font-size: 12px; }
  }
  .karte-zweispaltig.lage-rechts { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); }
  .karte-zweispaltig.lage-unten { grid-template-columns: minmax(0, 1fr); }
  @media (max-width: 700px) {
    .karte-zweispaltig.lage-rechts { grid-template-columns: minmax(0, 1fr); }
  }
  /* Die Karte kann die Bewegung abschalten; die Zustände bleiben sichtbar. */
  .schaubild.ruhig * { animation: none !important; }
  /* Heiß genug, um zu arbeiten: ein ruhiges Pulsieren, dieselbe Geste wie am
     Glutbett des Kessels. Nichts blinkt – es soll auffallen, nicht nerven. */
  .schaubild .heizkoerper.heiss { animation: glimmen 3.2s ease-in-out infinite; }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .heizkoerper.heiss { animation: none; }
  }

  /* Die Schichtung des Puffers: oben die Farbe der oberen Temperatur, unten
     die der unteren. Beide sind gemessen, hier wird nichts angedeutet. Ist
     der Speicher durchgeladen, steht er durchgehend in einer Farbe. */
  .schaubild .schichtung {
    position: absolute; pointer-events: none;
    /* Unter das Bild. Das muss ein *negativer* Wert sein: Ein absolut
       gesetztes Element malt sonst ueber jeden in-flow-Inhalt, auch wenn es
       im DOM davor steht. Mit z-index 0 lag die Farbe wieder ueber der
       Zeichnung und verdeckte Naehte, Deckel, Glanz und beim Boiler das
       Register - genau der Zustand, der behoben werden sollte. */
    z-index: -1;
    /* Nicht ausblendbar: Die Zeichnung laesst den Speicherkoerper frei,
       sobald ein Fuehlerwert bekannt ist. Stuende diese Flaeche auf
       Deckkraft null, sae man beim Laden durch den Speicher hindurch. Fehlen
       die Messwerte, setzt die Oberflaeche den neutralen Verlauf des
       Bauteils - er kommt mit den Daten vom Server, damit die Farben nicht
       hier und in schema.py getrennt gepflegt werden muessen. */
    transition: background 1.5s ease;
  }

  /* Ladezustand des Puffers, zwischen seinen beiden Temperaturen. */
  .schaubild .speicher {
    position: absolute; transform: translate(-50%, -50%);
    padding: 0.2em 0.7em; border-radius: 999px;
    font-size: clamp(
      calc(9px * var(--hn-schrift)),
      calc(var(--hn-einheit) * 12 * var(--hn-schrift)),
      calc(18px * var(--hn-schrift))
    );
    font-weight: 700; letter-spacing: 0.3px;
    background: rgba(10, 14, 19, 0.78);
    pointer-events: none; white-space: nowrap;
    opacity: 0; transition: opacity 0.4s ease;
  }
  .schaubild .speicher.laedt { opacity: 1; color: #ffab6f; }
  .schaubild .speicher.entlaedt { opacity: 1; color: var(--hn-akzent); }

  /* Lampen des Pumpen-/Relaismoduls. Ohne Anforderung unsichtbar – dann steht
     im Bild die gezeichnete Lampe. Mit Anforderung liegt Grün darüber; die
     Betriebslampe deckt das gezeichnete Rot vollständig ab. */
  .schaubild .lampe {
    position: absolute; transform: translate(-50%, -50%);
    aspect-ratio: 1; border-radius: 50%; pointer-events: none;
    opacity: 0; transition: opacity 0.4s ease;
    /* Innen fast weiß, außen grün: So leuchtet die Lampe, statt nur grün zu
       sein – auf dem dunklen Gehäuse sonst kaum zu sehen. */
    background: radial-gradient(circle at 50% 40%, #d6ffe2 0%, #4ade6a 55%, #2f9e46 100%);
  }
  /* Die Betriebslampe muss die gezeichnete rote vollständig verdecken. */
  .schaubild .lampe.betrieb { box-shadow: 0 0 10px 3px rgba(74, 222, 106, 0.75); }
  .schaubild .lampe.klemme { box-shadow: 0 0 7px 2px rgba(74, 222, 106, 0.7); }
  .schaubild .lampe.an { opacity: 1; }
  .schaubild .lampe.klemme.an { animation: lampe-blinken 1.8s ease-in-out infinite; }
  /* Am Wärmeerzeuger pulst die Lampe langsamer: Sie steht für den laufenden
     Betrieb, nicht für eine anliegende Anforderung. */
  .schaubild .lampe.erzeuger.an { animation: lampe-blinken 2.6s ease-in-out infinite; }
  /* Eine Wärmequelle pulst wie ein Erzeuger: Sie liefert, sie fordert nicht an. */
  .schaubild .lampe.quelle.an { animation: lampe-blinken 2.6s ease-in-out infinite; }
  @keyframes lampe-blinken {
    0%, 100% { opacity: 0.45; }
    50% { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .lampe.klemme.an,
    .schaubild .lampe.quelle.an,
    .schaubild .lampe.erzeuger.an { animation: none; opacity: 1; }
  }
  @keyframes glimmen {
    0%, 100% { filter: brightness(0.85); }
    50% { filter: brightness(1.25); }
  }

  /* Wer Bewegung abbestellt hat, bekommt den Zustand als ruhige Farbe. */
  @media (prefers-reduced-motion: reduce) {
    .schaubild .fluss.laeuft, .schaubild .glut.brennt { animation: none; }
  }
  /* Der Wärmeübergabepunkt in Betrieb: Glut im Gehäuse, Abgabe nach außen,
     dazu das drehende Laufrad darunter. Ohne Anforderung ist alles
     unsichtbar, dann steht im Bild das gezeichnete Modul. */
  .schaubild .uebergabe {
    position: absolute; pointer-events: none; overflow: hidden;
    opacity: 0; transition: opacity 0.8s ease;
  }
  .schaubild .uebergabe.an { opacity: 1; }
  .schaubild .uebergabe .glut {
    position: absolute; left: 50%; top: 53%; width: 112%; aspect-ratio: 1.15;
    transform: translate(-50%, -50%); border-radius: 50%;
    background: radial-gradient(circle, var(--hn-uebergabe) 0%,
      color-mix(in srgb, var(--hn-uebergabe) 55%, transparent) 45%,
      transparent 72%);
    animation: uebergabe-glimmen 3.4s ease-in-out infinite;
  }
  .schaubild .uebergabe .glut.zwei {
    left: 32%; top: 40%; width: 74%;
    animation-duration: 2.1s; animation-direction: reverse;
  }
  @keyframes uebergabe-glimmen {
    0%, 100% { opacity: 0.12; }
    45% { opacity: 0.40; }
    70% { opacity: 0.22; }
  }
  /* Die Wellen liegen im Gehäuse und werden am Rand beschnitten: Sie sollen
     die Abgabe andeuten, nicht über die Nachbarn im Bild laufen. */
  .schaubild .uebergabe .welle {
    position: absolute; left: 50%; top: 53%; width: 90%; aspect-ratio: 1;
    transform: translate(-50%, -50%); border-radius: 50%;
    border: 2px solid var(--hn-uebergabe); opacity: 0;
    animation: uebergabe-abgabe 3s ease-out infinite;
  }
  .schaubild .uebergabe .welle:nth-child(4) { animation-delay: 1s; }
  .schaubild .uebergabe .welle:nth-child(5) { animation-delay: 2s; }
  @keyframes uebergabe-abgabe {
    0% { opacity: 0; transform: translate(-50%, -50%) scale(0.5); }
    25% { opacity: 0.5; }
    100% { opacity: 0; transform: translate(-50%, -50%) scale(1.45); }
  }
  /* Das eigene Laufrad über dem gezeichneten. Es dreht sich viel langsamer
     als eine Pumpe: Hier fließt keine Fördermenge, hier geht Wärme über. */
  .schaubild .uebergabe-rad {
    position: absolute; transform: translate(-50%, -50%);
    aspect-ratio: 1; border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    background: var(--hn-karte, #151d26);
    color: var(--hn-gedaempft);
    opacity: 0; transition: opacity 0.8s ease, color 0.6s ease;
    /* Gedreht reicht der Kasten des Rads über die Scheibe; ohne Beschnitt
       bleiben dort Reste früherer Bilder stehen. */
    overflow: hidden; contain: paint;
  }
  .schaubild .uebergabe-rad.an { opacity: 1; color: var(--hn-uebergabe); }
  .schaubild .uebergabe-rad .rad {
    display: block; width: 78%; aspect-ratio: 1; transform-origin: 50% 50%;
  }
  .schaubild .uebergabe-rad .rad svg { display: block; width: 100%; height: 100%; }
  .schaubild .uebergabe-rad.an .rad { animation: dreht 16s linear infinite; will-change: transform; }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .uebergabe .glut,
    .schaubild .uebergabe .welle,
    .schaubild .uebergabe-rad.an .rad { animation: none; }
    .schaubild .uebergabe .glut { opacity: 0.3; }
    .schaubild .uebergabe .welle { opacity: 0; }
  }

  .schaubild .pumpe {
    position: absolute; transform: translate(-50%, -50%);
    width: var(--hn-marke);
    aspect-ratio: 1; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    /* Die stehende Pumpe nimmt den Grund der Karte an. Eine feste dunkle
       Scheibe wirkt im hellen Farbsatz wie ein Loch in der Leitung. */
    background: var(--hn-karte, #151d26);
    overflow: hidden; contain: paint;
    border: 1px solid color-mix(in srgb, var(--hn-gedaempft) 45%, transparent);
    color: var(--hn-gedaempft);
    transition: transform 0.5s ease, color 0.4s ease, border-color 0.4s ease,
      box-shadow 0.4s ease;
  }
  /* Das Laufrad ist eine eigene Zeichnung mit dem Nullpunkt in der Mitte des
     Kastens. Ein Symbolzeichensatz gibt diese Mitte nicht her: Die Nabe lag
     neben dem Drehpunkt, und das Rad eierte beim Drehen. */
  /* Gedreht wird der Kasten aus HTML, nicht das SVG selbst: WebKit legt den
     Drehpunkt eines SVG sonst an die Ecke seiner viewBox, und das Rad eiert. */
  .schaubild .pumpe .rad {
    display: block; width: 62%; aspect-ratio: 1;
    transform-origin: 50% 50%;
  }
  .schaubild .pumpe .rad svg { display: block; width: 100%; height: 100%; }
  /* Die laufende Pumpe tritt hervor. Der Faktor bleibt klein: Eine Marke, die
     doppelt so groß wird, ragte in Kessel und Speicher hinein. */
  .schaubild .pumpe.laeuft {
    color: var(--hn-akzent); border-color: color-mix(in srgb, var(--hn-akzent) 60%, transparent);
    box-shadow: 0 0 10px color-mix(in srgb, var(--hn-akzent) 35%, transparent);
    transform: translate(-50%, -50%) scale(1.18);
  }
  /* Das drehende Rad bekommt eine eigene Ebene. Ohne sie rastert WebKit es in
     den mit 1.18 skalierten Elternkasten hinein und rundet dabei je Bild auf
     ganze Pixel – das Rad eiert dann, je nach Position der Pumpe. */
  .schaubild .pumpe.laeuft .rad {
    animation: dreht 1.6s linear infinite;
    will-change: transform;
  }
  @keyframes dreht { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    .schaubild .pumpe.laeuft .rad { animation: none; }
  }
  .schaubild .marke-wert {
    position: absolute; transform: translate(-50%, -50%);
    background: rgba(10, 14, 19, 0.72); color: #fff;
    font-size: clamp(
      calc(10px * var(--hn-schrift)),
      calc(var(--hn-einheit) * 15 * var(--hn-schrift)),
      calc(22px * var(--hn-schrift))
    );
    font-weight: 600;
    padding: 0.22em 0.6em;
    border-radius: 0.55em; white-space: nowrap;
  }

  .linienwahl { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .linie {
    padding: 5px 10px; border-radius: 999px; font: inherit; font-size: 12px;
    font-weight: 600; cursor: pointer; color: inherit; opacity: 0.45;
    background: var(--hn-flaeche);
    border: 1px solid var(--hn-linie);
  }
  .linie:hover { opacity: 0.8; }
  .linie[aria-pressed="true"] {
    opacity: 1; color: var(--hn-akzent);
    background: color-mix(in srgb, var(--hn-akzent) 15%, transparent);
    border-color: color-mix(in srgb, var(--hn-akzent) 45%, transparent);
  }
  .gitter { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }
`;
