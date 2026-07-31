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
Assistant benötigen, werden lokal übersprungen und laufen in der CI.

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
gespeicherte Erkennungsstand verworfen werden: Version im `manifest.json`
erhöhen oder den Dienst `windhager.rediscover` aufrufen.

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
