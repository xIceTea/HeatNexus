# Dashboards

**Für den Normalfall wird hier nichts gebraucht:** Die Integration bringt ein
fertiges Dashboard *Heizung* mit, das sich aus den erkannten Geräten aufbaut
und in der Seitenleiste erscheint.

Die Dateien hier sind für alle, die ihre Ansichten selbst bauen wollen.

| Datei | Inhalt | Einbau |
|---|---|---|
| `heizung_uebersicht.yaml` | Gesamtübersicht: Kessel, Heizkreise, Warmwasser, Puffer, Störungen | Dashboard → ⋮ → Raw-Konfigurationseditor |
| `heizung_dashboard_full.yaml` | mehrseitiges Dashboard mit Bedienelementen | Raw-Konfigurationseditor |
| `heizung_card_manual.yaml` | Bedienkarte für einen Heizkreis | Karte hinzufügen → Manuell |
| `heizung_schaubild.yaml` | Anlagenschaubild über ein eigenes Hintergrundbild | Karte hinzufügen → Manuell, Bild nach `config/www/heizung.png` |
| `heizung_dashboard.json`, `heizung_app_dashboard.json` | JSON-Varianten zum Import | – |

## Entitäten anpassen

Die Vorlagen enthalten Beispiel-Entitäten. Alle mit `# <-- anpassen` markierten
Zeilen auf die eigenen Entitäten ändern; Home Assistant hebt unbekannte
Entitäten farblich hervor.

Namensschema: `sensor.<gerät>_<datenpunkt>`, z. B.
`sensor.purowin_kesseltemperatur_ist`.
