# Gmailify - Setup-Anleitung

Dieses Add-on synchronisiert Emails von GMX nach Gmail ueber IMAP IDLE (Echtzeit) und bewahrt dabei die Original-Mailheader.

## Voraussetzungen

- GMX-Konto mit aktiviertem IMAP-Zugang
- Google-Konto (Gmail)
- Google Cloud Projekt mit aktivierter Gmail API

## Schritt 1: GMX IMAP aktivieren

1. Melde dich bei [GMX](https://www.gmx.de) an
2. Gehe zu **Einstellungen** > **POP3/IMAP**
3. Aktiviere **IMAP-Zugang**
4. Speichern

## Schritt 2: Google Cloud Projekt einrichten

### 2.1 Projekt erstellen

1. Oeffne die [Google Cloud Console](https://console.cloud.google.com/)
2. Klicke oben auf das Projekt-Dropdown > **Neues Projekt**
3. Name: z.B. "Gmailify"
4. **Erstellen** klicken

### 2.2 Gmail API aktivieren

1. Im Projekt: **APIs & Dienste** > **Bibliothek**
2. Suche nach "Gmail API"
3. Klicke auf **Gmail API** > **Aktivieren**

### 2.3 OAuth2 Consent Screen einrichten

1. **APIs & Dienste** > **OAuth-Zustimmungsbildschirm**
2. Waehle **Extern** > **Erstellen**
3. App-Name: "Gmailify"
4. Support-Email: Deine Gmail-Adresse
5. Entwickler-Email: Deine Gmail-Adresse
6. **Speichern und fortfahren**
7. Bei **Bereiche (Scopes)**: Klicke **Bereiche hinzufuegen**
   - Suche nach `gmail.modify`
   - Waehle `https://www.googleapis.com/auth/gmail.modify`
   - **Aktualisieren** klicken
8. **Speichern und fortfahren**
9. Bei **Testnutzer**: Klicke **Nutzer hinzufuegen**
   - Trage deine Gmail-Adresse ein
   - **Hinzufuegen**
10. **Speichern und fortfahren** > **Zurueck zum Dashboard**

### 2.4 OAuth2 Client ID erstellen

1. **APIs & Dienste** > **Anmeldedaten**
2. **Anmeldedaten erstellen** > **OAuth-Client-ID**
3. Anwendungstyp: **Desktopanwendung**
4. Name: "Gmailify"
5. **Erstellen**
6. **Wichtig**: Notiere dir die **Client-ID** und das **Client-Secret**

## Schritt 3: Add-on installieren

### 3.1 Repository hinzufuegen

1. In Home Assistant: **Einstellungen** > **Add-ons** > **Add-on Store**
2. Oben rechts: drei Punkte > **Repositories**
3. Fuege die Repository-URL hinzu
4. **Hinzufuegen**

### 3.2 Add-on installieren und konfigurieren

1. Suche "Gmailify" im Add-on Store
2. **Installieren**
3. Gehe zum Tab **Konfiguration**
4. Trage ein:
   - **gmx_email**: Deine GMX-Emailadresse
   - **gmx_password**: Dein GMX-Passwort
   - **google_client_id**: Die Client-ID aus Schritt 2.4
   - **google_client_secret**: Das Client-Secret aus Schritt 2.4
   - **sync_interval_minutes**: Intervall fuer den Ordner-Sync (Standard: 15)
   - **folders**: Liste der zu synchronisierenden Ordner (Standard: INBOX, Gesendet)
5. **Speichern**
6. **Starten**

## Schritt 4: Gmail autorisieren

1. Klicke auf **Web-UI oeffnen** (oder den Gmailify-Eintrag in der Seitenleiste)
2. Klicke auf **Gmail verbinden**
3. Es oeffnet sich ein neuer Tab mit der Google-Anmeldung
4. Melde dich mit deinem Gmail-Konto an
5. Erlaube Gmailify den Zugriff auf Gmail
6. Du wirst zu einer Seite weitergeleitet, die nicht laden kann (`http://localhost:1/...`) - **das ist normal!**
7. Kopiere den `code`-Parameter aus der URL-Leiste:
   - URL sieht aus wie: `http://localhost:1/?code=4/0ABCD...&scope=...`
   - Kopiere den Teil nach `code=` bis zum `&`
8. Gehe zurueck zur Gmailify Web-UI
9. Fuege den Code ein und klicke **Verbinden**
10. Fertig! Die Synchronisation startet automatisch.

## Funktionsweise

### Echtzeit-Sync (INBOX)
Das Add-on haelt eine permanente IMAP IDLE-Verbindung zur GMX-Inbox offen. Sobald eine neue Mail eingeht, wird sie sofort nach Gmail importiert.

### Periodischer Sync (andere Ordner)
Alle konfigurierten Ordner (z.B. Gesendet) werden regelmaessig auf neue Mails geprueft (Standard: alle 15 Minuten).

### Labels in Gmail
Die Mails erscheinen in Gmail unter Labels:
- `GMX/Inbox` - Eingehende Mails
- `GMX/Sent` - Gesendete Mails
- `GMX/Drafts` - Entwuerfe
- etc.

### Deduplizierung
Das Add-on trackt importierte Mails per IMAP-UID und Message-ID. Doppelte Imports werden zuverlaessig verhindert, auch nach Neustart.

### Full-Sync
Beim ersten Start werden nur **neue** Mails synchronisiert. Ueber den Button "Full-Sync starten" im Dashboard koennen alle historischen Mails nachgeladen werden.

## Fehlerbehebung

### IMAP-Verbindung schlaegt fehl
- Pruefe ob IMAP bei GMX aktiviert ist
- Pruefe GMX-Email und Passwort in der Konfiguration
- GMX sperrt IMAP-Zugang bei zu vielen Fehlversuchen temporaer (30-60 Min warten)

### Gmail-Autorisierung schlaegt fehl
- Pruefe Client-ID und Client-Secret
- Stelle sicher, dass deine Gmail-Adresse als Testnutzer eingetragen ist (Schritt 2.3)
- Die Gmail API muss aktiviert sein (Schritt 2.2)

### Mails erscheinen nicht in Gmail
- Pruefe das Add-on Log (Add-on > Log Tab)
- Pruefe ob die richtigen Ordner konfiguriert sind
- Der erste Sync nach dem Start kann einen Moment dauern
