// Führt beim Scrollen mit: markiert den Abschnitt in Kopfzeile und Seitenbaum,
// füllt die rechte Spalte mit den Zwischenüberschriften des offenen Abschnitts
// und blendet den Knopf nach oben ein.
(function () {
  "use strict";

  var wurzel = document.documentElement;
  // Die Umbruchpunkte stehen im Stilblatt; hier wird nur gefragt, welcher gilt.
  var schmal = matchMedia("(max-width: 940px)");
  var mitSpalte = matchMedia("(min-width: 1241px)");

  /**
   * Ab welcher Höhe ein Abschnitt als erreicht gilt. Grundlage ist `--anker`
   * aus dem Stilblatt — derselbe Wert, der auch das `scroll-padding-top`
   * setzt. Ohne diesen Gleichlauf zählte ein angesprungener Abschnitt noch
   * als nicht erreicht und die Markierung blieb auf dem vorherigen stehen.
   */
  var GRENZE = 0;
  function grenzeLesen() {
    var anker = parseFloat(getComputedStyle(wurzel).getPropertyValue("--anker"));
    GRENZE = (anker || 96) + 28;
  }
  grenzeLesen();

  // ---- Verweise -----------------------------------------------------------
  // Ein Punkt der Kopfzeile vertritt mehrere Abschnitte und trägt sie in
  // `data-deckt`; im Baum steht je Abschnitt eine eigene Sprungmarke. Verweise
  // ohne Sprungmarke zeigen auf eine eigene Seite — trifft einer die gerade
  // offene, wird er markiert, sonst bliebe die Startseite ohne Hinweis.
  var verweise = {};
  var seite = location.pathname.replace(/index\.html$/, "");
  document.querySelectorAll(".wege a, .baum a").forEach(function (a) {
    var ziel = a.getAttribute("href") || "";
    if (ziel.indexOf("#") === -1) {
      if (a.hostname === location.hostname && a.pathname.replace(/index\.html$/, "") === seite) {
        a.setAttribute("aria-current", "true");
      }
      return;
    }
    var deckt = a.getAttribute("data-deckt");
    (deckt ? deckt.split(/\s+/) : [ziel.split("#")[1]]).forEach(function (marke) {
      if (marke) (verweise[marke] = verweise[marke] || []).push(a);
    });
  });

  // ---- Gliederung auf schmalen Geräten -----------------------------------
  // Der markierte Eintrag der Leiste ist zugleich der Griff: Ein Tipp darauf
  // faltet die ganze Gliederung mit ihren Gruppen aus.
  var leiste = document.querySelector(".baum-inhalt");
  var offenBei = 0;
  var letzteHand = 0;

  if (leiste) {
    ["touchstart", "touchmove", "pointerdown", "wheel"].forEach(function (art) {
      leiste.addEventListener(art, function () { letzteHand = Date.now(); }, { passive: true });
    });
  }

  function offen() {
    return wurzel.classList.contains("baum-offen");
  }

  // Wer die Leiste von Hand verschiebt, darf sie verschoben lassen — sobald er
  // aber weiterliest, holt sie den Abschnitt zurück, in dem er steht.
  function nachfuehren(sofort) {
    if (!leiste || !schmal.matches || offen()) return;
    if (!sofort && Date.now() - letzteHand < 1500) return;
    var weg = leiste.querySelector('a[aria-current="true"]');
    if (!weg) return;
    var links = weg.offsetLeft - leiste.scrollLeft;
    if (sofort || links < 12 || links + weg.offsetWidth > leiste.clientWidth - 12) {
      // `block: "nearest"` hält die Seite still, nur die Leiste rückt nach.
      weg.scrollIntoView({
        block: "nearest",
        inline: "center",
        behavior: sofort ? "auto" : "smooth",
      });
    }
  }

  function klappen(auf) {
    if (auf === offen()) return;
    // Der Bezugspunkt muss sofort stehen, sonst hält der nächste Scroll-Takt
    // das eben geöffnete Menü für weggescrollt und schließt es wieder.
    if (auf) offenBei = window.scrollY || 0;
    wurzel.classList.toggle("baum-offen", auf);
    if (!leiste) return;
    // Der Wechsel zwischen Zeile und Spalte setzt die Rollposition zurück;
    // der markierte Eintrag muss danach wieder in Sicht.
    requestAnimationFrame(function () {
      var weg = leiste.querySelector('a[aria-current="true"]');
      if (!weg) return;
      if (auf) weg.scrollIntoView({ block: "nearest", behavior: "auto" });
      else nachfuehren(true);
    });
  }

  if (leiste) {
    leiste.addEventListener("click", function (e) {
      var weg = e.target.closest("a");
      if (!weg || !schmal.matches) return;
      if (weg.getAttribute("aria-current") === "true" && !offen()) {
        e.preventDefault();
        klappen(true);
        return;
      }
      klappen(false);
    });
  }

  // ---- Knopf nach oben und Kopfzeile -------------------------------------
  var hochKnopf = document.querySelector(".hoch");
  var vorher = window.scrollY || 0;

  function rand() {
    var y = window.scrollY || 0;
    if (hochKnopf) hochKnopf.classList.toggle("sichtbar", y > 700);
    // Wer weiterliest, hat die Gliederung nicht mehr im Sinn.
    if (offen() && Math.abs(y - offenBei) > 60) klappen(false);

    // Die Kopfzeile weicht nur dort, wo sie Platz kostet.
    if (!schmal.matches || y < 140) wurzel.classList.remove("kopf-weg");
    else if (y > vorher + 10) wurzel.classList.add("kopf-weg");
    else if (y < vorher - 10) wurzel.classList.remove("kopf-weg");
    vorher = y;
  }

  // ---- Abschnitte --------------------------------------------------------
  var aufsatz = document.querySelector(".aufsatz");
  var kasten = document.getElementById("wegweiser");
  var teile = aufsatz ? Array.prototype.slice.call(aufsatz.querySelectorAll(".teil")) : [];
  var liste = null;

  if (teile.length && kasten) {
    var titel = document.createElement("h2");
    titel.textContent = "In diesem Abschnitt";
    liste = document.createElement("ul");
    kasten.appendChild(titel);
    kasten.appendChild(liste);
  }

  var geoeffnet = null;
  var punkte = [];
  var teilOben = [];
  var punktOben = [];
  var neuVermessen = true;

  /**
   * Dokumentkoordinaten statt Messung je Takt. Ein Abschnitt der Anleitung
   * führt bis zu 167 Überschriften; die einzeln zu vermessen erzwänge in
   * jedem Bild einen Neuaufbau der 176 000 px hohen Seite.
   */
  function vermessen() {
    var y = window.scrollY || 0;
    teilOben = teile.map(function (t) { return t.getBoundingClientRect().top + y; });
    punktOben = punkte.map(function (p) { return p.kopf.getBoundingClientRect().top + y; });
    neuVermessen = false;
  }

  /** Der letzte Eintrag, dessen Oberkante über der Grenze liegt. */
  function oberhalb(oben, linie) {
    var treffer = oben.length ? 0 : -1;
    for (var i = 0; i < oben.length; i++) {
      if (oben[i] <= linie) treffer = i;
      else break;
    }
    return treffer;
  }

  function inhaltAufbauen(teil) {
    punkte = [];
    // Ohne sichtbare Spalte gibt es nichts zu füllen und nichts zu verfolgen.
    if (!liste || !mitSpalte.matches) {
      if (kasten) kasten.hidden = true;
      return;
    }
    // Abschnitte ohne Zwischenebene (die Auswahlwerte) führen nur h3.
    var koepfe = teil.querySelectorAll("h2");
    if (koepfe.length < 2) koepfe = teil.querySelectorAll("h3");
    var sammlung = document.createDocumentFragment();
    koepfe.forEach(function (kopf, i) {
      if (!kopf.id) kopf.id = teil.id + "-" + i;
      var punkt = document.createElement("li");
      var weg = document.createElement("a");
      weg.href = "#" + kopf.id;
      weg.textContent = kopf.textContent.trim();
      punkt.appendChild(weg);
      sammlung.appendChild(punkt);
      punkte.push({ kopf: kopf, weg: weg });
    });
    liste.textContent = "";
    liste.appendChild(sammlung);
    kasten.hidden = punkte.length < 2;
  }

  var letzterPunkt = -1;

  function abschnitte() {
    if (!teile.length) return;
    if (neuVermessen) vermessen();
    var linie = (window.scrollY || 0) + GRENZE;

    var i = oberhalb(teilOben, linie);
    var teil = i >= 0 ? teile[i] : null;
    if (teil && teil !== geoeffnet) {
      geoeffnet = teil;
      // Erst alles abräumen, dann setzen: Ein Punkt der Kopfzeile steht unter
      // mehreren Abschnitten und würde sich sonst selbst wieder löschen.
      for (var marke in verweise) {
        verweise[marke].forEach(function (a) { a.removeAttribute("aria-current"); });
      }
      (verweise[teil.id] || []).forEach(function (a) { a.setAttribute("aria-current", "true"); });
      inhaltAufbauen(teil);
      if (kasten) kasten.scrollTop = 0;
      letzterPunkt = -1;
      // Nach dem Umbau der Liste erst messen lassen, dann nachführen.
      requestAnimationFrame(function () {
        vermessen();
        nachfuehren(true);
      });
      return;
    }

    if (!punkte.length) return;
    var j = oberhalb(punktOben, linie);
    if (j === letzterPunkt) return;
    if (letzterPunkt >= 0 && punkte[letzterPunkt]) punkte[letzterPunkt].weg.classList.remove("hier");
    if (j >= 0) punkte[j].weg.classList.add("hier");
    letzterPunkt = j;
  }

  var laeuft = false;
  function angestossen() {
    if (laeuft) return;
    laeuft = true;
    requestAnimationFrame(function () {
      laeuft = false;
      rand();
      if (teile.length) nachfuehren(false);
      abschnitte();
    });
  }

  function umgebaut() {
    grenzeLesen();
    neuVermessen = true;
    // Die Spalte kann durch die Breitenänderung dazugekommen oder weggefallen sein.
    if (geoeffnet) inhaltAufbauen(geoeffnet);
    angestossen();
  }

  addEventListener("scroll", angestossen, { passive: true });
  addEventListener("resize", umgebaut, { passive: true });
  // Ein Sprung auf dieselbe Marke löst kein Scrollen aus — die Markierung muss
  // trotzdem nachziehen.
  addEventListener("hashchange", angestossen);
  // Nachgeladene Bilder verschieben alles darunter.
  addEventListener("load", umgebaut);

  rand();
  abschnitte();
})();
