---
titel: Windhager-Heizungen in Home Assistant
beschreibung: HeatNexus liest die Anlage lokal aus, ohne Cloud und ohne Konto — mit Oberfläche, Dashboard, Anlagenschaubild und Zeitprogrammen.
---

{% assign anleitung = '/ANLEITUNG' | relative_url %}
{% assign hacs = 'https://my.home-assistant.io/redirect/hacs_repository/?owner=xIceTea&amp;repository=HeatNexus&amp;category=integration' %}

<section class="buehne" markdown="0">
  <div class="huelle">
    <h1>Die ganze Heizung.<br>Auf einen Blick.</h1>
    <p class="unter">HeatNexus bringt deine Windhager-Anlage lokal in Home Assistant. Ohne Cloud, ohne Konto.</p>
    <div class="tasten">
      <a class="taste voll" href="{{ hacs }}">In HACS öffnen</a>
      <a class="taste leer" href="#anlagen">Passt das zu meiner Anlage?</a>
    </div>
  </div>

  <svg class="ring" viewBox="-110 0 740 540" role="img" aria-label="Kessel, Puffer, Heizkreis und Warmwasser auf einem Ring um Home Assistant, mit Beispielwerten">
    <defs>
      <linearGradient id="ring-verlauf" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#f28a3a"/><stop offset=".45" stop-color="#e5533d"/><stop offset="1" stop-color="#4ba3e3"/>
      </linearGradient>
      <linearGradient id="ring-balken" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0" stop-color="#e5533d"/><stop offset="1" stop-color="#f28a3a"/>
      </linearGradient>
    </defs>
    <circle cx="260" cy="270" r="190" fill="none" stroke="url(#ring-verlauf)" stroke-width="10"/>
    <circle class="fluss" cx="260" cy="270" r="190" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".5"/>
    <g class="haus" fill="none" stroke-width="12" stroke-linecap="round" stroke-linejoin="round">
      <path d="M180 260 L260 192 L340 260"/>
      <path d="M198 248 V340 a10 10 0 0 0 10 10 H312 a10 10 0 0 0 10-10 V248"/>
    </g>
    <rect x="222" y="280" width="11" height="50" rx="4" fill="url(#ring-balken)"/>
    <rect x="241" y="270" width="11" height="60" rx="4" fill="url(#ring-balken)"/>
    <rect x="260" y="286" width="11" height="44" rx="4" fill="url(#ring-balken)"/>
    <rect x="279" y="300" width="11" height="30" rx="4" fill="#4ba3e3"/>
    <circle cx="284.5" cy="286" r="6" fill="#4ba3e3"/>
    <g font-size="19">
      <circle class="knoten" cx="260" cy="80" r="15" stroke="#f0703a" stroke-width="6"/>
      <text class="name" x="260" y="28" text-anchor="middle">Kessel</text>
      <text class="wert" x="260" y="50" text-anchor="middle">Modulation, 82 %</text>
      <circle class="knoten" cx="450" cy="270" r="15" stroke="#9b6c9a" stroke-width="6"/>
      <text class="name" x="478" y="264">Puffer</text>
      <text class="wert" x="478" y="288">71 / 48 °C</text>
      <circle class="knoten" cx="260" cy="460" r="15" stroke="#4ba3e3" stroke-width="6"/>
      <text class="name" x="260" y="506" text-anchor="middle">Heizkreis</text>
      <text class="wert" x="260" y="528" text-anchor="middle">Vorlauf 38,5 °C</text>
      <circle class="knoten" cx="70" cy="270" r="15" stroke="#f2a03a" stroke-width="6"/>
      <text class="name" x="42" y="264" text-anchor="end">Warmwasser</text>
      <text class="wert" x="42" y="288" text-anchor="end">52 °C</text>
    </g>
  </svg>
</section>

