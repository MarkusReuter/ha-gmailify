#!/usr/bin/with-contenv bashio

bashio::log.info "=== Gmailify Home Assistant Addon v1.0.0 ==="

# Verzeichnisse erstellen
mkdir -p /data/db /data/logs
chown -R root:root /data

# Config aus HA Options lesen
GMX_EMAIL=$(bashio::config 'gmx_email')
GMX_PASSWORD=$(bashio::config 'gmx_password')
GOOGLE_CLIENT_ID=$(bashio::config 'google_client_id')
GOOGLE_CLIENT_SECRET=$(bashio::config 'google_client_secret')
SYNC_INTERVAL=$(bashio::config 'sync_interval_minutes' '15')

# Folders als JSON-Array lesen
FOLDERS_JSON="["
FOLDER_COUNT=$(bashio::config 'folders | length')
for (( i=0; i<FOLDER_COUNT; i++ )); do
    FOLDER=$(bashio::config "folders[${i}]")
    if [ "$i" -gt 0 ]; then
        FOLDERS_JSON="${FOLDERS_JSON},"
    fi
    FOLDERS_JSON="${FOLDERS_JSON}\"${FOLDER}\""
done
FOLDERS_JSON="${FOLDERS_JSON}]"

# Config als JSON für Python schreiben
cat > /data/config.json << EOF
{
  "gmx_email": "${GMX_EMAIL}",
  "gmx_password": "${GMX_PASSWORD}",
  "google_client_id": "${GOOGLE_CLIENT_ID}",
  "google_client_secret": "${GOOGLE_CLIENT_SECRET}",
  "sync_interval_minutes": ${SYNC_INTERVAL},
  "folders": ${FOLDERS_JSON}
}
EOF

bashio::log.info "Configuration loaded for ${GMX_EMAIL}"
bashio::log.info "Syncing folders: ${FOLDERS_JSON}"
bashio::log.info "Sync interval: ${SYNC_INTERVAL} minutes"
bashio::log.info "Starting Gmailify sync service..."

# Python starten
cd /app
exec python3 -m main
