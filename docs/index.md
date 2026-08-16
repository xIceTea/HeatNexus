---
start: true
titel: Windhager-Heizungen in Home Assistant
beschreibung: HeatNexus liest die Anlage lokal aus, ohne Cloud und ohne Konto — mit Oberfläche, Dashboard, Anlagenschaubild und Zeitprogrammen.
---

<div class="huelle" markdown="0">
  <div class="held">
    <div>
      <p class="pille">
        <i class="punkt"></i>
        <span>Lokal&nbsp;· <b>0</b>&nbsp;Verbindungen&nbsp;nach&nbsp;außen&nbsp;· Abfrageintervall&nbsp;einstellbar</span>
      </p>
      <h1>Deine Windhager&#8209;Heizung in Home&nbsp;Assistant</h1>
      <p class="unter">
        HeatNexus spricht direkt mit der Steuerung im Heizraum. Kein Konto,
        keine Cloud, keine Entitäts-IDs von Hand — was die Anlage meldet,
        erscheint; was fehlt, entfällt.
      </p>
      <div class="tasten">
        <a class="taste voll" href="https://my.home-assistant.io/redirect/hacs_repository/?owner=xIceTea&amp;repository=HeatNexus&amp;category=integration">In HACS öffnen →</a>
        <a class="taste leer" href="#anlagen">Passt das zu meiner Anlage?</a>
      </div>
      <p class="beleg">kein Konto · keine Cloud · keine Fremdbibliothek · GPL-3.0</p>
    </div>

    <div class="karte">
      <div class="karte-kopf">
        <div>
          <div class="karte-titel">Systemstatus</div>
          <div class="karte-unter">PuroWIN 40 · Kesselhaus</div>
        </div>
        <span class="hilfe" aria-hidden="true">?</span>
      </div>
      <dl class="werte">
        <div class="zeile"><dt>Betriebszustand</dt><dd class="zustand">Modulation</dd></div>
        <div class="zeile"><dt>Laufzeit aktuell</dt><dd class="zahl">214 Min.</dd></div>
        <div class="zeile"><dt>Außentemperatur</dt><dd class="zahl">2,6 °C</dd></div>
        <div class="zeile"><dt>Kesselleistung</dt><dd class="last">82 %</dd></div>
        <div class="zeile"><dt>Brennkammertemperatur</dt><dd class="zahl">738,4 °C</dd></div>
        <div class="zeile"><dt>Abgastemperatur</dt><dd class="zahl">128,3 °C</dd></div>
        <div class="zeile"><dt>Brennstoff</dt><dd class="zustand">Hackgut normal</dd></div>
        <div class="zeile"><dt>Betriebsstunden</dt><dd class="zahl">18.116 h</dd></div>
        <div class="zeile"><dt>Bis Ascheentleerung</dt><dd class="zahl">96 h</dd></div>
      </dl>
      <p class="karte-fuss">Erfundene Werte, echter Aufbau — so zeigt es die Oberfläche.</p>
    </div>
  </div>
</div>

<div class="laufband" markdown="0" aria-hidden="true">
  <div class="band">
    <span>Alles wird erkannt</span><span>Kein Konto</span><span>Über 200 Störungstexte</span>
    <span>Schaubild aus der Anlage</span><span>Zeitprogramme lesen und schreiben</span>
    <span>Dashboard baut sich selbst</span><span>Fünf Farbsätze</span>
    <span>Alles wird erkannt</span><span>Kein Konto</span><span>Über 200 Störungstexte</span>
    <span>Schaubild aus der Anlage</span><span>Zeitprogramme lesen und schreiben</span>
    <span>Dashboard baut sich selbst</span><span>Fünf Farbsätze</span>
  </div>
</div>