<section class="leiste" aria-label="Kurz gesagt" markdown="0">
  <div class="huelle">
    <div><b>Lokal</b><span>Nur HTTP im eigenen Netz</span></div>
    <div><b>Selbst erkannt</b><span>Keine Entitäts-IDs von Hand</span></div>
    <div><b>Dashboard</b><span>Baut sich aus der Anlage</span></div>
    <div><b>Frei</b><span>GPL-3.0, keine Fremdbibliothek</span></div>
  </div>
</section>

<section class="oberflaeche" id="oberflaeche" markdown="0">
  <div class="huelle">
    <div class="abschnitt-kopf">
      <h2 class="titel">Eine eigene Seite<br>in Home Assistant.</h2>
      <p>Schaubild, Kennwerte, Heizkreise, Warmwasser, Wartung, Verlauf, Zeitprogramme und Auswertung liegen an einem Ort in der Seitenleiste.</p>
    </div>
    <figure class="schirm">
      <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/panel_rundgang.gif"
           alt="Rundgang durch die Oberfläche: Übersicht, Störung, Steuerung, Wartung, Zeitprogramme" loading="lazy">
    </figure>
  </div>
</section>

<section class="kacheln" id="funktionen" markdown="0">
  <div class="huelle">
    <div class="abschnitt-kopf">
      <h2 class="titel">Alles, was die<br>Anlage meldet.</h2>
      <p>Die Steuerung liefert Namen, Einheiten, Wertebereiche und Auswahllisten selbst. HeatNexus übernimmt sie, wie sie kommen.</p>
    </div>

    <div class="raster">
      <a class="k k-gross" href="{{ anleitung }}#karte">
        <h3>Das Schaubild zeigt die echte Anlage.</h3>
        <p>Pumpen drehen sich, solange sie fördern. Der Puffer färbt sich nach seinen Fühlern. Als Karte steht es auch in eigenen Dashboards.</p>
        <div class="bild">
          <img class="nur-dunkel" src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_animation.gif"
               alt="Anlagenschaubild in Bewegung: der Kessel startet, der Puffer lädt, Heizkreis und Warmwasser werden warm" loading="lazy">
          <img class="nur-hell" src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_animation_hell.gif"
               alt="Anlagenschaubild in Bewegung: der Kessel startet, der Puffer lädt, Heizkreis und Warmwasser werden warm" loading="lazy">
        </div>
      </a>
      <a class="k k-hoch insel" href="{{ anleitung }}#fehlersuche">
        <h3>Störungen im Klartext.</h3>
        <p>Code, Art und Handlungsempfehlung statt einer Zahl, dazu die Meldungsliste des Bediengeräts.</p>
        <div class="meldung" aria-label="Beispiel einer Störungsmeldung">
          <div class="meldung-kopf"><span>Kessel</span><span>06:42</span></div>
          <div class="meldung-titel">Brennraumtemperatur zu gering</div>
          <div class="meldung-rat">Brennraum und Brennraumfühler prüfen.</div>
          <span class="meldung-code">Alarm AL130</span>
        </div>
      </a>
      <a class="k k-halb" href="{{ anleitung }}#oberflaeche">
        <h3>Zeitprogramme als Wochenraster.</h3>
        <p>Heizung, Warmwasser und Zirkulation lesen und schreiben, so wie die Anlage sie führt.</p>
        <div class="woche" aria-hidden="true">
          <b>Mo</b><i></i><i></i><i></i><i></i><i></i><i></i><i class="an"></i><i class="an"></i><i class="an"></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i></i><i></i>
          <b>Sa</b><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i class="an"></i><i></i><i></i>
        </div>
      </a>
      <a class="k k-halb" href="{{ anleitung }}#automatik">
        <h3>Automatik je Heizkreis.</h3>
        <p>Sie lernt das Haus, senkt an sonnigen Tagen ab und legt an milden Tagen eine Heizpause ein. Sie beginnt im Beobachtungsmodus.</p>
        <div class="pause" aria-hidden="true">
          <i style="height:80%"></i><i style="height:72%"></i><i style="height:55%"></i><i class="ab" style="height:22%"></i><i class="ab" style="height:18%"></i><i style="height:48%"></i><i style="height:66%"></i>
        </div>
      </a>
      <a class="k k-drittel" href="{{ anleitung }}#einrichtung">
        <h3>Drei Sprachen.</h3>
        <p>Oberfläche, Dashboard, Schaubild und Störungstexte.</p>
        <div class="sprachen" aria-label="Deutsch, Englisch, Niederländisch"><span>DE</span><span>EN</span><span>NL</span></div>
      </a>
      <a class="k k-drittel" href="{{ anleitung }}#oberflaeche">
        <h3>Fünf Farbsätze.</h3>
        <p>Vor- und Rücklauf bleiben in jedem Satz rot und blau.</p>
        <div class="farben" aria-label="Dunkel, Hell, Terrakotta, Petrol, Pflaume">
          <i style="--a:#1e232b;--b:#5b8def" title="Dunkel"></i>
          <i style="--a:#ffffff;--b:#2e6de0" title="Hell"></i>
          <i style="--a:#242220;--b:#d98e46" title="Terrakotta"></i>
          <i style="--a:#192226;--b:#3fa89a" title="Petrol"></i>
          <i style="--a:#211b2a;--b:#a878e0" title="Pflaume"></i>
        </div>
      </a>
      <a class="k k-drittel insel" href="{{ anleitung }}#einrichtung">
        <h3>Mehrere Gebäude.</h3>
        <p>Mehrere Steuerungen in einem Eintrag, jede mit eigenem Namen.</p>
        <div class="gebaeude" aria-hidden="true"><span>Haupthaus</span><span>Werkstatt</span></div>
      </a>
      <a class="k k-halb" href="{{ anleitung }}#einrichtung">
        <h3>Eigene Wärmequellen.</h3>
        <p>Solaranlage, Heizstab oder Fernwärme hängen nicht an der Steuerung. Angelegt erscheinen sie im Schaubild und melden, wann sie liefern.</p>
      </a>
      <a class="k k-halb" href="{{ anleitung }}#vorlagen">
        <h3>Fertige Vorlagen.</h3>
        <p>Blueprints für Störungsmeldung, Wartungserinnerung und Vorratswarnung, einzeln abwählbar.</p>
      </a>
    </div>
  </div>
