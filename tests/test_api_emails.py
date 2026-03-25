import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.database import Database


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.db_path", tmp_path / "test.db")
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)

    # Re-create the module-level db with the patched path
    import app.main as main_mod
    new_db = Database(tmp_path / "test.db")
    monkeypatch.setattr(main_mod, "db", new_db)
    # Also patch the reference used by the emails module
    import app.api.emails as emails_mod
    monkeypatch.setattr(emails_mod, "db", new_db)

    await new_db.initialize()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await new_db.close()


async def _seed_via_db(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.initialize()
    for i in range(3):
        await db.execute(
            """INSERT INTO emails (id, subject, sender, sender_email, body_text, snippet,
               classification, date, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (f"msg_{i}", f"Subject {i}", f"Sender {i}", f"s{i}@test.com",
             f"Body {i}", f"Snippet {i}", "unclassified"),
        )
        await db.execute(
            """INSERT INTO emails_fts (rowid, subject, sender, body_text, snippet)
               VALUES ((SELECT rowid FROM emails WHERE id = ?), ?, ?, ?, ?)""",
            (f"msg_{i}", f"Subject {i}", f"Sender {i}", f"Body {i}", f"Snippet {i}"),
        )
    await db.close()


async def test_search_emails(client, tmp_path):
    await _seed_via_db(tmp_path)
    resp = await client.get("/api/emails", params={"query": "Subject"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3


async def test_get_email_by_id(client, tmp_path):
    await _seed_via_db(tmp_path)
    resp = await client.get("/api/emails/msg_0")
    assert resp.status_code == 200
    assert resp.json()["id"] == "msg_0"


async def test_get_email_not_found(client):
    resp = await client.get("/api/emails/nonexistent")
    assert resp.status_code == 404


async def test_classify_email(client, tmp_path):
    await _seed_via_db(tmp_path)
    resp = await client.patch("/api/emails/msg_0", json={"classification": "keep"})
    assert resp.status_code == 200
    assert resp.json()["classification"] == "keep"


async def test_bulk_classify(client, tmp_path):
    await _seed_via_db(tmp_path)
    resp = await client.post("/api/emails/classify-bulk", json={
        "email_ids": ["msg_0", "msg_1"],
        "classification": "junk",
    })
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2
