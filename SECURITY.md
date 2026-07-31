# Sicherheit

## Sicherheitslücken melden

Sicherheitsrelevante Funde bitte **nicht** als öffentliches Issue anlegen,
sondern über die Sicherheitsmeldung des Repositories
(Security → Report a vulnerability).

## Was diese Integration tut

- Sie spricht ausschließlich die Heizungsanlage im lokalen Netz an
  (HTTP, Digest-Authentifizierung). Es gibt keine Cloud-Verbindung und keine
  Telemetrie.
- Das Service-Passwort wird im Konfigurationseintrag von Home Assistant
  gespeichert und nur für Anfragen an die Anlage verwendet.
- Parameter der Service- und Werksebene sind standardmäßig nur lesbar. Sie
  lassen sich in den Optionen freischalten – falsch gesetzte Werte können den
  Betrieb der Anlage beeinträchtigen.

## Hinweise für Anlagenbetreiber

- Die Geräte-API kennt kein HTTPS. Die Anlage gehört deshalb nicht direkt ins
  Internet, sondern hinter Router bzw. VPN.
- Diagnosedateien aus `tools/heatnexus_probe.py` enthalten IP-Adressen und
  Anlagenwerte. Vor dem Teilen prüfen.
