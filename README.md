# GmailVault

> **Local use only.** This application is designed to run on your local machine. It has no authentication on its API endpoints and should not be exposed to the public internet.

Local-first Gmail management app. Sync, archive, search, classify, and bulk-delete emails — from a browser UI or via MCP from Claude Code.

## What it does

- **Syncs** emails from Gmail into a local SQLite database with full-text search (FTS5)
- **Archives** every email as `.eml` files to Cloudflare R2
- **Classifies** emails as Archive, Keep, Junk, or Unclassified using configurable rules
- **Deletes** archived/junk emails from Gmail to free space (kept in R2)
- **Schedules** recurring bulk deletions via cron
- **Exposes** 20 MCP tools for agent orchestration

## Classification model

| Status | In R2 | In Gmail | Purpose |
|--------|-------|----------|---------|
| **Archive** | Yes | Deleted | Free Gmail space, kept locally |
| **Keep** | Yes | Stays | Important, want in both places |
| **Junk** | Yes | Deleted | Trash, but recoverable locally |
| **Unclassified** | Yes | Stays | Default until reviewed |

## Prerequisites

- Python 3.12+
- Node.js 18+ (for frontend build)
- A Google account with Gmail
- A Cloudflare account (free tier works)

## Setup

### 1. Install dependencies

```bash
pip install -e ".[dev]"
```

### 2. Gmail API credentials

You need OAuth 2.0 credentials so the app can access your Gmail.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Library**
4. Search for **Gmail API** and click **Enable**
5. Navigate to **APIs & Services > Credentials**
6. Click **Create Credentials > OAuth client ID**
7. If prompted, configure the **OAuth consent screen** first:
   - User type: **External**
   - Fill in app name (e.g., "GmailVault") and your email
   - Scopes: add `https://www.googleapis.com/auth/gmail.modify`
   - Test users: **add your Gmail address** (required while app is in "Testing" mode)
8. Back in Credentials, create the OAuth client:
   - Application type: **Web application**
   - Name: anything (e.g., "GmailVault")
   - Authorized redirect URIs: add `http://localhost:8080/api/auth/callback`
9. Click **Create**, then **Download JSON**
10. Save the file as `credentials/client_secret.json`

```bash
mkdir -p credentials
mv ~/Downloads/client_secret_*.json credentials/client_secret.json
```

### 3. Cloudflare R2 credentials

R2 stores your `.eml` email archive. Free tier covers 10 GB storage + 1M writes/month.

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Navigate to **R2 Object Storage**
3. Click **Create Bucket**, name it `emails`
4. Go to **R2 > Overview > Manage R2 API Tokens**
5. Click **Create API Token**
   - Permissions: **Object Read & Write**
   - Specify bucket: select `emails`
6. Copy the credentials shown

Now create your `.env`:

```bash
cp .env.example .env
```

Fill in the values:

```bash
# Your Cloudflare account ID (visible in the R2 dashboard URL or sidebar)
R2_ACCOUNT_ID=your_account_id

# From the API token you just created
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key

# The bucket name you created
R2_BUCKET_NAME=emails

# How often to auto-sync (minutes). Default: 3600 (1 hour)
SYNC_INTERVAL_MINUTES=3600

# Server port (change if 8080 is taken)
PORT=8080
HOST=0.0.0.0
```

### 4. Start the app

```bash
./start.sh
```

Open http://localhost:8080. You'll see a login page — click **Connect Gmail Account** to complete the OAuth flow. After authorizing, you're in.

### 5. First sync

On the Dashboard, set **Max emails** to a small number (e.g., 100) for your first sync to verify everything works. Click **Full Sync**. Once confirmed, set it to 0 (unlimited) for a full sync.

Full sync of 500K emails takes several hours due to Gmail API rate limits (~10 messages/sec). The sync checkpoints after every batch — if it crashes or you restart, it resumes from where it left off.

## Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `R2_ACCOUNT_ID` | | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | | R2 API token access key |
| `R2_SECRET_ACCESS_KEY` | | R2 API token secret key |
| `R2_BUCKET_NAME` | `emails` | R2 bucket for `.eml` storage |
| `SYNC_INTERVAL_MINUTES` | `60` | Auto-sync interval |
| `PORT` | `8080` | Server port |
| `HOST` | `0.0.0.0` | Server bind address |