<section id="mitbringen" markdown="0">
  <div class="huelle">
    <div class="kopfzeile">
      <p class="marke-zeile">Was mitkommt</p>
      <h2>Was HeatNexus <em>mitbringt</em></h2>
      <p class="blei">
        Die Steuerung liefert Namen, Einheiten, Wertebereiche und Auswahllisten selbst.
        HeatNexus nimmt sie, wie sie kommen.
      </p>
    </div>

    <div class="gitter">
      <a class="feld" href="ANLEITUNG#datenpunkte">
        <span class="nr">01</span>
        <h3>Alles wird erkannt</h3>
        <p>Kessel, Puffer, Heizkreise, Warmwasser, Zirkulation, Solar und Module — samt Wertebereichen, Einheiten und Auswahllisten aus der Steuerung selbst.</p>
        <span class="weiter">Datenpunkte</span>
      </a>
      <a class="feld" href="ANLEITUNG#oberflaeche">
        <span class="nr">02</span>
        <h3>Eigene Oberfläche</h3>
        <p>Eine Seite in der Seitenleiste: Schaubild, Kennwerte, Heizkreise, Warmwasser, Wartung, Verlauf und Zeitprogramme.</p>
        <span class="weiter">Die Oberfläche</span>
      </a>
      <a class="feld" href="ANLEITUNG#dashboard">
        <span class="nr">03</span>
        <h3>Dashboard inklusive</h3>
        <p>Baut sich aus dem, was gefunden wurde, und passt sich an, wenn die Anlage sich ändert. Nichts einzutragen.</p>
        <span class="weiter">Wie es gebaut wird</span>
      </a>
      <a class="feld" href="ANLEITUNG#karte">
        <span class="nr">04</span>
        <h3>Schaubild als Karte</h3>
        <p>Das Anlagenschaubild gibt es als Lovelace-Karte für selbst gebaute Dashboards — mit Werteliste, Farbsätzen und wählbaren Anlagenteilen.</p>
        <span class="weiter">Karte einrichten</span>
      </a>
      <a class="feld" href="ANLEITUNG#zeitprogramme">
        <span class="nr">05</span>
        <h3>Zeitprogramme</h3>
        <p>Heizung, Warmwasser und Zirkulation als Wochenraster — lesen und schreiben, so wie die Anlage sie führt.</p>
        <span class="weiter">Wochenraster</span>
      </a>
      <a class="feld" href="ANLEITUNG#stoerung">
        <span class="nr">06</span>
        <h3>Störungen im Klartext</h3>
        <p>Code, Art und Handlungsempfehlung statt einer Zahl. Über 200 Meldungen hinterlegt.</p>
        <span class="weiter">Störungsanzeige</span>
      </a>
      <a class="feld" href="ANLEITUNG#vorlagen">
        <span class="nr">07</span>
        <h3>Automations-Vorlagen</h3>
        <p>Fertige Blueprints für Störungsmeldung, Wartungserinnerung und Vorratswarnung — einzeln abwählbar.</p>
        <span class="weiter">Vorlagen und Dienste</span>
      </a>
      <a class="feld" href="ANLEITUNG#geraeteschnittstelle">
        <span class="nr">08</span>
        <h3>Lokal, ohne Abhängigkeiten</h3>
        <p>Nur HTTP zur Steuerung im eigenen Netz. Keine Fremdbibliothek, keine Verbindung nach draußen.</p>
        <span class="weiter">Geräteschnittstelle</span>
      </a>
    </div>
  </div>
</section>

<section id="schaubild" markdown="0">
  <div class="huelle">
    <div class="kopfzeile">
      <p class="marke-zeile">Anlagenschaubild</p>
      <h2>Gezeichnet aus dem, was <em>tatsächlich</em> da ist</h2>
      <p class="blei">
        Das Anlagenschaubild wird aus den erkannten Anlagenteilen gezeichnet.
        Pumpen drehen sich, solange sie fördern, der Puffer färbt sich nach seinen
        beiden Fühlern, das Glutbett folgt der Kesselleistung.
      </p>
    </div>

    <figure class="tafel">
      <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_animation.gif"
           alt="Anlagenschaubild in Bewegung: der Kessel startet, der Puffer lädt, Heizkreis und Warmwasser werden warm"
           loading="lazy">
      <figcaption>Der Kessel startet, der Puffer lädt, Heizkreis und Warmwasser werden warm.</figcaption>
    </figure>

    <div class="zwei-tafeln">
      <figure class="tafel">
        <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/anlagenschema_farbsaetze.gif"
             alt="Dieselbe Anlage in fünf Farbsätzen: Dunkel, Hell, Terrakotta, Petrol, Pflaume"
             loading="lazy">
        <figcaption>
          Fünf Farbsätze für Oberfläche und Karte. Sie färben Gehäuse, Rahmen und
          Schrift — Vor- und Rücklauf bleiben überall rot und blau, denn das ist
          eine Auskunft und keine Gestaltung.
        </figcaption>
      </figure>
      <figure class="tafel">
        <img src="https://raw.githubusercontent.com/xIceTea/HeatNexus/main/assets/panel_rundgang.gif"
             alt="Rundgang durch die Oberfläche: Übersicht, Störung, Steuerung, Wartung, Zeitprogramme"
             loading="lazy">
        <figcaption>
          Die eigene Oberfläche, Reiter für Reiter. Ausführlich in der
          <a href="ANLEITUNG#oberflaeche">Anleitung zur Oberfläche</a>.
        </figcaption>
      </figure>
    </div>
  </div>
