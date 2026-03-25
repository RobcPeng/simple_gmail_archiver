import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.task_manager import TaskManager
from app.services.sync_manager import SyncManager


@pytest.fixture
def task_mgr():
    return TaskManager()


@pytest.fixture
async def sync_mgr(db):
    mock_gmail = MagicMock()
    mock_r2 = MagicMock()
    tm = TaskManager()
    from app.services.classifier import Classifier
    from app.services.gmail import GmailService
    classifier = Classifier(db)
    # Use real static methods for header parsing
    mock_gmail.parse_headers = GmailService.parse_headers
    mock_gmail.extract_email_address = GmailService.extract_email_address
    return SyncManager(db, mock_gmail, mock_r2, classifier, tm)


async def test_task_manager_sync_lock(task_mgr):
    acquired = await task_mgr.acquire_sync_lock()
    assert acquired is True
    acquired2 = await task_mgr.acquire_sync_lock()
    assert acquired2 is False
    task_mgr.release_sync_lock()
    acquired3 = await task_mgr.acquire_sync_lock()
    assert acquired3 is True
    task_mgr.release_sync_lock()


async def test_deletion_waits_for_sync(task_mgr):
    await task_mgr.acquire_sync_lock()

    async def try_delete():
        await task_mgr.wait_for_sync_complete()
        return True

    task = asyncio.create_task(try_delete())
    await asyncio.sleep(0.05)
    assert not task.done()
    task_mgr.release_sync_lock()
    result = await asyncio.wait_for(task, timeout=1.0)
    assert result is True


async def test_sync_processes_messages(sync_mgr, db):
    sync_mgr._gmail.list_messages.return_value = (
        [{"id": "msg_1"}, {"id": "msg_2"}], None
    )
    sync_mgr._gmail.get_message.side_effect = [
        {
            "id": "msg_1", "threadId": "t1", "labelIds": ["INBOX"],
            "snippet": "Hello", "sizeEstimate": 100,
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test 1"},
                    {"name": "From", "value": "alice@test.com"},
                    {"name": "Date", "value": "Mon, 24 Mar 2026 10:00:00 +0000"},
                ],
                "mimeType": "text/plain",
                "body": {"data": "SGVsbG8="},
            },
        },
        {
            "id": "msg_2", "threadId": "t2", "labelIds": ["INBOX"],
            "snippet": "World", "sizeEstimate": 200,
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test 2"},
                    {"name": "From", "value": "bob@test.com"},
                    {"name": "Date", "value": "Mon, 24 Mar 2026 11:00:00 +0000"},
                ],
                "mimeType": "text/plain",
                "body": {"data": "V29ybGQ="},
            },
        },
    ]
    sync_mgr._gmail.get_raw_message.return_value = b"raw email bytes"
    sync_mgr._r2.upload_eml.return_value = "2026/03/msg_1.eml"
    sync_mgr._gmail.get_profile.return_value = {"emailAddress": "user@gmail.com"}

    await sync_mgr.run_full_sync()

    emails = await db.execute_fetchall("SELECT * FROM emails ORDER BY id")
    assert len(emails) == 2
    assert emails[0]["id"] == "msg_1"
    assert emails[1]["id"] == "msg_2"


async def test_sync_skips_existing_emails(sync_mgr, db):
    await db.execute(
        """INSERT INTO emails (id, subject, classification, synced_at)
           VALUES (?, ?, ?, datetime('now'))""",
        ("msg_1", "Existing", "keep"),
    )
    sync_mgr._gmail.list_messages.return_value = ([{"id": "msg_1"}], None)
    sync_mgr._gmail.get_profile.return_value = {"emailAddress": "user@gmail.com"}

    await sync_mgr.run_full_sync()

    email = await db.execute_fetchone("SELECT * FROM emails WHERE id = ?", ("msg_1",))
    assert email["subject"] == "Existing"
    assert email["classification"] == "keep"
