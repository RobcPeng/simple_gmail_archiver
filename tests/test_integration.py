import pytest
from httpx import AsyncClient, ASGITransport
from app.database import Database
from app.main import create_app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.db_path", tmp_path / "test.db")
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)
    # Replace module-level db so lifespan and all API modules use the temp database
    test_db = Database(tmp_path / "test.db")
    monkeypatch.setattr("app.main.db", test_db)
    monkeypatch.setattr("app.api.emails.db", test_db)
    monkeypatch.setattr("app.api.rules.db", test_db)
    monkeypatch.setattr("app.api.stats.db", test_db)
    monkeypatch.setattr("app.api.sync.db", test_db)
    monkeypatch.setattr("app.api.schedules.db", test_db)
    app = create_app()
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_full_workflow(client):
    # Check stats
    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    assert resp.json()["total_emails"] == 0

    # Create classification rule
    resp = await client.post("/api/rules", json={
        "name": "Promo cleanup", "rule_type": "label",
        "pattern": "CATEGORY_PROMOTIONS", "classification": "junk", "priority": 10,
    })
    assert resp.status_code == 201

    # Create deletion schedule
    resp = await client.post("/api/schedules", json={
        "name": "Weekly Cleanup", "cron_expression": "0 2 * * 0",
        "filter_rules": {"label": "CATEGORY_PROMOTIONS"},
        "require_classification": True,
    })
    assert resp.status_code == 201

    # Verify schedule exists
    resp = await client.get("/api/schedules")
    assert len(resp.json()) == 1

    # Verify rule exists
    resp = await client.get("/api/rules")
    assert len(resp.json()) == 1

    # Health check
    resp = await client.get("/api/health")
    assert resp.json()["status"] == "ok"
