"""Gmail API client for importing messages and managing labels."""
import base64
import email
import email.policy
import email.utils
import logging
import re

from folder_mapping import GMAIL_SYSTEM_LABELS
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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

        System labels (INBOX, SENT, DRAFT, etc.) are returned as-is.
        Custom labels like 'GMX/Inbox' are created if they don't exist.
        """
        # System labels already exist; their ID equals their name
        if label_name in GMAIL_SYSTEM_LABELS:
            return label_name

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

    def message_exists(self, message_id: str) -> bool:
        """Check if a message with this Message-ID already exists in Gmail."""
        # Strip angle brackets for the query
        clean_id = message_id.strip().strip("<>")
        if not clean_id:
            return False

        try:
            response = (
                self._service.users()
                .messages()
                .list(userId="me", q=f"rfc822msgid:{clean_id}", maxResults=1)
                .execute()
            )
            return response.get("resultSizeEstimate", 0) > 0
        except Exception as e:
            logger.warning("Gmail Message-ID lookup failed for %s: %s", message_id, e)
            return False

    def import_message(self, raw_email: bytes, label_ids: list[str]) -> str:
        """Import a raw RFC 2822 email into Gmail with given labels.

        Uses messages.import_() which preserves original headers.
        Sanitizes malformed headers (duplicate From, etc.) before import.
        Uses base64url raw field to avoid ASCII encoding issues with
        non-ASCII email content.
        Returns the Gmail message ID.
        """
        raw_email = self._sanitize_headers(raw_email)

        raw_b64 = base64.urlsafe_b64encode(raw_email).decode("ascii")
        response = (
            self._service.users()
            .messages()
            .import_(
                userId="me",
                body={"raw": raw_b64, "labelIds": label_ids},
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

        Uses Python's email module for robust parsing, then fixes:
        - Multiple 'From' headers (keeps first, removes rest)
        - Missing 'From' header (adds placeholder)
        - From header with multiple addresses (keeps first address only)
        """
        try:
            msg = email.message_from_bytes(raw_email, policy=email.policy.compat32)
        except Exception as e:
            logger.warning("Failed to parse email for sanitization: %s", e)
            return raw_email

        from_headers = msg.get_all("From", [])
        needs_fix = False

        if len(from_headers) > 1:
            logger.info("Fixing email with %d From headers (keeping first: %s)",
                        len(from_headers), from_headers[0])
            needs_fix = True
        elif len(from_headers) == 0:
            logger.info("Fixing email with missing From header")
            needs_fix = True
        elif from_headers[0]:
            # Use email.utils to properly parse addresses (handles quoted commas)
            addresses = email.utils.getaddresses([from_headers[0]])
            if len(addresses) > 1:
                logger.info("Fixing From header with %d addresses: %s",
                            len(addresses), from_headers[0])
                needs_fix = True

        if not needs_fix:
            return raw_email

        # Remove all existing From headers
        while "From" in msg:
            del msg["From"]

        # Add back a single clean From header
        if from_headers:
            # Parse all addresses properly (respects quoted display names)
            addresses = email.utils.getaddresses(from_headers)
            if addresses:
                msg["From"] = email.utils.formataddr(addresses[0])
            else:
                msg["From"] = from_headers[0]
        else:
            msg["From"] = "unknown@unknown"

        return msg.as_bytes()


    def _load_labels(self) -> None:
        """Fetch all existing labels into cache."""
        results = (
            self._service.users().labels().list(userId="me").execute()
        )
        for label in results.get("labels", []):
            self._label_cache[label["name"]] = label["id"]
        logger.debug("Loaded %d Gmail labels", len(self._label_cache))