</section>

<section class="anlagen" id="anlagen" markdown="0">
  <div class="huelle">
    <div class="abschnitt-kopf">
      <h2 class="titel">Passt das zu<br>meiner Anlage?</h2>
      <p>Nötig ist ein <strong>InfoWIN Touch</strong> mit Netzwerkanschluss und das Service-Passwort. Öffne <code>http://&lt;IP der Anlage&gt;</code> im Browser. Erscheint die Weboberfläche, passt es.</p>
    </div>

    <svg class="symbolvorrat" width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
      <symbol id="sym-flamme" viewBox="0 0 24 24"><path d="M12.5 2c.6 3.2-1.8 4.4-3.2 6.6C8 10.6 7 12.5 7 14.5a5 5 0 0 0 10 0c0-2.4-1.4-4-2.4-6.2-.5 1-1 1.6-1.8 2 .5-2.6-.3-6-.3-8.3Z"/></symbol>
      <symbol id="sym-scheit" viewBox="0 0 24 24"><path d="M8 4.5h9a3.5 3.5 0 0 1 0 7H8a3.5 3.5 0 0 1 0-7Z"/><path d="M8 12.5h9a3.5 3.5 0 0 1 0 7H8a3.5 3.5 0 0 1 0-7Z"/></symbol>
      <symbol id="sym-waermepumpe" viewBox="0 0 24 24"><rect x="2.5" y="4.5" width="19" height="15" rx="2"/><circle cx="12" cy="12" r="4.6"/><path d="M12 12 9.2 8.4M12 12l4.5 1.1M12 12l-1.9 4.3"/></symbol>
    </svg>

    <div class="zug">
      <div class="serie"><svg><use href="#sym-flamme"/></svg><h3>PuroWIN</h3><p>Hackgut, wahlweise Pellets</p><span class="stand geprueft">An der Anlage geprüft</span></div>
      <div class="serie"><svg><use href="#sym-flamme"/></svg><h3>BioWIN</h3><p>Pellets, auch BioWIN 2 und PelletsWIN</p><span class="stand fremd">Fremde Anlage geprüft</span></div>
      <div class="serie"><svg><use href="#sym-scheit"/></svg><h3>LogWIN</h3><p>Scheitholz, auch VarioWIN</p><span class="stand fremd">Fremde Anlage geprüft</span></div>
      <div class="serie"><svg><use href="#sym-scheit"/></svg><h3>DuoWIN</h3><p>Pellets und Scheitholz</p><span class="stand fremd">Fremde Anlage geprüft</span></div>
      <div class="serie"><svg><use href="#sym-waermepumpe"/></svg><h3>AeroWIN</h3><p>Wärmepumpe</p><span class="stand offen">Eingebunden, ungeprüft</span></div>
    </div>

    <details class="alle">
      <summary>Alle Baureihen und Module</summary>
      <div class="alle-innen">
        <div>
          <h4>Wärmeerzeuger</h4>
          <table class="tabelle">
            <thead><tr><th>Baureihe</th><th>Brennstoff</th><th>Stand</th></tr></thead>
            <tbody>
              <tr><td>PuroWIN</td><td>Hackgut, wahlweise Pellets</td><td><span class="stand geprueft">An der Anlage geprüft</span></td></tr>
              <tr><td>BioWIN, BioWIN 2, PelletsWIN</td><td>Pellets</td><td><span class="stand fremd">Fremde Anlage geprüft</span></td></tr>
              <tr><td>LogWIN, VarioWIN</td><td>Scheitholz</td><td><span class="stand fremd">Fremde Anlage geprüft</span></td></tr>
              <tr><td>DuoWIN</td><td>Pellets und Scheitholz</td><td><span class="stand fremd">Fremde Anlage geprüft</span></td></tr>
              <tr><td>AeroWIN und andere Wärmepumpen</td><td>Strom</td><td><span class="stand offen">Eingebunden, ungeprüft</span></td></tr>
              <tr><td>Gas- und Ölkessel, Brennwerttherme</td><td>Gas, Öl</td><td><span class="stand offen">Eingebunden, ungeprüft</span></td></tr>
              <tr><td>E-Heizung, Automatik- und Zusatzkessel</td><td>—</td><td><span class="stand offen">Eingebunden, ungeprüft</span></td></tr>
            </tbody>
          </table>
        </div>
        <div>
          <h4>Module und Kreise</h4>
          <table class="tabelle">
            <thead><tr><th>Anlagenteil</th><th>Stand</th></tr></thead>
            <tbody>
              <tr><td>UML / UMLZ Heizkreismodul</td><td><span class="stand geprueft">An der Anlage geprüft</span></td></tr>
              <tr><td>B-PLMi Pufferlademodul</td><td><span class="stand geprueft">An der Anlage geprüft</span></td></tr>
              <tr><td>ZSP Pumpen- und Relaismodul</td><td><span class="stand geprueft">An der Anlage geprüft</span></td></tr>
              <tr><td>Infinity PLUS Heizkreis und Warmwasser</td><td><span class="stand fremd">Fremde Anlage geprüft</span></td></tr>
              <tr><td>Pufferspeicher am Kessel</td><td><span class="stand fremd">Fremde Anlage geprüft</span></td></tr>
              <tr><td>Solar, Kaskade, Umschaltung, weitere Puffer</td><td><span class="stand offen">Eingebunden, ungeprüft</span></td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <p class="nachsatz">
        „Eingebunden“ heißt: Die Funktion steht mit Namen, Einheiten und Auswahlwerten in der
        mitgelieferten Datenbank und wird erkannt. Nachgemessen hat sie noch niemand.
        „Fremde Anlage geprüft“ heißt: Das Auslesen ist an einem beigesteuerten Abzug belegt,
        das Bedienen noch nicht.
      </p>
    </details>

    <p class="nachsatz">
      Auch was hier nicht steht, wird erkannt: HeatNexus nimmt jeden Datenpunkt mit, den die
      Steuerung führt. Unsicher? Schreib in den
      <a href="https://github.com/xIceTea/HeatNexus/discussions">Diskussionen</a>, welches Gerät
      du hast. Ein Sondenwerkzeug liest die Anlage aus, ohne etwas zu verändern.
    </p>
  </div>