</section>

<section id="anlagen" markdown="0">
  <div class="huelle">
    <div class="kopfzeile">
      <p class="marke-zeile">Voraussetzungen</p>
      <h2>Passt das zu meiner Anlage?</h2>
      <p class="blei">
        HeatNexus spricht die Netzwerkschnittstelle der <strong>Windhager</strong>-Regelung
        an, nicht ein einzelnes Kesselmodell. Erkannt wird, was die Steuerung meldet —
        die Baureihe entscheidet nur darüber, welche Zeichnung im Schaubild erscheint.
      </p>
      <p class="blei" style="margin-top:16px">
        <strong>Voraussetzung</strong> ist ein <strong>InfoWIN Touch</strong> mit
        Netzwerkanschluss (oder eine gleichwertig angebundene Regelung), erreichbar im
        eigenen Netz, plus das Service-Passwort. Ob es passt, siehst du in einer halben
        Minute: <code>http://&lt;IP der Anlage&gt;</code> im Browser öffnen — kommt die
        Weboberfläche des InfoWIN Touch, ist der Weg frei.
      </p>
    </div>

    <div class="zwei-spalten">
      <div>
        <h4>Wärmeerzeuger</h4>
        <table class="tabelle">
          <thead><tr><th>Baureihe</th><th>Brennstoff</th><th>Stand</th></tr></thead>
          <tbody>
            <tr><td>PuroWIN</td><td>Hackgut, wahlweise Pellets</td><td><span class="stand geprueft">an der Anlage geprüft</span></td></tr>
            <tr><td>BioWIN, BioWIN 2, PelletsWIN</td><td>Pellets</td><td><span class="stand fremd">fremde Anlage geprüft</span></td></tr>
            <tr><td>LogWIN, VarioWIN</td><td>Scheitholz</td><td><span class="stand offen">eingebunden, ungeprüft</span></td></tr>
            <tr><td>AeroWIN und andere Wärmepumpen</td><td>Strom</td><td><span class="stand offen">eingebunden, ungeprüft</span></td></tr>
            <tr><td>DuoWIN, Gas- und Ölkessel, Brennwerttherme</td><td>Gas, Öl</td><td><span class="stand offen">eingebunden, ungeprüft</span></td></tr>
            <tr><td>E-Heizung, Automatik- und Zusatzkessel</td><td>—</td><td><span class="stand offen">eingebunden, ungeprüft</span></td></tr>
          </tbody>
        </table>
      </div>
      <div>
        <h4>Module und Kreise</h4>
        <table class="tabelle">
          <thead><tr><th>Anlagenteil</th><th>Stand</th></tr></thead>
          <tbody>
            <tr><td>UML / UMLZ Heizkreismodul</td><td><span class="stand geprueft">an der Anlage geprüft</span></td></tr>
            <tr><td>B-PLMi Pufferlademodul</td><td><span class="stand geprueft">an der Anlage geprüft</span></td></tr>
            <tr><td>ZSP Pumpen- und Relaismodul</td><td><span class="stand geprueft">an der Anlage geprüft</span></td></tr>
            <tr><td>Infinity PLUS Heizkreis und Warmwasser</td><td><span class="stand offen">eingebunden, ungeprüft</span></td></tr>
            <tr><td>Solar, Kaskade, Umschaltung, weitere Puffer</td><td><span class="stand offen">eingebunden, ungeprüft</span></td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <p class="nachsatz">
      „Eingebunden“ heißt: Die Funktion steht mit Namen, Einheiten und Auswahlwerten
      in der mitgelieferten Datenbank und wird erkannt — es stand nur noch keine
      solche Anlage zum Nachmessen bereit. „An einer fremden Anlage geprüft“ heißt:
      Jemand hat einen Abzug beigesteuert, das Auslesen ist daran belegt, das
      Bedienen noch nicht.
    </p>
    <p class="nachsatz">
      Was hier nicht steht, fällt trotzdem nicht durch: Die allgemeine Erkennung
      nimmt jeden Datenpunkt mit, den die Steuerung führt. Welcher Funktionstyp was
      ist, steht vollständig unter <a href="ANLEITUNG#datenpunkte">Datenpunkte</a>.
    </p>

    <div class="hinweis">
      Unsicher, ob deine Anlage mitspielt? Leg in den
      <a href="https://github.com/xIceTea/HeatNexus/discussions">Diskussionen</a> einen
      Beitrag an und schreib dazu, welches Gerät du hast. Es gibt ein Sondenwerkzeug, das
      deine Anlage ausliest, ohne etwas zu verändern — eine einzelne Python-Datei,
      die nichts an der Anlage verändert und im Betrieb nicht mitläuft.
    </div>
  </div>
