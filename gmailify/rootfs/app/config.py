"""Configuration management for Gmailify addon."""
import json
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = "/data/config.json"
TOKEN_PATH = "/data/gmail_token.json"


@dataclass
class Config:
    gmx_email: str
    gmx_password: str
    gmx_host: str = "imap.gmx.net"
    gmx_port: int = 993
    google_client_id: str = ""
    google_client_secret: str = ""
    sync_interval_minutes: int = 15
    folders: list[str] = field(default_factory=lambda: ["INBOX", "Gesendet"])

    @property
    def has_gmail_token(self) -> bool:
        return Path(TOKEN_PATH).exists()

    @property
    def gmail_credentials(self) -> dict:
        if not self.has_gmail_token:
            return {}
        with open(TOKEN_PATH) as f:
            return json.load(f)

    def save_gmail_token(self, credentials: dict) -> None:
        with open(TOKEN_PATH, "w") as f:
            json.dump(credentials, f, indent=2)
        logger.info("Gmail token saved to %s", TOKEN_PATH)


def load_config() -> Config:
    with open(CONFIG_PATH) as f:
        data = json.load(f)

    return Config(
        gmx_email=data["gmx_email"],
        gmx_password=data["gmx_password"],
        google_client_id=data.get("google_client_id", ""),
        google_client_secret=data.get("google_client_secret", ""),
        sync_interval_minutes=data.get("sync_interval_minutes", 15),
        folders=data.get("folders", ["INBOX", "Gesendet"]),
    )
