# GmailVault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack Gmail management app that syncs, archives (.eml to R2), searches (FTS5), classifies (rule-based with manual review), and bulk-deletes emails — controllable via browser UI and MCP server.

**Architecture:** Modular monolith — single FastAPI process with async background tasks, SQLite (WAL mode) for data/search, Cloudflare R2 for .eml storage, React SPA frontend, integrated MCP server.

**Tech Stack:** Python 3.12+, FastAPI, aiosqlite, SQLite FTS5, boto3 (R2), google-api-python-client, APScheduler, React 19, Vite, MCP Python SDK

**Spec:** `docs/superpowers/specs/2026-03-24-gmail-vault-design.md`

---

## File Map

### Backend Core
| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Project metadata, dependencies |
| `app/__init__.py` | Package init |
| `app/main.py` | FastAPI app factory, lifespan (scheduler start, DB init), static file serving |
| `app/config.py` | Pydantic Settings: paths, OAuth, R2 creds, sync interval |
| `app/database.py` | SQLite connection pool (aiosqlite), WAL mode, schema migrations, `schema_version` table |
| `app/models.py` | Pydantic models for all entities (Email, Schedule, Rule, SyncState, etc.) |

### Services
| File | Responsibility |
|------|---------------|
| `app/services/gmail.py` | Gmail API client: OAuth flow, message list/get, batch API, raw .eml download, history.list, token refresh |
| `app/services/r2.py` | R2 client: upload .eml, generate pre-signed download URL, delete |
| `app/services/search.py` | FTS5 query builder, search with filters, pagination |
| `app/services/classifier.py` | Rule engine (evaluate rules by priority), suggestion heuristics |
| `app/services/scheduler.py` | APScheduler setup, job persistence, cron schedule CRUD |
| `app/services/sync_manager.py` | Orchestrate sync: lock management, batch processing, .eml export, progress tracking |
| `app/services/deletion_manager.py` | Orchestrate deletion: lock management, batch Gmail API deletes, logging |
| `app/services/task_manager.py` | Background task tracking, SSE progress events, asyncio locks for concurrency |

### API Routes
| File | Responsibility |
|------|---------------|
| `app/api/__init__.py` | Router aggregation |
| `app/api/emails.py` | GET /api/emails (search), GET /api/emails/{id}, PATCH /api/emails/{id} (classify), POST /api/emails/classify-bulk |
| `app/api/sync.py` | POST /api/sync (trigger), GET /api/sync/status, GET /api/sync/events (SSE) |
| `app/api/schedules.py` | CRUD /api/schedules |
| `app/api/rules.py` | CRUD /api/rules |
| `app/api/stats.py` | GET /api/stats |
| `app/api/auth.py` | GET /api/auth/status, POST /api/auth/start, GET /api/auth/callback |

### MCP Server
| File | Responsibility |
|------|---------------|
| `app/mcp/__init__.py` | Package init |
| `app/mcp/server.py` | MCP protocol handler, SSE transport mount on FastAPI |
| `app/mcp/tools.py` | 20 tool definitions, delegating to services |

### Frontend
| File | Responsibility |
|------|---------------|
| `app/frontend/package.json` | React + Vite dependencies |
| `app/frontend/vite.config.ts` | Vite config with API proxy to FastAPI |
| `app/frontend/index.html` | Entry HTML |
| `app/frontend/src/main.tsx` | React root |
| `app/frontend/src/App.tsx` | Router setup, layout shell |
| `app/frontend/src/api.ts` | API client (fetch wrapper) |
| `app/frontend/src/pages/Dashboard.tsx` | Stats cards, sync status, next deletion preview |
| `app/frontend/src/pages/Search.tsx` | Search bar, filters, paginated results, bulk classify |
| `app/frontend/src/pages/ReviewQueue.tsx` | Grouped unclassified emails, suggestions, batch classify |
| `app/frontend/src/pages/Schedules.tsx` | Schedule + rule CRUD |
| `app/frontend/src/pages/Settings.tsx` | OAuth status, R2 config, sync interval |
| `app/frontend/src/components/EmailRow.tsx` | Single email result row |
| `app/frontend/src/components/ClassificationBadge.tsx` | Keep/junk/unclassified badge |
| `app/frontend/src/components/SenderGroup.tsx` | Expandable sender group for review queue |
| `app/frontend/src/components/StatsCard.tsx` | Dashboard stat card |

### Tests
| File | Responsibility |
|------|---------------|
| `tests/conftest.py` | Shared fixtures: test DB, mock Gmail, mock R2 |
| `tests/test_database.py` | Schema creation, migrations, CRUD operations |
| `tests/test_search.py` | FTS5 indexing, query parsing, pagination |
| `tests/test_classifier.py` | Rule evaluation, priority ordering, suggestions |
| `tests/test_gmail.py` | Gmail API client (mocked), batch processing, .eml parsing |
| `tests/test_r2.py` | R2 upload/download/presign (mocked) |
| `tests/test_sync_manager.py` | Sync orchestration, concurrency locks, progress tracking |
| `tests/test_deletion_manager.py` | Deletion orchestration, batching, logging |
| `tests/test_api_emails.py` | Email search/classify API endpoints |
| `tests/test_api_schedules.py` | Schedule CRUD API |
| `tests/test_api_rules.py` | Rule CRUD API |
| `tests/test_mcp_tools.py` | MCP tool invocations |
| `tests/test_integration.py` | End-to-end workflow test |

---

## Task 1: Project Scaffold & Database

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/database.py`
- Create: `app/models.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Create pyproject.toml with core dependencies**

```toml
[project]
name = "gmail-vault"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "aiosqlite>=0.20.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create app config**

Create `app/__init__.py` (empty) and `app/config.py`:

```python
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Paths
    data_dir: Path = Path("data")
    db_path: Path = Path("data/emails.db")

    # R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""

    # Gmail OAuth
    credentials_dir: Path = Path("credentials")
    client_secret_path: Path = Path("credentials/client_secret.json")
    token_path: Path = Path("credentials/token.json")

    # Sync
    sync_interval_minutes: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

- [ ] **Step 3: Create Pydantic models**

Create `app/models.py` with all entity models matching the spec schema:

```python
from datetime import datetime
from pydantic import BaseModel

class Email(BaseModel):
    id: str
    thread_id: str | None = None
    subject: str | None = None
    sender: str | None = None
    sender_email: str | None = None
    recipients: dict | None = None
    date: datetime | None = None
    snippet: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    labels: list[str] | None = None
    size_bytes: int | None = None
    has_attachments: bool = False
    classification: str = "unclassified"
    classification_reason: str | None = None
    eml_path: str | None = None
    synced_at: datetime | None = None
    classified_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_from_gmail: bool = False
    deletion_type: str | None = None

class EmailSearchResult(BaseModel):
    emails: list[Email]
    total: int
    page: int
    page_size: int

class Attachment(BaseModel):
    id: int | None = None
    email_id: str
    filename: str
    mime_type: str | None = None
    size_bytes: int | None = None

class SyncState(BaseModel):
    account_email: str | None = None
    last_history_id: str | None = None
    last_full_sync: datetime | None = None
    total_messages: int = 0
    synced_messages: int = 0

class DeletionSchedule(BaseModel):
    id: int | None = None
    name: str
    cron_expression: str
    filter_rules: dict
    require_classification: bool = True
    enabled: bool = True
    last_run: datetime | None = None
    created_at: datetime | None = None

class DeletionLog(BaseModel):
    id: int | None = None
    schedule_id: int | None = None
    email_id: str
    deleted_at: datetime | None = None
    trigger: str  # 'scheduled' | 'manual' | 'agent'

class ClassificationRule(BaseModel):
    id: int | None = None
    name: str
    rule_type: str  # 'sender' | 'domain' | 'label' | 'keyword' | 'size'
    pattern: str
    classification: str  # 'junk' | 'keep'
    priority: int = 100
    enabled: bool = True
    created_at: datetime | None = None

class Stats(BaseModel):
    total_emails: int = 0
    classified_keep: int = 0
    classified_junk: int = 0
    unclassified: int = 0
    deleted_from_gmail: int = 0
    total_size_bytes: int = 0
```

- [ ] **Step 4: Write database test**

Create `tests/__init__.py` (empty) and `tests/conftest.py`:

```python
import asyncio
import pytest
from pathlib import Path
from app.database import Database

@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "test.db")
    await database.initialize()
    yield database
    await database.close()
```

Create `tests/test_database.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd /Users/peng/Documents/Sandbox/email-management && pip install -e ".[dev]" && pytest tests/test_database.py -v`
Expected: FAIL — `app.database` module doesn't exist yet

- [ ] **Step 6: Implement database module**

Create `app/database.py`:

```python
import aiosqlite
from pathlib import Path

SCHEMA_VERSION = 1

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
    synced_messages INTEGER DEFAULT 0
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
        await self._conn.commit()

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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_database.py -v`
Expected: All 5 tests PASS

- [ ] **Step 8: Create minimal FastAPI app**

Create `app/main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database import Database

db = Database(settings.db_path)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()
    yield
    await db.close()

def create_app() -> FastAPI:
    app = FastAPI(title="GmailVault", version="0.1.0", lifespan=lifespan)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app

app = create_app()
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml app/ tests/
git commit -m "feat: project scaffold with SQLite database, schema, FTS5, and config"
```

---

## Task 2: Search Service & Email API

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/search.py`
- Create: `app/api/__init__.py`
- Create: `app/api/emails.py`
- Create: `tests/test_search.py`
- Create: `tests/test_api_emails.py`

- [ ] **Step 1: Write search service tests**

Create `tests/test_search.py`:

```python
import pytest
from app.services.search import SearchService

@pytest.fixture
async def search(db):
    return SearchService(db)

