# GmailVault — Design Specification

**Date:** 2026-03-24
**Status:** Approved

## Overview

GmailVault is a local-first web application for managing, archiving, and searching Gmail at scale. It syncs emails from Gmail, exports non-junk emails as `.eml` files to Cloudflare R2, provides full-text and (future) semantic search over a local SQLite index, and supports scheduled bulk deletion from Gmail — all controllable via a browser UI or MCP-compatible AI agents.

**Target scale:** 500K+ emails.

## Architecture

**Modular Monolith** — a single FastAPI process with clean internal boundaries:

- **Web Routes** — serves React SPA, handles API requests
- **REST API** — CRUD endpoints for emails, sync, schedules, rules, stats
- **MCP Server** — SSE/Streamable HTTP transport, exposes 20 tools and 5 resources for full agent orchestration
- **Background Task Manager** — async tasks for Gmail sync, classification, deletion, `.eml` export. Progress reported to UI via SSE.
- **Scheduler (APScheduler)** — cron-based deletion schedules, periodic incremental sync. Job store persisted in SQLite.

All components share a single SQLite database (WAL mode for concurrent read/write) and communicate in-process.

### Why This Architecture

- One process to run — no Redis, no Celery, no multi-service coordination
- Background tasks (sync, delete) never block the web UI
- SQLite WAL mode handles concurrent access from web requests + background tasks
- APScheduler persists jobs in SQLite — schedules survive restarts
- MCP server is additional FastAPI routes on the same app — no separate process

## Data Model

### Core Tables

**emails**
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Gmail message ID |
| thread_id | TEXT | Gmail thread ID |
| subject | TEXT | |
| sender | TEXT | Display name |
| sender_email | TEXT | Email address |
| recipients | JSON | To/CC/BCC |
| date | DATETIME | |
| snippet | TEXT | Gmail preview text |
| body_text | TEXT | Plain text body |
| body_html | TEXT | HTML body |
| labels | JSON | Gmail labels |
| size_bytes | INTEGER | |
| has_attachments | BOOLEAN | |
| classification | TEXT | 'keep' \| 'junk' \| 'unclassified' |
| classification_reason | TEXT | |
| eml_path | TEXT | R2 object key (null for junk) |
| synced_at | DATETIME | |
| classified_at | DATETIME | When classification last changed |
| updated_at | DATETIME | |
| deleted_from_gmail | BOOLEAN | DEFAULT FALSE |
| deletion_type | TEXT | 'trashed' \| 'permanently_deleted' \| null |

**attachments**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| email_id | TEXT FK | → emails.id |
| filename | TEXT | |
| mime_type | TEXT | |
| size_bytes | INTEGER | |

Metadata only — actual attachment data lives inside the `.eml` file in R2. Individual attachment download requires parsing the `.eml` from R2 (deferred to a future phase).

### Database Migrations

Schema version tracked in a `schema_version` table. Migrations are inline DDL scripts that run on startup — each migration checks the current version and applies incremental changes. No external migration tool required.

**sync_state** (single-row table — single Gmail account)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Always 1 |
| account_email | TEXT | Gmail address being synced |
| last_history_id | TEXT | Gmail incremental sync cursor |
| last_full_sync | DATETIME | |
| total_messages | INTEGER | |
| synced_messages | INTEGER | |

**deletion_schedules**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT | |
| cron_expression | TEXT | e.g., "0 2 * * 0" |
| filter_rules | JSON | Which emails to target |
| require_classification | BOOLEAN | Only delete if classified junk |
| enabled | BOOLEAN | |
| last_run | DATETIME | |
| created_at | DATETIME | |

**deletion_log**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| schedule_id | INTEGER FK | Nullable |
| email_id | TEXT FK | → emails.id |
| deleted_at | DATETIME | |
| trigger | TEXT | 'scheduled' \| 'manual' \| 'agent' |

**classification_rules**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT | |
| rule_type | TEXT | 'sender' \| 'domain' \| 'label' \| 'keyword' \| 'size' |
| pattern | TEXT | |
| classification | TEXT | 'junk' \| 'keep' |
| priority | INTEGER | Lower = higher priority |
| enabled | BOOLEAN | |
| created_at | DATETIME | |

### Search Indexes

**FTS5 (Full-Text Search)** — `emails_fts` virtual table indexing `subject`, `sender`, `body_text`, `snippet`. Supports keyword search, phrase matching, prefix queries, boolean operators (AND/OR/NOT), and column-scoped search (`subject:invoice`). FTS5 indexes content columns only — classification changes don't require re-indexing. Emails deleted from Gmail remain searchable in the local index (the archive is permanent).

