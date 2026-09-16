"""
Base de données SQLite asynchrone.
Stocke les messages traités, les logs de traduction et de remplacement.
"""
import json
import aiosqlite
from datetime import datetime
from pathlib import Path
from config import Config
from modules.logger import log


CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS processed_messages (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    source_message_id  INTEGER UNIQUE NOT NULL,
    source_channel     TEXT    NOT NULL,
    target_message_id  INTEGER,
    status             TEXT    NOT NULL DEFAULT 'success',
    original_caption   TEXT,
    processed_caption  TEXT,
    media_type         TEXT,
    media_count        INTEGER DEFAULT 0,
    error_message      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS translation_logs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    source_message_id  INTEGER,
    line_original      TEXT,
    line_translated    TEXT,
    detected_language  TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_contact_logs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    source_message_id  INTEGER,
    original_username  TEXT,
    replaced_with      TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_config (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    _instance = None

    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    @classmethod
    async def get(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance.init()
        return cls._instance

    async def init(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(CREATE_TABLES)
        await self._conn.commit()
        log.debug("[DB] Base de données initialisée.")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    async def is_processed(self, source_message_id: int) -> bool:
        async with self._conn.execute(
            "SELECT 1 FROM processed_messages WHERE source_message_id = ?",
            (source_message_id,),
        ) as cur:
            return await cur.fetchone() is not None

    async def save_message(self, source_message_id, source_channel, target_message_id=None, status="success", original_caption=None, processed_caption=None, media_type=None, media_count=0, error_message=None):
        await self._conn.execute("INSERT OR REPLACE INTO processed_messages (source_message_id, source_channel, target_message_id, status, original_caption, processed_caption, media_type, media_count, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (source_message_id, source_channel, target_message_id, status, original_caption, processed_caption, media_type, media_count, error_message)); await self._conn.commit()

    async def save_translation(self, source_message_id, line_original, line_translated, detected_language):
        await self._conn.execute("INSERT INTO translation_logs (source_message_id, line_original, line_translated, detected_language) VALUES (?, ?, ?, ?)", (source_message_id, line_original, line_translated, detected_language)); await self._conn.commit()

    async def save_order_replacement(self, source_message_id, original_username, replaced_with):
        await self._conn.execute("INSERT INTO order_contact_logs (source_message_id, original_username, replaced_with) VALUES (?, ?, ?)", (source_message_id, original_username, replaced_with)); await self._conn.commit()

    async def get_recent_messages(self, limit=50):
        async with self._conn.execute("SELECT * FROM processed_messages ORDER BY created_at DESC LIMIT ?", (limit,)) as cur: rows = await cur.fetchall(); return [dict(r) for r in rows]

    async def get_stats(self):
        async with self._conn.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed FROM processed_messages") as cur: row = await cur.fetchone(); return dict(row) if row else {}

    async def get_config(self, key, default=""):
        async with self._conn.execute("SELECT value FROM app_config WHERE key = ?", (key,)) as cur: row = await cur.fetchone(); return row["value"] if row else default

    async def set_config(self, key, value):
        await self._conn.execute("INSERT INTO app_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value)); await self._conn.commit()