async def _seed_emails(db, count=5):
    """Insert test emails into DB and FTS index."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_search.py -v`
Expected: FAIL — `app.services.search` doesn't exist

- [ ] **Step 3: Implement search service**

Create `app/services/__init__.py` (empty) and `app/services/search.py`:

```python
import json
from app.database import Database
from app.models import Email, EmailSearchResult

class SearchService:
    def __init__(self, db: Database):
        self.db = db

    async def search(
        self,
        query: str | None = None,
        classification: str | None = None,
        has_attachments: bool | None = None,
        date_after: str | None = None,
        date_before: str | None = None,
        sender: str | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EmailSearchResult:
        conditions = []
        params = []

        if query:
            conditions.append(
                "e.rowid IN (SELECT rowid FROM emails_fts WHERE emails_fts MATCH ?)"
            )
            params.append(query)

        if classification:
            conditions.append("e.classification = ?")
            params.append(classification)

        if has_attachments is not None:
            conditions.append("e.has_attachments = ?")
            params.append(1 if has_attachments else 0)

        if date_after:
            conditions.append("e.date >= ?")
            params.append(date_after)

        if date_before:
            conditions.append("e.date <= ?")
            params.append(date_before)

        if sender:
            conditions.append("(e.sender_email LIKE ? OR e.sender LIKE ?)")
            params.extend([f"%{sender}%", f"%{sender}%"])

        if min_size is not None:
            conditions.append("e.size_bytes >= ?")
            params.append(min_size)

        if max_size is not None:
            conditions.append("e.size_bytes <= ?")
            params.append(max_size)

        where = " AND ".join(conditions) if conditions else "1=1"

        count_row = await self.db.execute_fetchone(
            f"SELECT COUNT(*) as cnt FROM emails e WHERE {where}", tuple(params)
        )
        total = count_row["cnt"]

        offset = (page - 1) * page_size
        rows = await self.db.execute_fetchall(
            f"""SELECT * FROM emails e WHERE {where}
                ORDER BY e.date DESC LIMIT ? OFFSET ?""",
            tuple(params + [page_size, offset]),
        )

        emails = [self._row_to_email(r) for r in rows]
        return EmailSearchResult(emails=emails, total=total, page=page, page_size=page_size)

    async def get_email(self, email_id: str) -> Email | None:
        row = await self.db.execute_fetchone("SELECT * FROM emails WHERE id = ?", (email_id,))
        if row is None:
            return None
        return self._row_to_email(row)

    def _row_to_email(self, row) -> Email:
        d = dict(row)
        # Parse JSON fields
        for field in ("recipients", "labels"):
            if d.get(field) and isinstance(d[field], str):
                d[field] = json.loads(d[field])
        return Email(**d)
```

- [ ] **Step 4: Run search tests to verify they pass**

Run: `pytest tests/test_search.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Write email API tests**

Create `app/api/__init__.py` (empty) and `tests/test_api_emails.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.database import Database

@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.db_path", tmp_path / "test.db")
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

async def _seed_via_db(tmp_path):
    """Seed directly via DB for test setup."""
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
```

- [ ] **Step 6: Implement email API routes**

Create `app/api/emails.py`:

```python
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.main import db
from app.services.search import SearchService

router = APIRouter(prefix="/api/emails", tags=["emails"])

class ClassifyRequest(BaseModel):
    classification: str

class BulkClassifyRequest(BaseModel):
    email_ids: list[str]
    classification: str

@router.get("")
async def search_emails(
    query: str | None = None,
    classification: str | None = None,
    has_attachments: bool | None = None,
    date_after: str | None = None,
    date_before: str | None = None,
    sender: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    search = SearchService(db)
    return await search.search(
        query=query, classification=classification,
        has_attachments=has_attachments, date_after=date_after,
        date_before=date_before, sender=sender,
        page=page, page_size=page_size,
    )

@router.get("/{email_id}")
async def get_email(email_id: str):
    search = SearchService(db)
    email = await search.get_email(email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return email

@router.patch("/{email_id}")
async def classify_email(email_id: str, body: ClassifyRequest):
    search = SearchService(db)
    email = await search.get_email(email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    now = datetime.utcnow().isoformat()
    await db.execute(
        """UPDATE emails SET classification = ?, classified_at = ?, updated_at = ?
           WHERE id = ?""",
        (body.classification, now, now, email_id),
    )

    # Retroactive .eml export: when reclassifying junk → keep
    if email.classification == "junk" and body.classification == "keep" and not email.eml_path:
        if not email.deleted_from_gmail:
            # Re-fetch from Gmail and upload to R2 (done as background task)
            # Import gmail/r2 services from app context and trigger async export
            pass  # Wired in Task 10 via service injection
        else:
            await db.execute(
                "UPDATE emails SET eml_path = 'unrecoverable' WHERE id = ?", (email_id,)
            )

    return {**email.model_dump(), "classification": body.classification, "classified_at": now}

@router.post("/classify-bulk")
async def bulk_classify(body: BulkClassifyRequest):
    now = datetime.utcnow().isoformat()
    placeholders = ",".join("?" for _ in body.email_ids)
    await db.execute(
        f"""UPDATE emails SET classification = ?, classified_at = ?, updated_at = ?
            WHERE id IN ({placeholders})""",
        (body.classification, now, now, *body.email_ids),
    )
    return {"updated": len(body.email_ids), "classification": body.classification}
```

Wire routes into `app/main.py` — add inside `create_app()`:

```python
from app.api.emails import router as emails_router
app.include_router(emails_router)
```

- [ ] **Step 7: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add app/services/ app/api/ tests/test_search.py tests/test_api_emails.py
git commit -m "feat: search service with FTS5 and email CRUD API"
```

---

## Task 3: Classification Rule Engine

**Files:**
- Create: `app/services/classifier.py`
- Create: `tests/test_classifier.py`
- Create: `app/api/rules.py`
- Create: `tests/test_api_rules.py`

- [ ] **Step 1: Write classifier tests**

Create `tests/test_classifier.py`:

```python
import pytest
from app.services.classifier import Classifier

@pytest.fixture
async def classifier(db):
    return Classifier(db)

async def _add_rule(db, name, rule_type, pattern, classification, priority=100):
    await db.execute(
        """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority)
           VALUES (?, ?, ?, ?, ?)""",
        (name, rule_type, pattern, classification, priority),
    )

async def _add_email(db, id, sender_email="test@test.com", subject="Test", body="Body",
                      labels=None, size_bytes=100):
    import json
    await db.execute(
        """INSERT INTO emails (id, sender_email, subject, body_text, labels, size_bytes,
           classification, synced_at) VALUES (?, ?, ?, ?, ?, ?, 'unclassified', datetime('now'))""",
        (id, sender_email, subject, body, json.dumps(labels or []), size_bytes),
    )

async def test_sender_rule_matches(classifier, db):
    await _add_rule(db, "Block spam", "sender", "spam@junk.com", "junk")
    await _add_email(db, "msg_1", sender_email="spam@junk.com")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "junk"

async def test_domain_rule_wildcard(classifier, db):
    await _add_rule(db, "Block marketing", "domain", "*.marketing.*", "junk")
    await _add_email(db, "msg_1", sender_email="offers@email.marketing.co")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "junk"

async def test_label_rule(classifier, db):
    await _add_rule(db, "Promos are junk", "label", "CATEGORY_PROMOTIONS", "junk")
    await _add_email(db, "msg_1", labels=["CATEGORY_PROMOTIONS", "UNREAD"])
    result = await classifier.classify_email("msg_1")
    assert result.classification == "junk"

async def test_keyword_rule(classifier, db):
    await _add_rule(db, "Unsubscribe = junk", "keyword", "unsubscribe", "junk")
    await _add_email(db, "msg_1", body="Click here to unsubscribe from this list")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "junk"

async def test_size_rule(classifier, db):
    await _add_rule(db, "Big emails = keep", "size", ">5000000", "keep", priority=1)
    await _add_email(db, "msg_1", size_bytes=10_000_000)
    result = await classifier.classify_email("msg_1")
    assert result.classification == "keep"

async def test_priority_ordering(classifier, db):
    await _add_rule(db, "Keep important", "label", "IMPORTANT", "keep", priority=1)
    await _add_rule(db, "Promos junk", "label", "CATEGORY_PROMOTIONS", "junk", priority=10)
    await _add_email(db, "msg_1", labels=["IMPORTANT", "CATEGORY_PROMOTIONS"])
    result = await classifier.classify_email("msg_1")
    assert result.classification == "keep"

async def test_no_matching_rule_returns_unclassified(classifier, db):
    await _add_rule(db, "Block spam", "sender", "spam@junk.com", "junk")
    await _add_email(db, "msg_1", sender_email="friend@gmail.com")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "unclassified"

async def test_disabled_rule_skipped(classifier, db):
    await db.execute(
        """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority, enabled)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("Disabled", "sender", "test@test.com", "junk", 1, False),
    )
    await _add_email(db, "msg_1", sender_email="test@test.com")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "unclassified"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_classifier.py -v`
Expected: FAIL

- [ ] **Step 3: Implement classifier**

Create `app/services/classifier.py`:

```python
import fnmatch
import json
import re
from dataclasses import dataclass
from app.database import Database

@dataclass
class ClassificationResult:
    classification: str  # 'keep' | 'junk' | 'unclassified'
    rule_name: str | None = None
    reason: str | None = None

