# Regelung

Warum wird der Kessel auf 76 °C geheizt, wenn für den Puffer 60 °C eingestellt
sind? Warum bleibt die Pufferladung aus, obwohl unten nur 40 °C gemessen werden?

Die Anlage zeigt viele Temperaturen, aber nicht, wie sie zusammenhängen.
Dahinter stehen wenige Rechenregeln. Dieser Abschnitt erklärt sie und zeigt,
welche Einstellung was bewirkt.

Alle genannten Zahlen sind Werkseinstellungen. Was an einer Anlage wirklich
eingestellt ist, führt HeatNexus als Entität; die Adresse steht jeweils dabei.

## Der Sollwert wird aus dem Bedarf berechnet

Für den Pufferspeicher ist keine feste Temperatur eingestellt. Die Regelung
berechnet seinen Sollwert aus dem, was gerade gebraucht wird — meist aus dem
Warmwasserkreis oder einem Heizkreis. Auf diesen Bedarf kommen zwei Aufschläge:

```
Warmwasser-Sollwert                50 °C
+ WW-Überhöhung        16/5/1     +10 K
= Puffer-Sollwert      16/1/15     60 °C

+ Hysterese            16/9/35     +16 K
= Kessel-Sollwert      14/1/7      76 °C
```

Der erste Aufschlag hält den Puffer wärmer als das Warmwasser. Ohne ihn ließe
sich der Boiler nicht aufheizen. Der zweite hebt die Kesseltemperatur darüber
hinaus an, damit nicht bei jeder kleinen Abweichung nachgeheizt werden muss.

**Ohne Bedarf beträgt der Puffer-Sollwert 0.** Dann findet keine Ladung statt,
unabhängig von der Speichertemperatur. Das ist der häufigste Grund für die
Frage, warum die Anlage nicht anspringt.

## Wann geladen wird

Die Ladung beginnt nicht beim Sollwert, sondern eine halbe Hysterese darunter:

```
Puffer-Sollwert  60 °C
− Hysterese/2    − 8 K
= Einschaltpunkt 52 °C   am oberen Fühler (TPE)
```

Sinkt der obere Fühler unter diesen Wert, wird Wärme angefordert. Der untere
Fühler (TPA) hat auf den Beginn der Ladung keinen Einfluss.

HeatNexus legt beide Größen als eigene Werte an: **Einschaltpunkt** ist die
Temperatur aus der Rechnung oben, **Einschaltpunkt Delta** der Abstand des
Fühlers dahin in Kelvin. Das Delta ist der Wert, auf den sich eine Automation
setzen lässt: „in zwei Kelvin fordert die Anlage an".

## Wann die Ladung endet

Sobald der Bedarf gedeckt ist. Nicht, wenn der Puffer voll ist.

Erreicht das Warmwasser seine Solltemperatur, sinkt der Puffer-Sollwert auf 0
und die Ladung endet. Im unteren Speicherbereich kann es dann noch kalt sein.

Für die Nutzung als Wärmevorrat ist das der entscheidende Punkt: **Im
Automatikbetrieb wird der Puffer nie durchgeladen.** Maßgeblich ist der Bedarf
des Augenblicks, ein Vorratsziel gibt es nicht.

## Wann der Brenner startet

Der Brenner startet, sobald die Kesseltemperatur unter den Sollwert minus
Hysterese sinkt:

```
Kessel-Sollwert            76 °C
+ Hysterese Brenner EIN    − 5 K     Adresse 9/21, negativ angegeben
= Brenner startet bei      71 °C
```

Zwei Werte begrenzen das Ergebnis nach oben:

| Adresse | Bedeutung | ab Werk |
|---|---|---|
| `12/39` | Maximalwert der Solltemperatur | 80 °C |
| `9/57` | Solltemperatur bei externer Wärmeanforderung | 80 °C |

`12/39` ist eine harte Obergrenze. Liegt sie unter dem berechneten Sollwert,
wird gekappt. Eine höhere Überhöhung oder Hysterese bleibt dann wirkungslos.

