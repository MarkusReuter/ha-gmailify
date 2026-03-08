# Changelog

## 1.1.10

### Fixed
- Cancel zombie `_periodic_sync` tasks on IDLE reconnect: `asyncio.gather` didn't cancel the surviving task when one failed, causing duplicate sync loops that multiplied with each reconnect

## 1.1.9

### Fixed
- IDLE reconnects after GMX `BYE timeout`: `idle_start()` now has a 30s timeout guard so a dead connection triggers a reconnect instead of hanging forever

## 1.1.8

### Fixed
- Fix IDLE timeout race condition: `idle_start` and `asyncio.wait` both had the same 5-minute timeout, causing double DONE commands that corrupted IMAP protocol state and silently stopped IDLE notifications
- Periodic sync loop now survives errors (RefreshError, network issues) instead of crashing permanently, which would cause IDLE notifications to stop being processed

## 1.1.7

### Fixed
- Dashboard now shows actual Gmail API status instead of always "Autorisiert" — displays "Token abgelaufen" with re-auth link when credentials are invalid
- Sync engine detects expired Gmail tokens (`RefreshError`) and stops the sync cycle immediately instead of failing on every message individually

## 1.1.6

### Fixed
- Gmail OAuth credentials are now hot-reloaded after re-authentication — no addon restart required when the token expires

## 1.1.5

### Fixed
- IDLE now detects dead GMX connections: `asyncio.wait` has a timeout so hung connections are caught and IDLE is re-issued instead of blocking forever
- Layer 1 dedup now marks UIDs as synced when the Message-ID already exists in the local DB, preventing the same messages from reappearing as "new" every sync cycle

## 1.1.4

### Changed
- Fetch connection is now opened per sync cycle and closed afterward instead of kept idle. Eliminates GMX `BYE timeout` every 15 minutes and "Task was destroyed but it is pending" warnings.

## 1.1.3

### Fixed
- Proactive NOOP health check before each sync cycle prevents GMX idle-timeout (`BYE timeout`) from skipping the first folder

## 1.1.2

### Fixed
- Prevent concurrent syncs (IDLE-triggered + full sync) from sharing the same IMAP connection, which caused aioimaplib Abort errors

## 1.1.1

### Fixed
- Auto-reconnect IMAP fetch connection after folder sync errors (aioimaplib Abort/timeout no longer kills the entire sync cycle)

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