class Classifier:
    def __init__(self, db: Database):
        self.db = db

    async def classify_email(self, email_id: str) -> ClassificationResult:
        email = await self.db.execute_fetchone("SELECT * FROM emails WHERE id = ?", (email_id,))
        if email is None:
            return ClassificationResult(classification="unclassified", reason="Email not found")

        rules = await self.db.execute_fetchall(
            "SELECT * FROM classification_rules WHERE enabled = 1 ORDER BY priority ASC"
        )

        for rule in rules:
            if self._rule_matches(rule, email):
                return ClassificationResult(
                    classification=rule["classification"],
                    rule_name=rule["name"],
                    reason=f"Matched rule: {rule['name']} ({rule['rule_type']}: {rule['pattern']})",
                )

        return ClassificationResult(classification="unclassified", reason="No matching rule")

    def _rule_matches(self, rule, email) -> bool:
        rule_type = rule["rule_type"]
        pattern = rule["pattern"]

        if rule_type == "sender":
            return (email["sender_email"] or "").lower() == pattern.lower()

        elif rule_type == "domain":
            sender = email["sender_email"] or ""
            return fnmatch.fnmatch(sender.lower(), pattern.lower())

        elif rule_type == "label":
            labels_raw = email["labels"] or "[]"
            labels = json.loads(labels_raw) if isinstance(labels_raw, str) else labels_raw
            return pattern in labels

        elif rule_type == "keyword":
            text = f"{email['subject'] or ''} {email['body_text'] or ''}".lower()
            return pattern.lower() in text

        elif rule_type == "size":
            match = re.match(r"([<>])(\d+)", pattern)
            if not match:
                return False
            op, threshold = match.group(1), int(match.group(2))
            size = email["size_bytes"] or 0
            return (size > threshold) if op == ">" else (size < threshold)

        return False
```

- [ ] **Step 4: Run classifier tests**

Run: `pytest tests/test_classifier.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Write rules API tests**

Create `tests/test_api_rules.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app

@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.db_path", tmp_path / "test.db")
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

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
```

- [ ] **Step 6: Implement rules API**

Create `app/api/rules.py`:

```python
from fastapi import APIRouter, HTTPException, Response
from app.models import ClassificationRule
from app.main import db

router = APIRouter(prefix="/api/rules", tags=["rules"])

@router.get("")
async def list_rules():
    rows = await db.execute_fetchall(
        "SELECT * FROM classification_rules ORDER BY priority ASC"
    )
    return [dict(r) for r in rows]

@router.post("", status_code=201)
async def create_rule(rule: ClassificationRule):
    await db.execute(
        """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority, enabled)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (rule.name, rule.rule_type, rule.pattern, rule.classification, rule.priority, rule.enabled),
    )
    row = await db.execute_fetchone(
        "SELECT * FROM classification_rules ORDER BY id DESC LIMIT 1"
    )
    return dict(row)

@router.put("/{rule_id}")
async def update_rule(rule_id: int, rule: ClassificationRule):
    existing = await db.execute_fetchone(
        "SELECT * FROM classification_rules WHERE id = ?", (rule_id,)
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.execute(
        """UPDATE classification_rules
           SET name=?, rule_type=?, pattern=?, classification=?, priority=?, enabled=?
           WHERE id=?""",
        (rule.name, rule.rule_type, rule.pattern, rule.classification,
         rule.priority, rule.enabled, rule_id),
    )
    row = await db.execute_fetchone("SELECT * FROM classification_rules WHERE id = ?", (rule_id,))
    return dict(row)

@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: int):
    existing = await db.execute_fetchone(
        "SELECT * FROM classification_rules WHERE id = ?", (rule_id,)
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.execute("DELETE FROM classification_rules WHERE id = ?", (rule_id,))
    return Response(status_code=204)
```

Wire into `app/main.py`:
```python
from app.api.rules import router as rules_router
app.include_router(rules_router)
```

- [ ] **Step 7: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add app/services/classifier.py app/api/rules.py tests/test_classifier.py tests/test_api_rules.py
git commit -m "feat: classification rule engine with priority ordering and rules CRUD API"
```

---

## Task 4: R2 Storage Service

**Files:**
- Create: `app/services/r2.py`
- Create: `tests/test_r2.py`

- [ ] **Step 1: Add boto3 dependency**

Add `"boto3>=1.35.0"` to `pyproject.toml` dependencies.

- [ ] **Step 2: Write R2 service tests**

Create `tests/test_r2.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.r2 import R2Service
from app.config import Settings

@pytest.fixture
def r2():
    settings = Settings(
        r2_account_id="test_account",
        r2_access_key_id="test_key",
        r2_secret_access_key="test_secret",
        r2_bucket_name="test-bucket",
    )
    with patch("app.services.r2.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        service = R2Service(settings)
        service._client = mock_client
        yield service, mock_client

def test_upload_eml(r2):
    service, mock_client = r2
    key = service.upload_eml("msg_123", b"raw email content", year=2026, month=3)
    assert key == "2026/03/msg_123.eml"
    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="2026/03/msg_123.eml",
        Body=b"raw email content",
        ContentType="message/rfc822",
    )

def test_generate_presigned_url(r2):
    service, mock_client = r2
    mock_client.generate_presigned_url.return_value = "https://r2.example.com/signed"
    url = service.get_download_url("2026/03/msg_123.eml")
    assert url == "https://r2.example.com/signed"
    mock_client.generate_presigned_url.assert_called_once()

def test_delete_eml(r2):
    service, mock_client = r2
    service.delete_eml("2026/03/msg_123.eml")
    mock_client.delete_object.assert_called_once_with(
        Bucket="test-bucket", Key="2026/03/msg_123.eml"
    )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_r2.py -v`
Expected: FAIL

- [ ] **Step 4: Implement R2 service**

Create `app/services/r2.py`:

```python
import boto3
from app.config import Settings

class R2Service:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        self._bucket = settings.r2_bucket_name

    def upload_eml(self, message_id: str, raw_bytes: bytes, year: int, month: int) -> str:
        key = f"{year}/{month:02d}/{message_id}.eml"
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=raw_bytes,
            ContentType="message/rfc822",
        )
        return key

    def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_eml(self, key: str):
        self._client.delete_object(Bucket=self._bucket, Key=key)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_r2.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/r2.py tests/test_r2.py pyproject.toml
git commit -m "feat: R2 storage service for .eml upload, download, and presigned URLs"
```

---

## Task 5: Gmail Service & OAuth

**Files:**
- Create: `app/services/gmail.py`
- Create: `app/api/auth.py`
- Create: `tests/test_gmail.py`

- [ ] **Step 1: Add Gmail dependencies**

Add to `pyproject.toml` dependencies:
```
"google-api-python-client>=2.140.0",
"google-auth-oauthlib>=1.2.0",
"google-auth-httplib2>=0.2.0",
```

- [ ] **Step 2: Write Gmail service tests**

Create `tests/test_gmail.py`:

```python
import pytest
import base64
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.gmail import GmailService

@pytest.fixture
def gmail():
    with patch("app.services.gmail.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        gs = GmailService.__new__(GmailService)
        gs._service = mock_service
        gs._creds = MagicMock()
        yield gs, mock_service

def test_list_messages(gmail):
    gs, mock_service = gmail
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg_1"}, {"id": "msg_2"}],
        "nextPageToken": "token_abc",
        "resultSizeEstimate": 100,
    }
    messages, next_token = gs.list_messages(max_results=10)
    assert len(messages) == 2
    assert next_token == "token_abc"

def test_get_message(gmail):
    gs, mock_service = gmail
    mock_service.users().messages().get().execute.return_value = {
        "id": "msg_1",
        "threadId": "thread_1",
        "labelIds": ["INBOX"],
        "snippet": "Hello world",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "Alice <alice@example.com>"},
                {"name": "Date", "value": "Mon, 24 Mar 2026 10:00:00 +0000"},
            ],
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(b"Hello body").decode()},
        },
        "sizeEstimate": 1234,
    }
    msg = gs.get_message("msg_1")
    assert msg["id"] == "msg_1"
    assert msg["snippet"] == "Hello world"

def test_get_raw_message(gmail):
    gs, mock_service = gmail
    raw_content = b"From: test@test.com\r\nSubject: Test\r\n\r\nBody"
    mock_service.users().messages().get().execute.return_value = {
        "id": "msg_1",
        "raw": base64.urlsafe_b64encode(raw_content).decode(),
    }
    raw = gs.get_raw_message("msg_1")
    assert raw == raw_content

def test_parse_message_headers(gmail):
    gs, _ = gmail
    headers = [
        {"name": "Subject", "value": "Invoice"},
        {"name": "From", "value": "Bob <bob@co.com>"},
        {"name": "To", "value": "alice@test.com"},
        {"name": "Date", "value": "Mon, 24 Mar 2026 10:00:00 +0000"},
    ]
    parsed = gs.parse_headers(headers)
    assert parsed["subject"] == "Invoice"
    assert parsed["from"] == "Bob <bob@co.com>"

def test_trash_messages(gmail):
    gs, mock_service = gmail
    gs.trash_messages(["msg_1", "msg_2"])
    assert mock_service.users().messages().trash.call_count == 2

def test_list_history(gmail):
    gs, mock_service = gmail
    mock_service.users().history().list().execute.return_value = {
        "history": [{"messagesAdded": [{"message": {"id": "msg_new"}}]}],
        "historyId": "12345",
    }
    history, new_id = gs.list_history("11111")
    assert new_id == "12345"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_gmail.py -v`
Expected: FAIL

- [ ] **Step 4: Implement Gmail service**

Create `app/services/gmail.py`:

```python
import base64
import re
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

