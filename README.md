# Gmailify - Home Assistant Add-on

Google stellt seine Gmailify-Funktion ein. Dieses Add-on ist der Ersatz: Es uebertraegt Emails von GMX per IMAP IDLE **sekundenaktuell** nach Gmail -- mit vollstaendigen Original-Headern, Anhang und korrektem Absender.

## So funktioniert's

Das Add-on haelt eine permanente IMAP-Verbindung zu GMX offen. Sobald eine neue Mail im GMX-Postfach eintrifft, wird sie innerhalb von Sekunden per Gmail API (`messages.import()`) in Gmail eingefuegt. Keine Weiterleitung, keine veraenderten Header -- die Mail erscheint in Gmail exakt so, wie sie bei GMX angekommen ist.

## Features

- **Sekundenaktueller Sync**: IMAP IDLE auf dem GMX-Posteingang -- neue Mails sind in Sekunden in Gmail
- **Native Gmail-Ordner**: Posteingang landet im Gmail-Posteingang, Gesendet bei Gesendet, Entwuerfe bei Entwuerfe etc.
- **Periodischer Sync**: Weitere Ordner (Gesendet, Entwuerfe, eigene Ordner) werden alle N Minuten abgeglichen
- **Original-Header**: Absender, Datum, Message-ID, Anhang -- alles bleibt erhalten
- **Dreifache Deduplizierung**: Lokale DB (UIDs + Message-ID) + Gmail-API-Abfrage -- keine doppelten Mails, auch nicht nach Neustart
- **Ungelesen-Status**: Importierte Mails erscheinen als ungelesen in Gmail
- **Full-Sync**: Historische Mails auf Knopfdruck nachladen (unterbrechbar, setzt nach Neustart fort)
- **Web-Dashboard**: Status, Statistiken und Gmail-Autorisierung ueber die HA-Oberflaeche
- **Auto-Reconnect**: Verbindungsabbrueche werden automatisch behandelt

## Gmail-Ordner-Zuordnung

| GMX-Ordner | Gmail-Ordner |
|---|---|
| INBOX | Posteingang |
| Gesendet | Gesendet |
| Entwuerfe | Entwuerfe |
| Spam | Spam |
| Papierkorb | Papierkorb |
| Eigene Ordner | GMX/Ordnername |

## Installation

Siehe [DOCS.md](gmailify/DOCS.md) fuer die vollstaendige Setup-Anleitung.

[![Open your Home Assistant instance and show the add add-on repository dialog](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FMarkusReuter%2Fha-gmailify)

## Kurzanleitung

1. GMX: IMAP-Zugang aktivieren
2. Google Cloud Console: Projekt erstellen, Gmail API aktivieren, OAuth2 Client ID (Desktop) anlegen
3. Add-on installieren, GMX- und Google-Credentials eintragen
4. Add-on starten, Web-UI oeffnen, Gmail autorisieren
5. Fertig -- neue Mails werden ab sofort sekundenaktuell uebertragen
