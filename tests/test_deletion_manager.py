import pytest
from unittest.mock import MagicMock
from app.services.deletion_manager import DeletionManager
from app.services.task_manager import TaskManager


@pytest.fixture
async def deletion_mgr(db):
    mock_gmail = MagicMock()
    tm = TaskManager()
    return DeletionManager(db, mock_gmail, tm)


async def _seed_junk(db, count=5):
    for i in range(count):
        await db.execute(
            """INSERT INTO emails (id, subject, sender_email, classification, synced_at, deleted_from_gmail)
               VALUES (?, ?, ?, 'junk', datetime('now'), 0)""",
            (f"msg_{i}", f"Junk {i}", f"spam{i}@junk.com"),
        )


async def test_delete_by_ids(deletion_mgr, db):
    await _seed_junk(db, 3)
    result = await deletion_mgr.delete_emails(["msg_0", "msg_1"], trigger="manual")
    assert result["deleted"] == 2
    deletion_mgr._gmail.trash_messages.assert_called_once()
    row = await db.execute_fetchone("SELECT * FROM emails WHERE id = 'msg_0'")
    assert row["deleted_from_gmail"] == 1
    assert row["deletion_type"] == "trashed"


async def test_delete_by_filter(deletion_mgr, db):
    await _seed_junk(db, 5)
    result = await deletion_mgr.delete_by_filter(
        filter_rules={"classification": "junk"},
        require_classification=True,
        trigger="scheduled",
    )
    assert result["deleted"] == 5


async def test_delete_logs_entries(deletion_mgr, db):
    await _seed_junk(db, 2)
    await deletion_mgr.delete_emails(["msg_0"], trigger="agent")
    logs = await db.execute_fetchall("SELECT * FROM deletion_log")
    assert len(logs) == 1
    assert logs[0]["trigger"] == "agent"
    assert logs[0]["email_id"] == "msg_0"


async def test_delete_permanent(deletion_mgr, db):
    await _seed_junk(db, 1)
    await deletion_mgr.delete_emails(["msg_0"], trigger="manual", permanent=True)
    deletion_mgr._gmail.delete_messages.assert_called_once()
    row = await db.execute_fetchone("SELECT * FROM emails WHERE id = 'msg_0'")
    assert row["deletion_type"] == "permanently_deleted"


async def test_delete_skips_already_deleted(deletion_mgr, db):
    await db.execute(
        """INSERT INTO emails (id, classification, synced_at, deleted_from_gmail)
           VALUES (?, 'junk', datetime('now'), 1)""",
        ("msg_0",),
    )
    result = await deletion_mgr.delete_emails(["msg_0"], trigger="manual")
    assert result["deleted"] == 0
    assert result["skipped"] == 1