class GmailService:
    def __init__(self, client_secret_path: Path, token_path: Path):
        self._client_secret_path = client_secret_path
        self._token_path = token_path
        self._creds: Credentials | None = None
        self._service = None

    def authenticate(self) -> bool:
        """Load or refresh credentials. Returns True if authenticated."""
        if self._token_path.exists():
            self._creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)
        if self._creds and self._creds.expired and self._creds.refresh_token:
            self._creds.refresh(Request())
            self._save_token()
        if self._creds and self._creds.valid:
            self._service = build("gmail", "v1", credentials=self._creds)
            return True
        return False

    def start_oauth_flow(self, redirect_uri: str = "http://localhost:8000/api/auth/callback"):
        """Start OAuth flow and return authorization URL."""
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self._client_secret_path), SCOPES,
            redirect_uri=redirect_uri,
        )
        auth_url, _ = flow.authorization_url(prompt="consent")
        self._flow = flow
        return auth_url

    def complete_oauth_flow(self, code: str):
        """Complete OAuth with authorization code."""
        self._flow.fetch_token(code=code)
        self._creds = self._flow.credentials
        self._save_token()
        self._service = build("gmail", "v1", credentials=self._creds)

    def _save_token(self):
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(self._creds.to_json())

    @property
    def is_authenticated(self) -> bool:
        return self._creds is not None and self._creds.valid

    def list_messages(self, max_results=500, page_token=None, query=None):
        """List message IDs with pagination."""
        kwargs = {"userId": "me", "maxResults": max_results}
        if page_token:
            kwargs["pageToken"] = page_token
        if query:
            kwargs["q"] = query
        result = self._service.users().messages().list(**kwargs).execute()
        messages = result.get("messages", [])
        next_token = result.get("nextPageToken")
        return messages, next_token

    def get_message(self, msg_id: str, format="full"):
        """Get a single message."""
        return self._service.users().messages().get(
            userId="me", id=msg_id, format=format
        ).execute()

    def get_raw_message(self, msg_id: str) -> bytes:
        """Get raw RFC 2822 message bytes (.eml content)."""
        result = self._service.users().messages().get(
            userId="me", id=msg_id, format="raw"
        ).execute()
        return base64.urlsafe_b64decode(result["raw"])

    def trash_messages(self, msg_ids: list[str]):
        """Move messages to trash."""
        for msg_id in msg_ids:
            self._service.users().messages().trash(userId="me", id=msg_id).execute()

    def delete_messages(self, msg_ids: list[str]):
        """Permanently delete messages."""
        for msg_id in msg_ids:
            self._service.users().messages().delete(userId="me", id=msg_id).execute()

    def list_history(self, start_history_id: str):
        """Get changes since a history ID. Returns (history_records, new_history_id)."""
        try:
            result = self._service.users().history().list(
                userId="me", startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
            ).execute()
            return result.get("history", []), result.get("historyId")
        except Exception as e:
            if "404" in str(e) or "historyId" in str(e).lower():
                return None, None  # Signal to caller: need full sync
            raise

    def get_profile(self):
        """Get authenticated user's email address."""
        return self._service.users().getProfile(userId="me").execute()

    @staticmethod
    def parse_headers(headers: list[dict]) -> dict:
        """Extract common headers into a dict."""
        result = {}
        for h in headers:
            name = h["name"].lower()
            if name in ("subject", "from", "to", "cc", "bcc", "date"):
                result[name] = h["value"]
        return result

    @staticmethod
    def extract_email_address(from_header: str) -> str:
        """Extract email from 'Name <email>' format."""
        match = re.search(r"<(.+?)>", from_header)
        return match.group(1) if match else from_header
```

- [ ] **Step 5: Implement auth API**

Create `app/api/auth.py`:

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from app.config import settings
from app.services.gmail import GmailService

router = APIRouter(prefix="/api/auth", tags=["auth"])

_gmail = GmailService(settings.client_secret_path, settings.token_path)

def get_gmail_service() -> GmailService:
    return _gmail

@router.get("/status")
async def auth_status():
    authenticated = _gmail.authenticate()
    if authenticated:
        profile = _gmail.get_profile()
        return {"authenticated": True, "email": profile.get("emailAddress")}
    has_client_secret = settings.client_secret_path.exists()
    return {"authenticated": False, "has_client_secret": has_client_secret}

@router.post("/start")
async def start_auth():
    if not settings.client_secret_path.exists():
        raise HTTPException(
            status_code=400,
            detail="client_secret.json not found. Download it from Google Cloud Console "
                   f"and place it at {settings.client_secret_path}",
        )
    auth_url = _gmail.start_oauth_flow()
    return {"auth_url": auth_url}

@router.get("/callback")
async def auth_callback(code: str):
    _gmail.complete_oauth_flow(code)
    return RedirectResponse(url="/")
```

Wire into `app/main.py`:
```python
from app.api.auth import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/gmail.py app/api/auth.py tests/test_gmail.py pyproject.toml
git commit -m "feat: Gmail service with OAuth flow, message operations, and history API"
```

---

## Task 6: Sync Manager & Background Tasks

**Files:**
- Create: `app/services/task_manager.py`
- Create: `app/services/sync_manager.py`
- Create: `app/api/sync.py`
- Create: `tests/test_sync_manager.py`

- [ ] **Step 1: Write task manager and sync manager tests**

Create `tests/test_sync_manager.py`:

```python
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
    classifier = Classifier(db)
    return SyncManager(db, mock_gmail, mock_r2, classifier, tm)

async def test_task_manager_sync_lock(task_mgr):
    """Only one sync runs at a time."""
    acquired = await task_mgr.acquire_sync_lock()
    assert acquired is True
    acquired2 = await task_mgr.acquire_sync_lock()
    assert acquired2 is False
    task_mgr.release_sync_lock()
    acquired3 = await task_mgr.acquire_sync_lock()
    assert acquired3 is True
    task_mgr.release_sync_lock()

async def test_deletion_waits_for_sync(task_mgr):
    """Deletion lock waits while sync is active."""
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
    """Sync manager inserts emails from Gmail into DB."""
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
                "body": {"data": "SGVsbG8="},  # "Hello"
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
                "body": {"data": "V29ybGQ="},  # "World"
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
    """Sync does not overwrite emails already in the DB."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync_manager.py -v`
Expected: FAIL

- [ ] **Step 3: Implement task manager**

Create `app/services/task_manager.py`:

```python
import asyncio
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class TaskProgress:
    task_id: str
    task_type: str
    status: str = "pending"  # pending | running | completed | failed
    total: int = 0
    processed: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

class TaskManager:
    def __init__(self):
        self._sync_active = False
        self._sync_event = asyncio.Event()
        self._sync_event.set()  # Initially not syncing
        self._tasks: dict[str, TaskProgress] = {}
        self._counter = 0

    async def acquire_sync_lock(self) -> bool:
        """Atomically acquire sync lock. Returns False if already held.
        Safe because asyncio is single-threaded — no await between check and set."""
        if self._sync_active:
            return False
        self._sync_active = True
        self._sync_event.clear()
        return True

    def release_sync_lock(self):
        self._sync_active = False
        self._sync_event.set()

    async def wait_for_sync_complete(self):
        await self._sync_event.wait()

    def create_task(self, task_type: str) -> TaskProgress:
        self._counter += 1
        task = TaskProgress(
            task_id=f"{task_type}_{self._counter}",
            task_type=task_type,
            started_at=datetime.utcnow(),
            status="running",
        )
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> TaskProgress | None:
        return self._tasks.get(task_id)

    @property
    def is_syncing(self) -> bool:
        return self._sync_active
```

- [ ] **Step 4: Implement sync manager**

Create `app/services/sync_manager.py`:

```python
import base64
import json
import logging
from datetime import datetime
from app.database import Database
from app.services.gmail import GmailService
from app.services.r2 import R2Service
from app.services.classifier import Classifier
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)

class SyncManager:
    def __init__(
        self,
        db: Database,
        gmail: GmailService,
        r2: R2Service,
        classifier: Classifier,
        task_manager: TaskManager,
    ):
        self._db = db
        self._gmail = gmail
        self._r2 = r2
        self._classifier = classifier
        self._task_manager = task_manager

    async def run_full_sync(self):
        """Full paginated sync of all messages. Acquires sync lock."""
        acquired = await self._task_manager.acquire_sync_lock()
        if not acquired:
            raise RuntimeError("Sync already in progress")
        try:
            await self._do_full_sync()
        finally:
            self._task_manager.release_sync_lock()

    async def run_incremental_sync(self):
        """Sync only new messages since last history ID. Acquires sync lock."""
        acquired = await self._task_manager.acquire_sync_lock()
        if not acquired:
            raise RuntimeError("Sync already in progress")
        try:
            state = await self._db.execute_fetchone("SELECT * FROM sync_state WHERE id = 1")
            history_id = state["last_history_id"]

            if not history_id:
                # No history ID yet — do a full sync (lock already held)
                await self._do_full_sync()
                return

            history, new_id = self._gmail.list_history(history_id)
            if history is None:
                # History ID expired — fall back to full sync (lock already held)
                logger.warning("History ID expired, falling back to full sync")
                await self._do_full_sync()
                return

            for record in history:
                for added in record.get("messagesAdded", []):
                    msg_id = added["message"]["id"]
                    existing = await self._db.execute_fetchone(
                        "SELECT id FROM emails WHERE id = ?", (msg_id,)
                    )
                    if not existing:
                        await self._process_message(msg_id)

            if new_id:
                await self._db.execute(
                    "UPDATE sync_state SET last_history_id = ? WHERE id = 1",
                    (new_id,),
                )
        finally:
            self._task_manager.release_sync_lock()

    async def _do_full_sync(self):
        """Internal full sync — caller must hold sync lock."""
        profile = self._gmail.get_profile()
        await self._db.execute(
            "UPDATE sync_state SET account_email = ? WHERE id = 1",
            (profile.get("emailAddress"),),
        )

        page_token = None
        total_synced = 0
        while True:
            messages, page_token = self._gmail.list_messages(
                max_results=500, page_token=page_token
            )
            if not messages:
                break

            for msg_ref in messages:
                msg_id = msg_ref["id"]
                existing = await self._db.execute_fetchone(
                    "SELECT id FROM emails WHERE id = ?", (msg_id,)
                )
                if existing:
                    continue

                await self._process_message(msg_id)
                total_synced += 1

            if not page_token:
                break

        await self._db.execute(
            """UPDATE sync_state SET last_full_sync = ?, synced_messages = synced_messages + ?
               WHERE id = 1""",
            (datetime.utcnow().isoformat(), total_synced),
        )

    async def _process_message(self, msg_id: str):
        """Fetch, parse, classify, store a single message."""
        msg = self._gmail.get_message(msg_id)
        headers = self._gmail.parse_headers(msg.get("payload", {}).get("headers", []))
        sender_raw = headers.get("from", "")
        sender_email = self._gmail.extract_email_address(sender_raw)

        # Extract body text
        body_text = self._extract_body(msg.get("payload", {}))

        # Parse date
        date_str = headers.get("date", "")

        # Build email record
        labels = msg.get("labelIds", [])
        now = datetime.utcnow().isoformat()

        await self._db.execute(
            """INSERT INTO emails (id, thread_id, subject, sender, sender_email,
               recipients, date, snippet, body_text, labels, size_bytes,
               has_attachments, classification, synced_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unclassified', ?, ?)""",
            (
                msg["id"], msg.get("threadId"), headers.get("subject", ""),
                sender_raw, sender_email,
                json.dumps({"to": headers.get("to", ""), "cc": headers.get("cc", "")}),
                date_str, msg.get("snippet", ""), body_text,
                json.dumps(labels), msg.get("sizeEstimate", 0),
                self._has_attachments(msg.get("payload", {})),
                now, now,
            ),
        )

        # Index in FTS5
        await self._db.execute(
            """INSERT INTO emails_fts (rowid, subject, sender, body_text, snippet)
               VALUES ((SELECT rowid FROM emails WHERE id = ?), ?, ?, ?, ?)""",
            (msg["id"], headers.get("subject", ""), sender_raw, body_text, msg.get("snippet", "")),
        )

        # Run classifier
        result = await self._classifier.classify_email(msg["id"])
        if result.classification != "unclassified":
            await self._db.execute(
                """UPDATE emails SET classification = ?, classification_reason = ?,
                   classified_at = ? WHERE id = ?""",
                (result.classification, result.reason, now, msg["id"]),
            )

        # Upload .eml to R2 if not junk
        classification = result.classification
        if classification != "junk":
            try:
                raw = self._gmail.get_raw_message(msg_id)
                parsed_date = datetime.utcnow()  # Fallback
                try:
                    from email.utils import parsedate_to_datetime
                    parsed_date = parsedate_to_datetime(date_str)
                except Exception:
                    pass
                eml_path = self._r2.upload_eml(
                    msg_id, raw, year=parsed_date.year, month=parsed_date.month
                )
                await self._db.execute(
                    "UPDATE emails SET eml_path = ? WHERE id = ?", (eml_path, msg_id)
                )
            except Exception as e:
                logger.error(f"Failed to upload .eml for {msg_id}: {e}")

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain text body from message payload."""
        mime_type = payload.get("mimeType", "")
        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            text = self._extract_body(part)
            if text:
                return text
        return ""

    def _has_attachments(self, payload: dict) -> bool:
        """Check if message has file attachments."""
        for part in payload.get("parts", []):
            if part.get("filename"):
                return True
            if self._has_attachments(part):
                return True
        return False
```

