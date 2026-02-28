# Gmailify - Home Assistant Add-on

Synchronisiert Emails von GMX nach Gmail ueber IMAP IDLE mit Original-Mailheadern.

## Features

- **Echtzeit-Sync**: IMAP IDLE auf der GMX-Inbox fuer sofortige Mail-Zustellung
- **Periodischer Sync**: Regelmaessiger Abgleich weiterer Ordner (Gesendet, Entwuerfe, etc.)
- **Original-Header**: Verwendet Gmail API `messages.import()` - keine Header-Veraenderung
- **GMX-Label-Mapping**: Mails erscheinen unter GMX/Inbox, GMX/Sent etc. in Gmail
- **Deduplizierung**: Keine doppelten Mails durch UID + Message-ID Tracking
- **Web-Dashboard**: Status, Statistiken und Gmail-Autorisierung ueber die HA-Oberflaeche
- **Full-Sync**: Historische Mails auf Knopfdruck nachladen

## Installation

Siehe [DOCS.md](gmailify/DOCS.md) fuer die vollstaendige Setup-Anleitung.

[![Open your Home Assistant instance and show the add add-on repository dialog](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FMarkusReuter%2Fha-gmailify)
