// Führt beim Scrollen mit: markiert den Abschnitt in Kopfzeile und Seitenbaum
// und füllt die rechte Spalte mit den Zwischenüberschriften des Abschnitts,
// in dem man gerade liest.
(function () {
  "use strict";

  var GRENZE = 140; // Höhe der Kopfzeile plus etwas Luft
  var aufsatz = document.querySelector(".aufsatz");
  var kasten = document.getElementById("wegweiser");
  if (!aufsatz) return;

  var teile = Array.prototype.slice.call(aufsatz.querySelectorAll(".teil"));
  if (!teile.length) return;

  // Alle Verweise, die auf einen Abschnitt dieser Seite zeigen. Ein Punkt der
  // Kopfzeile vertritt mehrere Abschnitte und trägt sie in `data-deckt`.
  var verweise = {};
  Array.prototype.forEach.call(document.querySelectorAll(".wege a, .baum a"), function (a) {
    var deckt = a.getAttribute("data-deckt");
    var marken = deckt ? deckt.split(/\s+/) : [(a.getAttribute("href") || "").split("#")[1]];
    marken.forEach(function (marke) {
      if (marke) (verweise[marke] = verweise[marke] || []).push(a);
    });
  });

  var titel = document.createElement("h2");
  titel.textContent = "In diesem Abschnitt";
  var liste = document.createElement("ul");
  if (kasten) {
    kasten.appendChild(titel);
    kasten.appendChild(liste);
  }

  var offen = null;
  var punkte = [];

  function oberhalb(elemente) {
    var treffer = elemente[0] || null;
    for (var i = 0; i < elemente.length; i++) {
      if (elemente[i].getBoundingClientRect().top <= GRENZE) treffer = elemente[i];
      else break;
    }
    return treffer;
  }

  function inhaltAufbauen(teil) {
    liste.textContent = "";
    punkte = [];
    // Abschnitte ohne Zwischenebene (die Auswahlwerte) führen nur h3.
    var koepfe = teil.querySelectorAll("h2");
    if (koepfe.length < 2) koepfe = teil.querySelectorAll("h3");
    Array.prototype.forEach.call(koepfe, function (kopf, i) {
      if (!kopf.id) kopf.id = teil.id + "-" + i;
      var punkt = document.createElement("li");
      var weg = document.createElement("a");
      weg.href = "#" + kopf.id;
      weg.textContent = kopf.textContent.trim();
      punkt.appendChild(weg);
      liste.appendChild(punkt);
      punkte.push({ kopf: kopf, weg: weg });
    });
    if (kasten) kasten.hidden = punkte.length < 2;
  }

  function pruefen() {
    var teil = oberhalb(teile);
    if (teil && teil !== offen) {
      offen = teil;
      // Erst alles abräumen, dann setzen: Ein Punkt der Kopfzeile steht unter
      // mehreren Abschnitten und würde sich sonst selbst wieder löschen.
      for (var marke in verweise) {
        verweise[marke].forEach(function (a) { a.removeAttribute("aria-current"); });
      }
      (verweise[teil.id] || []).forEach(function (a) { a.setAttribute("aria-current", "true"); });
      if (kasten) {
        inhaltAufbauen(teil);
        kasten.scrollTop = 0;
      }
      mitfuehren(teil.id);
    }
    if (!punkte.length) return;
    var jetzt = oberhalb(punkte.map(function (p) { return p.kopf; }));
    punkte.forEach(function (p) { p.weg.classList.toggle("hier", p.kopf === jetzt); });
  }

  // Bei langem Baum den markierten Eintrag in Sicht halten.
  function mitfuehren(marke) {
    var baum = document.querySelector(".baum-inhalt");
    var weg = verweise[marke] && verweise[marke].filter(function (a) { return baum && baum.contains(a); })[0];
    if (!baum || !weg) return;
    var waagerecht = getComputedStyle(baum).flexDirection === "row";
    if (waagerecht) baum.scrollLeft = weg.offsetLeft - baum.clientWidth / 2 + weg.offsetWidth / 2;
  }

  var laeuft = false;
  function angestossen() {
    if (laeuft) return;
    laeuft = true;
    requestAnimationFrame(function () { laeuft = false; pruefen(); });
  }

  addEventListener("scroll", angestossen, { passive: true });
  addEventListener("resize", angestossen, { passive: true });
  pruefen();
})();