- [ ] **Step 5: Implement sync API**

Create `app/api/sync.py`:

```python
import asyncio
from fastapi import APIRouter, HTTPException
from app.main import db
from app.services.task_manager import TaskManager

router = APIRouter(prefix="/api/sync", tags=["sync"])

# These will be properly initialized in main.py lifespan
_task_manager: TaskManager | None = None
_sync_manager = None

def init_sync(task_manager, sync_manager):
    global _task_manager, _sync_manager
    _task_manager = task_manager
    _sync_manager = sync_manager

@router.post("")
async def trigger_sync(full: bool = False):
    if _sync_manager is None:
        raise HTTPException(status_code=503, detail="Gmail not configured")
    if _task_manager.is_syncing:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    task = _task_manager.create_task("sync")

    async def run():
        try:
            if full:
                await _sync_manager.run_full_sync()
            else:
                await _sync_manager.run_incremental_sync()
            task.status = "completed"
        except Exception as e:
            task.status = "failed"
            task.error = str(e)

    asyncio.create_task(run())
    return {"task_id": task.task_id, "status": "started"}

@router.get("/status")
async def sync_status():
    state = await db.execute_fetchone("SELECT * FROM sync_state WHERE id = 1")
    return {
        "is_syncing": _task_manager.is_syncing if _task_manager else False,
        "account_email": state["account_email"] if state else None,
        "last_history_id": state["last_history_id"] if state else None,
        "last_full_sync": state["last_full_sync"] if state else None,
        "synced_messages": state["synced_messages"] if state else 0,
    }
```

Wire into `app/main.py`:
```python
from app.api.sync import router as sync_router
app.include_router(sync_router)
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/task_manager.py app/services/sync_manager.py app/api/sync.py tests/test_sync_manager.py
git commit -m "feat: sync manager with concurrency locks, incremental sync, and .eml export"
```

---

## Task 7: Deletion Manager & Schedules

**Files:**
- Create: `app/services/deletion_manager.py`
- Create: `app/services/scheduler.py`
- Create: `app/api/schedules.py`
- Create: `app/api/stats.py`
- Create: `tests/test_deletion_manager.py`
- Create: `tests/test_api_schedules.py`

- [ ] **Step 1: Add APScheduler dependency**

Add `"apscheduler>=3.10.0"` to `pyproject.toml` dependencies.

- [ ] **Step 2: Write deletion manager tests**

Create `tests/test_deletion_manager.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_deletion_manager.py -v`
Expected: FAIL

- [ ] **Step 4: Implement deletion manager**

Create `app/services/deletion_manager.py`:

```python
import logging
from datetime import datetime
from app.database import Database
from app.services.gmail import GmailService
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)

BATCH_SIZE = 100

class DeletionManager:
    def __init__(self, db: Database, gmail: GmailService, task_manager: TaskManager):
        self._db = db
        self._gmail = gmail
        self._task_manager = task_manager

    async def delete_emails(
        self,
        email_ids: list[str],
        trigger: str,
        permanent: bool = False,
        schedule_id: int | None = None,
    ) -> dict:
        await self._task_manager.wait_for_sync_complete()

        to_delete = []
        skipped = 0
        for eid in email_ids:
            row = await self._db.execute_fetchone(
                "SELECT id, deleted_from_gmail FROM emails WHERE id = ?", (eid,)
            )
            if row and not row["deleted_from_gmail"]:
                to_delete.append(eid)
            else:
                skipped += 1

        # Batch delete via Gmail API
        for i in range(0, len(to_delete), BATCH_SIZE):
            batch = to_delete[i : i + BATCH_SIZE]
            if permanent:
                self._gmail.delete_messages(batch)
            else:
                self._gmail.trash_messages(batch)

        # Update DB
        now = datetime.utcnow().isoformat()
        deletion_type = "permanently_deleted" if permanent else "trashed"
        for eid in to_delete:
            await self._db.execute(
                """UPDATE emails SET deleted_from_gmail = 1, deletion_type = ?, updated_at = ?
                   WHERE id = ?""",
                (deletion_type, now, eid),
            )
            await self._db.execute(
                """INSERT INTO deletion_log (schedule_id, email_id, deleted_at, trigger)
                   VALUES (?, ?, ?, ?)""",
                (schedule_id, eid, now, trigger),
            )

        return {"deleted": len(to_delete), "skipped": skipped}

    async def delete_by_filter(
        self,
        filter_rules: dict,
        require_classification: bool = True,
        trigger: str = "scheduled",
        permanent: bool = False,
        schedule_id: int | None = None,
    ) -> dict:
        conditions = ["deleted_from_gmail = 0"]
        params = []

        if require_classification:
            conditions.append("classification = 'junk'")

        if "sender_email" in filter_rules:
            conditions.append("sender_email = ?")
            params.append(filter_rules["sender_email"])

        if "domain" in filter_rules:
            conditions.append("sender_email LIKE ?")
            params.append(f"%{filter_rules['domain']}")

        if "label" in filter_rules:
            conditions.append("labels LIKE ?")
            params.append(f'%"{filter_rules["label"]}"%')

        if "classification" in filter_rules:
            conditions.append("classification = ?")
            params.append(filter_rules["classification"])

        where = " AND ".join(conditions)
        rows = await self._db.execute_fetchall(
            f"SELECT id FROM emails WHERE {where}", tuple(params)
        )
        email_ids = [r["id"] for r in rows]

        if not email_ids:
            return {"deleted": 0, "skipped": 0}

        return await self.delete_emails(
            email_ids, trigger=trigger, permanent=permanent, schedule_id=schedule_id
        )
```

- [ ] **Step 5: Run deletion tests**

Run: `pytest tests/test_deletion_manager.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Implement scheduler service**

Create `app/services/scheduler.py`:

```python
import json
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import Database

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self, db: Database):
        self._db = db
        self._scheduler = AsyncIOScheduler()
        self._deletion_manager = None  # Set after init to avoid circular deps

    def set_deletion_manager(self, dm):
        self._deletion_manager = dm

    async def start(self):
        """Load schedules from DB and start the scheduler."""
        schedules = await self._db.execute_fetchall(
            "SELECT * FROM deletion_schedules WHERE enabled = 1"
        )
        for s in schedules:
            self._add_job(s)
        self._scheduler.start()

    def stop(self):
        self._scheduler.shutdown(wait=False)

    def _add_job(self, schedule):
        job_id = f"deletion_{schedule['id']}"
        try:
            trigger = CronTrigger.from_crontab(schedule["cron_expression"])
            self._scheduler.add_job(
                self._run_deletion,
                trigger=trigger,
                id=job_id,
                args=[schedule["id"]],
                replace_existing=True,
            )
        except Exception as e:
            logger.error(f"Failed to add schedule {schedule['id']}: {e}")

    async def _run_deletion(self, schedule_id: int):
        schedule = await self._db.execute_fetchone(
            "SELECT * FROM deletion_schedules WHERE id = ? AND enabled = 1",
            (schedule_id,),
        )
        if not schedule or not self._deletion_manager:
            return

        filter_rules = json.loads(schedule["filter_rules"])
        await self._deletion_manager.delete_by_filter(
            filter_rules=filter_rules,
            require_classification=bool(schedule["require_classification"]),
            trigger="scheduled",
            schedule_id=schedule_id,
        )

        from datetime import datetime
        await self._db.execute(
            "UPDATE deletion_schedules SET last_run = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), schedule_id),
        )

    async def add_schedule(self, schedule_id: int):
        s = await self._db.execute_fetchone(
            "SELECT * FROM deletion_schedules WHERE id = ?", (schedule_id,)
        )
        if s and s["enabled"]:
            self._add_job(s)

    def remove_schedule(self, schedule_id: int):
        job_id = f"deletion_{schedule_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
