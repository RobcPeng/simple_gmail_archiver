import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.database import Database


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.db_path", tmp_path / "test.db")
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)

    import app.main as main_mod
    new_db = Database(tmp_path / "test.db")
    monkeypatch.setattr(main_mod, "db", new_db)
    import app.api.schedules as schedules_mod
    monkeypatch.setattr(schedules_mod, "db", new_db)
    import app.api.stats as stats_mod
    monkeypatch.setattr(stats_mod, "db", new_db)

    await new_db.initialize()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await new_db.close()


async def test_create_schedule(client):
    resp = await client.post("/api/schedules", json={
        "name": "Weekly Cleanup",
        "cron_expression": "0 2 * * 0",
        "filter_rules": {"label": "CATEGORY_PROMOTIONS"},
        "require_classification": True,
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Weekly Cleanup"


async def test_list_schedules(client):
    await client.post("/api/schedules", json={
        "name": "S1", "cron_expression": "0 2 * * 0",
        "filter_rules": {}, "require_classification": True,
    })
    resp = await client.get("/api/schedules")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_delete_schedule(client):
    create = await client.post("/api/schedules", json={
        "name": "Temp", "cron_expression": "0 0 * * *",
        "filter_rules": {}, "require_classification": False,
    })
    sid = create.json()["id"]
    resp = await client.delete(f"/api/schedules/{sid}")
    assert resp.status_code == 204


async def test_get_stats(client):
    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    assert resp.json()["total_emails"] == 0
