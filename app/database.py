import aiosqlite
from pathlib import Path

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    thread_id TEXT,
    subject TEXT,
    sender TEXT,
    sender_email TEXT,
    recipients TEXT,  -- JSON
    date DATETIME,
    snippet TEXT,
    body_text TEXT,
    body_html TEXT,
    labels TEXT,  -- JSON
    size_bytes INTEGER,
    has_attachments BOOLEAN DEFAULT 0,
    classification TEXT DEFAULT 'unclassified',
    classification_reason TEXT,
    eml_path TEXT,
    synced_at DATETIME,
    classified_at DATETIME,
    updated_at DATETIME,
    deleted_from_gmail BOOLEAN DEFAULT 0,
    deletion_type TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL REFERENCES emails(id),
    filename TEXT,
    mime_type TEXT,
    size_bytes INTEGER
);

CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    account_email TEXT,
    last_history_id TEXT,
    last_full_sync DATETIME,
    total_messages INTEGER DEFAULT 0,
    synced_messages INTEGER DEFAULT 0,
    full_sync_page_token TEXT,
    full_sync_in_progress BOOLEAN DEFAULT 0,
    full_sync_max_messages INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deletion_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    filter_rules TEXT NOT NULL,  -- JSON
    require_classification BOOLEAN DEFAULT 1,
    enabled BOOLEAN DEFAULT 1,
    last_run DATETIME,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deletion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER REFERENCES deletion_schedules(id),
    email_id TEXT NOT NULL REFERENCES emails(id),
    deleted_at DATETIME DEFAULT (datetime('now')),
    trigger TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classification_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    pattern TEXT NOT NULL,
    classification TEXT NOT NULL,
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
    subject, sender, body_text, snippet,
    content='',
    tokenize='porter unicode61'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_emails_sender_email ON emails(sender_email);
CREATE INDEX IF NOT EXISTS idx_emails_classification ON emails(classification);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date);
CREATE INDEX IF NOT EXISTS idx_emails_deleted ON emails(deleted_from_gmail);
CREATE INDEX IF NOT EXISTS idx_deletion_log_email ON deletion_log(email_id);
CREATE INDEX IF NOT EXISTS idx_attachments_email ON attachments(email_id);
"""

INIT_SYNC_STATE = "INSERT OR IGNORE INTO sync_state (id) VALUES (1);"
INIT_SCHEMA_VERSION = "INSERT INTO schema_version (version) VALUES (?);"


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.execute(INIT_SYNC_STATE)
        # Set schema version if not already set
        row = await self.execute_fetchone("SELECT version FROM schema_version LIMIT 1")
        if row is None:
            await self._conn.execute(INIT_SCHEMA_VERSION, (SCHEMA_VERSION,))
        else:
            await self._run_migrations(row["version"])
        await self._conn.commit()

    async def _run_migrations(self, current_version: int):
        if current_version < 2:
            # Add checkpoint columns to sync_state
            for col in ("full_sync_page_token TEXT", "full_sync_in_progress BOOLEAN DEFAULT 0",
                        "full_sync_max_messages INTEGER DEFAULT 0"):
                try:
                    await self._conn.execute(f"ALTER TABLE sync_state ADD COLUMN {col}")
                except Exception:
                    pass  # Column already exists
            await self._conn.execute("UPDATE schema_version SET version = 2")

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def execute(self, sql: str, params: tuple = ()):
        await self._conn.execute(sql, params)
        await self._conn.commit()

    async def execute_fetchone(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchone()

    async def execute_fetchall(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchall()