```

- [ ] **Step 7: Implement schedules API and stats API**

Create `app/api/schedules.py`:

```python
import json
from fastapi import APIRouter, HTTPException, Response
from app.models import DeletionSchedule
from app.main import db

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

_scheduler_service = None

def init_scheduler(scheduler_service):
    global _scheduler_service
    _scheduler_service = scheduler_service

@router.get("")
async def list_schedules():
    rows = await db.execute_fetchall("SELECT * FROM deletion_schedules ORDER BY id")
    result = []
    for r in rows:
        d = dict(r)
        d["filter_rules"] = json.loads(d["filter_rules"]) if isinstance(d["filter_rules"], str) else d["filter_rules"]
        result.append(d)
    return result

@router.post("", status_code=201)
async def create_schedule(schedule: DeletionSchedule):
    await db.execute(
        """INSERT INTO deletion_schedules (name, cron_expression, filter_rules,
           require_classification, enabled)
           VALUES (?, ?, ?, ?, ?)""",
        (schedule.name, schedule.cron_expression, json.dumps(schedule.filter_rules),
         schedule.require_classification, schedule.enabled),
    )
    row = await db.execute_fetchone(
        "SELECT * FROM deletion_schedules ORDER BY id DESC LIMIT 1"
    )
    if _scheduler_service and row["enabled"]:
        await _scheduler_service.add_schedule(row["id"])
    d = dict(row)
    d["filter_rules"] = json.loads(d["filter_rules"])
    return d

