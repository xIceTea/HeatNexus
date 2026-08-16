// Führt beim Scrollen mit: markiert den Abschnitt in Kopfzeile und Seitenbaum,
// füllt die rechte Spalte mit den Zwischenüberschriften des offenen Abschnitts
// und blendet den Knopf nach oben ein.
(function () {
  "use strict";

  var GRENZE = 140; // Höhe der Kopfzeile plus etwas Luft
  var SCHMAL = 940; // ab hier steht die Abschnittsleiste statt der Spalte
  var wurzel = document.documentElement;

  // ---- Verweise auf eigene Seiten ----------------------------------------
  // Trifft einer die gerade offene Seite, wird er markiert — sonst bliebe die
  // Startseite ohne Hinweis in der Kopfzeile.
  var seite = location.pathname.replace(/index\.html$/, "");
  Array.prototype.forEach.call(document.querySelectorAll(".wege a"), function (a) {
    if ((a.getAttribute("href") || "").indexOf("#") !== -1) return;
    if (a.hostname !== location.hostname) return;
    if (a.pathname.replace(/index\.html$/, "") === seite) a.setAttribute("aria-current", "true");
  });

  // ---- Gliederung auf schmalen Geräten -----------------------------------
  // Der markierte Eintrag der Leiste ist zugleich der Griff: Ein Tipp darauf
  // faltet die ganze Gliederung mit ihren Gruppen aus.
  var leiste = document.querySelector(".baum-inhalt");
  var offenBei = 0;

  function klappen(auf) {
    wurzel.classList.toggle("baum-offen", auf);
    if (auf) offenBei = window.scrollY || 0;
  }

  if (leiste) {
    leiste.addEventListener("click", function (e) {
      var weg = e.target.closest ? e.target.closest("a") : null;
      if (!weg || window.innerWidth > SCHMAL) return;
      if (weg.getAttribute("aria-current") === "true" && !wurzel.classList.contains("baum-offen")) {
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
    if (wurzel.classList.contains("baum-offen") && Math.abs(y - offenBei) > 60) klappen(false);

    // Die Kopfzeile weicht nur dort, wo sie Platz kostet.
    if (window.innerWidth > SCHMAL) {
      wurzel.classList.remove("kopf-weg");
    } else if (y < 140) {
      wurzel.classList.remove("kopf-weg");
    } else if (y > vorher + 10) {
      wurzel.classList.add("kopf-weg");
    } else if (y < vorher - 10) {
      wurzel.classList.remove("kopf-weg");
    }
    vorher = y;
  }

  // ---- Abschnitte --------------------------------------------------------
  var aufsatz = document.querySelector(".aufsatz");
  var kasten = document.getElementById("wegweiser");
  var teile = aufsatz ? Array.prototype.slice.call(aufsatz.querySelectorAll(".teil")) : [];

  var verweise = {};
  var liste = null;
  var offen = null;
  var punkte = [];

  if (teile.length) {
    // Ein Punkt der Kopfzeile vertritt mehrere Abschnitte und trägt sie in
    // `data-deckt`; im Baum steht je Abschnitt eine eigene Sprungmarke.
    Array.prototype.forEach.call(document.querySelectorAll(".wege a, .baum a"), function (a) {
      var deckt = a.getAttribute("data-deckt");
      var marken = deckt ? deckt.split(/\s+/) : [(a.getAttribute("href") || "").split("#")[1]];
      marken.forEach(function (marke) {
        if (marke) (verweise[marke] = verweise[marke] || []).push(a);
      });
    });

    liste = document.createElement("ul");
    if (kasten) {
      var titel = document.createElement("h2");
      titel.textContent = "In diesem Abschnitt";
      kasten.appendChild(titel);
      kasten.appendChild(liste);
    }
  }

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

  // Bei der waagerechten Leiste den markierten Eintrag in Sicht halten.
  function mitfuehren(marke) {
    var baum = document.querySelector(".baum-inhalt");
    var weg = verweise[marke] && verweise[marke].filter(function (a) {
      return baum && baum.contains(a);
    })[0];
    if (!baum || !weg) return;
    if (getComputedStyle(baum).flexDirection === "row") {
      baum.scrollLeft = weg.offsetLeft - baum.clientWidth / 2 + weg.offsetWidth / 2;
    }
  }

  function abschnitte() {
    if (!teile.length) return;
    var teil = oberhalb(teile);
    if (teil && teil !== offen) {
      offen = teil;
      // Erst alles abräumen, dann setzen: Ein Punkt der Kopfzeile steht unter
      // mehreren Abschnitten und würde sich sonst selbst wieder löschen.
      for (var marke in verweise) {
        verweise[marke].forEach(function (a) { a.removeAttribute("aria-current"); });
      }
      (verweise[teil.id] || []).forEach(function (a) { a.setAttribute("aria-current", "true"); });
      if (kasten && liste) {
        inhaltAufbauen(teil);
        kasten.scrollTop = 0;
      }
      mitfuehren(teil.id);
    }
    if (!punkte.length) return;
    var jetzt = oberhalb(punkte.map(function (p) { return p.kopf; }));
    punkte.forEach(function (p) { p.weg.classList.toggle("hier", p.kopf === jetzt); });
  }

  var laeuft = false;
  function angestossen() {
    if (laeuft) return;
    laeuft = true;
    requestAnimationFrame(function () {
      laeuft = false;
      rand();
      abschnitte();
    });
  }

  addEventListener("scroll", angestossen, { passive: true });
  addEventListener("resize", angestossen, { passive: true });
  rand();
  abschnitte();
})();