**Vector Search (Phase 2)** — `email_embeddings` table with `email_id` + `embedding` BLOB. Uses sqlite-vec extension or in-process FAISS. Populated on-demand, not required for v1.

### Storage

- **SQLite database:** ~3-6 GB for 500K emails (metadata + body text + FTS5 index)
- **R2:** ~10-20 GB for `.eml` files (non-junk emails only)
- **R2 cost:** ~$0.15/month for storage, no egress fees
- **R2 structure:** `{bucket}/{YYYY}/{MM}/{gmail-message-id}.eml`

## Gmail Integration

### Authentication

OAuth 2.0 with guided setup:
1. App walks user through creating a Google Cloud project and enabling Gmail API
2. User downloads `client_secret.json` into `credentials/`
3. App handles OAuth consent flow and stores `token.json`
4. Automatic token refresh

### Task Concurrency

Background tasks follow these mutual exclusion rules:
- **Only one sync at a time.** If a sync is triggered while one is running, it is queued and starts after the current sync completes.
- **Deletion waits for active sync.** Scheduled or manual deletion jobs check for a running sync and wait for it to finish before executing, to avoid deleting emails mid-sync.
- **Classification can run concurrently** with sync and deletion — it only updates the `classification` column via short transactions.
- Enforced via an in-process asyncio Lock per task type.

### Sync Flow

1. Acquire sync lock (reject if already running, or queue)
2. Check `sync_state` for `last_history_id`
3. **First sync:** paginated `messages.list` (500 per batch via Gmail batch API)
4. **Incremental sync:** `history.list` since last history ID. **If Gmail returns 404 (history ID expired), fall back to full sync and log a warning.**
5. For each message batch:
   a. Fetch full message metadata via batch API
   b. Download raw `.eml` via `format=RAW`
   c. Run classification rules — if not classified as junk, upload `.eml` to R2
   d. Parse metadata → insert into SQLite
   e. Update FTS5 index
   f. Generate classification suggestion
6. Update `sync_state` with new history ID
7. Report progress via SSE to UI
8. Release sync lock

### Deletion Flow

1. APScheduler fires cron trigger (or manual/agent trigger)
2. Wait for any active sync to complete
3. Load schedule's `filter_rules`
4. Query matching emails
5. If `require_classification` is true, filter to `classification='junk'` only
6. Batch delete via Gmail API in groups of 100 (Gmail batch API limit), with exponential backoff on rate limits
7. Default behavior is **trash** (recoverable). Permanent delete requires explicit `permanent: true` in schedule config.
8. Mark `deleted_from_gmail = true` and set `deletion_type` in SQLite
9. Log each deletion in `deletion_log`
10. `.eml` files in R2 are **kept** (local archive is permanent)
11. Report progress via SSE with running count (e.g., "deleted 1,200 / 2,340")
12. Send summary notification via SSE

### Reclassification and Retroactive Export

When an email is reclassified from junk to keep:
1. If `eml_path` is null and the email still exists in Gmail (`deleted_from_gmail = false`), re-fetch the raw `.eml` from Gmail and upload to R2.
2. If the email has already been deleted from Gmail, mark `eml_path` as `'unrecoverable'` — the email metadata remains searchable but the original file cannot be retrieved.

## Classification System

### Rule Engine

Rules are evaluated in priority order (lower number = higher priority). First matching rule wins. Rule types:

- **sender** — exact email match (`newsletter@medium.com`)
- **domain** — wildcard domain match (`*.marketing.*`)
- **label** — Gmail label match (`CATEGORY_PROMOTIONS`)
- **keyword** — subject/body keyword match (`unsubscribe`)
- **size** — size threshold (`>5MB`)

### Suggestions

Emails that don't match any rule get auto-suggestions based on heuristics:
- Presence of unsubscribe link → suggest junk
- Gmail category (Promotions, Social) → suggest junk
- Personal sender (appears in sent mail) → suggest keep
- High engagement (replied to, starred) → suggest keep

Suggestions are displayed in the Review Queue but never acted on automatically.

## Web UI

React SPA served as static files by FastAPI. Four main views:

### Dashboard
- Stats cards: synced, keep, junk, unclassified counts
- Sync status with last sync time and next auto-sync
- Next scheduled deletion preview with match count

