"""Async IMAP client for fetching emails from GMX with IDLE support."""
import asyncio
import email.parser
import logging
import re
import ssl
from dataclasses import dataclass

import aioimaplib

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_SECONDS = 25 * 60  # Re-issue IDLE every 25 min (before 29 min RFC limit)
RECONNECT_DELAYS = [5, 10, 30, 60, 300]  # Exponential backoff in seconds


@dataclass
class RawEmail:
    uid: int
    folder: str
    uidvalidity: int
    message_id: str
    data: bytes


class GmxClient:
    def __init__(self, host: str, port: int, email_addr: str, password: str):
        self._host = host
        self._port = port
        self._email = email_addr
        self._password = password
        self._client: aioimaplib.IMAP4_SSL | None = None
        self._connected = False
        self._selected_folder: str | None = None
        self._last_uidvalidity: int = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Establish IMAP SSL connection and login."""
        ssl_context = ssl.create_default_context()
        self._client = aioimaplib.IMAP4_SSL(
            host=self._host,
            port=self._port,
            ssl_context=ssl_context,
        )
        await self._client.wait_hello_from_server()
        response = await self._client.login(self._email, self._password)
        if response.result != "OK":
            raise ConnectionError(f"IMAP login failed: {response.lines}")
        self._connected = True
        logger.info("Connected to %s as %s", self._host, self._email)

    async def disconnect(self) -> None:
        """Logout and close connection."""
        if self._client and self._connected:
            try:
                await self._client.logout()
            except Exception:
                pass
        self._connected = False
        self._client = None
        self._selected_folder = None
        logger.info("Disconnected from %s", self._host)

    async def reconnect(self, folder: str | None = None) -> None:
        """Reconnect after connection error. Optionally re-select folder."""
        logger.info("Reconnecting to %s...", self._host)
        try:
            await self.disconnect()
        except Exception:
            pass
        await self.connect()
        if folder:
            await self.select_folder(folder, force=True)

    async def list_folders(self) -> list[str]:
        """List all IMAP folders."""
        response = await self._client.list("", "*")
        if response.result != "OK":
            raise RuntimeError(f"LIST failed: {response.lines}")

        folders = []
        for line in response.lines:
            if not line or line == "LIST completed.":
                continue
            # Parse: (\HasNoChildren) "/" "INBOX"
            # The folder name is the last quoted or unquoted string
            parts = line.rsplit('" "', 1)
            if len(parts) == 2:
                folder_name = parts[1].strip('"')
            else:
                parts = line.rsplit(" ", 1)
                folder_name = parts[-1].strip('"')
            folders.append(folder_name)

        logger.info("Found folders: %s", folders)
        return folders

    async def select_folder(self, folder: str, force: bool = False) -> int:
        """Select a folder (readonly) and return UIDVALIDITY.

        Skips SELECT if the folder is already selected (unless force=True).
        """
        if not force and self._selected_folder == folder:
            logger.debug("Folder %s already selected, skipping SELECT", folder)
            return self._last_uidvalidity

        response = await self._client.select(folder)
        if response.result != "OK":
            self._selected_folder = None
            raise RuntimeError(f"SELECT {folder} failed: {response.lines}")

        # Extract UIDVALIDITY from response
        uidvalidity = 0
        for line in response.lines:
            if "UIDVALIDITY" in str(line):
                # Parse [UIDVALIDITY 12345]
                start = str(line).find("UIDVALIDITY") + len("UIDVALIDITY ")
                end = str(line).find("]", start)
                if end == -1:
                    end = len(str(line))
                uidvalidity = int(str(line)[start:end].strip())
                break

        self._selected_folder = folder
        self._last_uidvalidity = uidvalidity
        return uidvalidity

    async def fetch_uids(self, folder: str) -> tuple[int, list[int]]:
        """Select folder and return (uidvalidity, sorted list of UIDs)."""
        uidvalidity = await self.select_folder(folder)

        response = await self._client.uid_search("ALL")
        if response.result != "OK":
            raise RuntimeError(f"UID SEARCH failed: {response.lines}")

        uids = []
        for line in response.lines:
            if line and line != "SEARCH completed.":
                uids.extend(int(x) for x in line.split() if x.isdigit())

        uids.sort()
        logger.debug("Folder %s: UIDVALIDITY=%d, %d UIDs", folder, uidvalidity, len(uids))
        return uidvalidity, uids

    @staticmethod
    def _extract_email_bytes(response_lines: list) -> bytes | None:
        """Extract raw RFC 2822 email bytes from IMAP FETCH response.

        aioimaplib may return the IMAP protocol envelope mixed into the
        bytes data (e.g. b'862 FETCH (UID 11865 RFC822 {23115}\\r\\n<email>').
        This method strips that prefix to return only the email content.
        """
        raw_data = None
        for item in response_lines:
            if isinstance(item, bytes):
                raw_data = item
                break

        if raw_data is None:
            return None

        # Strip IMAP FETCH envelope if present
        # Pattern: "NNN FETCH (UID XXXXX RFC822 {SIZE}\r\n"
        match = re.match(rb'^\d+ FETCH \([^{]*\{\d+\}\r?\n', raw_data)
        if match:
            raw_data = raw_data[match.end():]
            # Also strip trailing ")" from IMAP response if present
            if raw_data.endswith(b')\r\n'):
                raw_data = raw_data[:-3]
            elif raw_data.endswith(b')'):
                raw_data = raw_data[:-1]

        return raw_data

    async def fetch_raw_email(self, folder: str, uid: int, uidvalidity: int) -> RawEmail | None:
        """Fetch a single email as raw RFC 2822 bytes by UID."""
        response = await self._client.uid("fetch", str(uid), "(RFC822)")
        if response.result != "OK":
            logger.error("FETCH UID %d failed: %s", uid, response.lines)
            return None

        raw_data = self._extract_email_bytes(response.lines)

        if raw_data is None:
            logger.warning("No data for UID %d in %s", uid, folder)
            return None

        # Sanity check: email should start with a header, not IMAP protocol
        if raw_data[:20].startswith(b'FETCH') or re.match(rb'^\d+ FETCH', raw_data[:20]):
            logger.error("UID %d: raw data still contains IMAP envelope: %s",
                         uid, raw_data[:100])
            return None

        # Extract Message-ID from headers only (efficient)
        header_parser = email.parser.BytesHeaderParser()
        headers = header_parser.parsebytes(raw_data)
        message_id = headers.get("Message-ID", f"<no-msgid-{folder}-{uid}>")

        return RawEmail(
            uid=uid,
            folder=folder,
            uidvalidity=uidvalidity,
            message_id=message_id,
            data=raw_data,
        )

    async def fetch_raw_emails(
        self, folder: str, uids: list[int], uidvalidity: int
    ) -> list[RawEmail]:
        """Fetch multiple emails by UID with auto-reconnect on connection errors."""
        emails = []
        # Ensure folder is selected (skips if already selected by fetch_uids)
        await self.select_folder(folder)

        for uid in uids:
            try:
                raw = await self.fetch_raw_email(folder, uid, uidvalidity)
                if raw:
                    emails.append(raw)
            except (aioimaplib.Abort, asyncio.TimeoutError, OSError) as e:
                # Connection is broken — reconnect and retry this UID once
                logger.warning(
                    "Connection error fetching UID %d from %s: %s. Reconnecting...",
                    uid, folder, e,
                )
                try:
                    await self.reconnect(folder)
                    raw = await self.fetch_raw_email(folder, uid, uidvalidity)
                    if raw:
                        emails.append(raw)
                except Exception as retry_err:
                    logger.error(
                        "Retry failed for UID %d from %s: %s",
                        uid, folder, retry_err,
                    )
            except Exception as e:
                logger.error("Error fetching UID %d from %s: %s", uid, folder, e)

        return emails

    async def idle_loop(
        self,
        folder: str,
        on_new_mail: "asyncio.Future | None" = None,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Run IMAP IDLE on a folder, calling on_new_mail when new messages arrive.

        Re-issues IDLE every 25 minutes (before 29 min RFC timeout).
        Stops when stop_event is set.
        """
        if stop_event is None:
            stop_event = asyncio.Event()

        await self.select_folder(folder, force=True)
        logger.info("Starting IDLE on %s", folder)

        while not stop_event.is_set():
            try:
                idle_task = await self._client.idle_start(timeout=IDLE_TIMEOUT_SECONDS)

                # Wait for either IDLE response or stop signal
                done, pending = await asyncio.wait(
                    [asyncio.ensure_future(self._client.wait_server_push()),
                     asyncio.ensure_future(stop_event.wait())],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass

                # Stop IDLE
                self._client.idle_done()
                await asyncio.wait_for(idle_task, timeout=10)

                if stop_event.is_set():
                    break

                # Check if we got new mail notification
                for task in done:
                    try:
                        result = task.result()
                        if result and any("EXISTS" in str(r) for r in (result if isinstance(result, list) else [result])):
                            logger.info("New mail detected in %s", folder)
                            if on_new_mail:
                                on_new_mail.set()
                    except Exception:
                        pass

            except asyncio.TimeoutError:
                # IDLE timeout, re-issue
                logger.debug("IDLE timeout on %s, re-issuing", folder)
                continue
            except Exception as e:
                logger.error("IDLE error on %s: %s", folder, e)
                raise

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