@router.put("/{schedule_id}")
async def update_schedule(schedule_id: int, schedule: DeletionSchedule):
    existing = await db.execute_fetchone(
        "SELECT * FROM deletion_schedules WHERE id = ?", (schedule_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.execute(
        """UPDATE deletion_schedules SET name=?, cron_expression=?, filter_rules=?,
           require_classification=?, enabled=? WHERE id=?""",
        (schedule.name, schedule.cron_expression, json.dumps(schedule.filter_rules),
         schedule.require_classification, schedule.enabled, schedule_id),
    )
    if _scheduler_service:
        _scheduler_service.remove_schedule(schedule_id)
        if schedule.enabled:
            await _scheduler_service.add_schedule(schedule_id)
    row = await db.execute_fetchone("SELECT * FROM deletion_schedules WHERE id = ?", (schedule_id,))
    d = dict(row)
    d["filter_rules"] = json.loads(d["filter_rules"])
    return d

@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: int):
    existing = await db.execute_fetchone(
        "SELECT * FROM deletion_schedules WHERE id = ?", (schedule_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if _scheduler_service:
        _scheduler_service.remove_schedule(schedule_id)
    await db.execute("DELETE FROM deletion_schedules WHERE id = ?", (schedule_id,))
    return Response(status_code=204)
```

Create `app/api/stats.py`:

```python
from fastapi import APIRouter
from app.main import db

router = APIRouter(prefix="/api/stats", tags=["stats"])

@router.get("")
async def get_stats():
    total = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails")
    keep = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='keep'")
    junk = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='junk'")
    unclassified = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='unclassified'")
    deleted = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE deleted_from_gmail=1")
    size = await db.execute_fetchone("SELECT COALESCE(SUM(size_bytes), 0) as total FROM emails")
    return {
        "total_emails": total["cnt"],
        "classified_keep": keep["cnt"],
        "classified_junk": junk["cnt"],
        "unclassified": unclassified["cnt"],
        "deleted_from_gmail": deleted["cnt"],
        "total_size_bytes": size["total"],
    }
```

Wire both into `app/main.py`:
```python
from app.api.schedules import router as schedules_router
from app.api.stats import router as stats_router
app.include_router(schedules_router)
app.include_router(stats_router)
```

- [ ] **Step 8: Write schedule API tests**

Create `tests/test_api_schedules.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app

@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.db_path", tmp_path / "test.db")
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

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
```

- [ ] **Step 9: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add app/services/deletion_manager.py app/services/scheduler.py app/api/schedules.py app/api/stats.py tests/test_deletion_manager.py tests/test_api_schedules.py pyproject.toml
git commit -m "feat: deletion manager with batching, scheduler service, schedules/stats API"
```

---

## Task 8: MCP Server

**Files:**
- Create: `app/mcp/__init__.py`
- Create: `app/mcp/server.py`
- Create: `app/mcp/tools.py`
- Create: `tests/test_mcp_tools.py`

- [ ] **Step 1: Add MCP dependency**

Add `"mcp>=1.0.0"` to `pyproject.toml` dependencies.

- [ ] **Step 2: Write MCP tool tests**

Create `tests/test_mcp_tools.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.mcp.tools import McpTools

@pytest.fixture
async def mcp_tools(db):
    from app.services.search import SearchService
    from app.services.classifier import Classifier
    from app.services.task_manager import TaskManager
    search = SearchService(db)
    classifier = Classifier(db)
    task_mgr = TaskManager()
    tools = McpTools(
        db=db, search=search, classifier=classifier,
        task_manager=task_mgr, gmail=MagicMock(),
        r2=MagicMock(), sync_manager=MagicMock(),
        deletion_manager=MagicMock(), scheduler=MagicMock(),
    )
    return tools

async def _seed(db):
    for i in range(3):
        await db.execute(
            """INSERT INTO emails (id, subject, sender_email, body_text, snippet,
               classification, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (f"msg_{i}", f"Subject {i}", f"s{i}@test.com", f"Body {i}", f"Snippet {i}",
             "keep" if i < 2 else "junk"),
        )
        await db.execute(
            """INSERT INTO emails_fts (rowid, subject, sender, body_text, snippet)
               VALUES ((SELECT rowid FROM emails WHERE id = ?), ?, ?, ?, ?)""",
            (f"msg_{i}", f"Subject {i}", f"Sender {i}", f"Body {i}", f"Snippet {i}"),
        )

async def test_search_emails_tool(mcp_tools, db):
    await _seed(db)
    result = await mcp_tools.search_emails(query="Subject")
    assert result["total"] == 3

async def test_get_email_tool(mcp_tools, db):
    await _seed(db)
    result = await mcp_tools.get_email(email_id="msg_0")
    assert result["id"] == "msg_0"

async def test_get_stats_tool(mcp_tools, db):
    await _seed(db)
    result = await mcp_tools.get_stats()
    assert result["total_emails"] == 3
    assert result["classified_keep"] == 2
    assert result["classified_junk"] == 1

async def test_classify_emails_tool(mcp_tools, db):
    await _seed(db)
    result = await mcp_tools.classify_emails(email_ids=["msg_2"], classification="keep")
    assert result["updated"] == 1
    row = await db.execute_fetchone("SELECT classification FROM emails WHERE id = 'msg_2'")
    assert row["classification"] == "keep"

async def test_list_rules_tool(mcp_tools, db):
    await db.execute(
        """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority)
           VALUES (?, ?, ?, ?, ?)""",
        ("Test Rule", "sender", "spam@junk.com", "junk", 10),
    )
    result = await mcp_tools.list_rules()
    assert len(result) == 1
    assert result[0]["name"] == "Test Rule"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_mcp_tools.py -v`
Expected: FAIL

- [ ] **Step 4: Implement MCP tools**

Create `app/mcp/__init__.py` (empty) and `app/mcp/tools.py`:

```python
from datetime import datetime
from app.database import Database
from app.services.search import SearchService
from app.services.classifier import Classifier
from app.services.task_manager import TaskManager

class McpTools:
    def __init__(self, db, search, classifier, task_manager, gmail, r2,
                 sync_manager, deletion_manager, scheduler):
        self._db = db
        self._search = search
        self._classifier = classifier
        self._task_manager = task_manager
        self._gmail = gmail
        self._r2 = r2
        self._sync_manager = sync_manager
        self._deletion_manager = deletion_manager
        self._scheduler = scheduler

    # --- Search & Read ---
    async def search_emails(self, query=None, classification=None, sender=None,
                            date_after=None, date_before=None, has_attachments=None,
                            page=1, page_size=50):
        result = await self._search.search(
            query=query, classification=classification, sender=sender,
            date_after=date_after, date_before=date_before,
            has_attachments=has_attachments, page=page, page_size=page_size,
        )
        return {"emails": [e.model_dump() for e in result.emails],
                "total": result.total, "page": result.page, "page_size": result.page_size}

    async def get_email(self, email_id):
        email = await self._search.get_email(email_id)
        if email is None:
            return {"error": "Email not found"}
        return email.model_dump()

    async def download_eml(self, email_id):
        email = await self._search.get_email(email_id)
        if email is None:
            return {"error": "Email not found"}
        if not email.eml_path or email.eml_path == "unrecoverable":
            return {"error": "No .eml file available"}
        url = self._r2.get_download_url(email.eml_path)
        return {"url": url, "email_id": email_id}

    async def get_stats(self):
        total = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails")
        keep = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='keep'")
        junk = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='junk'")
        unclassified = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='unclassified'")
        deleted = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE deleted_from_gmail=1")
        size = await self._db.execute_fetchone("SELECT COALESCE(SUM(size_bytes), 0) as total FROM emails")
        return {
            "total_emails": total["cnt"], "classified_keep": keep["cnt"],
            "classified_junk": junk["cnt"], "unclassified": unclassified["cnt"],
            "deleted_from_gmail": deleted["cnt"], "total_size_bytes": size["total"],
        }

    # --- Sync & Classify ---
    async def trigger_sync(self, full=False):
        if self._task_manager.is_syncing:
            return {"error": "Sync already in progress"}
        import asyncio
        task = self._task_manager.create_task("sync")
        async def run():
            try:
                if full:
                    await self._sync_manager.run_full_sync()
                else:
                    await self._sync_manager.run_incremental_sync()
                task.status = "completed"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
        asyncio.create_task(run())
        return {"task_id": task.task_id, "status": "started"}

    async def get_sync_status(self):
        state = await self._db.execute_fetchone("SELECT * FROM sync_state WHERE id = 1")
        return {
            "is_syncing": self._task_manager.is_syncing,
            "account_email": state["account_email"] if state else None,
            "last_history_id": state["last_history_id"] if state else None,
            "last_full_sync": state["last_full_sync"] if state else None,
            "synced_messages": state["synced_messages"] if state else 0,
        }

    async def classify_emails(self, email_ids, classification):
        now = datetime.utcnow().isoformat()
        for eid in email_ids:
            await self._db.execute(
                """UPDATE emails SET classification=?, classified_at=?, updated_at=?
                   WHERE id=?""",
                (classification, now, now, eid),
            )
        return {"updated": len(email_ids), "classification": classification}

    async def classify_by_sender(self, sender_email, classification):
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """UPDATE emails SET classification=?, classified_at=?, updated_at=?
               WHERE sender_email=?""",
            (classification, now, now, sender_email),
        )
        row = await self._db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM emails WHERE sender_email=?", (sender_email,)
        )
        return {"updated": row["cnt"], "sender_email": sender_email, "classification": classification}

    # --- Delete & Schedule ---
    async def delete_emails(self, email_ids, confirm=False):
        if not confirm:
            return {"error": "Must set confirm=true to delete"}
        return await self._deletion_manager.delete_emails(email_ids, trigger="agent")

    async def delete_by_filter(self, filter_rules, confirm=False, permanent=False):
        if not confirm:
            return {"error": "Must set confirm=true to delete"}
        return await self._deletion_manager.delete_by_filter(
            filter_rules=filter_rules, trigger="agent", permanent=permanent,
        )

    async def create_schedule(self, name, cron_expression, filter_rules,
                              require_classification=True):
        import json
        await self._db.execute(
            """INSERT INTO deletion_schedules (name, cron_expression, filter_rules, require_classification)
               VALUES (?, ?, ?, ?)""",
            (name, cron_expression, json.dumps(filter_rules), require_classification),
        )
        row = await self._db.execute_fetchone(
            "SELECT * FROM deletion_schedules ORDER BY id DESC LIMIT 1"
        )
        if self._scheduler:
            await self._scheduler.add_schedule(row["id"])
        return dict(row)

    async def update_schedule(self, schedule_id, **kwargs):
        import json
        sets, params = [], []
        for key in ("name", "cron_expression", "require_classification", "enabled"):
            if key in kwargs:
                sets.append(f"{key}=?")
                params.append(kwargs[key])
        if "filter_rules" in kwargs:
            sets.append("filter_rules=?")
            params.append(json.dumps(kwargs["filter_rules"]))
        if not sets:
            return {"error": "No fields to update"}
        params.append(schedule_id)
        await self._db.execute(
            f"UPDATE deletion_schedules SET {','.join(sets)} WHERE id=?", tuple(params),
        )
        return {"updated": schedule_id}

    async def list_schedules(self):
        import json
        rows = await self._db.execute_fetchall("SELECT * FROM deletion_schedules ORDER BY id")
        result = []
        for r in rows:
            d = dict(r)
            d["filter_rules"] = json.loads(d["filter_rules"]) if isinstance(d["filter_rules"], str) else d["filter_rules"]
            result.append(d)
        return result

    async def delete_schedule(self, schedule_id):
        await self._db.execute("DELETE FROM deletion_schedules WHERE id=?", (schedule_id,))
        if self._scheduler:
            self._scheduler.remove_schedule(schedule_id)
        return {"deleted": schedule_id}

    # --- Rules & Config ---
    async def create_rule(self, name, rule_type, pattern, classification, priority=100):
        await self._db.execute(
            """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority)
               VALUES (?, ?, ?, ?, ?)""",
            (name, rule_type, pattern, classification, priority),
        )
        row = await self._db.execute_fetchone(
            "SELECT * FROM classification_rules ORDER BY id DESC LIMIT 1"
        )
        return dict(row)

    async def update_rule(self, rule_id, **kwargs):
        sets, params = [], []
        for key in ("name", "rule_type", "pattern", "classification", "priority", "enabled"):
            if key in kwargs:
                sets.append(f"{key}=?")
                params.append(kwargs[key])
        if not sets:
            return {"error": "No fields to update"}
        params.append(rule_id)
        await self._db.execute(
            f"UPDATE classification_rules SET {','.join(sets)} WHERE id=?", tuple(params),
        )
        return {"updated": rule_id}

    async def list_rules(self):
        rows = await self._db.execute_fetchall(
            "SELECT * FROM classification_rules ORDER BY priority ASC"
        )
        return [dict(r) for r in rows]

    async def delete_rule(self, rule_id):
        await self._db.execute("DELETE FROM classification_rules WHERE id=?", (rule_id,))
        return {"deleted": rule_id}

    async def get_config(self):
        from app.config import settings
        return {
            "sync_interval_minutes": settings.sync_interval_minutes,
            "r2_bucket_name": settings.r2_bucket_name,
            "r2_configured": bool(settings.r2_access_key_id),
            "gmail_configured": settings.token_path.exists(),
        }

    async def update_config(self, **kwargs):
        return {"error": "Runtime config update not yet implemented"}
```

- [ ] **Step 5: Implement MCP server**

Create `app/mcp/server.py`:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("GmailVault", description="Gmail management and archival system")

_tools = None

def init_mcp_tools(tools):
    global _tools
    _tools = tools

@mcp.tool()
async def search_emails(query: str = "", classification: str = "", sender: str = "",
                        date_after: str = "", date_before: str = "",
                        page: int = 1, page_size: int = 50) -> dict:
    """Search archived emails with filters. Returns paginated results."""
    return await _tools.search_emails(
        query=query or None, classification=classification or None,
        sender=sender or None, date_after=date_after or None,
        date_before=date_before or None, page=page, page_size=page_size,
    )

@mcp.tool()
async def get_email(email_id: str) -> dict:
    """Get full email details by Gmail message ID."""
    return await _tools.get_email(email_id)

@mcp.tool()
async def download_eml(email_id: str) -> dict:
    """Get a pre-signed R2 URL to download the .eml file."""
    return await _tools.download_eml(email_id)

@mcp.tool()
async def get_stats() -> dict:
    """Get archive statistics: counts by classification, storage usage."""
    return await _tools.get_stats()

@mcp.tool()
async def trigger_sync(full: bool = False) -> dict:
    """Start a Gmail sync. Set full=True for full sync, False for incremental."""
    return await _tools.trigger_sync(full=full)

@mcp.tool()
async def get_sync_status() -> dict:
    """Check current sync status and progress."""
    return await _tools.get_sync_status()

@mcp.tool()
async def classify_emails(email_ids: list[str], classification: str) -> dict:
    """Classify emails as 'keep' or 'junk'. Accepts list of email IDs."""
    return await _tools.classify_emails(email_ids, classification)

@mcp.tool()
async def classify_by_sender(sender_email: str, classification: str) -> dict:
    """Classify all emails from a sender address as 'keep' or 'junk'."""
    return await _tools.classify_by_sender(sender_email, classification)

@mcp.tool()
async def delete_emails(email_ids: list[str], confirm: bool = False) -> dict:
    """Delete specific emails from Gmail by ID. Set confirm=True to execute."""
    return await _tools.delete_emails(email_ids, confirm=confirm)

@mcp.tool()
async def delete_by_filter(filter_rules: dict, confirm: bool = False,
                           permanent: bool = False) -> dict:
    """Bulk delete emails matching a filter. Requires confirm=True."""
    return await _tools.delete_by_filter(filter_rules, confirm=confirm, permanent=permanent)

@mcp.tool()
async def create_schedule(name: str, cron_expression: str, filter_rules: dict,
                          require_classification: bool = True) -> dict:
    """Create a new deletion schedule with cron expression."""
    return await _tools.create_schedule(name, cron_expression, filter_rules, require_classification)

@mcp.tool()
async def update_schedule(schedule_id: int, name: str = "", cron_expression: str = "",
                          enabled: bool = True) -> dict:
    """Update an existing deletion schedule."""
    kwargs = {}
    if name: kwargs["name"] = name
    if cron_expression: kwargs["cron_expression"] = cron_expression
    kwargs["enabled"] = enabled
    return await _tools.update_schedule(schedule_id, **kwargs)

@mcp.tool()
async def list_schedules() -> list:
    """List all deletion schedules."""
    return await _tools.list_schedules()

@mcp.tool()
async def delete_schedule(schedule_id: int) -> dict:
    """Remove a deletion schedule."""
    return await _tools.delete_schedule(schedule_id)

@mcp.tool()
async def create_rule(name: str, rule_type: str, pattern: str,
                      classification: str, priority: int = 100) -> dict:
    """Create a classification rule. Types: sender, domain, label, keyword, size."""
    return await _tools.create_rule(name, rule_type, pattern, classification, priority)

@mcp.tool()
async def update_rule(rule_id: int, name: str = "", pattern: str = "",
                      classification: str = "", priority: int = -1) -> dict:
    """Update a classification rule."""
    kwargs = {}
    if name: kwargs["name"] = name
    if pattern: kwargs["pattern"] = pattern
    if classification: kwargs["classification"] = classification
    if priority >= 0: kwargs["priority"] = priority
    return await _tools.update_rule(rule_id, **kwargs)

@mcp.tool()
async def list_rules() -> list:
    """List all classification rules ordered by priority."""
    return await _tools.list_rules()

@mcp.tool()
async def delete_rule(rule_id: int) -> dict:
    """Remove a classification rule."""
    return await _tools.delete_rule(rule_id)

@mcp.tool()
async def get_config() -> dict:
    """Read current app configuration."""
    return await _tools.get_config()

@mcp.tool()
async def update_config(sync_interval_minutes: int = -1) -> dict:
    """Update app settings. Pass -1 to leave unchanged."""
    kwargs = {}
    if sync_interval_minutes >= 0:
        kwargs["sync_interval_minutes"] = sync_interval_minutes
    return await _tools.update_config(**kwargs)

# --- MCP Resources ---
@mcp.resource("email://stats")
async def resource_stats() -> dict:
    """Current archive statistics."""
    return await _tools.get_stats()

@mcp.resource("email://sync-status")
async def resource_sync_status() -> dict:
    """Live sync progress."""
    return await _tools.get_sync_status()

@mcp.resource("email://schedules")
async def resource_schedules() -> list:
    """All deletion schedules."""
    return await _tools.list_schedules()

@mcp.resource("email://rules")
async def resource_rules() -> list:
    """All classification rules."""
    return await _tools.list_rules()

@mcp.resource("email://recent-deletions")
async def resource_recent_deletions() -> list:
    """Last 50 deletion log entries."""
    rows = await _tools._db.execute_fetchall(
        "SELECT * FROM deletion_log ORDER BY deleted_at DESC LIMIT 50"
    )
    return [dict(r) for r in rows]
```

- [ ] **Step 6: Run MCP tests**

Run: `pytest tests/test_mcp_tools.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/mcp/ tests/test_mcp_tools.py pyproject.toml
git commit -m "feat: MCP server with 20 tools for full agent orchestration"
```

---

## Task 9: React Frontend

**Files:**
- Create: all `app/frontend/` files listed in file map
- Modify: `app/main.py` (add static file serving)

- [ ] **Step 1: Scaffold React app with Vite**

```bash
cd /Users/peng/Documents/Sandbox/email-management/app
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom
```

- [ ] **Step 2: Create API client**

Create `app/frontend/src/api.ts`:

```typescript
const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export const api = {
  searchEmails: (params: Record<string, string>) =>
    request(`/emails?${new URLSearchParams(params)}`),
  getEmail: (id: string) => request(`/emails/${id}`),
  classifyEmail: (id: string, classification: string) =>
    request(`/emails/${id}`, { method: 'PATCH', body: JSON.stringify({ classification }) }),
  bulkClassify: (emailIds: string[], classification: string) =>
    request('/emails/classify-bulk', { method: 'POST', body: JSON.stringify({ email_ids: emailIds, classification }) }),
  getStats: () => request('/stats'),
  getSyncStatus: () => request('/sync/status'),
  triggerSync: (full = false) => request(`/sync?full=${full}`, { method: 'POST' }),
  getAuthStatus: () => request('/auth/status'),
  startAuth: () => request('/auth/start', { method: 'POST' }),
  listSchedules: () => request('/schedules'),
  createSchedule: (data: any) => request('/schedules', { method: 'POST', body: JSON.stringify(data) }),
  deleteSchedule: (id: number) => request(`/schedules/${id}`, { method: 'DELETE' }),
  listRules: () => request('/rules'),
  createRule: (data: any) => request('/rules', { method: 'POST', body: JSON.stringify(data) }),
  deleteRule: (id: number) => request(`/rules/${id}`, { method: 'DELETE' }),
};
```

- [ ] **Step 3: Create App shell with routing**

Replace `app/frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Search from './pages/Search';
import ReviewQueue from './pages/ReviewQueue';
import Schedules from './pages/Schedules';
import Settings from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="navbar">
          <span className="logo">GmailVault</span>
          <div className="nav-links">
            <NavLink to="/">Dashboard</NavLink>
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/review">Review</NavLink>
            <NavLink to="/schedules">Schedules</NavLink>
            <NavLink to="/settings">Settings</NavLink>
          </div>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/search" element={<Search />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/schedules" element={<Schedules />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: Create page components**

Create each page as a functional component using the `api` client. Each page should:
- **Dashboard** (`pages/Dashboard.tsx`): Fetch stats and sync status on mount, display 4 stat cards and status info
- **Search** (`pages/Search.tsx`): Search input with filter dropdowns, paginated email list, bulk classify buttons
- **ReviewQueue** (`pages/ReviewQueue.tsx`): Fetch unclassified emails grouped by sender_email, show count per group, Keep All / Junk All buttons
- **Schedules** (`pages/Schedules.tsx`): List schedules and rules, create/delete forms for each
- **Settings** (`pages/Settings.tsx`): Show auth status, sync config, R2 config status

Create shared components:
- **StatsCard** (`components/StatsCard.tsx`): Colored stat card with count and label
- **EmailRow** (`components/EmailRow.tsx`): Email row with checkbox, sender, subject, snippet, date, classification badge, .eml download
- **ClassificationBadge** (`components/ClassificationBadge.tsx`): Colored badge (green=keep, red=junk, yellow=unclassified)
- **SenderGroup** (`components/SenderGroup.tsx`): Expandable sender group with email count and bulk action buttons

*(Full component code follows the patterns shown in the UI mockups from brainstorming — see spec for layout details)*

- [ ] **Step 5: Configure Vite proxy**

Create `app/frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
```

- [ ] **Step 6: Add CSS styling**

Replace `app/frontend/src/index.css` with styles matching the dark theme from the mockups: dark background (#0f0f0f), subtle borders, indigo accent (#818cf8), clean typography.

- [ ] **Step 7: Build and configure static serving**

```bash
cd /Users/peng/Documents/Sandbox/email-management/app/frontend && npm run build
```

Update `app/main.py` to serve the built frontend:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# Inside create_app(), after all routers:
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(frontend_dist / "index.html")
```

- [ ] **Step 8: Test manually**

Run: `cd /Users/peng/Documents/Sandbox/email-management && uvicorn app.main:app --reload`
Open: http://localhost:8000
Expected: Dashboard loads with zero stats, navigation works between all pages

- [ ] **Step 9: Commit**

```bash
git add app/frontend/ app/main.py
git commit -m "feat: React frontend with dashboard, search, review queue, and schedule management"
```

---

## Task 10: Wire Everything Together & Integration Test

**Files:**
- Modify: `app/main.py` (full lifespan with all services)
- Create: `tests/test_integration.py`

- [ ] **Step 1: Update main.py lifespan to initialize all services**

Update `app/main.py` lifespan to create and wire: TaskManager, GmailService (if credentials exist), R2Service (if configured), Classifier, SyncManager, DeletionManager, SchedulerService, McpTools. Mount MCP SSE endpoint.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()

    task_manager = TaskManager()
    classifier = Classifier(db)

    # Gmail (optional — only if credentials exist)
    gmail = None
    if settings.client_secret_path.exists():
        gmail = GmailService(settings.client_secret_path, settings.token_path)
        gmail.authenticate()

    # R2 (optional — only if configured)
    r2 = None
    if settings.r2_access_key_id:
        r2 = R2Service(settings)

    # Managers
    sync_manager = SyncManager(db, gmail, r2, classifier, task_manager) if gmail else None
    deletion_manager = DeletionManager(db, gmail, task_manager) if gmail else None

    # Scheduler
    scheduler = SchedulerService(db)
    if deletion_manager:
        scheduler.set_deletion_manager(deletion_manager)
    await scheduler.start()

    # Wire into API modules
    from app.api.sync import init_sync
    from app.api.schedules import init_scheduler
    init_sync(task_manager, sync_manager)
    init_scheduler(scheduler)

    # MCP
    mcp_tools = McpTools(
        db=db, search=SearchService(db), classifier=classifier,
        task_manager=task_manager, gmail=gmail, r2=r2,
        sync_manager=sync_manager, deletion_manager=deletion_manager,
        scheduler=scheduler,
    )
    from app.mcp.server import init_mcp_tools
    init_mcp_tools(mcp_tools)

    yield

    scheduler.stop()
    await db.close()
```

- [ ] **Step 2: Write integration test**

Create `tests/test_integration.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app

@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.db_path", tmp_path / "test.db")
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

async def test_full_workflow(client):
    """End-to-end: stats → create rule → create schedule → verify."""
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
    assert resp.json()[0]["name"] == "Weekly Cleanup"

    # Verify rule exists
    resp = await client.get("/api/rules")
    assert len(resp.json()) == 1

    # Health check
    resp = await client.get("/api/health")
    assert resp.json()["status"] == "ok"

    # Auth status (no credentials in test)
    resp = await client.get("/api/auth/status")
    assert resp.json()["authenticated"] == False
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_integration.py
git commit -m "feat: wire all services together with full lifespan and integration test"
```

---

## Task 11: MCP Configuration File

**Files:**
- Create: `.mcp.json`

- [ ] **Step 1: Create MCP config for Claude Code**

Create `.mcp.json` at project root:

```json
{
  "mcpServers": {
    "gmail-vault": {
      "type": "sse",
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

- [ ] **Step 2: Mount MCP SSE in main.py**

Add to `create_app()` after MCP init in lifespan:

```python
from app.mcp.server import mcp
# Mount MCP SSE transport
app.mount("/mcp", mcp.sse_app())
```

- [ ] **Step 3: Commit**

```bash
git add .mcp.json app/main.py
git commit -m "feat: MCP SSE endpoint and configuration for Claude Code"
```

---

## Summary

| Task | What it builds | Key tests |
|------|---------------|-----------|
| 1 | Project scaffold, SQLite, schema, FTS5 | Schema creation, WAL mode, FTS5 search |
| 2 | Search service + email API | Keyword search, pagination, filters, CRUD |
| 3 | Classification rule engine + rules API | Priority ordering, 5 rule types, CRUD |
| 4 | R2 storage service | Upload, presigned URL, delete (mocked) |
| 5 | Gmail service + OAuth | Message ops, history API, auth flow |
| 6 | Sync manager + background tasks | Concurrency locks, batch processing |
| 7 | Deletion manager + scheduler | Batch deletion, cron schedules, logging |
| 8 | MCP server | 20 tools, full orchestration |
| 9 | React frontend | Dashboard, search, review, schedules UI |
| 10 | Integration wiring | End-to-end workflow test |
| 11 | MCP config | Claude Code integration |

**Each task produces a working, testable increment.** Tasks 1-8 are the backend core. Task 9 is the frontend. Tasks 10-11 wire everything together.
