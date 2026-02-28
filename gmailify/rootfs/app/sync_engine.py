"""Core sync engine - orchestrates GMX to Gmail sync."""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import Config
from folder_mapping import get_gmail_label, resolve_folder_name
from gmail_client import GmailClient
from gmx_client import GmxClient, RECONNECT_DELAYS
from sync_state import SyncState

logger = logging.getLogger(__name__)

BATCH_SIZE = 25


@dataclass
class SyncStats:
    folders_processed: int = 0
    messages_fetched: int = 0
    messages_imported: int = 0
    messages_skipped: int = 0
    errors: int = 0
    last_sync: str = ""
    is_running: bool = False
    gmx_connected: bool = False
    full_sync_running: bool = False
    last_errors: list[str] = field(default_factory=list)

    def record_error(self, msg: str) -> None:
        self.errors += 1
        self.last_errors.append(f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}")
        if len(self.last_errors) > 20:
            self.last_errors = self.last_errors[-20:]


class SyncEngine:
    def __init__(
        self,
        gmx: GmxClient,
        gmail: GmailClient,
        state: SyncState,
        config: Config,
    ):
        self._gmx = gmx
        self._gmail = gmail
        self._state = state
        self._config = config
        self._stop_event = asyncio.Event()
        self._new_mail_event = asyncio.Event()
        self.stats = SyncStats()
        self._initialized = False

    async def run(self) -> None:
        """Main entry point: runs IDLE on INBOX + periodic sync for other folders."""
        self.stats.is_running = True
        reconnect_attempt = 0

        while not self._stop_event.is_set():
            try:
                await self._gmx.connect()
                self.stats.gmx_connected = True
                reconnect_attempt = 0

                # On first connect, mark existing messages as seen
                if not self._initialized:
                    await self._initialize_folders()
                    self._initialized = True

                # Run IDLE and periodic sync in parallel
                await asyncio.gather(
                    self._idle_inbox(),
                    self._periodic_sync(),
                )
            except Exception as e:
                self.stats.gmx_connected = False
                self.stats.record_error(f"Connection error: {e}")
                logger.error("Connection error: %s", e)

                try:
                    await self._gmx.disconnect()
                except Exception:
                    pass

                if self._stop_event.is_set():
                    break

                # Exponential backoff reconnect
                delay = RECONNECT_DELAYS[min(reconnect_attempt, len(RECONNECT_DELAYS) - 1)]
                logger.info("Reconnecting in %d seconds...", delay)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                    break  # stop_event was set
                except asyncio.TimeoutError:
                    pass
                reconnect_attempt += 1

        self.stats.is_running = False
        await self._gmx.disconnect()

    async def stop(self) -> None:
        """Signal the engine to stop."""
        self._stop_event.set()
        self._new_mail_event.set()

    async def trigger_full_sync(self) -> None:
        """Trigger a full sync of all folders (imports all historical messages)."""
        if self.stats.full_sync_running:
            logger.warning("Full sync already in progress")
            return

        self.stats.full_sync_running = True
        logger.info("Starting full sync...")

        try:
            for folder_name in self._config.folders:
                imap_folder = resolve_folder_name(folder_name)
                await self._state.reset_folder(imap_folder)

            await self._sync_all_folders()
        except Exception as e:
            self.stats.record_error(f"Full sync error: {e}")
            logger.error("Full sync error: %s", e)
        finally:
            self.stats.full_sync_running = False
            logger.info("Full sync completed")

    async def _initialize_folders(self) -> None:
        """On first start, mark all existing UIDs as seen."""
        for folder_name in self._config.folders:
            imap_folder = resolve_folder_name(folder_name)

            # Check if we already have state for this folder
            stored = await self._state.get_uidvalidity(imap_folder)
            if stored is not None:
                logger.info("Folder %s already initialized, skipping", imap_folder)
                continue

            try:
                uidvalidity, uids = await self._gmx.fetch_uids(imap_folder)
                await self._state.mark_all_as_seen(imap_folder, uidvalidity, uids)
                logger.info(
                    "Initialized %s: marked %d existing messages as seen",
                    imap_folder, len(uids),
                )
            except Exception as e:
                self.stats.record_error(f"Init {imap_folder} failed: {e}")
                logger.error("Failed to initialize folder %s: %s", imap_folder, e)

    async def _idle_inbox(self) -> None:
        """Run IMAP IDLE on INBOX for real-time notifications."""
        inbox_folder = resolve_folder_name("INBOX")
        if inbox_folder not in [resolve_folder_name(f) for f in self._config.folders]:
            logger.info("INBOX not in configured folders, skipping IDLE")
            return

        while not self._stop_event.is_set():
            try:
                logger.info("Starting IDLE on %s", inbox_folder)
                await self._gmx.idle_loop(
                    folder=inbox_folder,
                    on_new_mail=self._new_mail_event,
                    stop_event=self._stop_event,
                )
            except Exception as e:
                if self._stop_event.is_set():
                    break
                logger.error("IDLE error: %s", e)
                raise  # Will be caught by run() for reconnect

    async def _periodic_sync(self) -> None:
        """Periodically sync all configured folders."""
        interval = self._config.sync_interval_minutes * 60

        while not self._stop_event.is_set():
            # Wait for either new mail event or interval timeout
            try:
                await asyncio.wait_for(
                    self._new_mail_event.wait(),
                    timeout=interval,
                )
                self._new_mail_event.clear()
                logger.info("New mail event received, syncing...")
            except asyncio.TimeoutError:
                logger.debug("Periodic sync interval reached")

            if self._stop_event.is_set():
                break

            await self._sync_all_folders()

    async def _sync_all_folders(self) -> None:
        """Sync all configured folders."""
        for folder_name in self._config.folders:
            if self._stop_event.is_set():
                break
            imap_folder = resolve_folder_name(folder_name)
            try:
                await self._sync_folder(imap_folder)
                self.stats.folders_processed += 1
            except Exception as e:
                self.stats.record_error(f"Sync {imap_folder}: {e}")
                logger.error("Error syncing folder %s: %s", imap_folder, e)

        self.stats.last_sync = datetime.now(timezone.utc).isoformat()

    async def _sync_folder(self, folder: str) -> None:
        """Sync a single folder: fetch new UIDs, import into Gmail."""
        uidvalidity, all_uids = await self._gmx.fetch_uids(folder)
        unsynced = await self._state.get_unsynced_uids(folder, uidvalidity, all_uids)

        if not unsynced:
            logger.debug("No new messages in %s", folder)
            return

        logger.info("Found %d new messages in %s", len(unsynced), folder)

        gmail_label = get_gmail_label(folder)
        label_id = self._gmail.ensure_label(gmail_label)

        # Process in batches
        for i in range(0, len(unsynced), BATCH_SIZE):
            if self._stop_event.is_set():
                break

            batch = unsynced[i : i + BATCH_SIZE]
            emails = await self._gmx.fetch_raw_emails(folder, batch, uidvalidity)
            self.stats.messages_fetched += len(emails)

            for raw_email in emails:
                await self._import_single(raw_email, label_id)

    async def _import_single(self, raw_email, label_id: str) -> None:
        """Import a single email with error handling."""
        try:
            # Message-ID dedup check
            if await self._state.is_message_id_synced(raw_email.message_id):
                self.stats.messages_skipped += 1
                logger.debug(
                    "Skipping UID %d (Message-ID already synced)", raw_email.uid
                )
                return

            gmail_id = self._gmail.import_message(raw_email.data, [label_id])
            await self._state.mark_synced(
                folder=raw_email.folder,
                uid=raw_email.uid,
                uidvalidity=raw_email.uidvalidity,
                message_id=raw_email.message_id,
                gmail_id=gmail_id,
            )
            self.stats.messages_imported += 1
            logger.info(
                "Imported UID %d from %s -> Gmail %s",
                raw_email.uid, raw_email.folder, gmail_id,
            )
        except Exception as e:
            self.stats.record_error(
                f"Import UID {raw_email.uid} from {raw_email.folder}: {e}"
            )
            logger.error(
                "Failed to import UID %d from %s: %s",
                raw_email.uid, raw_email.folder, e,
            )
