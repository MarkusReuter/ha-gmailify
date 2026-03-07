# CLAUDE.md

## Release Process

**MANDATORY:** Every code change must include:
1. Version bump in `gmailify/config.yaml` (semver: patch for fixes, minor for features, major for breaking changes)
2. Release notes entry in `gmailify/CHANGELOG.md` (follow existing format: ## version, ### category, - description)

## Project Structure

- `gmailify/rootfs/app/` - Python application code
  - `main.py` - Entry point, wires up components
  - `sync_engine.py` - Core sync orchestration (IDLE + periodic sync)
  - `gmail_client.py` - Gmail API client (import, dedup, labels)
  - `gmx_client.py` - IMAP client for GMX (aioimaplib)
  - `sync_state.py` - SQLite state tracking
  - `config.py` - Configuration loading
  - `folder_mapping.py` - GMX folder to Gmail label mapping
  - `web/server.py` - aiohttp web UI (OAuth flow, dashboard, full sync trigger)
- `gmailify/config.yaml` - Home Assistant addon metadata (version lives here)
- `gmailify/CHANGELOG.md` - Release notes

## Tech Stack

- Python 3.12, asyncio, aioimaplib (IMAP IDLE), Google API Python Client (Gmail)
- aiohttp + Jinja2 for web UI
- SQLite (aiosqlite) for sync state
- Runs as Home Assistant addon in Docker