</section>

<section class="ende" id="installation" markdown="0">
  <div class="huelle">
    <div>
      <h2 class="titel">In vier Schritten eingerichtet.</h2>
      <a class="taste voll" href="{{ hacs }}">In HACS öffnen</a>
    </div>
    <div>
      <ol class="schritte">
        <li><span><b>HACS öffnen</b>HeatNexus als Repository der Kategorie Integration hinzufügen.</span></li>
        <li><span><b>Herunterladen</b>Herunterladen und Home Assistant neu starten.</span></li>
        <li><span><b>Einrichten</b>Unter Einstellungen, Geräte &amp; Dienste die Integration HeatNexus hinzufügen. Gebraucht werden die IP der Steuerung, der Benutzer <code>USER</code> und das Passwort, ab Werk <code>123</code>.</span></li>
        <li><span><b>Warten</b>Der erste Durchlauf liest die ganze Anlage ein. Danach stehen Geräte, Oberfläche und Dashboard bereit.</span></li>
      </ol>
      <p class="nachsatz">
        Ohne HACS: Den Ordner <code>custom_components/heatnexus/</code> aus dem
        <a href="https://github.com/xIceTea/HeatNexus/releases/latest">Release</a> in den
        Konfigurationsordner kopieren und neu starten.
      </p>
    </div>
  </div>
