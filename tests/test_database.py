import pytest
from app.database import Database


async def test_initialize_creates_tables(db):
    tables = await db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = [t["name"] for t in tables]
    assert "emails" in table_names
    assert "attachments" in table_names
    assert "sync_state" in table_names
    assert "deletion_schedules" in table_names
    assert "deletion_log" in table_names
    assert "classification_rules" in table_names
    assert "emails_fts" in table_names
    assert "schema_version" in table_names


async def test_wal_mode_enabled(db):
    result = await db.execute_fetchone("PRAGMA journal_mode")
    assert result[0] == "wal"


async def test_schema_version_set(db):
    result = await db.execute_fetchone("SELECT version FROM schema_version")
    assert result["version"] == 1


async def test_insert_and_retrieve_email(db):
    await db.execute(
        """INSERT INTO emails (id, thread_id, subject, sender, sender_email, classification, synced_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        ("msg_1", "thread_1", "Test Subject", "Alice", "alice@example.com", "unclassified"),
    )
    row = await db.execute_fetchone("SELECT * FROM emails WHERE id = ?", ("msg_1",))
    assert row["subject"] == "Test Subject"
    assert row["sender_email"] == "alice@example.com"
    assert row["classification"] == "unclassified"


async def test_fts5_search(db):
    await db.execute(
        """INSERT INTO emails (id, subject, sender, body_text, snippet, classification, synced_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        ("msg_1", "Invoice from AWS", "Amazon", "Your invoice for March", "Invoice...", "keep"),
    )
    await db.execute(
        """INSERT INTO emails_fts (rowid, subject, sender, body_text, snippet)
           VALUES ((SELECT rowid FROM emails WHERE id = ?), ?, ?, ?, ?)""",
        ("msg_1", "Invoice from AWS", "Amazon", "Your invoice for March", "Invoice..."),
    )
    results = await db.execute_fetchall(
        """SELECT e.* FROM emails e
           JOIN emails_fts fts ON e.rowid = fts.rowid
           WHERE emails_fts MATCH ?""",
        ("invoice",),
    )
    assert len(results) == 1
    assert results[0]["id"] == "msg_1"


async def test_sync_state_single_row(db):
    result = await db.execute_fetchone("SELECT * FROM sync_state WHERE id = 1")
    assert result is not None
    assert result["account_email"] is None
