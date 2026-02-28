# Changelog

## 1.1.0

### Breaking Changes
- **Folder mapping changed:** GMX folders now map to native Gmail folders instead of custom `GMX/*` labels. INBOX→Inbox, Gesendet→Sent, Entwürfe→Drafts, Spam→Spam, Papierkorb→Trash. Previously imported mails under `GMX/*` labels are not moved automatically.

### New
- Imported emails are now marked as **unread** in Gmail
- Unknown/unmapped GMX folders still get custom `GMX/<name>` labels as fallback

### Fixed
- From header with comma in display name (e.g. `"Reuter, Markus"`) no longer gets corrupted
- Non-ASCII email content no longer causes UnicodeEncodeError during import

## 1.0.0

- Initial release
- IMAP IDLE for real-time inbox sync
- Periodic sync for other folders
- Gmail API import with original headers
- GMX folder to Gmail label mapping
- OAuth2 setup via web UI
- Status dashboard with sync stats
- Full-sync button for historical mail import