### Search
- Full-text search bar with FTS5 query syntax
- Filters: classification, has attachments, date range, size
- Results: sender, snippet, classification badge, date
- "Download .eml" link on non-junk emails (fetches pre-signed R2 URL)
- Bulk select for reclassification

### Review Queue
- Unclassified emails grouped by sender
- Shows email count per sender and classification suggestion with reasoning
- "Keep All" / "Junk All" per sender group for fast batch classification
- Expandable to review individual emails
- Sort by: sender groups, chronological, by suggestion confidence

### Schedules & Rules
- CRUD for deletion schedules (name, cron expression, filter rules, enabled toggle)
- CRUD for classification rules (type, pattern, classification, priority)
- Preview of next scheduled run with match count

## MCP Server

Exposed via SSE or Streamable HTTP transport on the same FastAPI app. Full orchestration capability.

### Tools (20)

**Search & Read:**
- `search_emails` — query with filters, paginated results
- `get_email` — full email details by ID
- `download_eml` — pre-signed R2 URL for `.eml` file
- `get_stats` — archive statistics

**Sync & Classify:**
- `trigger_sync` — start incremental or full sync, returns task ID
- `get_sync_status` — check sync progress
- `classify_emails` — classify one or more emails by ID
- `classify_by_sender` — classify all emails from a sender/domain

**Delete & Schedule:**
- `delete_emails` — delete specific emails from Gmail by ID
- `delete_by_filter` — bulk delete matching filter (requires `confirm: true`)
- `create_schedule` — new deletion schedule
- `update_schedule` — modify existing schedule
- `list_schedules` — list all schedules
- `delete_schedule` — remove a schedule

**Rules & Config:**
- `create_rule` — new classification rule
- `update_rule` — modify existing rule
- `list_rules` — list all rules
- `delete_rule` — remove a rule
- `get_config` — read app configuration
- `update_config` — modify app settings

### Resources (5)
- `email://stats` — current archive statistics
- `email://sync-status` — live sync progress
- `email://schedules` — all deletion schedules
- `email://rules` — all classification rules
- `email://recent-deletions` — last 50 deletion log entries

## Project Structure

```
email-management/
├── pyproject.toml
├── app/
│   ├── main.py                # FastAPI app + lifespan
│   ├── config.py              # Settings (paths, OAuth, R2, schedules)
│   ├── database.py            # SQLite connection + migrations
│   ├── models.py              # Pydantic models
│   ├── api/                   # REST API routes
│   │   ├── emails.py
│   │   ├── sync.py
│   │   ├── schedules.py
│   │   ├── rules.py
│   │   └── stats.py
│   ├── services/              # Business logic
│   │   ├── gmail.py           # Gmail API client + .eml export
│   │   ├── r2.py              # R2 upload/download/presign
│   │   ├── search.py          # FTS5 + vector search
│   │   ├── classifier.py      # Rule engine + suggestions
│   │   ├── scheduler.py       # APScheduler setup
│   │   └── sync_manager.py    # Orchestrates sync + export
│   ├── mcp/                   # MCP server
│   │   ├── server.py          # MCP protocol handler
│   │   └── tools.py           # Tool definitions
│   └── frontend/              # React SPA
│       ├── src/
│       ├── package.json
│       └── dist/              # Built static files served by FastAPI
├── data/                      # SQLite database files
│   └── emails.db
└── credentials/               # OAuth tokens (gitignored)
    ├── client_secret.json
    └── token.json
```

## Key Dependencies

- **FastAPI** + **uvicorn** — web framework + ASGI server
- **google-api-python-client** + **google-auth-oauthlib** — Gmail API
- **boto3** — R2 (S3-compatible API)
- **APScheduler** — cron-based job scheduling
- **aiosqlite** — async SQLite access
- **React** + **Vite** — frontend SPA
- **mcp** — MCP Python SDK for server implementation

## Error Handling

- **Gmail rate limits:** exponential backoff with jitter, respect 429 responses
- **Sync interruption:** resumable from last checkpoint (history ID or page token)
- **R2 upload failure:** retry with backoff, mark email as `eml_path=null` and retry on next sync
- **SQLite contention:** WAL mode minimizes this; background tasks use short transactions
- **OAuth token expiry:** automatic refresh; if refresh fails, prompt re-auth via UI

## Security

- OAuth tokens stored in `credentials/` directory (gitignored)
- R2 credentials via environment variables: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` (or in `.env` file, gitignored)
- MCP server binds to localhost only by default
- `delete_by_filter` requires explicit `confirm: true` parameter
- No email content sent to external services (classification is local rule-based)
