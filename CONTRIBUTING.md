# Mitwirken

Danke für das Interesse an HeatNexus.

## Entwicklungsumgebung

```bash
pip install -r requirements_test.txt
pytest
ruff check custom_components tests tools
ruff format custom_components tests
```

Die Logiktests laufen ohne Home-Assistant-Installation. Tests, die Home
Assistant benötigen, werden ohne installierte Umgebung übersprungen; die
Kopfzeile des Laufs weist darauf hin. Mit `requirements_test.txt` läuft die
gesamte Suite – auch unter Windows: `tests/conftest.py` nimmt dort die
Socket-Sperre der Home-Assistant-Testumgebung zurück, an der sonst jeder
einzelne Test schon beim Anlegen der Ereignisschleife scheitert.

## Grundsätze

- **Nichts blind schreiben.** Jeder Schreibpfad wird an einer echten Anlage
  verifiziert, bevor er als bedienbare Entität angeboten wird. Parameter der
  Service- und Werksebene sind standardmäßig nur lesbar.
- **Bestehende Entitäten bleiben stabil.** Die `unique_id` einer Entität wird
  nie geändert; Anzeigenamen und Übersetzungen dürfen sich ändern.
- **Fehlende Werte sind `None`, nie `0`.** Ein nicht gelieferter Messwert darf
  nicht wie ein gültiger aussehen.
- **Benutzeroberfläche auf Deutsch**, Code und Kommentare gemischt
  deutsch/englisch – dem umgebenden Modul folgen.

## Änderungen an der Erkennung

Nach Änderungen an `const.py`, `device_db.json` oder der Discovery muss der
gespeicherte Erkennungsstand verworfen werden – über den Dienst
`heatnexus.rediscover`. Eine höhere Version im `manifest.json` genügt **nicht**:
Sie verwirft den Stand bewusst nicht, sonst kostete jede Aktualisierung beim
Nutzer einen vollen Neuabzug.

## Anlage auslesen

```bash
python tools/heatnexus_probe.py            # geführter Modus
```

Die erzeugten Dateien enthalten Anlagendaten (IP-Adressen, Messwerte) und
gehören nicht ins Repository.

## Commits

Kurze, sachliche Betreffzeile im Imperativ. Ein Commit pro abgeschlossener
Änderung. Änderungen mit sichtbarer Wirkung bekommen einen Eintrag in
`CHANGELOG.md` (Nutzersicht, keine Implementierungsdetails).