## Was welche Einstellung bewirkt

| Einstellung | Wirkung |
|---|---|
| **WW-Überhöhung** `16/5/1` | Bei gleichem Warmwasserbedarf steigt der Puffer-Sollwert. Wirkt nur bei Warmwasser-Anforderung. |
| **Hysterese** `16/9/35` | Ein größerer Wert erhöht die Kesseltemperatur und verzögert den Beginn der Ladung. Beides zugleich, denn die Hysterese wirkt nach oben und nach unten. |
| **Puffer Minimaltemperatur** `16/9/32` | Untergrenze für den Speicher. |
| **Puffer Maximaltemperatur** `16/10/31` | Obergrenze für den Speicher. |
| **Betriebswahl** `16/20/15` | Bestimmt, ob der Bedarf oder das Zeitprogramm den Sollwert liefert. |
| **Minimale Laufzeit** `16/20/28` | Eine begonnene Ladung läuft mindestens so lange weiter, auch wenn der Bedarf vorher entfällt. |

## Die Betriebswahl entscheidet über alles

Am Pufferspeicher steht eine Auswahl, die leicht übersehen wird:

| Wert | Bedeutung | Wirkung |
|---|---|---|
| 0 | Standby | keine Anforderung, der Speicher bleibt kalt |
| 1 | Automatikbetrieb | der Bedarf bestimmt den Sollwert, das Zeitprogramm wirkt **nicht** |
| 2 | Festbrennstoffbetrieb | für Handbeschickung |
| 3 | Pufferbetrieb | |
| 4 | **Auto mit Zeitprogramm** | das Zeitprogramm des Puffers bestimmt den Sollwert |
| 6 | Handbetrieb | |
| 7 | Kaminkehrerfunktion | |

Bei `1` bleibt das Zeitprogramm des Puffers ohne Wirkung. Einstellen lässt es
sich, ausgewertet wird es nicht. Erst bei `4` bestimmt es den Sollwert, und zwar
unabhängig vom aktuellen Bedarf.

---

## Anwendungsfälle

### Puffer gezielt durchladen

Zum Beispiel abends, wenn für den nächsten Tag wenig Sonne gemeldet ist und von
der Solaranlage kein Beitrag zu erwarten ist.

1. Betriebswahl `16/20/15` auf **4 — Auto mit Zeitprogramm** setzen
2. Im Zeitprogramm des Puffers die gewünschte Temperatur eintragen, über den
   Dienst `heatnexus.set_time_program`
3. Am nächsten Morgen zurück auf **1 — Automatikbetrieb**

Damit richtet sich die Ladung nach dem Plan statt nach dem Bedarf. Für eine
Automation, die eine Solarprognose auswertet und die Betriebswahl umstellt,
genügt ein einziger Schreibvorgang.

### Anforderung unterbinden

Betriebswahl auf **0 — Standby** setzen. Danach wird keine Wärme mehr
angefordert.

Damit entfällt allerdings auch die Notversorgung. Um lediglich die Ladung zu
begrenzen, eignen sich die WW-Überhöhung oder die Maximaltemperatur besser.

### Warmwasser wärmer, ohne den Puffer stärker zu heizen

Getrennt geht das nicht. Der Puffer-Sollwert wird aus dem Warmwasser-Bedarf
berechnet und steigt bei gleichbleibender Überhöhung mit. Für einen wärmeren
Boiler bei gleicher Puffertemperatur muss die Überhöhung im selben Zug gesenkt
werden.

### Wärme von Hand anfordern

Einen Datenpunkt „jetzt anfordern" gibt es nicht. Ein Eingriff läuft über die
Bedingungen, unter denen die Regelung selbst anfordert:

| Ziel | Weg |
|---|---|
| jetzt laden | Betriebswahl auf `4`, dazu ein Zeitprogramm mit hoher Temperatur |
| nie laden | Betriebswahl auf `0` |
| tiefer laden | Puffer Minimaltemperatur anheben |
| heißer liefern | Solltemperatur ext. Wärmeanforderung anheben, an der liefernden Seite |

