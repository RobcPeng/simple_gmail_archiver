import pytest
from app.services.search import SearchService


@pytest.fixture
async def search(db):
    return SearchService(db)


async def _seed_emails(db, count=5):
    for i in range(count):
        await db.execute(
            """INSERT INTO emails (id, subject, sender, sender_email, body_text, snippet,
               classification, date, size_bytes, has_attachments, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', ?), ?, ?, datetime('now'))""",
            (f"msg_{i}", f"Subject {i} invoice" if i % 2 == 0 else f"Subject {i} newsletter",
             f"Sender {i}", f"sender{i}@example.com",
             f"Body text {i} with some content", f"Snippet {i}",
             "keep" if i % 3 != 0 else "junk",
             f"-{i} days", (i + 1) * 1000, i % 2 == 0),
        )
        await db.execute(
            """INSERT INTO emails_fts (rowid, subject, sender, body_text, snippet)
               VALUES ((SELECT rowid FROM emails WHERE id = ?), ?, ?, ?, ?)""",
            (f"msg_{i}", f"Subject {i} invoice" if i % 2 == 0 else f"Subject {i} newsletter",
             f"Sender {i}", f"Body text {i} with some content", f"Snippet {i}"),
        )


async def test_search_by_keyword(search, db):
    await _seed_emails(db)
    result = await search.search(query="invoice")
    assert result.total > 0
    assert all("invoice" in e.subject.lower() for e in result.emails)


async def test_search_pagination(search, db):
    await _seed_emails(db, count=10)
    page1 = await search.search(query="Subject", page=1, page_size=3)
    page2 = await search.search(query="Subject", page=2, page_size=3)
    assert len(page1.emails) == 3
    assert len(page2.emails) == 3
    assert page1.emails[0].id != page2.emails[0].id


async def test_search_filter_classification(search, db):
    await _seed_emails(db)
    result = await search.search(classification="junk")
    assert all(e.classification == "junk" for e in result.emails)


async def test_search_no_query_returns_all(search, db):
    await _seed_emails(db, count=5)
    result = await search.search()
    assert result.total == 5


async def test_get_email_by_id(search, db):
    await _seed_emails(db, count=1)
    email = await search.get_email("msg_0")
    assert email is not None
    assert email.id == "msg_0"


async def test_get_email_not_found(search, db):
    email = await search.get_email("nonexistent")
    assert email is None