</section>

<section id="installation" markdown="0">
  <div class="huelle">
    <div class="kopfzeile">
      <p class="marke-zeile">Installation</p>
      <h2>Vier Schritte, <em>einmal</em></h2>
    </div>
    <ol class="schritte">
      <li>
        <span class="nr">01</span>
        <h3>HACS öffnen</h3>
        <p>HeatNexus als eigenes Repository hinzufügen (Kategorie <em>Integration</em>), oder gleich über den Knopf oben.</p>
      </li>
      <li>
        <span class="nr">02</span>
        <h3>Herunterladen</h3>
        <p>Herunterladen und Home Assistant neu starten.</p>
      </li>
      <li>
        <span class="nr">03</span>
        <h3>Einrichten</h3>
        <p>Unter <em>Einstellungen → Geräte &amp; Dienste → Integration hinzufügen → HeatNexus</em>. Gebraucht werden die IP der Steuerung und das Service-Passwort; der Benutzer heißt immer <code>USER</code>.</p>
      </li>
      <li>
        <span class="nr">04</span>
        <h3>Warten</h3>
        <p>Der erste Durchlauf liest die ganze Anlage ein. Danach stehen Geräte, Entitäten, Oberfläche und Dashboard bereit.</p>
      </li>
    </ol>
    <p class="nachsatz">
      Ohne HACS geht es auch: Ordner <code>custom_components/heatnexus/</code> aus dem
      <a href="https://github.com/xIceTea/HeatNexus/releases/latest">Release</a> in den
      Konfigurationsordner von Home Assistant kopieren und neu starten.
    </p>
  </div>
</section>

<section id="weiterlesen" markdown="0">
  <div class="huelle">
    <div class="kopfzeile">
      <p class="marke-zeile">Weiterlesen</p>
      <h2>Die Anleitungen</h2>
    </div>
    <div class="gitter drei">
      <a class="feld" href="ANLEITUNG#einrichtung">
        <h3>Einrichtung</h3>
        <p>Bedienebenen, Abfrageintervall, mehrere Anlagen und was jeder Schalter bewirkt.</p>
      </a>
      <a class="feld" href="ANLEITUNG#fehlersuche">
        <h3>Fehlersuche</h3>
        <p>Die Fälle, die immer wiederkehren — nach Symptom sortiert.</p>
      </a>
      <a class="feld" href="ANLEITUNG#vorlagen">
        <h3>Vorlagen und Dienste</h3>
        <p>Sechs Automations-Vorlagen und sechs Dienste, mit Beispielaufruf.</p>
      </a>
      <a class="feld" href="ANLEITUNG#oberflaeche">
        <h3>Die eigene Oberfläche</h3>
        <p>Jeder Reiter, was er zeigt und was sich bedienen lässt.</p>
      </a>
      <a class="feld" href="ANLEITUNG#karte">
        <h3>Das Anlagenschaubild als Karte</h3>
        <p>Einrichtung und alle Einstellungen.</p>
      </a>
      <a class="feld" href="ANLEITUNG#datenpunkte">
        <h3>Datenpunkte</h3>
        <p>Welche Werte es je Anlagenteil gibt.</p>
      </a>
      <a class="feld" href="ANLEITUNG#aufzaehlungen">
        <h3>Auswahlwerte</h3>
        <p>Was hinter den Zustandstexten steckt.</p>
      </a>
      <a class="feld" href="ANLEITUNG#aufbau">
        <h3>Aufbau</h3>
        <p>Wie die Integration innen arbeitet.</p>
      </a>
      <a class="feld" href="ANLEITUNG#geraeteschnittstelle">
        <h3>Geräteschnittstelle</h3>
        <p>Die HTTP-Schnittstelle der Steuerung.</p>
      </a>
    </div>
    <p class="nachsatz">
      Fragen, Wünsche und Fehlermeldungen gehören in die
      <a href="https://github.com/xIceTea/HeatNexus/discussions">Diskussionen</a> oder die
      <a href="https://github.com/xIceTea/HeatNexus/issues">Issues</a>.
    </p>

    <a class="weiterlesen" href="ANLEITUNG#einrichtung">
      <span class="weiterlesen-text">Weiter zur Anleitung</span>
      <span class="weiterlesen-unter">Von der Einrichtung bis zum Aufbau — durchgehend auf einer Seite</span>
      <span class="weiterlesen-pfeil" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 5v14M6 13l6 6 6-6"/>
        </svg>
      </span>
    </a>
  </div>
</section>