Gmail OAuth uses file-based credentials (gitignored):
- `credentials/client_secret.json` — OAuth client config (you download this)
- `credentials/token.json` — auto-generated after first login (don't edit)

## Architecture

Single FastAPI process, no external dependencies beyond SQLite and R2:

```
FastAPI App
├── Web UI (React SPA)
├── REST API (/api/*)
├── MCP Server (/mcp/sse)
├── Background Tasks (sync, deletion)
├── APScheduler (cron jobs)
└── SQLite (WAL mode) + FTS5
```

- **Sync** fetches emails via Gmail API, parses raw `.eml`, indexes in SQLite, uploads to R2
- **Full sync** paginates through all messages with checkpointing (resumes on crash)
- **Incremental sync** uses Gmail history API for new messages only
- **Classification** applies rules by priority; unmatched emails go to Review Queue
- **Deletion** batches Gmail API calls (100/batch), deferred during active sync

## MCP integration

The app exposes an MCP server for use with Claude Code or any MCP client:

```json
// .mcp.json
{
  "mcpServers": {
    "gmail-vault": {
      "type": "sse",
      "url": "http://localhost:8080/mcp/sse"
    }
  }
}
```

20 tools: `search_emails`, `get_email`, `download_eml`, `get_stats`, `trigger_sync`, `get_sync_status`, `classify_emails`, `classify_by_sender`, `delete_emails`, `delete_by_filter`, `create_schedule`, `update_schedule`, `list_schedules`, `delete_schedule`, `create_rule`, `update_rule`, `list_rules`, `delete_rule`, `get_config`, `update_config`

## Project structure

```
email-management/
├── app/
│   ├── main.py              # FastAPI app, lifespan, service wiring
│   ├── config.py             # Settings from .env
│   ├── database.py           # SQLite + FTS5 + migrations
│   ├── models.py             # Pydantic models
│   ├── api/                  # REST endpoints
│   ├── services/             # Business logic
│   │   ├── gmail.py          # Gmail API client
│   │   ├── r2.py             # R2 storage
│   │   ├── search.py         # FTS5 search
│   │   ├── classifier.py     # Rule engine
│   │   ├── sync_manager.py   # Sync orchestration
│   │   ├── deletion_manager.py
│   │   ├── scheduler.py      # APScheduler
│   │   ├── task_manager.py   # Concurrency locks
│   │   └── registry.py       # Service registry
│   ├── mcp/                  # MCP server + tools
│   └── frontend/             # React SPA (Vite)
├── data/                     # SQLite database
├── credentials/              # OAuth tokens (gitignored)
├── start.sh                  # Start script
└── .env                      # Configuration (gitignored)
```

## Development

```bash
# Run tests
pytest tests/ -v

# Dev server with hot reload
./start.sh

# Rebuild frontend after changes
cd app/frontend && npm run build
```

## Security

This app is designed for **local use only**. Keep the following in mind:

- **No API authentication** — all endpoints are open. Anyone who can reach the server can read your emails, trigger syncs, and delete messages. Do not expose this to the internet.
- **Bind to localhost** — the default `HOST=0.0.0.0` listens on all interfaces, meaning other devices on your LAN can access it. Set `HOST=127.0.0.1` in `.env` if you only need local access.
- **Credentials are gitignored** — `credentials/`, `.env`, and `data/` are excluded from git. Never commit these.
- **OAuth tokens** — `credentials/token.json` grants full Gmail modify access. Treat it like a password.
- **R2 keys** — your `.env` contains R2 API keys with read/write access to your email archive bucket.

If you need to run this on a server or share access, add authentication middleware (e.g., API key or session auth) before exposing any ports.

## Costs

- **Gmail API**: Free (quota: 250 units/sec)
- **R2 storage**: Free under 10 GB, then $0.015/GB/month
- **R2 writes**: Free under 1M/month, then $4.50/million
- **R2 egress**: Always free
