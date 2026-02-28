"""Gmail API client for importing messages and managing labels."""
import email
import email.policy
import io
import logging
import re

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


class GmailClient:
    def __init__(self, credentials_dict: dict):
        """Build Gmail service from OAuth2 credentials dict.

        credentials_dict: {client_id, client_secret, refresh_token}
        """
        creds = Credentials(
            token=None,
            refresh_token=credentials_dict["refresh_token"],
            client_id=credentials_dict["client_id"],
            client_secret=credentials_dict["client_secret"],
            token_uri=credentials_dict.get("token_uri", TOKEN_URI),
        )
        self._service = build("gmail", "v1", credentials=creds)
        self._label_cache: dict[str, str] = {}
        logger.info("Gmail API client initialized")

    def ensure_label(self, label_name: str) -> str:
        """Get or create a Gmail label. Returns the label ID.

        Supports nested labels like 'GMX/Inbox'.
        """
        if label_name in self._label_cache:
            return self._label_cache[label_name]

        # Load all labels if cache is empty
        if not self._label_cache:
            self._load_labels()

        if label_name in self._label_cache:
            return self._label_cache[label_name]

        # Create the label
        body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        result = self._service.users().labels().create(
            userId="me", body=body
        ).execute()

        label_id = result["id"]
        self._label_cache[label_name] = label_id
        logger.info("Created Gmail label '%s' (ID: %s)", label_name, label_id)
        return label_id

    def import_message(self, raw_email: bytes, label_ids: list[str]) -> str:
        """Import a raw RFC 2822 email into Gmail with given labels.

        Uses messages.import_() which preserves original headers.
        Sanitizes malformed headers (duplicate From, etc.) before import.
        Returns the Gmail message ID.
        """
        raw_email = self._sanitize_headers(raw_email)

        media = MediaIoBaseUpload(
            io.BytesIO(raw_email),
            mimetype="message/rfc822",
        )
        response = (
            self._service.users()
            .messages()
            .import_(
                userId="me",
                body={"labelIds": label_ids},
                media_body=media,
                neverMarkSpam=True,
                processForCalendar=False,
                internalDateSource="dateHeader",
            )
            .execute(num_retries=3)
        )
        return response["id"]

    @staticmethod
    def _sanitize_headers(raw_email: bytes) -> bytes:
        """Fix malformed headers that Gmail API rejects.

        - Ensures exactly one 'From' header (keeps first, removes duplicates)
        - Adds a placeholder 'From' if missing
        """
        # Split into header section and body
        if b"\r\n\r\n" in raw_email:
            header_bytes, body = raw_email.split(b"\r\n\r\n", 1)
            separator = b"\r\n\r\n"
            line_sep = b"\r\n"
        elif b"\n\n" in raw_email:
            header_bytes, body = raw_email.split(b"\n\n", 1)
            separator = b"\n\n"
            line_sep = b"\n"
        else:
            return raw_email  # Can't parse, try as-is

        # Unfold headers (continuation lines start with space/tab)
        header_text = header_bytes.decode("utf-8", errors="replace")
        lines = header_text.split(line_sep.decode())

        # Build list of (header_name, full_line) tuples
        headers = []
        for line in lines:
            if line and line[0] in (" ", "\t") and headers:
                # Continuation line - append to previous header
                headers[-1] = (headers[-1][0], headers[-1][1] + line_sep.decode() + line)
            else:
                # New header
                colon_pos = line.find(":")
                if colon_pos > 0:
                    name = line[:colon_pos].strip()
                    headers.append((name, line))
                elif line:
                    headers.append(("", line))

        # Fix From headers: keep only the first one
        from_count = sum(1 for name, _ in headers if name.lower() == "from")

        if from_count > 1:
            seen_from = False
            new_headers = []
            for name, line in headers:
                if name.lower() == "from":
                    if not seen_from:
                        seen_from = True
                        new_headers.append((name, line))
                    else:
                        logger.debug("Removing duplicate From header")
                else:
                    new_headers.append((name, line))
            headers = new_headers
        elif from_count == 0:
            headers.insert(0, ("From", "From: unknown@unknown"))
            logger.debug("Added missing From header")

        # Reassemble
        header_text = line_sep.decode().join(line for _, line in headers)
        return header_text.encode("utf-8", errors="replace") + separator + body

    def _load_labels(self) -> None:
        """Fetch all existing labels into cache."""
        results = (
            self._service.users().labels().list(userId="me").execute()
        )
        for label in results.get("labels", []):
            self._label_cache[label["name"]] = label["id"]
        logger.debug("Loaded %d Gmail labels", len(self._label_cache))
