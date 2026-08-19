#!/usr/bin/env bash
#
# One-command setup for the RAG project.
#
# Usage:
#   ./setup.sh              # backend + frontend + postgres (LLM_PROVIDER from .env)
#   ./setup.sh --with-ollama    # also start local Ollama and pull the model
#
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

info()  { echo -e "${BOLD}==>${RESET} $1"; }
ok()    { echo -e "${GREEN}✔${RESET} $1"; }
warn()  { echo -e "${YELLOW}!${RESET} $1"; }
fail()  { echo -e "${RED}✘ $1${RESET}"; exit 1; }

WITH_OLLAMA=false
for arg in "$@"; do
  case "$arg" in
    --with-ollama) WITH_OLLAMA=true ;;
    *) warn "Unknown argument: $arg (ignored)" ;;
  esac
done

# ---------------------------------------------------------------------------
# 1. Preflight checks
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || fail "Docker is not installed or not on PATH. Install Docker Desktop first: https://www.docker.com/products/docker-desktop"
docker compose version >/dev/null 2>&1 || fail "'docker compose' is not available. Update Docker Desktop / the Compose plugin."
docker info >/dev/null 2>&1 || fail "Docker does not appear to be running. Start Docker Desktop and try again."
ok "Docker is installed and running"

# ---------------------------------------------------------------------------
# 2. Ensure .env exists
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    fail ".env.example not found — are you running this from the project root?"
  fi
  cp .env.example .env
  ok "Created .env from .env.example (default: local embeddings + Ollama LLM)"
else
  ok ".env already exists — leaving it as-is"
fi

# ---------------------------------------------------------------------------
# 3. Build images
# ---------------------------------------------------------------------------
info "Building images (this can take several minutes the first time)..."
docker compose build
ok "Images built"

# ---------------------------------------------------------------------------
# 4. Start core services
# ---------------------------------------------------------------------------
info "Starting postgres, backend, and frontend..."
docker compose up -d postgres backend frontend
ok "Core services started"

# ---------------------------------------------------------------------------
# 5. Start Ollama if requested
# ---------------------------------------------------------------------------
if [ "$WITH_OLLAMA" = true ]; then
  info "Starting Ollama..."
  docker compose --profile ollama up -d ollama
  ok "Ollama started"
fi

# ---------------------------------------------------------------------------
# 6. Wait for backend to report healthy
# ---------------------------------------------------------------------------
info "Waiting for the backend to become healthy..."
ATTEMPTS=0
MAX_ATTEMPTS=30
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
    fail "Backend did not become healthy in time. Check logs with: docker compose logs backend"
  fi
  sleep 2
done
ok "Backend is healthy"

# ---------------------------------------------------------------------------
# 7. Run database migrations
# ---------------------------------------------------------------------------
info "Running database migrations..."
docker compose exec -T backend alembic upgrade head
ok "Migrations applied"

# ---------------------------------------------------------------------------
# 8. Pull the Ollama model if requested
# ---------------------------------------------------------------------------
if [ "$WITH_OLLAMA" = true ]; then
  MODEL=$(grep -E '^LLM_MODEL=' .env | cut -d '=' -f2- || echo "llama3.1")
  MODEL=${MODEL:-llama3.1}
  info "Pulling Ollama model '$MODEL' (this can take a while for the first pull)..."
  docker compose exec -T ollama ollama pull "$MODEL"
  ok "Model '$MODEL' ready"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo
ok "Setup complete!"
echo -e "  Web UI:       ${BOLD}http://localhost:3000${RESET}"
echo -e "  API docs:     ${BOLD}http://localhost:8000/docs${RESET}"
echo -e "  Health check: ${BOLD}http://localhost:8000/api/v1/health/ready${RESET}"
if [ "$WITH_OLLAMA" = false ]; then
  echo
  warn "Ollama was not started. If .env has LLM_PROVIDER=ollama (the default), chat"
  warn "requests will fail until you run: ./setup.sh --with-ollama"
  warn "(or set LLM_PROVIDER=openai / openai_compatible with a valid API key in .env)"
fi
