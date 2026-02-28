"""Sync state management using SQLite for deduplication."""
import hashlib
import logging
from datetime import datetime, timezone

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = "/data/db/sync.db"


class SyncState:
    def __init__(self, db_path: str = DB_PATH):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open database and create tables if they don't exist."""
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS folder_state (
                folder TEXT PRIMARY KEY,
                uidvalidity INTEGER NOT NULL,
                last_sync TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS synced_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder TEXT NOT NULL,
                uid INTEGER NOT NULL,
                uidvalidity INTEGER NOT NULL,
                message_id_hash TEXT NOT NULL,
                gmail_id TEXT,
                synced_at TEXT NOT NULL,
                UNIQUE(folder, uid, uidvalidity)
            );

            CREATE INDEX IF NOT EXISTS idx_message_id_hash
                ON synced_messages(message_id_hash);

            CREATE INDEX IF NOT EXISTS idx_folder_uid
                ON synced_messages(folder, uidvalidity);
        """)
        await self._db.commit()
        logger.info("Sync state database initialized at %s", self._db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def get_uidvalidity(self, folder: str) -> int | None:
        """Get stored UIDVALIDITY for a folder."""
        async with self._db.execute(
            "SELECT uidvalidity FROM folder_state WHERE folder = ?", (folder,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_uidvalidity(self, folder: str, uidvalidity: int) -> None:
        """Store UIDVALIDITY for a folder."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """INSERT INTO folder_state (folder, uidvalidity, last_sync)
               VALUES (?, ?, ?)
               ON CONFLICT(folder) DO UPDATE SET
                   uidvalidity = excluded.uidvalidity,
                   last_sync = excluded.last_sync""",
            (folder, uidvalidity, now),
        )
        await self._db.commit()

    async def get_synced_uids(self, folder: str, uidvalidity: int) -> set[int]:
        """Get all synced UIDs for a folder with matching UIDVALIDITY."""
        uids = set()
        async with self._db.execute(
            "SELECT uid FROM synced_messages WHERE folder = ? AND uidvalidity = ?",
            (folder, uidvalidity),
        ) as cursor:
            async for row in cursor:
                uids.add(row[0])
        return uids

    async def get_unsynced_uids(
        self, folder: str, uidvalidity: int, all_uids: list[int]
    ) -> list[int]:
        """Return UIDs that haven't been synced yet.

        If UIDVALIDITY changed, clears old UID tracking for this folder
        (Message-ID dedup still prevents re-importing).
        """
        stored_validity = await self.get_uidvalidity(folder)

        if stored_validity is not None and stored_validity != uidvalidity:
            logger.warning(
                "UIDVALIDITY changed for %s: %d -> %d. Resetting UID tracking.",
                folder, stored_validity, uidvalidity,
            )
            await self._db.execute(
                "DELETE FROM synced_messages WHERE folder = ? AND uidvalidity = ?",
                (folder, stored_validity),
            )
            await self._db.commit()

        await self.set_uidvalidity(folder, uidvalidity)
        synced = await self.get_synced_uids(folder, uidvalidity)
        return [uid for uid in all_uids if uid not in synced]

    async def is_message_id_synced(self, message_id: str) -> bool:
        """Check if a Message-ID has already been imported."""
        mid_hash = self._hash_message_id(message_id)
        async with self._db.execute(
            "SELECT 1 FROM synced_messages WHERE message_id_hash = ? LIMIT 1",
            (mid_hash,),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def mark_synced(
        self,
        folder: str,
        uid: int,
        uidvalidity: int,
        message_id: str,
        gmail_id: str = "",
    ) -> None:
        """Record that a message has been successfully imported."""
        now = datetime.now(timezone.utc).isoformat()
        mid_hash = self._hash_message_id(message_id)
        await self._db.execute(
            """INSERT OR IGNORE INTO synced_messages
               (folder, uid, uidvalidity, message_id_hash, gmail_id, synced_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (folder, uid, uidvalidity, mid_hash, gmail_id, now),
        )
        await self._db.commit()

    async def mark_all_as_seen(
        self, folder: str, uidvalidity: int, uids: list[int]
    ) -> None:
        """Mark all given UIDs as 'seen' without importing them.

        Used on first start to skip existing messages.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.set_uidvalidity(folder, uidvalidity)
        await self._db.executemany(
            """INSERT OR IGNORE INTO synced_messages
               (folder, uid, uidvalidity, message_id_hash, gmail_id, synced_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (folder, uid, uidvalidity, f"initial_{folder}_{uid}", "", now)
                for uid in uids
            ],
        )
        await self._db.commit()
        logger.info(
            "Marked %d existing UIDs as seen in %s", len(uids), folder
        )

    async def reset_folder(self, folder: str) -> None:
        """Reset UID tracking for a folder (for full-sync).

        Deletes all UID records so they appear as 'new'.
        Message-ID dedup still prevents actual duplicates in Gmail.
        """
        await self._db.execute(
            "DELETE FROM synced_messages WHERE folder = ?", (folder,)
        )
        await self._db.execute(
            "DELETE FROM folder_state WHERE folder = ?", (folder,)
        )
        await self._db.commit()
        logger.info("Reset sync state for folder %s", folder)

    async def reset_all(self) -> None:
        """Reset all sync state (for full-sync of all folders)."""
        await self._db.execute("DELETE FROM synced_messages")
        await self._db.execute("DELETE FROM folder_state")
        await self._db.commit()
        logger.info("Reset all sync state")

    async def get_stats(self) -> dict:
        """Get sync statistics for the dashboard."""
        stats = {"folders": {}, "total_synced": 0}

        async with self._db.execute(
            "SELECT folder, COUNT(*) FROM synced_messages GROUP BY folder"
        ) as cursor:
            async for row in cursor:
                stats["folders"][row[0]] = row[1]
                stats["total_synced"] += row[1]

        async with self._db.execute(
            "SELECT folder, last_sync FROM folder_state"
        ) as cursor:
            async for row in cursor:
                if row[0] not in stats["folders"]:
                    stats["folders"][row[0]] = 0
                stats["folders"][row[0]] = {
                    "count": stats["folders"].get(row[0], 0)
                    if isinstance(stats["folders"].get(row[0]), int)
                    else stats["folders"][row[0]].get("count", 0),
                    "last_sync": row[1],
                }

        return stats

    @staticmethod
    def _hash_message_id(message_id: str) -> str:
        return hashlib.sha256(message_id.encode()).hexdigest()
