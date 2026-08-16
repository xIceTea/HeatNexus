---
titel: Anleitung
beschreibung: Einrichtung, Bedienung, Fehlersuche und Referenz von HeatNexus — alles auf einer Seite.
anleitung: true
---

{% comment %}
Alle Anleitungen stehen auf einer Seite, damit man von oben nach unten
durchlesen kann. Die Quelltexte liegen einzeln unter `_includes/`, bleiben
so im Repo lesbar und werden hier nur zusammengesetzt.
{% endcomment %}

<section id="einrichtung" class="teil" markdown="1">
{% include EINRICHTUNG.md %}
</section>

<section id="fehlersuche" class="teil" markdown="1">
{% include FEHLERSUCHE.md %}
</section>

<section id="oberflaeche" class="teil" markdown="1">
{% include OBERFLAECHE.md %}
</section>

<section id="karte" class="teil" markdown="1">
{% include KARTE.md %}
</section>

<section id="vorlagen" class="teil" markdown="1">
{% include VORLAGEN.md %}
</section>

<section id="datenpunkte" class="teil gross" markdown="1">
{% include DATAPOINTS.md %}
</section>

<section id="aufzaehlungen" class="teil gross" markdown="1">
{% include ENUMS.md %}
</section>

<section id="geraeteschnittstelle" class="teil" markdown="1">
{% include API.md %}
</section>

<section id="aufbau" class="teil" markdown="1">
{% include ARCHITECTURE.md %}
</section>