</section>

<section class="weiter" id="weiterlesen" markdown="0">
  <div class="huelle">
    <div class="abschnitt-kopf">
      <h2 class="titel">Die Anleitung.</h2>
      <p>Von der Einrichtung bis zum Aufbau, durchgehend auf einer Seite.</p>
    </div>
    <div class="weiter-gruppen">
      <div>
        <h3>Einstieg</h3>
        <a href="{{ anleitung }}#einrichtung">Einrichtung<span>Bedienebenen, Abfrageintervall, mehrere Anlagen</span></a>
        <a href="{{ anleitung }}#fehlersuche">Fehlersuche<span>Wiederkehrende Fälle, nach Symptom sortiert</span></a>
      </div>
      <div>
        <h3>Bedienung</h3>
        <a href="{{ anleitung }}#oberflaeche">Die Oberfläche<span>Jeder Reiter und was er zeigt</span></a>
        <a href="{{ anleitung }}#karte">Schaubild als Karte<span>Einrichtung und Einstellungen</span></a>
        <a href="{{ anleitung }}#automatik">Automatik<span>Wie sie entscheidet</span></a>
        <a href="{{ anleitung }}#vorlagen">Vorlagen und Dienste<span>Mit Beispielaufruf</span></a>
      </div>
      <div>
        <h3>Referenz</h3>
        <a href="{{ anleitung }}#regelung">Regelung<span>Was eine Einstellung bewirkt</span></a>
        <a href="{{ anleitung }}#datenpunkte">Datenpunkte<span>Welche Werte es je Anlagenteil gibt</span></a>
        <a href="{{ anleitung }}#aufzaehlungen">Auswahlwerte<span>Was hinter den Zustandstexten steckt</span></a>
      </div>
      <div>
        <h3>Innen</h3>
        <a href="{{ anleitung }}#geraeteschnittstelle">Geräteschnittstelle<span>Die HTTP-Schnittstelle der Steuerung</span></a>
        <a href="{{ anleitung }}#aufbau">Aufbau<span>Wie die Integration innen arbeitet</span></a>
      </div>
    </div>
  </div>
</section>
