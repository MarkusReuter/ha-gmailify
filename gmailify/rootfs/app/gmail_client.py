"""Gmail API client for importing messages and managing labels."""
import io
import logging

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
        Returns the Gmail message ID.
        """
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

    def _load_labels(self) -> None:
        """Fetch all existing labels into cache."""
        results = (
            self._service.users().labels().list(userId="me").execute()
        )
        for label in results.get("labels", []):
            self._label_cache[label["name"]] = label["id"]
        logger.debug("Loaded %d Gmail labels", len(self._label_cache))
