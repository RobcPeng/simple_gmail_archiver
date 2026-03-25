#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ┌─────────────────────────────┐"
echo "  │       GmailVault v0.1.0     │"
echo "  └─────────────────────────────┘"
echo -e "${NC}"

# Check Python version
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Python 3 is required but not found.${NC}"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  Python:    ${GREEN}${PY_VERSION}${NC}"

# Install dependencies if needed
if ! python3 -c "import fastapi" &>/dev/null; then
    echo -e "\n${YELLOW}Installing dependencies...${NC}"
    pip install -e ".[dev]" --quiet
fi

# Create required directories
mkdir -p data credentials

# Check Gmail credentials
if [ -f credentials/client_secret.json ]; then
    echo -e "  Gmail:     ${GREEN}client_secret.json found${NC}"
else
    echo -e "  Gmail:     ${YELLOW}No credentials yet${NC}"
    echo -e "             Place client_secret.json in credentials/"
fi

# Check R2 config
if [ -n "${R2_ACCESS_KEY_ID:-}" ]; then
    echo -e "  R2:        ${GREEN}Configured${NC}"
else
    echo -e "  R2:        ${YELLOW}Not configured (set R2_* env vars or .env)${NC}"
fi

# Load .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo -e "  Env:       ${GREEN}.env loaded${NC}"
fi

# Server config from .env
PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

# Build frontend if dist is missing
if [ ! -d app/frontend/dist ]; then
    echo -e "\n${YELLOW}Building frontend...${NC}"
    cd app/frontend
    npm install --silent
    npm run build
    cd ../..
fi

echo -e "\n  ${CYAN}Starting server on http://localhost:${PORT}${NC}\n"

exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
