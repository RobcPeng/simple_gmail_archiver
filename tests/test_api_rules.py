import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.db_path", tmp_path / "test.db")
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)

    from app.database import Database
    import app.main as main_mod
    import app.api.rules as rules_mod
    import app.api.emails as emails_mod

    new_db = Database(tmp_path / "test.db")
    monkeypatch.setattr(main_mod, "db", new_db)
    monkeypatch.setattr(rules_mod, "db", new_db)
    monkeypatch.setattr(emails_mod, "db", new_db)

    await new_db.initialize()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await new_db.close()


async def test_create_rule(client):
    resp = await client.post("/api/rules", json={
        "name": "Block spam", "rule_type": "sender",
        "pattern": "spam@junk.com", "classification": "junk", "priority": 10,
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Block spam"
    assert resp.json()["id"] is not None


async def test_list_rules(client):
    await client.post("/api/rules", json={
        "name": "Rule 1", "rule_type": "sender",
        "pattern": "a@b.com", "classification": "junk",
    })
    await client.post("/api/rules", json={
        "name": "Rule 2", "rule_type": "domain",
        "pattern": "*.spam.*", "classification": "junk",
    })
    resp = await client.get("/api/rules")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_update_rule(client):
    create_resp = await client.post("/api/rules", json={
        "name": "Original", "rule_type": "sender",
        "pattern": "a@b.com", "classification": "junk",
    })
    rule_id = create_resp.json()["id"]
    resp = await client.put(f"/api/rules/{rule_id}", json={
        "name": "Updated", "rule_type": "sender",
        "pattern": "a@b.com", "classification": "keep",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"
    assert resp.json()["classification"] == "keep"


async def test_delete_rule(client):
    create_resp = await client.post("/api/rules", json={
        "name": "To Delete", "rule_type": "sender",
        "pattern": "a@b.com", "classification": "junk",
    })
    rule_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/rules/{rule_id}")
    assert resp.status_code == 204
    list_resp = await client.get("/api/rules")
    assert len(list_resp.json()) == 0