---

## Zwei Anlagen im Verbund

Steht der Kessel im Nebengebäude und versorgt beide Häuser, arbeiten zwei
Regelkreise zusammen. Die Verständigung läuft über ein Pumpen- und Relaismodul,
bei Windhager ZSP genannt.

**Auf der anfordernden Seite** schaltet der Brenner-Ausgang `16/1/100`, sobald
die Puffertemperatur unter die Schaltschwelle sinkt. Das ist ein Relais und kein
Messwert; in HeatNexus erscheint es als Ja/Nein-Sensor.

**Auf der liefernden Seite** nimmt das ZSP die Anforderung an. Die
Kesseltemperatur wird daraus mit der **vollen** Hysterese berechnet:

```
Solltemperatur ext. Wärmeanforderung   16/9/57    60 °C
+ Hysterese                            16/9/35   +16 K
= Analog-Sollwert am ZSP               20/0/95    76 °C
```

Beide Seiten rechnen also unterschiedlich. Auf der anfordernden Seite beginnt
die Ladung bei Sollwert minus **halber** Hysterese, auf der liefernden gilt
Sollwert plus **voller** Hysterese.

Dazwischen liegt eine dritte Stufe, die leicht übersehen wird: Die Anforderung
wird zuerst aus dem Vorrat des liefernden Puffers gedeckt. Erst wenn dessen
oberer Fühler unter Sollwert minus halbe Hysterese sinkt, wird der Kessel
angefordert.

Die vollständige Kette hat damit vier Stufen:

```
Verbraucher meldet Bedarf
  → anfordernder Puffer schaltet seinen Brenner-Ausgang
    → ZSP überträgt den Sollwert
      → liefernder Puffer fordert den Kessel an
        → Brenner startet
```

---

## Das Pumpen- und Relaismodul

Ein ZSP ist ein Schaltgerät ohne feste Aufgabe. Vier Ja/Nein-Schalter legen
fest, was es tut, und sie schließen einander nicht aus:

| Adresse | Rolle |
|---|---|
| `29/0` | Sammelalarm |
| `29/1` | Pumpensteuerung, regelt eine Pumpe über die Drehzahl |
| `29/2` | Ext. Wärmeanforderung, nimmt eine Anforderung von außen an |
| `29/3` | Relaisfunktion, schaltet einen Kontakt |

HeatNexus wertet diese Schalter aus. Steht `29/1` auf Nein, erscheinen
Pumpendrehzahl und Kesseltemperatur des Moduls gar nicht erst. Diese
Abhängigkeit steht in den Herstellerunterlagen und wird beim Einlesen
ausgewertet. Was an einer Anlage keine Aufgabe hat, wird also auch nicht als
Entität angelegt.

### Drei Sollwerte für drei Anforderungsarten

Steht `29/2` auf Ja, führt das Modul drei Sollwerte nebeneinander:

| Adresse | Name | gilt für |
|---|---|---|
| `9/57` | Solltemperatur ext. Wärmeanforderung | digitale Anforderung Heizung |
| `20/23` | Digital-Sollwert WWK | digitale Anforderung Warmwasser |
| `0/95` | Analog-Sollwert | stufenlose Anforderung über 0–10 V |

Welcher davon gilt, hängt an der Verdrahtung; das Modul hat getrennte Eingänge
für Heizung und Warmwasser. Im Betrieb zeigt `0/95` den gerade angeforderten
Wert und ist damit der zuverlässigste Anzeiger für eine anliegende Anforderung.

### Der Pumpenausgang

Bei aktivem `29/1` gibt das Modul eine Drehzahl aus. Eine eigene Regelgröße
liegt dabei nicht vor, deshalb läuft die Pumpe mit der eingestellten
Mindestdrehzahl `20/14`. Sie schaltet mit der Anforderung ein und aus, ohne zu
modulieren.

Zusätzlich führt das Modul einen eigenen Fühler `0/7`. Er sitzt an der
Übergabestelle und steigt, sobald gefördert wird.
